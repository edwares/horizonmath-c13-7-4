"""Independent audit of serialized candidate-orbit PB formulas."""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from pathlib import Path
from typing import Any

from horizonlink.canonical import (
    pretty_json_bytes,
    sha256_bytes,
    sha256_file,
)
from horizonlink.input import load_link
from horizonlink.manifest import build_manifest


AUDIT_SCHEMA_VERSION = (
    "horizonmath.candidate-formula-independent-audit.v1"
)
CORPUS_SCHEMA_VERSION = "horizonmath.candidate-screening-pb-corpus.v1"
HEADER_RE = re.compile(
    r"^\* #variable= (?P<variables>[0-9]+) "
    r"#constraint= (?P<constraints>[0-9]+)$"
)
ROW_RE = re.compile(
    r"^(?P<terms>(?:\+1 x[1-9][0-9]* ?)+)"
    r"(?P<relation>>=|<=) (?P<rhs>-?[0-9]+) ;$"
)
TERM_RE = re.compile(r"\+1 x([1-9][0-9]*)")


class CandidateAuditError(ValueError):
    """Raised when a candidate formula corpus fails closed."""


class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        _DuplicateKeyError,
    ) as exc:
        raise CandidateAuditError(
            f"cannot load {path.name}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise CandidateAuditError(
            f"{path.name} must contain a JSON object"
        )
    return value


def _containing(
    block_sets: tuple[frozenset[int], ...],
    subset: tuple[int, ...],
) -> tuple[int, ...]:
    target = frozenset(subset)
    return tuple(
        index for index, block in enumerate(block_sets) if target <= block
    )


def _independent_expected_rows(
    point_labels: tuple[int, ...],
    link_blocks: tuple[tuple[int, ...], ...],
    representative: tuple[int, ...],
) -> tuple[tuple[tuple[int, ...], str, int, str], ...]:
    """Reconstruct every row without importing the production PB builder."""

    sevens = tuple(itertools.combinations(point_labels, 7))
    seven_sets = tuple(frozenset(block) for block in sevens)
    link_sets = tuple(frozenset(block) for block in link_blocks)
    covered_fours = {
        four
        for block in link_blocks
        for four in itertools.combinations(block, 4)
    }
    residual_fours = tuple(
        four
        for four in itertools.combinations(point_labels, 4)
        if four not in covered_fours
    )
    link_degrees = tuple(
        sum(point in block for block in link_sets)
        for point in point_labels
    )
    minimum_extension_degrees = tuple(
        15 - degree for degree in link_degrees
    )

    bounded: list[
        tuple[
            tuple[int, ...],
            int | None,
            int | None,
            str,
        ]
    ] = []
    for four in residual_fours:
        bounded.append(
            (
                _containing(seven_sets, four),
                1,
                None,
                "residual_four_coverage",
            )
        )
    representative_set = frozenset(representative)
    for point, lower in zip(
        point_labels, minimum_extension_degrees
    ):
        bounded.append(
            (
                _containing(seven_sets, (point,)),
                lower,
                lower if point in representative_set else None,
                "candidate_point_degree",
            )
        )
    for pair in itertools.combinations(point_labels, 2):
        pair_set = frozenset(pair)
        lower = 7 - sum(pair_set <= block for block in link_sets)
        if lower > 0:
            bounded.append(
                (
                    _containing(seven_sets, pair),
                    lower,
                    None,
                    "pair_degree_lower",
                )
            )
    for triple in itertools.combinations(point_labels, 3):
        triple_set = frozenset(triple)
        lower = 3 - sum(triple_set <= block for block in link_sets)
        if lower > 0:
            bounded.append(
                (
                    _containing(seven_sets, triple),
                    lower,
                    None,
                    "triple_degree_lower",
                )
            )
    bounded.append(
        (
            tuple(range(len(sevens))),
            14,
            14,
            "extension_block_count",
        )
    )

    rows = []
    for variables, lower, upper, family in bounded:
        if lower is not None:
            rows.append((variables, ">=", lower, family))
        if upper is not None:
            rows.append((variables, "<=", upper, family))
    return tuple(rows)


def _parse_opb(path: Path) -> dict[str, Any]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise CandidateAuditError(
            f"cannot read {path.name}: {exc}"
        ) from exc
    if not lines:
        raise CandidateAuditError(f"{path.name} is empty")
    header = HEADER_RE.fullmatch(lines[0])
    if header is None:
        raise CandidateAuditError(
            f"{path.name}: malformed OPB header"
        )
    rows = []
    comments = []
    for line_number, raw_line in enumerate(lines[1:], start=2):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("*"):
            comments.append(line)
            continue
        match = ROW_RE.fullmatch(line)
        if match is None:
            raise CandidateAuditError(
                f"{path.name}:{line_number}: unsupported OPB row"
            )
        variables = tuple(
            int(value) - 1
            for value in TERM_RE.findall(match.group("terms"))
        )
        if tuple(sorted(set(variables))) != variables:
            raise CandidateAuditError(
                f"{path.name}:{line_number}: variables are not unique "
                "and increasing"
            )
        rows.append(
            (
                variables,
                match.group("relation"),
                int(match.group("rhs")),
            )
        )
    return {
        "variable_count": int(header.group("variables")),
        "declared_constraint_count": int(
            header.group("constraints")
        ),
        "comments": comments,
        "rows": tuple(rows),
    }


def _canonical_formula_sha256(
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
                    (variable + 1, coefficient)
                    for variable in variables
                ),
            )
        )
    payload = {
        "variables": variable_count,
        "rows": canonical_rows,
    }
    encoded = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalized_native_row_sha256(
    rows: tuple[tuple[tuple[int, ...], str, int], ...],
) -> str:
    payload = [
        (relation, rhs, variables)
        for variables, relation, rhs in rows
    ]
    return sha256_bytes(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )


def _verify_corpus_checksums(corpus_directory: Path) -> bool:
    checksum_path = corpus_directory / "SHA256SUMS"
    try:
        lines = checksum_path.read_text(
            encoding="utf-8"
        ).splitlines()
    except (OSError, UnicodeError) as exc:
        raise CandidateAuditError(
            f"cannot read corpus checksums: {exc}"
        ) from exc
    rows = []
    for line_number, line in enumerate(lines, start=1):
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise CandidateAuditError(
                f"invalid corpus SHA256SUMS row {line_number}"
            )
        expected, relative = parts
        if (
            len(expected) != 64
            or any(character not in "0123456789abcdef" for character in expected)
            or not relative
            or relative.startswith("/")
            or ".." in Path(relative).parts
        ):
            raise CandidateAuditError(
                f"invalid corpus SHA256SUMS row {line_number}"
            )
        path = corpus_directory / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise CandidateAuditError(
                f"corpus checksum mismatch: {relative}"
            )
        rows.append(relative)
    expected_files = sorted(
        path.relative_to(corpus_directory).as_posix()
        for path in corpus_directory.rglob("*")
        if path.is_file()
        and path.name != "SHA256SUMS"
        and not path.name.endswith(".sha256")
    )
    if sorted(rows) != expected_files or len(rows) != len(set(rows)):
        raise CandidateAuditError(
            "corpus SHA256SUMS accounting is incomplete"
        )
    return True


def audit_candidate_formula_corpus(
    input_path: Path,
    corpus_directory: Path,
    *,
    input_artifact: dict[str, Any],
    corpus_artifact_path: str = "corpus/corpus.manifest.json",
) -> dict[str, Any]:
    """Compare every serialized formula with an independent construction."""

    link = load_link(input_path)
    structural = build_manifest(link, 4)
    if structural.get("status") != "ENUMERATED":
        raise CandidateAuditError("input structural analysis failed")
    corpus_path = corpus_directory / "corpus.manifest.json"
    corpus = _load_json_object(corpus_path)
    if (
        corpus.get("schema_version") != CORPUS_SCHEMA_VERSION
        or corpus.get("status") != "FORMULAS_GENERATED"
    ):
        raise CandidateAuditError(
            "candidate formula corpus schema or status is invalid"
        )
    checksum_passed = _verify_corpus_checksums(corpus_directory)
    instances = {
        int(row["orbit_index"]): row
        for row in corpus.get("instances", [])
    }
    expected_orbits = structural["candidate_minimum_point_sets"][
        "orbits"
    ]
    expected_indices = list(range(len(expected_orbits)))
    comparisons = []
    for orbit_index, orbit in enumerate(expected_orbits):
        representative = tuple(orbit["representative"])
        record = instances.get(orbit_index)
        if record is None:
            comparisons.append(
                {
                    "orbit_index": orbit_index,
                    "representative": list(representative),
                    "passed": False,
                    "error": "missing generated formula record",
                }
            )
            continue
        expected_with_families = _independent_expected_rows(
            link.point_labels,
            link.blocks,
            representative,
        )
        expected = tuple(
            (variables, relation, rhs)
            for variables, relation, rhs, _ in expected_with_families
        )
        expected_family_counts: dict[str, int] = {}
        for _, _, _, family in expected_with_families:
            expected_family_counts[family] = (
                expected_family_counts.get(family, 0) + 1
            )
        formula_path = corpus_directory / record["formula"]["path"]
        parsed = _parse_opb(formula_path)
        observed = parsed["rows"]
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
        canonical_hash = _canonical_formula_sha256(
            expected,
            parsed["variable_count"],
        )
        normalized_hash = _normalized_native_row_sha256(expected)
        metadata_path = corpus_directory / record["metadata"]["path"]
        metadata = _load_json_object(metadata_path)
        record_without_metadata = {
            key: value
            for key, value in record.items()
            if key != "metadata"
        }
        expected_comments = [
            (
                f"* class {link.class_index} candidate-minimum-point "
                f"orbit {orbit_index}"
            ),
            (
                "* candidate full-degree-15 points "
                f"{representative}"
            ),
            (
                "* necessary-condition screen; formal pruning requires "
                "VERIFIED_UNSAT"
            ),
        ]
        checks = {
            "representative_equal": (
                record["candidate_minimum_points"]
                == list(representative)
            ),
            "orbit_metadata_equal": (
                record["candidate_orbit"]
                == {
                    "member_count": len(orbit["members"]),
                    "stabilizer_order": orbit["stabilizer_order"],
                    "orbit_stabilizer_check": orbit[
                        "orbit_stabilizer_check"
                    ],
                }
            ),
            "native_formula_bytes_equal": (
                formula_path.stat().st_size
                == record["formula"]["bytes"]
            ),
            "native_formula_hash_equal": (
                sha256_file(formula_path)
                == record["formula"]["sha256"]
            ),
            "header_variable_count_equal": (
                parsed["variable_count"]
                == record["formula"]["variables"]
                == len(corpus["variable_map"])
            ),
            "header_constraint_count_equal": (
                parsed["declared_constraint_count"]
                == len(observed)
                == record["formula"]["opb_constraints"]
            ),
            "comments_equal": parsed["comments"] == expected_comments,
            "row_count_equal": len(expected) == len(observed),
            "rows_equal_in_order": expected == observed,
            "family_counts_equal": (
                dict(sorted(expected_family_counts.items()))
                == record["formula"]["serialized_family_counts"]
            ),
            "independent_canonical_hash_equal": (
                canonical_hash
                == record["formula"]["canonical_formula_sha256"]
            ),
            "independent_normalized_row_hash_equal": (
                normalized_hash
                == record["formula"]["normalized_native_row_sha256"]
            ),
            "metadata_bytes_equal": (
                metadata_path.stat().st_size
                == len(pretty_json_bytes(metadata))
            ),
            "metadata_hash_equal": (
                sha256_file(metadata_path)
                == record["metadata"]["sha256"]
            ),
            "metadata_record_equal": (
                metadata == record_without_metadata
            ),
            "status_boundaries_preserved": (
                record["status_ledger"]
                == {
                    "formula": "FORMULAS_GENERATED",
                    "root_lp": "NOT_STARTED",
                    "solver": "NOT_STARTED",
                    "proof": "NOT_STARTED",
                    "verification": "NOT_STARTED",
                }
                and record["formal_pruning_authorized"] is False
            ),
        }
        comparisons.append(
            {
                "orbit_index": orbit_index,
                "representative": list(representative),
                "expected_rows": len(expected),
                "observed_rows": len(observed),
                "independent_canonical_formula_sha256": canonical_hash,
                "independent_normalized_native_row_sha256": (
                    normalized_hash
                ),
                "checks": checks,
                "first_difference": first_difference,
                "passed": all(checks.values()),
            }
        )

    all_passed = (
        checksum_passed
        and sorted(instances) == expected_indices
        and all(row["passed"] for row in comparisons)
    )
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "status": "PASS" if all_passed else "ERROR",
        "input": {
            "link_artifact": input_artifact,
            "canonical_labeled_link_sha256": structural["input"][
                "canonical_labeled_link_sha256"
            ],
            "corpus_manifest": {
                "path": corpus_artifact_path,
                "bytes": corpus_path.stat().st_size,
                "sha256": sha256_file(corpus_path),
            },
        },
        "method": {
            "id": "independent-full-minpoints-row-audit-v2",
            "description": (
                "Independently reconstruct every bounded row, parse every "
                "serialized OPB row, and compare rows in order together with "
                "headers, comments, family counts, metadata, and hashes."
            ),
            "imports_candidate_formula_builder": False,
            "imports_pb_module": False,
        },
        "comparisons": comparisons,
        "summary": {
            "expected_orbits": len(expected_indices),
            "observed_orbits": len(instances),
            "comparisons_passed": sum(
                row["passed"] for row in comparisons
            ),
            "all_orbits_accounted_for": (
                sorted(instances) == expected_indices
            ),
            "all_rows_equal_in_order": all_passed,
            "corpus_checksums_passed": checksum_passed,
        },
    }
