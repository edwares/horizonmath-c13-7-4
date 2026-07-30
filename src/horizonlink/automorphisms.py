"""Complete deterministic automorphism search for labeled link blocks."""

from __future__ import annotations

import itertools
from collections import Counter
from typing import Any

from horizonlink.canonical import compact_json_bytes, sha256_bytes


Permutation = tuple[int, ...]


def compose(left: Permutation, right: Permutation) -> Permutation:
    """Return left after right."""
    return tuple(left[right[point]] for point in range(len(right)))


def inverse(permutation: Permutation) -> Permutation:
    result = [0] * len(permutation)
    for point, image in enumerate(permutation):
        result[image] = point
    return tuple(result)


def permute_block(block: tuple[int, ...], permutation: Permutation) -> tuple[int, ...]:
    return tuple(sorted(permutation[point] for point in block))


def permutation_cycles(permutation: Permutation) -> list[list[int]]:
    seen: set[int] = set()
    cycles: list[list[int]] = []
    for start in range(len(permutation)):
        if start in seen:
            continue
        current = start
        cycle = []
        while current not in seen:
            seen.add(current)
            cycle.append(current)
            current = permutation[current]
        if len(cycle) > 1:
            cycles.append(cycle)
    return cycles


def generated_subgroup(generators: list[Permutation], degree: int) -> set[Permutation]:
    identity = tuple(range(degree))
    steps = tuple(generators + [inverse(generator) for generator in generators])
    subgroup = {identity}
    frontier = [identity]
    while frontier:
        current = frontier.pop()
        for generator in steps:
            candidate = compose(generator, current)
            if candidate not in subgroup:
                subgroup.add(candidate)
                frontier.append(candidate)
    return subgroup


def deterministic_generators(group: tuple[Permutation, ...]) -> tuple[Permutation, ...]:
    if not group:
        raise ValueError("automorphism group cannot be empty")
    degree = len(group[0])
    generators: list[Permutation] = []
    subgroup = generated_subgroup(generators, degree)
    for permutation in group:
        if permutation not in subgroup:
            generators.append(permutation)
            subgroup = generated_subgroup(generators, degree)
        if len(subgroup) == len(group):
            break
    if subgroup != set(group):
        raise AssertionError("selected generators do not reproduce the full group")
    return tuple(generators)


def _multiplicity(
    block_sets: tuple[frozenset[int], ...], subset: tuple[int, ...]
) -> int:
    frozen = frozenset(subset)
    return sum(frozen <= block for block in block_sets)


def enumerate_automorphisms(
    point_labels: tuple[int, ...],
    blocks: tuple[tuple[int, ...], ...],
) -> tuple[tuple[Permutation, ...], dict[str, Any]]:
    """Enumerate every block-multiset-preserving point permutation.

    Candidate images are restricted only by point, pair, and triple invariants
    that every true automorphism must preserve. Every compatible bijection is
    still visited, and the complete block multiset is checked at each leaf.
    """

    if point_labels != tuple(range(len(point_labels))):
        raise ValueError("version 1 requires consecutive point labels starting at zero")
    points = point_labels
    block_counter = Counter(blocks)
    block_sets = tuple(frozenset(block) for block in blocks)

    point_degree = {
        point: _multiplicity(block_sets, (point,)) for point in points
    }
    pair_degree = {
        pair: _multiplicity(block_sets, pair)
        for pair in itertools.combinations(points, 2)
    }
    triple_degree = {
        triple: _multiplicity(block_sets, triple)
        for triple in itertools.combinations(points, 3)
    }

    def pair_value(a: int, b: int) -> int:
        return pair_degree[tuple(sorted((a, b)))]

    def triple_value(a: int, b: int, c: int) -> int:
        return triple_degree[tuple(sorted((a, b, c)))]

    signatures = {}
    for point in points:
        others = tuple(other for other in points if other != point)
        signatures[point] = (
            point_degree[point],
            tuple(sorted(pair_value(point, other) for other in others)),
            tuple(
                sorted(
                    triple_value(point, a, b)
                    for a, b in itertools.combinations(others, 2)
                )
            ),
        )

    candidates = {
        point: tuple(
            image for image in points if signatures[image] == signatures[point]
        )
        for point in points
    }
    source_order = tuple(
        sorted(
            points,
            key=lambda point: (
                len(candidates[point]),
                -point_degree[point],
                point,
            ),
        )
    )

    assignment: dict[int, int] = {}
    used: set[int] = set()
    automorphisms: list[Permutation] = []
    search_nodes = 0
    complete_bijections_tested = 0
    rejected_at_leaf = 0

    def compatible(point: int, image: int) -> bool:
        assigned_points = tuple(assignment)
        for other in assigned_points:
            if pair_value(point, other) != pair_value(image, assignment[other]):
                return False
        for a, b in itertools.combinations(assigned_points, 2):
            if triple_value(point, a, b) != triple_value(
                image, assignment[a], assignment[b]
            ):
                return False
        return True

    def search(depth: int) -> None:
        nonlocal search_nodes, complete_bijections_tested, rejected_at_leaf
        search_nodes += 1
        if depth == len(source_order):
            complete_bijections_tested += 1
            permutation = tuple(assignment[point] for point in points)
            transformed = Counter(
                permute_block(block, permutation) for block in blocks
            )
            if transformed == block_counter:
                automorphisms.append(permutation)
            else:
                rejected_at_leaf += 1
            return
        point = source_order[depth]
        for image in candidates[point]:
            if image in used or not compatible(point, image):
                continue
            assignment[point] = image
            used.add(image)
            search(depth + 1)
            used.remove(image)
            del assignment[point]

    search(0)
    group = tuple(sorted(automorphisms))
    if len(group) != len(set(group)):
        raise AssertionError("automorphism search emitted duplicate permutations")
    identity = tuple(points)
    if identity not in group:
        raise AssertionError("identity permutation is missing")
    return group, {
        "candidate_cell_sizes": {
            str(point): len(candidates[point]) for point in points
        },
        "source_order": list(source_order),
        "search_nodes": search_nodes,
        "complete_bijections_tested": complete_bijections_tested,
        "rejected_at_block_multiset_check": rejected_at_leaf,
    }


def automorphism_manifest(
    point_labels: tuple[int, ...],
    blocks: tuple[tuple[int, ...], ...],
) -> dict[str, Any]:
    group, search_statistics = enumerate_automorphisms(point_labels, blocks)
    generators = deterministic_generators(group)
    generated = generated_subgroup(list(generators), len(point_labels))
    group_payload = [list(permutation) for permutation in group]
    return {
        "algorithm": {
            "id": "complete-invariant-backtracking-v1",
            "completeness": (
                "Every bijection preserving necessary point/pair/triple "
                "invariants is visited; every leaf is checked against the full "
                "block multiset."
            ),
        },
        "permutation_convention": "images[i] is the image of point i",
        "order": len(group),
        "group_sha256": sha256_bytes(compact_json_bytes(group_payload)),
        "permutations": group_payload,
        "generator_selection": "lexicographic-greedy-v1",
        "generator_count": len(generators),
        "generators": [
            {
                "images": list(permutation),
                "nontrivial_cycles": permutation_cycles(permutation),
            }
            for permutation in generators
        ],
        "audit_checks": {
            "identity_present": tuple(point_labels) in group,
            "permutations_unique": len(group) == len(set(group)),
            "generators_reproduce_group": generated == set(group),
            "generated_group_order": len(generated),
        },
        "search_statistics": search_statistics,
    }
