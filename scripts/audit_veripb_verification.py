#!/usr/bin/env python3
"""Independently audit hashes, flags, statuses, and logs of VeriPB runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from horizonlink.canonical import sha256_file, write_json, write_sha256_sidecar


def _log_value(lines: list[str], prefix: str) -> str | None:
    matches = [line[len(prefix) :] for line in lines if line.startswith(prefix)]
    return matches[0] if len(matches) == 1 else None


def _audit_record(
    record: dict[str, Any],
    candidate_corpus_directory: Path,
    farkas_directory: Path,
    verification_directory: Path,
) -> dict[str, Any]:
    source_formula = (
        candidate_corpus_directory / record["source_formula"]["path"]
    )
    formula = farkas_directory / record["formula"]["path"]
    proof = farkas_directory / record["proof"]["path"]
    certificate = farkas_directory / record["certificate"]["path"]
    log_path = (
        verification_directory / record["verification_log"]["path"]
    )
    result_path = (
        verification_directory / record["result_artifact"]["path"]
    )
    lines = log_path.read_text(encoding="utf-8").splitlines()
    command_text = _log_value(lines, "command_json: ")
    command = json.loads(command_text) if command_text is not None else []
    stdout_index = lines.index("stdout:") if "stdout:" in lines else -1
    stderr_index = lines.index("stderr:") if "stderr:" in lines else -1
    stdout_lines = (
        lines[stdout_index + 1 : stderr_index]
        if 0 <= stdout_index < stderr_index
        else []
    )
    stderr_lines = lines[stderr_index + 1 :] if stderr_index >= 0 else []
    checks = {
        "source_formula_hash_equal": (
            sha256_file(source_formula)
            == record["source_formula"]["expected_sha256"]
            == record["source_formula"]["actual_sha256"]
        ),
        "formula_hash_equal": (
            sha256_file(formula)
            == record["formula"]["expected_sha256"]
            == record["formula"]["actual_sha256"]
        ),
        "proof_hash_equal": (
            sha256_file(proof)
            == record["proof"]["expected_sha256"]
            == record["proof"]["actual_sha256"]
        ),
        "certificate_hash_equal": (
            sha256_file(certificate)
            == record["certificate"]["expected_sha256"]
            == record["certificate"]["actual_sha256"]
        ),
        "verification_log_hash_equal": (
            sha256_file(log_path) == record["verification_log"]["sha256"]
        ),
        "result_artifact_hash_equal": (
            sha256_file(result_path) == record["result_artifact"]["sha256"]
        ),
        "all_recorded_prechecks_true": all(record["prechecks"].values()),
        "all_recorded_verification_checks_true": all(
            record["verification_checks"].values()
        ),
        "record_status_verified_unsat": (
            record["status"] == "VERIFIED_UNSAT"
        ),
        "status_ledger_verified_unsat": (
            record["status_ledger"]["verification"] == "VERIFIED_UNSAT"
        ),
        "formal_pruning_authorized": (
            record["formal_pruning_authorized"] is True
        ),
        "command_has_require_unsat_exactly_once": (
            command.count("--requireUnsat") == 1
        ),
        "command_formula_path_equal": (
            len(command) >= 2 and command[-2] == str(formula)
        ),
        "command_proof_path_equal": (
            len(command) >= 1 and command[-1] == str(proof)
        ),
        "log_formula_hashes_equal": (
            _log_value(lines, "expected_formula_sha256: ")
            == record["formula"]["expected_sha256"]
            and _log_value(lines, "actual_formula_sha256: ")
            == record["formula"]["actual_sha256"]
        ),
        "log_proof_hashes_equal": (
            _log_value(lines, "expected_proof_sha256: ")
            == record["proof"]["expected_sha256"]
            and _log_value(lines, "actual_proof_sha256: ")
            == record["proof"]["actual_sha256"]
        ),
        "log_used_require_unsat": (
            _log_value(lines, "used_require_unsat: ") == "true"
        ),
        "log_exit_code_zero": _log_value(lines, "exit_code: ") == "0",
        "log_did_not_timeout": (
            _log_value(lines, "timed_out: ") == "false"
        ),
        "log_reported_success": (
            _log_value(lines, "reported_success: ") == "true"
        ),
        "log_stdout_reports_success": (
            stdout_lines == ["Verification succeeded."]
        ),
        "log_stderr_empty": not any(stderr_lines),
    }
    return {
        "orbit_index": record["orbit_index"],
        "checks": checks,
        "passed": all(checks.values()),
    }


def audit(
    candidate_corpus_directory: Path,
    farkas_directory: Path,
    verification_directory: Path,
) -> dict[str, Any]:
    manifest_path = verification_directory / "verification.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    comparisons = [
        _audit_record(
            record,
            candidate_corpus_directory,
            farkas_directory,
            verification_directory,
        )
        for record in manifest["instances"]
    ]
    verifier = manifest["verifier"]
    installed = verifier["installed_wheel_audit"]
    top_level_checks = {
        "manifest_status_verified_unsat": (
            manifest["status"] == "VERIFIED_UNSAT"
        ),
        "all_orbit_indices_unique": (
            len({row["orbit_index"] for row in manifest["instances"]})
            == len(manifest["instances"])
        ),
        "wheel_hash_equal": (
            sha256_file(Path(verifier["wheel"]["path"]))
            == verifier["wheel"]["sha256"]
        ),
        "source_archive_hash_equal": (
            sha256_file(Path(verifier["source_archive"]["path"]))
            == verifier["source_archive"]["sha256"]
        ),
        "build_setup_hash_equal": (
            sha256_file(Path(verifier["cp312_build_setup"]["path"]))
            == verifier["cp312_build_setup"]["sha256"]
        ),
        "verifier_executable_hash_equal": (
            sha256_file(Path(verifier["executable"]["path"]))
            == verifier["executable"]["sha256"]
        ),
        "required_flag_is_require_unsat": (
            verifier["required_flag"] == "--requireUnsat"
        ),
        "installed_wheel_record_all_matches": (
            installed["all_recorded_files_match"] is True
            and installed["recorded_files"] == installed["matched_files"]
            and all(row["passed"] for row in installed["comparisons"])
        ),
        "summary_counts_equal": (
            manifest["summary"]["proofs_submitted"] == len(comparisons)
            and manifest["summary"]["expected_formula_hashes_matched"]
            == len(comparisons)
            and manifest["summary"]["expected_proof_hashes_matched"]
            == len(comparisons)
            and manifest["summary"]["require_unsat_runs"]
            == len(comparisons)
            and manifest["summary"]["successful_veripb_runs"]
            == len(comparisons)
            and manifest["summary"]["verified_unsat"] == len(comparisons)
            and manifest["summary"]["formal_pruning_authorized"]
            == len(comparisons)
        ),
        "class_elimination_not_claimed": (
            manifest["summary"]["class_formally_eliminated"] is False
            and manifest["scope"]["class_formally_eliminated"] is False
            and manifest["scope"]["C_13_7_4_equals_30_claimed"] is False
        ),
    }
    all_passed = all(top_level_checks.values()) and all(
        comparison["passed"] for comparison in comparisons
    )
    return {
        "schema_version": (
            "horizonmath.independent-veripb-verification-audit.v1"
        ),
        "status": "PASS" if all_passed else "ERROR",
        "input": {
            "verification_manifest": {
                "path": str(manifest_path),
                "sha256": sha256_file(manifest_path),
            }
        },
        "method": {
            "description": (
                "Independently rehash every formula, proof, certificate, "
                "result, and log; parse every command and log; require one "
                "--requireUnsat flag, zero exit status, the exact VeriPB "
                "success report, empty stderr, and consistent VERIFIED_UNSAT "
                "status; recheck the installed package against the wheel "
                "RECORD."
            ),
            "reruns_verifier": False,
        },
        "top_level_checks": top_level_checks,
        "comparisons": comparisons,
        "summary": {
            "verification_records": len(comparisons),
            "records_passing": sum(row["passed"] for row in comparisons),
            "verified_unsat_confirmed": sum(
                row["passed"] for row in comparisons
            ),
            "class_formally_eliminated": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate-corpus-directory", type=Path, required=True
    )
    parser.add_argument("--farkas-directory", type=Path, required=True)
    parser.add_argument(
        "--verification-directory", type=Path, required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(
            args.candidate_corpus_directory,
            args.farkas_directory,
            args.verification_directory,
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(
            json.dumps(
                {"status": "ERROR", "message": str(exc)},
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    write_json(args.output, report)
    write_sha256_sidecar(args.output)
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
