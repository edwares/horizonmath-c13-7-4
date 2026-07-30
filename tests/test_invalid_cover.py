from __future__ import annotations

import copy
import unittest
from pathlib import Path

from horizonlink.canonical import pretty_json_bytes
from horizonlink.input import load_link, parse_link_bytes
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


class InvalidCoverTests(unittest.TestCase):
    def test_structurally_valid_but_noncovering_input_stops_cleanly(self) -> None:
        baseline = load_link(CLASS52)
        invalid = copy.deepcopy(baseline.canonical_document)
        invalid["blocks"][-1] = [0, 1, 2, 3, 4, 5]
        parsed = parse_link_bytes(pretty_json_bytes(invalid))
        manifest = build_manifest(parsed)

        self.assertEqual(manifest["status"], "ERROR")
        validation = manifest["mathematical_validation"]
        self.assertFalse(validation["valid_15_block_C_12_6_3_cover"])
        self.assertEqual(len(validation["uncovered_triples"]), 14)
        self.assertIsNone(manifest["automorphism_group"])
        self.assertIsNone(manifest["candidate_minimum_point_sets"])
        self.assertEqual(manifest["status_ledger"]["link"], "ERROR")
        self.assertEqual(
            manifest["status_ledger"]["multiplicities"], "ENUMERATED"
        )
        for stage in (
            "automorphism_group",
            "candidate_minimum_point_set_orbits",
            "extension_degree_profiles",
            "screening",
            "formulas",
            "solver",
            "proof",
            "verification",
        ):
            self.assertEqual(manifest["status_ledger"][stage], "NOT_STARTED")

        regression = run_class52_regression(
            manifest, GOLDEN_AUTOMORPHISMS, GOLDEN_ORBITS
        )
        self.assertEqual(regression["status"], "FAIL")
        self.assertFalse(regression["all_checks_passed"])
        self.assertEqual(
            regression["checks"][0]["id"], "structural_manifest_enumerated"
        )


if __name__ == "__main__":
    unittest.main()
