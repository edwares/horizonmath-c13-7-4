from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from horizonlink.farkas import generate_root_lp_farkas_corpus
from horizonlink.input import load_link
from horizonlink.manifest import build_manifest
from tests.fixture_support import build_candidate_fixture


ROOT = Path(__file__).resolve().parents[1]
CLASS52 = ROOT / "data" / "class52.link.json"
SCIPY_AVAILABLE = importlib.util.find_spec("scipy") is not None


@unittest.skipUnless(SCIPY_AVAILABLE, "SciPy is not installed")
class ExactRootLPFarkasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.structural = build_manifest(load_link(CLASS52), 4)
        cls.fixture_temporary = tempfile.TemporaryDirectory(
            prefix="horizonlink-farkas-fixture-"
        )
        cls.addClassCleanup(cls.fixture_temporary.cleanup)
        cls.candidate_corpus, cls.solver_manifest = (
            build_candidate_fixture(
                cls.structural,
                Path(cls.fixture_temporary.name),
                orbit_index=0,
                root_lp_status="SOLVER_UNSAT",
                mip_status="NOT_STARTED",
            )
        )

    def _generate(self, directory: Path) -> dict:
        return generate_root_lp_farkas_corpus(
            self.structural,
            self.candidate_corpus,
            self.solver_manifest,
            directory,
            orbit_indices=[0],
        )

    def test_orbit_zero_exact_certificate_and_status_guardrails(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonlink-farkas-test-"
        ) as temporary:
            output = Path(temporary)
            manifest = self._generate(output)
            self.assertEqual(manifest["status"], "PROOF_GENERATED")
            self.assertEqual(manifest["summary"]["proofs_generated"], 1)
            self.assertEqual(manifest["summary"]["verified_unsat"], 0)
            self.assertEqual(
                manifest["summary"]["formal_pruning_authorized"], 0
            )
            record = manifest["instances"][0]
            self.assertEqual(record["orbit_index"], 0)
            self.assertTrue(
                all(record["exact_certificate"]["exact_checks"].values())
            )
            self.assertGreater(
                record["exact_certificate"]["combined_rhs_after_bounds"], 0
            )
            self.assertEqual(
                record["status_ledger"]["proof"], "PROOF_GENERATED"
            )
            self.assertEqual(
                record["status_ledger"]["verification"], "NOT_STARTED"
            )
            self.assertFalse(record["formal_pruning_authorized"])

            source_formula = (
                self.candidate_corpus
                / record["source_formula"]["path"]
            ).read_text(encoding="utf-8")
            verifier_formula = (
                output / record["formula"]["path"]
            ).read_text(encoding="utf-8")
            self.assertIn(" <= ", source_formula)
            self.assertNotIn(" <= ", verifier_formula)
            self.assertEqual(verifier_formula.count(" >= "), 567)
            self.assertTrue(
                record["formula"][
                    "canonical_equivalent_to_source_formula"
                ]
            )

            proof = (
                output / record["proof"]["path"]
            ).read_text(encoding="utf-8")
            lines = proof.splitlines()
            self.assertEqual(len(lines), 4)
            self.assertEqual(
                lines[0], "pseudo-Boolean proof version 1.0"
            )
            self.assertEqual(lines[1], "f 567")
            self.assertTrue(lines[2].startswith("p "))
            self.assertEqual(lines[3], "c 568")

    def test_proof_corpus_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonlink-farkas-first-"
        ) as first_temporary, tempfile.TemporaryDirectory(
            prefix="horizonlink-farkas-second-"
        ) as second_temporary:
            first = Path(first_temporary)
            second = Path(second_temporary)
            first_manifest = self._generate(first)
            second_manifest = self._generate(second)
            self.assertEqual(first_manifest, second_manifest)
            first_files = {
                path.relative_to(first): path.read_bytes()
                for path in first.rglob("*")
                if path.is_file()
            }
            second_files = {
                path.relative_to(second): path.read_bytes()
                for path in second.rglob("*")
                if path.is_file()
            }
            self.assertEqual(first_files, second_files)

    def test_nonempty_output_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonlink-farkas-nonempty-"
        ) as temporary:
            output = Path(temporary)
            (output / "unrelated.txt").write_text(
                "preserve me\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "must be empty"):
                self._generate(output)
            self.assertEqual(
                (output / "unrelated.txt").read_text(encoding="utf-8"),
                "preserve me\n",
            )


if __name__ == "__main__":
    unittest.main()
