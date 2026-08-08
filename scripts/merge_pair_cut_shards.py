#!/usr/bin/env python3
"""Merge disjoint pair-cut census shards with exact profile coverage checks."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from horizonlink.canonical import sha256_file, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile_census", type=Path)
    parser.add_argument("shards", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output path already exists")

    census = json.loads(args.profile_census.read_text(encoding="utf-8"))
    census_hash = sha256_file(args.profile_census)
    expected_indices = sorted(
        int(row["index"])
        for row in census["profiles"]
        if row["root_lp"]["status"] == "LP_FEASIBLE"
    )
    loaded = [json.loads(path.read_text(encoding="utf-8")) for path in args.shards]
    if not loaded:
        raise ValueError("at least one shard is required")
    shard_count = int(loaded[0]["shard"]["count"])
    expected_shards = set(range(shard_count))
    observed_shards = {int(row["shard"]["index"]) for row in loaded}
    if observed_shards != expected_shards or len(loaded) != shard_count:
        raise ValueError("shard indices are incomplete or duplicated")

    reference = loaded[0]
    for row in loaded:
        if row.get("status") != "CUT_SEARCH_COMPLETE":
            raise ValueError("pair-cut shard is incomplete")
        if row["profile_census_sha256"] != census_hash:
            raise ValueError("pair-cut shard binds a different profile census")
        for key in (
            "class_index",
            "structural_manifest_sha256",
            "max_cuts_per_profile",
            "lp_time_limit_seconds",
        ):
            if row[key] != reference[key]:
                raise ValueError(f"pair-cut shard mismatch for {key}")
        if int(row["shard"]["total_lp_feasible_profiles"]) != len(expected_indices):
            raise ValueError("pair-cut shard records wrong feasible-profile total")

    records = sorted(
        (instance for shard in loaded for instance in shard["instances"]),
        key=lambda row: int(row["index"]),
    )
    observed_indices = [int(row["index"]) for row in records]
    if observed_indices != expected_indices:
        raise ValueError("merged pair-cut shards do not exactly cover LP-feasible profiles")
    counts = Counter(row["status"] for row in records)
    payload = {
        "schema_version": "horizonmath.pair-integrality-cut-census.v2",
        "class_index": census["class_index"],
        "profile_census_sha256": census_hash,
        "structural_manifest_sha256": reference["structural_manifest_sha256"],
        "max_cuts_per_profile": reference["max_cuts_per_profile"],
        "lp_time_limit_seconds": reference["lp_time_limit_seconds"],
        "source_shards": [
            {
                "path": str(path),
                "sha256": sha256_file(path),
            }
            for path in sorted(args.shards, key=lambda path: path.as_posix())
        ],
        "coverage": {
            "expected_lp_feasible_profiles": len(expected_indices),
            "observed_profiles": len(records),
            "indices_exactly_match": True,
            "indices_unique": len(observed_indices) == len(set(observed_indices)),
        },
        "status_counts": dict(sorted(counts.items())),
        "instances": records,
        "formal_pruning_authorized": False,
        "status": "CUT_SEARCH_COMPLETE",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, payload)
    print(
        json.dumps(
            {
                "status_counts": payload["status_counts"],
                "coverage": payload["coverage"],
                "output": str(args.output),
                "sha256": sha256_file(args.output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
