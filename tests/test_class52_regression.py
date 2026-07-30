from __future__ import annotations

import unittest
from pathlib import Path

from horizonlink.input import load_link
from horizonlink.manifest import build_manifest
from horizonlink.regression import run_class52_regression


ROOT = Path(__file__).resolve().parents[1]
CLASS52 = ROOT / "data" / "class52.link.json"
GOLDEN_AUTOMORPHISMS = (
    ROOT / "tests" / "data" / "golden" / "results_class52_automorphisms.json"
)
GOLDEN_ORBITS = (
    ROOT / "tests" / "data" / "golden" / "results_class52_minpoint4_orbits.json"
)


class Class52RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.link = load_link(CLASS52)
        cls.manifest = build_manifest(cls.link)
        cls.regression = run_class52_regression(
            cls.manifest,
            GOLDEN_AUTOMORPHISMS,
            GOLDEN_ORBITS,
        )

    def test_structural_manifest_is_enumerated(self) -> None:
        self.assertEqual(self.manifest["status"], "ENUMERATED")
        self.assertTrue(
            self.manifest["mathematical_validation"][
                "valid_15_block_C_12_6_3_cover"
            ]
        )
        self.assertTrue(self.manifest["structural_audit"]["all_checks_passed"])

    def test_known_class52_counts(self) -> None:
        self.assertEqual(
            self.manifest["input"]["canonical_labeled_link_sha256"],
            "034d4c7cd44947c6fe2e8d562850611670af399f5d850b2c141990152a6af571",
        )
        self.assertEqual(
            self.manifest["multiplicities"]["residual_four_sets"]["count"], 279
        )
        self.assertEqual(self.manifest["automorphism_group"]["order"], 36)
        self.assertEqual(
            self.manifest["candidate_minimum_point_sets"]["universe_count"], 495
        )
        self.assertEqual(
            self.manifest["candidate_minimum_point_sets"]["orbit_count"], 26
        )

    def test_complete_golden_regression(self) -> None:
        self.assertEqual(self.regression["status"], "PASS")
        self.assertTrue(self.regression["all_checks_passed"])
        self.assertEqual(len(self.regression["checks"]), 14)
        self.assertTrue(
            all(check["passed"] for check in self.regression["checks"])
        )

    def test_no_downstream_stage_is_promoted(self) -> None:
        ledger = self.manifest["status_ledger"]
        for stage in (
            "extension_degree_profiles",
            "screening",
            "formulas",
            "solver",
            "proof",
            "verification",
        ):
            self.assertEqual(ledger[stage], "NOT_STARTED")
        self.assertFalse(self.manifest["scope_guardrails"]["profiles_computed"])
        self.assertFalse(
            self.manifest["scope_guardrails"]["class_elimination_claimed"]
        )

    def test_incidence_identities(self) -> None:
        for name in ("points", "pairs", "triples", "four_sets"):
            section = self.manifest["multiplicities"][name]
            self.assertEqual(
                section["total_incidence"], section["expected_total_incidence"]
            )


if __name__ == "__main__":
    unittest.main()
