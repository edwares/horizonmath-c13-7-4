"""Independent exact audit for root-LP screening checkpoints.

This module deliberately does not import the production root-LP scanner,
the production OPB parser, or the Farkas proof renderer.  It reparses the
serialized formulas and verifier-normalized formulas and checks every
mathematical witness with Python arbitrary-precision arithmetic.
"""

from __future__ import annotations

import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Any


_NATIVE_HEADER_RE = re.compile(
    r"^\* #variable= (?P<variables>[0-9]+) "
    r"#constraint= (?P<constraints>[0-9]+)$"
)
_NATIVE_ROW_RE = re.compile(
    r"^(?P<terms>(?:\+1 x[1-9][0-9]* ?)+)"
    r"(?P<relation>>=|<=) (?P<rhs>-?[0-9]+) ;$"
)
_NATIVE_TERM_RE = re.compile(r"\+1 x([1-9][0-9]*)")
_NORMALIZED_ROW_RE = re.compile(
    r"^(?P<terms>(?:[+-]1 x[1-9][0-9]* ?)+)"
    r">= (?P<rhs>-?[0-9]+) ;$"
)
_NORMALIZED_TERM_RE = re.compile(r"([+-]1) x([1-9][0-9]*)")


class RootLPAuditError(ValueError):
    """Raised when an independently audited artifact is malformed."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RootLPAuditError(f"{path}: expected a JSON object")
    return value


def _safe_path(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise RootLPAuditError(f"unsafe artifact path: {relative!r}")
    path = root.joinpath(*pure.parts)
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise RootLPAuditError(
            f"artifact path escapes checkpoint: {relative!r}"
        ) from exc
    return path


def _verify_checksums(checkpoint: Path) -> dict[str, Any]:
    checksum_path = checkpoint / "SHA256SUMS"
    lines = checksum_path.read_text(encoding="utf-8").splitlines()
    recorded: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        parts = line.split("  ", 1)
        if (
            len(parts) != 2
            or len(parts[0]) != 64
            or any(character not in "0123456789abcdef" for character in parts[0])
            or not parts[1]
        ):
            raise RootLPAuditError(
                f"invalid SHA256SUMS row {line_number} in {checkpoint}"
            )
        expected, relative = parts
        if relative in recorded:
            raise RootLPAuditError(f"duplicate checksum path: {relative}")
        path = _safe_path(checkpoint, relative)
        if not path.is_file() or _sha256_file(path) != expected:
            raise RootLPAuditError(f"checksum mismatch: {relative}")
        recorded[relative] = expected
    observed = sorted(
        path.relative_to(checkpoint).as_posix()
        for path in checkpoint.rglob("*")
        if path.is_file() and path != checksum_path
    )
    if sorted(recorded) != observed:
        raise RootLPAuditError(
            f"SHA256SUMS does not cover every file in {checkpoint}"
        )
    return {
        "status": "PASS",
        "recorded_files": len(recorded),
        "sha256sums_sha256": _sha256_file(checksum_path),
        "all_recorded_hashes_match": True,
        "every_checkpoint_file_accounted_for": True,
    }


def _parse_native_opb(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise RootLPAuditError(f"{path}: empty OPB")
    header = _NATIVE_HEADER_RE.fullmatch(lines[0])
    if header is None:
        raise RootLPAuditError(f"{path}: malformed OPB header")
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(lines[1:], start=2):
        line = raw_line.strip()
        if not line or line.startswith("*"):
            continue
        match = _NATIVE_ROW_RE.fullmatch(line)
        if match is None:
            raise RootLPAuditError(
                f"{path}:{line_number}: unsupported native OPB row"
            )
        variables = tuple(
            int(value) for value in _NATIVE_TERM_RE.findall(match.group("terms"))
        )
        if tuple(sorted(set(variables))) != variables:
            raise RootLPAuditError(f"{path}:{line_number}: bad variable order")
        rows.append(
            {
                "variables": variables,
                "relation": match.group("relation"),
                "rhs": int(match.group("rhs")),
            }
        )
    variable_count = int(header.group("variables"))
    constraint_count = int(header.group("constraints"))
    if len(rows) != constraint_count:
        raise RootLPAuditError(f"{path}: constraint count mismatch")
    if any(
        variable < 1 or variable > variable_count
        for row in rows
        for variable in row["variables"]
    ):
        raise RootLPAuditError(f"{path}: variable outside declared range")
    return {
        "variable_count": variable_count,
        "constraint_count": constraint_count,
        "rows": rows,
    }


def _parse_normalized_opb(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise RootLPAuditError(f"{path}: empty normalized OPB")
    header = _NATIVE_HEADER_RE.fullmatch(lines[0])
    if header is None:
        raise RootLPAuditError(f"{path}: malformed normalized OPB header")
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(lines[1:], start=2):
        line = raw_line.strip()
        if not line or line.startswith("*"):
            continue
        match = _NORMALIZED_ROW_RE.fullmatch(line)
        if match is None:
            raise RootLPAuditError(
                f"{path}:{line_number}: unsupported normalized OPB row"
            )
        coefficients: dict[int, int] = {}
        for coefficient, variable in _NORMALIZED_TERM_RE.findall(
            match.group("terms")
        ):
            variable_id = int(variable)
            coefficients[variable_id] = (
                coefficients.get(variable_id, 0) + int(coefficient)
            )
        rows.append(
            {"coefficients": coefficients, "rhs": int(match.group("rhs"))}
        )
    variable_count = int(header.group("variables"))
    constraint_count = int(header.group("constraints"))
    if len(rows) != constraint_count:
        raise RootLPAuditError(f"{path}: normalized constraint count mismatch")
    return {
        "variable_count": variable_count,
        "constraint_count": constraint_count,
        "rows": rows,
    }


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _audit_feasible_witness(
    parsed: dict[str, Any], witness: dict[str, Any]
) -> dict[str, Any]:
    variable_count = parsed["variable_count"]
    values = [Fraction(0) for _ in range(variable_count)]
    seen: set[int] = set()
    for item in witness["nonzero_values"]:
        variable = int(item["variable_id_1based"])
        if variable < 1 or variable > variable_count or variable in seen:
            raise RootLPAuditError("invalid exact feasible witness variable")
        seen.add(variable)
        numerator = int(item["numerator"])
        denominator = int(item["denominator"])
        if denominator <= 0:
            raise RootLPAuditError("nonpositive witness denominator")
        values[variable - 1] = Fraction(numerator, denominator)

    serialized_vector = json.dumps(
        [[value.numerator, value.denominator] for value in values],
        separators=(",", ":"),
    ).encode("utf-8")
    bounds_pass = all(Fraction(0) <= value <= Fraction(1) for value in values)
    violations: list[int] = []
    tight_rows = 0
    minimum_slack: Fraction | None = None
    for row_id, row in enumerate(parsed["rows"], start=1):
        lhs = sum(values[variable - 1] for variable in row["variables"])
        if row["relation"] == ">=":
            slack = lhs - row["rhs"]
        else:
            slack = Fraction(row["rhs"]) - lhs
        if slack < 0:
            violations.append(row_id)
        if slack == 0:
            tight_rows += 1
        if minimum_slack is None or slack < minimum_slack:
            minimum_slack = slack
    checks = {
        "declared_variable_count_equal": (
            int(witness["variable_count"]) == variable_count
        ),
        "nonzero_count_equal": (
            int(witness["nonzero_variable_count"]) == len(seen)
        ),
        "vector_hash_equal": (
            witness["exact_vector_sha256"] == _sha256_bytes(serialized_vector)
        ),
        "all_bounds_satisfied_exactly": bounds_pass,
        "all_formula_rows_satisfied_exactly": not violations,
        "tight_row_count_equal": (
            int(witness["exact_tight_row_count"]) == tight_rows
        ),
        "minimum_slack_equal": (
            witness["minimum_exact_slack"] == _fraction_text(minimum_slack or Fraction(0))
        ),
    }
    return {
        "checks": checks,
        "violating_row_ids_1based": violations,
        "exact_tight_row_count": tight_rows,
        "minimum_exact_slack": _fraction_text(minimum_slack or Fraction(0)),
        "passed": all(checks.values()),
    }


def _expected_normalized_row(native: dict[str, Any]) -> dict[str, Any]:
    sign = 1 if native["relation"] == ">=" else -1
    return {
        "coefficients": {variable: sign for variable in native["variables"]},
        "rhs": sign * int(native["rhs"]),
    }


def _render_expected_proof(
    certificate: dict[str, Any], constraint_count: int
) -> bytes:
    tokens: list[str] = []
    first = True

    def append(operand: str, multiplier: int) -> None:
        nonlocal first
        tokens.extend([operand, str(multiplier), "*"])
        if not first:
            tokens.append("+")
        first = False

    for item in certificate["row_multipliers"]:
        append(str(item["row_id_1based"]), int(item["multiplier"]))
    for item in certificate["lower_bound_multipliers"]:
        append(f"x{item['variable']}", int(item["multiplier"]))
    for item in certificate["upper_bound_multipliers"]:
        append(f"~x{item['variable']}", int(item["multiplier"]))
    if first:
        raise RootLPAuditError("empty Farkas certificate")
    lines = [
        "pseudo-Boolean proof version 1.0",
        f"f {constraint_count}",
        "p " + " ".join(tokens),
        f"c {constraint_count + 1}",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _audit_farkas(
    parsed_native: dict[str, Any],
    normalized_path: Path,
    proof_path: Path,
    certificate: dict[str, Any],
) -> dict[str, Any]:
    normalized = _parse_normalized_opb(normalized_path)
    expected_rows = [_expected_normalized_row(row) for row in parsed_native["rows"]]
    rows_equal = normalized["rows"] == expected_rows
    variable_count = parsed_native["variable_count"]
    coefficients = [0 for _ in range(variable_count)]
    combined_rhs = 0
    row_ids_valid = True
    positive_multipliers = True
    for item in certificate["row_multipliers"]:
        row_id = int(item["row_id_1based"])
        multiplier = int(item["multiplier"])
        if row_id < 1 or row_id > len(expected_rows):
            row_ids_valid = False
            continue
        if multiplier <= 0:
            positive_multipliers = False
        row = expected_rows[row_id - 1]
        for variable, coefficient in row["coefficients"].items():
            coefficients[variable - 1] += coefficient * multiplier
        combined_rhs += row["rhs"] * multiplier
    for item in certificate["lower_bound_multipliers"]:
        variable = int(item["variable"])
        multiplier = int(item["multiplier"])
        if variable < 1 or variable > variable_count or multiplier <= 0:
            positive_multipliers = False
            continue
        coefficients[variable - 1] += multiplier
    for item in certificate["upper_bound_multipliers"]:
        variable = int(item["variable"])
        multiplier = int(item["multiplier"])
        if variable < 1 or variable > variable_count or multiplier <= 0:
            positive_multipliers = False
            continue
        coefficients[variable - 1] -= multiplier
        combined_rhs -= multiplier

    expected_proof = _render_expected_proof(
        certificate, parsed_native["constraint_count"]
    )
    actual_proof = proof_path.read_bytes()
    checks = {
        "normalized_variable_count_equal": (
            normalized["variable_count"] == variable_count
        ),
        "normalized_constraint_count_equal": (
            normalized["constraint_count"] == parsed_native["constraint_count"]
        ),
        "normalized_rows_equal_source_row_for_row": rows_equal,
        "all_row_ids_valid": row_ids_valid,
        "all_multipliers_strictly_positive": positive_multipliers,
        "all_variable_coefficients_cancel": not any(coefficients),
        "combined_rhs_strictly_positive": combined_rhs > 0,
        "combined_rhs_matches_certificate": (
            combined_rhs == int(certificate["combined_rhs_after_bounds"])
        ),
        "proof_tokens_equal_certificate": actual_proof == expected_proof,
    }
    return {
        "checks": checks,
        "recomputed_combined_rhs_after_bounds": combined_rhs,
        "proof_sha256": _sha256_bytes(actual_proof),
        "passed": all(checks.values()),
    }


def audit_root_lp_checkpoint(
    candidate_checkpoint_directory: Path,
    direct_containment_directory: Path,
    root_lp_directory: Path,
) -> dict[str, Any]:
    """Independently audit all exact root-LP results and proof bytes."""

    candidate_checksums = _verify_checksums(candidate_checkpoint_directory)
    direct_checksums = _verify_checksums(direct_containment_directory)
    candidate_phase = _load_json(candidate_checkpoint_directory / "phase.manifest.json")
    corpus_path = candidate_checkpoint_directory / "corpus" / "corpus.manifest.json"
    corpus = _load_json(corpus_path)
    direct_phase_path = direct_containment_directory / "phase.manifest.json"
    direct_phase = _load_json(direct_phase_path)
    root_manifest_path = root_lp_directory / "root-lp.manifest.json"
    root_manifest = _load_json(root_manifest_path)

    corpus_records = {
        int(row["orbit_index"]): row for row in corpus["instances"]
    }
    root_records = {
        int(row["orbit_index"]): row for row in root_manifest["instances"]
    }
    expected = [int(value) for value in candidate_phase["summary"]["orbit_indices"]]
    direct_survivors = [
        int(value) for value in direct_phase["summary"]["survivor_orbit_indices"]
    ]

    comparisons: list[dict[str, Any]] = []
    for orbit_index in expected:
        source = corpus_records[orbit_index]
        record = root_records[orbit_index]
        source_formula = _safe_path(
            candidate_checkpoint_directory / "corpus",
            source["formula"]["path"],
        )
        parsed = _parse_native_opb(source_formula)
        metadata_path = _safe_path(root_lp_directory, record["metadata"]["path"])
        metadata = _load_json(metadata_path)
        common_checks = {
            "source_formula_hash_equal": (
                _sha256_file(source_formula)
                == source["formula"]["sha256"]
                == record["source_formula"]["sha256"]
            ),
            "formula_variable_count_equal": (
                parsed["variable_count"] == int(source["formula"]["variables"])
            ),
            "formula_constraint_count_equal": (
                parsed["constraint_count"]
                == int(source["formula"]["opb_constraints"])
            ),
            "candidate_points_equal": (
                record["candidate_minimum_points"]
                == source["candidate_minimum_points"]
            ),
            "metadata_hash_equal": (
                _sha256_file(metadata_path) == record["metadata"]["sha256"]
            ),
            "metadata_body_equal": (
                {key: value for key, value in record.items() if key != "metadata"}
                == metadata
            ),
        }

        exact_status = record["exact_result"]["status"]
        if exact_status == "EXACT_LP_FEASIBLE":
            detail = _audit_feasible_witness(
                parsed, record["exact_result"]["feasible_witness"]
            )
            artifact_checks = {
                "no_farkas_formula_artifact": (
                    record["artifacts"]["verifier_normalized_formula"] is None
                ),
                "no_farkas_proof_artifact": record["artifacts"]["proof"] is None,
                "solver_reported_feasible": (
                    record["solver_report"]["status"] == "LP_FEASIBLE"
                ),
                "formal_pruning_not_authorized": (
                    record["formal_pruning_authorized"] is False
                ),
            }
        elif exact_status == "EXACT_FARKAS_CONTRADICTION":
            formula_artifact = record["artifacts"]["verifier_normalized_formula"]
            proof_artifact = record["artifacts"]["proof"]
            normalized_path = _safe_path(root_lp_directory, formula_artifact["path"])
            proof_path = _safe_path(root_lp_directory, proof_artifact["path"])
            detail = _audit_farkas(
                parsed,
                normalized_path,
                proof_path,
                record["exact_result"]["farkas_certificate"],
            )
            artifact_checks = {
                "normalized_formula_hash_equal": (
                    _sha256_file(normalized_path) == formula_artifact["sha256"]
                ),
                "proof_hash_equal": _sha256_file(proof_path) == proof_artifact["sha256"],
                "solver_reported_infeasible": (
                    record["solver_report"]["status"] == "SOLVER_UNSAT"
                ),
                "proof_status_generated": (
                    record["status_ledger"]["proof"] == "PROOF_GENERATED"
                ),
                "verification_not_started": (
                    record["status_ledger"]["verification"] == "NOT_STARTED"
                ),
                "formal_pruning_not_authorized": (
                    record["formal_pruning_authorized"] is False
                ),
            }
        else:
            raise RootLPAuditError(
                f"orbit {orbit_index}: unsupported exact result {exact_status}"
            )
        checks = {**common_checks, **artifact_checks}
        passed = all(checks.values()) and detail["passed"]
        comparisons.append(
            {
                "orbit_index": orbit_index,
                "exact_status": exact_status,
                "checks": checks,
                "exact_evidence_audit": detail,
                "passed": passed,
            }
        )

    top_level_checks = {
        "candidate_checkpoint_checksums_pass": candidate_checksums["status"] == "PASS",
        "direct_checkpoint_checksums_pass": direct_checksums["status"] == "PASS",
        "candidate_phase_status_formula_generated": (
            candidate_phase["status"] == "FORMULAS_GENERATED"
        ),
        "direct_phase_status_enumerated": direct_phase["status"] == "ENUMERATED",
        "direct_scan_had_no_contradictions": (
            int(direct_phase["summary"]["direct_contradictions_found"]) == 0
        ),
        "direct_survivors_equal_candidate_orbits": direct_survivors == expected,
        "root_orbits_complete": sorted(root_records) == expected,
        "root_manifest_candidate_phase_hash_equal": (
            root_manifest["input"]["candidate_checkpoint"]["phase_manifest_sha256"]
            == _sha256_file(candidate_checkpoint_directory / "phase.manifest.json")
        ),
        "root_manifest_direct_phase_hash_equal": (
            root_manifest["input"]["direct_containment_checkpoint"]["phase_manifest_sha256"]
            == _sha256_file(direct_phase_path)
        ),
        "milp_not_run": root_manifest["scope_guardrails"]["milp_run"] is False,
        "roundingsat_not_run": (
            root_manifest["scope_guardrails"]["roundingsat_run"] is False
        ),
        "verifier_not_run_in_math_checkpoint": (
            root_manifest["scope_guardrails"]["verifier_run"] is False
        ),
        "class_elimination_not_claimed": (
            root_manifest["scope_guardrails"]["class_elimination_claimed"] is False
            and root_manifest["scope_guardrails"]["C_13_7_4_equals_30_claimed"] is False
        ),
    }
    all_passed = all(top_level_checks.values()) and all(
        row["passed"] for row in comparisons
    )
    return {
        "schema_version": "horizonmath.independent-root-lp-checkpoint-audit.v1",
        "status": "PASS" if all_passed else "ERROR",
        "input": {
            "candidate_checkpoint_sha256sums": candidate_checksums,
            "direct_containment_sha256sums": direct_checksums,
            "root_lp_manifest": {
                "path": "root-lp.manifest.json",
                "sha256": _sha256_file(root_manifest_path),
            },
        },
        "method": {
            "imports_production_root_lp": False,
            "imports_production_opb_parser": False,
            "imports_production_farkas_renderer": False,
            "arithmetic": "Python Fraction and arbitrary-precision integers",
            "description": (
                "Reparse each native OPB; exactly check every rational LP "
                "witness or integer Farkas weighted sum; independently "
                "normalize source rows and reconstruct every four-line proof."
            ),
        },
        "top_level_checks": top_level_checks,
        "comparisons": comparisons,
        "summary": {
            "candidate_orbits": len(expected),
            "comparisons_passed": sum(row["passed"] for row in comparisons),
            "exact_lp_feasible_confirmed": sum(
                row["passed"] and row["exact_status"] == "EXACT_LP_FEASIBLE"
                for row in comparisons
            ),
            "exact_farkas_contradictions_confirmed": sum(
                row["passed"]
                and row["exact_status"] == "EXACT_FARKAS_CONTRADICTION"
                for row in comparisons
            ),
            "all_exact_evidence_confirmed": all_passed,
            "class_formally_eliminated": False,
        },
    }

