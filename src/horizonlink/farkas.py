"""Exact root-LP Farkas certificate and VeriPB proof generation."""

from __future__ import annotations

import json
import math
import os
import platform
import sys
import time
import warnings
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from horizonlink.canonical import (
    sha256_file,
    write_json,
    write_sha256_sidecar,
)
from horizonlink.pb import (
    PBRow,
    build_candidate_minimum_set_formula,
    canonical_formula_sha256,
)


FARKAS_MANIFEST_SCHEMA_VERSION = (
    "horizonmath.candidate-root-lp-farkas-corpus.v1"
)


def _normalized_sign(row: PBRow) -> int:
    return 1 if row.relation == ">=" else -1


def _dual_alternative(
    rows: tuple[PBRow, ...],
    variable_count: int,
    numpy_module: Any,
    scipy_optimize: Any,
    scipy_sparse: Any,
) -> dict[str, Any]:
    """Find a sparse floating support for an exact Farkas alternative."""

    matrix_rows: list[int] = []
    matrix_columns: list[int] = []
    matrix_values: list[float] = []
    rhs: list[float] = []
    kinds: list[tuple[str, int]] = []
    column = 0
    for row_index, row in enumerate(rows):
        sign = _normalized_sign(row)
        for variable in row.variables:
            matrix_rows.append(variable)
            matrix_columns.append(column)
            matrix_values.append(float(sign))
        rhs.append(float(sign * row.rhs))
        kinds.append(("row", row_index))
        column += 1
    for variable in range(variable_count):
        matrix_rows.append(variable)
        matrix_columns.append(column)
        matrix_values.append(1.0)
        rhs.append(0.0)
        kinds.append(("lower", variable))
        column += 1
    for variable in range(variable_count):
        matrix_rows.append(variable)
        matrix_columns.append(column)
        matrix_values.append(-1.0)
        rhs.append(-1.0)
        kinds.append(("upper", variable))
        column += 1

    coefficient_matrix = scipy_sparse.coo_matrix(
        (matrix_values, (matrix_rows, matrix_columns)),
        shape=(variable_count, column),
    ).tocsr()
    rhs_vector = numpy_module.asarray(rhs, dtype=float)
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
    started = time.monotonic()
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
    seconds = time.monotonic() - started
    if int(result.status) != 0 or result.x is None:
        raise ValueError(
            "Farkas alternative LP failed: "
            f"{result.status}: {result.message}"
        )
    support = numpy_module.flatnonzero(result.x > 1e-9).tolist()
    formula_columns = [
        column_index
        for column_index in support
        if kinds[column_index][0] == "row"
    ]
    lower_variables = {
        kinds[column_index][1]
        for column_index in support
        if kinds[column_index][0] == "lower"
    }
    upper_variables = {
        kinds[column_index][1]
        for column_index in support
        if kinds[column_index][0] == "upper"
    }
    active_variables = [
        variable
        for variable in range(variable_count)
        if variable not in lower_variables
        and variable not in upper_variables
    ]
    margin = float(rhs_vector @ result.x)
    if margin <= 1e-10:
        raise ValueError("floating Farkas alternative has no positive margin")
    return {
        "coefficient_matrix": coefficient_matrix,
        "rhs_vector": rhs_vector,
        "kinds": kinds,
        "support": support,
        "formula_columns": formula_columns,
        "floating_lower_variables": sorted(lower_variables),
        "floating_upper_variables": sorted(upper_variables),
        "active_variables": active_variables,
        "seconds": seconds,
        "reported_status": int(result.status),
        "reported_message": str(result.message),
        "margin": margin,
        "support_size": len(support),
        "formula_support_size": len(formula_columns),
    }


def _one_dimensional_integer_nullspace(
    equations: list[dict[int, int]], column_count: int
) -> dict[str, Any]:
    """Compute a primitive integer null vector using exact sparse elimination."""

    matrix = [
        {
            column: Fraction(value)
            for column, value in row.items()
            if value
        }
        for row in equations
        if row
    ]
    row_count = len(matrix)
    pivot_row = 0
    pivot_columns: list[int] = []
    started = time.monotonic()
    for column in range(column_count):
        candidate = next(
            (
                row_index
                for row_index in range(pivot_row, row_count)
                if matrix[row_index].get(column, 0)
            ),
            None,
        )
        if candidate is None:
            continue
        matrix[pivot_row], matrix[candidate] = (
            matrix[candidate],
            matrix[pivot_row],
        )
        pivot_value = matrix[pivot_row][column]
        if pivot_value != 1:
            matrix[pivot_row] = {
                index: value / pivot_value
                for index, value in matrix[pivot_row].items()
            }
        normalized_pivot = matrix[pivot_row]
        for row_index in range(pivot_row + 1, row_count):
            factor = matrix[row_index].get(column, 0)
            if not factor:
                continue
            reduced = dict(matrix[row_index])
            for index, value in normalized_pivot.items():
                replacement = reduced.get(index, Fraction(0)) - (
                    factor * value
                )
                if replacement:
                    reduced[index] = replacement
                else:
                    reduced.pop(index, None)
            matrix[row_index] = reduced
        pivot_columns.append(column)
        pivot_row += 1
        if pivot_row == row_count:
            break

    free_columns = sorted(set(range(column_count)) - set(pivot_columns))
    if len(free_columns) != 1:
        raise ValueError(
            "floating support does not yield a one-dimensional exact "
            f"nullspace: rank={len(pivot_columns)}, "
            f"columns={column_count}, free={len(free_columns)}"
        )
    vector = [Fraction(0) for _ in range(column_count)]
    vector[free_columns[0]] = Fraction(1)
    for row_index in range(len(pivot_columns) - 1, -1, -1):
        column = pivot_columns[row_index]
        row = matrix[row_index]
        vector[column] = -sum(
            value * vector[index]
            for index, value in row.items()
            if index != column
        )

    common_denominator = 1
    for value in vector:
        common_denominator = math.lcm(
            common_denominator, value.denominator
        )
    integers = [
        int(value * common_denominator) for value in vector
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
    return {
        "integers": integers,
        "equation_count": len(equations),
        "nonzero_equation_count": row_count,
        "column_count": column_count,
        "rank": len(pivot_columns),
        "nullspace_dimension": 1,
        "free_column": free_columns[0],
        "seconds": time.monotonic() - started,
    }


def _exact_certificate(
    rows: tuple[PBRow, ...],
    variable_count: int,
    alternative: dict[str, Any],
) -> dict[str, Any]:
    formula_columns = alternative["formula_columns"]
    active_variables = alternative["active_variables"]
    support_position = {
        column: position
        for position, column in enumerate(formula_columns)
    }
    equations: list[dict[int, int]] = []
    for variable in active_variables:
        equation: dict[int, int] = {}
        for column in formula_columns:
            row = rows[column]
            if variable in row.variables:
                equation[support_position[column]] = _normalized_sign(row)
        if equation:
            equations.append(equation)
    nullspace = _one_dimensional_integer_nullspace(
        equations, len(formula_columns)
    )
    multipliers = nullspace["integers"]

    coefficients = [0] * variable_count
    combined_rhs_before_bounds = 0
    row_multipliers = []
    for row_index, multiplier in zip(formula_columns, multipliers):
        row = rows[row_index]
        sign = _normalized_sign(row)
        for variable in row.variables:
            coefficients[variable] += sign * multiplier
        combined_rhs_before_bounds += sign * row.rhs * multiplier
        row_multipliers.append(
            {
                "row_index_0based": row_index,
                "row_id_1based": row_index + 1,
                "multiplier": multiplier,
            }
        )

    lower_bounds = []
    upper_bounds = []
    combined_rhs = combined_rhs_before_bounds
    for variable, coefficient in enumerate(coefficients):
        if coefficient < 0:
            lower_bounds.append(
                {
                    "variable": variable + 1,
                    "multiplier": -coefficient,
                }
            )
        elif coefficient > 0:
            upper_bounds.append(
                {
                    "variable": variable + 1,
                    "multiplier": coefficient,
                }
            )
            combined_rhs -= coefficient
    if combined_rhs <= 0:
        raise ValueError(
            f"exact Farkas contradiction margin is not positive: {combined_rhs}"
        )

    residual_coefficients = list(coefficients)
    for item in lower_bounds:
        residual_coefficients[item["variable"] - 1] += item["multiplier"]
    for item in upper_bounds:
        residual_coefficients[item["variable"] - 1] -= item["multiplier"]
    if any(residual_coefficients):
        raise AssertionError("Boolean bounds did not cancel all coefficients")

    return {
        "row_multipliers": row_multipliers,
        "lower_bound_multipliers": lower_bounds,
        "upper_bound_multipliers": upper_bounds,
        "combined_lhs_coefficients_before_bounds": [
            {
                "variable": variable + 1,
                "coefficient": coefficient,
            }
            for variable, coefficient in enumerate(coefficients)
            if coefficient
        ],
        "combined_rhs_before_bounds": combined_rhs_before_bounds,
        "combined_rhs_after_bounds": combined_rhs,
        "nullspace": {
            key: value
            for key, value in nullspace.items()
            if key not in {"integers", "seconds"}
        },
        "exact_checks": {
            "all_row_multipliers_strictly_positive": all(
                item["multiplier"] > 0 for item in row_multipliers
            ),
            "all_bound_multipliers_strictly_positive": all(
                item["multiplier"] > 0
                for item in lower_bounds + upper_bounds
            ),
            "all_variable_coefficients_cancel": not any(
                residual_coefficients
            ),
            "contradiction_rhs_strictly_positive": combined_rhs > 0,
        },
    }


def _render_veripb_proof(
    certificate: dict[str, Any], formula_constraint_count: int
) -> bytes:
    tokens: list[str] = []
    first = True

    def append_term(operand: str, multiplier: int) -> None:
        nonlocal first
        tokens.extend([operand, str(multiplier), "*"])
        if not first:
            tokens.append("+")
        first = False

    for item in certificate["row_multipliers"]:
        append_term(str(item["row_id_1based"]), item["multiplier"])
    for item in certificate["lower_bound_multipliers"]:
        append_term(f"x{item['variable']}", item["multiplier"])
    for item in certificate["upper_bound_multipliers"]:
        append_term(f"~x{item['variable']}", item["multiplier"])
    if first:
        raise ValueError("cannot render an empty Farkas proof")
    contradiction_id = formula_constraint_count + 1
    lines = [
        "pseudo-Boolean proof version 1.0",
        f"f {formula_constraint_count}",
        "p " + " ".join(tokens),
        f"c {contradiction_id}",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _render_verifier_opb(
    rows: tuple[PBRow, ...],
    *,
    variable_count: int,
    class_index: int,
    orbit_index: int,
) -> bytes:
    """Render the all->= OPB syntax accepted by the bundled VeriPB release."""

    lines = [
        f"* #variable= {variable_count} #constraint= {len(rows)}",
        (
            f"* class {class_index} candidate-minimum-point orbit "
            f"{orbit_index}"
        ),
        (
            "* verifier-normalized from the native screen; row order and "
            "constraint ids preserved"
        ),
    ]
    for row in rows:
        coefficient = 1 if row.relation == ">=" else -1
        rhs = row.rhs if row.relation == ">=" else -row.rhs
        terms = " ".join(
            f"{coefficient:+d} x{variable + 1}"
            for variable in row.variables
        )
        lines.append(f"{terms} >= {rhs} ;")
    return ("\n".join(lines) + "\n").encode("utf-8")


def generate_root_lp_farkas_corpus(
    structural_manifest: dict[str, Any],
    candidate_corpus_directory: Path,
    solver_manifest_path: Path,
    output_directory: Path,
    *,
    orbit_indices: Iterable[int] | None = None,
) -> dict[str, Any]:
    """Generate exact direct Farkas proofs for root-LP-infeasible orbits."""

    try:
        import numpy
        import scipy
        import scipy.optimize
        import scipy.sparse
    except ImportError as exc:
        raise RuntimeError(
            "Farkas support extraction requires NumPy and SciPy"
        ) from exc

    if structural_manifest.get("status") != "ENUMERATED":
        raise ValueError("structural manifest must be ENUMERATED")
    if output_directory.exists() and any(output_directory.iterdir()):
        raise ValueError("Farkas output directory must be empty")
    corpus_path = candidate_corpus_directory / "corpus.manifest.json"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    if corpus.get("status") != "FORMULAS_GENERATED":
        raise ValueError("candidate screening corpus must be FORMULAS_GENERATED")
    solver_manifest = json.loads(
        solver_manifest_path.read_text(encoding="utf-8")
    )
    structural_link_hash = structural_manifest["input"][
        "canonical_labeled_link_sha256"
    ]
    corpus_hash = sha256_file(corpus_path)
    if (
        corpus.get("input", {}).get("canonical_labeled_link_sha256")
        != structural_link_hash
    ):
        raise ValueError("candidate corpus link hash does not match input link")
    if (
        solver_manifest.get("input", {}).get(
            "canonical_labeled_link_sha256"
        )
        != structural_link_hash
    ):
        raise ValueError("solver manifest link hash does not match input link")
    if (
        solver_manifest.get("input", {}).get("corpus_manifest_sha256")
        != corpus_hash
    ):
        raise ValueError(
            "solver manifest does not reference the supplied candidate corpus"
        )
    solver_records = {
        int(record["orbit_index"]): record
        for record in solver_manifest["instances"]
    }
    root_unsat = tuple(
        sorted(
            orbit_index
            for orbit_index, record in solver_records.items()
            if record.get("root_lp", {}).get("status") == "SOLVER_UNSAT"
        )
    )
    selected_orbits = (
        root_unsat
        if orbit_indices is None
        else tuple(sorted(set(int(index) for index in orbit_indices)))
    )
    if not selected_orbits:
        raise ValueError("no root-LP-infeasible orbit was selected")
    if not set(selected_orbits) <= set(root_unsat):
        raise ValueError(
            "every selected orbit must have fresh root LP status SOLVER_UNSAT"
        )

    normalized = structural_manifest["input"]["normalized_document"]
    point_labels = tuple(normalized["point_labels"])
    link_blocks = tuple(tuple(block) for block in normalized["blocks"])
    orbit_rows = structural_manifest["candidate_minimum_point_sets"][
        "orbits"
    ]
    formula_records = {
        int(record["orbit_index"]): record
        for record in corpus["instances"]
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    instance_directory = output_directory / "instances"
    instance_directory.mkdir(parents=True, exist_ok=True)
    records = []
    for orbit_index in selected_orbits:
        representative = tuple(orbit_rows[orbit_index]["representative"])
        formula_record = formula_records[orbit_index]
        solver_record = solver_records[orbit_index]
        source_formula_path = (
            candidate_corpus_directory / formula_record["formula"]["path"]
        )
        actual_formula_hash = sha256_file(source_formula_path)
        if actual_formula_hash != formula_record["formula"]["sha256"]:
            raise ValueError(f"formula hash mismatch for orbit {orbit_index}")
        if (
            solver_record.get("formula", {}).get("actual_sha256")
            != actual_formula_hash
        ):
            raise ValueError(
                f"solver formula hash mismatch for orbit {orbit_index}"
            )
        built = build_candidate_minimum_set_formula(
            point_labels, link_blocks, representative
        )
        rebuilt_canonical_hash = canonical_formula_sha256(
            built["rows"],
            variable_count=built["metadata"]["variables"],
        )
        if (
            rebuilt_canonical_hash
            != formula_record["formula"]["canonical_formula_sha256"]
        ):
            raise ValueError(
                f"canonical formula hash mismatch for orbit {orbit_index}"
            )

        alternative = _dual_alternative(
            built["rows"],
            built["metadata"]["variables"],
            numpy,
            scipy.optimize,
            scipy.sparse,
        )
        exact = _exact_certificate(
            built["rows"], built["metadata"]["variables"], alternative
        )
        if not all(exact["exact_checks"].values()):
            raise AssertionError("exact Farkas checks did not all pass")

        name = formula_record["name"]
        verifier_formula_path = (
            instance_directory / f"{name}.root-lp-farkas.opb"
        )
        verifier_formula_path.write_bytes(
            _render_verifier_opb(
                built["rows"],
                variable_count=built["metadata"]["variables"],
                class_index=structural_manifest["input"]["class_index"],
                orbit_index=orbit_index,
            )
        )
        proof_path = instance_directory / f"{name}.root-lp-farkas.pbp"
        proof_path.write_bytes(
            _render_veripb_proof(
                exact, built["metadata"]["opb_constraints"]
            )
        )
        certificate = {
            "schema_version": (
                "horizonmath.exact-root-lp-farkas-certificate.v1"
            ),
            "class_index": structural_manifest["input"]["class_index"],
            "orbit_index": orbit_index,
            "candidate_minimum_points": list(representative),
            "source_formula": {
                "path": formula_record["formula"]["path"],
                "path_base": "candidate_corpus_directory",
                "sha256": actual_formula_hash,
                "canonical_formula_sha256": rebuilt_canonical_hash,
            },
            "formula": {
                "path": verifier_formula_path.relative_to(
                    output_directory
                ).as_posix(),
                "sha256": sha256_file(verifier_formula_path),
                "canonical_formula_sha256": rebuilt_canonical_hash,
                "constraint_count": built["metadata"]["opb_constraints"],
                "variable_count": built["metadata"]["variables"],
                "syntax": (
                    "all constraints normalized to >=; native <= rows use "
                    "negated coefficients and RHS"
                ),
                "canonical_equivalent_to_source_formula": True,
            },
            "floating_support_extraction": {
                key: alternative[key]
                for key in (
                    "reported_status",
                    "reported_message",
                    "margin",
                    "support_size",
                    "formula_support_size",
                    "floating_lower_variables",
                    "floating_upper_variables",
                    "active_variables",
                )
            },
            "exact_certificate": exact,
            "proof": {
                "path": proof_path.relative_to(
                    output_directory
                ).as_posix(),
                "sha256": sha256_file(proof_path),
                "bytes": proof_path.stat().st_size,
                "format": "VeriPB pseudo-Boolean proof version 1.0",
                "expected_contradiction_id": (
                    built["metadata"]["opb_constraints"] + 1
                ),
            },
            "status": "PROOF_GENERATED",
            "status_ledger": {
                "formula": "FORMULAS_GENERATED",
                "root_lp": "SOLVER_UNSAT",
                "solver": solver_record["status"],
                "proof": "PROOF_GENERATED",
                "verification": "NOT_STARTED",
            },
            "formal_pruning_authorized": False,
            "guardrail": (
                "Exact arithmetic checks passed, but this proof is not "
                "VERIFIED_UNSAT until VeriPB checks the expected formula hash "
                "and proof hash with --requireUnsat and reports success."
            ),
        }
        certificate_path = (
            instance_directory / f"{name}.root-lp-farkas.json"
        )
        write_json(certificate_path, certificate)
        certificate["certificate_artifact"] = {
            "path": certificate_path.relative_to(
                output_directory
            ).as_posix(),
            "sha256": sha256_file(certificate_path),
        }
        records.append(certificate)

    all_exact_checks_passed = all(
        all(record["exact_certificate"]["exact_checks"].values())
        for record in records
    )
    manifest = {
        "schema_version": FARKAS_MANIFEST_SCHEMA_VERSION,
        "status": (
            "PROOF_GENERATED" if all_exact_checks_passed else "ERROR"
        ),
        "input": {
            "class_index": structural_manifest["input"]["class_index"],
            "canonical_labeled_link_sha256": structural_manifest["input"][
                "canonical_labeled_link_sha256"
            ],
            "candidate_corpus_manifest": {
                "path": os.path.relpath(corpus_path, output_directory),
                "sha256": corpus_hash,
            },
            "solver_manifest": {
                "path": os.path.relpath(
                    solver_manifest_path, output_directory
                ),
                "sha256": sha256_file(solver_manifest_path),
            },
            "selected_orbits": list(selected_orbits),
        },
        "method": {
            "id": "exact-root-lp-farkas-direct-veripb-v1",
            "floating_stage": (
                "HiGHS dual-simplex support for the normalized Farkas "
                "alternative including Boolean bounds"
            ),
            "exact_stage": (
                "stdlib Fraction sparse elimination; primitive positive "
                "one-dimensional integer null vector; exact coefficient and "
                "RHS recomputation"
            ),
            "proof_stage": (
                "one cutting-planes weighted sum of input rows and Boolean "
                "bounds, followed by contradiction check"
            ),
            "derived_from_published_mechanism": (
                "Class52 release scripts extract_farkas_lp.py, "
                "exact_farkas_from_active.py, and "
                "build_eq6_farkas_proof.py"
            ),
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": numpy.__version__,
            "scipy": scipy.__version__,
        },
        "instances": records,
        "summary": {
            "root_lp_solver_unsat_orbits_available": len(root_unsat),
            "selected_orbits": len(selected_orbits),
            "proofs_generated": len(records),
            "exact_certificates_passed": sum(
                all(record["exact_certificate"]["exact_checks"].values())
                for record in records
            ),
            "verified_unsat": 0,
            "formal_pruning_authorized": 0,
        },
        "scope": {
            "proofs_generated": True,
            "verifier_run": False,
            "formal_orbit_pruning_authorized": False,
            "class_elimination_claimed": False,
        },
    }
    manifest_path = output_directory / "farkas_corpus.manifest.json"
    write_json(manifest_path, manifest)
    write_sha256_sidecar(manifest_path)
    checksum_targets = sorted(
        [
            path
            for path in output_directory.rglob("*")
            if path.is_file()
            and path.name != "SHA256SUMS"
            and not path.name.endswith(".sha256")
        ],
        key=lambda path: path.relative_to(output_directory).as_posix(),
    )
    (output_directory / "SHA256SUMS").write_text(
        "".join(
            f"{sha256_file(path)}  "
            f"{path.relative_to(output_directory).as_posix()}\n"
            for path in checksum_targets
        ),
        encoding="utf-8",
    )
    return manifest
