"""Deterministic formula generation for candidate minimum-point screens."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from horizonlink.canonical import (
    canonical_document_sha256,
    sha256_file,
    write_json,
    write_sha256_sidecar,
)
from horizonlink.pb import (
    build_candidate_minimum_set_formula,
    canonical_formula_sha256,
    normalized_native_row_sha256,
    write_candidate_screening_opb,
)


CORPUS_SCHEMA_VERSION = "horizonmath.candidate-screening-pb-corpus.v1"


def _formula_name(class_index: int | None, orbit_index: int) -> str:
    prefix = f"c{class_index:02d}" if class_index is not None else "unindexed"
    return f"{prefix}_candidate_orbit{orbit_index:02d}"


def generate_candidate_screening_corpus(
    structural_manifest: dict[str, Any],
    output_directory: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Emit one native OPB formula for every candidate-point-set orbit.

    The returned formulas exactly encode the historical ``full_minpoints``
    necessary-condition model.  This stage does not run a solver and does not
    authorize pruning any orbit.
    """

    if structural_manifest.get("status") != "ENUMERATED":
        raise ValueError("structural manifest must be ENUMERATED")
    if not structural_manifest.get("structural_audit", {}).get(
        "all_checks_passed"
    ):
        raise ValueError("structural audit must pass before formula generation")
    if output_directory.exists() and any(output_directory.iterdir()):
        raise ValueError("candidate screening output directory must be empty")

    manifest = copy.deepcopy(structural_manifest)
    structural_manifest_sha256 = canonical_document_sha256(manifest)
    normalized = manifest["input"]["normalized_document"]
    point_labels = tuple(normalized["point_labels"])
    link_blocks = tuple(tuple(block) for block in normalized["blocks"])
    class_index = manifest["input"]["class_index"]
    candidate_orbits = manifest["candidate_minimum_point_sets"]["orbits"]

    output_directory.mkdir(parents=True, exist_ok=True)
    instance_directory = output_directory / "instances"
    instance_directory.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    variable_map: list[dict[str, Any]] | None = None
    for orbit_index, orbit in enumerate(candidate_orbits):
        representative = tuple(orbit["representative"])
        built = build_candidate_minimum_set_formula(
            point_labels,
            link_blocks,
            representative,
        )
        if variable_map is None:
            variable_map = [
                {"variable": f"x{index + 1}", "block": list(block)}
                for index, block in enumerate(built["extension_blocks"])
            ]

        name = _formula_name(class_index, orbit_index)
        opb_path = instance_directory / f"{name}.opb"
        written = write_candidate_screening_opb(
            opb_path,
            built["rows"],
            variable_count=built["metadata"]["variables"],
            class_index=class_index if class_index is not None else 0,
            orbit_index=orbit_index,
            candidate_minimum_points=representative,
        )
        canonical_hash = canonical_formula_sha256(
            built["rows"],
            variable_count=built["metadata"]["variables"],
        )
        record = {
            "name": name,
            "class_index": class_index,
            "orbit_index": orbit_index,
            "candidate_minimum_points": list(representative),
            "candidate_orbit": {
                "member_count": len(orbit["members"]),
                "stabilizer_order": orbit["stabilizer_order"],
                "orbit_stabilizer_check": orbit[
                    "orbit_stabilizer_check"
                ],
            },
            "formula": {
                "path": opb_path.relative_to(output_directory).as_posix(),
                "bytes": written["bytes"],
                "sha256": written["sha256"],
                "canonical_formula_sha256": canonical_hash,
                "normalized_native_row_sha256": (
                    normalized_native_row_sha256(built["rows"])
                ),
                "variables": built["metadata"]["variables"],
                "matrix_rows": built["metadata"]["matrix_rows"],
                "opb_constraints": built["metadata"]["opb_constraints"],
                "serialized_family_counts": built["metadata"][
                    "serialized_family_counts"
                ],
            },
            "model": {
                "role": built["metadata"]["model_role"],
                "residual_four_sets": built["metadata"][
                    "residual_four_sets"
                ],
                "point_rows": built["metadata"]["point_rows"],
                "pair_rows": built["metadata"]["pair_rows"],
                "triple_rows": built["metadata"]["triple_rows"],
                "link_point_degrees": built["metadata"][
                    "link_point_degrees"
                ],
                "minimum_extension_degrees": built["metadata"][
                    "minimum_extension_degrees"
                ],
                "mathematical_reason": (
                    "Any 29-block extension with these candidate points at "
                    "full degree 15 must satisfy residual four-set coverage, "
                    "the induced point/pair/triple lower bounds, and exactly "
                    "14 extension blocks."
                ),
            },
            "prior_formula_comparison": {
                "status": "NOT_AVAILABLE",
                "reason": (
                    "The recovered archive contains the historical generator "
                    "source but no per-orbit full_minpoints formulas."
                ),
            },
            "status_ledger": {
                "formula": "FORMULAS_GENERATED",
                "root_lp": "NOT_STARTED",
                "solver": "NOT_STARTED",
                "proof": "NOT_STARTED",
                "verification": "NOT_STARTED",
            },
            "formal_pruning_authorized": False,
        }
        metadata_path = instance_directory / f"{name}.json"
        write_json(metadata_path, record)
        record["metadata"] = {
            "path": metadata_path.relative_to(output_directory).as_posix(),
            "sha256": sha256_file(metadata_path),
        }
        records.append(record)

    if variable_map is None:
        raise ValueError("candidate orbit partition is empty")
    expected_indices = list(range(len(candidate_orbits)))
    observed_indices = [record["orbit_index"] for record in records]
    all_orbits_accounted_for = observed_indices == expected_indices
    corpus_manifest = {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "status": (
            "FORMULAS_GENERATED" if all_orbits_accounted_for else "ERROR"
        ),
        "generator": {
            "id": "candidate-minimum-set-native-opb-v1",
            "runtime_dependencies": [],
            "variable_order": (
                "lexicographic 7-subsets of the labeled 12-point link ground set"
            ),
            "row_order": [
                "residual four-set coverage lower bounds",
                "point-degree lower bounds and selected-point equalities",
                "positive pair-degree lower bounds",
                "positive triple-degree lower bounds",
                "exact extension block count",
            ],
            "historical_model_source": "legacy_source/full_minpoints.py",
        },
        "input": {
            "class_index": class_index,
            "numbering_source": manifest["input"]["numbering_source"],
            "canonical_labeled_link_sha256": manifest["input"][
                "canonical_labeled_link_sha256"
            ],
            "canonical_link_document_sha256": manifest["input"][
                "canonical_document_sha256"
            ],
            "structural_manifest_canonical_sha256": (
                structural_manifest_sha256
            ),
            "automorphism_group_order": manifest["automorphism_group"][
                "order"
            ],
            "candidate_orbit_partition_sha256": manifest[
                "candidate_minimum_point_sets"
            ]["partition_sha256"],
        },
        "variable_count": len(variable_map),
        "variable_map": variable_map,
        "instances": records,
        "summary": {
            "candidate_orbits": len(candidate_orbits),
            "formulas_generated": len(records),
            "all_orbits_accounted_for": all_orbits_accounted_for,
            "orbit_indices": observed_indices,
            "unique_native_formula_hashes": len(
                {record["formula"]["sha256"] for record in records}
            ),
            "unique_canonical_formula_hashes": len(
                {
                    record["formula"]["canonical_formula_sha256"]
                    for record in records
                }
            ),
        },
        "scope": {
            "formulas_generated": True,
            "solver_run": False,
            "proof_generated": False,
            "verifier_run": False,
            "formal_orbit_pruning_authorized": False,
            "class_elimination_claimed": False,
        },
    }
    corpus_manifest_path = output_directory / "corpus.manifest.json"
    write_json(corpus_manifest_path, corpus_manifest)
    write_sha256_sidecar(corpus_manifest_path)

    checksum_targets = sorted(
        [
            path
            for path in output_directory.rglob("*")
            if path.is_file()
            and path.name != "SHA256SUMS"
            and not path.name.endswith(".sha256")
        ],
        key=lambda path: path.relative_to(output_directory).as_posix(),
    )
    checksum_path = output_directory / "SHA256SUMS"
    checksum_path.write_text(
        "".join(
            f"{sha256_file(path)}  "
            f"{path.relative_to(output_directory).as_posix()}\n"
            for path in checksum_targets
        ),
        encoding="utf-8",
    )

    manifest["candidate_screening_formula_generation"] = {
        "corpus_manifest": {
            "path": str(corpus_manifest_path),
            "sha256": sha256_file(corpus_manifest_path),
        },
        "summary": corpus_manifest["summary"],
        "status": corpus_manifest["status"],
    }
    manifest["status_ledger"][
        "candidate_screening_formulas"
    ] = corpus_manifest["status"]
    manifest["scope_guardrails"][
        "candidate_screening_formulas_generated"
    ] = True
    manifest["scope_guardrails"][
        "candidate_orbits_formally_pruned"
    ] = False
    manifest["status"] = corpus_manifest["status"]
    return manifest, corpus_manifest
