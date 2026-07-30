from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from horizonlink.input import load_link
from horizonlink.manifest import build_manifest
from horizonlink.split_farkas import generate_lp_split_farkas_corpus
from tests.fixture_support import build_candidate_fixture


ROOT = Path(__file__).resolve().parents[1]
CLASS52 = ROOT / "data" / "class52.link.json"
PRESERVED = ROOT / "tests" / "data" / "golden" / "split_orbit05"
SCIPY_AVAILABLE = importlib.util.find_spec("scipy") is not None
SYMPY_AVAILABLE = importlib.util.find_spec("sympy") is not None


@unittest.skipUnless(
    SCIPY_AVAILABLE and SYMPY_AVAILABLE,
    "SciPy and the pinned SymPy proof dependency are required",
)
class ExactSplitFarkasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.structural = build_manifest(load_link(CLASS52), 4)
        cls.temporary = tempfile.TemporaryDirectory(
            prefix="horizonlink-split-farkas-test-"
        )
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.temporary_root = Path(cls.temporary.name)
        cls.candidate_corpus, cls.solver_manifest = (
            build_candidate_fixture(
                cls.structural,
                cls.temporary_root / "fixture",
                orbit_index=5,
                root_lp_status="LP_FEASIBLE",
                mip_status="SOLVER_UNSAT",
                historical_disposition="DISCARDED",
            )
        )
        cls.output = cls.temporary_root / "generated"
        cls.manifest = generate_lp_split_farkas_corpus(
            cls.structural,
            cls.candidate_corpus,
            cls.solver_manifest,
            cls.output,
            orbit_indices=[5],
            max_nodes=5000,
            lp_time_limit=30.0,
        )

    def test_orbit_five_tree_and_status_guardrails(self) -> None:
        self.assertEqual(self.manifest["status"], "PROOF_GENERATED")
        self.assertEqual(self.manifest["summary"]["proofs_generated"], 1)
        self.assertEqual(self.manifest["summary"]["verified_unsat"], 0)
        self.assertEqual(
            self.manifest["summary"]["formal_pruning_authorized"], 0
        )
        record = self.manifest["instances"][0]
        self.assertEqual(record["orbit_index"], 5)
        self.assertEqual(record["tree"]["node_count"], 3)
        self.assertEqual(record["tree"]["leaf_count"], 2)
        self.assertEqual(record["tree"]["max_depth"], 1)
        self.assertFalse(record["formal_pruning_authorized"])
        self.assertEqual(
            record["status_ledger"]["verification"], "NOT_STARTED"
        )
        for leaf_record in record["leaf_certificates"]:
            leaf = json.loads(
                (self.output / leaf_record["path"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(all(leaf["exact_checks"].values()))
            self.assertGreater(leaf["exact_margin"], 0)
            self.assertEqual(
                leaf["nullspace"]["engine"],
                "SymPy DomainMatrix exact integer nullspace over ZZ",
            )

    def test_orbit_five_artifacts_match_preserved_corpus(self) -> None:
        generated = self.output / "instances" / "c52_candidate_orbit05"
        preserved = PRESERVED
        generated_files = {
            path.relative_to(generated): path.read_bytes()
            for path in generated.rglob("*")
            if path.is_file()
        }
        preserved_files = {
            path.relative_to(preserved): path.read_bytes()
            for path in preserved.rglob("*")
            if path.is_file()
        }
        self.assertEqual(generated_files, preserved_files)

    def test_proof_has_leaf_derivations_and_root_contradiction(self) -> None:
        record = self.manifest["instances"][0]
        lines = (
            self.output / record["proof"]["path"]
        ).read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "pseudo-Boolean proof version 1.0")
        self.assertEqual(lines[1], "f 567")
        self.assertEqual(sum(line.startswith("p ") for line in lines), 3)
        self.assertTrue(lines[-1].startswith("c "))

    def test_nonempty_output_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonlink-split-farkas-nonempty-"
        ) as temporary:
            output = Path(temporary)
            marker = output / "unrelated.txt"
            marker.write_text("preserve me\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be empty"):
                generate_lp_split_farkas_corpus(
                    self.structural,
                    self.candidate_corpus,
                    self.solver_manifest,
                    output,
                    orbit_indices=[5],
                )
            self.assertEqual(
                marker.read_text(encoding="utf-8"), "preserve me\n"
            )


if __name__ == "__main__":
    unittest.main()
