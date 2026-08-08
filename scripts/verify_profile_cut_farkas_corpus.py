#!/usr/bin/env python3
"""Independently run VeriPB over a profile cut/Farkas proof corpus."""

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
    parser.add_argument("corpus_directory", type=Path)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path("/usr/bin/python3"))
    parser.add_argument("--veripb-pythonpath", type=Path, required=True)
    parser.add_argument("--veripb-wheel", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--skip-index", type=int, action="append")
    args = parser.parse_args()

    if args.output_directory.exists() and any(args.output_directory.iterdir()):
        raise ValueError("verification output directory must be empty")
    args.output_directory.mkdir(parents=True, exist_ok=True)
    logs_dir = args.output_directory / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = args.corpus_directory / "corpus.manifest.json"
    corpus = json.loads(manifest_path.read_text(encoding="utf-8"))
    if corpus.get("status") != "PROOFS_GENERATED_NOT_YET_VERIFIED":
        raise ValueError("proof corpus is not ready for verification")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(args.veripb_pythonpath)
    skipped = set(args.skip_index or [])
    selected_instances = [
        source
        for source in corpus["instances"]
        if int(source["index"]) not in skipped
    ]

    def resolve_artifact(relative_path: str) -> Path:
        direct = args.corpus_directory / relative_path
        if direct.exists():
            return direct
        legacy = args.corpus_directory / "instances" / relative_path
        if legacy.exists():
            return legacy
        raise FileNotFoundError(relative_path)

    records = []
    for ordinal, source in enumerate(selected_instances, start=1):
        formula_path = resolve_artifact(source["formula"]["path"])
        proof_path = resolve_artifact(source["proof"]["path"])
        hash_checks = {
            "formula": sha256_file(formula_path) == source["formula"]["sha256"],
            "proof": sha256_file(proof_path) == source["proof"]["sha256"],
        }
        if not all(hash_checks.values()):
            raise ValueError("formula/proof hash mismatch before verification")
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
        success_marker = "Verification succeeded." in completed.stdout
        assumptions_warning = "unjustified assumptions" in (
            completed.stdout + completed.stderr
        ).lower()
        status = (
            "VERIFIED_UNSAT"
            if completed.returncode == 0
            and success_marker
            and not assumptions_warning
            else "VERIFICATION_FAILED"
        )
        name = Path(source["proof"]["path"]).stem
        log_path = logs_dir / f"{name}.veripb.json"
        log = {
            "index": source["index"],
            "case_id": source["case_id"],
            "profile_id": source["profile_id"],
            "command": command,
            "formula_sha256": sha256_file(formula_path),
            "proof_sha256": sha256_file(proof_path),
            "hash_checks": hash_checks,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "success_marker_present": success_marker,
            "unjustified_assumptions_warning_present": assumptions_warning,
            "seconds": seconds,
            "status": status,
        }
        write_json(log_path, log)
        records.append(
            {
                "index": source["index"],
                "case_id": source["case_id"],
                "profile_id": source["profile_id"],
                "status": status,
                "seconds": seconds,
                "log": {
                    "path": log_path.relative_to(args.output_directory).as_posix(),
                    "sha256": sha256_file(log_path),
                },
            }
        )
        print(
            f"[{ordinal}/{len(selected_instances)}] index={source['index']} "
            f"status={status} seconds={seconds:.3f}",
            flush=True,
        )
        if status != "VERIFIED_UNSAT":
            raise RuntimeError(f"VeriPB rejected profile index {source['index']}")

    counts = Counter(row["status"] for row in records)
    report = {
        "schema_version": "horizonmath.profile-cut-farkas-verification.v1",
        "class_index": corpus["class_index"],
        "target_candidate_orbit": corpus["target_candidate_orbit"],
        "proof_corpus_manifest_sha256": sha256_file(manifest_path),
        "verifier": {
            "wheel": str(args.veripb_wheel),
            "wheel_sha256": sha256_file(args.veripb_wheel),
            "python": str(args.python),
            "pythonpath": str(args.veripb_pythonpath),
            "required_flag": "--requireUnsat",
        },
        "instance_count": len(records),
        "skipped_indices": sorted(skipped),
        "status_counts": dict(sorted(counts.items())),
        "instances": records,
        "all_verified_unsat": (
            len(records) == len(selected_instances)
            and all(row["status"] == "VERIFIED_UNSAT" for row in records)
        ),
        "status": "VERIFIED_UNSAT" if all(
            row["status"] == "VERIFIED_UNSAT" for row in records
        ) else "VERIFICATION_FAILED",
    }
    report_path = args.output_directory / "verification.manifest.json"
    write_json(report_path, report)
    print(json.dumps({
        "status": report["status"],
        "status_counts": report["status_counts"],
        "manifest": str(report_path),
        "sha256": sha256_file(report_path),
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
