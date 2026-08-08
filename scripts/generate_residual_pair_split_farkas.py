#!/usr/bin/env python3
"""Generate exact pair-CG + split-tree VeriPB proofs for residual profiles.

The input profiles have survived the root-LP and forced-pair-equality passes.
We first derive one-sided integral pair-count bounds by exact Farkas/CG
reasoning, then branch only if the strengthened LP is still feasible.  The
floating LP computations choose cuts and a tree; every emitted proof step is
reconstructed in exact integer arithmetic before VeriPB sees it.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import time
import warnings
from pathlib import Path

from horizonlink.canonical import sha256_bytes, sha256_file, write_json
from horizonlink.farkas import (
    _dual_alternative,
    _exact_certificate,
    _render_verifier_opb,
)
from horizonlink.pb import PBRow, build_corrected_formula
from horizonlink.split_farkas import (
    _build_split_tree,
    _exact_leaf_certificate,
    _leaf_dual_alternative,
    _normalized_lp_system,
    _render_split_proof,
)


def _proof_term(
    tokens: list[str], operand: str, multiplier: int, first: bool
) -> bool:
    tokens.extend([operand, str(multiplier), "*"])
    if not first:
        tokens.append("+")
    return False


def _normalized_row_text(row: PBRow) -> str:
    if row.relation == ">=":
        coefficient, rhs = "+1", row.rhs
    else:
        coefficient, rhs = "-1", -row.rhs
    return (
        " ".join(f"{coefficient} x{variable + 1}" for variable in row.variables)
        + f" >= {rhs} ;"
    )


def _derive_integral_bound(
    current_rows: tuple[PBRow, ...],
    requested: PBRow,
    assumption: PBRow,
    variable_count: int,
    numpy_module,
    scipy_optimize,
    scipy_sparse,
) -> tuple[str, PBRow, dict]:
    """Derive a bound and return the exact (possibly stronger) CG result."""

    augmented = current_rows + (assumption,)
    alternative = _dual_alternative(
        augmented,
        variable_count,
        numpy_module,
        scipy_optimize,
        scipy_sparse,
    )
    certificate = _exact_certificate(augmented, variable_count, alternative)
    assumption_id = len(augmented)
    assumption_items = [
        item
        for item in certificate["row_multipliers"]
        if int(item["row_id_1based"]) == assumption_id
    ]
    if len(assumption_items) != 1:
        raise ValueError("pair-cut assumption is absent from Farkas support")
    divisor = int(assumption_items[0]["multiplier"])
    margin = int(certificate["combined_rhs_after_bounds"])
    if divisor <= 0 or margin <= 0:
        raise ValueError("invalid exact Farkas divisor or contradiction margin")

    tokens: list[str] = []
    first = True
    for item in certificate["row_multipliers"]:
        if int(item["row_id_1based"]) == assumption_id:
            continue
        first = _proof_term(
            tokens,
            str(item["row_id_1based"]),
            int(item["multiplier"]),
            first,
        )
    for item in certificate["lower_bound_multipliers"]:
        first = _proof_term(
            tokens,
            f"x{item['variable']}",
            int(item["multiplier"]),
            first,
        )
    for item in certificate["upper_bound_multipliers"]:
        first = _proof_term(
            tokens,
            f"~x{item['variable']}",
            int(item["multiplier"]),
            first,
        )
    if first:
        raise ValueError("pair-cut Farkas line has no globally valid terms")
    tokens.extend([str(divisor), "d"])

    quotient = (margin + divisor - 1) // divisor
    if requested.relation == ">=":
        # Negation was y <= L-1.  Division proves
        # y >= (L-1) + ceil(margin/divisor).
        effective_rhs = requested.rhs - 1 + quotient
        if effective_rhs < requested.rhs:
            raise AssertionError("derived lower bound is weaker than requested")
    elif requested.relation == "<=":
        # Negation was y >= U+1.  Division proves
        # y <= (U+1) - ceil(margin/divisor).
        effective_rhs = requested.rhs + 1 - quotient
        if effective_rhs > requested.rhs:
            raise AssertionError("derived upper bound is weaker than requested")
    else:
        raise ValueError(f"unsupported relation {requested.relation}")
    effective = PBRow(
        requested.variables,
        requested.relation,
        effective_rhs,
        "exact_pair_cg_bound",
        requested.subject,
    )
    return "p " + " ".join(tokens), effective, {
        "requested_relation": requested.relation,
        "requested_rhs": requested.rhs,
        "effective_relation": effective.relation,
        "effective_rhs": effective.rhs,
        "assumption_relation": assumption.relation,
        "assumption_rhs": assumption.rhs,
        "assumption_multiplier": divisor,
        "exact_contradiction_margin": margin,
        "ceil_margin_over_multiplier": quotient,
        "farkas_row_support_size": len(certificate["row_multipliers"]),
        "exact_checks": certificate["exact_checks"],
    }


def _root_lp(
    rows: tuple[PBRow, ...],
    variable_count: int,
    numpy_module,
    scipy_optimize,
    scipy_sparse,
    time_limit: float,
):
    matrix, rhs = _normalized_lp_system(
        rows, variable_count, numpy_module, scipy_sparse
    )
    def solve(method: str, limit: float):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return scipy_optimize.linprog(
                numpy_module.zeros(variable_count),
                A_ub=-matrix,
                b_ub=-rhs,
                bounds=(0, 1),
                method=method,
                options={
                    "presolve": True,
                    "time_limit": limit,
                    "threads": 1,
                    "parallel": False,
                    "random_seed": 0,
                },
            )

    result = solve("highs", time_limit)
    if int(result.status) in {0, 2}:
        return result
    # Auxiliary cut tests are heuristic search only.  A short time limit may
    # occasionally expire under load, so retry deterministically with the
    # dual-simplex driver and a modestly larger bound before declaring the
    # search indeterminate.  Exact certificates remain a separate step.
    return solve("highs-ds", max(10.0, 5.0 * time_limit))


def _discover_pair_cut(
    current_rows: tuple[PBRow, ...],
    pair_variables: dict[tuple[int, ...], tuple[int, ...]],
    root_result,
    variable_count: int,
    numpy_module,
    scipy_optimize,
    scipy_sparse,
    time_limit: float,
) -> tuple[PBRow, PBRow, dict] | None:
    """Return the first lexicographic one-sided integral cut, if one exists."""

    tests = 0
    for pair, variables in pair_variables.items():
        value = sum(float(root_result.x[index]) for index in variables)
        nearest = round(value)
        if abs(value - nearest) <= 1e-7:
            continue
        lower_rhs = math.ceil(value - 1e-9)
        lower = PBRow(
            variables, ">=", lower_rhs, "pair_cg_requested", pair
        )
        lower_assumption = PBRow(
            variables, "<=", lower_rhs - 1, "pair_cg_negation", pair
        )
        result = _root_lp(
            current_rows + (lower_assumption,),
            variable_count,
            numpy_module,
            scipy_optimize,
            scipy_sparse,
            time_limit,
        )
        tests += 1
        if int(result.status) == 2:
            return lower, lower_assumption, {
                "pair": list(pair),
                "fractional_value": value,
                "lp_tests_this_search": tests,
            }
        if int(result.status) not in {0, 2}:
            raise ValueError(
                f"pair lower-negation LP indeterminate for {pair}: "
                f"status={result.status}, message={result.message}"
            )

        upper_rhs = math.floor(value + 1e-9)
        upper = PBRow(
            variables, "<=", upper_rhs, "pair_cg_requested", pair
        )
        upper_assumption = PBRow(
            variables, ">=", upper_rhs + 1, "pair_cg_negation", pair
        )
        result = _root_lp(
            current_rows + (upper_assumption,),
            variable_count,
            numpy_module,
            scipy_optimize,
            scipy_sparse,
            time_limit,
        )
        tests += 1
        if int(result.status) == 2:
            return upper, upper_assumption, {
                "pair": list(pair),
                "fractional_value": value,
                "lp_tests_this_search": tests,
            }
        if int(result.status) not in {0, 2}:
            raise ValueError(
                f"pair upper-negation LP indeterminate for {pair}: "
                f"status={result.status}, message={result.message}"
            )
    return None


def _planned_cut(
    spec: dict,
    pair_variables: dict[tuple[int, int], tuple[int, ...]],
) -> tuple[PBRow, PBRow, dict]:
    pair = tuple(int(value) for value in spec["pair"])
    variables = pair_variables[pair]
    relation = str(spec["relation"])
    rhs = int(spec["rhs"])
    requested = PBRow(
        variables, relation, rhs, "pair_cg_requested", pair
    )
    if relation == ">=":
        assumption = PBRow(
            variables, "<=", rhs - 1, "pair_cg_negation", pair
        )
    elif relation == "<=":
        assumption = PBRow(
            variables, ">=", rhs + 1, "pair_cg_negation", pair
        )
    else:
        raise ValueError(f"unsupported planned relation {relation}")
    return requested, assumption, {"pair": list(pair), "planned": True}


def _final_farkas_line(certificate: dict) -> str:
    tokens: list[str] = []
    first = True
    for item in certificate["row_multipliers"]:
        first = _proof_term(
            tokens,
            str(item["row_id_1based"]),
            int(item["multiplier"]),
            first,
        )
    for item in certificate["lower_bound_multipliers"]:
        first = _proof_term(
            tokens,
            f"x{item['variable']}",
            int(item["multiplier"]),
            first,
        )
    for item in certificate["upper_bound_multipliers"]:
        first = _proof_term(
            tokens,
            f"~x{item['variable']}",
            int(item["multiplier"]),
            first,
        )
    if first:
        raise ValueError("final Farkas line has no terms")
    return "p " + " ".join(tokens)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("structural_manifest", type=Path)
    parser.add_argument("profile_census", type=Path)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--index", type=int, action="append", required=True)
    parser.add_argument("--cut-plan", type=Path)
    parser.add_argument("--continue-after-plan", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="reuse an existing cut checkpoint, split tree, and exact leaves",
    )
    parser.add_argument("--max-cuts", type=int, default=32)
    parser.add_argument(
        "--cut-subset-size",
        type=int,
        choices=(2, 3),
        default=2,
        help="point-subset size whose integral extension count is cut",
    )
    parser.add_argument("--max-nodes", type=int, default=1000)
    parser.add_argument("--lp-time-limit", type=float, default=5.0)
    parser.add_argument("--leaf-shard-count", type=int, default=1)
    parser.add_argument("--leaf-shard-index", type=int, default=0)
    parser.add_argument("--leaf-only", action="store_true")
    args = parser.parse_args()
    if args.leaf_shard_count <= 0:
        raise ValueError("leaf-shard-count must be positive")
    if not 0 <= args.leaf_shard_index < args.leaf_shard_count:
        raise ValueError("leaf-shard-index is outside the shard count")
    if not args.leaf_only and args.leaf_shard_count != 1:
        raise ValueError("leaf sharding is only valid with --leaf-only")

    import numpy
    import scipy
    import scipy.optimize
    import scipy.sparse

    try:
        import sympy
        from sympy.polys.matrices import DomainMatrix
    except ImportError:
        sympy = None
        DomainMatrix = None

    structural = json.loads(args.structural_manifest.read_text(encoding="utf-8"))
    census = json.loads(args.profile_census.read_text(encoding="utf-8"))
    plans = (
        {}
        if args.cut_plan is None
        else json.loads(args.cut_plan.read_text(encoding="utf-8"))["profiles"]
    )
    if (
        not args.resume
        and args.output_directory.exists()
        and any(args.output_directory.iterdir())
    ):
        raise ValueError("output directory must be empty")
    if args.resume and not args.output_directory.exists():
        raise ValueError("resume output directory does not exist")
    if args.resume and args.cut_plan is not None:
        raise ValueError("resume reconstructs its cut plan from the checkpoint")
    instance_root = args.output_directory / "instances"
    instance_root.mkdir(parents=True, exist_ok=True)

    normalized = structural["input"]["normalized_document"]
    point_labels = tuple(normalized["point_labels"])
    link_blocks = tuple(tuple(block) for block in normalized["blocks"])
    class_index = int(census["class_index"])
    target_candidate_orbit = census.get("target_candidate_orbit")
    sources = {int(row["index"]): row for row in census["profiles"]}
    selected = sorted(set(args.index))
    missing = set(selected) - set(sources)
    if missing:
        raise ValueError(f"unknown profile indices: {sorted(missing)}")

    records = []
    for ordinal, index in enumerate(selected, start=1):
        started = time.monotonic()
        source = sources[index]
        built = build_corrected_formula(
            point_labels, link_blocks, source["extension_degrees"]
        )
        base_rows = built["rows"]
        current_rows = base_rows
        variable_count = int(built["metadata"]["variables"])
        pair_variables = {
            pair: tuple(
                variable
                for variable, block in enumerate(built["extension_blocks"])
                if frozenset(pair) <= frozenset(block)
            )
            for pair in itertools.combinations(
                point_labels, args.cut_subset_size
            )
        }
        name = (
            f"c{class_index:02d}_case{int(source['case_id']):03d}_"
            f"profile{int(source['profile_id']):03d}"
        )
        instance_dir = instance_root / name
        leaf_dir = instance_dir / "leaves"
        leaf_dir.mkdir(parents=True, exist_ok=True)
        formula_bytes = _render_verifier_opb(
            base_rows,
            variable_count=variable_count,
            class_index=class_index,
            orbit_index=(
                None
                if target_candidate_orbit is None
                else int(target_candidate_orbit)
            ),
        )
        formula_path = instance_dir / f"{name}.verifier.opb"
        if args.resume and formula_path.exists():
            if formula_path.read_bytes() != formula_bytes:
                raise ValueError("resume verifier formula does not match")
        else:
            formula_path.write_bytes(formula_bytes)

        prefix = [
            "pseudo-Boolean proof version 1.0",
            f"f {len(base_rows)}",
        ]
        cut_records = []
        resume_expected_cuts = []
        if args.resume:
            checkpoint_path = (
                instance_dir / f"{name}.cut-search.checkpoint.json"
            )
            if checkpoint_path.exists():
                checkpoint = json.loads(
                    checkpoint_path.read_text(encoding="utf-8")
                )
                resume_expected_cuts = checkpoint["derived_pair_cuts"]
            planned = [
                {
                    "pair": cut["pair"],
                    "relation": cut["requested_relation"],
                    "rhs": cut["requested_rhs"],
                }
                for cut in resume_expected_cuts
            ]
        else:
            planned = plans.get(str(index))
        planned_position = 0
        root_solves = 0
        cut_search_lp_tests = 0
        root = _root_lp(
            current_rows,
            variable_count,
            numpy,
            scipy.optimize,
            scipy.sparse,
            args.lp_time_limit,
        )
        root_solves += 1
        if int(root.status) != 0 or root.x is None:
            raise ValueError(
                f"residual index {index} does not start LP feasible: "
                f"status={root.status}, message={root.message}"
            )

        while len(cut_records) < args.max_cuts:
            if planned is not None:
                if (
                    planned_position >= len(planned)
                    and not args.continue_after_plan
                ):
                    break
                if planned_position < len(planned):
                    requested, assumption, discovery = _planned_cut(
                        planned[planned_position], pair_variables
                    )
                    planned_position += 1
                else:
                    found = _discover_pair_cut(
                        current_rows,
                        pair_variables,
                        root,
                        variable_count,
                        numpy,
                        scipy.optimize,
                        scipy.sparse,
                        args.lp_time_limit,
                    )
                    if found is None:
                        break
                    requested, assumption, discovery = found
                    cut_search_lp_tests += int(
                        discovery.get("lp_tests_this_search", 0)
                    )
            else:
                found = _discover_pair_cut(
                    current_rows,
                    pair_variables,
                    root,
                    variable_count,
                    numpy,
                    scipy.optimize,
                    scipy.sparse,
                    args.lp_time_limit,
                )
                if found is None:
                    break
                requested, assumption, discovery = found
                cut_search_lp_tests += int(
                    discovery.get("lp_tests_this_search", 0)
                )

            proof_line, effective, exact = _derive_integral_bound(
                current_rows,
                requested,
                assumption,
                variable_count,
                numpy,
                scipy.optimize,
                scipy.sparse,
            )
            if args.resume:
                expected = resume_expected_cuts[len(cut_records)]
                if (
                    effective.relation != expected["effective_relation"]
                    or effective.rhs != int(expected["effective_rhs"])
                ):
                    raise AssertionError(
                        "resumed exact cut differs from the tree checkpoint"
                    )
            prefix.append(proof_line)
            derived_id = len(current_rows) + 1
            prefix.append(f"e {derived_id} {_normalized_row_text(effective)}")
            current_rows = current_rows + (effective,)
            cut_record = {
                **discovery,
                **exact,
                "derived_constraint_id": derived_id,
            }
            cut_records.append(cut_record)
            if not args.resume:
                write_json(
                    instance_dir / f"{name}.cut-search.checkpoint.json",
                    {
                        "schema_version": (
                            "horizonmath.residual-pair-cut-checkpoint.v1"
                        ),
                        "index": index,
                        "case_id": source["case_id"],
                        "profile_id": source["profile_id"],
                        "derived_pair_cuts": cut_records,
                        "strengthened_constraint_count": len(current_rows),
                        "status": "CUT_SEARCH_IN_PROGRESS",
                    },
                )
            print(
                f"[{ordinal}/{len(selected)}] index={index} "
                f"cut={len(cut_records)} pair={discovery['pair']} "
                f"{effective.relation}{effective.rhs}",
                flush=True,
            )

            root = _root_lp(
                current_rows,
                variable_count,
                numpy,
                scipy.optimize,
                scipy.sparse,
                args.lp_time_limit,
            )
            root_solves += 1
            if int(root.status) == 2:
                break
            if int(root.status) != 0 or root.x is None:
                raise ValueError(
                    f"strengthened root LP indeterminate at index {index}: "
                    f"status={root.status}, message={root.message}"
                )

        if planned is not None and planned_position != len(planned):
            raise ValueError(
                f"max-cuts stopped before planned cuts for index {index}"
            )

        tree = None
        leaf_records = []
        split_metadata = None
        if int(root.status) == 2:
            alternative = _dual_alternative(
                current_rows,
                variable_count,
                numpy,
                scipy.optimize,
                scipy.sparse,
            )
            certificate = _exact_certificate(
                current_rows, variable_count, alternative
            )
            prefix.append(_final_farkas_line(certificate))
            prefix.append(f"c {len(current_rows) + 1}")
            proof_bytes = ("\n".join(prefix) + "\n").encode("utf-8")
            method = "ONE_SIDED_PAIR_CG_THEN_ROOT_FARKAS"
        else:
            print(
                f"[{ordinal}/{len(selected)}] index={index} "
                f"building split tree after {len(cut_records)} cuts",
                flush=True,
            )
            checkpoint_tree_path = instance_dir / f"{name}.split-tree.json"
            if args.resume and checkpoint_tree_path.exists():
                tree = json.loads(
                    checkpoint_tree_path.read_text(encoding="utf-8")
                )
                if (
                    int(tree["variables"]) != variable_count
                    or int(tree["constraints"]) != len(current_rows)
                    or not tree.get("complete")
                ):
                    raise ValueError("resume split tree does not match rows")
                print(
                    f"[{ordinal}/{len(selected)}] index={index} resuming "
                    f"tree nodes={tree['node_count']} leaves={tree['leaf_count']}",
                    flush=True,
                )
            else:
                tree = _build_split_tree(
                    current_rows,
                    variable_count,
                    numpy,
                    scipy.optimize,
                    scipy.sparse,
                    max_nodes=args.max_nodes,
                    lp_time_limit=args.lp_time_limit,
                )
            # Persist the floating search tree before exact leaf work: the tree
            # is not a certificate by itself, but it is an expensive and fully
            # deterministic search artifact worth checkpointing.
            checkpoint_tree_path = instance_dir / f"{name}.split-tree.json"
            if not (args.resume and checkpoint_tree_path.exists()):
                write_json(checkpoint_tree_path, tree)
            nodes = {int(node["id"]): node for node in tree["nodes"]}
            leaf_certificates = {}
            for leaf_ordinal, leaf_id in enumerate(
                sorted(int(value) for value in tree["leaves"]), start=1
            ):
                if (
                    args.leaf_only
                    and (leaf_ordinal - 1) % args.leaf_shard_count
                    != args.leaf_shard_index
                ):
                    continue
                node = nodes[leaf_id]
                leaf_path = leaf_dir / f"leaf_{leaf_id:06d}.json"
                if args.resume and leaf_path.exists():
                    certificate = json.loads(
                        leaf_path.read_text(encoding="utf-8")
                    )
                    if (
                        int(certificate["leaf_id"]) != leaf_id
                        or certificate["assignments"] != node["assignments"]
                        or not all(certificate["exact_checks"].values())
                    ):
                        raise ValueError(
                            f"invalid cached exact leaf {leaf_id}"
                        )
                    leaf_certificates[leaf_id] = certificate
                    leaf_records.append(
                        {
                            "leaf_id": leaf_id,
                            "path": leaf_path.relative_to(
                                args.output_directory
                            ).as_posix(),
                            "sha256": sha256_file(leaf_path),
                            "depth": certificate["depth"],
                            "exact_margin": certificate["exact_margin"],
                        }
                    )
                    if (
                        leaf_ordinal % 10 == 0
                        or leaf_ordinal == len(tree["leaves"])
                    ):
                        print(
                            f"[{ordinal}/{len(selected)}] index={index} "
                            f"exact leaves {leaf_ordinal}/{len(tree['leaves'])} "
                            "(resume)",
                            flush=True,
                        )
                    continue
                assignments = {
                    int(variable) - 1: int(value)
                    for variable, value in node["assignments"].items()
                }
                certificate = None
                errors = []
                for support_threshold in (1e-9, 1e-10, 1e-11, 1e-12, 1e-13):
                    alternative = _leaf_dual_alternative(
                        current_rows,
                        variable_count,
                        assignments,
                        numpy,
                        scipy.optimize,
                        scipy.sparse,
                        support_threshold=support_threshold,
                    )
                    try:
                        certificate = _exact_leaf_certificate(
                            current_rows,
                            variable_count,
                            node,
                            alternative,
                            sympy,
                            DomainMatrix,
                        )
                        certificate["floating_support"][
                            "support_threshold"
                        ] = support_threshold
                        certificate["floating_support"][
                            "threshold_retry_count"
                        ] = len(errors)
                        break
                    except ValueError as exc:
                        errors.append(
                            {
                                "support_threshold": support_threshold,
                                "error": str(exc),
                            }
                        )
                if certificate is None:
                    raise ValueError(
                        f"exact leaf reconstruction failed at leaf {leaf_id}: "
                        f"{errors}"
                    )
                leaf_certificates[leaf_id] = certificate
                write_json(leaf_path, certificate)
                leaf_records.append(
                    {
                        "leaf_id": leaf_id,
                        "path": leaf_path.relative_to(
                            args.output_directory
                        ).as_posix(),
                        "sha256": sha256_file(leaf_path),
                        "depth": certificate["depth"],
                        "exact_margin": certificate["exact_margin"],
                    }
                )
                if leaf_ordinal % 10 == 0 or leaf_ordinal == len(tree["leaves"]):
                    print(
                        f"[{ordinal}/{len(selected)}] index={index} exact leaves "
                        f"{leaf_ordinal}/{len(tree['leaves'])}",
                        flush=True,
                    )
            if args.leaf_only:
                print(
                    json.dumps(
                        {
                            "index": index,
                            "leaf_shard_count": args.leaf_shard_count,
                            "leaf_shard_index": args.leaf_shard_index,
                            "status": "LEAF_SHARD_COMPLETE",
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
                return
            split_proof, split_metadata = _render_split_proof(
                tree,
                leaf_certificates,
                len(current_rows),
            )
            split_lines = split_proof.decode("utf-8").splitlines()
            if split_lines[:2] != [
                "pseudo-Boolean proof version 1.0",
                f"f {len(current_rows)}",
            ]:
                raise AssertionError("unexpected split-proof preamble")
            prefix.extend(split_lines[2:])
            proof_bytes = ("\n".join(prefix) + "\n").encode("utf-8")
            method = "ONE_SIDED_PAIR_CG_THEN_EXACT_LP_SPLIT_FARKAS"

        proof_path = instance_dir / f"{name}.pbp"
        proof_path.write_bytes(proof_bytes)
        tree_record = None
        if tree is not None:
            tree_path = instance_dir / f"{name}.split-tree.json"
            write_json(tree_path, tree)
            tree_record = {
                "path": tree_path.relative_to(
                    args.output_directory
                ).as_posix(),
                "sha256": sha256_file(tree_path),
                "nodes": tree["node_count"],
                "leaves": tree["leaf_count"],
                "max_depth": tree["max_depth"],
            }
        metadata = {
            "schema_version": "horizonmath.residual-pair-split-farkas.v1",
            "index": index,
            "case_id": source["case_id"],
            "profile_id": source["profile_id"],
            "method": method,
            "base_constraint_count": len(base_rows),
            "derived_pair_cut_count": len(cut_records),
            "derived_pair_cuts": cut_records,
            "integral_cut_point_subset_size": args.cut_subset_size,
            "strengthened_constraint_count": len(current_rows),
            "root_lp_solve_count": root_solves,
            "cut_search_lp_test_count": cut_search_lp_tests,
            "tree": tree_record,
            "leaf_certificates": leaf_records,
            "split_proof_metadata": split_metadata,
            "formula": {
                "path": formula_path.relative_to(
                    args.output_directory
                ).as_posix(),
                "sha256": sha256_bytes(formula_bytes),
                "bytes": len(formula_bytes),
            },
            "proof": {
                "path": proof_path.relative_to(
                    args.output_directory
                ).as_posix(),
                "sha256": sha256_bytes(proof_bytes),
                "bytes": len(proof_bytes),
            },
            "seconds": time.monotonic() - started,
            "formal_status": "PROOF_GENERATED_NOT_YET_VERIFIED",
        }
        metadata_path = instance_dir / f"{name}.json"
        write_json(metadata_path, metadata)
        records.append(
            {
                "index": index,
                "case_id": source["case_id"],
                "profile_id": source["profile_id"],
                "method": method,
                "cut_count": len(cut_records),
                "tree": tree_record,
                "formula": metadata["formula"],
                "proof": metadata["proof"],
                "metadata": {
                    "path": metadata_path.relative_to(
                        args.output_directory
                    ).as_posix(),
                    "sha256": sha256_file(metadata_path),
                },
            }
        )
        print(
            f"[{ordinal}/{len(selected)}] index={index} generated "
            f"method={method} cuts={len(cut_records)} "
            f"seconds={metadata['seconds']:.3f}",
            flush=True,
        )

    manifest = {
        "schema_version": "horizonmath.residual-pair-split-farkas-corpus.v1",
        "class_index": class_index,
        "target_candidate_orbit": target_candidate_orbit,
        "profile_census_sha256": sha256_file(args.profile_census),
        "structural_manifest_sha256": sha256_file(args.structural_manifest),
        "cut_plan_sha256": (
            None if args.cut_plan is None else sha256_file(args.cut_plan)
        ),
        "integral_cut_point_subset_size": args.cut_subset_size,
        "instances": records,
        "instance_count": len(records),
        "status": "PROOFS_GENERATED_NOT_YET_VERIFIED",
    }
    manifest_path = args.output_directory / "corpus.manifest.json"
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "instances": len(records),
                "manifest": str(manifest_path),
                "sha256": sha256_file(manifest_path),
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
