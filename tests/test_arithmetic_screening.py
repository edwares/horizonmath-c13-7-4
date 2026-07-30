from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from horizonlink.arithmetic_screening import (
    ArithmeticScreeningError,
    SOLVER_FREE_PROFILE_SCREENING_PRODUCER_VERSION,
    generate_solver_free_profile_screening,
)
from horizonlink.canonical import sha256_file


ROOT = Path(__file__).resolve().parents[1]
STRUCTURAL_CHECKPOINT = (
    ROOT / "results" / "structural-census-v0.1.0"
)
PILOT_CHECKPOINT = (
    ROOT / "results" / "pilot-screening-v0.1.0"
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _gzip_jsonl_audit(
    root: Path,
    artifact: dict,
) -> tuple[list[dict], str, int]:
    path = root / artifact["path"]
    digest = hashlib.sha256()
    rows = []
    uncompressed_bytes = 0
    with gzip.open(path, "rb") as handle:
        for line in handle:
            digest.update(line)
            uncompressed_bytes += len(line)
            rows.append(json.loads(line))
    return rows, digest.hexdigest(), uncompressed_bytes


class ArithmeticScreeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(
            prefix="horizonmath-pilot-screening-test-"
        )
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.output = Path(cls.temporary.name) / "screening"
        cls.manifest, cls.ranking = (
            generate_solver_free_profile_screening(
                STRUCTURAL_CHECKPOINT,
                [68, 4, 59],
                cls.output,
            )
        )
        cls.class_manifests = {
            class_index: _read_json(
                cls.output
                / "classes"
                / f"class{class_index:02d}.screening.manifest.json"
            )
            for class_index in (4, 59, 68)
        }

    def test_pilot_counts_and_status_boundaries(self) -> None:
        expected = {
            68: {
                "candidate": 12,
                "exact": 88,
                "exact_retained": 87,
                "profiles": 755,
                "discarded": 4,
                "retained": 751,
            },
            4: {
                "candidate": 279,
                "exact": 2123,
                "exact_retained": 2122,
                "profiles": 39618,
                "discarded": 54,
                "retained": 39564,
            },
            59: {
                "candidate": 495,
                "exact": 3797,
                "exact_retained": 3796,
                "profiles": 75582,
                "discarded": 78,
                "retained": 75504,
            },
        }
        self.assertEqual(
            self.manifest["producer"]["version"],
            SOLVER_FREE_PROFILE_SCREENING_PRODUCER_VERSION,
        )
        self.assertEqual(self.manifest["status"], "ENUMERATED")
        self.assertEqual(
            self.manifest["summary"][
                "unscreened_profile_orbit_count"
            ],
            115955,
        )
        self.assertEqual(
            self.manifest["summary"][
                "discarded_profile_count_by_direct_arithmetic"
            ],
            136,
        )
        self.assertEqual(
            self.manifest["summary"][
                "retained_profile_count_after_solver_free_screening"
            ],
            115819,
        )
        for class_index, counts in expected.items():
            manifest = self.class_manifests[class_index]
            candidate = manifest["candidate_orbit_screening"]
            exact = manifest["exact_minimum_set_screening"]
            profiles = manifest["degree_profile_screening"]
            self.assertEqual(
                candidate["orbit_count"], counts["candidate"]
            )
            self.assertEqual(
                candidate["retained_count"], counts["candidate"]
            )
            self.assertEqual(candidate["discarded_count"], 0)
            self.assertEqual(exact["orbit_count"], counts["exact"])
            self.assertEqual(
                exact["retained_case_count"],
                counts["exact_retained"],
            )
            self.assertEqual(exact["discarded_case_count"], 1)
            self.assertEqual(
                profiles["unscreened_profile_orbit_count"],
                counts["profiles"],
            )
            self.assertEqual(
                profiles["discarded_profile_orbit_count"],
                counts["discarded"],
            )
            self.assertEqual(
                profiles["retained_profile_orbit_count"],
                counts["retained"],
            )
            self.assertEqual(
                profiles["rules"],
                {
                    "EXTENSION_POINT_DEGREE_EXCEEDS_BLOCK_COUNT": (
                        counts["discarded"]
                    ),
                    "PASSED_SOLVER_FREE_ARITHMETIC_SCREENS": (
                        counts["retained"]
                    ),
                },
            )
            self.assertEqual(
                manifest["status_ledger"]["solver"], "NOT_STARTED"
            )
            self.assertFalse(
                manifest["scope_guardrails"]["formulas_generated"]
            )
            self.assertFalse(
                manifest["scope_guardrails"]["root_lp_run"]
            )
            self.assertFalse(
                manifest["scope_guardrails"]["solver_run"]
            )
            self.assertFalse(
                manifest["scope_guardrails"]["proof_generated"]
            )
            self.assertFalse(
                manifest["scope_guardrails"]["verifier_run"]
            )

    def test_every_candidate_orbit_has_a_retained_decision(self) -> None:
        for manifest in self.class_manifests.values():
            candidate = manifest["candidate_orbit_screening"]
            decisions = candidate["decisions"]
            self.assertEqual(
                [row["orbit_index"] for row in decisions],
                list(range(candidate["orbit_count"])),
            )
            self.assertTrue(
                all(
                    row["disposition"] == "RETAINED"
                    and row["evidence_status"]
                    == "NO_CONTRADICTION_FOUND"
                    for row in decisions
                )
            )
            self.assertTrue(
                candidate["accounting"][
                    "no_candidate_orbit_disappeared"
                ]
            )

    def test_every_exact_case_and_profile_is_in_artifacts(self) -> None:
        for class_index, manifest in self.class_manifests.items():
            exact = manifest["exact_minimum_set_screening"]
            exact_rows, exact_hash, exact_bytes = (
                _gzip_jsonl_audit(
                    self.output,
                    exact["artifact"],
                )
            )
            self.assertEqual(
                len(exact_rows), exact["orbit_count"]
            )
            self.assertEqual(
                exact_hash,
                exact["artifact"]["uncompressed_sha256"],
            )
            self.assertEqual(
                exact_bytes,
                exact["artifact"]["uncompressed_bytes"],
            )
            self.assertEqual(
                [row["case_id"] for row in exact_rows],
                list(range(exact["orbit_count"])),
            )
            discarded_cases = [
                row
                for row in exact_rows
                if row["disposition"] == "DISCARDED"
            ]
            self.assertEqual(len(discarded_cases), 1)
            self.assertEqual(
                discarded_cases[0]["minimum_set_size"], 12
            )
            self.assertEqual(
                discarded_cases[0]["rule_id"],
                "NO_POSITIVE_EXCESS_COMPOSITION",
            )

            profiles = manifest["degree_profile_screening"]
            profile_rows, profile_hash, profile_bytes = (
                _gzip_jsonl_audit(
                    self.output,
                    profiles["artifact"],
                )
            )
            self.assertEqual(
                len(profile_rows),
                profiles["unscreened_profile_orbit_count"],
            )
            self.assertEqual(
                profile_hash,
                profiles["artifact"]["uncompressed_sha256"],
            )
            self.assertEqual(
                profile_bytes,
                profiles["artifact"]["uncompressed_bytes"],
            )
            keys = {
                (row["case_id"], row["profile_id"])
                for row in profile_rows
            }
            self.assertEqual(len(keys), len(profile_rows))
            for row in profile_rows:
                self.assertEqual(
                    sum(row["extension_degrees"]), 98
                )
                self.assertTrue(row["orbit_stabilizer_check"])
                self.assertTrue(
                    row["orbit_decision_audit"][
                        "decision_is_orbit_invariant"
                    ]
                )
                self.assertEqual(
                    row["orbit_decision_audit"]["members_checked"],
                    row["orbit_size"],
                )
                if row["disposition"] == "DISCARDED":
                    self.assertGreater(
                        max(row["extension_degrees"]), 14
                    )
                    self.assertEqual(
                        row["evidence_status"],
                        "DIRECT_ARITHMETIC_CONTRADICTION",
                    )
                else:
                    self.assertLessEqual(
                        max(row["extension_degrees"]), 14
                    )
                    self.assertTrue(
                        row["certificate"][
                            "all_pair_intervals_nonempty"
                        ]
                    )

    def test_ranking_is_refined_without_solver_metrics(self) -> None:
        self.assertEqual(
            [row["class_index"] for row in self.ranking["classes"]],
            [68, 4, 59],
        )
        self.assertEqual(
            [
                row[
                    "retained_profile_count_after_solver_free_screening"
                ]
                for row in self.ranking["classes"]
            ],
            [751, 39564, 75504],
        )
        self.assertTrue(
            self.ranking["scope"][
                "solver_free_arithmetic_screening_completed"
            ]
        )
        self.assertFalse(self.ranking["scope"]["root_lp_run"])
        self.assertFalse(self.ranking["scope"]["solver_run"])
        self.assertFalse(self.ranking["scope"]["proof_generated"])

    def test_class52_unscreened_boundary_is_not_rewritten(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonmath-class52-arithmetic-boundary-"
        ) as temporary:
            output = Path(temporary) / "screening"
            manifest, _ = generate_solver_free_profile_screening(
                STRUCTURAL_CHECKPOINT,
                [52],
                output,
            )
            row = manifest["classes"][0]["ranking_metrics"]
            self.assertEqual(
                row["unscreened_degree_profile_orbit_count"],
                2578,
            )
            self.assertEqual(
                row[
                    "discarded_profile_count_by_direct_arithmetic"
                ],
                6,
            )
            self.assertEqual(
                row[
                    "retained_profile_count_after_solver_free_screening"
                ],
                2572,
            )
            historical = _read_json(
                ROOT
                / "data"
                / "class52.recovered-screening-ledger.json"
            )
            self.assertEqual(
                historical["expected_regression"][
                    "degree_profile_orbit_count"
                ],
                107,
            )
            self.assertEqual(
                historical["expected_regression"][
                    "retained_profile_count"
                ],
                20,
            )

    def test_checkpoint_checksums_cover_every_output(self) -> None:
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
                sha256_file(self.output / relative), expected
            )

    def test_gzip_artifacts_are_deterministic_and_timestamp_free(
        self,
    ) -> None:
        for path in self.output.rglob("*.gz"):
            header = path.read_bytes()[:10]
            self.assertEqual(header[:2], b"\x1f\x8b")
            self.assertEqual(header[4:8], b"\x00\x00\x00\x00")
        with tempfile.TemporaryDirectory(
            prefix="horizonmath-pilot-screening-second-"
        ) as temporary:
            second = Path(temporary) / "screening"
            generate_solver_free_profile_screening(
                STRUCTURAL_CHECKPOINT,
                [59, 68, 4],
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
            path.relative_to(PILOT_CHECKPOINT): path.read_bytes()
            for path in PILOT_CHECKPOINT.rglob("*")
            if path.is_file()
        }
        self.assertEqual(generated_files, checkpoint_files)

    def test_no_formula_solver_or_proof_artifacts_exist(self) -> None:
        forbidden_suffixes = {
            ".opb",
            ".pbp",
            ".proof",
            ".log",
        }
        emitted = [
            path
            for path in self.output.rglob("*")
            if path.is_file() and path.suffix in forbidden_suffixes
        ]
        self.assertEqual(emitted, [])

    def test_nonempty_output_is_rejected_without_deletion(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonmath-pilot-screening-nonempty-"
        ) as temporary:
            output = Path(temporary)
            marker = output / "preserve.txt"
            marker.write_text("preserve\n", encoding="utf-8")
            with self.assertRaisesRegex(
                ArithmeticScreeningError,
                "must be empty",
            ):
                generate_solver_free_profile_screening(
                    STRUCTURAL_CHECKPOINT,
                    [68],
                    output,
                )
            self.assertEqual(
                marker.read_text(encoding="utf-8"),
                "preserve\n",
            )


if __name__ == "__main__":
    unittest.main()
