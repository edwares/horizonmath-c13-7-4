"""VeriPB verification gate for exact root-LP Farkas proofs."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from horizonlink import __version__
from horizonlink.canonical import sha256_file, write_json, write_sha256_sidecar
from horizonlink.root_lp_verification_audit import audit_root_lp_verification


VERIFICATION_SCHEMA_VERSION = "horizonmath.root-lp-veripb-verification.v1"
VERIFICATION_CHECKPOINT_SCHEMA_VERSION = (
    "horizonmath.root-lp-verification-checkpoint.v1"
)


class RootLPVerificationError(ValueError):
    """Raised when root-LP proof verification cannot safely start."""


def _write_checksums(output_directory: Path) -> Path:
    checksum_path = output_directory / "SHA256SUMS"
    targets = sorted(
        (
            path
            for path in output_directory.rglob("*")
            if path.is_file() and path != checksum_path
        ),
        key=lambda path: path.relative_to(output_directory).as_posix(),
    )
    checksum_path.write_text(
        "".join(
            f"{sha256_file(path)}  "
            f"{path.relative_to(output_directory).as_posix()}\n"
            for path in targets
        ),
        encoding="utf-8",
    )
    return checksum_path


def _verify_root_checkpoint_checksums(root_lp_directory: Path) -> dict[str, Any]:
    checksum_path = root_lp_directory / "SHA256SUMS"
    lines = checksum_path.read_text(encoding="utf-8").splitlines()
    recorded: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        parts = line.split("  ", 1)
        if len(parts) != 2 or len(parts[0]) != 64 or not parts[1]:
            raise RootLPVerificationError(
                f"invalid root-LP SHA256SUMS row {line_number}"
            )
        expected, relative = parts
        if relative in recorded:
            raise RootLPVerificationError(f"duplicate root-LP checksum path {relative}")
        path = root_lp_directory / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise RootLPVerificationError(f"root-LP checksum mismatch: {relative}")
        recorded[relative] = expected
    observed = sorted(
        path.relative_to(root_lp_directory).as_posix()
        for path in root_lp_directory.rglob("*")
        if path.is_file() and path != checksum_path
    )
    if sorted(recorded) != observed:
        raise RootLPVerificationError("root-LP checksum inventory is incomplete")
    return {
        "status": "PASS",
        "sha256sums_sha256": sha256_file(checksum_path),
        "recorded_files": len(recorded),
    }


def _audit_installed_wheel(verifier_python: Path, verifier_wheel: Path) -> dict[str, Any]:
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
        raise RootLPVerificationError("cannot probe installed VeriPB package")
    metadata = json.loads(probe.stdout)
    package_root = Path(metadata["package_root"])
    with zipfile.ZipFile(verifier_wheel) as archive:
        record_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/RECORD")
        ]
        if len(record_names) != 1:
            raise RootLPVerificationError("VeriPB wheel must contain one RECORD")
        rows = list(
            csv.reader(archive.read(record_names[0]).decode("utf-8").splitlines())
        )
    comparisons: list[tuple[str, str, int]] = []
    for relative, digest_field, size_field in rows:
        if not digest_field:
            continue
        algorithm, encoded = digest_field.split("=", 1)
        if algorithm != "sha256":
            raise RootLPVerificationError("unsupported wheel RECORD digest")
        expected = base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4)
        ).hex()
        installed = package_root / relative
        if not installed.is_file():
            raise RootLPVerificationError(f"installed wheel file missing: {relative}")
        actual = sha256_file(installed)
        actual_size = installed.stat().st_size
        if actual != expected or actual_size != int(size_field):
            raise RootLPVerificationError(f"installed wheel file mismatch: {relative}")
        comparisons.append((relative, actual, actual_size))
    digest = hashlib.sha256(
        json.dumps(comparisons, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "reported_version": metadata["version"],
        "recorded_files": len(comparisons),
        "matched_files": len(comparisons),
        "all_recorded_files_match": True,
        "installed_record_tree_sha256": digest,
    }


def _run_verifier(
    verifier: Path,
    formula: Path,
    proof: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    command = [str(verifier), "--requireUnsat", str(formula), str(proof)]
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
            "exit_code": None,
            "timed_out": True,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "reported_success": False,
        }
    output = completed.stdout + completed.stderr
    return {
        "exit_code": completed.returncode,
        "timed_out": False,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "reported_success": "Verification succeeded." in output,
    }


def _render_log(
    orbit_index: int,
    formula_artifact: dict[str, Any],
    proof_artifact: dict[str, Any],
    actual_formula_hash: str,
    actual_proof_hash: str,
    run: dict[str, Any],
) -> str:
    logical_command = [
        "veripb",
        "--requireUnsat",
        formula_artifact["path"],
        proof_artifact["path"],
    ]
    fields = [
        f"orbit_index: {orbit_index}",
        "logical_command_json: "
        + json.dumps(logical_command, separators=(",", ":")),
        "used_require_unsat: true",
        f"expected_formula_sha256: {formula_artifact['sha256']}",
        f"actual_formula_sha256: {actual_formula_hash}",
        f"expected_proof_sha256: {proof_artifact['sha256']}",
        f"actual_proof_sha256: {actual_proof_hash}",
        f"exit_code: {run['exit_code']}",
        f"timed_out: {str(run['timed_out']).lower()}",
        f"reported_success: {str(run['reported_success']).lower()}",
        "stdout:",
        run["stdout"].rstrip("\n"),
        "stderr:",
        run["stderr"].rstrip("\n"),
    ]
    return "\n".join(fields) + "\n"


def verify_root_lp_checkpoint(
    root_lp_directory: Path,
    verifier: Path,
    verifier_python: Path,
    verifier_wheel: Path,
    verifier_build_provenance: Path,
    output_directory: Path,
    *,
    timeout_seconds: float = 60.0,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Verify every exact Farkas proof and preserve a complete status ledger."""

    if timeout_seconds <= 0:
        raise RootLPVerificationError("verification timeout must be positive")
    if output_directory.exists() and any(output_directory.iterdir()):
        raise RootLPVerificationError("verification output directory must be empty")
    for label, path in (
        ("VeriPB executable", verifier),
        ("VeriPB Python", verifier_python),
        ("VeriPB wheel", verifier_wheel),
        ("VeriPB build provenance", verifier_build_provenance),
    ):
        if not path.is_file():
            raise RootLPVerificationError(f"{label} does not exist")

    checksum_audit = _verify_root_checkpoint_checksums(root_lp_directory)
    root_phase_path = root_lp_directory / "phase.manifest.json"
    root_manifest_path = root_lp_directory / "root-lp.manifest.json"
    root_audit_path = root_lp_directory / "independent-audit.json"
    root_phase = json.loads(root_phase_path.read_text(encoding="utf-8"))
    root_manifest = json.loads(root_manifest_path.read_text(encoding="utf-8"))
    root_audit = json.loads(root_audit_path.read_text(encoding="utf-8"))
    if (
        root_phase.get("status") != "PROOF_GENERATED"
        or root_audit.get("status") != "PASS"
        or root_phase.get("scope_guardrails", {}).get("verifier_run") is not False
        or root_phase.get("scope_guardrails", {}).get("formal_orbit_pruning_authorized")
        is not False
    ):
        raise RootLPVerificationError("root-LP mathematical checkpoint is not ready")

    build_provenance = json.loads(
        verifier_build_provenance.read_text(encoding="utf-8")
    )
    actual_wheel_hash = sha256_file(verifier_wheel)
    if (
        build_provenance.get("status") != "BUILT_AND_SMOKE_TESTED"
        or build_provenance.get("wheel", {}).get("sha256") != actual_wheel_hash
    ):
        raise RootLPVerificationError("VeriPB wheel does not match build provenance")
    installed_wheel_audit = _audit_installed_wheel(verifier_python, verifier_wheel)
    if not installed_wheel_audit["all_recorded_files_match"]:
        raise RootLPVerificationError("installed VeriPB package does not match wheel")

    root_records = {
        int(row["orbit_index"]): row for row in root_manifest["instances"]
    }
    farkas_orbits = [
        int(value) for value in root_manifest["summary"]["exact_farkas_orbit_indices"]
    ]
    audit_records = {
        int(row["orbit_index"]): row for row in root_audit["comparisons"]
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    instance_directory = output_directory / "instances"
    instance_directory.mkdir(parents=True, exist_ok=True)
    verification_records: list[dict[str, Any]] = []

    for orbit_index in farkas_orbits:
        root_record = root_records[orbit_index]
        formula_artifact = root_record["artifacts"]["verifier_normalized_formula"]
        proof_artifact = root_record["artifacts"]["proof"]
        formula = root_lp_directory / formula_artifact["path"]
        proof = root_lp_directory / proof_artifact["path"]
        actual_formula_hash = sha256_file(formula)
        actual_proof_hash = sha256_file(proof)
        prechecks = {
            "root_independent_audit_passed": audit_records[orbit_index]["passed"],
            "exact_result_is_farkas_contradiction": (
                root_record["exact_result"]["status"]
                == "EXACT_FARKAS_CONTRADICTION"
            ),
            "formula_hash_matches_expected": (
                actual_formula_hash == formula_artifact["sha256"]
            ),
            "proof_hash_matches_expected": actual_proof_hash == proof_artifact["sha256"],
            "proof_status_is_generated": (
                root_record["status_ledger"]["proof"] == "PROOF_GENERATED"
            ),
            "prior_verification_not_started": (
                root_record["status_ledger"]["verification"] == "NOT_STARTED"
            ),
        }
        if all(prechecks.values()):
            run = _run_verifier(verifier, formula, proof, timeout_seconds)
        else:
            run = {
                "exit_code": None,
                "timed_out": False,
                "stdout": "",
                "stderr": "VeriPB not run because a precheck failed.\n",
                "reported_success": False,
            }
        verification_checks = {
            "used_require_unsat": True,
            "verifier_did_not_timeout": not run["timed_out"],
            "verifier_exit_code_zero": run["exit_code"] == 0,
            "verifier_reported_success": run["reported_success"],
        }
        verified = all(prechecks.values()) and all(verification_checks.values())
        status = (
            "VERIFIED_UNSAT"
            if verified
            else ("TIMEOUT" if run["timed_out"] else "ERROR")
        )
        log_path = instance_directory / f"c{root_manifest['input']['class_index']}_candidate_orbit{orbit_index:02d}.veripb.log"
        log_path.write_text(
            _render_log(
                orbit_index,
                formula_artifact,
                proof_artifact,
                actual_formula_hash,
                actual_proof_hash,
                run,
            ),
            encoding="utf-8",
        )
        record = {
            "class_index": int(root_manifest["input"]["class_index"]),
            "orbit_index": orbit_index,
            "candidate_minimum_points": root_record["candidate_minimum_points"],
            "formula": {
                "path": formula_artifact["path"],
                "expected_sha256": formula_artifact["sha256"],
                "actual_sha256": actual_formula_hash,
            },
            "proof": {
                "path": proof_artifact["path"],
                "expected_sha256": proof_artifact["sha256"],
                "actual_sha256": actual_proof_hash,
            },
            "prechecks": prechecks,
            "verification_checks": verification_checks,
            "verification_log": {
                "path": log_path.relative_to(output_directory).as_posix(),
                "bytes": log_path.stat().st_size,
                "sha256": sha256_file(log_path),
            },
            "status": status,
            "status_ledger": {
                "formula": "FORMULAS_GENERATED",
                "direct_containment": "ENUMERATED",
                "root_lp": "SOLVER_UNSAT",
                "proof": "PROOF_GENERATED",
                "verification": status,
            },
            "formal_pruning_authorized": verified,
        }
        result_path = instance_directory / f"c{root_manifest['input']['class_index']}_candidate_orbit{orbit_index:02d}.verification.json"
        write_json(result_path, record)
        record["result_artifact"] = {
            "path": result_path.relative_to(output_directory).as_posix(),
            "bytes": result_path.stat().st_size,
            "sha256": sha256_file(result_path),
        }
        verification_records.append(record)

    all_verified = bool(verification_records) and all(
        record["status"] == "VERIFIED_UNSAT" for record in verification_records
    )
    verification_manifest = {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "status": "VERIFIED_UNSAT" if all_verified else "ERROR",
        "producer": {
            "package": "horizonlink",
            "version": __version__,
            "command": "verify-root-lp",
        },
        "input": {
            "class_index": int(root_manifest["input"]["class_index"]),
            "root_lp_phase_manifest_sha256": sha256_file(root_phase_path),
            "root_lp_manifest_sha256": sha256_file(root_manifest_path),
            "root_lp_independent_audit_sha256": sha256_file(root_audit_path),
            "root_lp_sha256sums_sha256": checksum_audit["sha256sums_sha256"],
            "proof_orbit_indices": farkas_orbits,
        },
        "verifier": {
            "name": "VeriPB",
            "reported_package_version": installed_wheel_audit["reported_version"],
            "executable": {
                "name": verifier.name,
                "sha256": sha256_file(verifier),
            },
            "wheel": {
                "name": verifier_wheel.name,
                "sha256": actual_wheel_hash,
            },
            "build_provenance": {
                "name": verifier_build_provenance.name,
                "sha256": sha256_file(verifier_build_provenance),
                "immutable_source_sha256": build_provenance["immutable_source"][
                    "sha256"
                ],
            },
            "required_flag": "--requireUnsat",
            "installed_wheel_audit": installed_wheel_audit,
        },
        "instances": verification_records,
        "summary": {
            "proofs_submitted": len(verification_records),
            "formula_hashes_matched": sum(
                row["prechecks"]["formula_hash_matches_expected"]
                for row in verification_records
            ),
            "proof_hashes_matched": sum(
                row["prechecks"]["proof_hash_matches_expected"]
                for row in verification_records
            ),
            "require_unsat_runs": len(verification_records),
            "successful_veripb_runs": sum(
                row["verification_checks"]["verifier_exit_code_zero"]
                and row["verification_checks"]["verifier_reported_success"]
                for row in verification_records
            ),
            "verified_unsat": sum(
                row["status"] == "VERIFIED_UNSAT" for row in verification_records
            ),
            "formal_pruning_authorized": sum(
                row["formal_pruning_authorized"] for row in verification_records
            ),
            "class_formally_eliminated": False,
        },
        "scope": {
            "root_lp_only": True,
            "milp_run": False,
            "roundingsat_run": False,
            "verifier_run": True,
            "class_formally_eliminated": False,
            "C_13_7_4_equals_30_claimed": False,
        },
    }
    verification_path = output_directory / "verification.manifest.json"
    write_json(verification_path, verification_manifest)
    write_sha256_sidecar(verification_path)

    audit = audit_root_lp_verification(
        root_lp_directory,
        output_directory,
        verifier_wheel,
        verifier_build_provenance,
    )
    audit_path = output_directory / "independent-audit.json"
    write_json(audit_path, audit)
    write_sha256_sidecar(audit_path)

    verified_by_orbit = {
        int(row["orbit_index"]): row for row in verification_records
    }
    phase_instances: list[dict[str, Any]] = []
    for root_record in root_manifest["instances"]:
        orbit_index = int(root_record["orbit_index"])
        if root_record["exact_result"]["status"] == "EXACT_LP_FEASIBLE":
            phase_instances.append(
                {
                    "orbit_index": orbit_index,
                    "candidate_minimum_points": root_record[
                        "candidate_minimum_points"
                    ],
                    "exact_root_lp_status": "EXACT_LP_FEASIBLE",
                    "status_ledger": {
                        "formula": "FORMULAS_GENERATED",
                        "direct_containment": "ENUMERATED",
                        "root_lp": "LP_FEASIBLE",
                        "proof": "NOT_STARTED",
                        "verification": "NOT_STARTED",
                    },
                    "formal_disposition": "SURVIVES_ROOT_LP",
                    "formal_pruning_authorized": False,
                }
            )
        else:
            verified_record = verified_by_orbit[orbit_index]
            phase_instances.append(
                {
                    "orbit_index": orbit_index,
                    "candidate_minimum_points": root_record[
                        "candidate_minimum_points"
                    ],
                    "exact_root_lp_status": "EXACT_FARKAS_CONTRADICTION",
                    "status_ledger": verified_record["status_ledger"],
                    "formal_disposition": (
                        "FORMALLY_PRUNED_ROOT_LP"
                        if verified_record["formal_pruning_authorized"]
                        else "RETAINED_PENDING_VERIFICATION"
                    ),
                    "formal_pruning_authorized": verified_record[
                        "formal_pruning_authorized"
                    ],
                }
            )

    pruned = [
        row["orbit_index"]
        for row in phase_instances
        if row["formal_pruning_authorized"]
    ]
    survivors = [
        row["orbit_index"]
        for row in phase_instances
        if not row["formal_pruning_authorized"]
    ]
    phase_ok = all_verified and audit["status"] == "PASS"
    phase = {
        "schema_version": VERIFICATION_CHECKPOINT_SCHEMA_VERSION,
        "status": "ENUMERATED" if phase_ok else "ERROR",
        "producer": verification_manifest["producer"],
        "input": verification_manifest["input"],
        "verifier": verification_manifest["verifier"],
        "instances": phase_instances,
        "summary": {
            "candidate_orbits_accounted_for": len(phase_instances),
            "exact_lp_feasible_survivors": len(survivors),
            "survivor_orbit_indices": survivors,
            "exact_farkas_proofs_verified": len(pruned),
            "formally_pruned_orbit_indices": pruned,
            "formal_orbits_pruned": len(pruned),
            "independent_verification_audit_records_passed": audit["summary"][
                "records_passing"
            ],
            "class_formally_eliminated": False,
        },
        "status_ledger": {
            "candidate_formulas": "FORMULAS_GENERATED",
            "direct_containment": "ENUMERATED",
            "root_lp": "ENUMERATED",
            "proof": "PROOF_GENERATED",
            "verification": "VERIFIED_UNSAT" if all_verified else "ERROR",
            "class": "ENUMERATED",
        },
        "scope_guardrails": {
            "all_candidate_orbits_accounted_for": len(phase_instances) == 12,
            "root_lp_run": True,
            "milp_run": False,
            "roundingsat_run": False,
            "verifier_run": True,
            "all_verifier_runs_used_requireUnsat": all_verified,
            "formal_orbit_pruning_authorized_only_for_verified_unsat": True,
            "class_elimination_claimed": False,
            "C_13_7_4_equals_30_claimed": False,
        },
        "artifacts": {
            "verification_manifest": {
                "path": "verification.manifest.json",
                "bytes": verification_path.stat().st_size,
                "sha256": sha256_file(verification_path),
            },
            "independent_audit": {
                "path": "independent-audit.json",
                "bytes": audit_path.stat().st_size,
                "sha256": sha256_file(audit_path),
            },
        },
    }
    phase_path = output_directory / "phase.manifest.json"
    write_json(phase_path, phase)
    write_sha256_sidecar(phase_path)
    _write_checksums(output_directory)
    return phase, verification_manifest, audit
