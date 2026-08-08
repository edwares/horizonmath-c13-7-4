#!/usr/bin/env python3
"""Independently audit a class-wide profile proof cover and record closure."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from horizonlink.canonical import compact_json_bytes, sha256_file, write_json
from horizonlink.farkas import _render_verifier_opb
from horizonlink.pb import build_corrected_formula, canonical_formula_sha256
from horizonlink.profiles import (
    compute_exact_minimum_set_orbits,
    compute_extension_degree_profiles,
    degree_budget,
)


EASY_SCHEMA = "horizonmath.profile-cut-farkas-corpus.v1"
HARD_SCHEMA = "horizonmath.residual-pair-split-farkas-corpus.v1"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def resolve_artifact(directory: Path, relative_path: str) -> Path:
    direct = directory / relative_path
    if direct.exists():
        return direct
    legacy = directory / "instances" / relative_path
    if legacy.exists():
        return legacy
    raise FileNotFoundError(relative_path)


def audit_root_verification(
    farkas_path: Path,
    verification_path: Path,
) -> tuple[dict[str, Any], list[int]]:
    farkas = read_json(farkas_path)
    verification = read_json(verification_path)
    instances = verification.get("instances", [])
    if (
        farkas.get("status") != "PROOF_GENERATED"
        or verification.get("status") != "VERIFIED_UNSAT"
        or verification.get("all_verified_unsat") is not True
        or verification.get("instance_count") != len(instances)
        or verification.get("status_counts")
        != {"VERIFIED_UNSAT": len(instances)}
        or verification.get("farkas_corpus_manifest_sha256")
        != sha256_file(farkas_path)
    ):
        raise ValueError("root Farkas verification failed top-level audit")
    proof_orbits = sorted(int(row["orbit_index"]) for row in farkas["instances"])
    verified_orbits = sorted(
        int(row["orbit_index"])
        for row in instances
        if row.get("status") == "VERIFIED_UNSAT"
    )
    if proof_orbits != verified_orbits or len(proof_orbits) != len(set(proof_orbits)):
        raise ValueError("root proof and verification orbit coverage differ")
    for row in instances:
        log_record = row["log"]
        log_path = verification_path.parent / log_record["path"]
        if sha256_file(log_path) != log_record["sha256"]:
            raise ValueError(f"root verification-log hash mismatch: {log_path}")
        log = read_json(log_path)
        if (
            log.get("status") != "VERIFIED_UNSAT"
            or log.get("exit_code") != 0
            or log.get("success_marker_present") is not True
            or log.get("unjustified_assumptions_warning_present") is not False
            or not all(log.get("hash_checks", {}).values())
        ):
            raise ValueError(f"root verification log failed audit: {log_path}")
    return verification, verified_orbits


def audit_profile_source(
    proof_directory: Path,
    verification_directory: Path,
    *,
    class_index: int,
    structural_sha256: str,
    profile_census_sha256: str,
    cut_census_sha256: str,
    profile_by_index: dict[int, dict[str, Any]],
    point_labels: tuple[int, ...],
    link_blocks: tuple[tuple[int, ...], ...],
) -> tuple[dict[str, Any], list[dict[str, Any]], tuple[str, str]]:
    proof_path = proof_directory / "corpus.manifest.json"
    verification_path = verification_directory / "verification.manifest.json"
    proof = read_json(proof_path)
    verification = read_json(verification_path)
    schema = proof.get("schema_version")
    if schema not in {EASY_SCHEMA, HARD_SCHEMA}:
        raise ValueError(f"unexpected proof schema: {proof_path}")
    if (
        proof.get("class_index") != class_index
        or proof.get("target_candidate_orbit") is not None
        or proof.get("profile_census_sha256") != profile_census_sha256
        or proof.get("status") != "PROOFS_GENERATED_NOT_YET_VERIFIED"
        or proof.get("instance_count") != len(proof.get("instances", []))
    ):
        raise ValueError(f"profile proof provenance failed audit: {proof_path}")
    if schema == EASY_SCHEMA and proof.get("cut_census_sha256") != cut_census_sha256:
        raise ValueError(f"easy proof cut-census hash mismatch: {proof_path}")
    if schema == HARD_SCHEMA and proof.get("structural_manifest_sha256") != structural_sha256:
        raise ValueError(f"hard proof structural hash mismatch: {proof_path}")

    verification_instances = verification.get("instances", [])
    if (
        verification.get("status") != "VERIFIED_UNSAT"
        or verification.get("all_verified_unsat") is not True
        or verification.get("class_index") != class_index
        or verification.get("target_candidate_orbit") is not None
        or verification.get("instance_count") != len(verification_instances)
        or verification.get("status_counts")
        != {"VERIFIED_UNSAT": len(verification_instances)}
        or verification.get("proof_corpus_manifest_sha256") != sha256_file(proof_path)
    ):
        raise ValueError(f"profile verification failed top-level audit: {verification_path}")
    verified_by_index = {int(row["index"]): row for row in verification_instances}
    if len(verified_by_index) != len(verification_instances):
        raise ValueError(f"duplicate verification index: {verification_path}")

    audited: list[dict[str, Any]] = []
    seen: set[int] = set()
    for instance in proof["instances"]:
        index = int(instance["index"])
        if index in seen or index not in profile_by_index:
            raise ValueError(f"duplicate or unknown proof index {index}: {proof_path}")
        seen.add(index)
        profile = profile_by_index[index]
        if (
            int(instance["case_id"]) != int(profile["case_id"])
            or int(instance["profile_id"]) != int(profile["profile_id"])
        ):
            raise ValueError(f"profile identity mismatch at index {index}")
        built = build_corrected_formula(
            point_labels, link_blocks, profile["extension_degrees"]
        )
        expected_formula = _render_verifier_opb(
            built["rows"],
            variable_count=int(built["metadata"]["variables"]),
            class_index=class_index,
            orbit_index=None,
        )
        expected_formula_sha256 = hashlib.sha256(expected_formula).hexdigest()
        if instance["formula"]["sha256"] != expected_formula_sha256:
            raise ValueError(f"rebuilt verifier formula mismatch at index {index}")
        for key in ("formula", "proof", "metadata"):
            artifact = instance[key]
            artifact_path = resolve_artifact(proof_directory, artifact["path"])
            if sha256_file(artifact_path) != artifact["sha256"]:
                raise ValueError(f"{key} hash mismatch at index {index}")
        if instance.get("tree") is not None:
            tree_record = instance["tree"]
            tree_path = resolve_artifact(proof_directory, tree_record["path"])
            if sha256_file(tree_path) != tree_record["sha256"]:
                raise ValueError(f"split-tree hash mismatch at index {index}")
            tree = read_json(tree_path)
            if (
                tree.get("complete") is not True
                or int(tree["node_count"]) != int(tree_record["nodes"])
                or int(tree["leaf_count"]) != int(tree_record["leaves"])
            ):
                raise ValueError(f"split-tree accounting mismatch at index {index}")

        verified = verified_by_index.get(index)
        if verified is None or verified.get("status") != "VERIFIED_UNSAT":
            raise ValueError(f"proof index {index} lacks verified UNSAT replay")
        log_record = verified["log"]
        log_path = verification_directory / log_record["path"]
        if sha256_file(log_path) != log_record["sha256"]:
            raise ValueError(f"verification-log hash mismatch at index {index}")
        log = read_json(log_path)
        if (
            log.get("status") != "VERIFIED_UNSAT"
            or log.get("exit_code") != 0
            or log.get("success_marker_present") is not True
            or log.get("unjustified_assumptions_warning_present") is not False
            or not all(log.get("hash_checks", {}).values())
            or log.get("formula_sha256") != instance["formula"]["sha256"]
            or log.get("proof_sha256") != instance["proof"]["sha256"]
        ):
            raise ValueError(f"verification log failed audit at index {index}")
        audited.append(
            {
                "index": index,
                "method": instance["method"],
                "cut_count": instance.get("cut_count"),
                "tree": instance.get("tree"),
            }
        )
    if set(verified_by_index) != seen:
        raise ValueError(f"proof/verification index sets differ: {proof_path}")
    verifier = verification.get("verifier", {})
    fingerprint = (
        str(verifier.get("wheel_sha256")),
        str(verifier.get("required_flag")),
    )
    source_record = {
        "schema_version": schema,
        "proof_manifest": {
            "path": proof_path.as_posix(),
            "sha256": sha256_file(proof_path),
        },
        "verification_manifest": {
            "path": verification_path.as_posix(),
            "sha256": sha256_file(verification_path),
        },
        "verified_indices": sorted(seen),
    }
    return source_record, audited, fingerprint


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("structural_manifest", type=Path)
    parser.add_argument("root_farkas_manifest", type=Path)
    parser.add_argument("root_verification_manifest", type=Path)
    parser.add_argument("profile_census", type=Path)
    parser.add_argument("cut_census", type=Path)
    parser.add_argument("--proof-corpus", type=Path, action="append", required=True)
    parser.add_argument("--verification", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(args.proof_corpus) != len(args.verification):
        raise ValueError("proof-corpus and verification arguments must pair one-to-one")
    if args.output.exists():
        raise ValueError("output path already exists")

    structural = read_json(args.structural_manifest)
    census = read_json(args.profile_census)
    cuts = read_json(args.cut_census)
    structural_sha256 = sha256_file(args.structural_manifest)
    census_sha256 = sha256_file(args.profile_census)
    cuts_sha256 = sha256_file(args.cut_census)
    if (
        structural.get("status") not in {"ENUMERATED", "FORMULAS_GENERATED"}
        or structural.get("structural_audit", {}).get("all_checks_passed") is not True
    ):
        raise ValueError("structural manifest failed audit gate")
    class_index = int(structural["input"]["class_index"])
    if census.get("class_index") != class_index:
        raise ValueError("profile census class mismatch")

    root_verification, root_orbits = audit_root_verification(
        args.root_farkas_manifest, args.root_verification_manifest
    )
    candidates = structural["candidate_minimum_point_sets"]
    orbit_count = int(candidates["orbit_count"])
    candidate_accounting = candidates.get("accounting", {})
    if (
        len(candidates.get("orbits", [])) != orbit_count
        or candidate_accounting.get("all_candidates_accounted_for") is not True
        or candidate_accounting.get("all_orbit_stabilizer_checks_pass") is not True
        or candidate_accounting.get("duplicate_member_count") != 0
    ):
        raise ValueError("candidate-orbit partition failed accounting audit")
    retained = sorted(set(range(orbit_count)) - set(root_orbits))
    partition = census.get("candidate_partition", {})
    if (
        partition.get("orbit_count") != orbit_count
        or partition.get("partition_sha256") != candidates.get("partition_sha256")
        or partition.get("verified_root_pruned_orbits") != root_orbits
        or partition.get("retained_orbits") != retained
    ):
        raise ValueError("profile census candidate partition differs from root verification")

    normalized = structural["input"]["normalized_document"]
    point_labels = tuple(int(value) for value in normalized["point_labels"])
    link_blocks = tuple(tuple(int(value) for value in block) for block in normalized["blocks"])
    group = tuple(
        tuple(int(value) for value in permutation)
        for permutation in structural["automorphism_group"]["permutations"]
    )
    exact_sets = compute_exact_minimum_set_orbits(point_labels, group, candidates, retained)
    observed_exact = census.get("exact_minimum_sets", {})
    for key in (
        "orbit_count",
        "raw_surviving_set_count",
        "orbits_by_size",
        "partition_sha256",
        "accounting",
    ):
        if observed_exact.get(key) != exact_sets.get(key):
            raise ValueError(f"exact-minimum-set recomputation differs at {key}")
    budget = degree_budget(point_labels, link_blocks)
    recomputed_profiles = compute_extension_degree_profiles(
        point_labels,
        group,
        exact_sets,
        range(int(exact_sets["orbit_count"])),
        budget["minimum_extension_degrees"],
        int(budget["derivation"]["excess"]),
    )
    observed_profile_meta = census.get("extension_degree_profiles", {})
    for key in (
        "profile_orbit_count",
        "raw_profile_count_before_symmetry",
        "profile_index_sha256",
        "accounting",
    ):
        if observed_profile_meta.get(key) != recomputed_profiles.get(key):
            raise ValueError(f"degree-profile recomputation differs at {key}")
    observed_profiles = census.get("profiles", [])
    if len(observed_profiles) != int(recomputed_profiles["profile_orbit_count"]):
        raise ValueError("profile census length mismatch")
    profile_by_index: dict[int, dict[str, Any]] = {}
    for index, (observed, recomputed) in enumerate(
        zip(observed_profiles, recomputed_profiles["profiles"], strict=True)
    ):
        if (
            int(observed["index"]) != index
            or int(observed["case_id"]) != int(recomputed["case_id"])
            or int(observed["profile_id"]) != int(recomputed["profile_id"])
            or int(observed["profile_orbit_size"]) != int(recomputed["orbit_size"])
            or tuple(observed["excess_profile"]) != tuple(recomputed["representative"])
            or tuple(observed["extension_degrees"])
            != tuple(recomputed["extension_degrees"])
        ):
            raise ValueError(f"recomputed profile differs at index {index}")
        built = build_corrected_formula(point_labels, link_blocks, observed["extension_degrees"])
        canonical_hash = canonical_formula_sha256(
            built["rows"], variable_count=int(built["metadata"]["variables"])
        )
        if canonical_hash != observed["formula"]["canonical_formula_sha256"]:
            raise ValueError(f"canonical formula hash mismatch at index {index}")
        profile_by_index[index] = observed

    feasible_indices = {
        int(row["index"])
        for row in observed_profiles
        if row["root_lp"]["status"] == "LP_FEASIBLE"
    }
    cut_instances = cuts.get("instances", [])
    cut_by_index = {int(row["index"]): row for row in cut_instances}
    if (
        cuts.get("class_index") != class_index
        or cuts.get("profile_census_sha256") != census_sha256
        or cuts.get("structural_manifest_sha256") != structural_sha256
        or len(cut_by_index) != len(cut_instances)
        or set(cut_by_index) != feasible_indices
        or cuts.get("coverage", {}).get("indices_exactly_match") is not True
        or cuts.get("coverage", {}).get("indices_unique") is not True
    ):
        raise ValueError("pair-cut census failed coverage/provenance audit")

    expected_method: dict[int, str] = {}
    for index, row in profile_by_index.items():
        if row["root_lp"]["status"] == "SOLVER_UNSAT":
            expected_method[index] = "DIRECT_ROOT_LP_FARKAS"
        else:
            status = cut_by_index[index]["status"]
            if status == "LP_UNSAT_AFTER_INTEGRALITY_CUTS":
                expected_method[index] = "INTEGRALITY_PAIR_CUTS_THEN_ROOT_LP_FARKAS"
            elif status == "NO_FORCED_PAIR_CUT":
                expected_method[index] = "ONE_SIDED_PAIR_CG_THEN_EXACT_LP_SPLIT_FARKAS"
            else:
                raise ValueError(f"unclosed cut-census status at index {index}: {status}")

    sources = []
    audited_instances: list[dict[str, Any]] = []
    verifier_fingerprints = {
        (
            str(root_verification.get("verifier", {}).get("wheel_sha256")),
            str(root_verification.get("verifier", {}).get("required_flag")),
        )
    }
    for proof_directory, verification_directory in zip(
        args.proof_corpus, args.verification, strict=True
    ):
        source, instances, fingerprint = audit_profile_source(
            proof_directory,
            verification_directory,
            class_index=class_index,
            structural_sha256=structural_sha256,
            profile_census_sha256=census_sha256,
            cut_census_sha256=cuts_sha256,
            profile_by_index=profile_by_index,
            point_labels=point_labels,
            link_blocks=link_blocks,
        )
        sources.append(source)
        audited_instances.extend(instances)
        verifier_fingerprints.add(fingerprint)
    audited_by_index = {int(row["index"]): row for row in audited_instances}
    expected_indices = set(profile_by_index)
    if len(audited_by_index) != len(audited_instances) or set(audited_by_index) != expected_indices:
        observed = set(audited_by_index)
        raise ValueError(
            "verified profile proofs are not an exact cover: "
            f"missing={sorted(expected_indices-observed)} "
            f"unexpected={sorted(observed-expected_indices)}"
        )
    for index, expected in expected_method.items():
        if audited_by_index[index]["method"] != expected:
            raise ValueError(
                f"proof method mismatch at index {index}: "
                f"{audited_by_index[index]['method']} != {expected}"
            )
    if len(verifier_fingerprints) != 1:
        raise ValueError(f"verifier fingerprint mismatch: {sorted(verifier_fingerprints)}")
    verifier_wheel_sha256, required_flag = next(iter(verifier_fingerprints))
    if required_flag != "--requireUnsat":
        raise ValueError("formal sources were not uniformly checked with --requireUnsat")

    method_counts = Counter(row["method"] for row in audited_instances)
    split_trees = {
        str(index): {
            "cut_count": audited_by_index[index]["cut_count"],
            "nodes": audited_by_index[index]["tree"]["nodes"],
            "leaves": audited_by_index[index]["tree"]["leaves"],
            "sha256": audited_by_index[index]["tree"]["sha256"],
        }
        for index, method in sorted(expected_method.items())
        if method == "ONE_SIDED_PAIR_CG_THEN_EXACT_LP_SPLIT_FARKAS"
    }
    verified_indices = sorted(audited_by_index)
    output = {
        "schema_version": "horizonmath.class-profile-formal-closure.v1",
        "status": f"VERIFIED_UNSAT_CLASS_{class_index}",
        "class_index": class_index,
        "inputs": {
            "structural_manifest": {
                "path": args.structural_manifest.as_posix(),
                "sha256": structural_sha256,
            },
            "profile_census": {
                "path": args.profile_census.as_posix(),
                "sha256": census_sha256,
            },
            "cut_census": {
                "path": args.cut_census.as_posix(),
                "sha256": cuts_sha256,
            },
        },
        "candidate_orbit_partition": {
            "orbit_count": orbit_count,
            "partition_sha256": candidates["partition_sha256"],
            "verified_root_pruned_orbits": root_orbits,
            "retained_orbits": retained,
            "exact_candidate_orbit_cover": sorted(set(root_orbits) | set(retained))
            == list(range(orbit_count)),
        },
        "exact_minimum_sets": {
            "orbit_count": exact_sets["orbit_count"],
            "raw_surviving_set_count": exact_sets["raw_surviving_set_count"],
            "partition_sha256": exact_sets["partition_sha256"],
            "accounting": exact_sets["accounting"],
        },
        "profile_cover": {
            "profile_count": len(profile_by_index),
            "verified_profile_count": len(verified_indices),
            "verified_indices_sha256": hashlib.sha256(
                compact_json_bytes(verified_indices)
            ).hexdigest(),
            "method_counts": dict(sorted(method_counts.items())),
            "split_trees": split_trees,
            "sources": sources,
            "exact_cover": verified_indices == list(range(len(profile_by_index))),
        },
        "root_verification": {
            "farkas_manifest": {
                "path": args.root_farkas_manifest.as_posix(),
                "sha256": sha256_file(args.root_farkas_manifest),
            },
            "verification_manifest": {
                "path": args.root_verification_manifest.as_posix(),
                "sha256": sha256_file(args.root_verification_manifest),
            },
        },
        "verifier": {
            "wheel_sha256": verifier_wheel_sha256,
            "required_flag": required_flag,
        },
        "coverage_audit": {
            "candidate_orbits_exact": sorted(set(root_orbits) | set(retained))
            == list(range(orbit_count)),
            "exact_minimum_sets_recomputed": True,
            "degree_profiles_recomputed": True,
            "profile_proofs_exact": verified_indices == list(range(len(profile_by_index))),
            "all_checks_passed": True,
        },
        "logical_scope": {
            "class_formally_eliminated": True,
            "C_13_7_4_equals_30_claimed": False,
            "reason": (
                "The verified root proofs eliminate the pruned candidate 4-set orbits; "
                "the retained candidate orbits are independently re-expanded into exact "
                "minimum-set and degree-profile orbits, and every resulting profile has "
                "an exact pinned-VeriPB UNSAT proof."
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, output)
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "sha256": sha256_file(args.output),
                "status": output["status"],
                "candidate_orbits": orbit_count,
                "profiles": len(verified_indices),
                "method_counts": output["profile_cover"]["method_counts"],
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
