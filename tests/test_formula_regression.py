from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from horizonlink.formulas import generate_formula_corpus
from horizonlink.input import load_link
from horizonlink.manifest import build_manifest
from horizonlink.screening import (
    extend_manifest_with_screening,
    load_screening_ledger,
)


ROOT = Path(__file__).resolve().parents[1]
CLASS52 = ROOT / "data" / "class52.link.json"
LEDGER = ROOT / "data" / "class52.recovered-screening-ledger.json"


class Class52FormulaRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        temporary = tempfile.TemporaryDirectory(
            prefix="horizonlink-formula-test-"
        )
        cls.addClassCleanup(temporary.cleanup)
        cls.output = Path(temporary.name)
        base = extend_manifest_with_screening(
            build_manifest(load_link(CLASS52)),
            load_screening_ledger(LEDGER),
        )
        cls.analysis, cls.corpus = generate_formula_corpus(
            base, cls.output
        )

    def test_all_30_native_formulas_are_byte_identical(self) -> None:
        summary = self.corpus["summary"]
        self.assertEqual(summary["instances"], 30)
        self.assertEqual(summary["unique_case_profile_pairs"], 20)
        self.assertEqual(
            summary["byte_identical_to_prior_native_formulas"], 30
        )
        self.assertEqual(
            summary["canonical_row_equivalent_to_prior_formulas"], 30
        )
        self.assertTrue(summary["all_comparisons_passed"])
        self.assertTrue(
            all(
                row["comparison"]["native_formula_byte_hash_equal"]
                for row in self.corpus["instances"]
            )
        )

    def test_direct_and_split_constraint_counts(self) -> None:
        direct = [
            row
            for row in self.corpus["instances"]
            if row["split_pair"] is None
        ]
        split = [
            row
            for row in self.corpus["instances"]
            if row["split_pair"] is not None
        ]
        self.assertEqual(len(direct), 19)
        self.assertEqual(len(split), 11)
        self.assertTrue(
            all(row["formula"]["matrix_rows"] == 562 for row in direct)
        )
        self.assertTrue(
            all(row["formula"]["opb_constraints"] == 641 for row in direct)
        )
        self.assertTrue(
            all(row["formula"]["matrix_rows"] == 563 for row in split)
        )
        self.assertTrue(
            all(row["formula"]["opb_constraints"] == 643 for row in split)
        )

    def test_variable_map_is_complete_and_lexicographic(self) -> None:
        variable_map = self.corpus["variable_map"]
        self.assertEqual(len(variable_map), 792)
        self.assertEqual(
            variable_map[0], {"variable": "x1", "block": list(range(7))}
        )
        self.assertEqual(
            variable_map[-1],
            {"variable": "x792", "block": list(range(5, 12))},
        )

    def test_generated_formula_status_is_not_verification_status(self) -> None:
        self.assertEqual(self.analysis["status"], "FORMULAS_GENERATED")
        self.assertEqual(
            self.analysis["status_ledger"]["formulas"],
            "FORMULAS_GENERATED",
        )
        self.assertEqual(
            self.analysis["status_ledger"]["solver"], "NOT_STARTED"
        )
        self.assertEqual(
            self.analysis["status_ledger"]["proof"], "NOT_STARTED"
        )
        self.assertEqual(
            self.analysis["status_ledger"]["verification"], "NOT_STARTED"
        )
        self.assertFalse(
            self.corpus["scope"]["class_elimination_claimed"]
        )

    def test_corpus_checksums_cover_every_generated_artifact(self) -> None:
        checksum_path = self.output / "SHA256SUMS"
        rows = checksum_path.read_text().splitlines()
        self.assertEqual(len(rows), 61)
        for row in rows:
            expected, relative = row.split("  ", 1)
            target = self.output / relative
            self.assertTrue(target.is_file())
            self.assertEqual(
                hashlib.sha256(target.read_bytes()).hexdigest(), expected
            )


if __name__ == "__main__":
    unittest.main()
