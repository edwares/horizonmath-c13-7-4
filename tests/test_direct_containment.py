from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from horizonlink.canonical import sha256_file
from horizonlink.direct_containment import (
    ContainmentRow,
    DirectContainmentError,
    generate_direct_containment_checkpoint,
    render_direct_containment_proof,
    scan_direct_containment_rows,
)
from horizonlink.input import load_link
from horizonlink.pb import build_corrected_formula


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_CHECKPOINT = (
    ROOT / "results" / "class68-candidate-formulas-v0.1.0"
)
CONTAINMENT_CHECKPOINT = (
    ROOT / "results" / "class68-direct-containment-v0.1.0"
)
EXPECTED_SUPPORT_CONTAINMENTS = [
    1207,
    1182,
    1207,
    1182,
    1207,
    1207,
    1157,
    1182,
    1182,
    1207,
    1207,
    1157,
]
EXPECTED_CHECKPOINT_HASHES = {
    "SHA256SUMS": (
        "fe14bac9f54439a52eee055952381c26e2075081e7126a873239034699433f81"
    ),
    "phase.manifest.json": (
        "49c3d14d2918261398fa2e683ebcb27d347af9cdceadfa5d26057d3267f2a470"
    ),
    "scan.manifest.json": (
        "a8d5a2b96eb067fe2b82855876163392b1459f9945365063d7c2ac2a20b4b479"
    ),
    "independent-audit.json": (
        "df713833ee5a18634f4b24c76891efee7b8620f54b83861a433ea9512a34973d"
    ),
}


class DirectContainmentCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(
            prefix="horizonmath-class68-direct-containment-test-"
        )
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.output = Path(cls.temporary.name) / "checkpoint"
        cls.phase, cls.scan, cls.audit = (
            generate_direct_containment_checkpoint(
                CANDIDATE_CHECKPOINT,
                cls.output,
            )
        )

    def test_exact_class68_outcome_and_status_boundaries(self) -> None:
        self.assertEqual(self.phase["status"], "ENUMERATED")
        self.assertEqual(self.phase["input"]["class_index"], 68)
        self.assertEqual(
            self.phase["summary"],
            {
                "candidate_orbits_expected": 12,
                "candidate_orbits_scanned": 12,
                "all_candidate_orbits_accounted_for": True,
                "orbit_indices": list(range(12)),
                "direct_contradictions_found": 0,
                "proofs_generated": 0,
                "survivors": 12,
                "proof_orbit_indices": [],
                "survivor_orbit_indices": list(range(12)),
                "total_row_pairs_tested": 33780,
                "total_support_containments": 14284,
                "independent_comparisons_passed": 12,
                "all_scan_results_independently_recomputed": True,
            },
        )
        self.assertEqual(
            self.phase["status_ledger"],
            {
                "candidate_formulas": "FORMULAS_GENERATED",
                "direct_containment": "ENUMERATED",
                "root_lp": "NOT_STARTED",
                "solver": "NOT_STARTED",
                "proof": "NOT_STARTED",
                "verification": "NOT_STARTED",
            },
        )
        scope = self.phase["scope_guardrails"]
        self.assertTrue(scope["direct_containment_run"])
        self.assertFalse(scope["root_lp_run"])
        self.assertFalse(scope["solver_run"])
        self.assertFalse(scope["proof_generated"])
        self.assertFalse(scope["verifier_run"])
        self.assertFalse(scope["formal_orbit_pruning_authorized"])
        self.assertFalse(scope["class_elimination_claimed"])
        self.assertFalse(scope["C_13_7_4_equals_30_claimed"])

    def test_every_orbit_is_scanned_and_survives(self) -> None:
        self.assertEqual(
            [row["orbit_index"] for row in self.scan["instances"]],
            list(range(12)),
        )
        self.assertEqual(
            [
                row["scan"]["support_containments"]
                for row in self.scan["instances"]
            ],
            EXPECTED_SUPPORT_CONTAINMENTS,
        )
        for row in self.scan["instances"]:
            result = row["scan"]
            self.assertEqual(result["lower_rows"], 563)
            self.assertEqual(result["upper_rows"], 5)
            self.assertEqual(result["row_pairs_tested"], 2815)
            self.assertEqual(result["maximum_containment_gap"], 0)
            self.assertEqual(result["contradictions_found"], 0)
            self.assertEqual(result["witnesses"], [])
            self.assertEqual(
                sum(result["containment_gap_histogram"].values()),
                result["support_containments"],
            )
            self.assertTrue(
                all(
                    int(gap) <= 0
                    for gap in result[
                        "containment_gap_histogram"
                    ]
                )
            )
            self.assertEqual(
                row["result"]["disposition"],
                "SURVIVED_DIRECT_CONTAINMENT_SCAN",
            )
            self.assertEqual(
                row["result"]["evidence_status"],
                "NO_CONTRADICTION_FOUND",
            )
            self.assertIsNone(row["selected_witness"])
            self.assertIsNone(
                row["artifacts"]["verifier_normalized_formula"]
            )
            self.assertIsNone(row["artifacts"]["proof"])
            self.assertFalse(row["formal_pruning_authorized"])

    def test_independent_audit_recomputes_every_comparison(self) -> None:
        self.assertEqual(self.audit["status"], "PASS")
        self.assertFalse(
            self.audit["method"][
                "imports_direct_containment_module"
            ]
        )
        self.assertFalse(
            self.audit["method"]["imports_production_opb_parser"]
        )
        self.assertFalse(
            self.audit["method"]["imports_production_proof_renderer"]
        )
        self.assertEqual(
            self.audit["summary"],
            {
                "expected_orbits": 12,
                "observed_orbits": 12,
                "comparisons_passed": 12,
                "all_orbits_accounted_for": True,
                "all_scan_results_equal": True,
                "proofs_independently_reconstructed": 0,
                "survivors_independently_confirmed": 12,
            },
        )
        self.assertTrue(all(self.audit["input_checks"].values()))
        for comparison in self.audit["comparisons"]:
            self.assertEqual(
                comparison["row_pairs_independently_tested"],
                2815,
            )
            self.assertEqual(
                comparison["contradictions_independently_found"],
                0,
            )
            self.assertTrue(comparison["passed"])
            self.assertTrue(all(comparison["checks"].values()))

    def test_no_proof_lp_solver_or_verifier_artifacts_exist(self) -> None:
        paths = [
            path.relative_to(self.output).as_posix()
            for path in self.output.rglob("*")
            if path.is_file()
        ]
        self.assertFalse(any(path.endswith(".opb") for path in paths))
        self.assertFalse(any(path.endswith(".pbp") for path in paths))
        self.assertFalse(any(path.endswith(".log") for path in paths))
        self.assertFalse(
            any("farkas" in path.lower() for path in paths)
        )

    def test_checkpoint_checksum_accounting_is_complete(self) -> None:
        checksum_path = self.output / "SHA256SUMS"
        rows = [
            line.split("  ", 1)
            for line in checksum_path.read_text(
                encoding="utf-8"
            ).splitlines()
        ]
        files = sorted(
            path.relative_to(self.output).as_posix()
            for path in self.output.rglob("*")
            if path.is_file() and path != checksum_path
        )
        self.assertEqual([path for _, path in rows], files)
        for expected, relative in rows:
            self.assertEqual(
                sha256_file(self.output / relative),
                expected,
            )
        for relative, expected in EXPECTED_CHECKPOINT_HASHES.items():
            self.assertEqual(
                sha256_file(CONTAINMENT_CHECKPOINT / relative),
                expected,
            )

    def test_checkpoint_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonmath-class68-direct-containment-second-"
        ) as temporary:
            second = Path(temporary) / "checkpoint"
            generate_direct_containment_checkpoint(
                CANDIDATE_CHECKPOINT,
                second,
            )
            first_files = {
                path.relative_to(self.output): path.read_bytes()
                for path in self.output.rglob("*")
                if path.is_file()
            }
            second_files = {
                path.relative_to(second): path.read_bytes()
                for path in second.rglob("*")
                if path.is_file()
            }
            self.assertEqual(first_files, second_files)

    def test_checked_in_checkpoint_matches_generation(self) -> None:
        generated_files = {
            path.relative_to(self.output): path.read_bytes()
            for path in self.output.rglob("*")
            if path.is_file()
        }
        checkpoint_files = {
            path.relative_to(CONTAINMENT_CHECKPOINT): path.read_bytes()
            for path in CONTAINMENT_CHECKPOINT.rglob("*")
            if path.is_file()
        }
        self.assertEqual(generated_files, checkpoint_files)

    def test_nonempty_output_is_rejected_without_deletion(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonmath-direct-containment-nonempty-"
        ) as temporary:
            output = Path(temporary)
            marker = output / "preserve.txt"
            marker.write_text("preserve\n", encoding="utf-8")
            with self.assertRaisesRegex(
                DirectContainmentError,
                "must be empty",
            ):
                generate_direct_containment_checkpoint(
                    CANDIDATE_CHECKPOINT,
                    output,
                )
            self.assertEqual(
                marker.read_text(encoding="utf-8"),
                "preserve\n",
            )

    def test_incomplete_input_checkpoint_fails_before_output(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonmath-direct-containment-incomplete-"
        ) as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            (source / "SHA256SUMS").write_text(
                "",
                encoding="utf-8",
            )
            output = Path(temporary) / "output"
            with self.assertRaises(DirectContainmentError):
                generate_direct_containment_checkpoint(
                    source,
                    output,
                )
            self.assertFalse(output.exists())


class PublishedMethodRegressionTests(unittest.TestCase):
    @staticmethod
    def _class52_rows(split_value: int) -> tuple[ContainmentRow, ...]:
        link = load_link(ROOT / "data" / "class52.link.json")
        built = build_corrected_formula(
            link.point_labels,
            link.blocks,
            (8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 9, 9),
            split_pair=(1, 2),
            split_value=split_value,
        )
        return tuple(
            ContainmentRow(
                tuple(variable + 1 for variable in row.variables),
                row.relation,
                row.rhs,
                row.family,
                row.subject,
            )
            for row in built["rows"]
        )

    def test_class52_threshold_reproduces_eq9_through_eq14(self) -> None:
        for split_value in range(4, 9):
            with self.subTest(split_value=split_value):
                result = scan_direct_containment_rows(
                    self._class52_rows(split_value)
                )
                self.assertEqual(result["contradictions_found"], 0)

        for split_value in range(9, 15):
            with self.subTest(split_value=split_value):
                result = scan_direct_containment_rows(
                    self._class52_rows(split_value)
                )
                self.assertEqual(result["contradictions_found"], 2)
                first = result["witnesses"][0]
                self.assertEqual(
                    first["lower_row"]["id_1based"],
                    642,
                )
                self.assertEqual(
                    first["upper_row"]["id_1based"],
                    283,
                )
                self.assertEqual(
                    first["contradiction_gap"],
                    split_value - 8,
                )
                self.assertTrue(all(first["exact_checks"].values()))

    def test_class52_eq9_four_line_proof_is_exactly_57_bytes(
        self,
    ) -> None:
        result = scan_direct_containment_rows(
            self._class52_rows(9)
        )
        proof = render_direct_containment_proof(
            643,
            result["witnesses"][0],
        )
        self.assertEqual(
            proof,
            (
                b"pseudo-Boolean proof version 1.0\n"
                b"f 643\n"
                b"p 283 642 +\n"
                b"c 644\n"
            ),
        )
        self.assertEqual(len(proof), 57)


if __name__ == "__main__":
    unittest.main()
