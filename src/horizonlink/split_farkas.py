"""Exact LP split-tree/Farkas certificate generation.

Floating-point LP solves choose a complete binary split tree and sparse leaf
supports. Every leaf clause is then reconstructed with positive integer
multipliers and checked in exact arithmetic before a VeriPB proof is emitted.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sys
import warnings
import zipfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from horizonlink.canonical import (
    sha256_file,
    write_json,
    write_sha256_sidecar,
)
from horizonlink.farkas import (
    _one_dimensional_integer_nullspace,
    _render_verifier_opb,
)
from horizonlink.pb import (
    PBRow,
    build_candidate_minimum_set_formula,
    canonical_formula_sha256,
)


SPLIT_FARKAS_MANIFEST_SCHEMA_VERSION = (
    "horizonmath.candidate-lp-split-farkas-corpus.v1"
)
CLASS52_IMMUTABLE_RELEASE_SHA256 = (
    "c4c1ddc812affd9bd05c452855bdfcd614a68906f8bf536fab8bcd4b3123ae56"
)
REFERENCE_SCRIPT_MEMBERS = (
    "Class52_formal_certification_complete/"
    "proof_generation_scripts/build_lp_split_tree.py",
    "Class52_formal_certification_complete/"
    "proof_generation_scripts/extract_leaf_exact_cut.py",
    "Class52_formal_certification_complete/"
    "proof_generation_scripts/extract_leaf_exact_cut_fast.py",
    "Class52_formal_certification_complete/"
    "proof_generation_scripts/build_split_tree_proof_generic.py",
    "Class52_formal_certification_complete/"
    "proof_generation_scripts/certify_remaining_split_trees.py",
)


def _normalized_sign(row: PBRow) -> int:
    return 1 if row.relation == ">=" else -1


def _normalized_lp_system(
    rows: tuple[PBRow, ...],
    variable_count: int,
    numpy_module: Any,
    scipy_sparse: Any,
) -> tuple[Any, Any]:
    matrix_rows: list[int] = []
    matrix_columns: list[int] = []
    matrix_values: list[float] = []
    rhs: list[float] = []
    for row_index, row in enumerate(rows):
        sign = _normalized_sign(row)
        for variable in row.variables:
            matrix_rows.append(row_index)
            matrix_columns.append(variable)
            matrix_values.append(float(sign))
        rhs.append(float(sign * row.rhs))
    matrix = scipy_sparse.coo_matrix(
        (matrix_values, (matrix_rows, matrix_columns)),
        shape=(len(rows), variable_count),
    ).tocsr()
    return matrix, numpy_module.asarray(rhs, dtype=float)


def _solve_node_lp(
    matrix: Any,
    rhs: Any,
    variable_count: int,
    assignments: dict[int, int],
    numpy_module: Any,
    scipy_optimize: Any,
    *,
    time_limit: float,
) -> Any:
    bounds = [(0.0, 1.0)] * variable_count
    for variable, value in assignments.items():
        bounds[variable] = (float(value), float(value))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return scipy_optimize.linprog(
            numpy_module.zeros(variable_count, dtype=float),
            A_ub=-matrix,
            b_ub=-rhs,
            bounds=bounds,
            method="highs-ds",
            options={
                "presolve": True,
                "time_limit": time_limit,
                "primal_feasibility_tolerance": 1e-10,
                "dual_feasibility_tolerance": 1e-10,
                "threads": 1,
                "parallel": "off",
                "random_seed": 0,
            },
        )


def _assignment_document(assignments: dict[int, int]) -> dict[str, int]:
    return {
        str(variable + 1): assignments[variable]
        for variable in sorted(assignments)
    }


def _build_split_tree(
    rows: tuple[PBRow, ...],
    variable_count: int,
    numpy_module: Any,
    scipy_optimize: Any,
    scipy_sparse: Any,
    *,
    max_nodes: int,
    lp_time_limit: float,
) -> dict[str, Any]:
    if max_nodes <= 0:
        raise ValueError("split-tree maximum node count must be positive")
    if lp_time_limit <= 0:
        raise ValueError("split-tree LP time limit must be positive")
    matrix, rhs = _normalized_lp_system(
        rows, variable_count, numpy_module, scipy_sparse
    )
    nodes: list[dict[str, Any]] = []
    leaves: list[int] = []
    solve_count = 0
    # LIFO: push 1 first so child value 0 receives the smaller node id.
    stack: list[
        tuple[int | None, int | None, int | None, dict[int, int], int]
    ] = [(None, None, None, {}, 0)]
    while stack:
        parent, branch_variable, branch_value, assignments, depth = stack.pop()
        if len(nodes) >= max_nodes:
            raise ValueError(
                f"split tree reached the {max_nodes}-node safety limit"
            )
        result = _solve_node_lp(
            matrix,
            rhs,
            variable_count,
            assignments,
            numpy_module,
            scipy_optimize,
            time_limit=lp_time_limit,
        )
        solve_count += 1
        node_id = len(nodes)
        node: dict[str, Any] = {
            "id": node_id,
            "parent": parent,
            "branch_variable": (
                None if branch_variable is None else branch_variable + 1
            ),
            "branch_value": branch_value,
            "depth": depth,
            "assignments": _assignment_document(assignments),
            "lp_reported_status": int(result.status),
        }
        nodes.append(node)
        if int(result.status) == 2:
            node["type"] = "LP_INFEASIBLE_LEAF"
            node["lp_status"] = "SOLVER_UNSAT"
            leaves.append(node_id)
            continue
        if int(result.status) != 0 or result.x is None:
            raise ValueError(
                "split-tree LP did not return feasible or infeasible: "
                f"status={result.status}, message={result.message}"
            )
        fractional = [
            variable
            for variable in range(variable_count)
            if variable not in assignments
            and 1e-7 < float(result.x[variable]) < 1.0 - 1e-7
        ]
        if not fractional:
            ones = [
                variable + 1
                for variable, value in enumerate(result.x)
                if float(value) > 0.5
            ]
            raise ValueError(
                "split-tree LP found an integral feasible assignment; "
                f"selected one-based variables={ones}"
            )
        chosen = min(
            fractional,
            key=lambda variable: (
                abs(float(result.x[variable]) - 0.5),
                variable,
            ),
        )
        node.update(
            {
                "type": "BRANCH",
                "lp_status": "LP_FEASIBLE",
                "chosen_variable": chosen + 1,
                "fractional_variable_count": len(fractional),
                "branch_rule": (
                    "minimum absolute distance to 1/2; "
                    "smallest variable index breaks ties"
                ),
            }
        )
        for value in (1, 0):
            child_assignments = dict(assignments)
            child_assignments[chosen] = value
            stack.append(
                (
                    node_id,
                    chosen,
                    value,
                    child_assignments,
                    depth + 1,
                )
            )

    children: dict[int, dict[int, int]] = {}
    for node in nodes:
        if node["parent"] is not None:
            children.setdefault(int(node["parent"]), {})[
                int(node["branch_value"])
            ] = int(node["id"])
    complete = all(
        node["type"] != "BRANCH"
        or set(children.get(int(node["id"]), {})) == {0, 1}
        for node in nodes
    )
    if not complete:
        raise AssertionError("generated split tree is not complete")
    return {
        "schema_version": "horizonmath.deterministic-lp-split-tree.v1",
        "complete": True,
        "variables": variable_count,
        "constraints": len(rows),
        "nodes": nodes,
        "leaves": leaves,
        "node_count": len(nodes),
        "leaf_count": len(leaves),
        "branch_count": sum(node["type"] == "BRANCH" for node in nodes),
        "solve_count": solve_count,
        "max_depth": max(node["depth"] for node in nodes),
        "solver_configuration": {
            "method": "HiGHS dual simplex through scipy.optimize.linprog",
            "presolve": True,
            "threads": 1,
            "parallel": False,
            "random_seed": 0,
            "primal_feasibility_tolerance": 1e-10,
            "dual_feasibility_tolerance": 1e-10,
            "node_lp_time_limit_seconds": lp_time_limit,
            "maximum_nodes": max_nodes,
        },
        "proof_role": (
            "The floating tree is not a certificate. Every listed leaf must "
            "receive an exact Farkas clause and the clauses must resolve to "
            "the empty root clause."
        ),
    }


def _leaf_dual_alternative(
    rows: tuple[PBRow, ...],
    variable_count: int,
    assignments: dict[int, int],
    numpy_module: Any,
    scipy_optimize: Any,
    scipy_sparse: Any,
) -> dict[str, Any]:
    matrix_rows: list[int] = []
    matrix_columns: list[int] = []
    matrix_values: list[float] = []
    rhs: list[int] = []
    kinds: list[tuple[str, int]] = []
    column = 0
    for row_index, row in enumerate(rows):
        sign = _normalized_sign(row)
        for variable in row.variables:
            matrix_rows.append(variable)
            matrix_columns.append(column)
            matrix_values.append(float(sign))
        rhs.append(sign * row.rhs)
        kinds.append(("row", row_index))
        column += 1
    for variable in range(variable_count):
        matrix_rows.append(variable)
        matrix_columns.append(column)
        matrix_values.append(1.0)
        if assignments.get(variable) == 1:
            rhs.append(1)
            kinds.append(("assume1", variable))
        else:
            rhs.append(0)
            kinds.append(("lower", variable))
        column += 1
    for variable in range(variable_count):
        matrix_rows.append(variable)
        matrix_columns.append(column)
        matrix_values.append(-1.0)
        if assignments.get(variable) == 0:
            rhs.append(0)
            kinds.append(("assume0", variable))
        else:
            rhs.append(-1)
            kinds.append(("upper", variable))
        column += 1

    coefficient_matrix = scipy_sparse.coo_matrix(
        (matrix_values, (matrix_rows, matrix_columns)),
        shape=(variable_count, column),
    ).tocsr()
    equality_matrix = scipy_sparse.vstack(
        [
            coefficient_matrix,
            scipy_sparse.csr_matrix(
                numpy_module.ones((1, column), dtype=float)
            ),
        ],
        format="csr",
    )
    equality_rhs = numpy_module.r_[
        numpy_module.zeros(variable_count), 1.0
    ]
    rhs_vector = numpy_module.asarray(rhs, dtype=float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = scipy_optimize.linprog(
            -rhs_vector,
            A_eq=equality_matrix,
            b_eq=equality_rhs,
            bounds=(0, None),
            method="highs-ds",
            options={
                "presolve": True,
                "primal_feasibility_tolerance": 1e-10,
                "dual_feasibility_tolerance": 1e-10,
                "threads": 1,
                "parallel": "off",
                "random_seed": 0,
            },
        )
    if int(result.status) != 0 or result.x is None:
        raise ValueError(
            "leaf Farkas support LP failed: "
            f"status={result.status}, message={result.message}"
        )
    support = numpy_module.flatnonzero(result.x > 1e-9).tolist()
    margin = float(rhs_vector @ result.x)
    if margin <= 1e-10:
        raise ValueError("floating leaf Farkas alternative has no margin")
    return {
        "coefficient_matrix": coefficient_matrix,
        "rhs": rhs,
        "kinds": kinds,
        "support": support,
        "support_values": [
            float(result.x[column]) for column in support
        ],
        "reported_status": int(result.status),
        "reported_message": str(result.message),
        "support_size": len(support),
    }


def _positive_integer_nullspace(
    equations: list[dict[int, int]],
    column_count: int,
    floating_values: list[float],
    sympy_module: Any | None,
    domain_matrix_class: Any | None,
) -> dict[str, Any]:
    if sympy_module is not None and domain_matrix_class is not None:
        matrix = sympy_module.MutableSparseMatrix(
            len(equations), column_count, {}
        )
        for row_index, equation in enumerate(equations):
            for column, value in equation.items():
                matrix[row_index, column] = value
        nullspace = domain_matrix_class.from_Matrix(matrix).nullspace()
        if nullspace.shape[0] != 1:
            raise ValueError(
                "floating support does not yield a one-dimensional exact "
                f"nullspace: rows={nullspace.shape[0]}, "
                f"columns={column_count}"
            )
        integers = [
            int(value) for value in list(nullspace.to_Matrix().row(0))
        ]
        if all(value < 0 for value in integers):
            integers = [-value for value in integers]
        common_divisor = 0
        for value in integers:
            common_divisor = math.gcd(common_divisor, abs(value))
        if common_divisor == 0:
            raise ValueError("exact nullspace vector is zero")
        integers = [value // common_divisor for value in integers]
        if not all(value > 0 for value in integers):
            raise ValueError(
                "exact nullspace vector is not strictly positive: "
                f"min={min(integers)}, max={max(integers)}"
            )
        if not all(
            sum(
                coefficient * integers[column]
                for column, coefficient in equation.items()
            )
            == 0
            for equation in equations
        ):
            raise AssertionError(
                "integer-domain nullspace vector failed exact equations"
            )
        return {
            "integers": integers,
            "equation_count": len(equations),
            "nonzero_equation_count": len(equations),
            "column_count": column_count,
            "rank": column_count - 1,
            "nullspace_dimension": 1,
            "engine": "SymPy DomainMatrix exact integer nullspace over ZZ",
        }

    if len(floating_values) != column_count:
        raise ValueError("floating support length does not match column count")
    reference = max(floating_values)
    if reference <= 0:
        raise ValueError("floating support has no positive reference value")
    for denominator_limit in (
        10**3,
        10**4,
        10**5,
        10**6,
        10**7,
        10**8,
        10**9,
        10**10,
        10**11,
        10**12,
    ):
        ratios = [
            Fraction(value / reference).limit_denominator(
                denominator_limit
            )
            for value in floating_values
        ]
        common_denominator = 1
        for ratio in ratios:
            common_denominator = math.lcm(
                common_denominator, ratio.denominator
            )
        integers = [
            int(ratio * common_denominator) for ratio in ratios
        ]
        common_divisor = 0
        for value in integers:
            common_divisor = math.gcd(common_divisor, abs(value))
        if common_divisor:
            integers = [value // common_divisor for value in integers]
        if not all(value > 0 for value in integers):
            continue
        if all(
            sum(
                coefficient * integers[column]
                for column, coefficient in equation.items()
            )
            == 0
            for equation in equations
        ):
            return {
                "integers": integers,
                "equation_count": len(equations),
                "nonzero_equation_count": len(equations),
                "column_count": column_count,
                "rank": column_count - 1,
                "nullspace_dimension": 1,
                "engine": (
                    "bounded-denominator reconstruction from floating ray "
                    "with exact integer equation verification"
                ),
                "denominator_limit": denominator_limit,
            }
    fallback = _one_dimensional_integer_nullspace(
        equations, column_count
    )
    fallback["engine"] = (
        "stdlib Fraction sparse elimination fallback after rational "
        "reconstruction attempts"
    )
    return fallback


def _exact_leaf_certificate(
    rows: tuple[PBRow, ...],
    variable_count: int,
    node: dict[str, Any],
    alternative: dict[str, Any],
    sympy_module: Any | None,
    domain_matrix_class: Any | None,
) -> dict[str, Any]:
    support = [int(column) for column in alternative["support"]]
    coefficient_matrix = alternative["coefficient_matrix"].tocsc()
    equations: list[dict[int, int]] = []
    for variable in range(variable_count):
        equation: dict[int, int] = {}
        for position, column in enumerate(support):
            coefficient = int(coefficient_matrix[variable, column])
            if coefficient:
                equation[position] = coefficient
        if equation:
            equations.append(equation)
    nullspace = _positive_integer_nullspace(
        equations,
        len(support),
        alternative["support_values"],
        sympy_module,
        domain_matrix_class,
    )
    multipliers = [int(value) for value in nullspace["integers"]]
    coefficients = [0] * variable_count
    exact_margin = 0
    row_multipliers: list[dict[str, int]] = []
    global_bounds: list[dict[str, int | str]] = []
    assumptions: list[dict[str, int | str]] = []
    for column, multiplier in zip(support, multipliers):
        start = coefficient_matrix.indptr[column]
        end = coefficient_matrix.indptr[column + 1]
        for offset in range(start, end):
            variable = int(coefficient_matrix.indices[offset])
            coefficients[variable] += (
                int(coefficient_matrix.data[offset]) * multiplier
            )
        exact_margin += int(alternative["rhs"][column]) * multiplier
        kind, index = alternative["kinds"][column]
        if kind == "row":
            row_multipliers.append(
                {
                    "row_index_0based": index,
                    "row_id_1based": index + 1,
                    "multiplier": multiplier,
                }
            )
        elif kind in {"lower", "upper"}:
            global_bounds.append(
                {
                    "kind": kind,
                    "variable": index + 1,
                    "multiplier": multiplier,
                }
            )
        elif kind in {"assume0", "assume1"}:
            assumptions.append(
                {
                    "kind": kind,
                    "variable": index + 1,
                    "multiplier": multiplier,
                }
            )
        else:
            raise AssertionError(f"unknown Farkas support kind {kind}")
    if any(coefficients):
        raise AssertionError("exact leaf alternative does not cancel")
    if exact_margin <= 0:
        raise ValueError("exact leaf Farkas margin is not positive")
    if not assumptions:
        raise ValueError("leaf Farkas alternative uses no branch assumption")

    assignments = {
        int(variable): int(value)
        for variable, value in node["assignments"].items()
    }
    assumptions.sort(key=lambda item: int(item["variable"]))
    row_multipliers.sort(key=lambda item: int(item["row_id_1based"]))
    global_bounds.sort(
        key=lambda item: (
            0 if item["kind"] == "lower" else 1,
            int(item["variable"]),
        )
    )
    clause = []
    expected_global_coefficients = [0] * variable_count
    assumed_one_weight = 0
    for item in assumptions:
        variable = int(item["variable"])
        multiplier = int(item["multiplier"])
        kind = str(item["kind"])
        expected_value = 0 if kind == "assume0" else 1
        if assignments.get(variable) != expected_value:
            raise AssertionError("assumption does not match the leaf path")
        if kind == "assume0":
            literal = f"x{variable}"
            expected_global_coefficients[variable - 1] += multiplier
        else:
            literal = f"~x{variable}"
            expected_global_coefficients[variable - 1] -= multiplier
            assumed_one_weight += multiplier
        clause.append(
            {
                "literal": literal,
                "variable": variable,
                "path_value": expected_value,
                "weight_before_division": multiplier,
            }
        )

    global_coefficients = [0] * variable_count
    global_rhs = 0
    for item in row_multipliers:
        row = rows[int(item["row_index_0based"])]
        multiplier = int(item["multiplier"])
        sign = _normalized_sign(row)
        for variable in row.variables:
            global_coefficients[variable] += sign * multiplier
        global_rhs += sign * row.rhs * multiplier
    for item in global_bounds:
        variable = int(item["variable"]) - 1
        multiplier = int(item["multiplier"])
        if item["kind"] == "lower":
            global_coefficients[variable] += multiplier
        else:
            global_coefficients[variable] -= multiplier
            global_rhs -= multiplier
    expected_global_rhs = exact_margin - assumed_one_weight
    exact_checks = {
        "all_support_multipliers_strictly_positive": all(
            multiplier > 0 for multiplier in multipliers
        ),
        "all_variable_coefficients_cancel_with_assumptions": not any(
            coefficients
        ),
        "contradiction_margin_strictly_positive": exact_margin > 0,
        "at_least_one_assumption_multiplier": bool(assumptions),
        "every_assumption_matches_leaf_path": all(
            assignments[int(item["variable"])]
            == (0 if item["kind"] == "assume0" else 1)
            for item in assumptions
        ),
        "global_cut_coefficients_equal_weighted_clause": (
            global_coefficients == expected_global_coefficients
        ),
        "global_cut_rhs_equal_weighted_clause": (
            global_rhs == expected_global_rhs
        ),
        "division_and_saturation_yield_path_clause": all(
            int(item["weight_before_division"]) > 0 for item in clause
        ),
    }
    if not all(exact_checks.values()):
        raise AssertionError("an exact leaf-certificate check failed")
    return {
        "schema_version": "horizonmath.exact-split-leaf-farkas.v1",
        "leaf_id": int(node["id"]),
        "depth": int(node["depth"]),
        "assignments": node["assignments"],
        "floating_support": {
            "reported_status": alternative["reported_status"],
            "reported_message": alternative["reported_message"],
            "support_size": alternative["support_size"],
        },
        "nullspace": {
            key: value
            for key, value in nullspace.items()
            if key not in {"integers", "seconds"}
        },
        "exact_margin": exact_margin,
        "minimum_multiplier": min(multipliers),
        "maximum_multiplier": max(multipliers),
        "row_multipliers": row_multipliers,
        "global_bound_multipliers": global_bounds,
        "assumption_multipliers": assumptions,
        "weighted_clause": clause,
        "clause_literals_after_division": [
            item["literal"] for item in clause
        ],
        "global_cut_linear_form": {
            "nonzero_coefficients": [
                {
                    "variable": variable + 1,
                    "coefficient": coefficient,
                }
                for variable, coefficient in enumerate(global_coefficients)
                if coefficient
            ],
            "rhs": global_rhs,
        },
        "exact_checks": exact_checks,
        "formal_status": "EXACT_ARITHMETIC_CHECKED_NOT_YET_VERIFIED",
    }


def _append_term(
    tokens: list[str], operand: str, multiplier: int, first: bool
) -> bool:
    if multiplier <= 0:
        raise ValueError("proof multipliers must be positive")
    tokens.extend([operand, str(multiplier), "*"])
    if not first:
        tokens.append("+")
    return False


def _literal_matches_assignments(
    literal: str, assignments: dict[int, int]
) -> bool:
    negated = literal.startswith("~")
    variable = int(literal[2:] if negated else literal[1:])
    return (
        variable in assignments
        and assignments[variable] == (1 if negated else 0)
    )


def _render_split_proof(
    tree: dict[str, Any],
    leaf_certificates: dict[int, dict[str, Any]],
    formula_constraint_count: int,
) -> tuple[bytes, dict[str, Any]]:
    nodes = tree["nodes"]
    children: dict[int, dict[int, int]] = {}
    for node in nodes:
        if node["parent"] is not None:
            children.setdefault(int(node["parent"]), {})[
                int(node["branch_value"])
            ] = int(node["id"])
    lines = [
        "pseudo-Boolean proof version 1.0",
        f"f {formula_constraint_count}",
    ]
    next_constraint_id = formula_constraint_count + 1
    node_constraint: dict[int, int] = {}
    node_clause: dict[int, set[str]] = {}
    leaf_records = []
    for leaf_id in sorted(int(value) for value in tree["leaves"]):
        certificate = leaf_certificates[leaf_id]
        tokens: list[str] = []
        first = True
        for item in certificate["row_multipliers"]:
            first = _append_term(
                tokens,
                str(item["row_id_1based"]),
                int(item["multiplier"]),
                first,
            )
        for item in certificate["global_bound_multipliers"]:
            operand = (
                f"x{item['variable']}"
                if item["kind"] == "lower"
                else f"~x{item['variable']}"
            )
            first = _append_term(
                tokens, operand, int(item["multiplier"]), first
            )
        if first:
            raise ValueError("leaf proof line has no globally valid terms")
        margin = int(certificate["exact_margin"])
        tokens.extend([str(margin), "d", "s"])
        lines.append("p " + " ".join(tokens))
        clause = set(certificate["clause_literals_after_division"])
        assignments = {
            int(variable): int(value)
            for variable, value in certificate["assignments"].items()
        }
        if not clause or not all(
            _literal_matches_assignments(literal, assignments)
            for literal in clause
        ):
            raise AssertionError("leaf clause is not falsified by its path")
        node_constraint[leaf_id] = next_constraint_id
        node_clause[leaf_id] = clause
        leaf_records.append(
            {
                "leaf_id": leaf_id,
                "constraint_id": next_constraint_id,
                "depth": int(certificate["depth"]),
                "literal_count": len(clause),
            }
        )
        next_constraint_id += 1

    resolution_records = []
    for node in sorted(
        nodes, key=lambda item: (-int(item["depth"]), int(item["id"]))
    ):
        if node["type"] != "BRANCH":
            continue
        node_id = int(node["id"])
        variable = int(node["chosen_variable"])
        child0 = children[node_id][0]
        child1 = children[node_id][1]
        id0 = node_constraint[child0]
        id1 = node_constraint[child1]
        clause0 = node_clause[child0]
        clause1 = node_clause[child1]
        positive = f"x{variable}"
        negative = f"~x{variable}"
        if positive not in clause0:
            node_constraint[node_id] = id0
            node_clause[node_id] = set(clause0)
            resolution_records.append(
                {
                    "node": node_id,
                    "action": "propagate_child0",
                    "source_constraint_id": id0,
                }
            )
        elif negative not in clause1:
            node_constraint[node_id] = id1
            node_clause[node_id] = set(clause1)
            resolution_records.append(
                {
                    "node": node_id,
                    "action": "propagate_child1",
                    "source_constraint_id": id1,
                }
            )
        else:
            lines.append(f"p {id0} {id1} + s")
            resolvent = (clause0 - {positive}) | (clause1 - {negative})
            node_constraint[node_id] = next_constraint_id
            node_clause[node_id] = resolvent
            resolution_records.append(
                {
                    "node": node_id,
                    "action": "resolve",
                    "variable": variable,
                    "left_constraint_id": id0,
                    "right_constraint_id": id1,
                    "result_constraint_id": next_constraint_id,
                    "result_literal_count": len(resolvent),
                }
            )
            next_constraint_id += 1
        assignments = {
            int(key): int(value)
            for key, value in node["assignments"].items()
        }
        if not all(
            _literal_matches_assignments(literal, assignments)
            for literal in node_clause[node_id]
        ):
            raise AssertionError(
                f"derived node clause is not falsified at node {node_id}"
            )
    root_constraint_id = node_constraint[0]
    if node_clause[0]:
        raise AssertionError("split-tree root clause is not empty")
    lines.append(f"c {root_constraint_id}")
    proof = ("\n".join(lines) + "\n").encode("utf-8")
    metadata = {
        "formula_constraint_count": formula_constraint_count,
        "tree_node_count": len(nodes),
        "leaf_clause_count": len(leaf_records),
        "resolution_step_count": sum(
            item["action"] == "resolve" for item in resolution_records
        ),
        "propagation_count": sum(
            item["action"] != "resolve" for item in resolution_records
        ),
        "final_contradiction_id": root_constraint_id,
        "proof_line_count": len(lines),
        "leaf_records": leaf_records,
        "resolution_records": resolution_records,
        "exact_tree_resolution_checks": {
            "every_branch_has_two_children": all(
                node["type"] != "BRANCH"
                or set(children.get(int(node["id"]), {})) == {0, 1}
                for node in nodes
            ),
            "every_leaf_has_exact_clause": (
                set(leaf_certificates)
                == {int(value) for value in tree["leaves"]}
            ),
            "root_clause_is_empty": not node_clause[0],
        },
    }
    return proof, metadata


def _reference_provenance(
    release_archive: Path | None, class_index: int
) -> dict[str, Any] | None:
    if release_archive is None:
        return None
    archive_hash = sha256_file(release_archive)
    if (
        class_index == 52
        and archive_hash != CLASS52_IMMUTABLE_RELEASE_SHA256
    ):
        raise ValueError(
            "class-52 reference archive hash does not match the immutable "
            "published release"
        )
    with zipfile.ZipFile(release_archive) as archive:
        names = set(archive.namelist())
        missing = [
            member for member in REFERENCE_SCRIPT_MEMBERS if member not in names
        ]
        if missing:
            raise ValueError(
                "reference release is missing split-proof source scripts: "
                + ", ".join(missing)
            )
        scripts = [
            {
                "archive_member": member,
                "sha256": hashlib.sha256(archive.read(member)).hexdigest(),
            }
            for member in REFERENCE_SCRIPT_MEMBERS
        ]
    return {
        "archive_file_name": release_archive.name,
        "archive_sha256": archive_hash,
        "immutable_class52_release_hash_matches": (
            class_index != 52
            or archive_hash == CLASS52_IMMUTABLE_RELEASE_SHA256
        ),
        "source_scripts": scripts,
        "use": (
            "Mechanism audit only. The implementation in horizonlink is "
            "class-agnostic and does not execute or copy class-number-specific "
            "release scripts."
        ),
    }


def _write_checksums(output_directory: Path) -> None:
    targets = sorted(
        (
            path
            for path in output_directory.rglob("*")
            if path.is_file()
            and path.name != "SHA256SUMS"
            and not path.name.endswith(".sha256")
        ),
        key=lambda path: path.relative_to(output_directory).as_posix(),
    )
    (output_directory / "SHA256SUMS").write_text(
        "".join(
            f"{sha256_file(path)}  "
            f"{path.relative_to(output_directory).as_posix()}\n"
            for path in targets
        ),
        encoding="utf-8",
    )


def generate_lp_split_farkas_corpus(
    structural_manifest: dict[str, Any],
    candidate_corpus_directory: Path,
    solver_manifest_path: Path,
    output_directory: Path,
    *,
    orbit_indices: Iterable[int] | None = None,
    max_nodes: int = 5000,
    lp_time_limit: float = 30.0,
    reference_release_archive: Path | None = None,
    dependency_wheels: Iterable[Path] | None = None,
) -> dict[str, Any]:
    """Generate complete exact split-tree refutations for selected screens."""

    try:
        import numpy
        import scipy
        import scipy.optimize
        import scipy.sparse
    except ImportError as exc:
        raise RuntimeError(
            "split-tree Farkas generation requires NumPy and SciPy"
        ) from exc
    try:
        import sympy
        from sympy.polys.matrices import DomainMatrix
    except ImportError:
        sympy = None
        DomainMatrix = None

    if structural_manifest.get("status") != "ENUMERATED":
        raise ValueError("structural manifest must be ENUMERATED")
    if output_directory.exists() and any(output_directory.iterdir()):
        raise ValueError("split-Farkas output directory must be empty")
    candidate_manifest_path = (
        candidate_corpus_directory / "corpus.manifest.json"
    )
    candidate = json.loads(
        candidate_manifest_path.read_text(encoding="utf-8")
    )
    solver = json.loads(solver_manifest_path.read_text(encoding="utf-8"))
    if candidate.get("status") != "FORMULAS_GENERATED":
        raise ValueError("candidate corpus must be FORMULAS_GENERATED")
    link_hash = structural_manifest["input"][
        "canonical_labeled_link_sha256"
    ]
    if (
        candidate.get("input", {}).get("canonical_labeled_link_sha256")
        != link_hash
        or solver.get("input", {}).get("canonical_labeled_link_sha256")
        != link_hash
    ):
        raise ValueError("input link hashes do not agree")
    candidate_manifest_hash = sha256_file(candidate_manifest_path)
    if (
        solver.get("input", {}).get("corpus_manifest_sha256")
        != candidate_manifest_hash
    ):
        raise ValueError("solver manifest references a different corpus")

    candidate_records = {
        int(record["orbit_index"]): record
        for record in candidate["instances"]
    }
    solver_records = {
        int(record["orbit_index"]): record
        for record in solver["instances"]
    }
    eligible = tuple(
        sorted(
            orbit_index
            for orbit_index, record in solver_records.items()
            if record.get("root_lp", {}).get("status") == "LP_FEASIBLE"
            and record.get("mip", {}).get("status") == "SOLVER_UNSAT"
        )
    )
    selected = (
        eligible
        if orbit_indices is None
        else tuple(sorted(set(int(index) for index in orbit_indices)))
    )
    if not selected:
        raise ValueError("no split-tree orbit was selected")
    if not set(selected) <= set(eligible):
        raise ValueError(
            "selected orbits must be root-LP feasible and MILP SOLVER_UNSAT"
        )

    normalized = structural_manifest["input"]["normalized_document"]
    point_labels = tuple(normalized["point_labels"])
    link_blocks = tuple(tuple(block) for block in normalized["blocks"])
    orbit_rows = structural_manifest["candidate_minimum_point_sets"][
        "orbits"
    ]
    class_index = int(structural_manifest["input"]["class_index"])
    provenance = _reference_provenance(
        reference_release_archive, class_index
    )
    dependency_records = [
        {
            "file_name": path.name,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(
            (Path(path) for path in (dependency_wheels or ())),
            key=lambda path: path.name,
        )
    ]
    output_directory.mkdir(parents=True, exist_ok=True)
    instance_root = output_directory / "instances"
    instance_root.mkdir(parents=True, exist_ok=True)
    records = []
    for orbit_index in selected:
        formula_record = candidate_records[orbit_index]
        solver_record = solver_records[orbit_index]
        representative = tuple(orbit_rows[orbit_index]["representative"])
        source_formula_path = (
            candidate_corpus_directory / formula_record["formula"]["path"]
        )
        source_formula_hash = sha256_file(source_formula_path)
        if source_formula_hash != formula_record["formula"]["sha256"]:
            raise ValueError(f"source formula hash mismatch at orbit {orbit_index}")
        built = build_candidate_minimum_set_formula(
            point_labels, link_blocks, representative
        )
        canonical_hash = canonical_formula_sha256(
            built["rows"],
            variable_count=built["metadata"]["variables"],
        )
        if (
            canonical_hash
            != formula_record["formula"]["canonical_formula_sha256"]
        ):
            raise ValueError(
                f"canonical formula hash mismatch at orbit {orbit_index}"
            )
        name = formula_record["name"]
        instance_directory = instance_root / name
        instance_directory.mkdir(parents=True, exist_ok=True)
        leaf_directory = instance_directory / "leaves"
        leaf_directory.mkdir(parents=True, exist_ok=True)
        verifier_formula_path = (
            instance_directory / f"{name}.split-farkas.opb"
        )
        verifier_formula_path.write_bytes(
            _render_verifier_opb(
                built["rows"],
                variable_count=built["metadata"]["variables"],
                class_index=class_index,
                orbit_index=orbit_index,
            )
        )
        tree = _build_split_tree(
            built["rows"],
            built["metadata"]["variables"],
            numpy,
            scipy.optimize,
            scipy.sparse,
            max_nodes=max_nodes,
            lp_time_limit=lp_time_limit,
        )
        tree.update(
            {
                "class_index": class_index,
                "orbit_index": orbit_index,
                "candidate_minimum_points": list(representative),
                "source_formula_sha256": source_formula_hash,
                "canonical_formula_sha256": canonical_hash,
            }
        )
        tree_path = instance_directory / f"{name}.split-tree.json"
        write_json(tree_path, tree)

        nodes = {int(node["id"]): node for node in tree["nodes"]}
        leaf_certificates: dict[int, dict[str, Any]] = {}
        leaf_records = []
        for leaf_id in sorted(int(value) for value in tree["leaves"]):
            node = nodes[leaf_id]
            assignments = {
                int(variable) - 1: int(value)
                for variable, value in node["assignments"].items()
            }
            alternative = _leaf_dual_alternative(
                built["rows"],
                built["metadata"]["variables"],
                assignments,
                numpy,
                scipy.optimize,
                scipy.sparse,
            )
            certificate = _exact_leaf_certificate(
                built["rows"],
                built["metadata"]["variables"],
                node,
                alternative,
                sympy,
                DomainMatrix,
            )
            leaf_path = leaf_directory / f"leaf_{leaf_id:06d}.json"
            write_json(leaf_path, certificate)
            leaf_certificates[leaf_id] = certificate
            leaf_records.append(
                {
                    "leaf_id": leaf_id,
                    "depth": certificate["depth"],
                    "path": leaf_path.relative_to(
                        output_directory
                    ).as_posix(),
                    "sha256": sha256_file(leaf_path),
                    "exact_margin": certificate["exact_margin"],
                    "clause_literal_count": len(
                        certificate["clause_literals_after_division"]
                    ),
                    "all_exact_checks_passed": all(
                        certificate["exact_checks"].values()
                    ),
                }
            )

        proof, proof_metadata = _render_split_proof(
            tree,
            leaf_certificates,
            built["metadata"]["opb_constraints"],
        )
        proof_path = instance_directory / f"{name}.split-farkas.pbp"
        proof_path.write_bytes(proof)
        proof_metadata.update(
            {
                "formula_sha256": sha256_file(verifier_formula_path),
                "tree_sha256": sha256_file(tree_path),
                "proof_sha256": sha256_file(proof_path),
                "proof_bytes": proof_path.stat().st_size,
            }
        )
        proof_metadata_path = (
            instance_directory / f"{name}.split-proof-metadata.json"
        )
        write_json(proof_metadata_path, proof_metadata)
        historical_comparison = solver_record.get("historical_comparison")
        certificate_record = {
            "schema_version": (
                "horizonmath.exact-lp-split-farkas-certificate.v1"
            ),
            "class_index": class_index,
            "orbit_index": orbit_index,
            "candidate_minimum_points": list(representative),
            "method": {
                "id": "exact-lp-split-tree-farkas-veripb-v1",
                "root_lp_status": "LP_FEASIBLE",
                "milp_status": "SOLVER_UNSAT",
            },
            "source_formula": {
                "path": formula_record["formula"]["path"],
                "path_base": "candidate_corpus_directory",
                "sha256": source_formula_hash,
                "canonical_formula_sha256": canonical_hash,
            },
            "formula": {
                "path": verifier_formula_path.relative_to(
                    output_directory
                ).as_posix(),
                "sha256": sha256_file(verifier_formula_path),
                "canonical_formula_sha256": canonical_hash,
                "constraint_count": built["metadata"]["opb_constraints"],
                "variable_count": built["metadata"]["variables"],
                "canonical_equivalent_to_source_formula": True,
            },
            "tree": {
                "path": tree_path.relative_to(
                    output_directory
                ).as_posix(),
                "sha256": sha256_file(tree_path),
                "complete": tree["complete"],
                "node_count": tree["node_count"],
                "leaf_count": tree["leaf_count"],
                "branch_count": tree["branch_count"],
                "max_depth": tree["max_depth"],
            },
            "leaf_certificates": leaf_records,
            "proof": {
                "path": proof_path.relative_to(
                    output_directory
                ).as_posix(),
                "sha256": sha256_file(proof_path),
                "bytes": proof_path.stat().st_size,
                "format": "VeriPB pseudo-Boolean proof version 1.0",
                "expected_contradiction_id": proof_metadata[
                    "final_contradiction_id"
                ],
                "metadata": {
                    "path": proof_metadata_path.relative_to(
                        output_directory
                    ).as_posix(),
                    "sha256": sha256_file(proof_metadata_path),
                },
            },
            "historical_comparison": historical_comparison,
            "historical_disposition_differs_from_fresh_solver": bool(
                historical_comparison
                and historical_comparison.get("equal") is False
            ),
            "status": "PROOF_GENERATED",
            "status_ledger": {
                "formula": "FORMULAS_GENERATED",
                "root_lp": "LP_FEASIBLE",
                "solver": "SOLVER_UNSAT",
                "split_tree": "ENUMERATED",
                "proof": "PROOF_GENERATED",
                "verification": "NOT_STARTED",
            },
            "formal_pruning_authorized": False,
            "guardrail": (
                "The tree and leaf arithmetic are exact, but formal pruning "
                "requires expected hash matches and a successful VeriPB run "
                "with --requireUnsat."
            ),
        }
        certificate_path = instance_directory / f"{name}.split-farkas.json"
        write_json(certificate_path, certificate_record)
        certificate_record["certificate_artifact"] = {
            "path": certificate_path.relative_to(
                output_directory
            ).as_posix(),
            "sha256": sha256_file(certificate_path),
        }
        generation_log = instance_directory / f"{name}.generation.log"
        generation_log.write_text(
            "\n".join(
                [
                    f"class_index={class_index}",
                    f"orbit_index={orbit_index}",
                    f"source_formula_sha256={source_formula_hash}",
                    f"canonical_formula_sha256={canonical_hash}",
                    f"tree_sha256={sha256_file(tree_path)}",
                    f"tree_nodes={tree['node_count']}",
                    f"tree_leaves={tree['leaf_count']}",
                    f"tree_max_depth={tree['max_depth']}",
                    f"proof_sha256={sha256_file(proof_path)}",
                    f"proof_bytes={proof_path.stat().st_size}",
                    "status=PROOF_GENERATED",
                    "formal_pruning_authorized=false",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        certificate_record["generation_log"] = {
            "path": generation_log.relative_to(
                output_directory
            ).as_posix(),
            "sha256": sha256_file(generation_log),
        }
        records.append(certificate_record)

    manifest = {
        "schema_version": SPLIT_FARKAS_MANIFEST_SCHEMA_VERSION,
        "status": "PROOF_GENERATED",
        "input": {
            "class_index": class_index,
            "canonical_labeled_link_sha256": link_hash,
            "candidate_corpus_manifest": {
                "path": os.path.relpath(
                    candidate_manifest_path, output_directory
                ),
                "sha256": candidate_manifest_hash,
            },
            "solver_manifest": {
                "path": os.path.relpath(
                    solver_manifest_path, output_directory
                ),
                "sha256": sha256_file(solver_manifest_path),
            },
            "selected_orbits": list(selected),
            "eligible_orbits": list(eligible),
        },
        "reference_provenance": provenance,
        "dependency_artifacts": dependency_records,
        "method": {
            "id": "exact-lp-split-tree-farkas-veripb-v1",
            "tree_stage": (
                "deterministic HiGHS dual-simplex binary splitting on the "
                "most fractional unassigned variable"
            ),
            "leaf_stage": (
                "floating support extraction followed by stdlib Fraction "
                "sparse elimination and primitive positive integer "
                "multipliers"
            ),
            "proof_stage": (
                "one exact Farkas-derived path clause per LP-infeasible leaf; "
                "bottom-up cutting-planes resolution to the empty root clause"
            ),
            "floating_results_are_not_formal": True,
            "formal_arithmetic": "exact Python integers and Fraction",
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": numpy.__version__,
            "scipy": scipy.__version__,
            "sympy": None if sympy is None else sympy.__version__,
        },
        "instances": records,
        "summary": {
            "eligible_orbits": len(eligible),
            "selected_orbits": len(selected),
            "complete_split_trees": sum(
                record["tree"]["complete"] for record in records
            ),
            "tree_nodes": sum(
                record["tree"]["node_count"] for record in records
            ),
            "exact_leaf_certificates": sum(
                record["tree"]["leaf_count"] for record in records
            ),
            "proofs_generated": len(records),
            "verified_unsat": 0,
            "formal_pruning_authorized": 0,
        },
        "scope": {
            "proofs_generated": True,
            "verifier_run": False,
            "formal_orbit_pruning_authorized": False,
            "class_elimination_claimed": False,
            "C_13_7_4_equals_30_claimed": False,
        },
    }
    manifest_path = output_directory / "farkas_corpus.manifest.json"
    write_json(manifest_path, manifest)
    write_sha256_sidecar(manifest_path)
    _write_checksums(output_directory)
    return manifest
