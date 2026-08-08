#!/usr/bin/env python3
"""Verify a direct root-LP Farkas corpus with a pinned VeriPB wheel."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from collections import Counter
from pathlib import Path

from horizonlink.canonical import sha256_file, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("farkas_directory", type=Path)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path("/usr/bin/python3"))
    parser.add_argument("--veripb-pythonpath", type=Path, required=True)
    parser.add_argument("--veripb-wheel", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    args = parser.parse_args()

    if args.output_directory.exists() and any(args.output_directory.iterdir()):
        raise ValueError("verification output directory must be empty")
    args.output_directory.mkdir(parents=True, exist_ok=True)
    logs_dir = args.output_directory / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = args.farkas_directory / "farkas_corpus.manifest.json"
    corpus = json.loads(manifest_path.read_text(encoding="utf-8"))
    if corpus.get("status") != "PROOF_GENERATED":
        raise ValueError("Farkas corpus is not ready for verification")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(args.veripb_pythonpath)
    records = []
    for ordinal, source in enumerate(corpus["instances"], start=1):
        orbit = int(source["orbit_index"])
        formula_path = args.farkas_directory / source["formula"]["path"]
        proof_path = args.farkas_directory / source["proof"]["path"]
        certificate_path = (
            args.farkas_directory / source["certificate_artifact"]["path"]
        )
        hash_checks = {
            "formula": sha256_file(formula_path) == source["formula"]["sha256"],
            "proof": sha256_file(proof_path) == source["proof"]["sha256"],
            "certificate": (
                sha256_file(certificate_path)
                == source["certificate_artifact"]["sha256"]
            ),
        }
        if not all(hash_checks.values()):
            raise ValueError(f"artifact hash mismatch for orbit {orbit}")

        command = [
            str(args.python),
            "-m",
            "veripb",
            str(formula_path),
            str(proof_path),
            "--requireUnsat",
        ]
        started = time.monotonic()
        completed = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            timeout=args.timeout_seconds,
            check=False,
        )
        seconds = time.monotonic() - started
        output = completed.stdout + completed.stderr
        success_marker = "Verification succeeded." in completed.stdout
        assumptions_warning = "unjustified assumptions" in output.lower()
        status = (
            "VERIFIED_UNSAT"
            if completed.returncode == 0
            and success_marker
            and not assumptions_warning
            else "VERIFICATION_FAILED"
        )
        log = {
            "orbit_index": orbit,
            "command": command,
            "hash_checks": hash_checks,
            "formula_sha256": sha256_file(formula_path),
            "proof_sha256": sha256_file(proof_path),
            "certificate_sha256": sha256_file(certificate_path),
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "success_marker_present": success_marker,
            "unjustified_assumptions_warning_present": assumptions_warning,
            "seconds": seconds,
            "status": status,
        }
        log_path = logs_dir / f"orbit_{orbit:02d}.veripb.json"
        write_json(log_path, log)
        records.append(
            {
                "orbit_index": orbit,
                "status": status,
                "seconds": seconds,
                "log": {
                    "path": log_path.relative_to(args.output_directory).as_posix(),
                    "sha256": sha256_file(log_path),
                },
            }
        )
        print(
            f"[{ordinal}/{len(corpus['instances'])}] orbit={orbit} "
            f"status={status} seconds={seconds:.3f}",
            flush=True,
        )
        if status != "VERIFIED_UNSAT":
            raise RuntimeError(f"VeriPB rejected root-LP orbit {orbit}")

    counts = Counter(record["status"] for record in records)
    all_verified = bool(records) and all(
        record["status"] == "VERIFIED_UNSAT" for record in records
    )
    report = {
        "schema_version": "horizonmath.root-lp-farkas-verification.v1",
        "farkas_corpus_manifest_sha256": sha256_file(manifest_path),
        "verifier": {
            "wheel": str(args.veripb_wheel),
            "wheel_sha256": sha256_file(args.veripb_wheel),
            "python": str(args.python),
            "pythonpath": str(args.veripb_pythonpath),
            "required_flag": "--requireUnsat",
        },
        "instance_count": len(records),
        "status_counts": dict(sorted(counts.items())),
        "instances": records,
        "all_verified_unsat": all_verified,
        "status": "VERIFIED_UNSAT" if all_verified else "VERIFICATION_FAILED",
    }
    report_path = args.output_directory / "verification.manifest.json"
    write_json(report_path, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "status_counts": report["status_counts"],
                "manifest": str(report_path),
                "sha256": sha256_file(report_path),
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
