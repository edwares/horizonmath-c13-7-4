from __future__ import annotations

import itertools
import tempfile
import unittest
from pathlib import Path

from horizonlink.candidate_screening import (
    generate_candidate_screening_corpus,
)
from horizonlink.input import load_link
from horizonlink.manifest import build_manifest
from horizonlink.pb import build_candidate_minimum_set_formula


ROOT = Path(__file__).resolve().parents[1]
CLASS52 = ROOT / "data" / "class52.link.json"
HARD4 = {14, 19, 20, 21, 22, 23, 24, 25}


def _historical_full_minpoints_rows(
    point_labels: tuple[int, ...],
    link_blocks: tuple[tuple[int, ...], ...],
    representative: tuple[int, ...],
) -> tuple[tuple[tuple[int, ...], int | None, int | None], ...]:
    """Independent transcription of legacy_source/full_minpoints.py."""

    sevens = tuple(itertools.combinations(point_labels, 7))
    seven_sets = tuple(frozenset(block) for block in sevens)
    link_sets = tuple(frozenset(block) for block in link_blocks)
    covered_fours = {
        four
        for block in link_blocks
        for four in itertools.combinations(block, 4)
    }
    residual = tuple(
        four
        for four in itertools.combinations(point_labels, 4)
        if four not in covered_fours
    )
    link_degrees = tuple(
        sum(point in block for block in link_sets)
        for point in point_labels
    )
    minimum_extension = tuple(15 - degree for degree in link_degrees)

    def containing(subset: tuple[int, ...]) -> tuple[int, ...]:
        target = frozenset(subset)
        return tuple(
            index
            for index, block in enumerate(seven_sets)
            if target <= block
        )

    rows: list[tuple[tuple[int, ...], int | None, int | None]] = []
    for four in residual:
        rows.append((containing(four), 1, None))
    representative_set = frozenset(representative)
    for point, lower in zip(point_labels, minimum_extension):
        rows.append(
            (
                containing((point,)),
                lower,
                lower if point in representative_set else None,
            )
        )
    for pair in itertools.combinations(point_labels, 2):
        pair_set = frozenset(pair)
        lower = 7 - sum(pair_set <= block for block in link_sets)
        if lower > 0:
            rows.append((containing(pair), lower, None))
    for triple in itertools.combinations(point_labels, 3):
        triple_set = frozenset(triple)
        lower = 3 - sum(triple_set <= block for block in link_sets)
        if lower > 0:
            rows.append((containing(triple), lower, None))
    rows.append((tuple(range(len(sevens))), 14, 14))
    return tuple(rows)


class CandidateScreeningRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.link = load_link(CLASS52)
        cls.structural = build_manifest(cls.link)
        cls.temporary = tempfile.TemporaryDirectory(
            prefix="horizonlink-candidate-screening-test-"
        )
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.output = Path(cls.temporary.name)
        cls.analysis, cls.corpus = generate_candidate_screening_corpus(
            cls.structural, cls.output
        )

    def test_one_formula_per_orbit_and_no_pruning(self) -> None:
        self.assertEqual(self.corpus["summary"]["candidate_orbits"], 26)
        self.assertEqual(self.corpus["summary"]["formulas_generated"], 26)
        self.assertTrue(
            self.corpus["summary"]["all_orbits_accounted_for"]
        )
        self.assertEqual(
            self.corpus["summary"]["orbit_indices"], list(range(26))
        )
        self.assertFalse(
            self.corpus["scope"]["formal_orbit_pruning_authorized"]
        )
        self.assertTrue(
            all(
                not record["formal_pruning_authorized"]
                for record in self.corpus["instances"]
            )
        )

    def test_class52_row_counts(self) -> None:
        for record in self.corpus["instances"]:
            formula = record["formula"]
            self.assertEqual(formula["variables"], 792)
            self.assertEqual(formula["matrix_rows"], 562)
            self.assertEqual(formula["opb_constraints"], 567)
            self.assertEqual(
                formula["serialized_family_counts"],
                {
                    "candidate_point_degree": 16,
                    "extension_block_count": 2,
                    "pair_degree_lower": 66,
                    "residual_four_coverage": 279,
                    "triple_degree_lower": 204,
                },
            )

    def test_all_bounded_rows_match_historical_source_semantics(self) -> None:
        point_labels = self.link.point_labels
        link_blocks = self.link.blocks
        for orbit in self.structural["candidate_minimum_point_sets"][
            "orbits"
        ]:
            representative = tuple(orbit["representative"])
            built = build_candidate_minimum_set_formula(
                point_labels, link_blocks, representative
            )
            observed = tuple(
                (row.variables, row.lower, row.upper)
                for row in built["bounded_rows"]
            )
            expected = _historical_full_minpoints_rows(
                point_labels, link_blocks, representative
            )
            self.assertEqual(observed, expected)

    def test_corpus_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonlink-candidate-screening-rerun-"
        ) as temporary:
            second_output = Path(temporary)
            _, second_corpus = generate_candidate_screening_corpus(
                self.structural, second_output
            )
            self.assertEqual(self.corpus, second_corpus)
            first_files = {
                path.relative_to(self.output): path.read_bytes()
                for path in self.output.rglob("*")
                if path.is_file()
            }
            second_files = {
                path.relative_to(second_output): path.read_bytes()
                for path in second_output.rglob("*")
                if path.is_file()
            }
            self.assertEqual(first_files, second_files)

    def test_recovered_hard4_is_only_a_regression_target(self) -> None:
        historical = {
            row["orbit_index"]
            for row in self.corpus["instances"]
            if row["orbit_index"] in HARD4
        }
        self.assertEqual(historical, HARD4)
        self.assertTrue(
            all(
                row["status_ledger"]["solver"] == "NOT_STARTED"
                and row["status_ledger"]["verification"] == "NOT_STARTED"
                for row in self.corpus["instances"]
            )
        )

    def test_nonempty_output_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonlink-candidate-screening-nonempty-"
        ) as temporary:
            output = Path(temporary)
            marker = output / "unrelated.txt"
            marker.write_text("preserve me\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be empty"):
                generate_candidate_screening_corpus(
                    self.structural, output
                )
            self.assertEqual(
                marker.read_text(encoding="utf-8"), "preserve me\n"
            )


if __name__ == "__main__":
    unittest.main()
