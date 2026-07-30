from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from horizonlink.candidate_checkpoint import (
    CandidateCheckpointError,
    generate_candidate_formula_checkpoint,
)
from horizonlink.canonical import sha256_file


ROOT = Path(__file__).resolve().parents[1]
STRUCTURAL_CHECKPOINT = (
    ROOT / "results" / "structural-census-v0.1.0"
)
PROFILE_CHECKPOINT = (
    ROOT / "results" / "pilot-screening-v0.1.0"
)
CANDIDATE_CHECKPOINT = (
    ROOT / "results" / "class68-candidate-formulas-v0.1.0"
)
EXPECTED_NATIVE_HASHES = [
    "0c64a2330b2f267d062a3d13d33fcf00b69beb8f7af6157f78d788d941862089",
    "a927d0c231b39feaddb3799ca77334b329f861b397232fbe4fcb586ed46e28f2",
    "99d24cc29c11f6797cc3cd400ae08aa9c9c07612b0afd06d6cfd64cb83a2ca3e",
    "2f21eb1e877e49204a3e042031d588114456fdebaab0729c33d970e596160239",
    "31bc05d71706c9389f99dcf6bbd9856b177837f226cd79ab4c4d96d7a8eb4490",
    "0f3596ccb376ad1df6697c8062357c7adbd8132f9fc61206c19bbac748ad3899",
    "12bbeb7a2880ed65fac58d350c0961943116528e6d8aac6eca564b7fc872de4b",
    "3f052e674693244a08e1bd10e395fef4d54668aa4b8bca3c200b5e9890b0c73d",
    "96fad168d0d1488f53ff663a6124fb8e35b50f774df5ee024205ef64e43f8739",
    "d39c339c6ff26816ecbf280303998135675668c6de3e56ad8ff8a1cc66187b18",
    "9e0a8971e7dfa62a15849851e76e631723850ad29c88b4364dedf3ffa63b67ad",
    "83c73c3341bb53ce7074af7b1c80f023f9489dcb7449b87a3dedba83f1d7d93b",
]
EXPECTED_FAMILY_COUNTS = {
    "candidate_point_degree": 16,
    "extension_block_count": 2,
    "pair_degree_lower": 65,
    "residual_four_coverage": 285,
    "triple_degree_lower": 200,
}


class CandidateFormulaCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(
            prefix="horizonmath-class68-candidate-checkpoint-test-"
        )
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.output = Path(cls.temporary.name) / "checkpoint"
        cls.phase, cls.corpus, cls.audit = (
            generate_candidate_formula_checkpoint(
                STRUCTURAL_CHECKPOINT,
                PROFILE_CHECKPOINT,
                68,
                cls.output,
            )
        )

    def test_exact_class68_counts_and_status_boundaries(self) -> None:
        self.assertEqual(self.phase["status"], "FORMULAS_GENERATED")
        self.assertEqual(self.phase["input"]["class_index"], 68)
        self.assertEqual(
            self.phase["summary"],
            {
                "candidate_orbits": 12,
                "formulas_generated": 12,
                "independent_formula_audits_passed": 12,
                "all_candidate_orbits_accounted_for": True,
                "all_serialized_rows_audited_equal": True,
                "orbit_indices": list(range(12)),
                "unique_native_formula_hashes": 12,
                "unique_canonical_formula_hashes": 12,
                "total_native_formula_bytes": 6325777,
            },
        )
        self.assertEqual(
            self.phase["status_ledger"],
            {
                "structural_checkpoint_audit": "ENUMERATED",
                "profile_screening_gate": "ENUMERATED",
                "candidate_formulas": "FORMULAS_GENERATED",
                "independent_formula_audit": "FORMULAS_GENERATED",
                "direct_containment": "NOT_STARTED",
                "root_lp": "NOT_STARTED",
                "solver": "NOT_STARTED",
                "proof": "NOT_STARTED",
                "verification": "NOT_STARTED",
            },
        )
        scope = self.phase["scope_guardrails"]
        self.assertTrue(scope["formulas_generated"])
        self.assertFalse(scope["direct_containment_run"])
        self.assertFalse(scope["root_lp_run"])
        self.assertFalse(scope["solver_run"])
        self.assertFalse(scope["proof_generated"])
        self.assertFalse(scope["verifier_run"])
        self.assertFalse(scope["formal_orbit_pruning_authorized"])
        self.assertFalse(scope["class_elimination_claimed"])
        self.assertFalse(scope["C_13_7_4_equals_30_claimed"])

    def test_every_orbit_has_one_exact_formula(self) -> None:
        instances = self.phase["instances"]
        self.assertEqual(
            [row["orbit_index"] for row in instances],
            list(range(12)),
        )
        self.assertEqual(
            [row["formula"]["sha256"] for row in instances],
            EXPECTED_NATIVE_HASHES,
        )
        for row in instances:
            formula = row["formula"]
            self.assertEqual(formula["variables"], 792)
            self.assertEqual(formula["matrix_rows"], 563)
            self.assertEqual(formula["opb_constraints"], 568)
            self.assertEqual(
                formula["serialized_family_counts"],
                EXPECTED_FAMILY_COUNTS,
            )
            self.assertEqual(
                row["screening_gate"],
                {
                    "prior_disposition": "RETAINED",
                    "prior_evidence_status": (
                        "NO_CONTRADICTION_FOUND"
                    ),
                    "prior_rule_id": (
                        "NO_SOLVER_FREE_CANDIDATE_CONTRADICTION"
                    ),
                },
            )
            self.assertTrue(row["independent_audit"]["passed"])
            self.assertFalse(row["formal_pruning_authorized"])

    def test_independent_serialization_audit_passes_every_row(self) -> None:
        self.assertEqual(self.audit["status"], "PASS")
        self.assertFalse(
            self.audit["method"]["imports_candidate_formula_builder"]
        )
        self.assertFalse(self.audit["method"]["imports_pb_module"])
        self.assertEqual(
            self.audit["summary"],
            {
                "expected_orbits": 12,
                "observed_orbits": 12,
                "comparisons_passed": 12,
                "all_orbits_accounted_for": True,
                "all_rows_equal_in_order": True,
                "corpus_checksums_passed": True,
            },
        )
        for comparison in self.audit["comparisons"]:
            self.assertEqual(comparison["expected_rows"], 568)
            self.assertEqual(comparison["observed_rows"], 568)
            self.assertIsNone(comparison["first_difference"])
            self.assertTrue(comparison["passed"])
            self.assertTrue(all(comparison["checks"].values()))

    def test_audited_input_checkpoints_are_bound_by_hash(self) -> None:
        structural = self.phase["input"]["structural_census"]
        screening = self.phase["input"]["profile_screening"]
        self.assertTrue(structural["all_checks_passed"])
        self.assertTrue(screening["all_checks_passed"])
        self.assertTrue(all(structural["checks"].values()))
        self.assertTrue(all(screening["checks"].values()))
        self.assertEqual(
            structural["checkpoint_checksums"]["sha256sums_sha256"],
            "86ec09c20b888ceffe88c70c5f4013e5dcddda94e12d55b348a05dfc712a553e",
        )
        self.assertEqual(
            screening["checkpoint_checksums"]["sha256sums_sha256"],
            "5202b0e664e2ddef7860a488afecad623e7cca42e06d2217d4ea648d4ff9cecb",
        )
        self.assertEqual(
            self.phase["input"]["canonical_labeled_link_sha256"],
            "a66e49afc58526140a16d71c9cd89ab11add1e1e01832eecd1a6792764a28731",
        )
        self.assertEqual(
            self.phase["model"]["candidate_orbit_partition_sha256"],
            "9c433703f4d97c2d68d841f4b42e232db4631e6c4342a4a4611122ace3b70d96",
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

    def test_checkpoint_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonmath-class68-candidate-second-"
        ) as temporary:
            second = Path(temporary) / "checkpoint"
            generate_candidate_formula_checkpoint(
                STRUCTURAL_CHECKPOINT,
                PROFILE_CHECKPOINT,
                68,
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
            path.relative_to(CANDIDATE_CHECKPOINT): path.read_bytes()
            for path in CANDIDATE_CHECKPOINT.rglob("*")
            if path.is_file()
        }
        self.assertEqual(generated_files, checkpoint_files)

    def test_no_lp_solver_or_proof_artifacts_exist(self) -> None:
        forbidden_suffixes = {".pbp", ".proof", ".log"}
        forbidden_names = {
            "solver",
            "farkas",
            "veripb",
            "verification",
        }
        for path in self.output.rglob("*"):
            if not path.is_file():
                continue
            self.assertNotIn(path.suffix, forbidden_suffixes)
            lowered = path.name.lower()
            self.assertFalse(
                any(name in lowered for name in forbidden_names)
            )

    def test_nonempty_output_is_rejected_without_deletion(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonmath-class68-candidate-nonempty-"
        ) as temporary:
            output = Path(temporary)
            marker = output / "preserve.txt"
            marker.write_text("preserve\n", encoding="utf-8")
            with self.assertRaisesRegex(
                CandidateCheckpointError,
                "must be empty",
            ):
                generate_candidate_formula_checkpoint(
                    STRUCTURAL_CHECKPOINT,
                    PROFILE_CHECKPOINT,
                    68,
                    output,
                )
            self.assertEqual(
                marker.read_text(encoding="utf-8"),
                "preserve\n",
            )

    def test_class_not_present_in_screening_checkpoint_fails_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonmath-candidate-absent-class-"
        ) as temporary:
            output = Path(temporary) / "checkpoint"
            with self.assertRaisesRegex(
                CandidateCheckpointError,
                "must contain class 1 exactly once",
            ):
                generate_candidate_formula_checkpoint(
                    STRUCTURAL_CHECKPOINT,
                    PROFILE_CHECKPOINT,
                    1,
                    output,
                )
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
