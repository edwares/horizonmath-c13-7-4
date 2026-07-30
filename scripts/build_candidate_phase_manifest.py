#!/usr/bin/env python3
"""Merge candidate formula, solver, proof, and verification accounting."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from horizonlink.canonical import sha256_file, write_json, write_sha256_sidecar


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build(
    candidate_corpus_directory: Path,
    solver_manifest_path: Path,
    farkas_directory: Path,
    verification_directory: Path,
    source_audit_path: Path,
    farkas_audit_path: Path,
    verification_audit_path: Path,
    split_farkas_directory: Path | None = None,
    split_verification_directory: Path | None = None,
    split_farkas_audit_path: Path | None = None,
    split_verification_audit_path: Path | None = None,
) -> dict[str, Any]:
    candidate_manifest_path = (
        candidate_corpus_directory / "corpus.manifest.json"
    )
    farkas_manifest_path = (
        farkas_directory / "farkas_corpus.manifest.json"
    )
    verification_manifest_path = (
        verification_directory / "verification.manifest.json"
    )
    candidate = _load(candidate_manifest_path)
    solver = _load(solver_manifest_path)
    farkas = _load(farkas_manifest_path)
    verification = _load(verification_manifest_path)
    source_audit = _load(source_audit_path)
    farkas_audit = _load(farkas_audit_path)
    verification_audit = _load(verification_audit_path)
    if source_audit["status"] != "PASS":
        raise ValueError("candidate source audit did not pass")
    if farkas_audit["status"] != "PASS":
        raise ValueError("exact Farkas audit did not pass")
    if verification_audit["status"] != "PASS":
        raise ValueError("VeriPB verification audit did not pass")
    split_arguments = (
        split_farkas_directory,
        split_verification_directory,
        split_farkas_audit_path,
        split_verification_audit_path,
    )
    if any(value is not None for value in split_arguments) and not all(
        value is not None for value in split_arguments
    ):
        raise ValueError(
            "all split proof and verification arguments must be supplied "
            "together"
        )

    candidate_records = {
        int(record["orbit_index"]): record
        for record in candidate["instances"]
    }
    solver_records = {
        int(record["orbit_index"]): record
        for record in solver["instances"]
    }
    farkas_records = {
        int(record["orbit_index"]): record
        for record in farkas["instances"]
    }
    verification_records = {
        int(record["orbit_index"]): record
        for record in verification["instances"]
    }
    proof_method_by_orbit = {
        orbit_index: farkas["method"]["id"]
        for orbit_index in farkas_records
    }
    split_artifacts: dict[str, Any] = {}
    if split_farkas_directory is not None:
        split_farkas_manifest_path = (
            split_farkas_directory / "farkas_corpus.manifest.json"
        )
        split_verification_manifest_path = (
            split_verification_directory / "verification.manifest.json"
        )
        split_farkas = _load(split_farkas_manifest_path)
        split_verification = _load(split_verification_manifest_path)
        split_farkas_audit = _load(split_farkas_audit_path)
        split_verification_audit = _load(
            split_verification_audit_path
        )
        if split_farkas_audit["status"] != "PASS":
            raise ValueError("exact split-Farkas audit did not pass")
        if split_verification_audit["status"] != "PASS":
            raise ValueError("split VeriPB verification audit did not pass")
        split_farkas_records = {
            int(record["orbit_index"]): record
            for record in split_farkas["instances"]
        }
        split_verification_records = {
            int(record["orbit_index"]): record
            for record in split_verification["instances"]
        }
        if sorted(split_farkas_records) != sorted(
            split_verification_records
        ):
            raise ValueError(
                "split proof and verification orbit sets differ"
            )
        overlap = set(farkas_records) & set(split_farkas_records)
        if overlap:
            raise ValueError(
                "an orbit appears in both proof corpora: "
                + ", ".join(map(str, sorted(overlap)))
            )
        farkas_records.update(split_farkas_records)
        verification_records.update(split_verification_records)
        proof_method_by_orbit.update(
            {
                orbit_index: split_farkas["method"]["id"]
                for orbit_index in split_farkas_records
            }
        )
        split_artifacts = {
            "split_farkas_manifest": {
                "path": str(split_farkas_manifest_path),
                "sha256": sha256_file(split_farkas_manifest_path),
            },
            "split_verification_manifest": {
                "path": str(split_verification_manifest_path),
                "sha256": sha256_file(
                    split_verification_manifest_path
                ),
            },
            "split_farkas_audit": {
                "path": str(split_farkas_audit_path),
                "sha256": sha256_file(split_farkas_audit_path),
            },
            "split_verification_audit": {
                "path": str(split_verification_audit_path),
                "sha256": sha256_file(
                    split_verification_audit_path
                ),
            },
        }
    expected = list(range(candidate["summary"]["candidate_orbits"]))
    if sorted(candidate_records) != expected or sorted(solver_records) != expected:
        raise ValueError("candidate or solver manifest has missing orbit records")
    if sorted(farkas_records) != sorted(verification_records):
        raise ValueError("proof and verification orbit sets differ")

    records = []
    for orbit_index in expected:
        formula = candidate_records[orbit_index]
        solved = solver_records[orbit_index]
        proof = farkas_records.get(orbit_index)
        verified = verification_records.get(orbit_index)
        is_verified = (
            verified is not None
            and verified.get("status") == "VERIFIED_UNSAT"
            and verified.get("formal_pruning_authorized") is True
        )
        if is_verified:
            final_status = "VERIFIED_UNSAT"
            formal_disposition = "PRUNED_VERIFIED_UNSAT"
            if proof_method_by_orbit[orbit_index].startswith(
                "exact-root-lp"
            ):
                mathematical_reason = (
                    "The root-LP relaxation has an exact integer Farkas "
                    "proof. The expected verifier-normalized formula and "
                    "proof hashes matched, and VeriPB accepted the proof "
                    "with --requireUnsat."
                )
            else:
                mathematical_reason = (
                    "A complete binary LP split tree has one independently "
                    "audited exact integer Farkas clause at every infeasible "
                    "leaf and resolves to contradiction. The expected formula "
                    "and proof hashes matched, and VeriPB accepted the proof "
                    "with --requireUnsat."
                )
        elif solved["status"] == "SOLVER_UNSAT":
            final_status = "SOLVER_UNSAT"
            formal_disposition = "RETAINED_PENDING_VERIFIED_CERTIFICATE"
            mathematical_reason = (
                "The controlled MILP run reported UNSAT, but no accepted "
                "formal certificate exists; the orbit remains in formal "
                "accounting."
            )
        elif solved["status"] == "TIMEOUT":
            final_status = "TIMEOUT"
            formal_disposition = "RETAINED_UNRESOLVED"
            mathematical_reason = (
                "The controlled MILP run reached its time limit without a "
                "formal result; the orbit remains unresolved."
            )
        else:
            final_status = solved["status"]
            formal_disposition = "RETAINED_UNRESOLVED"
            mathematical_reason = (
                "No VERIFIED_UNSAT certificate authorizes formal pruning."
            )
        record = {
            "orbit_index": orbit_index,
            "candidate_minimum_points": formula[
                "candidate_minimum_points"
            ],
            "formula": {
                "path": formula["formula"]["path"],
                "sha256": formula["formula"]["sha256"],
                "canonical_formula_sha256": formula["formula"][
                    "canonical_formula_sha256"
                ],
                "status": "FORMULAS_GENERATED",
            },
            "solver": {
                "root_lp_status": solved["root_lp"]["status"],
                "mip_status": solved["mip"]["status"],
                "status": solved["status"],
                "result_artifact": solved["result_artifact"],
                "solver_log": solved["solver_log"],
            },
            "proof": (
                {
                    "status": "PROOF_GENERATED",
                    "method": proof_method_by_orbit[orbit_index],
                    "artifact_corpus": (
                        "root_lp_farkas"
                        if proof_method_by_orbit[orbit_index].startswith(
                            "exact-root-lp"
                        )
                        else "lp_split_farkas"
                    ),
                    "formula": proof["formula"],
                    "proof": proof["proof"],
                    "certificate_artifact": proof[
                        "certificate_artifact"
                    ],
                    **(
                        {
                            "tree": proof["tree"],
                            "leaf_certificates": proof[
                                "leaf_certificates"
                            ],
                        }
                        if "tree" in proof
                        else {}
                    ),
                }
                if proof is not None
                else {"status": "NOT_STARTED"}
            ),
            "verification": (
                {
                    "status": verified["status"],
                    "artifact_corpus": (
                        "root_lp_verification"
                        if proof_method_by_orbit[orbit_index].startswith(
                            "exact-root-lp"
                        )
                        else "lp_split_verification"
                    ),
                    "verification_log": verified["verification_log"],
                    "result_artifact": verified["result_artifact"],
                    "formula_hash_matches_expected": verified["prechecks"][
                        "formula_hash_matches_expected"
                    ],
                    "proof_hash_matches_expected": verified["prechecks"][
                        "proof_hash_matches_expected"
                    ],
                    "used_require_unsat": verified[
                        "verification_checks"
                    ]["used_require_unsat"],
                    "verifier_exit_code_zero": verified[
                        "verification_checks"
                    ]["verifier_exit_code_zero"],
                    "verifier_reported_success": verified[
                        "verification_checks"
                    ]["verifier_reported_success"],
                }
                if verified is not None
                else {"status": "NOT_STARTED"}
            ),
            "historical_comparison": solved.get(
                "historical_comparison"
            ),
            "final_status": final_status,
            "formal_disposition": formal_disposition,
            "formal_pruning_authorized": is_verified,
            "mathematical_reason": mathematical_reason,
            "status_ledger": {
                "formula": "FORMULAS_GENERATED",
                "solver": solved["status"],
                "proof": (
                    "PROOF_GENERATED"
                    if proof is not None
                    else "NOT_STARTED"
                ),
                "verification": (
                    "VERIFIED_UNSAT"
                    if is_verified
                    else "NOT_STARTED"
                ),
            },
        }
        records.append(record)

    status_counts = Counter(record["final_status"] for record in records)
    verified_orbits = [
        record["orbit_index"]
        for record in records
        if record["formal_pruning_authorized"]
    ]
    retained_orbits = [
        record["orbit_index"]
        for record in records
        if not record["formal_pruning_authorized"]
    ]
    historical_discarded_orbits = [
        record["orbit_index"]
        for record in records
        if (record.get("historical_comparison") or {}).get(
            "historical_disposition"
        )
        == "DISCARDED"
    ]
    historical_retained_orbits = [
        record["orbit_index"]
        for record in records
        if (record.get("historical_comparison") or {}).get(
            "historical_disposition"
        )
        == "RETAINED"
    ]
    verified_set = set(verified_orbits)
    historical_discarded_verified = [
        orbit_index
        for orbit_index in historical_discarded_orbits
        if orbit_index in verified_set
    ]
    additional_verified = [
        orbit_index
        for orbit_index in verified_orbits
        if orbit_index not in set(historical_discarded_orbits)
    ]
    return {
        "schema_version": (
            "horizonmath.candidate-screening-phase-accounting.v1"
        ),
        "status": "FORMULAS_GENERATED",
        "input": {
            "class_index": candidate["input"]["class_index"],
            "canonical_labeled_link_sha256": candidate["input"][
                "canonical_labeled_link_sha256"
            ],
            "artifacts": {
                "candidate_corpus_manifest": {
                    "path": str(candidate_manifest_path),
                    "sha256": sha256_file(candidate_manifest_path),
                },
                "solver_manifest": {
                    "path": str(solver_manifest_path),
                    "sha256": sha256_file(solver_manifest_path),
                },
                "farkas_manifest": {
                    "path": str(farkas_manifest_path),
                    "sha256": sha256_file(farkas_manifest_path),
                },
                "verification_manifest": {
                    "path": str(verification_manifest_path),
                    "sha256": sha256_file(verification_manifest_path),
                },
                "source_audit": {
                    "path": str(source_audit_path),
                    "sha256": sha256_file(source_audit_path),
                },
                "farkas_audit": {
                    "path": str(farkas_audit_path),
                    "sha256": sha256_file(farkas_audit_path),
                },
                "verification_audit": {
                    "path": str(verification_audit_path),
                    "sha256": sha256_file(verification_audit_path),
                },
                **split_artifacts,
            },
        },
        "instances": records,
        "summary": {
            "candidate_orbits": len(records),
            "all_orbits_accounted_for": (
                [record["orbit_index"] for record in records] == expected
            ),
            "final_status_counts": dict(sorted(status_counts.items())),
            "verified_unsat_orbits": verified_orbits,
            "formally_pruned_orbits": len(verified_orbits),
            "retained_orbits": retained_orbits,
            "retained_orbit_count": len(retained_orbits),
            "solver_unsat_without_verified_proof": sum(
                record["final_status"] == "SOLVER_UNSAT"
                for record in records
            ),
            "timeouts": sum(
                record["final_status"] == "TIMEOUT"
                for record in records
            ),
            "class_formally_eliminated": False,
            "historical_18_8_partition": {
                "discarded_orbits": historical_discarded_orbits,
                "retained_orbits": historical_retained_orbits,
                "discarded_count": len(historical_discarded_orbits),
                "retained_count": len(historical_retained_orbits),
                "formally_verified_discarded_orbits": (
                    historical_discarded_verified
                ),
                "all_historical_discarded_orbits_now_verified": (
                    historical_discarded_verified
                    == historical_discarded_orbits
                ),
            },
            "additional_verified_orbits_beyond_historical_discarded": (
                additional_verified
            ),
        },
        "scope": {
            "formal_pruning_applies_only_to_listed_verified_orbits": True,
            "historical_18_8_partition_replaced": False,
            "historical_regression_outputs_preserved": True,
            "historical_18_8_partition_preserved_as_regression": (
                len(historical_discarded_orbits) == 18
                and len(historical_retained_orbits) == 8
            ),
            "fresh_formal_candidate_screening_status_recorded_separately": (
                True
            ),
            "class_formally_eliminated": False,
            "C_13_7_4_equals_30_claimed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate-corpus-directory", type=Path, required=True
    )
    parser.add_argument("--solver-manifest", type=Path, required=True)
    parser.add_argument("--farkas-directory", type=Path, required=True)
    parser.add_argument(
        "--verification-directory", type=Path, required=True
    )
    parser.add_argument("--source-audit", type=Path, required=True)
    parser.add_argument("--farkas-audit", type=Path, required=True)
    parser.add_argument("--verification-audit", type=Path, required=True)
    parser.add_argument("--split-farkas-directory", type=Path)
    parser.add_argument("--split-verification-directory", type=Path)
    parser.add_argument("--split-farkas-audit", type=Path)
    parser.add_argument("--split-verification-audit", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = build(
            args.candidate_corpus_directory,
            args.solver_manifest,
            args.farkas_directory,
            args.verification_directory,
            args.source_audit,
            args.farkas_audit,
            args.verification_audit,
            args.split_farkas_directory,
            args.split_verification_directory,
            args.split_farkas_audit,
            args.split_verification_audit,
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
    write_json(args.output, manifest)
    write_sha256_sidecar(args.output)
    print(json.dumps(manifest["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
