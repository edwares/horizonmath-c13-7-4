#!/usr/bin/env python3
"""Search a deterministic shard of exact profiles for forced pair equalities."""

from __future__ import annotations

import argparse
import itertools
import json
import time
import warnings
from collections import Counter
from pathlib import Path

from horizonlink.canonical import sha256_file, write_json
from horizonlink.pb import PBRow, build_corrected_formula
from horizonlink.split_farkas import _normalized_lp_system


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("structural_manifest", type=Path)
    parser.add_argument("profile_census", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-cuts", type=int, default=16)
    parser.add_argument("--lp-time-limit", type=float, default=5.0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    args = parser.parse_args()

    if args.output.exists():
        raise ValueError("output path already exists")
    if args.max_cuts <= 0 or args.lp_time_limit <= 0:
        raise ValueError("cut and LP limits must be positive")
    if args.shard_count <= 0:
        raise ValueError("shard count must be positive")
    if not 0 <= args.shard_index < args.shard_count:
        raise ValueError("shard index is outside shard count")

    import numpy
    import scipy
    import scipy.optimize
    import scipy.sparse

    structural = json.loads(args.structural_manifest.read_text(encoding="utf-8"))
    census = json.loads(args.profile_census.read_text(encoding="utf-8"))
    if census.get("status") != "ENUMERATED_AND_LP_SCREENED":
        raise ValueError("profile census is not ready for pair-cut discovery")
    normalized = structural["input"]["normalized_document"]
    point_labels = tuple(normalized["point_labels"])
    link_blocks = tuple(tuple(block) for block in normalized["blocks"])

    def solve(rows: tuple[PBRow, ...], variable_count: int):
        matrix, rhs = _normalized_lp_system(
            rows, variable_count, numpy, scipy.sparse
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return scipy.optimize.linprog(
                numpy.zeros(variable_count),
                A_ub=-matrix,
                b_ub=-rhs,
                bounds=(0, 1),
                method="highs",
                options={
                    "presolve": True,
                    "time_limit": float(args.lp_time_limit),
                    "threads": 1,
                    "parallel": False,
                    "random_seed": 0,
                },
            )

    all_selected = [
        row
        for row in census["profiles"]
        if row["root_lp"]["status"] == "LP_FEASIBLE"
    ]
    selected = [
        row
        for ordinal, row in enumerate(all_selected)
        if ordinal % args.shard_count == args.shard_index
    ]
    output_records = []
    for ordinal, source in enumerate(selected, start=1):
        started = time.monotonic()
        built = build_corrected_formula(
            point_labels, link_blocks, source["extension_degrees"]
        )
        blocks = built["extension_blocks"]
        variable_count = built["metadata"]["variables"]
        current_rows = built["rows"]
        pair_variables = {
            pair: tuple(
                index
                for index, block in enumerate(blocks)
                if frozenset(pair) <= frozenset(block)
            )
            for pair in itertools.combinations(point_labels, 2)
        }
        lp_solves = 0
        cuts = []
        used_pairs: set[tuple[int, int]] = set()
        result = solve(current_rows, variable_count)
        lp_solves += 1
        if int(result.status) != 0 or result.x is None:
            raise ValueError("census-LP-feasible profile did not rebuild feasible")

        final_status = "UNRESOLVED"
        while len(cuts) < args.max_cuts:
            chosen = None
            for pair in itertools.combinations(point_labels, 2):
                if pair in used_pairs:
                    continue
                variables = pair_variables[pair]
                value = int(round(sum(float(result.x[index]) for index in variables)))
                lower_negation = PBRow(
                    variables, "<=", value - 1, "cut_negation", pair
                )
                low_result = solve(current_rows + (lower_negation,), variable_count)
                lp_solves += 1
                if int(low_result.status) != 2:
                    if int(low_result.status) not in {0, 2}:
                        final_status = "LP_ERROR"
                        chosen = None
                        break
                    continue
                upper_negation = PBRow(
                    variables, ">=", value + 1, "cut_negation", pair
                )
                high_result = solve(current_rows + (upper_negation,), variable_count)
                lp_solves += 1
                if int(high_result.status) == 2:
                    chosen = (pair, variables, value)
                    break
                if int(high_result.status) != 0:
                    final_status = "LP_ERROR"
                    chosen = None
                    break
            if final_status == "LP_ERROR":
                break
            if chosen is None:
                final_status = "NO_FORCED_PAIR_CUT"
                break
            pair, variables, value = chosen
            used_pairs.add(pair)
            lower = PBRow(
                variables, ">=", value, "integrality_forced_pair", pair
            )
            upper = PBRow(
                variables, "<=", value, "integrality_forced_pair", pair
            )
            current_rows = current_rows + (lower, upper)
            cuts.append({"pair": list(pair), "value": value})
            result = solve(current_rows, variable_count)
            lp_solves += 1
            if int(result.status) == 2:
                final_status = "LP_UNSAT_AFTER_INTEGRALITY_CUTS"
                break
            if int(result.status) != 0 or result.x is None:
                final_status = "LP_ERROR"
                break
        else:
            final_status = "CUT_LIMIT"

        record = {
            "index": source["index"],
            "case_id": source["case_id"],
            "profile_id": source["profile_id"],
            "status": final_status,
            "cuts": cuts,
            "cut_count": len(cuts),
            "lp_solve_count": lp_solves,
            "seconds": time.monotonic() - started,
        }
        output_records.append(record)
        print(
            f"[{ordinal}/{len(selected)}] shard={args.shard_index}/"
            f"{args.shard_count} index={source['index']} status={final_status} "
            f"cuts={len(cuts)} lp_solves={lp_solves} "
            f"seconds={record['seconds']:.3f}",
            flush=True,
        )

    counts = Counter(row["status"] for row in output_records)
    payload = {
        "schema_version": "horizonmath.pair-integrality-cut-census-shard.v1",
        "class_index": census["class_index"],
        "profile_census_sha256": sha256_file(args.profile_census),
        "structural_manifest_sha256": sha256_file(args.structural_manifest),
        "max_cuts_per_profile": args.max_cuts,
        "lp_time_limit_seconds": args.lp_time_limit,
        "shard": {
            "count": args.shard_count,
            "index": args.shard_index,
            "total_lp_feasible_profiles": len(all_selected),
            "selected_profiles": len(selected),
        },
        "status_counts": dict(sorted(counts.items())),
        "instances": output_records,
        "formal_pruning_authorized": False,
        "status": "CUT_SEARCH_COMPLETE",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, payload)
    print(
        json.dumps(
            {
                "shard_index": args.shard_index,
                "status_counts": payload["status_counts"],
                "output": str(args.output),
                "sha256": sha256_file(args.output),
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
