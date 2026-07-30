"""Deterministic point-subset orbits under a complete automorphism group."""

from __future__ import annotations

import itertools
import math
from typing import Any

from horizonlink.automorphisms import Permutation
from horizonlink.canonical import compact_json_bytes, sha256_bytes


def permute_subset(
    subset: tuple[int, ...], permutation: Permutation
) -> tuple[int, ...]:
    return tuple(sorted(permutation[point] for point in subset))


def compute_subset_orbits(
    point_labels: tuple[int, ...],
    group: tuple[Permutation, ...],
    subset_size: int,
) -> dict[str, Any]:
    if not 1 <= subset_size <= len(point_labels):
        raise ValueError("subset size must be between 1 and the point count")
    if not group:
        raise ValueError("group cannot be empty")

    universe = tuple(itertools.combinations(point_labels, subset_size))
    universe_set = set(universe)
    remaining = set(universe)
    orbit_records = []
    all_members: list[tuple[int, ...]] = []
    while remaining:
        representative = min(remaining)
        members = tuple(
            sorted(
                {
                    permute_subset(representative, permutation)
                    for permutation in group
                }
            )
        )
        if not set(members) <= universe_set:
            raise AssertionError("group action left the subset universe")
        stabilizer_order = sum(
            permute_subset(representative, permutation) == representative
            for permutation in group
        )
        orbit_id = f"orbit{len(orbit_records):03d}"
        orbit_records.append(
            {
                "id": orbit_id,
                "representative": list(representative),
                "size": len(members),
                "stabilizer_order": stabilizer_order,
                "orbit_stabilizer_check": (
                    len(members) * stabilizer_order == len(group)
                ),
                "members": [list(member) for member in members],
            }
        )
        all_members.extend(members)
        remaining.difference_update(members)

    expected = math.comb(len(point_labels), subset_size)
    partition_payload = [record["members"] for record in orbit_records]
    return {
        "algorithm": "lexicographic-full-group-action-v1",
        "subset_size": subset_size,
        "universe_count": expected,
        "orbit_count": len(orbit_records),
        "member_count": len(all_members),
        "orbit_sizes": [record["size"] for record in orbit_records],
        "representatives": [
            record["representative"] for record in orbit_records
        ],
        "partition_sha256": sha256_bytes(compact_json_bytes(partition_payload)),
        "orbits": orbit_records,
        "accounting": {
            "all_candidates_accounted_for": (
                len(all_members) == expected and set(all_members) == universe_set
            ),
            "members_unique": len(all_members) == len(set(all_members)),
            "all_orbit_stabilizer_checks_pass": all(
                record["orbit_stabilizer_check"] for record in orbit_records
            ),
            "unaccounted_candidates": [
                list(member) for member in sorted(universe_set - set(all_members))
            ],
            "duplicate_member_count": len(all_members) - len(set(all_members)),
        },
    }
