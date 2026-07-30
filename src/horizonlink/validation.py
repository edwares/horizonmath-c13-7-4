"""Mathematical validation for a minimum C(12,6,3) link."""

from __future__ import annotations

import math
from typing import Any

from horizonlink.input import LinkDocument


def validate_cover(
    link: LinkDocument, multiplicities: dict[str, Any]
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, observed: Any, expected: Any) -> None:
        checks.append(
            {
                "id": check_id,
                "passed": passed,
                "observed": observed,
                "expected": expected,
            }
        )

    add("point_count", len(link.point_labels) == 12, len(link.point_labels), 12)
    add("block_count", len(link.blocks) == 15, len(link.blocks), 15)
    add("unique_blocks", len(set(link.blocks)) == 15, len(set(link.blocks)), 15)
    add(
        "block_sizes",
        all(len(block) == 6 for block in link.blocks),
        sorted({len(block) for block in link.blocks}),
        [6],
    )
    add(
        "block_points_in_universe",
        all(set(block) <= set(link.point_labels) for block in link.blocks),
        all(set(block) <= set(link.point_labels) for block in link.blocks),
        True,
    )

    triple_rows = multiplicities["triples"]["rows"]
    uncovered_triples = [
        row["set"] for row in triple_rows if row["multiplicity"] == 0
    ]
    add(
        "triple_universe_count",
        len(triple_rows) == math.comb(12, 3),
        len(triple_rows),
        math.comb(12, 3),
    )
    add(
        "all_triples_covered",
        not uncovered_triples,
        len(uncovered_triples),
        0,
    )

    for name in ("points", "pairs", "triples", "four_sets"):
        section = multiplicities[name]
        add(
            f"{name}_incidence_identity",
            section["total_incidence"] == section["expected_total_incidence"],
            section["total_incidence"],
            section["expected_total_incidence"],
        )

    errors = [
        {
            "code": check["id"].upper(),
            "message": (
                f"{check['id']} failed: observed {check['observed']!r}, "
                f"expected {check['expected']!r}"
            ),
        }
        for check in checks
        if not check["passed"]
    ]
    return {
        "valid_15_block_C_12_6_3_cover": not errors,
        "checks": checks,
        "errors": errors,
        "uncovered_triples": uncovered_triples,
    }
