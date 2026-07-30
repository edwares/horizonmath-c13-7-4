from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from horizonlink.canonical import sha256_file
from horizonlink.census import (
    STRUCTURAL_CENSUS_PRODUCER_VERSION,
    CensusError,
    generate_structural_census,
)
from horizonlink.input import load_link
from horizonlink.profiles import (
    compute_unscreened_degree_profile_orbit_census,
)


ROOT = Path(__file__).resolve().parents[1]
NUMBERING = (
    ROOT
    / "catalog_audit"
    / "build"
    / "authoritative"
    / "numbering.manifest.json"
)
CLASSIFICATION = (
    ROOT
    / "provenance"
    / "classification"
    / "audit"
    / "classification-provenance.audit.json"
)
CHECKPOINT = ROOT / "results" / "structural-census-v0.1.0"


class StructuralCensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(
            prefix="horizonmath-structural-census-test-"
        )
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.output = Path(cls.temporary.name) / "census"
        cls.census, cls.ranking = generate_structural_census(
            NUMBERING,
            CLASSIFICATION,
            cls.output,
        )
        cls.class52 = json.loads(
            (
                cls.output
                / "classes"
                / "class52.structural-census.json"
            ).read_text(encoding="utf-8")
        )

    def test_identity_group_burnside_count_is_closed_form(self) -> None:
        result = compute_unscreened_degree_profile_orbit_census(
            (tuple(range(12)),),
            total_excess=8,
            point_count=12,
        )
        self.assertEqual(
            result["raw_profile_count_before_symmetry"], 75582
        )
        self.assertEqual(result["profile_orbit_count"], 75582)
        self.assertEqual(
            result["profile_orbits_by_minimum_set_size"],
            {
                "4": 495,
                "5": 5544,
                "6": 19404,
                "7": 27720,
                "8": 17325,
                "9": 4620,
                "10": 462,
                "11": 12,
            },
        )
        self.assertTrue(
            result["burnside_audit"][
                "all_divisibility_checks_pass"
            ]
        )

    def test_all_68_classes_are_accounted_for_without_solver_runs(
        self,
    ) -> None:
        self.assertEqual(
            self.census["producer"]["version"],
            STRUCTURAL_CENSUS_PRODUCER_VERSION,
        )
        self.assertEqual(
            self.ranking["producer"]["version"],
            STRUCTURAL_CENSUS_PRODUCER_VERSION,
        )
        self.assertEqual(self.census["status"], "ENUMERATED")
        self.assertEqual(
            self.census["summary"]["enumerated_class_count"], 68
        )
        self.assertEqual(
            self.census["summary"]["class_indices"],
            list(range(1, 69)),
        )
        self.assertTrue(
            self.census["summary"]["all_classes_accounted_for"]
        )
        guardrails = self.census["scope_guardrails"]
        self.assertFalse(guardrails["formulas_generated"])
        self.assertFalse(guardrails["root_lp_run"])
        self.assertFalse(guardrails["solver_run"])
        self.assertFalse(guardrails["proof_generated"])
        self.assertFalse(guardrails["verifier_run"])
        self.assertFalse(guardrails["another_class_eliminated"])
        self.assertFalse(guardrails["C_13_7_4_equals_30_claimed"])

    def test_checked_in_checkpoint_matches_generation(self) -> None:
        generated_files = {
            path.relative_to(self.output): path.read_bytes()
            for path in self.output.rglob("*")
            if path.is_file()
        }
        checkpoint_files = {
            path.relative_to(CHECKPOINT): path.read_bytes()
            for path in CHECKPOINT.rglob("*")
            if path.is_file()
        }
        self.assertEqual(generated_files, checkpoint_files)

    def test_every_generated_input_is_canonical_and_indexed(self) -> None:
        for class_index in range(1, 69):
            path = (
                self.output
                / "inputs"
                / f"class{class_index:02d}.link.json"
            )
            link = load_link(path)
            self.assertEqual(link.class_index, class_index)
            self.assertTrue(link.content_was_canonical)
            self.assertTrue(link.bytes_were_canonical_serialization)
            self.assertEqual(
                link.numbering_source["status"], "AUDITED"
            )

    def test_class52_structural_regression_and_scope_boundary(
        self,
    ) -> None:
        self.assertEqual(
            self.class52["input"]["canonical_labeled_link_sha256"],
            "034d4c7cd44947c6fe2e8d562850611670af399f5d850b2c141990152a6af571",
        )
        self.assertEqual(
            self.class52["automorphism_group"]["order"], 36
        )
        self.assertEqual(
            self.class52["multiplicities"][
                "residual_four_sets"
            ]["count"],
            279,
        )
        self.assertEqual(
            self.class52["candidate_minimum_point_sets"][
                "orbit_count"
            ],
            26,
        )
        self.assertEqual(
            self.class52[
                "unscreened_degree_profile_orbit_census"
            ]["profile_orbit_count"],
            2578,
        )
        self.assertEqual(
            self.class52["status_ledger"][
                "extension_degree_profiles"
            ],
            "NOT_STARTED",
        )
        self.assertEqual(
            self.class52["unavailable_difficulty_metrics"][
                "retained_profile_count"
            ]["status"],
            "NOT_STARTED",
        )

    def test_structural_ranking_and_provisional_pilot(self) -> None:
        rows = self.ranking["classes"]
        self.assertEqual(len(rows), 68)
        self.assertEqual(rows[0]["class_index"], 68)
        self.assertEqual(
            rows[0]["unscreened_degree_profile_orbit_count"], 755
        )
        self.assertEqual(rows[1]["class_index"], 52)
        self.assertEqual(
            rows[1]["unscreened_degree_profile_orbit_count"], 2578
        )
        pilot = self.ranking["provisional_three_class_pilot"]
        self.assertEqual(pilot["status"], "STRUCTURAL_ONLY_PRESELECTION")
        self.assertFalse(pilot["solver_runs_authorized"])
        self.assertEqual(
            pilot["easy_high_symmetry"]["class_index"], 68
        )
        self.assertEqual(pilot["median"]["class_index"], 4)
        self.assertEqual(
            pilot["difficult_low_symmetry"]["class_index"], 59
        )

    def test_checksum_manifest_covers_every_other_file(self) -> None:
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

    def test_no_formula_proof_or_solver_artifacts_are_emitted(
        self,
    ) -> None:
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

    def test_census_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonmath-structural-census-second-"
        ) as temporary:
            second = Path(temporary) / "census"
            generate_structural_census(
                NUMBERING,
                CLASSIFICATION,
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

    def test_nonempty_output_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonmath-structural-census-nonempty-"
        ) as temporary:
            output = Path(temporary)
            marker = output / "preserve.txt"
            marker.write_text("preserve\n", encoding="utf-8")
            with self.assertRaisesRegex(CensusError, "must be empty"):
                generate_structural_census(
                    NUMBERING,
                    CLASSIFICATION,
                    output,
                )
            self.assertEqual(
                marker.read_text(encoding="utf-8"), "preserve\n"
            )


if __name__ == "__main__":
    unittest.main()
