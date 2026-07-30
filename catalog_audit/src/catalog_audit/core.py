from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from itertools import combinations, product
import json
from math import prod
from typing import Iterable, Iterator, Sequence


Block = tuple[int, ...]
Link = tuple[Block, ...]


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            separators=(",", ": "),
        )
        + "\n"
    ).encode("utf-8")


def compact_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def normalize_link(link: Iterable[Iterable[int]]) -> Link:
    return tuple(sorted(tuple(sorted(int(point) for point in block)) for block in link))


def link_sha256(
    link: Iterable[Iterable[int]], *, point_count: int | None = None
) -> str:
    """Hash the canonical labeled-link payload used by horizonlink v0.4.0."""

    normalized = [list(block) for block in normalize_link(link)]
    if point_count is None:
        points = sorted({point for block in normalized for point in block})
    else:
        points = list(range(point_count))
    payload = {"blocks": normalized, "points": points}
    return sha256(compact_json_bytes(payload)).hexdigest()


def _block_masks(link: Link) -> tuple[int, ...]:
    masks: list[int] = []
    for block in link:
        mask = 0
        for point in block:
            mask |= 1 << point
        masks.append(mask)
    return tuple(masks)


def validate_link(
    link: Iterable[Iterable[int]],
    *,
    point_count: int,
    block_size: int,
    block_count: int,
    cover_strength: int = 3,
) -> dict[str, object]:
    normalized = normalize_link(link)
    problems: list[str] = []
    if len(normalized) != block_count:
        problems.append(f"expected {block_count} blocks, found {len(normalized)}")
    if len(set(normalized)) != len(normalized):
        problems.append("duplicate blocks")
    for index, block in enumerate(normalized):
        if len(block) != block_size:
            problems.append(
                f"block {index} has size {len(block)}, expected {block_size}"
            )
        if len(set(block)) != len(block):
            problems.append(f"block {index} repeats a point")
        if any(point < 0 or point >= point_count for point in block):
            problems.append(f"block {index} contains a point outside the ground set")

    covered: set[tuple[int, ...]] = set()
    if not problems:
        for block in normalized:
            covered.update(combinations(block, cover_strength))
    expected_cover_count = len(list(combinations(range(point_count), cover_strength)))
    missing = expected_cover_count - len(covered)
    if missing:
        problems.append(f"{missing} {cover_strength}-subsets are uncovered")

    return {
        "valid": not problems,
        "problems": problems,
        "block_count": len(normalized),
        "distinct_block_count": len(set(normalized)),
        "covered_subset_count": len(covered),
        "expected_covered_subset_count": expected_cover_count,
        "canonical_labeled_link_sha256": link_sha256(
            normalized, point_count=point_count
        ),
    }


def link_statistics(link: Link, point_count: int) -> dict[str, object]:
    block_sets = tuple(set(block) for block in link)
    point_multiplicities = [
        sum(point in block for block in block_sets) for point in range(point_count)
    ]
    pair_multiplicities = [
        sum(set(pair) <= block for block in block_sets)
        for pair in combinations(range(point_count), 2)
    ]
    triple_multiplicities = [
        sum(set(triple) <= block for block in block_sets)
        for triple in combinations(range(point_count), 3)
    ]
    covered_fours = {
        four for block in link for four in combinations(block, 4)
    }
    total_fours = len(list(combinations(range(point_count), 4)))
    return {
        "point_multiplicities": point_multiplicities,
        "pair_multiplicity_histogram": {
            str(key): value
            for key, value in sorted(Counter(pair_multiplicities).items())
        },
        "triple_multiplicity_histogram": {
            str(key): value
            for key, value in sorted(Counter(triple_multiplicities).items())
        },
        "covered_four_set_count": len(covered_fours),
        "residual_four_set_count": total_fours - len(covered_fours),
    }


@lru_cache(maxsize=256)
def _containment_counts(link: Link) -> dict[int, int]:
    counts: defaultdict[int, int] = defaultdict(int)
    for block in link:
        block_mask = sum(1 << point for point in block)
        submask = block_mask
        while True:
            counts[submask] += 1
            if submask == 0:
                break
            submask = (submask - 1) & block_mask
    return dict(counts)


@lru_cache(maxsize=1024)
def _refinement_tokens(
    link: Link, point_count: int, rounds: int = 8
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    node_count = point_count + len(link)
    neighbors: list[list[int]] = [[] for _ in range(node_count)]
    for block_index, block in enumerate(link):
        block_node = point_count + block_index
        for point in block:
            neighbors[point].append(block_node)
            neighbors[block_node].append(point)

    tokens = [
        sha256(("point" if node < point_count else "block").encode()).hexdigest()
        for node in range(node_count)
    ]
    for _ in range(rounds):
        updated = []
        for node in range(node_count):
            payload = tokens[node] + "|" + "|".join(
                sorted(tokens[neighbor] for neighbor in neighbors[node])
            )
            updated.append(sha256(payload.encode()).hexdigest())
        if updated == tokens:
            break
        tokens = updated
    return tuple(tokens[:point_count]), tuple(tokens[point_count:])


def _invariant(link: Link, point_count: int) -> tuple[object, ...]:
    block_sets = tuple(set(block) for block in link)
    point_degrees = tuple(
        sorted(sum(point in block for block in block_sets) for point in range(point_count))
    )
    pair_degrees = tuple(
        sorted(
            sum(set(pair) <= block for block in block_sets)
            for pair in combinations(range(point_count), 2)
        )
    )
    triple_degrees = tuple(
        sorted(
            sum(set(triple) <= block for block in block_sets)
            for triple in combinations(range(point_count), 3)
        )
    )
    intersections = tuple(
        sorted(
            len(block_sets[left] & block_sets[right])
            for left in range(len(link))
            for right in range(left)
        )
    )
    point_tokens, block_tokens = _refinement_tokens(link, point_count)
    return (
        point_degrees,
        pair_degrees,
        triple_degrees,
        intersections,
        tuple(sorted(point_tokens)),
        tuple(sorted(block_tokens)),
    )


def invariant_sha256(link: Link, point_count: int) -> str:
    return sha256(canonical_json_bytes(_invariant(link, point_count))).hexdigest()


def exact_isomorphism(
    left: Iterable[Iterable[int]],
    right: Iterable[Iterable[int]],
    *,
    point_count: int,
    return_mapping: bool = False,
    assume_invariant_equal: bool = False,
) -> bool | tuple[bool, tuple[int, ...] | None]:
    """Test exact hypergraph isomorphism by point-map backtracking.

    Refinement tokens and aggregate invariants are pruning devices only.
    A successful mapping is accepted only after every source block maps to a
    target block. During search, containment multiplicities of all assigned
    subsets through size six must agree.
    """

    a = normalize_link(left)
    b = normalize_link(right)
    if len(a) != len(b) or any(len(x) != len(y) for x, y in zip(a, b)):
        result: bool | tuple[bool, tuple[int, ...] | None] = (
            (False, None) if return_mapping else False
        )
        return result
    if not assume_invariant_equal and _invariant(a, point_count) != _invariant(
        b, point_count
    ):
        return (False, None) if return_mapping else False

    counts_a = _containment_counts(a)
    counts_b = _containment_counts(b)
    tokens_a, _ = _refinement_tokens(a, point_count)
    tokens_b, _ = _refinement_tokens(b, point_count)
    target_blocks = set(_block_masks(b))
    mapping = [-1] * point_count
    used_target_mask = 0
    assigned_source_mask = 0

    def mapped_submask(source_submask: int) -> int:
        target_submask = 0
        while source_submask:
            bit = source_submask & -source_submask
            source = bit.bit_length() - 1
            target_submask |= 1 << mapping[source]
            source_submask ^= bit
        return target_submask

    def compatible(source: int, target: int) -> bool:
        submask = assigned_source_mask
        while True:
            if submask.bit_count() <= 5:
                source_mask = submask | (1 << source)
                target_mask = mapped_submask(submask) | (1 << target)
                if counts_a.get(source_mask, 0) != counts_b.get(target_mask, 0):
                    return False
            if submask == 0:
                return True
            submask = (submask - 1) & assigned_source_mask

    def search() -> bool:
        nonlocal used_target_mask, assigned_source_mask
        if assigned_source_mask == (1 << point_count) - 1:
            mapped_blocks = {
                sum(1 << mapping[point] for point in block) for block in a
            }
            return mapped_blocks == target_blocks

        best_source = -1
        best_candidates: list[int] | None = None
        for source in range(point_count):
            if assigned_source_mask & (1 << source):
                continue
            candidates = [
                target
                for target in range(point_count)
                if not (used_target_mask & (1 << target))
                and tokens_a[source] == tokens_b[target]
                and compatible(source, target)
            ]
            if not candidates:
                return False
            if best_candidates is None or (len(candidates), source) < (
                len(best_candidates),
                best_source,
            ):
                best_source = source
                best_candidates = candidates

        assert best_candidates is not None
        source_bit = 1 << best_source
        for target in best_candidates:
            target_bit = 1 << target
            mapping[best_source] = target
            assigned_source_mask |= source_bit
            used_target_mask |= target_bit
            if search():
                return True
            used_target_mask ^= target_bit
            assigned_source_mask ^= source_bit
            mapping[best_source] = -1
        return False

    isomorphic = search()
    if return_mapping:
        return isomorphic, tuple(mapping) if isomorphic else None
    return isomorphic


def iter_completions(spec: dict[str, object]) -> Iterator[tuple[int, tuple[Block, ...], Link]]:
    point_count = int(spec["parameters"]["point_count"])  # type: ignore[index]
    template = spec["first_template"]  # type: ignore[index]
    fixed_blocks = normalize_link(template["fixed_blocks"])  # type: ignore[index]
    files = tuple(tuple(file) for file in template["files"])  # type: ignore[index]
    choice_domains = tuple(
        tuple(tuple(choice) for choice in domain)
        for domain in template["choice_domains"]  # type: ignore[index]
    )
    if len(files) != len(choice_domains):
        raise ValueError("files and choice_domains have different lengths")
    completion_index = 0
    for choices in product(*choice_domains):
        completion_index += 1
        appended = [
            tuple(sorted(tuple(files[index]) + tuple(choice)))
            for index, choice in enumerate(choices)
        ]
        link = normalize_link(tuple(fixed_blocks) + tuple(appended))
        if any(point < 0 or point >= point_count for block in link for point in block):
            raise ValueError("completion contains a point outside the ground set")
        yield completion_index, tuple(choices), link


@dataclass
class ClassificationResult:
    representatives: list[Link]
    full_counts: list[int]
    prefix_counts: list[int]
    first_occurrences: list[int]
    first_choices: list[tuple[Block, ...]]
    ledger: list[dict[str, object]]
    invalid_completions: list[dict[str, object]]


def classify_completions(spec: dict[str, object]) -> ClassificationResult:
    parameters = spec["parameters"]  # type: ignore[index]
    point_count = int(parameters["point_count"])  # type: ignore[index]
    block_size = int(parameters["block_size"])  # type: ignore[index]
    block_count = int(parameters["link_block_count"])  # type: ignore[index]
    cover_strength = int(parameters["cover_strength"])  # type: ignore[index]
    historical_prefix = int(
        spec["historical_catalog"]["archived_num_completions"]  # type: ignore[index]
    )

    buckets: defaultdict[tuple[object, ...], list[int]] = defaultdict(list)
    representatives: list[Link] = []
    full_counts: list[int] = []
    prefix_counts: list[int] = []
    first_occurrences: list[int] = []
    first_choices: list[tuple[Block, ...]] = []
    ledger: list[dict[str, object]] = []
    invalid_completions: list[dict[str, object]] = []

    for completion_index, choices, link in iter_completions(spec):
        validation = validate_link(
            link,
            point_count=point_count,
            block_size=block_size,
            block_count=block_count,
            cover_strength=cover_strength,
        )
        if not validation["valid"]:
            invalid_completions.append(
                {
                    "completion_index": completion_index,
                    "choices": [[*choice] for choice in choices],
                    "validation": validation,
                }
            )

        signature = _invariant(link, point_count)
        found: int | None = None
        for candidate in buckets[signature]:
            if exact_isomorphism(
                link,
                representatives[candidate],
                point_count=point_count,
                assume_invariant_equal=True,
            ):
                found = candidate
                break
        if found is None:
            found = len(representatives)
            representatives.append(link)
            full_counts.append(0)
            prefix_counts.append(0)
            first_occurrences.append(completion_index)
            first_choices.append(choices)
            buckets[signature].append(found)
        full_counts[found] += 1
        if completion_index <= historical_prefix:
            prefix_counts[found] += 1

        ledger.append(
            {
                "completion_index": completion_index,
                "choices": [[*choice] for choice in choices],
                "discovered_class_index": found + 1,
                "canonical_labeled_link_sha256": validation[
                    "canonical_labeled_link_sha256"
                ],
                "valid_cover": validation["valid"],
            }
        )

    return ClassificationResult(
        representatives=representatives,
        full_counts=full_counts,
        prefix_counts=prefix_counts,
        first_occurrences=first_occurrences,
        first_choices=first_choices,
        ledger=ledger,
        invalid_completions=invalid_completions,
    )


def expected_completion_count(spec: dict[str, object]) -> int:
    domains = spec["first_template"]["choice_domains"]  # type: ignore[index]
    return prod(len(domain) for domain in domains)
