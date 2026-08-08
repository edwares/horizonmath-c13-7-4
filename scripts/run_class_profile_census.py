#!/usr/bin/env python3
"""Build an exhaustive exact-degree profile census after verified root pruning."""

from __future__ import annotations

import argparse
import json
import time
import warnings
from collections import Counter
from pathlib import Path

from horizonlink.canonical import sha256_file, write_json
from horizonlink.pb import build_corrected_formula, canonical_formula_sha256
from horizonlink.profiles import (
    compute_exact_minimum_set_orbits,
    compute_extension_degree_profiles,
    degree_budget,
)
from horizonlink.solver import _root_lp_matrices, _status_from_scipy


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object in {path}")
    return value


def _verified_root_partition(
    structural: dict,
    farkas_manifest_path: Path,
    verification_manifest_path: Path,
) -> tuple[list[int], list[int], dict, dict]:
    farkas = _load_json(farkas_manifest_path)
    verification = _load_json(verification_manifest_path)
    if farkas.get("status") != "PROOF_GENERATED":
        raise ValueError("root Farkas corpus must have status PROOF_GENERATED")
    if verification.get("status") != "VERIFIED_UNSAT":
        raise ValueError("root verification must have status VERIFIED_UNSAT")
    if not verification.get("all_verified_unsat"):
        raise ValueError("root verification is not an all-UNSAT gate")
    if verification.get("farkas_corpus_manifest_sha256") != sha256_file(
        farkas_manifest_path
    ):
        raise ValueError("root verification does not bind the Farkas corpus")

    proof_orbits = sorted(int(row["orbit_index"]) for row in farkas["instances"])
    verified_orbits = sorted(
        int(row["orbit_index"])
        for row in verification["instances"]
        if row.get("status") == "VERIFIED_UNSAT"
    )
    if proof_orbits != verified_orbits or len(proof_orbits) != len(set(proof_orbits)):
        raise ValueError("root proof and verification orbit coverage differ")

    orbit_count = int(structural["candidate_minimum_point_sets"]["orbit_count"])
    if not set(verified_orbits) <= set(range(orbit_count)):
        raise ValueError("verified root orbit index is outside the structural partition")
    retained = sorted(set(range(orbit_count)) - set(verified_orbits))
    return verified_orbits, retained, farkas, verification


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("structural_manifest", type=Path)
    parser.add_argument("root_farkas_manifest", type=Path)
    parser.add_argument("root_verification_manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root-lp-time-limit", type=float, default=5.0)
    args = parser.parse_args()

    if args.root_lp_time_limit <= 0:
        raise ValueError("root LP time limit must be positive")
    if args.output.exists():
        raise ValueError("output path already exists")

    import numpy
    import scipy
    import scipy.optimize
    import scipy.sparse

    structural = _load_json(args.structural_manifest)
    if structural.get("status") != "ENUMERATED":
        raise ValueError("structural manifest must have status ENUMERATED")
    normalized = structural["input"]["normalized_document"]
    point_labels = tuple(int(value) for value in normalized["point_labels"])
    link_blocks = tuple(
        tuple(int(value) for value in block) for block in normalized["blocks"]
    )
    group = tuple(
        tuple(int(value) for value in permutation)
        for permutation in structural["automorphism_group"]["permutations"]
    )

    pruned, retained, farkas, verification = _verified_root_partition(
        structural,
        args.root_farkas_manifest,
        args.root_verification_manifest,
    )
    exact_sets = compute_exact_minimum_set_orbits(
        point_labels,
        group,
        structural["candidate_minimum_point_sets"],
        retained,
    )
    budget = degree_budget(point_labels, link_blocks)
    profiles = compute_extension_degree_profiles(
        point_labels,
        group,
        exact_sets,
        range(int(exact_sets["orbit_count"])),
        budget["minimum_extension_degrees"],
        int(budget["derivation"]["excess"]),
    )

    records = []
    for index, profile in enumerate(profiles["profiles"]):
        built = build_corrected_formula(
            point_labels, link_blocks, profile["extension_degrees"]
        )
        variable_count = int(built["metadata"]["variables"])
        a_ub, b_ub, a_eq, b_eq = _root_lp_matrices(
            built["bounded_rows"], variable_count, numpy, scipy.sparse
        )
        started = time.monotonic()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = scipy.optimize.linprog(
                numpy.zeros(variable_count),
                A_ub=a_ub,
                b_ub=b_ub,
                A_eq=a_eq,
                b_eq=b_eq,
                bounds=(0, 1),
                method="highs",
                options={
                    "time_limit": float(args.root_lp_time_limit),
                    "presolve": True,
                    "threads": 1,
                    "parallel": False,
                    "random_seed": 0,
                },
            )
        raw_status = _status_from_scipy(int(result.status))
        status = "LP_FEASIBLE" if raw_status == "SAT" else raw_status
        records.append(
            {
                "index": index,
                "case_id": int(profile["case_id"]),
                "profile_id": int(profile["profile_id"]),
                "profile_orbit_size": int(profile["orbit_size"]),
                "excess_profile": list(profile["representative"]),
                "extension_degrees": list(profile["extension_degrees"]),
                "formula": {
                    "variables": variable_count,
                    "constraints": len(built["rows"]),
                    "canonical_formula_sha256": canonical_formula_sha256(
                        built["rows"], variable_count=variable_count
                    ),
                },
                "root_lp": {
                    "status": status,
                    "reported_status": int(result.status),
                    "reported_message": str(result.message),
                    "iterations": (
                        None if result.nit is None else int(result.nit)
                    ),
                    "seconds": time.monotonic() - started,
                },
            }
        )
        if (index + 1) % 100 == 0 or index + 1 == profiles["profile_orbit_count"]:
            print(
                f"[{index + 1}/{profiles['profile_orbit_count']}] "
                f"root_lp={status}",
                flush=True,
            )

    counts = Counter(record["root_lp"]["status"] for record in records)
    payload = {
        "schema_version": "horizonmath.class-profile-lp-census.v1",
        "class_index": int(structural["input"]["class_index"]),
        "inputs": {
            "structural_manifest": {
                "path": str(args.structural_manifest),
                "sha256": sha256_file(args.structural_manifest),
            },
            "root_farkas_manifest": {
                "path": str(args.root_farkas_manifest),
                "sha256": sha256_file(args.root_farkas_manifest),
            },
            "root_verification_manifest": {
                "path": str(args.root_verification_manifest),
                "sha256": sha256_file(args.root_verification_manifest),
            },
            "veripb_wheel_sha256": verification["verifier"]["wheel_sha256"],
        },
        "candidate_partition": {
            "orbit_count": structural["candidate_minimum_point_sets"]["orbit_count"],
            "partition_sha256": structural["candidate_minimum_point_sets"][
                "partition_sha256"
            ],
            "verified_root_pruned_orbits": pruned,
            "retained_orbits": retained,
        },
        "exact_minimum_sets": {
            "orbit_count": exact_sets["orbit_count"],
            "raw_surviving_set_count": exact_sets["raw_surviving_set_count"],
            "orbits_by_size": exact_sets["orbits_by_size"],
            "partition_sha256": exact_sets["partition_sha256"],
            "accounting": exact_sets["accounting"],
        },
        "extension_degree_profiles": {
            "profile_orbit_count": profiles["profile_orbit_count"],
            "raw_profile_count_before_symmetry": profiles[
                "raw_profile_count_before_symmetry"
            ],
            "profile_index_sha256": profiles["profile_index_sha256"],
            "accounting": profiles["accounting"],
        },
        "root_lp_status_counts": dict(sorted(counts.items())),
        "profiles": records,
        "status": "ENUMERATED_AND_LP_SCREENED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, payload)
    print(
        json.dumps(
            {
                "class_index": payload["class_index"],
                "verified_root_pruned": len(pruned),
                "retained_candidate_orbits": len(retained),
                "exact_minimum_set_orbits": exact_sets["orbit_count"],
                "profile_orbits": profiles["profile_orbit_count"],
                "root_lp_status_counts": payload["root_lp_status_counts"],
                "output": str(args.output),
                "sha256": sha256_file(args.output),
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
