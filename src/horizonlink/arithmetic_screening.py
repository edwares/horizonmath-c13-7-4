"""Deterministic solver-free profile materialization and screening."""

from __future__ import annotations

import csv
import gzip
import hashlib
import itertools
import json
import os
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path, PurePosixPath
from typing import Any

from horizonlink.canonical import (
    compact_json_bytes,
    sha256_bytes,
    sha256_file,
    write_json,
)
from horizonlink.input import load_link
from horizonlink.manifest import build_manifest
from horizonlink.profiles import (
    compute_exact_minimum_set_orbits,
    compute_extension_degree_profiles,
    degree_budget,
    expected_raw_profile_count,
)


GLOBAL_SCHEMA_VERSION = (
    "horizonmath.solver-free-profile-screening.v1"
)
CLASS_SCHEMA_VERSION = (
    "horizonmath.solver-free-profile-screening-class.v1"
)
RANKING_SCHEMA_VERSION = (
    "horizonmath.solver-free-pilot-ranking.v1"
)
STRUCTURAL_CENSUS_SCHEMA_VERSION = (
    "horizonmath.structural-census.v1"
)
STRUCTURAL_CLASS_SCHEMA_VERSION = (
    "horizonmath.structural-census-class.v1"
)
STRUCTURAL_RANKING_SCHEMA_VERSION = (
    "horizonmath.structural-ranking.v1"
)
EXPECTED_POINT_COUNT = 12
EXPECTED_EXTENSION_BLOCK_COUNT = 14
EXPECTED_EXTENSION_BLOCK_SIZE = 7
EXPECTED_EXTENSION_DEGREE_SUM = 98
SOLVER_FREE_PROFILE_SCREENING_PRODUCER_VERSION = "0.6.0"


class ArithmeticScreeningError(ValueError):
    """Raised when provenance or screening accounting fails closed."""


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


def _load_json_object(path: Path) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        _DuplicateKeyError,
    ) as exc:
        raise ArithmeticScreeningError(
            f"cannot load {path.name}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ArithmeticScreeningError(
            f"{path.name} must contain a JSON object"
        )
    return value, sha256_bytes(raw)


def _safe_checkpoint_path(
    checkpoint: Path,
    relative: str,
) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise ArithmeticScreeningError(
            f"unsafe checkpoint path: {relative!r}"
        )
    path = checkpoint.joinpath(*pure.parts)
    try:
        path.resolve().relative_to(checkpoint.resolve())
    except ValueError as exc:
        raise ArithmeticScreeningError(
            f"checkpoint path escapes root: {relative!r}"
        ) from exc
    return path


def _verify_checkpoint_checksums(
    checkpoint: Path,
) -> dict[str, Any]:
    checksum_path = checkpoint / "SHA256SUMS"
    try:
        lines = checksum_path.read_text(
            encoding="utf-8"
        ).splitlines()
    except (OSError, UnicodeError) as exc:
        raise ArithmeticScreeningError(
            f"cannot read checkpoint checksums: {exc}"
        ) from exc

    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        parts = line.split("  ", 1)
        if (
            len(parts) != 2
            or len(parts[0]) != 64
            or any(
                character not in "0123456789abcdef"
                for character in parts[0]
            )
            or not parts[1]
        ):
            raise ArithmeticScreeningError(
                f"invalid SHA256SUMS row {line_number}"
            )
        expected, relative = parts
        if relative in seen:
            raise ArithmeticScreeningError(
                f"duplicate SHA256SUMS path: {relative}"
            )
        seen.add(relative)
        path = _safe_checkpoint_path(checkpoint, relative)
        if not path.is_file():
            raise ArithmeticScreeningError(
                f"missing checkpoint artifact: {relative}"
            )
        actual = sha256_file(path)
        if actual != expected:
            raise ArithmeticScreeningError(
                f"checkpoint hash mismatch: {relative}"
            )
        rows.append((expected, relative))

    observed_files = sorted(
        path.relative_to(checkpoint).as_posix()
        for path in checkpoint.rglob("*")
        if path.is_file() and path != checksum_path
    )
    recorded_files = sorted(relative for _, relative in rows)
    if observed_files != recorded_files:
        raise ArithmeticScreeningError(
            "checkpoint SHA256SUMS does not account for every file"
        )
    return {
        "status": "PASS",
        "sha256sums_sha256": sha256_file(checksum_path),
        "recorded_file_count": len(rows),
        "all_recorded_hashes_match": True,
        "every_checkpoint_file_accounted_for": True,
    }


def _checkpoint_index(
    checkpoint: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[int, Any]]:
    checksum_audit = _verify_checkpoint_checksums(checkpoint)
    census, census_sha256 = _load_json_object(
        checkpoint / "census.manifest.json"
    )
    ranking, ranking_sha256 = _load_json_object(
        checkpoint / "ranking.json"
    )
    checks = {
        "census_schema_supported": (
            census.get("schema_version")
            == STRUCTURAL_CENSUS_SCHEMA_VERSION
        ),
        "census_status_enumerated": (
            census.get("status") == "ENUMERATED"
        ),
        "all_68_classes_accounted_for": (
            census.get("summary", {}).get(
                "all_classes_accounted_for"
            )
            is True
            and census.get("summary", {}).get(
                "enumerated_class_count"
            )
            == 68
        ),
        "ranking_schema_supported": (
            ranking.get("schema_version")
            == STRUCTURAL_RANKING_SCHEMA_VERSION
        ),
        "ranking_status_enumerated": (
            ranking.get("status") == "ENUMERATED"
        ),
        "ranking_has_68_classes": (
            len(ranking.get("classes", [])) == 68
        ),
        "checkpoint_declares_no_solver_run": (
            census.get("scope_guardrails", {}).get(
                "solver_run"
            )
            is False
            and ranking.get("scope", {}).get("solver_run") is False
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ArithmeticScreeningError(
            "structural checkpoint audit failed: "
            + ", ".join(failed)
        )

    classes = census.get("classes")
    if not isinstance(classes, list):
        raise ArithmeticScreeningError(
            "structural census classes must be an array"
        )
    class_index = {
        int(row["class_index"]): row for row in classes
    }
    if set(class_index) != set(range(1, 69)):
        raise ArithmeticScreeningError(
            "structural census class index is incomplete"
        )
    return (
        {
            "checkpoint_checksums": checksum_audit,
            "census_manifest_sha256": census_sha256,
            "ranking_sha256": ranking_sha256,
            "checks": checks,
            "all_checks_passed": True,
        },
        ranking,
        class_index,
    )


def _artifact_check(
    checkpoint: Path,
    artifact: dict[str, Any],
) -> Path:
    relative = artifact.get("path")
    expected = artifact.get("sha256")
    if not isinstance(relative, str) or not isinstance(expected, str):
        raise ArithmeticScreeningError(
            "checkpoint artifact metadata is incomplete"
        )
    path = _safe_checkpoint_path(checkpoint, relative)
    if not path.is_file() or sha256_file(path) != expected:
        raise ArithmeticScreeningError(
            f"checkpoint artifact failed hash audit: {relative}"
        )
    return path


def _structural_comparison(
    structural: dict[str, Any],
    checkpoint_class: dict[str, Any],
) -> dict[str, Any]:
    compact_artifact = checkpoint_class["class_record"]
    checks = {
        "class_index_equal": (
            structural["input"]["class_index"]
            == checkpoint_class["class_index"]
        ),
        "canonical_labeled_link_sha256_equal": (
            structural["input"]["canonical_labeled_link_sha256"]
            == checkpoint_class["input"]["sha256_labeled_link"]
        ),
        "automorphism_group_order_equal": (
            structural["automorphism_group"]["order"]
            == checkpoint_class["ranking_metrics"][
                "automorphism_group_order"
            ]
        ),
        "candidate_orbit_count_equal": (
            structural["candidate_minimum_point_sets"][
                "orbit_count"
            ]
            == checkpoint_class["ranking_metrics"][
                "candidate_minimum_point_orbit_count"
            ]
        ),
        "candidate_partition_hash_present": bool(
            structural["candidate_minimum_point_sets"].get(
                "partition_sha256"
            )
        ),
        "class_record_hash_present": (
            isinstance(compact_artifact.get("sha256"), str)
            and len(compact_artifact["sha256"]) == 64
        ),
        "valid_cover": (
            structural["mathematical_validation"][
                "valid_15_block_C_12_6_3_cover"
            ]
            is True
        ),
    }
    return {
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def _pair_data(
    point_labels: tuple[int, ...],
    link_blocks: tuple[tuple[int, ...], ...],
) -> tuple[tuple[tuple[int, int], int], ...]:
    block_sets = tuple(frozenset(block) for block in link_blocks)
    return tuple(
        (
            pair,
            sum(frozenset(pair) <= block for block in block_sets),
        )
        for pair in itertools.combinations(point_labels, 2)
    )


def _screen_profile(
    profile: dict[str, Any],
    *,
    link_point_degrees: tuple[int, ...],
    pair_data: tuple[tuple[tuple[int, int], int], ...],
) -> dict[str, Any]:
    extension_degrees = tuple(profile["extension_degrees"])
    if (
        len(extension_degrees) != EXPECTED_POINT_COUNT
        or sum(extension_degrees) != EXPECTED_EXTENSION_DEGREE_SUM
    ):
        raise ArithmeticScreeningError(
            "generated extension-degree vector failed invariants"
        )

    offending_points = [
        {
            "point": point,
            "extension_degree": degree,
            "maximum": EXPECTED_EXTENSION_BLOCK_COUNT,
        }
        for point, degree in enumerate(extension_degrees)
        if degree < 0 or degree > EXPECTED_EXTENSION_BLOCK_COUNT
    ]
    if offending_points:
        return {
            "disposition": "DISCARDED",
            "rule_id": (
                "EXTENSION_POINT_DEGREE_EXCEEDS_BLOCK_COUNT"
            ),
            "evidence_status": "DIRECT_ARITHMETIC_CONTRADICTION",
            "mathematical_reason": (
                "A point can occur in at most all 14 selected extension "
                "blocks, so an extension degree greater than 14 is "
                "impossible."
            ),
            "certificate": {
                "extension_block_count": (
                    EXPECTED_EXTENSION_BLOCK_COUNT
                ),
                "offending_points": offending_points,
                "check": "extension_degree <= extension_block_count",
                "passed": True,
            },
        }

    full_degrees = tuple(
        link_point_degrees[point] + extension_degrees[point]
        for point in range(EXPECTED_POINT_COUNT)
    )
    intervals = []
    for pair, link_multiplicity in pair_data:
        first, second = pair
        lower = 7 - link_multiplicity
        upper = min(
            6 * full_degrees[first] - 70 - link_multiplicity,
            6 * full_degrees[second] - 70 - link_multiplicity,
        )
        intervals.append(
            {
                "pair": list(pair),
                "link_multiplicity": link_multiplicity,
                "lower": lower,
                "upper": upper,
                "slack": upper - lower,
            }
        )
    minimum_interval = min(
        intervals,
        key=lambda row: (row["slack"], row["pair"]),
    )
    if minimum_interval["slack"] < 0:
        return {
            "disposition": "DISCARDED",
            "rule_id": "CORRECTED_PAIR_INTERVAL_EMPTY",
            "evidence_status": "DIRECT_ARITHMETIC_CONTRADICTION",
            "mathematical_reason": (
                "The corrected necessary lower and upper bounds for one "
                "extension pair multiplicity form an empty integer interval."
            ),
            "certificate": {
                **minimum_interval,
                "corrected_upper_bound": (
                    "min(6*r_i-70-ell_ij, 6*r_j-70-ell_ij)"
                ),
                "check": "lower <= upper",
                "passed": True,
            },
        }

    return {
        "disposition": "RETAINED",
        "rule_id": "PASSED_SOLVER_FREE_ARITHMETIC_SCREENS",
        "evidence_status": "NO_CONTRADICTION_FOUND",
        "mathematical_reason": (
            "The exact degree vector satisfies the 14-block point-capacity "
            "bound and every corrected pair interval is nonempty. This is "
            "not a feasibility proof."
        ),
        "certificate": {
            "extension_degree_sum": sum(extension_degrees),
            "expected_extension_degree_sum": (
                EXPECTED_EXTENSION_DEGREE_SUM
            ),
            "maximum_extension_degree": max(extension_degrees),
            "extension_block_count": EXPECTED_EXTENSION_BLOCK_COUNT,
            "minimum_pair_interval": minimum_interval,
            "all_pair_intervals_nonempty": True,
        },
    }


def _write_gzip_jsonl(
    path: Path,
    rows: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        path.name + f".tmp-{os.getpid()}"
    )
    digest = hashlib.sha256()
    line_count = 0
    uncompressed_bytes = 0
    with temporary.open("wb") as raw:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw,
            compresslevel=9,
            mtime=0,
        ) as compressed:
            for row in rows:
                payload = compact_json_bytes(row) + b"\n"
                digest.update(payload)
                compressed.write(payload)
                uncompressed_bytes += len(payload)
                line_count += 1
    temporary.replace(path)
    return {
        "path": path.as_posix(),
        "media_type": "application/x-ndjson",
        "content_encoding": "gzip",
        "line_count": line_count,
        "uncompressed_bytes": uncompressed_bytes,
        "uncompressed_sha256": digest.hexdigest(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _relative_artifact(
    artifact: dict[str, Any],
    output_directory: Path,
) -> dict[str, Any]:
    result = dict(artifact)
    result["path"] = Path(result["path"]).relative_to(
        output_directory
    ).as_posix()
    return result


def _candidate_decisions(
    structural: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "orbit_index": orbit_index,
            "representative": orbit["representative"],
            "orbit_size": orbit["size"],
            "stabilizer_order": orbit["stabilizer_order"],
            "disposition": "RETAINED",
            "rule_id": (
                "NO_SOLVER_FREE_CANDIDATE_CONTRADICTION"
            ),
            "evidence_status": "NO_CONTRADICTION_FOUND",
            "mathematical_reason": (
                "The degree budget alone requires at least four minimum "
                "points but does not eliminate this four-set orbit. No LP "
                "or solver screen was run, so the orbit is retained."
            ),
        }
        for orbit_index, orbit in enumerate(
            structural["candidate_minimum_point_sets"]["orbits"]
        )
    ]


def _exact_case_rows(
    exact_sets: dict[str, Any],
    profile_case_index: dict[int, dict[str, Any]],
    *,
    excess: int,
) -> Iterator[dict[str, Any]]:
    for case in exact_sets["cases"]:
        outside_points = EXPECTED_POINT_COUNT - case["size"]
        raw_count = expected_raw_profile_count(
            excess,
            outside_points,
        )
        if raw_count == 0:
            decision = {
                "disposition": "DISCARDED",
                "rule_id": "NO_POSITIVE_EXCESS_COMPOSITION",
                "evidence_status": (
                    "DIRECT_ARITHMETIC_CONTRADICTION"
                ),
                "mathematical_reason": (
                    "Every point outside the exact minimum set must receive "
                    "positive integral excess, but no such composition of "
                    "the total excess exists."
                ),
                "certificate": {
                    "excess": excess,
                    "outside_point_count": outside_points,
                    "positive_composition_count": raw_count,
                    "check": (
                        "C(excess-1, outside_points-1), with the zero-part "
                        "case handled exactly"
                    ),
                    "passed": True,
                },
            }
        else:
            generated = profile_case_index[case["case_id"]]
            if generated["raw_positive_profile_count"] != raw_count:
                raise ArithmeticScreeningError(
                    "closed-form raw profile count mismatch"
                )
            decision = {
                "disposition": "RETAINED",
                "rule_id": "POSITIVE_EXCESS_COMPOSITIONS_EXIST",
                "evidence_status": "ENUMERATED",
                "mathematical_reason": (
                    "Positive integral excess allocations exist and are "
                    "materialized modulo the exact-set stabilizer."
                ),
                "certificate": {
                    "excess": excess,
                    "outside_point_count": outside_points,
                    "positive_composition_count": raw_count,
                    "profile_orbit_count": generated[
                        "profile_orbit_count"
                    ],
                    "profile_partition_sha256": generated[
                        "profile_partition_sha256"
                    ],
                    "all_raw_profiles_accounted_for": generated[
                        "accounting"
                    ]["raw_profiles_accounted_for"],
                },
            }
        yield {
            "case_id": case["case_id"],
            "representative": case["representative"],
            "minimum_set_size": case["size"],
            "source_candidate_orbit_index": case[
                "source_candidate_orbit_index"
            ],
            "orbit_size": case["orbit_size"],
            "stabilizer_order": case["stabilizer_order"],
            "orbit_members_sha256": sha256_bytes(
                compact_json_bytes(case["members"])
            ),
            **decision,
        }


def _profile_rows(
    profiles: dict[str, Any],
    exact_sets: dict[str, Any],
    *,
    minimum_extension_degrees: tuple[int, ...],
    link_point_degrees: tuple[int, ...],
    pair_data: tuple[tuple[tuple[int, int], int], ...],
    statistics: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    cases = {
        case["case_id"]: case for case in exact_sets["cases"]
    }
    profile_members = {
        (case["case_id"], profile["profile_id"]): profile[
            "members"
        ]
        for case in profiles["cases"]
        for profile in case["profiles"]
    }
    for profile in profiles["profiles"]:
        decision = _screen_profile(
            profile,
            link_point_degrees=link_point_degrees,
            pair_data=pair_data,
        )
        members = profile_members[
            (profile["case_id"], profile["profile_id"])
        ]
        for member in members:
            member_decision = _screen_profile(
                {
                    "extension_degrees": [
                        minimum_extension_degrees[point]
                        + member[point]
                        for point in range(EXPECTED_POINT_COUNT)
                    ]
                },
                link_point_degrees=link_point_degrees,
                pair_data=pair_data,
            )
            if (
                member_decision["disposition"]
                != decision["disposition"]
                or member_decision["rule_id"]
                != decision["rule_id"]
            ):
                raise ArithmeticScreeningError(
                    "profile screening rule is not orbit invariant"
                )
        statistics["dispositions"][decision["disposition"]] += 1
        statistics["rules"][decision["rule_id"]] += 1
        case = cases[profile["case_id"]]
        statistics["by_minimum_set_size"][
            (str(case["size"]), decision["disposition"])
        ] += 1
        yield {
            "case_id": profile["case_id"],
            "profile_id": profile["profile_id"],
            "id": profile["id"],
            "minimum_set_size": case["size"],
            "degree_excess": profile["representative"],
            "extension_degrees": profile["extension_degrees"],
            "extension_degree_sum": profile[
                "extension_degree_sum"
            ],
            "orbit_size": profile["orbit_size"],
            "profile_stabilizer_order": profile[
                "profile_stabilizer_order"
            ],
            "orbit_stabilizer_check": profile[
                "orbit_stabilizer_check"
            ],
            "orbit_decision_audit": {
                "members_checked": len(members),
                "decision_is_orbit_invariant": True,
            },
            **decision,
        }


def _build_class_screening(
    checkpoint: Path,
    checkpoint_class: dict[str, Any],
    output_directory: Path,
) -> dict[str, Any]:
    class_index = int(checkpoint_class["class_index"])
    input_path = _artifact_check(
        checkpoint,
        checkpoint_class["input"],
    )
    class_record_path = _artifact_check(
        checkpoint,
        checkpoint_class["class_record"],
    )
    compact_class, compact_class_sha256 = _load_json_object(
        class_record_path
    )
    if (
        compact_class.get("schema_version")
        != STRUCTURAL_CLASS_SCHEMA_VERSION
    ):
        raise ArithmeticScreeningError(
            f"class {class_index} structural schema is unsupported"
        )

    link = load_link(input_path)
    structural = build_manifest(link, 4)
    comparison = _structural_comparison(
        structural,
        {
            **checkpoint_class,
            "input": {
                **checkpoint_class["input"],
                "sha256_labeled_link": compact_class["input"][
                    "canonical_labeled_link_sha256"
                ],
            },
        },
    )
    comparison["checks"][
        "compact_class_record_sha256_equal"
    ] = (
        compact_class_sha256
        == checkpoint_class["class_record"]["sha256"]
    )
    comparison["checks"][
        "candidate_partition_sha256_equal"
    ] = (
        structural["candidate_minimum_point_sets"][
            "partition_sha256"
        ]
        == compact_class["candidate_minimum_point_sets"][
            "partition_sha256"
        ]
    )
    comparison["checks"]["automorphism_group_sha256_equal"] = (
        structural["automorphism_group"]["group_sha256"]
        == compact_class["automorphism_group"]["group_sha256"]
    )
    comparison["all_checks_passed"] = all(
        comparison["checks"].values()
    )
    if not comparison["all_checks_passed"]:
        failed = [
            name
            for name, passed in comparison["checks"].items()
            if not passed
        ]
        raise ArithmeticScreeningError(
            f"class {class_index} structural comparison failed: "
            + ", ".join(failed)
        )

    point_labels = tuple(link.point_labels)
    link_blocks = tuple(link.blocks)
    group = tuple(
        tuple(permutation)
        for permutation in structural["automorphism_group"][
            "permutations"
        ]
    )
    budget = degree_budget(point_labels, link_blocks)
    candidate_orbit_count = structural[
        "candidate_minimum_point_sets"
    ]["orbit_count"]
    candidate_decisions = _candidate_decisions(structural)
    retained_candidate_indices = tuple(
        range(candidate_orbit_count)
    )
    exact_sets = compute_exact_minimum_set_orbits(
        point_labels,
        group,
        structural["candidate_minimum_point_sets"],
        retained_candidate_indices,
    )
    excess = budget["derivation"]["excess"]
    retained_case_ids = tuple(
        case["case_id"]
        for case in exact_sets["cases"]
        if expected_raw_profile_count(
            excess,
            EXPECTED_POINT_COUNT - case["size"],
        )
        > 0
    )
    profiles = compute_extension_degree_profiles(
        point_labels,
        group,
        exact_sets,
        retained_case_ids,
        budget["minimum_extension_degrees"],
        excess,
    )
    expected_profile_orbits = compact_class[
        "unscreened_degree_profile_orbit_census"
    ]["profile_orbit_count"]
    if profiles["profile_orbit_count"] != expected_profile_orbits:
        raise ArithmeticScreeningError(
            f"class {class_index} profile count does not match Burnside census"
        )

    class_directory = (
        output_directory / "classes" / f"class{class_index:02d}"
    )
    profile_case_index = {
        case["case_id"]: case for case in profiles["cases"]
    }
    exact_artifact = _write_gzip_jsonl(
        class_directory / "exact-minimum-sets.jsonl.gz",
        _exact_case_rows(
            exact_sets,
            profile_case_index,
            excess=excess,
        ),
    )
    statistics: dict[str, Any] = {
        "dispositions": Counter(),
        "rules": Counter(),
        "by_minimum_set_size": Counter(),
    }
    pair_data = _pair_data(point_labels, link_blocks)
    profile_artifact = _write_gzip_jsonl(
        class_directory / "degree-profiles.jsonl.gz",
        _profile_rows(
            profiles,
            exact_sets,
            minimum_extension_degrees=tuple(
                budget["minimum_extension_degrees"]
            ),
            link_point_degrees=tuple(
                budget["link_point_degrees"]
            ),
            pair_data=pair_data,
            statistics=statistics,
        ),
    )
    dispositions = dict(
        sorted(statistics["dispositions"].items())
    )
    rules = dict(sorted(statistics["rules"].items()))
    by_size: dict[str, dict[str, int]] = {}
    for (size, disposition), count in sorted(
        statistics["by_minimum_set_size"].items()
    ):
        by_size.setdefault(size, {})[disposition] = count
    if profile_artifact["line_count"] != expected_profile_orbits:
        raise ArithmeticScreeningError(
            "profile artifact line accounting failed"
        )
    retained_profile_count = dispositions.get("RETAINED", 0)
    discarded_profile_count = dispositions.get("DISCARDED", 0)
    if (
        retained_profile_count + discarded_profile_count
        != expected_profile_orbits
    ):
        raise ArithmeticScreeningError(
            "profile screening disposition accounting failed"
        )

    class_manifest = {
        "schema_version": CLASS_SCHEMA_VERSION,
        "producer": {
            "name": "horizonlink",
            "version": SOLVER_FREE_PROFILE_SCREENING_PRODUCER_VERSION,
        },
        "status": "ENUMERATED",
        "class_index": class_index,
        "input": {
            "canonical_labeled_link_sha256": (
                link.canonical_labeled_link_sha256
            ),
            "canonical_document_sha256": (
                link.canonical_document_sha256
            ),
            "numbering_source": link.numbering_source,
            "structural_input_artifact": (
                checkpoint_class["input"]
            ),
            "structural_class_artifact": (
                checkpoint_class["class_record"]
            ),
        },
        "structural_comparison": comparison,
        "degree_budget": budget,
        "candidate_orbit_screening": {
            "status": "ENUMERATED",
            "orbit_count": candidate_orbit_count,
            "retained_count": len(candidate_decisions),
            "discarded_count": 0,
            "decisions": candidate_decisions,
            "accounting": {
                "one_decision_per_orbit": (
                    len(candidate_decisions)
                    == candidate_orbit_count
                ),
                "no_candidate_orbit_disappeared": True,
            },
        },
        "exact_minimum_set_screening": {
            "status": "ENUMERATED",
            "orbit_count": exact_sets["orbit_count"],
            "retained_case_count": len(retained_case_ids),
            "discarded_case_count": (
                exact_sets["orbit_count"] - len(retained_case_ids)
            ),
            "orbits_by_size": exact_sets["orbits_by_size"],
            "partition_sha256": exact_sets["partition_sha256"],
            "artifact": _relative_artifact(
                exact_artifact,
                output_directory,
            ),
            "accounting": exact_sets["accounting"],
        },
        "degree_profile_screening": {
            "status": "ENUMERATED",
            "unscreened_profile_orbit_count": (
                expected_profile_orbits
            ),
            "retained_profile_orbit_count": (
                retained_profile_count
            ),
            "discarded_profile_orbit_count": (
                discarded_profile_count
            ),
            "dispositions": dispositions,
            "rules": rules,
            "dispositions_by_minimum_set_size": by_size,
            "profile_index_sha256": profiles[
                "profile_index_sha256"
            ],
            "artifact": _relative_artifact(
                profile_artifact,
                output_directory,
            ),
            "accounting": {
                **profiles["accounting"],
                "profile_count_matches_burnside_census": True,
                "one_screening_decision_per_profile": (
                    profile_artifact["line_count"]
                    == expected_profile_orbits
                ),
                "every_orbit_member_decision_checked": True,
                "all_screening_decisions_orbit_invariant": True,
                "no_profile_disappeared": True,
            },
        },
        "ranking_metrics": {
            **checkpoint_class["ranking_metrics"],
            "retained_profile_count_after_solver_free_screening": (
                retained_profile_count
            ),
            "discarded_profile_count_by_direct_arithmetic": (
                discarded_profile_count
            ),
        },
        "status_ledger": {
            "link": "ENUMERATED",
            "structural_regression": "ENUMERATED",
            "candidate_orbits": "ENUMERATED",
            "exact_minimum_sets": "ENUMERATED",
            "degree_profiles": "ENUMERATED",
            "arithmetic_screening": "ENUMERATED",
            "formulas": "NOT_STARTED",
            "root_lp": "NOT_STARTED",
            "solver": "NOT_STARTED",
            "proof": "NOT_STARTED",
            "verification": "NOT_STARTED",
        },
        "scope_guardrails": {
            "all_candidate_orbits_retained": True,
            "all_exact_minimum_set_orbits_recorded": True,
            "all_profile_orbit_representatives_recorded": True,
            "only_direct_arithmetic_contradictions_discarded": True,
            "retained_means_feasible": False,
            "formulas_generated": False,
            "root_lp_run": False,
            "solver_run": False,
            "proof_generated": False,
            "verifier_run": False,
            "class_elimination_claimed": False,
        },
    }
    class_manifest_path = (
        output_directory
        / "classes"
        / f"class{class_index:02d}.screening.manifest.json"
    )
    write_json(class_manifest_path, class_manifest)
    return {
        "class_index": class_index,
        "class_manifest": {
            "path": class_manifest_path.relative_to(
                output_directory
            ).as_posix(),
            "bytes": class_manifest_path.stat().st_size,
            "sha256": sha256_file(class_manifest_path),
        },
        "ranking_metrics": class_manifest["ranking_metrics"],
        "status": class_manifest["status"],
    }


def _build_ranking(
    class_results: list[dict[str, Any]],
    structural_ranking: dict[str, Any],
) -> dict[str, Any]:
    structural_rows = {
        row["class_index"]: row
        for row in structural_ranking["classes"]
    }
    ordered = sorted(
        class_results,
        key=lambda row: (
            row["ranking_metrics"][
                "retained_profile_count_after_solver_free_screening"
            ],
            row["ranking_metrics"][
                "candidate_minimum_point_orbit_count"
            ],
            row["ranking_metrics"]["residual_four_set_count"],
            -row["ranking_metrics"]["automorphism_group_order"],
            row["class_index"],
        ),
    )
    rows = []
    for position, result in enumerate(ordered, start=1):
        class_index = result["class_index"]
        rows.append(
            {
                "pilot_position": position,
                "class_index": class_index,
                "prior_structural_ordinal_position": structural_rows[
                    class_index
                ]["ordinal_position"],
                **result["ranking_metrics"],
                "class_manifest": result["class_manifest"],
                "root_lp_status": "NOT_STARTED",
                "solver_status": "NOT_STARTED",
                "proof_status": "NOT_STARTED",
            }
        )
    return {
        "schema_version": RANKING_SCHEMA_VERSION,
        "producer": {
            "name": "horizonlink",
            "version": SOLVER_FREE_PROFILE_SCREENING_PRODUCER_VERSION,
        },
        "status": "ENUMERATED",
        "method": {
            "id": (
                "solver-free-retained-profile-lexicographic-pilot-v1"
            ),
            "ordered_key": [
                {
                    "field": (
                        "retained_profile_count_after_solver_free_screening"
                    ),
                    "direction": "ascending",
                },
                {
                    "field": (
                        "candidate_minimum_point_orbit_count"
                    ),
                    "direction": "ascending",
                },
                {
                    "field": "residual_four_set_count",
                    "direction": "ascending",
                },
                {
                    "field": "automorphism_group_order",
                    "direction": "descending",
                },
                {
                    "field": "class_index",
                    "direction": "ascending",
                    "role": "deterministic tie-break only",
                },
            ],
            "limitations": [
                (
                    "Retained means only that the implemented arithmetic "
                    "screens found no contradiction; it does not mean SAT."
                ),
                (
                    "Root LP, solver runtime, and proof-size metrics remain "
                    "NOT_STARTED."
                ),
                (
                    "This ranking compares only the requested pilot classes."
                ),
            ],
        },
        "classes": rows,
        "scope": {
            "profile_representatives_materialized": True,
            "solver_free_arithmetic_screening_completed": True,
            "formulas_generated": False,
            "root_lp_run": False,
            "solver_run": False,
            "proof_generated": False,
            "verifier_run": False,
        },
    }


def _write_ranking_csv(
    path: Path,
    ranking: dict[str, Any],
) -> None:
    fieldnames = [
        "pilot_position",
        "class_index",
        "prior_structural_ordinal_position",
        "automorphism_group_order",
        "residual_four_set_count",
        "candidate_minimum_point_orbit_count",
        "unscreened_degree_profile_orbit_count",
        "discarded_profile_count_by_direct_arithmetic",
        "retained_profile_count_after_solver_free_screening",
        "root_lp_status",
        "solver_status",
        "proof_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        for row in ranking["classes"]:
            writer.writerow(
                {field: row[field] for field in fieldnames}
            )


def _write_checksums(output_directory: Path) -> None:
    partials = sorted(
        path.relative_to(output_directory).as_posix()
        for path in output_directory.rglob("*")
        if path.is_file()
        and (
            path.name.endswith(".tmp")
            or ".tmp-" in path.name
        )
    )
    if partials:
        raise ArithmeticScreeningError(
            "partial output artifacts remain: "
            + ", ".join(partials)
        )
    targets = sorted(
        (
            path
            for path in output_directory.rglob("*")
            if path.is_file() and path.name != "SHA256SUMS"
        ),
        key=lambda path: path.relative_to(
            output_directory
        ).as_posix(),
    )
    (output_directory / "SHA256SUMS").write_text(
        "".join(
            f"{sha256_file(path)}  "
            f"{path.relative_to(output_directory).as_posix()}\n"
            for path in targets
        ),
        encoding="utf-8",
    )


def generate_solver_free_profile_screening(
    structural_census_directory: Path,
    class_indices: Iterable[int],
    output_directory: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Materialize and arithmetically screen selected link classes."""

    if output_directory.exists() and any(output_directory.iterdir()):
        raise ArithmeticScreeningError(
            "profile-screening output directory must be empty"
        )
    requested = tuple(sorted(set(int(value) for value in class_indices)))
    if not requested:
        raise ArithmeticScreeningError(
            "at least one class index is required"
        )
    if requested[0] < 1 or requested[-1] > 68:
        raise ArithmeticScreeningError(
            "class indices must be between 1 and 68"
        )

    (
        checkpoint_audit,
        structural_ranking,
        checkpoint_classes,
    ) = _checkpoint_index(structural_census_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    class_results = [
        _build_class_screening(
            structural_census_directory,
            checkpoint_classes[class_index],
            output_directory,
        )
        for class_index in requested
    ]
    if (
        [row["class_index"] for row in class_results]
        != list(requested)
        or not all(row["status"] == "ENUMERATED" for row in class_results)
    ):
        raise ArithmeticScreeningError(
            "a requested class disappeared from screening"
        )

    ranking = _build_ranking(
        class_results,
        structural_ranking,
    )
    ranking_path = output_directory / "ranking.json"
    ranking_csv_path = output_directory / "ranking.csv"
    write_json(ranking_path, ranking)
    _write_ranking_csv(ranking_csv_path, ranking)
    structural_pilot = structural_ranking[
        "provisional_three_class_pilot"
    ]
    provisional_indices = sorted(
        (
            structural_pilot["easy_high_symmetry"]["class_index"],
            structural_pilot["median"]["class_index"],
            structural_pilot["difficult_low_symmetry"]["class_index"],
        )
    )
    global_manifest = {
        "schema_version": GLOBAL_SCHEMA_VERSION,
        "producer": {
            "name": "horizonlink",
            "version": SOLVER_FREE_PROFILE_SCREENING_PRODUCER_VERSION,
        },
        "status": "ENUMERATED",
        "input": {
            "structural_census": checkpoint_audit,
            "class_indices": list(requested),
            "matches_provisional_three_class_pilot": (
                list(requested) == provisional_indices
            ),
            "provisional_three_class_pilot_indices": (
                provisional_indices
            ),
        },
        "algorithm": {
            "id": (
                "all-profile-orbits-direct-arithmetic-screening-v1"
            ),
            "candidate_rule": (
                "Retain every candidate four-set orbit because no "
                "solver-free candidate contradiction is asserted."
            ),
            "exact_minimum_set_rule": (
                "Discard exactly when the closed-form positive-composition "
                "count is zero."
            ),
            "profile_rules_in_order": [
                "EXTENSION_POINT_DEGREE_EXCEEDS_BLOCK_COUNT",
                "CORRECTED_PAIR_INTERVAL_EMPTY",
                "PASSED_SOLVER_FREE_ARITHMETIC_SCREENS",
            ],
        },
        "summary": {
            "requested_class_count": len(requested),
            "enumerated_class_count": len(class_results),
            "class_indices": list(requested),
            "all_requested_classes_accounted_for": True,
            "unscreened_profile_orbit_count": sum(
                row["ranking_metrics"][
                    "unscreened_degree_profile_orbit_count"
                ]
                for row in class_results
            ),
            "discarded_profile_count_by_direct_arithmetic": sum(
                row["ranking_metrics"][
                    "discarded_profile_count_by_direct_arithmetic"
                ]
                for row in class_results
            ),
            "retained_profile_count_after_solver_free_screening": sum(
                row["ranking_metrics"][
                    "retained_profile_count_after_solver_free_screening"
                ]
                for row in class_results
            ),
        },
        "classes": class_results,
        "ranking": {
            "json": {
                "path": "ranking.json",
                "bytes": ranking_path.stat().st_size,
                "sha256": sha256_file(ranking_path),
            },
            "csv": {
                "path": "ranking.csv",
                "bytes": ranking_csv_path.stat().st_size,
                "sha256": sha256_file(ranking_csv_path),
            },
        },
        "status_ledger": {
            "structural_checkpoint_audit": "ENUMERATED",
            "candidate_orbits": "ENUMERATED",
            "exact_minimum_sets": "ENUMERATED",
            "degree_profiles": "ENUMERATED",
            "arithmetic_screening": "ENUMERATED",
            "formulas": "NOT_STARTED",
            "root_lp": "NOT_STARTED",
            "solver": "NOT_STARTED",
            "proof": "NOT_STARTED",
            "verification": "NOT_STARTED",
        },
        "scope_guardrails": {
            "all_requested_classes_accounted_for": True,
            "all_generated_profile_orbits_recorded": True,
            "retained_profiles_claimed_sat": False,
            "formulas_generated": False,
            "root_lp_run": False,
            "solver_run": False,
            "proof_generated": False,
            "verifier_run": False,
            "another_class_eliminated": False,
            "C_13_7_4_equals_30_claimed": False,
        },
    }
    manifest_path = output_directory / "screening.manifest.json"
    write_json(manifest_path, global_manifest)
    _write_checksums(output_directory)
    return global_manifest, ranking
