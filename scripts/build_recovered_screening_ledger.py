#!/usr/bin/env python3
"""Build the portable class-52 golden screening ledger.

The input is the independently generated recovered-profile audit.  The output
contains every candidate orbit, exact minimum-set case, degree profile, and
retained formula row, while keeping solver-only and formally verified statuses
distinct.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = (
    ROOT.parent / "provenance_recovery" / "profile_provenance_audit.json"
)
DEFAULT_OUTPUT = ROOT / "data" / "class52.recovered-screening-ledger.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def logical_evidence(evidence: dict[str, Any] | None) -> dict[str, Any] | None:
    if evidence is None:
        return None
    result = dict(evidence)
    if "path" in result:
        result["path"] = result["path"].split(
            "HorizonMath_C13_7_4_class52_corrected_checkpoint/", 1
        )[-1]
    if "paths" in result:
        result["paths"] = [
            path.split(
                "HorizonMath_C13_7_4_class52_corrected_checkpoint/", 1
            )[-1]
            for path in result["paths"]
        ]
    return result


def build_ledger(audit_path: Path) -> dict[str, Any]:
    audit = load_json(audit_path)
    if audit["status"] != "PASS":
        raise ValueError("recovered profile audit did not pass")

    exact_rows = []
    for row in audit["exact_minimum_sets"]["cases"]:
        item = {
            "case_id": row["case"],
            "minimum_set_size": row["size"],
            "minimum_set": row["minimum_set"],
            "source_candidate_orbit_index": row["source_four_orbit"],
            "disposition": row["disposition"],
            "status": row["status"],
        }
        if row["disposition"] == "DISCARDED":
            item["rule_id"] = "HISTORICAL_EXACT_MINSET_MILP_INFEASIBLE"
            item["mathematical_reason"] = (
                "The exact-minimum-set 0-1 model fixes every point in the set "
                "to its minimum extension degree, requires every outside "
                "point to have at least one excess unit, enforces residual "
                "four-set coverage and point/pair/triple lower bounds, and "
                "requires exactly 14 extension blocks. The archived HiGHS run "
                "reported this model infeasible."
            )
            item["evidence"] = logical_evidence(row["evidence"])
        else:
            item["rule_id"] = "RETAIN_FOR_EXACT_DEGREE_PROFILES"
            item["mathematical_reason"] = (
                "The historical whole-case screen did not eliminate this "
                "case, so every positive integral allocation of the eight "
                "excess degree units outside the exact minimum set must be "
                "enumerated modulo its stabilizer."
            )
        exact_rows.append(item)

    profile_rows = []
    for row in audit["degree_profiles"]["profiles"]:
        source = row["screening_source"]
        retained = row["formula_disposition"] == "RETAINED_FOR_PB_CERTIFICATION"
        if source == "initial_milp":
            rule_id = "HISTORICAL_BASE_MILP_INFEASIBLE"
            reason = (
                "The archived base exact-degree 0-1 model reported infeasible."
            )
        elif source == "proof_tuned_milp":
            rule_id = "HISTORICAL_PROOF_TUNED_MILP_INFEASIBLE"
            reason = (
                "The archived proof-tuned exact-degree 0-1 model reported "
                "infeasible."
            )
        elif source == "corrected_pairbound_milp":
            rule_id = "RETAIN_CORRECTED_PAIRBOUND_FORMULA"
            reason = (
                "This profile was one of the 20 affected by the discarded "
                "pair-bound formula and was retained for a corrected native "
                "PB formula using the full pair-degree bound before "
                "subtracting the fixed link multiplicity once."
            )
        elif source == "corrected_pair_split":
            rule_id = "RETAIN_EXACT_PAIR_MULTIPLICITY_PARTITION"
            reason = (
                "The corrected profile was partitioned by extension "
                "multiplicity of pair {1,2}; the exact integer range 4 through "
                "14 yields eleven formulas."
            )
        else:
            raise ValueError(f"unknown profile source {source!r}")
        profile_rows.append(
            {
                "case_id": row["case"],
                "profile_id": row["profile"],
                "minimum_set": row["minimum_set"],
                "degree_profile": row["degree_profile"],
                "extension_degrees": row["extension_degrees"],
                "source": source,
                "disposition": "RETAINED" if retained else "DISCARDED",
                "status": (
                    "FORMULAS_GENERATED" if retained else "SOLVER_UNSAT"
                ),
                "rule_id": rule_id,
                "mathematical_reason": reason,
                "evidence": logical_evidence(row["evidence"]),
            }
        )

    formula_rows = []
    for row in audit["formulas"]["rows"]:
        formula_rows.append(
            {
                "name": row["name"],
                "case_id": row["case"],
                "profile_id": row["profile"],
                "split_pair": row["split_pair"],
                "split_value": row["split_value"],
                "native_formula_sha256": row["native_formula"]["sha256"],
                "canonical_formula_sha256": row[
                    "canonical_formula_sha256"
                ],
                "published_formula_sha256": row[
                    "published_formula_sha256"
                ],
                "published_proof_gzip_sha256": row[
                    "published_proof_gzip_sha256"
                ],
                "status": row["status"],
                "canonical_comparison_passed": row["checks"][
                    "canonical_formula_equivalence_passed"
                ],
                "certificate_final_audit_passed": row["checks"][
                    "certificate_final_audit_passed"
                ],
            }
        )

    source_artifacts = audit["source_artifacts"]
    return {
        "schema_version": "horizonmath.recovered-screening-ledger.v1",
        "class_index": 52,
        "canonical_labeled_link_sha256": audit["class52"][
            "canonical_labeled_link_sha256"
        ],
        "provenance": {
            "derivation": (
                "Mechanically extracted from the recovered corrected "
                "checkpoint, recomputed combinatorics, recovered screening "
                "ledger, native PB bundle, and canonical formula comparison."
            ),
            "source_artifacts": {
                key: {
                    field: value
                    for field, value in record.items()
                    if field in {"sha256", "path"}
                }
                for key, record in source_artifacts.items()
                if isinstance(record, dict)
            },
            "limitations": [
                "The original 26 per-orbit full_minpoints result files were not recovered.",
                "The 17 whole-case and 87 early-profile exclusions are archived HiGHS SOLVER_UNSAT reports, not VERIFIED_UNSAT certificates.",
                "The 30 retained formula instances are independently recorded as VERIFIED_UNSAT.",
            ],
        },
        "degree_budget": {
            "link_point_degrees": audit["class52"]["link_point_degrees"],
            "minimum_extension_degrees": audit["class52"][
                "minimum_extension_degrees"
            ],
            "extension_degree_sum": audit["class52"]["extension_degree_sum"],
            "excess": audit["class52"]["degree_excess"],
        },
        "candidate_orbit_screening": audit["four_orbit_screening"],
        "exact_minimum_set_screening": exact_rows,
        "degree_profile_screening": profile_rows,
        "formula_instances": formula_rows,
        "expected_regression": {
            "automorphism_group_order": 36,
            "candidate_subset_count": 495,
            "candidate_orbit_count": 26,
            "retained_candidate_orbit_indices": audit["class52"][
                "hard_four_orbit_ids"
            ],
            "raw_exact_minimum_set_count": audit["exact_minimum_sets"][
                "raw_surviving_set_total"
            ],
            "exact_minimum_set_orbit_count": audit["exact_minimum_sets"][
                "orbit_count"
            ],
            "exact_minimum_set_orbits_by_size": audit[
                "exact_minimum_sets"
            ]["orbits_by_size"],
            "whole_case_solver_unsat_count": 17,
            "profile_case_ids": audit["degree_profiles"]["profile_cases"],
            "raw_degree_profile_count": audit["degree_profiles"][
                "raw_profile_total_before_symmetry"
            ],
            "degree_profile_orbit_count": audit["degree_profiles"][
                "profile_orbit_total"
            ],
            "screening_partition_70_17_20": audit["degree_profiles"][
                "historical_70_17_20_partition"
            ],
            "retained_profile_count": 20,
            "formula_count": audit["formulas"]["count"],
            "unique_formula_profile_count": audit["formulas"][
                "unique_case_profile_pairs"
            ],
            "split_case_profile": [21, 14],
            "split_pair": [1, 2],
            "split_values": list(range(4, 15)),
        },
        "status_assessment": audit["formal_status_assessment"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    ledger = build_ledger(args.audit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {args.output} "
        f"({len(ledger['degree_profile_screening'])} profiles)"
    )
    print(f"sha256 {sha256_file(args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
