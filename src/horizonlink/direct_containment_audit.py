"""Independent audit for direct-containment scan checkpoints.

This module deliberately does not import the production scanner or proof
renderer.  It reparses every source formula, recomputes every lower/upper
support comparison, and reconstructs any normalized formula and four-line
proof independently.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from horizonlink.canonical import (
    pretty_json_bytes,
    sha256_bytes,
    sha256_file,
)


AUDIT_SCHEMA_VERSION = (
    "horizonmath.direct-containment-independent-audit.v1"
)
SCAN_SCHEMA_VERSION = "horizonmath.direct-containment-scan.v1"
INPUT_CHECKPOINT_SCHEMA_VERSION = (
    "horizonmath.candidate-formula-checkpoint.v1"
)
INPUT_CORPUS_SCHEMA_VERSION = (
    "horizonmath.candidate-screening-pb-corpus.v1"
)
NATIVE_HEADER_RE = re.compile(
    r"^\* #variable= (?P<variables>[0-9]+) "
    r"#constraint= (?P<constraints>[0-9]+)$"
)
NATIVE_ROW_RE = re.compile(
    r"^(?P<terms>(?:\+1 x[1-9][0-9]* ?)+)"
    r"(?P<relation>>=|<=) (?P<rhs>-?[0-9]+) ;$"
)
NATIVE_TERM_RE = re.compile(r"\+1 x([1-9][0-9]*)")
NORMALIZED_ROW_RE = re.compile(
    r"^(?P<terms>(?:[+-]1 x[1-9][0-9]* ?)+)"
    r">= (?P<rhs>-?[0-9]+) ;$"
)
NORMALIZED_TERM_RE = re.compile(r"([+-]1) x([1-9][0-9]*)")


class DirectContainmentAuditError(ValueError):
    """Raised when an independent scan audit fails closed."""


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
        raise DirectContainmentAuditError(
            f"cannot load {path.name}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise DirectContainmentAuditError(
            f"{path.name} must contain a JSON object"
        )
    return value, sha256_bytes(raw)


def _safe_path(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise DirectContainmentAuditError(
            f"unsafe artifact path: {relative!r}"
        )
    path = root.joinpath(*pure.parts)
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise DirectContainmentAuditError(
            f"artifact path escapes root: {relative!r}"
        ) from exc
    return path


def _verify_candidate_checksums(checkpoint: Path) -> dict[str, Any]:
    checksum_path = checkpoint / "SHA256SUMS"
    try:
        lines = checksum_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise DirectContainmentAuditError(
            f"cannot read candidate checksums: {exc}"
        ) from exc

    recorded: list[str] = []
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
            raise DirectContainmentAuditError(
                f"invalid candidate SHA256SUMS row {line_number}"
            )
        expected, relative = parts
        if relative in seen:
            raise DirectContainmentAuditError(
                f"duplicate candidate SHA256SUMS path: {relative}"
            )
        seen.add(relative)
        path = _safe_path(checkpoint, relative)
        if not path.is_file() or sha256_file(path) != expected:
            raise DirectContainmentAuditError(
                f"candidate checkpoint checksum mismatch: {relative}"
            )
        recorded.append(relative)

    observed = sorted(
        path.relative_to(checkpoint).as_posix()
        for path in checkpoint.rglob("*")
        if path.is_file() and path != checksum_path
    )
    if sorted(recorded) != observed:
        raise DirectContainmentAuditError(
            "candidate checkpoint checksum accounting is incomplete"
        )
    return {
        "sha256sums_sha256": sha256_file(checksum_path),
        "recorded_file_count": len(recorded),
        "all_recorded_hashes_match": True,
        "every_checkpoint_file_accounted_for": True,
    }


def _parse_native_formula(
    path: Path,
    family_counts: dict[str, int],
) -> dict[str, Any]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise DirectContainmentAuditError(
            f"cannot read {path.name}: {exc}"
        ) from exc
    if not lines:
        raise DirectContainmentAuditError(f"{path.name} is empty")
    header = NATIVE_HEADER_RE.fullmatch(lines[0])
    if header is None:
        raise DirectContainmentAuditError(
            f"{path.name}: malformed native OPB header"
        )

    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(lines[1:], start=2):
        line = raw_line.strip()
        if not line or line.startswith("*"):
            continue
        match = NATIVE_ROW_RE.fullmatch(line)
        if match is None:
            raise DirectContainmentAuditError(
                f"{path.name}:{line_number}: unsupported native row"
            )
        variables = tuple(
            int(value)
            for value in NATIVE_TERM_RE.findall(
                match.group("terms")
            )
        )
        if (
            not variables
            or tuple(sorted(set(variables))) != variables
        ):
            raise DirectContainmentAuditError(
                f"{path.name}:{line_number}: invalid variable order"
            )
        rows.append(
            {
                "variables": variables,
                "relation": match.group("relation"),
                "rhs": int(match.group("rhs")),
                "family": None,
            }
        )

    family_order = (
        "residual_four_coverage",
        "candidate_point_degree",
        "pair_degree_lower",
        "triple_degree_lower",
        "extension_block_count",
    )
    if set(family_counts) != set(family_order):
        raise DirectContainmentAuditError(
            f"{path.name}: unsupported family inventory"
        )
    if sum(int(family_counts[name]) for name in family_order) != len(
        rows
    ):
        raise DirectContainmentAuditError(
            f"{path.name}: family inventory does not cover all rows"
        )
    cursor = 0
    for family in family_order:
        count = int(family_counts[family])
        for row in rows[cursor : cursor + count]:
            row["family"] = family
        cursor += count

    return {
        "variable_count": int(header.group("variables")),
        "constraint_count": int(header.group("constraints")),
        "rows": tuple(rows),
    }


def _support_sha256(variables: tuple[int, ...]) -> str:
    return sha256_bytes(
        json.dumps(
            list(variables),
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _witness(
    lower_id: int,
    lower: dict[str, Any],
    upper_id: int,
    upper: dict[str, Any],
) -> dict[str, Any]:
    lower_set = frozenset(lower["variables"])
    upper_set = frozenset(upper["variables"])
    difference = tuple(sorted(upper_set - lower_set))
    gap = lower["rhs"] - upper["rhs"]
    return {
        "lower_row": {
            "id_1based": lower_id,
            "relation": lower["relation"],
            "rhs": lower["rhs"],
            "support_size": len(lower["variables"]),
            "support_sha256": _support_sha256(lower["variables"]),
            "family": lower["family"],
            "subject": None,
        },
        "upper_row": {
            "id_1based": upper_id,
            "relation": upper["relation"],
            "rhs": upper["rhs"],
            "support_size": len(upper["variables"]),
            "support_sha256": _support_sha256(upper["variables"]),
            "family": upper["family"],
            "subject": None,
        },
        "support_relation": (
            "LOWER_SUPPORT_SUBSET_OF_UPPER_SUPPORT"
        ),
        "support_difference_variable_ids_1based": list(difference),
        "contradiction_gap": gap,
        "derived_inequality": {
            "negative_unit_variables_1based": list(difference),
            "rhs": gap,
            "interpretation": (
                "-sum(difference variables) >= contradiction_gap"
            ),
        },
        "exact_checks": {
            "lower_relation_is_greater_equal": True,
            "upper_relation_is_less_equal": True,
            "lower_support_is_subset": lower_set <= upper_set,
            "lower_rhs_strictly_exceeds_upper_rhs": gap > 0,
            "derived_coefficients_are_nonpositive": True,
            "derived_rhs_is_strictly_positive": gap > 0,
        },
    }


def _independent_scan(
    rows: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    lowers = [
        (row_id, row)
        for row_id, row in enumerate(rows, start=1)
        if row["relation"] == ">="
    ]
    uppers = [
        (row_id, row)
        for row_id, row in enumerate(rows, start=1)
        if row["relation"] == "<="
    ]
    containments = 0
    gaps: Counter[int] = Counter()
    witnesses = []
    for lower_id, lower in lowers:
        lower_set = frozenset(lower["variables"])
        for upper_id, upper in uppers:
            upper_set = frozenset(upper["variables"])
            if not lower_set <= upper_set:
                continue
            containments += 1
            gap = lower["rhs"] - upper["rhs"]
            gaps[gap] += 1
            if gap > 0:
                witnesses.append(
                    _witness(
                        lower_id,
                        lower,
                        upper_id,
                        upper,
                    )
                )
    witnesses.sort(
        key=lambda row: (
            row["lower_row"]["id_1based"],
            row["upper_row"]["id_1based"],
        )
    )
    return {
        "lower_rows": len(lowers),
        "upper_rows": len(uppers),
        "row_pairs_tested": len(lowers) * len(uppers),
        "support_containments": containments,
        "containment_gap_histogram": {
            str(gap): count for gap, count in sorted(gaps.items())
        },
        "maximum_containment_gap": (
            max(gaps) if gaps else None
        ),
        "contradictions_found": len(witnesses),
        "witnesses": witnesses,
    }


def _expected_normalized_formula(
    rows: tuple[dict[str, Any], ...],
    *,
    variable_count: int,
    source_name: str,
) -> bytes:
    lines = [
        (
            f"* #variable= {variable_count} "
            f"#constraint= {len(rows)}"
        ),
        f"* source formula {source_name}",
        (
            "* verifier-normalized for direct containment; "
            "constraint ids preserved"
        ),
    ]
    for row in rows:
        coefficient = 1 if row["relation"] == ">=" else -1
        rhs = row["rhs"] if row["relation"] == ">=" else -row["rhs"]
        terms = " ".join(
            f"{coefficient:+d} x{variable}"
            for variable in row["variables"]
        )
        lines.append(f"{terms} >= {rhs} ;")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _audit_normalized_formula(
    path: Path,
    source_rows: tuple[dict[str, Any], ...],
    variable_count: int,
) -> bool:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise DirectContainmentAuditError(
            f"cannot read normalized formula: {exc}"
        ) from exc
    header = NATIVE_HEADER_RE.fullmatch(lines[0]) if lines else None
    if (
        header is None
        or int(header.group("variables")) != variable_count
        or int(header.group("constraints")) != len(source_rows)
    ):
        return False
    observed = []
    for raw_line in lines[1:]:
        line = raw_line.strip()
        if not line or line.startswith("*"):
            continue
        match = NORMALIZED_ROW_RE.fullmatch(line)
        if match is None:
            return False
        terms = NORMALIZED_TERM_RE.findall(match.group("terms"))
        coefficients = tuple(int(item[0]) for item in terms)
        variables = tuple(int(item[1]) for item in terms)
        observed.append(
            (coefficients, variables, int(match.group("rhs")))
        )
    expected = []
    for row in source_rows:
        coefficient = 1 if row["relation"] == ">=" else -1
        rhs = row["rhs"] if row["relation"] == ">=" else -row["rhs"]
        expected.append(
            (
                tuple(coefficient for _ in row["variables"]),
                row["variables"],
                rhs,
            )
        )
    return observed == expected


def _expected_proof(
    constraint_count: int,
    witness: dict[str, Any],
) -> bytes:
    upper_id = witness["upper_row"]["id_1based"]
    lower_id = witness["lower_row"]["id_1based"]
    return (
        "pseudo-Boolean proof version 1.0\n"
        f"f {constraint_count}\n"
        f"p {upper_id} {lower_id} +\n"
        f"c {constraint_count + 1}\n"
    ).encode("utf-8")


def audit_direct_containment_scan(
    candidate_checkpoint_directory: Path,
    scan_directory: Path,
) -> dict[str, Any]:
    """Independently recompute a serialized direct-containment scan."""

    checksum_audit = _verify_candidate_checksums(
        candidate_checkpoint_directory
    )
    candidate_phase_path = (
        candidate_checkpoint_directory / "phase.manifest.json"
    )
    candidate_phase, candidate_phase_hash = _load_json_object(
        candidate_phase_path
    )
    if (
        candidate_phase.get("schema_version")
        != INPUT_CHECKPOINT_SCHEMA_VERSION
        or candidate_phase.get("status") != "FORMULAS_GENERATED"
    ):
        raise DirectContainmentAuditError(
            "candidate checkpoint schema or status is invalid"
        )
    corpus_path = (
        candidate_checkpoint_directory
        / candidate_phase["artifacts"]["candidate_corpus_manifest"][
            "path"
        ]
    )
    corpus, corpus_hash = _load_json_object(corpus_path)
    if (
        corpus.get("schema_version") != INPUT_CORPUS_SCHEMA_VERSION
        or corpus.get("status") != "FORMULAS_GENERATED"
    ):
        raise DirectContainmentAuditError(
            "candidate corpus schema or status is invalid"
        )
    scan_path = scan_directory / "scan.manifest.json"
    scan, scan_hash = _load_json_object(scan_path)
    if (
        scan.get("schema_version") != SCAN_SCHEMA_VERSION
        or scan.get("status") not in {"ENUMERATED", "PROOF_GENERATED"}
    ):
        raise DirectContainmentAuditError(
            "direct-containment scan schema or status is invalid"
        )

    candidate_records = {
        int(row["orbit_index"]): row
        for row in corpus.get("instances", [])
    }
    scan_records = {
        int(row["orbit_index"]): row
        for row in scan.get("instances", [])
    }
    expected_indices = candidate_phase["summary"]["orbit_indices"]
    comparisons = []
    expected_files = {
        "scan.manifest.json",
        "scan.manifest.json.sha256",
    }
    for orbit_index in expected_indices:
        source = candidate_records.get(orbit_index)
        record = scan_records.get(orbit_index)
        if source is None or record is None:
            comparisons.append(
                {
                    "orbit_index": orbit_index,
                    "passed": False,
                    "error": "missing source or scan record",
                }
            )
            continue

        source_path = (
            candidate_checkpoint_directory
            / "corpus"
            / source["formula"]["path"]
        )
        parsed = _parse_native_formula(
            source_path,
            source["formula"]["serialized_family_counts"],
        )
        independent = _independent_scan(parsed["rows"])
        contradiction_found = (
            independent["contradictions_found"] > 0
        )
        selected = (
            independent["witnesses"][0]
            if contradiction_found
            else None
        )
        metadata_artifact = record["metadata"]
        metadata_path = _safe_path(
            scan_directory,
            metadata_artifact["path"],
        )
        metadata, metadata_hash = _load_json_object(metadata_path)
        expected_files.add(metadata_artifact["path"])
        record_without_metadata = {
            key: value
            for key, value in record.items()
            if key != "metadata"
        }

        normalized_checks = {
            "normalized_formula_absent_for_survivor": True,
            "proof_absent_for_survivor": True,
            "normalized_formula_bytes_equal": True,
            "normalized_formula_hash_equal": True,
            "normalized_rows_equal": True,
            "proof_bytes_equal": True,
            "proof_hash_equal": True,
            "proof_tokens_equal": True,
        }
        if contradiction_found:
            normalized_artifact = record["artifacts"][
                "verifier_normalized_formula"
            ]
            proof_artifact = record["artifacts"]["proof"]
            if normalized_artifact is None or proof_artifact is None:
                raise DirectContainmentAuditError(
                    f"orbit {orbit_index} is missing proof artifacts"
                )
            normalized_path = _safe_path(
                scan_directory,
                normalized_artifact["path"],
            )
            proof_path = _safe_path(
                scan_directory,
                proof_artifact["path"],
            )
            expected_files.update(
                {
                    normalized_artifact["path"],
                    proof_artifact["path"],
                }
            )
            expected_normalized = _expected_normalized_formula(
                parsed["rows"],
                variable_count=parsed["variable_count"],
                source_name=source_path.name,
            )
            expected_proof = _expected_proof(
                parsed["constraint_count"],
                selected,
            )
            normalized_checks = {
                "normalized_formula_absent_for_survivor": True,
                "proof_absent_for_survivor": True,
                "normalized_formula_bytes_equal": (
                    normalized_path.read_bytes()
                    == expected_normalized
                    and normalized_path.stat().st_size
                    == normalized_artifact["bytes"]
                ),
                "normalized_formula_hash_equal": (
                    sha256_file(normalized_path)
                    == normalized_artifact["sha256"]
                ),
                "normalized_rows_equal": _audit_normalized_formula(
                    normalized_path,
                    parsed["rows"],
                    parsed["variable_count"],
                ),
                "proof_bytes_equal": (
                    proof_path.read_bytes() == expected_proof
                    and proof_path.stat().st_size
                    == proof_artifact["bytes"]
                ),
                "proof_hash_equal": (
                    sha256_file(proof_path)
                    == proof_artifact["sha256"]
                ),
                "proof_tokens_equal": (
                    proof_path.read_bytes() == expected_proof
                ),
            }
        else:
            normalized_checks[
                "normalized_formula_absent_for_survivor"
            ] = (
                record["artifacts"]["verifier_normalized_formula"]
                is None
            )
            normalized_checks["proof_absent_for_survivor"] = (
                record["artifacts"]["proof"] is None
            )

        expected_direct_status = (
            "PROOF_GENERATED" if contradiction_found else "ENUMERATED"
        )
        expected_proof_status = (
            "PROOF_GENERATED"
            if contradiction_found
            else "NOT_STARTED"
        )
        checks = {
            "source_formula_hash_equal": (
                sha256_file(source_path)
                == source["formula"]["sha256"]
                == record["source_formula"]["sha256"]
            ),
            "source_formula_bytes_equal": (
                source_path.stat().st_size
                == source["formula"]["bytes"]
                == record["source_formula"]["bytes"]
            ),
            "source_header_equal": (
                parsed["variable_count"]
                == source["formula"]["variables"]
                == record["source_formula"]["variables"]
                and parsed["constraint_count"]
                == len(parsed["rows"])
                == source["formula"]["opb_constraints"]
                == record["source_formula"]["constraints"]
            ),
            "candidate_points_equal": (
                record["candidate_minimum_points"]
                == source["candidate_minimum_points"]
            ),
            "scan_statistics_equal": record["scan"] == independent,
            "selected_witness_equal": (
                record["selected_witness"] == selected
            ),
            "metadata_bytes_equal": (
                metadata_path.stat().st_size
                == metadata_artifact["bytes"]
                == len(pretty_json_bytes(metadata))
            ),
            "metadata_hash_equal": (
                metadata_hash == metadata_artifact["sha256"]
            ),
            "metadata_record_equal": (
                metadata == record_without_metadata
            ),
            "status_boundaries_equal": (
                record["status_ledger"]
                == {
                    "formula": "FORMULAS_GENERATED",
                    "direct_containment": expected_direct_status,
                    "root_lp": "NOT_STARTED",
                    "solver": "NOT_STARTED",
                    "proof": expected_proof_status,
                    "verification": "NOT_STARTED",
                }
                and record["formal_pruning_authorized"] is False
            ),
            **normalized_checks,
        }
        comparisons.append(
            {
                "orbit_index": orbit_index,
                "formula_sha256": sha256_file(source_path),
                "row_pairs_independently_tested": independent[
                    "row_pairs_tested"
                ],
                "support_containments_independently_found": independent[
                    "support_containments"
                ],
                "contradictions_independently_found": independent[
                    "contradictions_found"
                ],
                "checks": checks,
                "passed": all(checks.values()),
            }
        )

    observed_files = sorted(
        path.relative_to(scan_directory).as_posix()
        for path in scan_directory.rglob("*")
        if path.is_file()
    )
    expected_file_list = sorted(expected_files)
    inventory_equal = observed_files == expected_file_list
    proof_indices = [
        row["orbit_index"]
        for row in scan["instances"]
        if row["scan"]["contradictions_found"] > 0
    ]
    survivor_indices = [
        row["orbit_index"]
        for row in scan["instances"]
        if row["scan"]["contradictions_found"] == 0
    ]
    expected_summary = {
        "candidate_orbits_expected": len(expected_indices),
        "candidate_orbits_scanned": len(scan_records),
        "all_candidate_orbits_accounted_for": (
            sorted(scan_records) == expected_indices
        ),
        "orbit_indices": sorted(scan_records),
        "direct_contradictions_found": len(proof_indices),
        "proofs_generated": len(proof_indices),
        "survivors": len(survivor_indices),
        "proof_orbit_indices": proof_indices,
        "survivor_orbit_indices": survivor_indices,
        "total_row_pairs_tested": sum(
            row["scan"]["row_pairs_tested"]
            for row in scan["instances"]
        ),
        "total_support_containments": sum(
            row["scan"]["support_containments"]
            for row in scan["instances"]
        ),
    }
    input_checks = {
        "candidate_checkpoint_checksums_passed": True,
        "candidate_phase_hash_equal": (
            scan["input"]["candidate_checkpoint"][
                "phase_manifest"
            ]["sha256"]
            == candidate_phase_hash
        ),
        "candidate_corpus_hash_equal": (
            scan["input"]["candidate_checkpoint"][
                "candidate_corpus_manifest"
            ]["sha256"]
            == corpus_hash
        ),
        "class_index_equal": (
            scan["input"]["class_index"]
            == candidate_phase["input"]["class_index"]
        ),
        "canonical_link_hash_equal": (
            scan["input"]["canonical_labeled_link_sha256"]
            == candidate_phase["input"][
                "canonical_labeled_link_sha256"
            ]
        ),
        "candidate_partition_hash_equal": (
            scan["input"]["candidate_orbit_partition_sha256"]
            == candidate_phase["model"][
                "candidate_orbit_partition_sha256"
            ]
        ),
        "scan_summary_equal": scan["summary"] == expected_summary,
        "scan_file_inventory_equal": inventory_equal,
    }
    all_passed = (
        sorted(candidate_records) == expected_indices
        and sorted(scan_records) == expected_indices
        and all(row["passed"] for row in comparisons)
        and all(input_checks.values())
    )
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "status": "PASS" if all_passed else "ERROR",
        "input": {
            "candidate_checkpoint": {
                **checksum_audit,
                "phase_manifest_sha256": candidate_phase_hash,
                "corpus_manifest_sha256": corpus_hash,
            },
            "scan_manifest": {
                "path": "scan.manifest.json",
                "bytes": scan_path.stat().st_size,
                "sha256": scan_hash,
            },
        },
        "method": {
            "id": "independent-unit-support-containment-audit-v1",
            "description": (
                "Independently parse every native formula, enumerate every "
                "lower/upper row pair, recompute support containment and "
                "bound gaps, and reconstruct every emitted normalized "
                "formula and four-line proof byte for byte."
            ),
            "imports_direct_containment_module": False,
            "imports_production_opb_parser": False,
            "imports_production_proof_renderer": False,
        },
        "input_checks": input_checks,
        "comparisons": comparisons,
        "summary": {
            "expected_orbits": len(expected_indices),
            "observed_orbits": len(scan_records),
            "comparisons_passed": sum(
                row["passed"] for row in comparisons
            ),
            "all_orbits_accounted_for": (
                sorted(scan_records) == expected_indices
            ),
            "all_scan_results_equal": all_passed,
            "proofs_independently_reconstructed": len(proof_indices),
            "survivors_independently_confirmed": len(
                survivor_indices
            ),
        },
    }
