"""Independent audit of root-LP VeriPB verification records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any


class RootLPVerificationAuditError(ValueError):
    """Raised when a verification checkpoint cannot be independently read."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_path(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise RootLPVerificationAuditError(f"unsafe path: {relative!r}")
    path = root.joinpath(*pure.parts)
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise RootLPVerificationAuditError(f"path escapes root: {relative!r}") from exc
    return path


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RootLPVerificationAuditError(f"{path}: expected object")
    return value


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
            raise RootLPVerificationAuditError(
                f"invalid root-LP SHA256SUMS row {line_number}"
            )
        expected, relative = parts
        if relative in recorded:
            raise RootLPVerificationAuditError(f"duplicate root-LP checksum path {relative}")
        path = _safe_path(checkpoint, relative)
        if not path.is_file() or _sha256_file(path) != expected:
            raise RootLPVerificationAuditError(f"root-LP checksum mismatch: {relative}")
        recorded[relative] = expected
    observed = sorted(
        path.relative_to(checkpoint).as_posix()
        for path in checkpoint.rglob("*")
        if path.is_file() and path != checksum_path
    )
    if sorted(recorded) != observed:
        raise RootLPVerificationAuditError("root-LP checksum inventory is incomplete")
    return {
        "status": "PASS",
        "recorded_files": len(recorded),
        "sha256sums_sha256": _sha256_file(checksum_path),
    }


def _log_value(lines: list[str], prefix: str) -> str | None:
    matches = [line[len(prefix) :] for line in lines if line.startswith(prefix)]
    return matches[0] if len(matches) == 1 else None


def _audit_record(
    record: dict[str, Any],
    root_record: dict[str, Any],
    root_lp_directory: Path,
    verification_directory: Path,
) -> dict[str, Any]:
    formula_artifact = root_record["artifacts"]["verifier_normalized_formula"]
    proof_artifact = root_record["artifacts"]["proof"]
    formula = _safe_path(root_lp_directory, formula_artifact["path"])
    proof = _safe_path(root_lp_directory, proof_artifact["path"])
    log_path = _safe_path(verification_directory, record["verification_log"]["path"])
    result_path = _safe_path(verification_directory, record["result_artifact"]["path"])
    result_body = _load_json(result_path)
    lines = log_path.read_text(encoding="utf-8").splitlines()
    command_text = _log_value(lines, "logical_command_json: ")
    command = json.loads(command_text) if command_text is not None else []
    stdout_index = lines.index("stdout:") if "stdout:" in lines else -1
    stderr_index = lines.index("stderr:") if "stderr:" in lines else -1
    stdout_lines = (
        lines[stdout_index + 1 : stderr_index]
        if 0 <= stdout_index < stderr_index
        else []
    )
    stderr_lines = lines[stderr_index + 1 :] if stderr_index >= 0 else []
    expected_command = [
        "veripb",
        "--requireUnsat",
        formula_artifact["path"],
        proof_artifact["path"],
    ]
    checks = {
        "root_exact_status_farkas": (
            root_record["exact_result"]["status"] == "EXACT_FARKAS_CONTRADICTION"
        ),
        "formula_hash_equal": (
            _sha256_file(formula)
            == formula_artifact["sha256"]
            == record["formula"]["expected_sha256"]
            == record["formula"]["actual_sha256"]
        ),
        "proof_hash_equal": (
            _sha256_file(proof)
            == proof_artifact["sha256"]
            == record["proof"]["expected_sha256"]
            == record["proof"]["actual_sha256"]
        ),
        "verification_log_hash_equal": (
            _sha256_file(log_path) == record["verification_log"]["sha256"]
        ),
        "result_artifact_hash_equal": (
            _sha256_file(result_path) == record["result_artifact"]["sha256"]
        ),
        "result_body_equal_manifest_record": (
            {key: value for key, value in record.items() if key != "result_artifact"}
            == result_body
        ),
        "all_prechecks_true": all(record["prechecks"].values()),
        "all_verification_checks_true": all(record["verification_checks"].values()),
        "record_status_verified_unsat": record["status"] == "VERIFIED_UNSAT",
        "formal_pruning_authorized": record["formal_pruning_authorized"] is True,
        "logical_command_exact": command == expected_command,
        "command_has_require_unsat_once": command.count("--requireUnsat") == 1,
        "log_expected_formula_hash_equal": (
            _log_value(lines, "expected_formula_sha256: ")
            == formula_artifact["sha256"]
        ),
        "log_actual_formula_hash_equal": (
            _log_value(lines, "actual_formula_sha256: ")
            == formula_artifact["sha256"]
        ),
        "log_expected_proof_hash_equal": (
            _log_value(lines, "expected_proof_sha256: ") == proof_artifact["sha256"]
        ),
        "log_actual_proof_hash_equal": (
            _log_value(lines, "actual_proof_sha256: ") == proof_artifact["sha256"]
        ),
        "log_used_require_unsat": _log_value(lines, "used_require_unsat: ") == "true",
        "log_exit_code_zero": _log_value(lines, "exit_code: ") == "0",
        "log_did_not_timeout": _log_value(lines, "timed_out: ") == "false",
        "log_reported_success": _log_value(lines, "reported_success: ") == "true",
        "stdout_exact_success": stdout_lines == ["Verification succeeded."],
        "stderr_empty": not any(stderr_lines),
    }
    return {
        "orbit_index": int(record["orbit_index"]),
        "checks": checks,
        "passed": all(checks.values()),
    }


def audit_root_lp_verification(
    root_lp_directory: Path,
    verification_directory: Path,
    verifier_wheel: Path,
    verifier_build_provenance: Path,
) -> dict[str, Any]:
    root_checksums = _verify_checksums(root_lp_directory)
    root_manifest_path = root_lp_directory / "root-lp.manifest.json"
    root_manifest = _load_json(root_manifest_path)
    verification_manifest_path = verification_directory / "verification.manifest.json"
    verification = _load_json(verification_manifest_path)
    build_provenance = _load_json(verifier_build_provenance)
    root_records = {
        int(row["orbit_index"]): row for row in root_manifest["instances"]
    }
    comparisons = [
        _audit_record(
            record,
            root_records[int(record["orbit_index"])],
            root_lp_directory,
            verification_directory,
        )
        for record in verification["instances"]
    ]
    expected_orbits = [
        int(value) for value in root_manifest["summary"]["exact_farkas_orbit_indices"]
    ]
    observed_orbits = [row["orbit_index"] for row in comparisons]
    wheel_hash = _sha256_file(verifier_wheel)
    provenance_hash = _sha256_file(verifier_build_provenance)
    top_level_checks = {
        "root_checkpoint_checksums_pass": root_checksums["status"] == "PASS",
        "root_math_audit_passed": (
            root_manifest["summary"]["exact_farkas_contradictions"]
            == len(expected_orbits)
        ),
        "verification_manifest_status_verified_unsat": (
            verification["status"] == "VERIFIED_UNSAT"
        ),
        "verified_orbits_equal_all_farkas_orbits": observed_orbits == expected_orbits,
        "verified_orbits_unique": observed_orbits == sorted(set(observed_orbits)),
        "wheel_hash_equal_manifest": (
            wheel_hash == verification["verifier"]["wheel"]["sha256"]
        ),
        "wheel_hash_equal_build_provenance": (
            wheel_hash == build_provenance["wheel"]["sha256"]
        ),
        "build_provenance_hash_equal_manifest": (
            provenance_hash
            == verification["verifier"]["build_provenance"]["sha256"]
        ),
        "build_provenance_status_smoke_tested": (
            build_provenance["status"] == "BUILT_AND_SMOKE_TESTED"
        ),
        "required_flag_exact": (
            verification["verifier"]["required_flag"] == "--requireUnsat"
        ),
        "installed_wheel_record_audit_passed": (
            verification["verifier"]["installed_wheel_audit"][
                "all_recorded_files_match"
            ]
            is True
        ),
        "summary_counts_equal": (
            verification["summary"]["proofs_submitted"] == len(comparisons)
            and verification["summary"]["formula_hashes_matched"] == len(comparisons)
            and verification["summary"]["proof_hashes_matched"] == len(comparisons)
            and verification["summary"]["require_unsat_runs"] == len(comparisons)
            and verification["summary"]["successful_veripb_runs"] == len(comparisons)
            and verification["summary"]["verified_unsat"] == len(comparisons)
        ),
        "class_elimination_not_claimed": (
            verification["scope"]["class_formally_eliminated"] is False
            and verification["scope"]["C_13_7_4_equals_30_claimed"] is False
        ),
    }
    all_passed = all(top_level_checks.values()) and all(
        comparison["passed"] for comparison in comparisons
    )
    return {
        "schema_version": "horizonmath.independent-root-lp-verification-audit.v1",
        "status": "PASS" if all_passed else "ERROR",
        "method": {
            "reruns_verifier": False,
            "description": (
                "Independently rehash every submitted formula, proof, result, "
                "and log; parse each preserved command and VeriPB outcome; "
                "rehash the pinned wheel and its build provenance."
            ),
        },
        "top_level_checks": top_level_checks,
        "comparisons": comparisons,
        "summary": {
            "verification_records": len(comparisons),
            "records_passing": sum(row["passed"] for row in comparisons),
            "verified_unsat_confirmed": sum(row["passed"] for row in comparisons),
            "all_verification_records_confirmed": all_passed,
            "class_formally_eliminated": False,
        },
    }

