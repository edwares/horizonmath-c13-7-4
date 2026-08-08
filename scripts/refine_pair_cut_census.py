#!/usr/bin/env python3
"""Refine only unresolved CUT_LIMIT rows in a pair-cut census."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from horizonlink.canonical import sha256_file, write_json


TERMINAL_STATUSES = {
    "LP_UNSAT_AFTER_INTEGRALITY_CUTS",
    "NO_FORCED_PAIR_CUT",
}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_census", type=Path)
    parser.add_argument("profile_census", type=Path)
    parser.add_argument("refinements", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.output.exists():
        raise ValueError("output path already exists")

    profile = read_json(args.profile_census)
    base = read_json(args.base_census)
    profile_sha256 = sha256_file(args.profile_census)
    expected_indices = sorted(
        int(row["index"])
        for row in profile["profiles"]
        if row["root_lp"]["status"] == "LP_FEASIBLE"
    )
    expected_set = set(expected_indices)
    base_rows = base.get("instances", [])
    base_by_index = {int(row["index"]): row for row in base_rows}
    if (
        base.get("status") != "CUT_SEARCH_COMPLETE"
        or base.get("class_index") != profile.get("class_index")
        or base.get("profile_census_sha256") != profile_sha256
        or len(base_by_index) != len(base_rows)
        or set(base_by_index) != expected_set
        or base.get("coverage", {}).get("indices_exactly_match") is not True
        or base.get("coverage", {}).get("indices_unique") is not True
    ):
        raise ValueError("base pair-cut census failed coverage/provenance audit")

    replacement_by_index: dict[int, dict[str, Any]] = {}
    refinement_sources: list[dict[str, Any]] = []
    for path in args.refinements:
        refinement = read_json(path)
        rows = refinement.get("instances", [])
        if (
            refinement.get("status") != "CUT_SEARCH_COMPLETE"
            or refinement.get("class_index") != base.get("class_index")
            or refinement.get("profile_census_sha256") != profile_sha256
            or refinement.get("structural_manifest_sha256")
            != base.get("structural_manifest_sha256")
            or int(refinement.get("shard", {}).get("total_lp_feasible_profiles", -1))
            != len(expected_indices)
            or not rows
        ):
            raise ValueError(f"refinement failed provenance audit: {path}")

        source_indices: list[int] = []
        for row in rows:
            index = int(row["index"])
            if index in replacement_by_index:
                raise ValueError(f"duplicate refinement index: {index}")
            if index not in base_by_index:
                raise ValueError(f"unknown refinement index: {index}")
            if base_by_index[index].get("status") != "CUT_LIMIT":
                raise ValueError(f"refinement index {index} was not CUT_LIMIT")
            if row.get("status") not in TERMINAL_STATUSES:
                raise ValueError(
                    f"refinement index {index} is not terminal: {row.get('status')}"
                )
            if (
                int(row["case_id"]) != int(base_by_index[index]["case_id"])
                or int(row["profile_id"]) != int(base_by_index[index]["profile_id"])
                or int(row.get("cut_count", -1)) != len(row.get("cuts", []))
            ):
                raise ValueError(f"refinement identity/accounting mismatch: {index}")
            replacement_by_index[index] = row
            source_indices.append(index)

        refinement_sources.append(
            {
                "path": path.as_posix(),
                "sha256": sha256_file(path),
                "indices": sorted(source_indices),
                "max_cuts_per_profile": refinement.get("max_cuts_per_profile"),
                "lp_time_limit_seconds": refinement.get("lp_time_limit_seconds"),
            }
        )

    original_cut_limits = sorted(
        index for index, row in base_by_index.items() if row.get("status") == "CUT_LIMIT"
    )
    if sorted(replacement_by_index) != original_cut_limits:
        raise ValueError(
            "refinements must resolve every and only base CUT_LIMIT index: "
            f"expected={original_cut_limits}, observed={sorted(replacement_by_index)}"
        )

    records = [
        replacement_by_index.get(index, base_by_index[index]) for index in expected_indices
    ]
    statuses = [str(row.get("status")) for row in records]
    nonterminal = sorted(
        int(row["index"]) for row in records if row.get("status") not in TERMINAL_STATUSES
    )
    if nonterminal:
        raise ValueError(f"refined census still has nonterminal rows: {nonterminal}")

    payload = {
        "schema_version": "horizonmath.pair-integrality-cut-census.refined.v1",
        "class_index": base["class_index"],
        "profile_census_sha256": profile_sha256,
        "structural_manifest_sha256": base["structural_manifest_sha256"],
        "base_census": {
            "path": args.base_census.as_posix(),
            "sha256": sha256_file(args.base_census),
        },
        "refinements": refinement_sources,
        "refined_indices": sorted(replacement_by_index),
        "coverage": {
            "expected_lp_feasible_profiles": len(expected_indices),
            "observed_profiles": len(records),
            "indices_exactly_match": [int(row["index"]) for row in records]
            == expected_indices,
            "indices_unique": len(records)
            == len({int(row["index"]) for row in records}),
        },
        "status_counts": dict(sorted(Counter(statuses).items())),
        "instances": records,
        "formal_pruning_authorized": False,
        "status": "CUT_SEARCH_COMPLETE",
    }
    if not all(payload["coverage"].values()):
        raise AssertionError("refined coverage audit failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, payload)
    print(
        json.dumps(
            {
                "coverage": payload["coverage"],
                "output": str(args.output),
                "refined_indices": payload["refined_indices"],
                "sha256": sha256_file(args.output),
                "status_counts": payload["status_counts"],
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
