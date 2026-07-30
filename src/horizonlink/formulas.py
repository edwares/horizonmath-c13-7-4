"""Generate a deterministic corrected native-OPB formula corpus."""

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
    build_corrected_formula,
    canonical_formula_sha256,
    normalized_native_row_sha256,
    write_native_opb,
)


def generate_formula_corpus(
    analysis_manifest: dict[str, Any],
    output_directory: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate every formula specified by the validated screening ledger.

    Returns ``(updated_analysis_manifest, corpus_manifest)``.  Solver, proof,
    and verifier stages remain ``NOT_STARTED`` for the current run.
    """

    if analysis_manifest.get("status") != "ENUMERATED":
        raise ValueError("analysis manifest must be ENUMERATED")
    if not analysis_manifest.get("screening", {}).get("comparison", {}).get(
        "all_checks_passed"
    ):
        raise ValueError("screening/profile regression must pass first")

    manifest = copy.deepcopy(analysis_manifest)
    input_analysis_manifest_sha256 = canonical_document_sha256(manifest)
    normalized = manifest["input"]["normalized_document"]
    point_labels = tuple(normalized["point_labels"])
    link_blocks = tuple(tuple(block) for block in normalized["blocks"])
    class_index = manifest["input"]["class_index"]
    if class_index is None:
        raise ValueError("formula filenames require a class index")

    profile_index = {
        (row["case_id"], row["profile_id"]): row
        for row in manifest["extension_degree_profiles"]["profiles"]
    }
    formula_plan = manifest["prior_formula_corpus"]["instances"]
    output_directory.mkdir(parents=True, exist_ok=True)
    instance_directory = output_directory / "instances"
    instance_directory.mkdir(parents=True, exist_ok=True)

    records = []
    for specification in formula_plan:
        name = specification["name"]
        key = (specification["case_id"], specification["profile_id"])
        if key not in profile_index:
            raise ValueError(f"formula {name} refers to an unknown profile")
        profile = profile_index[key]
        built = build_corrected_formula(
            point_labels,
            link_blocks,
            profile["extension_degrees"],
            split_pair=specification["split_pair"],
            split_value=specification["split_value"],
        )
        opb_path = instance_directory / f"{name}.opb"
        written = write_native_opb(
            opb_path,
            built["rows"],
            variable_count=built["metadata"]["variables"],
            class_index=class_index,
            case_id=key[0],
            profile_id=key[1],
            split_pair=specification["split_pair"],
            split_value=specification["split_value"],
        )
        canonical_hash = canonical_formula_sha256(
            built["rows"],
            variable_count=built["metadata"]["variables"],
        )
        normalized_row_hash = normalized_native_row_sha256(built["rows"])
        comparisons = {
            "native_formula_byte_hash_equal": (
                written["sha256"]
                == specification["native_formula_sha256"]
            ),
            "canonical_formula_hash_equal": (
                canonical_hash
                == specification["canonical_formula_sha256"]
            ),
            "prior_canonical_comparison_passed": specification[
                "canonical_comparison_passed"
            ],
            "prior_certificate_final_audit_passed": specification[
                "certificate_final_audit_passed"
            ],
        }
        comparisons["all_checks_passed"] = all(comparisons.values())
        record = {
            "name": name,
            "class_index": class_index,
            "case_id": key[0],
            "profile_id": key[1],
            "split_pair": specification["split_pair"],
            "split_value": specification["split_value"],
            "minimum_set": next(
                row["minimum_set"]
                for row in manifest["screening"][
                    "degree_profile_decisions"
                ]
                if (row["case_id"], row["profile_id"]) == key
            ),
            "degree_profile": profile["representative"],
            "extension_degrees": profile["extension_degrees"],
            "formula": {
                "path": opb_path.relative_to(output_directory).as_posix(),
                "bytes": written["bytes"],
                "sha256": written["sha256"],
                "canonical_formula_sha256": canonical_hash,
                "normalized_native_row_sha256": normalized_row_hash,
                "variables": built["metadata"]["variables"],
                "matrix_rows": built["metadata"]["matrix_rows"],
                "opb_constraints": built["metadata"]["opb_constraints"],
                "serialized_family_counts": built["metadata"][
                    "serialized_family_counts"
                ],
                "corrected_pair_upper_bound": built["metadata"][
                    "corrected_pair_upper_bound"
                ],
            },
            "prior_formula": {
                "native_formula_sha256": specification[
                    "native_formula_sha256"
                ],
                "canonical_formula_sha256": specification[
                    "canonical_formula_sha256"
                ],
                "published_formula_sha256": specification[
                    "published_formula_sha256"
                ],
                "published_proof_gzip_sha256": specification[
                    "published_proof_gzip_sha256"
                ],
                "status": specification["status"],
            },
            "comparison": comparisons,
            "status_ledger": {
                "formula": "FORMULAS_GENERATED",
                "solver": "NOT_STARTED",
                "proof": "NOT_STARTED",
                "verification": "NOT_STARTED",
            },
        }
        metadata_path = instance_directory / f"{name}.json"
        write_json(metadata_path, record)
        record["metadata"] = {
            "path": metadata_path.relative_to(output_directory).as_posix(),
            "sha256": sha256_file(metadata_path),
        }
        records.append(record)

    variable_map = [
        {"variable": f"x{index + 1}", "block": list(block)}
        for index, block in enumerate(
            build_corrected_formula(
                point_labels,
                link_blocks,
                records[0]["extension_degrees"],
                split_pair=records[0]["split_pair"],
                split_value=records[0]["split_value"],
            )["extension_blocks"]
        )
    ]
    all_comparisons_passed = all(
        record["comparison"]["all_checks_passed"] for record in records
    )
    corpus_manifest = {
        "schema_version": "horizonmath.native-pb-corpus.v1",
        "status": (
            "FORMULAS_GENERATED" if all_comparisons_passed else "ERROR"
        ),
        "generator": {
            "id": "corrected-native-opb-v1",
            "runtime_dependencies": [],
            "variable_order": (
                "lexicographic 7-subsets of the labeled 12-point link ground set"
            ),
            "row_order": [
                "residual four-set coverage",
                "exact point degrees",
                "corrected pair lower and upper bounds",
                "positive triple lower bounds",
                "exact extension block count",
                "optional exact pair split",
            ],
        },
        "input": {
            "class_index": class_index,
            "canonical_labeled_link_sha256": manifest["input"][
                "canonical_labeled_link_sha256"
            ],
            "screening_ledger_canonical_sha256": manifest["screening"]["ledger"][
                "canonical_document_sha256"
            ],
            "analysis_manifest_sha256": input_analysis_manifest_sha256,
        },
        "variable_count": len(variable_map),
        "variable_map": variable_map,
        "instances": records,
        "summary": {
            "instances": len(records),
            "unique_case_profile_pairs": len(
                {(row["case_id"], row["profile_id"]) for row in records}
            ),
            "byte_identical_to_prior_native_formulas": sum(
                row["comparison"]["native_formula_byte_hash_equal"]
                for row in records
            ),
            "canonical_row_equivalent_to_prior_formulas": sum(
                row["comparison"]["canonical_formula_hash_equal"]
                for row in records
            ),
            "all_comparisons_passed": all_comparisons_passed,
        },
        "scope": {
            "formulas_generated": True,
            "solver_run": False,
            "proof_generated": False,
            "verifier_run": False,
            "class_elimination_claimed": False,
        },
    }
    corpus_manifest_path = output_directory / "formula_corpus.manifest.json"
    write_json(corpus_manifest_path, corpus_manifest)
    write_sha256_sidecar(corpus_manifest_path)

    checksum_targets = sorted(
        [
            path
            for path in output_directory.rglob("*")
            if path.is_file()
            and path.name not in {"SHA256SUMS"}
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

    manifest["formula_generation"] = {
        "corpus_manifest": {
            "path": str(corpus_manifest_path),
            "sha256": sha256_file(corpus_manifest_path),
        },
        "summary": corpus_manifest["summary"],
        "status": corpus_manifest["status"],
    }
    manifest["status_ledger"]["formulas"] = corpus_manifest["status"]
    manifest["scope_guardrails"]["current_run_generated_formulas"] = True
    manifest["status"] = corpus_manifest["status"]
    return manifest, corpus_manifest
