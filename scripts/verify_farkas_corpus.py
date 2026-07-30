#!/usr/bin/env python3
"""Verify a generated Farkas corpus with VeriPB and preserve every log."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

from horizonlink.canonical import (
    sha256_file,
    write_json,
    write_sha256_sidecar,
)


SCHEMA_VERSION = "horizonmath.farkas-veripb-verification.v1"


def _audit_installed_wheel(
    verifier_python: Path, verifier_wheel: Path
) -> dict[str, Any]:
    probe = subprocess.run(
        [
            str(verifier_python),
            "-c",
            (
                "import importlib.metadata,json,pathlib,sys,veripb;"
                "print(json.dumps({"
                "'python':sys.executable,"
                "'package_root':str(pathlib.Path(veripb.__file__).parent.parent),"
                "'version':importlib.metadata.version('veripb')"
                "},sort_keys=True))"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        raise ValueError("cannot probe the installed VeriPB package")
    metadata = json.loads(probe.stdout)
    package_root = Path(metadata["package_root"])
    with zipfile.ZipFile(verifier_wheel) as archive:
        record_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/RECORD")
        ]
        if len(record_names) != 1:
            raise ValueError("VeriPB wheel must contain exactly one RECORD")
        rows = list(
            csv.reader(
                archive.read(record_names[0]).decode("utf-8").splitlines()
            )
        )
    comparisons = []
    for relative, digest_field, size_field in rows:
        if not digest_field:
            continue
        algorithm, encoded = digest_field.split("=", 1)
        if algorithm != "sha256":
            raise ValueError("unsupported wheel RECORD digest algorithm")
        expected_digest = base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4)
        ).hex()
        installed = package_root / relative
        actual_digest = sha256_file(installed) if installed.is_file() else None
        actual_size = installed.stat().st_size if installed.is_file() else None
        comparisons.append(
            {
                "path": relative,
                "expected_sha256": expected_digest,
                "actual_sha256": actual_digest,
                "expected_bytes": int(size_field),
                "actual_bytes": actual_size,
                "passed": (
                    actual_digest == expected_digest
                    and actual_size == int(size_field)
                ),
            }
        )
    return {
        "python_executable": metadata["python"],
        "package_root": str(package_root),
        "reported_version": metadata["version"],
        "recorded_files": len(comparisons),
        "matched_files": sum(row["passed"] for row in comparisons),
        "all_recorded_files_match": all(
            row["passed"] for row in comparisons
        ),
        "installed_tree_sha256": hashlib.sha256(
            json.dumps(
                [
                    (row["path"], row["actual_sha256"], row["actual_bytes"])
                    for row in comparisons
                ],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "comparisons": comparisons,
    }


def _run_verifier(
    verifier: Path,
    formula_path: Path,
    proof_path: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    command = [
        str(verifier),
        "--requireUnsat",
        str(formula_path),
        str(proof_path),
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "used_require_unsat": "--requireUnsat" in command,
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "seconds": time.monotonic() - started,
            "timed_out": True,
            "reported_success": False,
        }
    output = completed.stdout + completed.stderr
    return {
        "command": command,
        "used_require_unsat": "--requireUnsat" in command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "seconds": time.monotonic() - started,
        "timed_out": False,
        "reported_success": "Verification succeeded." in output,
    }


def _render_log(
    orbit_index: int,
    expected_formula_hash: str,
    actual_formula_hash: str,
    expected_proof_hash: str,
    actual_proof_hash: str,
    run: dict[str, Any],
) -> str:
    fields = [
        f"orbit_index: {orbit_index}",
        "command_json: "
        + json.dumps(run["command"], separators=(",", ":")),
        f"used_require_unsat: {str(run['used_require_unsat']).lower()}",
        f"expected_formula_sha256: {expected_formula_hash}",
        f"actual_formula_sha256: {actual_formula_hash}",
        f"expected_proof_sha256: {expected_proof_hash}",
        f"actual_proof_sha256: {actual_proof_hash}",
        f"exit_code: {run['exit_code']}",
        f"timed_out: {str(run['timed_out']).lower()}",
        f"reported_success: {str(run['reported_success']).lower()}",
        f"seconds: {run['seconds']:.9f}",
        "stdout:",
        run["stdout"].rstrip("\n"),
        "stderr:",
        run["stderr"].rstrip("\n"),
    ]
    return "\n".join(fields) + "\n"


def verify(
    candidate_corpus_directory: Path,
    farkas_directory: Path,
    verifier: Path,
    verifier_python: Path,
    verifier_wheel: Path,
    verifier_source_archive: Path,
    verifier_setup: Path,
    output_directory: Path,
    *,
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    if timeout_seconds <= 0:
        raise ValueError("verification timeout must be positive")
    if output_directory.exists() and any(output_directory.iterdir()):
        raise ValueError("verification output directory must be empty")
    if not verifier.is_file():
        raise ValueError("VeriPB executable does not exist")
    if not verifier_python.is_file():
        raise ValueError("VeriPB Python executable does not exist")
    if not verifier_wheel.is_file():
        raise ValueError("VeriPB wheel does not exist")
    if not verifier_source_archive.is_file():
        raise ValueError("VeriPB source archive does not exist")
    if not verifier_setup.is_file():
        raise ValueError("VeriPB build setup does not exist")

    candidate_manifest_path = (
        candidate_corpus_directory / "corpus.manifest.json"
    )
    farkas_manifest_path = (
        farkas_directory / "farkas_corpus.manifest.json"
    )
    candidate_manifest = json.loads(
        candidate_manifest_path.read_text(encoding="utf-8")
    )
    farkas_manifest = json.loads(
        farkas_manifest_path.read_text(encoding="utf-8")
    )
    if farkas_manifest.get("status") != "PROOF_GENERATED":
        raise ValueError("Farkas corpus must have status PROOF_GENERATED")
    installed_wheel_audit = _audit_installed_wheel(
        verifier_python, verifier_wheel
    )
    if not installed_wheel_audit["all_recorded_files_match"]:
        raise ValueError("installed VeriPB package does not match wheel RECORD")
    candidate_records = {
        int(record["orbit_index"]): record
        for record in candidate_manifest["instances"]
    }

    output_directory.mkdir(parents=True, exist_ok=True)
    instance_directory = output_directory / "instances"
    instance_directory.mkdir(parents=True, exist_ok=True)
    records = []
    for manifest_record in farkas_manifest["instances"]:
        orbit_index = int(manifest_record["orbit_index"])
        certificate_path = (
            farkas_directory
            / manifest_record["certificate_artifact"]["path"]
        )
        certificate_hash = sha256_file(certificate_path)
        certificate = json.loads(
            certificate_path.read_text(encoding="utf-8")
        )
        source_formula_path = (
            candidate_corpus_directory
            / certificate["source_formula"]["path"]
        )
        formula_path = farkas_directory / certificate["formula"]["path"]
        proof_path = farkas_directory / certificate["proof"]["path"]
        expected_formula_hash = certificate["formula"]["sha256"]
        expected_proof_hash = certificate["proof"]["sha256"]
        actual_source_formula_hash = sha256_file(source_formula_path)
        actual_formula_hash = sha256_file(formula_path)
        actual_proof_hash = sha256_file(proof_path)
        prechecks = {
            "certificate_hash_matches_manifest": (
                certificate_hash
                == manifest_record["certificate_artifact"]["sha256"]
            ),
            "source_formula_hash_matches_candidate_manifest": (
                candidate_records[orbit_index]["formula"]["sha256"]
                == certificate["source_formula"]["sha256"]
                == actual_source_formula_hash
            ),
            "formula_hash_matches_expected": (
                actual_formula_hash == expected_formula_hash
            ),
            "proof_hash_matches_expected": (
                actual_proof_hash == expected_proof_hash
            ),
            "proof_status_is_proof_generated": (
                certificate["status"] == "PROOF_GENERATED"
            ),
            "prior_verification_status_is_not_started": (
                certificate["status_ledger"]["verification"]
                == "NOT_STARTED"
            ),
        }
        if all(prechecks.values()):
            run = _run_verifier(
                verifier, formula_path, proof_path, timeout_seconds
            )
        else:
            run = {
                "command": [
                    str(verifier),
                    "--requireUnsat",
                    str(formula_path),
                    str(proof_path),
                ],
                "used_require_unsat": True,
                "exit_code": None,
                "stdout": "",
                "stderr": "VeriPB not run because a hash/status precheck failed.\n",
                "seconds": 0.0,
                "timed_out": False,
                "reported_success": False,
            }
        log_path = (
            instance_directory
            / f"c52_candidate_orbit{orbit_index:02d}.veripb.log"
        )
        log_path.write_text(
            _render_log(
                orbit_index,
                expected_formula_hash,
                actual_formula_hash,
                expected_proof_hash,
                actual_proof_hash,
                run,
            ),
            encoding="utf-8",
        )
        verification_checks = {
            "used_require_unsat": run["used_require_unsat"],
            "verifier_did_not_timeout": not run["timed_out"],
            "verifier_exit_code_zero": run["exit_code"] == 0,
            "verifier_reported_success": run["reported_success"],
        }
        verified = all(prechecks.values()) and all(
            verification_checks.values()
        )
        status = (
            "VERIFIED_UNSAT"
            if verified
            else ("TIMEOUT" if run["timed_out"] else "ERROR")
        )
        record = {
            "orbit_index": orbit_index,
            "candidate_minimum_points": certificate[
                "candidate_minimum_points"
            ],
            "source_formula": {
                "path": certificate["source_formula"]["path"],
                "expected_sha256": certificate["source_formula"]["sha256"],
                "actual_sha256": actual_source_formula_hash,
            },
            "formula": {
                "path": certificate["formula"]["path"],
                "expected_sha256": expected_formula_hash,
                "actual_sha256": actual_formula_hash,
            },
            "proof": {
                "path": certificate["proof"]["path"],
                "expected_sha256": expected_proof_hash,
                "actual_sha256": actual_proof_hash,
            },
            "certificate": {
                "path": manifest_record["certificate_artifact"]["path"],
                "expected_sha256": manifest_record[
                    "certificate_artifact"
                ]["sha256"],
                "actual_sha256": certificate_hash,
            },
            "prechecks": prechecks,
            "verification_checks": verification_checks,
            "verifier_run": {
                "command": run["command"],
                "seconds": run["seconds"],
                "exit_code": run["exit_code"],
                "timed_out": run["timed_out"],
                "reported_success": run["reported_success"],
            },
            "verification_log": {
                "path": log_path.relative_to(
                    output_directory
                ).as_posix(),
                "sha256": sha256_file(log_path),
            },
            "status": status,
            "status_ledger": {
                "formula": "FORMULAS_GENERATED",
                "root_lp": certificate["status_ledger"]["root_lp"],
                "solver": certificate["status_ledger"]["solver"],
                "proof": "PROOF_GENERATED",
                "verification": status,
            },
            "formal_pruning_authorized": verified,
        }
        result_path = (
            instance_directory
            / f"c52_candidate_orbit{orbit_index:02d}.verification.json"
        )
        write_json(result_path, record)
        record["result_artifact"] = {
            "path": result_path.relative_to(
                output_directory
            ).as_posix(),
            "sha256": sha256_file(result_path),
        }
        records.append(record)

    all_verified = bool(records) and all(
        record["status"] == "VERIFIED_UNSAT" for record in records
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "VERIFIED_UNSAT" if all_verified else "ERROR",
        "input": {
            "candidate_corpus_manifest": {
                "path": str(candidate_manifest_path),
                "sha256": sha256_file(candidate_manifest_path),
            },
            "farkas_corpus_manifest": {
                "path": str(farkas_manifest_path),
                "sha256": sha256_file(farkas_manifest_path),
            },
        },
        "verifier": {
            "name": "VeriPB",
            "reported_package_version": "0.3a0",
            "executable": {
                "path": str(verifier),
                "sha256": sha256_file(verifier),
            },
            "wheel": {
                "path": str(verifier_wheel),
                "sha256": sha256_file(verifier_wheel),
            },
            "source_archive": {
                "path": str(verifier_source_archive),
                "sha256": sha256_file(verifier_source_archive),
            },
            "cp312_build_setup": {
                "path": str(verifier_setup),
                "sha256": sha256_file(verifier_setup),
            },
            "required_flag": "--requireUnsat",
            "installed_wheel_audit": installed_wheel_audit,
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
        },
        "instances": records,
        "summary": {
            "proofs_submitted": len(records),
            "expected_formula_hashes_matched": sum(
                record["prechecks"]["formula_hash_matches_expected"]
                for record in records
            ),
            "expected_proof_hashes_matched": sum(
                record["prechecks"]["proof_hash_matches_expected"]
                for record in records
            ),
            "require_unsat_runs": sum(
                record["verification_checks"]["used_require_unsat"]
                for record in records
            ),
            "successful_veripb_runs": sum(
                record["verification_checks"]["verifier_exit_code_zero"]
                and record["verification_checks"][
                    "verifier_reported_success"
                ]
                for record in records
            ),
            "verified_unsat": sum(
                record["status"] == "VERIFIED_UNSAT"
                for record in records
            ),
            "formal_pruning_authorized": sum(
                record["formal_pruning_authorized"]
                for record in records
            ),
            "class_formally_eliminated": False,
        },
        "scope": {
            "verified_candidate_orbits_only": True,
            "all_candidate_orbits_verified": (
                len(records)
                == candidate_manifest["summary"]["candidate_orbits"]
            ),
            "class_formally_eliminated": False,
            "C_13_7_4_equals_30_claimed": False,
        },
    }
    manifest_path = output_directory / "verification.manifest.json"
    write_json(manifest_path, manifest)
    write_sha256_sidecar(manifest_path)
    checksum_targets = sorted(
        (
            path
            for path in output_directory.rglob("*")
            if path.is_file()
            and path.name != "SHA256SUMS"
            and not path.name.endswith(".sha256")
        ),
        key=lambda path: path.relative_to(output_directory).as_posix(),
    )
    (output_directory / "SHA256SUMS").write_text(
        "".join(
            f"{sha256_file(path)}  "
            f"{path.relative_to(output_directory).as_posix()}\n"
            for path in checksum_targets
        ),
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate-corpus-directory", type=Path, required=True
    )
    parser.add_argument("--farkas-directory", type=Path, required=True)
    parser.add_argument("--verifier", type=Path, required=True)
    parser.add_argument("--verifier-python", type=Path, required=True)
    parser.add_argument("--verifier-wheel", type=Path, required=True)
    parser.add_argument(
        "--verifier-source-archive", type=Path, required=True
    )
    parser.add_argument("--verifier-setup", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    args = parser.parse_args()
    try:
        report = verify(
            args.candidate_corpus_directory,
            args.farkas_directory,
            args.verifier,
            args.verifier_python,
            args.verifier_wheel,
            args.verifier_source_archive,
            args.verifier_setup,
            args.output_directory,
            timeout_seconds=args.timeout_seconds,
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
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "VERIFIED_UNSAT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
