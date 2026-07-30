"""Controlled solver runs for candidate minimum-point screening formulas."""

from __future__ import annotations

import json
import itertools
import platform
import sys
import time
import warnings
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from horizonlink.canonical import (
    sha256_file,
    write_json,
    write_sha256_sidecar,
)
from horizonlink.pb import (
    BoundedRow,
    PBRow,
    build_candidate_minimum_set_formula,
    canonical_formula_sha256,
)


SOLVER_MANIFEST_SCHEMA_VERSION = (
    "horizonmath.candidate-screening-solver-run.v1"
)


def _status_from_scipy(status: int) -> str:
    return {
        0: "SAT",
        1: "TIMEOUT",
        2: "SOLVER_UNSAT",
        3: "ERROR",
        4: "ERROR",
    }.get(status, "ERROR")


def _sparse_matrix(
    specifications: list[tuple[tuple[int, ...], float]],
    variable_count: int,
    sparse_module: Any,
) -> Any:
    matrix = sparse_module.lil_matrix(
        (len(specifications), variable_count), dtype=float
    )
    for row_index, (variables, coefficient) in enumerate(specifications):
        matrix.rows[row_index] = list(variables)
        matrix.data[row_index] = [coefficient] * len(variables)
    return sparse_module.csc_matrix(matrix)


def _root_lp_matrices(
    bounded_rows: tuple[BoundedRow, ...],
    variable_count: int,
    numpy_module: Any,
    sparse_module: Any,
) -> tuple[Any, Any, Any, Any]:
    inequalities: list[tuple[tuple[int, ...], float]] = []
    inequality_rhs: list[float] = []
    equalities: list[tuple[tuple[int, ...], float]] = []
    equality_rhs: list[float] = []
    for row in bounded_rows:
        if (
            row.lower is not None
            and row.upper is not None
            and row.lower == row.upper
        ):
            equalities.append((row.variables, 1.0))
            equality_rhs.append(float(row.lower))
            continue
        if row.lower is not None:
            inequalities.append((row.variables, -1.0))
            inequality_rhs.append(float(-row.lower))
        if row.upper is not None:
            inequalities.append((row.variables, 1.0))
            inequality_rhs.append(float(row.upper))
    return (
        _sparse_matrix(inequalities, variable_count, sparse_module),
        numpy_module.asarray(inequality_rhs, dtype=float),
        _sparse_matrix(equalities, variable_count, sparse_module),
        numpy_module.asarray(equality_rhs, dtype=float),
    )


def _mip_matrix(
    bounded_rows: tuple[BoundedRow, ...],
    variable_count: int,
    numpy_module: Any,
    sparse_module: Any,
) -> tuple[Any, Any, Any]:
    specifications = [(row.variables, 1.0) for row in bounded_rows]
    lower = numpy_module.asarray(
        [
            -numpy_module.inf if row.lower is None else row.lower
            for row in bounded_rows
        ],
        dtype=float,
    )
    upper = numpy_module.asarray(
        [
            numpy_module.inf if row.upper is None else row.upper
            for row in bounded_rows
        ],
        dtype=float,
    )
    return (
        _sparse_matrix(specifications, variable_count, sparse_module),
        lower,
        upper,
    )


def _validate_binary_assignment(
    values: Any,
    rows: tuple[PBRow, ...],
    extension_blocks: tuple[tuple[int, ...], ...],
    link_blocks: tuple[tuple[int, ...], ...],
    point_labels: tuple[int, ...],
) -> dict[str, Any]:
    rounded = [int(round(float(value))) for value in values]
    maximum_integrality_error = max(
        abs(float(value) - integer)
        for value, integer in zip(values, rounded)
    )
    selected = tuple(
        index for index, value in enumerate(rounded) if value == 1
    )
    violations = []
    selected_set = frozenset(selected)
    for row_index, row in enumerate(rows):
        lhs = sum(variable in selected_set for variable in row.variables)
        satisfied = (
            lhs >= row.rhs if row.relation == ">=" else lhs <= row.rhs
        )
        if not satisfied:
            violations.append(
                {
                    "row_index": row_index,
                    "relation": row.relation,
                    "rhs": row.rhs,
                    "lhs": lhs,
                    "family": row.family,
                    "subject": (
                        list(row.subject)
                        if row.subject is not None
                        else None
                    ),
                }
            )

    new_point = max(point_labels) + 1
    lifted_link_blocks = tuple(
        tuple(sorted((*block, new_point))) for block in link_blocks
    )
    selected_extension_blocks = tuple(
        extension_blocks[index] for index in selected
    )
    design_blocks = lifted_link_blocks + selected_extension_blocks
    uncovered_fours = []
    for four in itertools.combinations((*point_labels, new_point), 4):
        target = frozenset(four)
        if not any(target <= frozenset(block) for block in design_blocks):
            uncovered_fours.append(list(four))

    return {
        "binary_within_tolerance": maximum_integrality_error <= 1e-7,
        "maximum_integrality_error": maximum_integrality_error,
        "selected_variable_count": len(selected),
        "selected_variable_indices_zero_based": list(selected),
        "selected_extension_blocks": [
            list(block) for block in selected_extension_blocks
        ],
        "formula_rows_satisfied": not violations,
        "formula_row_violations": violations,
        "independent_29_block_cover_check": {
            "new_point_label": new_point,
            "block_count": len(design_blocks),
            "all_four_sets_covered": not uncovered_fours,
            "uncovered_four_sets": uncovered_fours,
        },
        "valid_sat_witness": (
            maximum_integrality_error <= 1e-7
            and not violations
            and len(design_blocks) == 29
            and not uncovered_fours
        ),
    }


def _historical_partition(path: Path | None) -> dict[int, str] | None:
    if path is None:
        return None
    ledger = json.loads(path.read_text(encoding="utf-8"))
    return {
        int(row["orbit"]): row["disposition"]
        for row in ledger["candidate_orbit_screening"]
    }


def solve_candidate_screening_corpus(
    structural_manifest: dict[str, Any],
    corpus_directory: Path,
    output_directory: Path,
    *,
    root_lp_time_limit: float = 10.0,
    mip_time_limit: float = 10.0,
    orbit_indices: Iterable[int] | None = None,
    historical_ledger: Path | None = None,
) -> dict[str, Any]:
    """Run root LP and controlled MILP checks without claiming formal proof."""

    try:
        import numpy
        import scipy
        import scipy.optimize
        import scipy.sparse
    except ImportError as exc:
        raise RuntimeError(
            "controlled solver runs require NumPy and SciPy"
        ) from exc

    if structural_manifest.get("status") != "ENUMERATED":
        raise ValueError("structural manifest must be ENUMERATED")
    if root_lp_time_limit <= 0 or mip_time_limit <= 0:
        raise ValueError("solver time limits must be positive")
    if output_directory.exists() and any(output_directory.iterdir()):
        raise ValueError("solver output directory must be empty")
    corpus_path = corpus_directory / "corpus.manifest.json"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    if corpus.get("status") != "FORMULAS_GENERATED":
        raise ValueError("candidate screening corpus must be FORMULAS_GENERATED")

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
    expected_all = tuple(range(len(orbit_rows)))
    selected_orbits = (
        expected_all
        if orbit_indices is None
        else tuple(sorted(set(int(index) for index in orbit_indices)))
    )
    if not selected_orbits:
        raise ValueError("at least one orbit must be selected")
    if selected_orbits[0] < 0 or selected_orbits[-1] >= len(orbit_rows):
        raise ValueError("selected orbit index is out of range")

    historical = _historical_partition(historical_ledger)
    output_directory.mkdir(parents=True, exist_ok=True)
    instance_directory = output_directory / "instances"
    instance_directory.mkdir(parents=True, exist_ok=True)
    records = []
    run_started = time.time()
    for orbit_index in selected_orbits:
        orbit = orbit_rows[orbit_index]
        representative = tuple(orbit["representative"])
        formula_record = formula_records.get(orbit_index)
        if formula_record is None:
            raise ValueError(f"missing formula record for orbit {orbit_index}")
        formula_path = corpus_directory / formula_record["formula"]["path"]
        built = build_candidate_minimum_set_formula(
            point_labels, link_blocks, representative
        )
        actual_native_hash = sha256_file(formula_path)
        rebuilt_canonical_hash = canonical_formula_sha256(
            built["rows"],
            variable_count=built["metadata"]["variables"],
        )
        hash_checks = {
            "expected_native_formula_hash_matches": (
                actual_native_hash == formula_record["formula"]["sha256"]
            ),
            "rebuilt_canonical_formula_hash_matches": (
                rebuilt_canonical_hash
                == formula_record["formula"]["canonical_formula_sha256"]
            ),
        }
        hashes_match = all(hash_checks.values())

        log_lines = [
            f"orbit={orbit_index}",
            f"candidate_minimum_points={list(representative)}",
            f"formula_path={formula_path}",
            f"expected_native_sha256={formula_record['formula']['sha256']}",
            f"actual_native_sha256={actual_native_hash}",
            f"hashes_match={hashes_match}",
        ]
        if not hashes_match:
            result_record = {
                "orbit_index": orbit_index,
                "candidate_minimum_points": list(representative),
                "formula": {
                    "path": str(formula_path),
                    "expected_sha256": formula_record["formula"]["sha256"],
                    "actual_sha256": actual_native_hash,
                    "expected_canonical_sha256": formula_record["formula"][
                        "canonical_formula_sha256"
                    ],
                    "rebuilt_canonical_sha256": rebuilt_canonical_hash,
                    "hash_checks": hash_checks,
                },
                "status": "ERROR",
                "status_ledger": {
                    "formula": "ERROR",
                    "root_lp": "NOT_STARTED",
                    "solver": "NOT_STARTED",
                    "proof": "NOT_STARTED",
                    "verification": "NOT_STARTED",
                },
                "formal_pruning_authorized": False,
                "formal_disposition": "RETAINED_DUE_TO_ERROR",
            }
            log_lines.append("status=ERROR")
            log_lines.append("reason=formula hash mismatch")
        else:
            variable_count = built["metadata"]["variables"]
            a_ub, b_ub, a_eq, b_eq = _root_lp_matrices(
                built["bounded_rows"],
                variable_count,
                numpy,
                scipy.sparse,
            )
            root_options = {
                "time_limit": float(root_lp_time_limit),
                "presolve": True,
                "threads": 1,
                "parallel": "off",
                "random_seed": 0,
            }
            root_started = time.monotonic()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                root_result = scipy.optimize.linprog(
                    numpy.zeros(variable_count),
                    A_ub=a_ub,
                    b_ub=b_ub,
                    A_eq=a_eq,
                    b_eq=b_eq,
                    bounds=(0, 1),
                    method="highs",
                    options=root_options,
                )
            root_seconds = time.monotonic() - root_started
            root_status = _status_from_scipy(int(root_result.status))
            root_record = {
                "status": (
                    "LP_FEASIBLE" if root_status == "SAT" else root_status
                ),
                "reported_status": int(root_result.status),
                "reported_message": str(root_result.message),
                "seconds": root_seconds,
                "iterations": (
                    None
                    if getattr(root_result, "nit", None) is None
                    else int(root_result.nit)
                ),
                "certificate_generated": False,
                "certificate_verified": False,
            }
            log_lines.extend(
                [
                    f"root_lp_status={root_record['status']}",
                    f"root_lp_reported_status={root_result.status}",
                    f"root_lp_message={root_result.message}",
                    f"root_lp_seconds={root_seconds:.9f}",
                ]
            )

            mip_record: dict[str, Any]
            assignment_validation = None
            if root_status == "SOLVER_UNSAT":
                solver_status = "SOLVER_UNSAT"
                mip_record = {
                    "status": "NOT_STARTED",
                    "reason": (
                        "The floating-point root LP solver reported the "
                        "relaxation infeasible; MILP was skipped."
                    ),
                }
            elif root_status in {"TIMEOUT", "ERROR"}:
                solver_status = root_status
                mip_record = {
                    "status": "NOT_STARTED",
                    "reason": "root LP did not complete successfully",
                }
            else:
                matrix, lower, upper = _mip_matrix(
                    built["bounded_rows"],
                    variable_count,
                    numpy,
                    scipy.sparse,
                )
                mip_options = {
                    "time_limit": float(mip_time_limit),
                    "mip_rel_gap": 0.0,
                    "presolve": True,
                    "disp": False,
                    "threads": 1,
                    "parallel": "off",
                    "random_seed": 0,
                }
                mip_started = time.monotonic()
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    mip_result = scipy.optimize.milp(
                        c=numpy.zeros(variable_count),
                        integrality=numpy.ones(variable_count),
                        bounds=scipy.optimize.Bounds(0, 1),
                        constraints=scipy.optimize.LinearConstraint(
                            matrix, lower, upper
                        ),
                        options=mip_options,
                    )
                mip_seconds = time.monotonic() - mip_started
                solver_status = _status_from_scipy(int(mip_result.status))
                if mip_result.x is not None:
                    assignment_validation = _validate_binary_assignment(
                        mip_result.x,
                        built["rows"],
                        built["extension_blocks"],
                        link_blocks,
                        point_labels,
                    )
                    if assignment_validation["valid_sat_witness"]:
                        solver_status = "SAT"
                    elif solver_status == "SAT":
                        solver_status = "ERROR"
                mip_record = {
                    "status": solver_status,
                    "reported_status": int(mip_result.status),
                    "reported_message": str(mip_result.message),
                    "seconds": mip_seconds,
                    "nodes": (
                        None
                        if getattr(mip_result, "mip_node_count", None)
                        is None
                        else int(mip_result.mip_node_count)
                    ),
                    "dual_bound": (
                        None
                        if getattr(mip_result, "mip_dual_bound", None)
                        is None
                        else float(mip_result.mip_dual_bound)
                    ),
                    "gap": (
                        None
                        if getattr(mip_result, "mip_gap", None) is None
                        else float(mip_result.mip_gap)
                    ),
                }
                log_lines.extend(
                    [
                        f"mip_status={solver_status}",
                        f"mip_reported_status={mip_result.status}",
                        f"mip_message={mip_result.message}",
                        f"mip_seconds={mip_seconds:.9f}",
                        f"mip_nodes={mip_record['nodes']}",
                    ]
                )

            formal_disposition = {
                "SOLVER_UNSAT": "RETAINED_PENDING_VERIFIED_CERTIFICATE",
                "TIMEOUT": "RETAINED_UNRESOLVED",
                "SAT": "RETAINED_SAT_WITNESS",
                "ERROR": "RETAINED_DUE_TO_ERROR",
            }[solver_status]
            exploratory_disposition = (
                "SCREENED_OUT_SOLVER_ONLY"
                if solver_status == "SOLVER_UNSAT"
                else "RETAINED"
            )
            status_ledger = {
                "formula": "FORMULAS_GENERATED",
                "root_lp": root_record["status"],
                "solver": solver_status,
                "proof": "NOT_STARTED",
                "verification": "NOT_STARTED",
            }
            result_record = {
                "orbit_index": orbit_index,
                "candidate_minimum_points": list(representative),
                "formula": {
                    "path": str(formula_path),
                    "expected_sha256": formula_record["formula"]["sha256"],
                    "actual_sha256": actual_native_hash,
                    "expected_canonical_sha256": formula_record["formula"][
                        "canonical_formula_sha256"
                    ],
                    "rebuilt_canonical_sha256": rebuilt_canonical_hash,
                    "hash_checks": hash_checks,
                },
                "root_lp": root_record,
                "mip": mip_record,
                "assignment_validation": assignment_validation,
                "status": solver_status,
                "status_ledger": status_ledger,
                "exploratory_disposition": exploratory_disposition,
                "formal_disposition": formal_disposition,
                "formal_pruning_authorized": False,
                "mathematical_reason": (
                    "The candidate-orbit necessary-condition model was "
                    f"reported {solver_status}. A solver report is not a "
                    "formal certificate; this orbit remains in formal "
                    "accounting until VERIFIED_UNSAT."
                ),
            }
            if historical is not None:
                historical_disposition = historical.get(orbit_index)
                historical_exploratory = (
                    "SCREENED_OUT_SOLVER_ONLY"
                    if historical_disposition == "DISCARDED"
                    else "RETAINED"
                )
                result_record["historical_comparison"] = {
                    "historical_disposition": historical_disposition,
                    "historical_exploratory_disposition": (
                        historical_exploratory
                    ),
                    "fresh_exploratory_disposition": (
                        exploratory_disposition
                    ),
                    "equal": (
                        historical_exploratory
                        == exploratory_disposition
                    ),
                    "interpretation": (
                        "A difference may reflect solver/version/runtime "
                        "progress; it does not alter formal status."
                    ),
                }
            log_lines.append(f"aggregate_status={solver_status}")
            log_lines.append(
                f"formal_disposition={formal_disposition}"
            )
            log_lines.append("formal_pruning_authorized=False")

        name = formula_record["name"]
        log_path = instance_directory / f"{name}.solver.log"
        log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        result_record["solver_log"] = {
            "path": log_path.relative_to(output_directory).as_posix(),
            "sha256": sha256_file(log_path),
        }
        result_path = instance_directory / f"{name}.solver.json"
        write_json(result_path, result_record)
        result_record["result_artifact"] = {
            "path": result_path.relative_to(output_directory).as_posix(),
            "sha256": sha256_file(result_path),
        }
        records.append(result_record)

    status_counts = Counter(record["status"] for record in records)
    root_counts = Counter(
        record.get("root_lp", {}).get("status", "NOT_STARTED")
        for record in records
    )
    if status_counts.get("ERROR"):
        aggregate_status = "ERROR"
    elif status_counts.get("TIMEOUT"):
        aggregate_status = "TIMEOUT"
    elif status_counts.get("SAT"):
        aggregate_status = "SAT"
    elif status_counts.get("SOLVER_UNSAT") == len(records):
        aggregate_status = "SOLVER_UNSAT"
    else:
        aggregate_status = "ENUMERATED"
    historical_equal = [
        record["historical_comparison"]["equal"]
        for record in records
        if "historical_comparison" in record
    ]
    manifest = {
        "schema_version": SOLVER_MANIFEST_SCHEMA_VERSION,
        "status": aggregate_status,
        "input": {
            "class_index": structural_manifest["input"]["class_index"],
            "canonical_labeled_link_sha256": structural_manifest["input"][
                "canonical_labeled_link_sha256"
            ],
            "corpus_manifest_path": str(corpus_path),
            "corpus_manifest_sha256": sha256_file(corpus_path),
            "selected_orbits": list(selected_orbits),
            "historical_ledger": (
                None
                if historical_ledger is None
                else {
                    "path": str(historical_ledger),
                    "sha256": sha256_file(historical_ledger),
                }
            ),
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": numpy.__version__,
            "scipy": scipy.__version__,
        },
        "options": {
            "root_lp": {
                "method": "HiGHS through scipy.optimize.linprog",
                "time_limit_seconds_per_orbit": root_lp_time_limit,
                "presolve": True,
                "threads": 1,
                "parallel": "off",
                "random_seed": 0,
            },
            "mip": {
                "method": "HiGHS through scipy.optimize.milp",
                "time_limit_seconds_per_orbit": mip_time_limit,
                "presolve": True,
                "threads": 1,
                "parallel": "off",
                "random_seed": 0,
                "mip_rel_gap": 0.0,
                "objective": "zero feasibility objective",
            },
        },
        "instances": records,
        "summary": {
            "selected_orbits": len(selected_orbits),
            "status_counts": dict(sorted(status_counts.items())),
            "root_lp_status_counts": dict(sorted(root_counts.items())),
            "formula_hash_checks_passed": sum(
                all(record["formula"]["hash_checks"].values())
                for record in records
            ),
            "formal_pruning_authorized": 0,
            "historical_comparisons": len(historical_equal),
            "historical_exploratory_dispositions_equal": sum(
                historical_equal
            ),
            "wall_seconds": time.time() - run_started,
        },
        "scope": {
            "solver_run": True,
            "proof_generated": False,
            "verifier_run": False,
            "formal_orbit_pruning_authorized": False,
            "class_elimination_claimed": False,
        },
    }
    manifest_path = output_directory / "solver_run.manifest.json"
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
