"""Exact minimum-point sets and extension-degree profiles.

The functions in this module contain no class-52 constants.  A prior screening
stage supplies the candidate minimum-point orbits that remain possible.  This
module then expands that result into exact minimum-point-set orbits and exact
degree-profile orbits under the complete link automorphism group.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable
from typing import Any

from horizonlink.automorphisms import Permutation
from horizonlink.canonical import compact_json_bytes, sha256_bytes
from horizonlink.orbits import permute_subset


Profile = tuple[int, ...]


def _permutation_cycle_lengths(
    permutation: Permutation,
) -> tuple[int, ...]:
    seen: set[int] = set()
    lengths: list[int] = []
    for start in range(len(permutation)):
        if start in seen:
            continue
        point = start
        length = 0
        while point not in seen:
            seen.add(point)
            length += 1
            point = permutation[point]
        lengths.append(length)
    return tuple(sorted(lengths))


def _cycle_type_id(cycle_lengths: tuple[int, ...]) -> str:
    counts: dict[int, int] = {}
    for length in cycle_lengths:
        counts[length] = counts.get(length, 0) + 1
    return "*".join(
        f"{length}^{counts[length]}" for length in sorted(counts)
    )


def _fixed_weak_profiles_by_minimum_set_size(
    cycle_lengths: tuple[int, ...],
    *,
    total_excess: int,
    point_count: int,
) -> dict[int, int]:
    """Count fixed weak profiles by zero-coordinate count."""

    states: dict[tuple[int, int], int] = {(0, 0): 1}
    for cycle_length in cycle_lengths:
        updated: dict[tuple[int, int], int] = {}
        for (current_total, support_size), count in states.items():
            maximum_value = (
                total_excess - current_total
            ) // cycle_length
            for value in range(maximum_value + 1):
                key = (
                    current_total + value * cycle_length,
                    support_size + (cycle_length if value else 0),
                )
                updated[key] = updated.get(key, 0) + count
        states = updated

    fixed: dict[int, int] = {}
    for (current_total, support_size), count in states.items():
        if current_total != total_excess:
            continue
        minimum_set_size = point_count - support_size
        fixed[minimum_set_size] = (
            fixed.get(minimum_set_size, 0) + count
        )
    return fixed


def compute_unscreened_degree_profile_orbit_census(
    group: tuple[Permutation, ...],
    *,
    total_excess: int,
    point_count: int,
) -> dict[str, Any]:
    """Count all unscreened degree-profile orbits exactly by Burnside.

    A weak profile assigns nonnegative integral excess to every point. Its
    zero coordinates are exactly the minimum-degree points. Counting weak
    profiles of total ``total_excess`` under the full link automorphism group
    therefore counts the complete degree-budget search space before any
    candidate, case, LP, or solver screening.
    """

    if total_excess < 0:
        raise ValueError("total excess must be nonnegative")
    if point_count < 1:
        raise ValueError("point count must be positive")
    if not group:
        raise ValueError("automorphism group cannot be empty")
    if any(
        len(permutation) != point_count
        or set(permutation) != set(range(point_count))
        for permutation in group
    ):
        raise ValueError(
            "every group element must be a point permutation"
        )

    fixed_sums: dict[int, int] = {}
    cycle_type_histogram: dict[str, int] = {}
    for permutation in group:
        cycle_lengths = _permutation_cycle_lengths(permutation)
        cycle_type = _cycle_type_id(cycle_lengths)
        cycle_type_histogram[cycle_type] = (
            cycle_type_histogram.get(cycle_type, 0) + 1
        )
        fixed = _fixed_weak_profiles_by_minimum_set_size(
            cycle_lengths,
            total_excess=total_excess,
            point_count=point_count,
        )
        for minimum_set_size, count in fixed.items():
            fixed_sums[minimum_set_size] = (
                fixed_sums.get(minimum_set_size, 0) + count
            )

    group_order = len(group)
    divisibility = {
        str(size): fixed_sums[size] % group_order == 0
        for size in sorted(fixed_sums)
    }
    if not all(divisibility.values()):
        raise AssertionError(
            "Burnside fixed-profile sum is not divisible by group order"
        )
    orbit_counts = {
        str(size): fixed_sums[size] // group_order
        for size in sorted(fixed_sums)
    }

    raw_counts: dict[str, int] = {}
    if total_excess == 0:
        raw_counts[str(point_count)] = 1
    else:
        for support_size in range(
            1, min(point_count, total_excess) + 1
        ):
            minimum_set_size = point_count - support_size
            raw_counts[str(minimum_set_size)] = (
                math.comb(point_count, support_size)
                * math.comb(total_excess - 1, support_size - 1)
            )
    raw_counts = {
        key: raw_counts[key]
        for key in sorted(raw_counts, key=int)
    }
    raw_total = math.comb(
        total_excess + point_count - 1,
        point_count - 1,
    )
    profile_orbit_count = sum(orbit_counts.values())
    return {
        "algorithm": (
            "burnside-weak-compositions-by-permutation-cycle-type-v1"
        ),
        "interpretation": (
            "Exact symmetry-reduced count of all nonnegative integral "
            "degree-excess vectors before any screening. No profile "
            "representatives, formulas, LPs, or solver runs are generated."
        ),
        "point_count": point_count,
        "total_excess": total_excess,
        "group_order": group_order,
        "raw_profile_count_before_symmetry": raw_total,
        "raw_profiles_by_minimum_set_size": raw_counts,
        "profile_orbit_count": profile_orbit_count,
        "profile_orbits_by_minimum_set_size": orbit_counts,
        "burnside_audit": {
            "cycle_type_histogram": dict(
                sorted(cycle_type_histogram.items())
            ),
            "fixed_profile_sum_by_minimum_set_size": {
                str(size): fixed_sums[size]
                for size in sorted(fixed_sums)
            },
            "fixed_sums_divisible_by_group_order": divisibility,
            "all_divisibility_checks_pass": all(
                divisibility.values()
            ),
            "raw_counts_sum_to_weak_composition_count": (
                sum(raw_counts.values()) == raw_total
            ),
            "orbit_counts_sum_to_total": (
                sum(orbit_counts.values()) == profile_orbit_count
            ),
        },
        "scope": {
            "counts_enumerated": True,
            "profile_representatives_generated": False,
            "candidate_screening_run": False,
            "root_lp_run": False,
            "solver_run": False,
            "formulas_generated": False,
            "proofs_generated": False,
            "verifier_run": False,
        },
    }


def degree_budget(
    point_labels: tuple[int, ...],
    link_blocks: tuple[tuple[int, ...], ...],
    *,
    target_full_point_degree: int = 15,
    extension_block_count: int = 14,
    extension_block_size: int = 7,
) -> dict[str, Any]:
    """Compute the exact excess above point-degree lower bounds."""

    link_point_degrees = tuple(
        sum(point in block for block in link_blocks) for point in point_labels
    )
    minimum_extension_degrees = tuple(
        target_full_point_degree - degree for degree in link_point_degrees
    )
    if any(degree < 0 for degree in minimum_extension_degrees):
        raise ValueError("a link point degree exceeds the target full degree")
    extension_degree_sum = extension_block_count * extension_block_size
    minimum_degree_sum = sum(minimum_extension_degrees)
    excess = extension_degree_sum - minimum_degree_sum
    if excess < 0:
        raise ValueError("minimum extension degrees exceed the degree budget")

    minimum_point_lower_bound = max(0, len(point_labels) - excess)
    return {
        "derivation": {
            "target_full_point_degree": target_full_point_degree,
            "extension_block_count": extension_block_count,
            "extension_block_size": extension_block_size,
            "extension_degree_sum": extension_degree_sum,
            "minimum_extension_degree_sum": minimum_degree_sum,
            "excess": excess,
            "minimum_point_lower_bound": minimum_point_lower_bound,
            "minimum_point_lower_bound_reason": (
                "Every nonminimum point consumes at least one integral unit of "
                "excess, so at most `excess` points are nonminimum."
            ),
        },
        "link_point_degrees": list(link_point_degrees),
        "minimum_extension_degrees": list(minimum_extension_degrees),
    }


def _screened_orbit_index(
    subset_orbits: dict[str, Any],
) -> dict[tuple[int, ...], int]:
    result: dict[tuple[int, ...], int] = {}
    for orbit_index, orbit in enumerate(subset_orbits["orbits"]):
        for raw_member in orbit["members"]:
            member = tuple(raw_member)
            prior = result.setdefault(member, orbit_index)
            if prior != orbit_index:
                raise AssertionError(
                    f"candidate subset {member} occurs in two orbits"
                )
    if len(result) != subset_orbits["universe_count"]:
        raise AssertionError("candidate orbit partition is incomplete")
    return result


def _subset_orbit(
    representative: tuple[int, ...],
    group: tuple[Permutation, ...],
) -> tuple[tuple[int, ...], ...]:
    return tuple(
        sorted(
            {
                permute_subset(representative, permutation)
                for permutation in group
            }
        )
    )


def _stabilizer(
    subset: tuple[int, ...],
    group: tuple[Permutation, ...],
) -> tuple[Permutation, ...]:
    return tuple(
        permutation
        for permutation in group
        if permute_subset(subset, permutation) == subset
    )


def compute_exact_minimum_set_orbits(
    point_labels: tuple[int, ...],
    group: tuple[Permutation, ...],
    candidate_subset_orbits: dict[str, Any],
    retained_candidate_orbit_indices: Iterable[int],
) -> dict[str, Any]:
    """Enumerate every exact minimum-point-set orbit.

    A set can be the complete set of minimum-degree points only if every one of
    its base-size subsets survived the earlier candidate screen.
    """

    base_size = int(candidate_subset_orbits["subset_size"])
    if base_size < 1:
        raise ValueError("candidate subset size must be positive")
    retained = tuple(sorted(set(int(index) for index in retained_candidate_orbit_indices)))
    if not retained:
        return {
            "algorithm": "all-base-subsets-retained-full-group-action-v1",
            "base_subset_size": base_size,
            "retained_candidate_orbit_indices": [],
            "raw_surviving_set_count": 0,
            "raw_surviving_sets_by_size": {},
            "orbit_count": 0,
            "orbits_by_size": {},
            "cases": [],
            "accounting": {
                "all_surviving_sets_accounted_for": True,
                "case_ids_consecutive": True,
            },
        }
    orbit_count = int(candidate_subset_orbits["orbit_count"])
    if retained[0] < 0 or retained[-1] >= orbit_count:
        raise ValueError("retained candidate orbit index is out of range")

    subset_to_orbit = _screened_orbit_index(candidate_subset_orbits)
    retained_set = set(retained)
    cases: list[dict[str, Any]] = []
    all_members: list[tuple[int, ...]] = []
    raw_by_size: dict[str, int] = {}
    orbit_counts_by_size: dict[str, int] = {}

    for size in range(base_size, len(point_labels) + 1):
        survivors = {
            subset
            for subset in itertools.combinations(point_labels, size)
            if all(
                subset_to_orbit[base_subset] in retained_set
                for base_subset in itertools.combinations(subset, base_size)
            )
        }
        raw_by_size[str(size)] = len(survivors)
        remaining = set(survivors)
        size_orbit_count = 0
        while remaining:
            representative = min(remaining)
            members = _subset_orbit(representative, group)
            if not set(members) <= survivors:
                raise AssertionError(
                    "minimum-set survivor family is not group invariant"
                )
            case_id = len(cases)
            source_candidate_orbit = (
                subset_to_orbit[representative] if size == base_size else None
            )
            case_stabilizer = _stabilizer(representative, group)
            cases.append(
                {
                    "case_id": case_id,
                    "id": f"case{case_id:03d}",
                    "size": size,
                    "representative": list(representative),
                    "source_candidate_orbit_index": source_candidate_orbit,
                    "orbit_size": len(members),
                    "stabilizer_order": len(case_stabilizer),
                    "orbit_stabilizer_check": (
                        len(members) * len(case_stabilizer) == len(group)
                    ),
                    "members": [list(member) for member in members],
                }
            )
            all_members.extend(members)
            remaining.difference_update(members)
            size_orbit_count += 1
        orbit_counts_by_size[str(size)] = size_orbit_count

    nonzero_raw = {
        size: count for size, count in raw_by_size.items() if count != 0
    }
    nonzero_orbits = {
        size: count
        for size, count in orbit_counts_by_size.items()
        if count != 0
    }
    partition_payload = [case["members"] for case in cases]
    return {
        "algorithm": "all-base-subsets-retained-full-group-action-v1",
        "base_subset_size": base_size,
        "retained_candidate_orbit_indices": list(retained),
        "raw_surviving_set_count": sum(raw_by_size.values()),
        "raw_surviving_sets_by_size": nonzero_raw,
        "orbit_count": len(cases),
        "orbits_by_size": nonzero_orbits,
        "partition_sha256": sha256_bytes(compact_json_bytes(partition_payload)),
        "cases": cases,
        "accounting": {
            "all_surviving_sets_accounted_for": (
                len(all_members) == sum(raw_by_size.values())
                and len(all_members) == len(set(all_members))
            ),
            "case_ids_consecutive": [
                case["case_id"] for case in cases
            ]
            == list(range(len(cases))),
            "all_orbit_stabilizer_checks_pass": all(
                case["orbit_stabilizer_check"] for case in cases
            ),
        },
    }


def positive_compositions(total: int, parts: int) -> Iterable[tuple[int, ...]]:
    """Yield lexicographically ordered positive compositions."""

    if total < 0 or parts < 0:
        raise ValueError("composition arguments must be nonnegative")
    if parts == 0:
        if total == 0:
            yield ()
        return
    if parts == 1:
        if total > 0:
            yield (total,)
        return
    if total < parts:
        return
    for cuts in itertools.combinations(range(1, total), parts - 1):
        boundaries = (0,) + cuts + (total,)
        yield tuple(
            boundaries[index + 1] - boundaries[index]
            for index in range(parts)
        )


def transform_profile(profile: Profile, permutation: Permutation) -> Profile:
    transformed = [0] * len(profile)
    for point, value in enumerate(profile):
        transformed[permutation[point]] = value
    return tuple(transformed)


def _profile_orbits_for_case(
    point_labels: tuple[int, ...],
    group: tuple[Permutation, ...],
    minimum_set: tuple[int, ...],
    excess: int,
) -> tuple[list[dict[str, Any]], int, int]:
    outside = tuple(point for point in point_labels if point not in minimum_set)
    case_stabilizer = _stabilizer(minimum_set, group)
    profiles: set[Profile] = set()
    for composition in positive_compositions(excess, len(outside)):
        profile = [0] * len(point_labels)
        for point, value in zip(outside, composition):
            profile[point] = value
        profiles.add(tuple(profile))
    raw_count = len(profiles)

    records = []
    while profiles:
        representative = min(profiles)
        members = tuple(
            sorted(
                {
                    transform_profile(representative, permutation)
                    for permutation in case_stabilizer
                }
            )
        )
        profile_id = len(records)
        profile_stabilizer_order = sum(
            transform_profile(representative, permutation) == representative
            for permutation in case_stabilizer
        )
        records.append(
            {
                "profile_id": profile_id,
                "representative": list(representative),
                "orbit_size": len(members),
                "profile_stabilizer_order": profile_stabilizer_order,
                "orbit_stabilizer_check": (
                    len(members) * profile_stabilizer_order
                    == len(case_stabilizer)
                ),
                "members": [list(member) for member in members],
            }
        )
        profiles.difference_update(members)
    return records, raw_count, len(case_stabilizer)


def compute_extension_degree_profiles(
    point_labels: tuple[int, ...],
    group: tuple[Permutation, ...],
    exact_minimum_sets: dict[str, Any],
    profile_case_ids: Iterable[int],
    minimum_extension_degrees: Iterable[int],
    excess: int,
) -> dict[str, Any]:
    """Enumerate exact degree profiles for every retained minimum-set case."""

    baseline = tuple(int(value) for value in minimum_extension_degrees)
    if len(baseline) != len(point_labels):
        raise ValueError("minimum extension degree vector has wrong length")
    case_by_id = {
        int(case["case_id"]): case for case in exact_minimum_sets["cases"]
    }
    selected_case_ids = tuple(sorted(set(int(value) for value in profile_case_ids)))
    if not set(selected_case_ids) <= set(case_by_id):
        raise ValueError("profile case id is not an exact minimum-set case")

    case_records = []
    flat_profiles = []
    raw_total = 0
    for case_id in selected_case_ids:
        case = case_by_id[case_id]
        minimum_set = tuple(case["representative"])
        records, raw_count, stabilizer_order = _profile_orbits_for_case(
            point_labels, group, minimum_set, excess
        )
        raw_total += raw_count
        for record in records:
            representative = tuple(record["representative"])
            record["id"] = (
                f"case{case_id:03d}/profile{record['profile_id']:03d}"
            )
            record["extension_degrees"] = [
                baseline[point] + representative[point]
                for point in point_labels
            ]
            record["extension_degree_sum"] = sum(
                record["extension_degrees"]
            )
            flat_profiles.append(
                {
                    "case_id": case_id,
                    **{
                        key: value
                        for key, value in record.items()
                        if key != "members"
                    },
                }
            )
        case_records.append(
            {
                "case_id": case_id,
                "minimum_set": list(minimum_set),
                "minimum_set_size": len(minimum_set),
                "case_stabilizer_order": stabilizer_order,
                "raw_positive_profile_count": raw_count,
                "profile_orbit_count": len(records),
                "profile_partition_sha256": sha256_bytes(
                    compact_json_bytes([record["members"] for record in records])
                ),
                "profiles": records,
                "accounting": {
                    "raw_profiles_accounted_for": sum(
                        record["orbit_size"] for record in records
                    )
                    == raw_count,
                    "all_orbit_stabilizer_checks_pass": all(
                        record["orbit_stabilizer_check"]
                        for record in records
                    ),
                },
            }
        )

    expected_extension_sum = sum(baseline) + excess
    return {
        "algorithm": (
            "positive-excess-compositions-stabilizer-orbits-lexicographic-v1"
        ),
        "excess": excess,
        "minimum_extension_degrees": list(baseline),
        "profile_case_ids": list(selected_case_ids),
        "raw_profile_count_before_symmetry": raw_total,
        "profile_orbit_count": len(flat_profiles),
        "case_count": len(case_records),
        "cases": case_records,
        "profiles": flat_profiles,
        "profile_index_sha256": sha256_bytes(
            compact_json_bytes(
                [
                    {
                        "case_id": row["case_id"],
                        "profile_id": row["profile_id"],
                        "representative": row["representative"],
                    }
                    for row in flat_profiles
                ]
            )
        ),
        "accounting": {
            "case_ids_unique": len(selected_case_ids)
            == len(set(selected_case_ids)),
            "profile_keys_unique": len(flat_profiles)
            == len(
                {
                    (row["case_id"], row["profile_id"])
                    for row in flat_profiles
                }
            ),
            "all_raw_profiles_accounted_for": all(
                case["accounting"]["raw_profiles_accounted_for"]
                for case in case_records
            ),
            "all_orbit_stabilizer_checks_pass": all(
                case["accounting"]["all_orbit_stabilizer_checks_pass"]
                for case in case_records
            ),
            "all_extension_degree_sums_exact": all(
                row["extension_degree_sum"] == expected_extension_sum
                for row in flat_profiles
            ),
        },
    }


def expected_raw_profile_count(excess: int, outside_points: int) -> int:
    """Closed-form check for the number of positive compositions."""

    if outside_points == 0:
        return 1 if excess == 0 else 0
    if excess < outside_points:
        return 0
    return math.comb(excess - 1, outside_points - 1)
