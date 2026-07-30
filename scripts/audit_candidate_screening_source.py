#!/usr/bin/env python3
"""Compare generated candidate screens with legacy full_minpoints semantics."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
from pathlib import Path
from typing import Any

from horizonlink.canonical import sha256_file, write_json, write_sha256_sidecar
from horizonlink.input import load_link
from horizonlink.manifest import build_manifest


ROW_RE = re.compile(r"^(?P<terms>(?:\+1 x[1-9][0-9]* ?)+)(?P<relation>>=|<=) (?P<rhs>-?[0-9]+) ;$")
TERM_RE = re.compile(r"\+1 x([1-9][0-9]*)")


def _containing(
    block_sets: tuple[frozenset[int], ...], subset: tuple[int, ...]
) -> tuple[int, ...]:
    target = frozenset(subset)
    return tuple(
        index for index, block in enumerate(block_sets) if target <= block
    )


def _legacy_rows(
    point_labels: tuple[int, ...],
    link_blocks: tuple[tuple[int, ...], ...],
    representative: tuple[int, ...],
) -> tuple[tuple[tuple[int, ...], str, int], ...]:
    """Independent row construction mirroring legacy full_minpoints.py."""

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

    bounded: list[
        tuple[tuple[int, ...], int | None, int | None]
    ] = []
    for four in residual:
        bounded.append((_containing(seven_sets, four), 1, None))
    representative_set = frozenset(representative)
    for point, lower in zip(point_labels, minimum_extension):
        bounded.append(
            (
                _containing(seven_sets, (point,)),
                lower,
                lower if point in representative_set else None,
            )
        )
    for pair in itertools.combinations(point_labels, 2):
        pair_set = frozenset(pair)
        lower = 7 - sum(pair_set <= block for block in link_sets)
        if lower > 0:
            bounded.append((_containing(seven_sets, pair), lower, None))
    for triple in itertools.combinations(point_labels, 3):
        triple_set = frozenset(triple)
        lower = 3 - sum(triple_set <= block for block in link_sets)
        if lower > 0:
            bounded.append((_containing(seven_sets, triple), lower, None))
    bounded.append((tuple(range(len(sevens))), 14, 14))

    rows = []
    for variables, lower, upper in bounded:
        if lower is not None:
            rows.append((variables, ">=", lower))
        if upper is not None:
            rows.append((variables, "<=", upper))
    return tuple(rows)


def _parse_opb(path: Path) -> tuple[tuple[tuple[int, ...], str, int], ...]:
    rows = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw_line.strip()
        if not line or line.startswith("*"):
            continue
        match = ROW_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"{path}:{line_number}: unsupported OPB row")
        variables = tuple(
            int(value) - 1
            for value in TERM_RE.findall(match.group("terms"))
        )
        rows.append(
            (
                variables,
                match.group("relation"),
                int(match.group("rhs")),
            )
        )
    return tuple(rows)


def _canonical_hash(
    rows: tuple[tuple[tuple[int, ...], str, int], ...],
    variable_count: int,
) -> str:
    canonical_rows = []
    for variables, relation, rhs in rows:
        coefficient = 1 if relation == ">=" else -1
        canonical_rhs = rhs if relation == ">=" else -rhs
        canonical_rows.append(
            (
                ">=",
                canonical_rhs,
                tuple(
                    (variable + 1, coefficient) for variable in variables
                ),
            )
        )
    payload = {"variables": variable_count, "rows": canonical_rows}
    encoded = json.dumps(
        payload, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def audit(
    input_path: Path,
    corpus_directory: Path,
    historical_source: Path | None,
) -> dict[str, Any]:
    link = load_link(input_path)
    structural = build_manifest(link)
    corpus_path = corpus_directory / "corpus.manifest.json"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    instances = {
        row["orbit_index"]: row for row in corpus["instances"]
    }
    expected_indices = list(
        range(
            structural["candidate_minimum_point_sets"]["orbit_count"]
        )
    )
    comparisons = []
    for orbit_index in expected_indices:
        orbit = structural["candidate_minimum_point_sets"]["orbits"][
            orbit_index
        ]
        record = instances.get(orbit_index)
        if record is None:
            comparisons.append(
                {
                    "orbit_index": orbit_index,
                    "passed": False,
                    "error": "missing generated formula record",
                }
            )
            continue
        representative = tuple(orbit["representative"])
        expected = _legacy_rows(
            link.point_labels, link.blocks, representative
        )
        formula_path = corpus_directory / record["formula"]["path"]
        observed = _parse_opb(formula_path)
        first_difference = None
        for row_index, (left, right) in enumerate(
            itertools.zip_longest(expected, observed)
        ):
            if left != right:
                first_difference = {
                    "row_index": row_index,
                    "expected": left,
                    "observed": right,
                }
                break
        canonical_hash = _canonical_hash(expected, len(corpus["variable_map"]))
        checks = {
            "representative_equal": (
                record["candidate_minimum_points"]
                == list(representative)
            ),
            "native_formula_hash_equal": (
                sha256_file(formula_path) == record["formula"]["sha256"]
            ),
            "row_count_equal": len(expected) == len(observed),
            "rows_equal_in_order": expected == observed,
            "independent_canonical_hash_equal": (
                canonical_hash
                == record["formula"]["canonical_formula_sha256"]
            ),
        }
        comparisons.append(
            {
                "orbit_index": orbit_index,
                "representative": list(representative),
                "expected_rows": len(expected),
                "observed_rows": len(observed),
                "independent_canonical_formula_sha256": canonical_hash,
                "checks": checks,
                "first_difference": first_difference,
                "passed": all(checks.values()),
            }
        )

    all_passed = (
        sorted(instances) == expected_indices
        and all(row["passed"] for row in comparisons)
    )
    source_record: dict[str, Any]
    if historical_source is None:
        source_record = {"status": "NOT_SUPPLIED"}
    else:
        source_record = {
            "status": "AUDITED",
            "path": str(historical_source),
            "sha256": sha256_file(historical_source),
        }
    return {
        "schema_version": (
            "horizonmath.candidate-screening-source-comparison.v1"
        ),
        "status": "PASS" if all_passed else "ERROR",
        "input": {
            "link_path": str(input_path),
            "link_sha256": sha256_file(input_path),
            "canonical_labeled_link_sha256": (
                structural["input"]["canonical_labeled_link_sha256"]
            ),
            "corpus_manifest_path": str(corpus_path),
            "corpus_manifest_sha256": sha256_file(corpus_path),
            "historical_source": source_record,
        },
        "method": {
            "description": (
                "Independent stdlib transcription of every bounded row in "
                "legacy full_minpoints.py, followed by an ordered comparison "
                "with every row parsed from each generated OPB."
            ),
            "imports_candidate_formula_builder": False,
        },
        "comparisons": comparisons,
        "summary": {
            "expected_orbits": len(expected_indices),
            "observed_orbits": len(instances),
            "comparisons_passed": sum(
                row["passed"] for row in comparisons
            ),
            "all_orbits_accounted_for": sorted(instances)
            == expected_indices,
            "all_rows_equal_in_order": all_passed,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--corpus-directory", type=Path, required=True)
    parser.add_argument("--historical-source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(
        args.input, args.corpus_directory, args.historical_source
    )
    write_json(args.output, report)
    write_sha256_sidecar(args.output)
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
