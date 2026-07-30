"""Exact class-52 structural regression against supplied golden artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from horizonlink.canonical import (
    canonical_document_sha256,
    sha256_file,
)


EXPECTED_LINK_HASH = (
    "034d4c7cd44947c6fe2e8d562850611670af399f5d850b2c141990152a6af571"
)
EXPECTED_POINT_MULTIPLICITIES = [9, 7, 7, 7, 9, 7, 7, 7, 9, 7, 7, 7]
EXPECTED_PAIR_HISTOGRAM = {"3": 45, "4": 18, "6": 3}
EXPECTED_TRIPLE_HISTOGRAM = {"1": 159, "2": 45, "3": 15, "6": 1}
EXPECTED_FOUR_HISTOGRAM = {"0": 279, "1": 207, "2": 9}


def _partition_set(orbits: list[list[list[int]]]) -> set[tuple[tuple[int, ...], ...]]:
    return {
        tuple(sorted(tuple(member) for member in orbit))
        for orbit in orbits
    }


def run_class52_regression(
    manifest: dict[str, Any],
    golden_automorphisms_path: Path,
    golden_four_orbits_path: Path,
) -> dict[str, Any]:
    golden_automorphisms = json.loads(golden_automorphisms_path.read_text())
    golden_four_orbits = json.loads(golden_four_orbits_path.read_text())
    golden_sources = {
        "automorphisms_sha256": sha256_file(golden_automorphisms_path),
        "four_set_orbits_sha256": sha256_file(golden_four_orbits_path),
    }
    scope = {
        "profiles_checked": False,
        "screening_checked": False,
        "formulas_checked": False,
        "prior_formula_metadata_checked": False,
        "solver_run": False,
        "proof_checked": False,
    }

    if (
        manifest.get("status") != "ENUMERATED"
        or manifest.get("automorphism_group") is None
        or manifest.get("candidate_minimum_point_sets") is None
    ):
        check = {
            "id": "structural_manifest_enumerated",
            "passed": False,
            "observed": manifest.get("status"),
            "expected": "ENUMERATED",
        }
        return {
            "schema_version": "horizonmath.class52-structural-regression.v1",
            "status": "FAIL",
            "all_checks_passed": False,
            "analysis_manifest_sha256": canonical_document_sha256(manifest),
            "golden_sources": golden_sources,
            "checks": [check],
            "scope": scope,
        }

    computed_group = {
        tuple(permutation)
        for permutation in manifest["automorphism_group"]["permutations"]
    }
    expected_group = {
        tuple(permutation)
        for permutation in golden_automorphisms["permutations"]
    }
    computed_orbit_members = [
        record["members"]
        for record in manifest["candidate_minimum_point_sets"]["orbits"]
    ]
    expected_orbit_members = golden_four_orbits["orbits"]

    point_rows = manifest["multiplicities"]["points"]["rows"]
    checks = [
        {
            "id": "canonical_labeled_link_sha256",
            "passed": manifest["input"]["canonical_labeled_link_sha256"]
            == EXPECTED_LINK_HASH,
            "observed": manifest["input"]["canonical_labeled_link_sha256"],
            "expected": EXPECTED_LINK_HASH,
        },
        {
            "id": "link_validation",
            "passed": manifest["mathematical_validation"][
                "valid_15_block_C_12_6_3_cover"
            ],
            "observed": manifest["mathematical_validation"][
                "valid_15_block_C_12_6_3_cover"
            ],
            "expected": True,
        },
        {
            "id": "point_multiplicities",
            "passed": [row["multiplicity"] for row in point_rows]
            == EXPECTED_POINT_MULTIPLICITIES,
            "observed": [row["multiplicity"] for row in point_rows],
            "expected": EXPECTED_POINT_MULTIPLICITIES,
        },
        {
            "id": "pair_multiplicity_histogram",
            "passed": manifest["multiplicities"]["pairs"]["histogram"]
            == EXPECTED_PAIR_HISTOGRAM,
            "observed": manifest["multiplicities"]["pairs"]["histogram"],
            "expected": EXPECTED_PAIR_HISTOGRAM,
        },
        {
            "id": "triple_multiplicity_histogram",
            "passed": manifest["multiplicities"]["triples"]["histogram"]
            == EXPECTED_TRIPLE_HISTOGRAM,
            "observed": manifest["multiplicities"]["triples"]["histogram"],
            "expected": EXPECTED_TRIPLE_HISTOGRAM,
        },
        {
            "id": "four_set_multiplicity_histogram",
            "passed": manifest["multiplicities"]["four_sets"]["histogram"]
            == EXPECTED_FOUR_HISTOGRAM,
            "observed": manifest["multiplicities"]["four_sets"]["histogram"],
            "expected": EXPECTED_FOUR_HISTOGRAM,
        },
        {
            "id": "residual_four_set_count",
            "passed": manifest["multiplicities"]["residual_four_sets"]["count"]
            == 279,
            "observed": manifest["multiplicities"]["residual_four_sets"]["count"],
            "expected": 279,
        },
        {
            "id": "automorphism_group_order",
            "passed": manifest["automorphism_group"]["order"] == 36,
            "observed": manifest["automorphism_group"]["order"],
            "expected": 36,
        },
        {
            "id": "automorphism_permutations_as_set",
            "passed": computed_group == expected_group,
            "observed": len(computed_group),
            "expected": len(expected_group),
        },
        {
            "id": "four_subset_universe_count",
            "passed": manifest["candidate_minimum_point_sets"]["universe_count"]
            == 495,
            "observed": manifest["candidate_minimum_point_sets"][
                "universe_count"
            ],
            "expected": 495,
        },
        {
            "id": "four_subset_orbit_count",
            "passed": manifest["candidate_minimum_point_sets"]["orbit_count"]
            == 26,
            "observed": manifest["candidate_minimum_point_sets"]["orbit_count"],
            "expected": 26,
        },
        {
            "id": "four_subset_orbit_partition",
            "passed": _partition_set(computed_orbit_members)
            == _partition_set(expected_orbit_members),
            "observed": len(_partition_set(computed_orbit_members)),
            "expected": len(_partition_set(expected_orbit_members)),
        },
        {
            "id": "four_subset_representative_order",
            "passed": manifest["candidate_minimum_point_sets"][
                "representatives"
            ]
            == golden_four_orbits["representatives"],
            "observed": manifest["candidate_minimum_point_sets"][
                "representatives"
            ],
            "expected": golden_four_orbits["representatives"],
        },
        {
            "id": "no_silent_candidate_loss",
            "passed": manifest["candidate_minimum_point_sets"]["accounting"][
                "all_candidates_accounted_for"
            ]
            and manifest["candidate_minimum_point_sets"]["accounting"][
                "members_unique"
            ],
            "observed": manifest["candidate_minimum_point_sets"]["accounting"],
            "expected": {
                "all_candidates_accounted_for": True,
                "members_unique": True,
            },
        },
    ]
    if (
        manifest.get("screening") is not None
        and manifest.get("exact_minimum_point_sets") is not None
        and manifest.get("extension_degree_profiles") is not None
        and manifest.get("prior_formula_corpus") is not None
    ):
        screening = manifest["screening"]
        exact_sets = manifest["exact_minimum_point_sets"]
        profiles = manifest["extension_degree_profiles"]
        prior_formulas = manifest["prior_formula_corpus"]
        expected = prior_formulas["expected_regression"]
        profile_comparisons = screening["comparison"]["degree_profiles"]
        formula_comparison = prior_formulas["comparison"]
        formula_instances = prior_formulas["instances"]
        formula_keys = {
            (row["case_id"], row["profile_id"]) for row in formula_instances
        }
        split_rows = [
            row
            for row in formula_instances
            if [row["case_id"], row["profile_id"]]
            == expected["split_case_profile"]
        ]
        source_counts = screening["summary"]["profile_sources"]
        screening_70_17_20 = {
            "initial_milp": source_counts.get("initial_milp", 0),
            "proof_tuned_milp": source_counts.get("proof_tuned_milp", 0),
            "corrected_affected": (
                source_counts.get("corrected_pairbound_milp", 0)
                + source_counts.get("corrected_pair_split", 0)
            ),
        }
        downstream_checks = [
            {
                "id": "degree_excess",
                "passed": manifest["degree_budget"]["derivation"]["excess"]
                == 8,
                "observed": manifest["degree_budget"]["derivation"]["excess"],
                "expected": 8,
            },
            {
                "id": "retained_candidate_orbit_indices",
                "passed": exact_sets["retained_candidate_orbit_indices"]
                == expected["retained_candidate_orbit_indices"],
                "observed": exact_sets[
                    "retained_candidate_orbit_indices"
                ],
                "expected": expected["retained_candidate_orbit_indices"],
            },
            {
                "id": "raw_exact_minimum_set_count",
                "passed": exact_sets["raw_surviving_set_count"]
                == expected["raw_exact_minimum_set_count"],
                "observed": exact_sets["raw_surviving_set_count"],
                "expected": expected["raw_exact_minimum_set_count"],
            },
            {
                "id": "exact_minimum_set_orbit_count",
                "passed": exact_sets["orbit_count"]
                == expected["exact_minimum_set_orbit_count"],
                "observed": exact_sets["orbit_count"],
                "expected": expected["exact_minimum_set_orbit_count"],
            },
            {
                "id": "exact_minimum_set_orbits_by_size",
                "passed": exact_sets["orbits_by_size"]
                == expected["exact_minimum_set_orbits_by_size"],
                "observed": exact_sets["orbits_by_size"],
                "expected": expected["exact_minimum_set_orbits_by_size"],
            },
            {
                "id": "whole_case_screening_count",
                "passed": screening["summary"][
                    "exact_minimum_set_cases_discarded"
                ]
                == expected["whole_case_solver_unsat_count"],
                "observed": screening["summary"][
                    "exact_minimum_set_cases_discarded"
                ],
                "expected": expected["whole_case_solver_unsat_count"],
            },
            {
                "id": "profile_case_ids",
                "passed": profiles["profile_case_ids"]
                == expected["profile_case_ids"],
                "observed": profiles["profile_case_ids"],
                "expected": expected["profile_case_ids"],
            },
            {
                "id": "raw_degree_profiles_before_symmetry",
                "passed": profiles["raw_profile_count_before_symmetry"]
                == expected["raw_degree_profile_count"],
                "observed": profiles["raw_profile_count_before_symmetry"],
                "expected": expected["raw_degree_profile_count"],
            },
            {
                "id": "degree_profile_orbit_count",
                "passed": profiles["profile_orbit_count"]
                == expected["degree_profile_orbit_count"],
                "observed": profiles["profile_orbit_count"],
                "expected": expected["degree_profile_orbit_count"],
            },
            {
                "id": "all_107_profiles_row_exact",
                "passed": len(profile_comparisons)
                == expected["degree_profile_orbit_count"]
                and all(row["passed"] for row in profile_comparisons),
                "observed": {
                    "rows": len(profile_comparisons),
                    "passed": sum(
                        row["passed"] for row in profile_comparisons
                    ),
                },
                "expected": {
                    "rows": expected["degree_profile_orbit_count"],
                    "passed": expected["degree_profile_orbit_count"],
                },
            },
            {
                "id": "screening_partition_70_17_20",
                "passed": screening_70_17_20
                == expected["screening_partition_70_17_20"],
                "observed": screening_70_17_20,
                "expected": expected["screening_partition_70_17_20"],
            },
            {
                "id": "retained_profile_count",
                "passed": screening["summary"]["profile_dispositions"].get(
                    "RETAINED", 0
                )
                == expected["retained_profile_count"],
                "observed": screening["summary"][
                    "profile_dispositions"
                ].get("RETAINED", 0),
                "expected": expected["retained_profile_count"],
            },
            {
                "id": "case21_profile014_exact_split",
                "passed": (
                    len(split_rows) == len(expected["split_values"])
                    and all(
                        row["split_pair"] == expected["split_pair"]
                        for row in split_rows
                    )
                    and sorted(row["split_value"] for row in split_rows)
                    == expected["split_values"]
                ),
                "observed": {
                    "count": len(split_rows),
                    "pairs": sorted(
                        {tuple(row["split_pair"]) for row in split_rows}
                    ),
                    "values": sorted(
                        row["split_value"] for row in split_rows
                    ),
                },
                "expected": {
                    "count": len(expected["split_values"]),
                    "pairs": [tuple(expected["split_pair"])],
                    "values": expected["split_values"],
                },
            },
            {
                "id": "prior_formula_instance_count",
                "passed": len(formula_instances)
                == expected["formula_count"],
                "observed": len(formula_instances),
                "expected": expected["formula_count"],
            },
            {
                "id": "prior_formula_unique_profile_count",
                "passed": len(formula_keys)
                == expected["unique_formula_profile_count"],
                "observed": len(formula_keys),
                "expected": expected["unique_formula_profile_count"],
            },
            {
                "id": "prior_formula_metadata_and_canonical_audit",
                "passed": formula_comparison["accounting"][
                    "all_checks_passed"
                ],
                "observed": formula_comparison["accounting"],
                "expected": {"all_checks_passed": True},
            },
            {
                "id": "no_silent_downstream_loss",
                "passed": screening["comparison"]["all_checks_passed"]
                and exact_sets["accounting"][
                    "all_surviving_sets_accounted_for"
                ]
                and profiles["accounting"][
                    "all_raw_profiles_accounted_for"
                ],
                "observed": {
                    "screening": screening["comparison"][
                        "all_checks_passed"
                    ],
                    "exact_sets": exact_sets["accounting"],
                    "profiles": profiles["accounting"],
                },
                "expected": True,
            },
            {
                "id": "solver_unsat_not_promoted",
                "passed": (
                    screening["summary"]["profile_statuses"].get(
                        "SOLVER_UNSAT", 0
                    )
                    == 87
                    and manifest["status_ledger"]["formulas"]
                    == "NOT_STARTED"
                    and not manifest["scope_guardrails"][
                        "current_run_generated_formulas"
                    ]
                ),
                "observed": {
                    "solver_unsat_profiles": screening["summary"][
                        "profile_statuses"
                    ].get("SOLVER_UNSAT", 0),
                    "current_formula_stage": manifest["status_ledger"][
                        "formulas"
                    ],
                },
                "expected": {
                    "solver_unsat_profiles": 87,
                    "current_formula_stage": "NOT_STARTED",
                },
            },
        ]
        checks.extend(downstream_checks)
        scope["profiles_checked"] = True
        scope["screening_checked"] = True
        scope["prior_formula_metadata_checked"] = True

    return {
        "schema_version": (
            "horizonmath.class52-full-regression.v1"
            if scope["profiles_checked"]
            else "horizonmath.class52-structural-regression.v1"
        ),
        "status": "PASS" if all(check["passed"] for check in checks) else "FAIL",
        "all_checks_passed": all(check["passed"] for check in checks),
        "analysis_manifest_sha256": canonical_document_sha256(manifest),
        "golden_sources": golden_sources,
        "checks": checks,
        "scope": scope,
    }
