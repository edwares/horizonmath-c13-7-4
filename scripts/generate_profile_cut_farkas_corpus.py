#!/usr/bin/env python3
"""Generate exact VeriPB Farkas/CG proofs for candidate degree profiles."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from horizonlink.canonical import sha256_bytes, sha256_file, write_json
from horizonlink.farkas import (
    _dual_alternative,
    _exact_certificate,
    _render_verifier_opb,
    _render_veripb_proof,
)
from horizonlink.pb import PBRow, build_corrected_formula


def _dual_and_exact_with_threshold_retries(
    rows: tuple[PBRow, ...],
    variable_count: int,
    numpy_module,
    scipy_optimize,
    scipy_sparse,
):
    """Reconstruct an exact ray, relaxing only the floating support cutoff."""

    errors = []
    for support_threshold in (1e-9, 1e-10, 1e-11, 1e-12, 1e-13):
        alternative = _dual_alternative(
            rows,
            variable_count,
            numpy_module,
            scipy_optimize,
            scipy_sparse,
            support_threshold=support_threshold,
        )
        try:
            certificate = _exact_certificate(rows, variable_count, alternative)
        except ValueError as exc:
            errors.append(
                {
                    "support_threshold": support_threshold,
                    "error": str(exc),
                }
            )
            continue
        return alternative, certificate, {
            "support_threshold": support_threshold,
            "threshold_retry_count": len(errors),
        }
    raise ValueError(f"exact Farkas reconstruction failed: {errors}")


def _proof_term(tokens: list[str], operand: str, multiplier: int, first: bool) -> bool:
    tokens.extend([operand, str(multiplier), "*"])
    if not first:
        tokens.append("+")
    return False


def _normalized_row_text(row: PBRow) -> str:
    if row.relation == ">=":
        coefficient, rhs = "+1", row.rhs
    else:
        coefficient, rhs = "-1", -row.rhs
    return (
        " ".join(f"{coefficient} x{variable + 1}" for variable in row.variables)
        + f" >= {rhs} ;"
    )


def _derive_integrality_bound(
    current_rows: tuple[PBRow, ...],
    desired: PBRow,
    assumption: PBRow,
    variable_count: int,
    numpy_module,
    scipy_optimize,
    scipy_sparse,
) -> tuple[str, dict]:
    augmented = current_rows + (assumption,)
    alternative, certificate, reconstruction = _dual_and_exact_with_threshold_retries(
        augmented,
        variable_count,
        numpy_module,
        scipy_optimize,
        scipy_sparse,
    )
    assumption_id = len(augmented)
    assumption_items = [
        item
        for item in certificate["row_multipliers"]
        if int(item["row_id_1based"]) == assumption_id
    ]
    if len(assumption_items) != 1:
        raise ValueError("integrality-cut assumption is absent from Farkas support")
    divisor = int(assumption_items[0]["multiplier"])

    tokens: list[str] = []
    first = True
    for item in certificate["row_multipliers"]:
        if int(item["row_id_1based"]) == assumption_id:
            continue
        first = _proof_term(
            tokens,
            str(item["row_id_1based"]),
            int(item["multiplier"]),
            first,
        )
    for item in certificate["lower_bound_multipliers"]:
        first = _proof_term(
            tokens,
            f"x{item['variable']}",
            int(item["multiplier"]),
            first,
        )
    for item in certificate["upper_bound_multipliers"]:
        first = _proof_term(
            tokens,
            f"~x{item['variable']}",
            int(item["multiplier"]),
            first,
        )
    if first:
        raise ValueError("integrality-cut Farkas line has no global terms")
    tokens.extend([str(divisor), "d"])
    proof_line = "p " + " ".join(tokens)
    return proof_line, {
        "desired_relation": desired.relation,
        "desired_rhs": desired.rhs,
        "assumption_relation": assumption.relation,
        "assumption_rhs": assumption.rhs,
        "assumption_multiplier": divisor,
        "exact_contradiction_margin": certificate[
            "combined_rhs_after_bounds"
        ],
        "farkas_row_support_size": len(certificate["row_multipliers"]),
        "floating_support_reconstruction": reconstruction,
        "exact_checks": certificate["exact_checks"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("structural_manifest", type=Path)
    parser.add_argument("profile_census", type=Path)
    parser.add_argument("cut_census", type=Path)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--index", type=int, action="append")
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    args = parser.parse_args()
    if args.shard_count <= 0:
        raise ValueError("shard-count must be positive")
    if not 0 <= args.shard_index < args.shard_count:
        raise ValueError("shard-index is outside the shard count")

    import numpy
    import scipy
    import scipy.optimize
    import scipy.sparse

    structural = json.loads(args.structural_manifest.read_text(encoding="utf-8"))
    census = json.loads(args.profile_census.read_text(encoding="utf-8"))
    cuts = json.loads(args.cut_census.read_text(encoding="utf-8"))
    if args.output_directory.exists() and any(args.output_directory.iterdir()):
        raise ValueError("output directory must be empty")
    instances_dir = args.output_directory / "instances"
    instances_dir.mkdir(parents=True, exist_ok=True)

    normalized = structural["input"]["normalized_document"]
    point_labels = tuple(normalized["point_labels"])
    link_blocks = tuple(tuple(block) for block in normalized["blocks"])
    class_index = int(census["class_index"])
    cut_by_index = {int(row["index"]): row for row in cuts["instances"]}
    records = []
    selected_sources = [
        row
        for row in census["profiles"]
        if row["root_lp"]["status"] == "SOLVER_UNSAT"
        or cut_by_index.get(int(row["index"]), {}).get("status")
        == "LP_UNSAT_AFTER_INTEGRALITY_CUTS"
    ]
    if args.index:
        requested = set(args.index)
        selected_sources = [
            row for row in selected_sources if int(row["index"]) in requested
        ]
        if {int(row["index"]) for row in selected_sources} != requested:
            raise ValueError("a requested profile index is not formally closed")
    selected_sources = sorted(selected_sources, key=lambda row: int(row["index"]))
    unsharded_count = len(selected_sources)
    selected_sources = [
        row
        for source_ordinal, row in enumerate(selected_sources)
        if source_ordinal % args.shard_count == args.shard_index
    ]
    target_candidate_orbit = census.get("target_candidate_orbit")
    for ordinal, source in enumerate(selected_sources, start=1):
        started = time.monotonic()
        built = build_corrected_formula(
            point_labels, link_blocks, source["extension_degrees"]
        )
        base_rows = built["rows"]
        variable_count = built["metadata"]["variables"]
        name = (
            f"c{class_index:02d}_case{int(source['case_id']):03d}_"
            f"profile{int(source['profile_id']):03d}"
        )
        formula_path = instances_dir / f"{name}.verifier.opb"
        formula_bytes = _render_verifier_opb(
            base_rows,
            variable_count=variable_count,
            class_index=class_index,
            orbit_index=(
                None
                if target_candidate_orbit is None
                else int(target_candidate_orbit)
            ),
        )
        formula_path.write_bytes(formula_bytes)

        proof_metadata = []
        final_farkas_reconstruction = None
        cut_record = cut_by_index.get(int(source["index"]))
        if source["root_lp"]["status"] == "SOLVER_UNSAT":
            alternative, certificate, reconstruction = _dual_and_exact_with_threshold_retries(
                base_rows,
                variable_count,
                numpy,
                scipy.optimize,
                scipy.sparse,
            )
            proof_bytes = _render_veripb_proof(certificate, len(base_rows))
            method = "DIRECT_ROOT_LP_FARKAS"
            final_margin = certificate["combined_rhs_after_bounds"]
            derived_count = 0
            final_farkas_reconstruction = reconstruction
        else:
            if cut_record is None:
                raise ValueError("missing cut record")
            current_rows = base_rows
            lines = [
                "pseudo-Boolean proof version 1.0",
                f"f {len(base_rows)}",
            ]
            for cut in cut_record["cuts"]:
                pair = tuple(int(value) for value in cut["pair"])
                value = int(cut["value"])
                variables = tuple(
                    index
                    for index, block in enumerate(built["extension_blocks"])
                    if frozenset(pair) <= frozenset(block)
                )
                for side in ("lower", "upper"):
                    if side == "lower":
                        desired = PBRow(
                            variables, ">=", value,
                            "integrality_forced_pair", pair,
                        )
                        assumption = PBRow(
                            variables, "<=", value - 1,
                            "integrality_cut_negation", pair,
                        )
                    else:
                        desired = PBRow(
                            variables, "<=", value,
                            "integrality_forced_pair", pair,
                        )
                        assumption = PBRow(
                            variables, ">=", value + 1,
                            "integrality_cut_negation", pair,
                        )
                    proof_line, metadata = _derive_integrality_bound(
                        current_rows,
                        desired,
                        assumption,
                        variable_count,
                        numpy,
                        scipy.optimize,
                        scipy.sparse,
                    )
                    lines.append(proof_line)
                    derived_id = len(current_rows) + 1
                    exact_requested_bound = (
                        int(metadata["exact_contradiction_margin"])
                        <= int(metadata["assumption_multiplier"])
                    )
                    if exact_requested_bound:
                        lines.append(
                            f"e {derived_id} {_normalized_row_text(desired)}"
                        )
                    metadata.update(
                        {
                            "pair": list(pair),
                            "value": value,
                            "side": side,
                            "derived_constraint_id": derived_id,
                            "diagnostic_exact_equality_check_emitted": (
                                exact_requested_bound
                            ),
                            "derived_bound_strength": (
                                "EXACT_REQUESTED_BOUND"
                                if exact_requested_bound
                                else "STRICTLY_STRONGER_THAN_REQUESTED"
                            ),
                        }
                    )
                    proof_metadata.append(metadata)
                    current_rows = current_rows + (desired,)

            alternative, certificate, reconstruction = _dual_and_exact_with_threshold_retries(
                current_rows,
                variable_count,
                numpy,
                scipy.optimize,
                scipy.sparse,
            )
            tokens: list[str] = []
            first = True
            for item in certificate["row_multipliers"]:
                first = _proof_term(
                    tokens,
                    str(item["row_id_1based"]),
                    int(item["multiplier"]),
                    first,
                )
            for item in certificate["lower_bound_multipliers"]:
                first = _proof_term(
                    tokens,
                    f"x{item['variable']}",
                    int(item["multiplier"]),
                    first,
                )
            for item in certificate["upper_bound_multipliers"]:
                first = _proof_term(
                    tokens,
                    f"~x{item['variable']}",
                    int(item["multiplier"]),
                    first,
                )
            lines.append("p " + " ".join(tokens))
            contradiction_id = len(current_rows) + 1
            lines.append(f"c {contradiction_id}")
            proof_bytes = ("\n".join(lines) + "\n").encode("utf-8")
            method = "INTEGRALITY_PAIR_CUTS_THEN_ROOT_LP_FARKAS"
            final_margin = certificate["combined_rhs_after_bounds"]
            derived_count = len(current_rows) - len(base_rows)
            final_farkas_reconstruction = reconstruction

        proof_path = instances_dir / f"{name}.pbp"
        proof_path.write_bytes(proof_bytes)
        metadata_path = instances_dir / f"{name}.json"
        metadata_document = {
            "schema_version": "horizonmath.profile-cut-farkas-proof.v1",
            "index": source["index"],
            "case_id": source["case_id"],
            "profile_id": source["profile_id"],
            "method": method,
            "base_constraint_count": len(base_rows),
            "derived_integrality_bound_count": derived_count,
            "integrality_bounds": proof_metadata,
            "final_exact_farkas_margin": final_margin,
            "final_farkas_floating_support_reconstruction": (
                final_farkas_reconstruction
            ),
            "formula": {
                "path": formula_path.name,
                "sha256": sha256_bytes(formula_bytes),
                "bytes": len(formula_bytes),
            },
            "proof": {
                "path": proof_path.name,
                "sha256": sha256_bytes(proof_bytes),
                "bytes": len(proof_bytes),
            },
            "formal_status": "PROOF_GENERATED_NOT_YET_VERIFIED",
        }
        write_json(metadata_path, metadata_document)
        records.append(
            {
                "index": source["index"],
                "case_id": source["case_id"],
                "profile_id": source["profile_id"],
                "method": method,
                "formula": metadata_document["formula"],
                "proof": metadata_document["proof"],
                "metadata": {
                    "path": metadata_path.name,
                    "sha256": sha256_file(metadata_path),
                },
            }
        )
        print(
            f"[{ordinal}/{len(selected_sources)}] index={source['index']} "
            f"method={method} bounds={derived_count} "
            f"seconds={time.monotonic() - started:.3f}",
            flush=True,
        )

    manifest = {
        "schema_version": "horizonmath.profile-cut-farkas-corpus.v1",
        "class_index": class_index,
        "target_candidate_orbit": target_candidate_orbit,
        "profile_census_sha256": sha256_file(args.profile_census),
        "cut_census_sha256": sha256_file(args.cut_census),
        "selection": {
            "unsharded_instance_count": unsharded_count,
            "shard_count": args.shard_count,
            "shard_index": args.shard_index,
            "ordinal_rule": "zero_based_ordinal_mod_shard_count",
        },
        "instance_count": len(records),
        "instances": records,
        "status": "PROOFS_GENERATED_NOT_YET_VERIFIED",
    }
    manifest_path = args.output_directory / "corpus.manifest.json"
    write_json(manifest_path, manifest)
    print(json.dumps({
        "instances": len(records),
        "manifest": str(manifest_path),
        "sha256": sha256_file(manifest_path),
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
