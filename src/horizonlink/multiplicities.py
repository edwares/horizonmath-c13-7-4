"""Complete subset multiplicities for a labeled block family."""

from __future__ import annotations

import itertools
import math
from collections import Counter
from typing import Any, Iterable

from horizonlink.canonical import compact_json_bytes, sha256_bytes


def subset_multiplicities(
    point_labels: Iterable[int],
    blocks: Iterable[Iterable[int]],
    subset_size: int,
) -> tuple[tuple[tuple[int, ...], int], ...]:
    points = tuple(sorted(point_labels))
    block_sets = tuple(frozenset(block) for block in blocks)
    return tuple(
        (
            subset,
            sum(frozenset(subset) <= block for block in block_sets),
        )
        for subset in itertools.combinations(points, subset_size)
    )


def multiplicity_table(
    rows: tuple[tuple[tuple[int, ...], int], ...]
) -> list[dict[str, Any]]:
    return [
        {"set": list(subset), "multiplicity": multiplicity}
        for subset, multiplicity in rows
    ]


def multiplicity_histogram(
    rows: tuple[tuple[tuple[int, ...], int], ...]
) -> dict[str, int]:
    counts = Counter(multiplicity for _, multiplicity in rows)
    return {str(value): counts[value] for value in sorted(counts)}


def table_sha256(rows: tuple[tuple[tuple[int, ...], int], ...]) -> str:
    payload = [
        {"set": list(subset), "multiplicity": multiplicity}
        for subset, multiplicity in rows
    ]
    return sha256_bytes(compact_json_bytes(payload))


def compute_multiplicities(
    point_labels: tuple[int, ...],
    blocks: tuple[tuple[int, ...], ...],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    names = {1: "points", 2: "pairs", 3: "triples", 4: "four_sets"}
    for size, name in names.items():
        rows = subset_multiplicities(point_labels, blocks, size)
        result[name] = {
            "subset_size": size,
            "subset_count": len(rows),
            "expected_subset_count": math.comb(len(point_labels), size),
            "total_incidence": sum(multiplicity for _, multiplicity in rows),
            "expected_total_incidence": len(blocks) * math.comb(6, size),
            "histogram": multiplicity_histogram(rows),
            "table_sha256": table_sha256(rows),
            "rows": multiplicity_table(rows),
        }
    four_rows = subset_multiplicities(point_labels, blocks, 4)
    result["residual_four_sets"] = {
        "count": sum(multiplicity == 0 for _, multiplicity in four_rows),
        "sets": [
            list(subset)
            for subset, multiplicity in four_rows
            if multiplicity == 0
        ],
    }
    return result
