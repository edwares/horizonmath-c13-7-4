from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from horizonlink.canonical import sha256_file
from horizonlink.root_lp import RootLPError, generate_root_lp_checkpoint


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "results" / "class68-candidate-formulas-v0.1.0"
DIRECT = ROOT / "results" / "class68-direct-containment-v0.1.0"
CHECKPOINT = ROOT / "results" / "class68-root-lp-v0.1.0"
VERIFICATION = ROOT / "results" / "class68-root-lp-verification-v0.1.0"


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _checksum_rows(directory: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        rows[relative] = digest
    return rows


class RootLPCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="horizon-root-lp-test-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.generated = Path(cls.temporary.name)
        cls.phase, cls.root_manifest, cls.audit = generate_root_lp_checkpoint(
            CANDIDATE,
            DIRECT,
            cls.generated,
            root_lp_time_limit=30.0,
        )

    def test_exact_class68_partition_and_status_boundaries(self) -> None:
        summary = self.phase["summary"]
        self.assertEqual(summary["candidate_orbits_scanned"], 12)
        self.assertEqual(summary["exact_lp_feasible"], 6)
        self.assertEqual(
            summary["exact_lp_feasible_orbit_indices"], [0, 2, 4, 5, 9, 10]
        )
        self.assertEqual(summary["exact_farkas_contradictions"], 6)
        self.assertEqual(
            summary["exact_farkas_orbit_indices"], [1, 3, 6, 7, 8, 11]
        )
        self.assertEqual(summary["proofs_generated"], 6)
        self.assertEqual(summary["proofs_verified"], 0)
        self.assertEqual(summary["formal_orbits_pruned"], 0)
        self.assertFalse(self.phase["scope_guardrails"]["milp_run"])
        self.assertFalse(self.phase["scope_guardrails"]["roundingsat_run"])
        self.assertFalse(self.phase["scope_guardrails"]["verifier_run"])
        self.assertFalse(
            self.phase["scope_guardrails"]["formal_orbit_pruning_authorized"]
        )

    def test_all_twelve_have_exact_mathematical_evidence(self) -> None:
        for record in self.root_manifest["instances"]:
            status = record["exact_result"]["status"]
            if status == "EXACT_LP_FEASIBLE":
                witness = record["exact_result"]["feasible_witness"]
                self.assertTrue(all(witness["exact_checks"].values()))
                self.assertEqual(witness["minimum_exact_slack"], "0/1")
                self.assertIsNone(record["artifacts"]["proof"])
                self.assertEqual(record["status_ledger"]["root_lp"], "LP_FEASIBLE")
            else:
                self.assertEqual(status, "EXACT_FARKAS_CONTRADICTION")
                certificate = record["exact_result"]["farkas_certificate"]
                self.assertTrue(all(certificate["exact_checks"].values()))
                self.assertGreater(certificate["combined_rhs_after_bounds"], 0)
                self.assertIsNotNone(record["artifacts"]["proof"])
                self.assertEqual(record["status_ledger"]["root_lp"], "SOLVER_UNSAT")
                self.assertEqual(record["status_ledger"]["proof"], "PROOF_GENERATED")
            self.assertEqual(record["status_ledger"]["verification"], "NOT_STARTED")
            self.assertFalse(record["formal_pruning_authorized"])

    def test_independent_audit_confirms_all_exact_evidence(self) -> None:
        self.assertEqual(self.audit["status"], "PASS")
        self.assertEqual(self.audit["summary"]["comparisons_passed"], 12)
        self.assertEqual(self.audit["summary"]["exact_lp_feasible_confirmed"], 6)
        self.assertEqual(
            self.audit["summary"]["exact_farkas_contradictions_confirmed"], 6
        )
        self.assertTrue(self.audit["summary"]["all_exact_evidence_confirmed"])
        self.assertFalse(self.audit["method"]["imports_production_root_lp"])
        self.assertFalse(self.audit["method"]["imports_production_opb_parser"])
        self.assertFalse(self.audit["method"]["imports_production_farkas_renderer"])

    def test_checked_in_checkpoint_is_byte_identical(self) -> None:
        self.assertEqual(_files(self.generated), _files(CHECKPOINT))

    def test_checksum_manifest_covers_every_output(self) -> None:
        rows = _checksum_rows(CHECKPOINT)
        observed = sorted(
            path.relative_to(CHECKPOINT).as_posix()
            for path in CHECKPOINT.rglob("*")
            if path.is_file() and path.name != "SHA256SUMS"
        )
        self.assertEqual(sorted(rows), observed)
        for relative, expected in rows.items():
            self.assertEqual(sha256_file(CHECKPOINT / relative), expected)

    def test_nonempty_output_is_rejected_without_deletion(self) -> None:
        with tempfile.TemporaryDirectory(prefix="horizon-root-lp-nonempty-") as tmp:
            output = Path(tmp)
            marker = output / "preserve.txt"
            marker.write_text("preserve me\n", encoding="utf-8")
            with self.assertRaisesRegex(RootLPError, "must be empty"):
                generate_root_lp_checkpoint(CANDIDATE, DIRECT, output)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve me\n")


class RootLPVerificationArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.phase = json.loads(
            (VERIFICATION / "phase.manifest.json").read_text(encoding="utf-8")
        )
        cls.verification = json.loads(
            (VERIFICATION / "verification.manifest.json").read_text(
                encoding="utf-8"
            )
        )
        cls.audit = json.loads(
            (VERIFICATION / "independent-audit.json").read_text(encoding="utf-8")
        )
        cls.root = json.loads(
            (CHECKPOINT / "root-lp.manifest.json").read_text(encoding="utf-8")
        )

    def test_six_proofs_are_verified_and_only_those_orbits_are_pruned(self) -> None:
        self.assertEqual(self.verification["status"], "VERIFIED_UNSAT")
        self.assertEqual(self.verification["summary"]["verified_unsat"], 6)
        self.assertEqual(self.phase["summary"]["formal_orbits_pruned"], 6)
        self.assertEqual(
            self.phase["summary"]["formally_pruned_orbit_indices"],
            [1, 3, 6, 7, 8, 11],
        )
        self.assertEqual(
            self.phase["summary"]["survivor_orbit_indices"], [0, 2, 4, 5, 9, 10]
        )
        self.assertFalse(self.phase["summary"]["class_formally_eliminated"])

    def test_every_verification_has_hashes_require_unsat_and_success_log(self) -> None:
        root_records = {
            int(row["orbit_index"]): row for row in self.root["instances"]
        }
        for record in self.verification["instances"]:
            orbit = int(record["orbit_index"])
            source = root_records[orbit]
            formula = CHECKPOINT / source["artifacts"]["verifier_normalized_formula"]["path"]
            proof = CHECKPOINT / source["artifacts"]["proof"]["path"]
            self.assertEqual(sha256_file(formula), record["formula"]["expected_sha256"])
            self.assertEqual(sha256_file(proof), record["proof"]["expected_sha256"])
            self.assertTrue(all(record["prechecks"].values()))
            self.assertTrue(all(record["verification_checks"].values()))
            self.assertEqual(record["status"], "VERIFIED_UNSAT")
            self.assertTrue(record["formal_pruning_authorized"])
            log = (VERIFICATION / record["verification_log"]["path"]).read_text(
                encoding="utf-8"
            )
            self.assertIn('"--requireUnsat"', log)
            self.assertIn("exit_code: 0\n", log)
            self.assertIn("reported_success: true\n", log)
            self.assertIn("stdout:\nVerification succeeded.\n", log)

    def test_independent_verification_audit_passes_six_of_six(self) -> None:
        self.assertEqual(self.audit["status"], "PASS")
        self.assertEqual(self.audit["summary"]["verification_records"], 6)
        self.assertEqual(self.audit["summary"]["records_passing"], 6)
        self.assertEqual(self.audit["summary"]["verified_unsat_confirmed"], 6)
        self.assertFalse(self.audit["summary"]["class_formally_eliminated"])

    def test_verifier_identity_is_bound_to_preserved_build(self) -> None:
        verifier = self.verification["verifier"]
        self.assertEqual(verifier["reported_package_version"], "0.3a0")
        self.assertEqual(
            verifier["wheel"]["sha256"],
            "3844f3b416c870f6ef96fc737125e4ec97b6cfd1c4d1726a2bc158626c77b369",
        )
        self.assertEqual(
            verifier["build_provenance"]["immutable_source_sha256"],
            "c4c1ddc812affd9bd05c452855bdfcd614a68906f8bf536fab8bcd4b3123ae56",
        )
        self.assertEqual(verifier["required_flag"], "--requireUnsat")
        self.assertTrue(
            verifier["installed_wheel_audit"]["all_recorded_files_match"]
        )

    def test_verification_checksums_cover_every_output(self) -> None:
        rows = _checksum_rows(VERIFICATION)
        observed = sorted(
            path.relative_to(VERIFICATION).as_posix()
            for path in VERIFICATION.rglob("*")
            if path.is_file() and path.name != "SHA256SUMS"
        )
        self.assertEqual(sorted(rows), observed)
        for relative, expected in rows.items():
            self.assertEqual(sha256_file(VERIFICATION / relative), expected)


if __name__ == "__main__":
    unittest.main()
