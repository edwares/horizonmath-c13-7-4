from __future__ import annotations

import copy
import unittest
from pathlib import Path

from horizonlink.canonical import pretty_json_bytes
from horizonlink.input import load_link
from horizonlink.manifest import build_manifest
from horizonlink.profiles import expected_raw_profile_count
from horizonlink.regression import run_class52_regression
from horizonlink.screening import (
    extend_manifest_with_screening,
    load_screening_ledger,
)


ROOT = Path(__file__).resolve().parents[1]
CLASS52 = ROOT / "data" / "class52.link.json"
LEDGER = ROOT / "data" / "class52.recovered-screening-ledger.json"
GOLDEN_AUTOMORPHISMS = (
    ROOT / "tests" / "data" / "golden" / "results_class52_automorphisms.json"
)
GOLDEN_ORBITS = (
    ROOT / "tests" / "data" / "golden" / "results_class52_minpoint4_orbits.json"
)


class Class52ProfileRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.link = load_link(CLASS52)
        cls.ledger = load_screening_ledger(LEDGER)
        cls.manifest = extend_manifest_with_screening(
            build_manifest(cls.link), cls.ledger
        )
        cls.regression = run_class52_regression(
            cls.manifest,
            GOLDEN_AUTOMORPHISMS,
            GOLDEN_ORBITS,
        )

    def test_exact_minimum_set_regression(self) -> None:
        exact = self.manifest["exact_minimum_point_sets"]
        self.assertEqual(exact["retained_candidate_orbit_indices"], [
            14,
            19,
            20,
            21,
            22,
            23,
            24,
            25,
        ])
        self.assertEqual(exact["raw_surviving_set_count"], 400)
        self.assertEqual(exact["orbit_count"], 26)
        self.assertEqual(
            exact["orbits_by_size"],
            {"4": 8, "5": 7, "6": 6, "7": 3, "8": 1, "9": 1},
        )
        self.assertTrue(
            exact["accounting"]["all_surviving_sets_accounted_for"]
        )

    def test_all_107_profiles_match_row_for_row(self) -> None:
        profiles = self.manifest["extension_degree_profiles"]
        comparison = self.manifest["screening"]["comparison"][
            "degree_profiles"
        ]
        self.assertEqual(profiles["raw_profile_count_before_symmetry"], 225)
        self.assertEqual(profiles["profile_orbit_count"], 107)
        self.assertEqual(len(comparison), 107)
        self.assertTrue(all(row["passed"] for row in comparison))
        self.assertTrue(
            profiles["accounting"]["all_raw_profiles_accounted_for"]
        )
        self.assertTrue(
            profiles["accounting"]["all_extension_degree_sums_exact"]
        )

    def test_profile_case_counts_have_closed_form_raw_counts(self) -> None:
        profiles = self.manifest["extension_degree_profiles"]
        for case in profiles["cases"]:
            outside_points = 12 - case["minimum_set_size"]
            self.assertEqual(
                case["raw_positive_profile_count"],
                expected_raw_profile_count(8, outside_points),
            )

    def test_screening_partition_and_no_silent_loss(self) -> None:
        screening = self.manifest["screening"]
        sources = screening["summary"]["profile_sources"]
        self.assertEqual(sources["initial_milp"], 70)
        self.assertEqual(sources["proof_tuned_milp"], 17)
        self.assertEqual(sources["corrected_pairbound_milp"], 19)
        self.assertEqual(sources["corrected_pair_split"], 1)
        self.assertEqual(
            screening["summary"]["profile_dispositions"],
            {"DISCARDED": 87, "RETAINED": 20},
        )
        self.assertTrue(screening["comparison"]["all_checks_passed"])

    def test_prior_formula_metadata_regression(self) -> None:
        prior = self.manifest["prior_formula_corpus"]
        instances = prior["instances"]
        self.assertEqual(len(instances), 30)
        self.assertEqual(
            len({(row["case_id"], row["profile_id"]) for row in instances}),
            20,
        )
        split = [
            row
            for row in instances
            if (row["case_id"], row["profile_id"]) == (21, 14)
        ]
        self.assertEqual(len(split), 11)
        self.assertTrue(all(row["split_pair"] == [1, 2] for row in split))
        self.assertEqual(
            sorted(row["split_value"] for row in split), list(range(4, 15))
        )
        self.assertTrue(
            prior["comparison"]["accounting"]["all_checks_passed"]
        )

    def test_full_regression_passes(self) -> None:
        self.assertEqual(
            self.regression["schema_version"],
            "horizonmath.class52-full-regression.v1",
        )
        self.assertEqual(self.regression["status"], "PASS")
        self.assertTrue(self.regression["all_checks_passed"])
        self.assertTrue(self.regression["scope"]["profiles_checked"])
        self.assertTrue(self.regression["scope"]["screening_checked"])
        self.assertTrue(
            self.regression["scope"]["prior_formula_metadata_checked"]
        )
        self.assertFalse(self.regression["scope"]["formulas_checked"])

    def test_solver_only_rows_are_not_promoted(self) -> None:
        self.assertEqual(
            self.manifest["screening"]["summary"]["profile_statuses"],
            {"FORMULAS_GENERATED": 20, "SOLVER_UNSAT": 87},
        )
        self.assertEqual(
            self.manifest["status_ledger"]["formulas"], "NOT_STARTED"
        )
        self.assertFalse(
            self.manifest["scope_guardrails"][
                "current_run_generated_formulas"
            ]
        )
        self.assertFalse(
            self.manifest["scope_guardrails"][
                "current_run_verified_certificates"
            ]
        )
        self.assertFalse(
            self.manifest["scope_guardrails"]["class_elimination_claimed"]
        )

    def test_full_manifest_is_deterministic(self) -> None:
        second = extend_manifest_with_screening(
            build_manifest(load_link(CLASS52)),
            load_screening_ledger(LEDGER),
        )
        self.assertEqual(
            pretty_json_bytes(self.manifest), pretty_json_bytes(second)
        )

    def test_profile_vector_tampering_fails_closed(self) -> None:
        tampered = copy.deepcopy(self.ledger)
        tampered["degree_profile_screening"][0]["degree_profile"][0] += 1
        manifest = extend_manifest_with_screening(
            build_manifest(self.link), tampered
        )
        self.assertEqual(manifest["status"], "ERROR")
        self.assertEqual(
            manifest["status_ledger"]["extension_degree_profiles"], "ERROR"
        )
        self.assertFalse(
            manifest["screening"]["comparison"]["all_checks_passed"]
        )


if __name__ == "__main__":
    unittest.main()
