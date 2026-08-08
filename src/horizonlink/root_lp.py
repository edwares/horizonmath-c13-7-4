"""Deterministic root-LP-only screening with exact mathematical witnesses."""

from __future__ import annotations

import json
import warnings
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

from horizonlink import __version__
from horizonlink.canonical import (
    sha256_bytes,
    sha256_file,
    write_json,
    write_sha256_sidecar,
)
from horizonlink.direct_containment import (
    CHECKPOINT_SCHEMA_VERSION as DIRECT_CHECKPOINT_SCHEMA_VERSION,
    _audit_candidate_checkpoint,
    _load_json_object,
    _parse_native_opb,
    _safe_path,
    _verify_checkpoint_checksums,
)
from horizonlink.farkas import (
    _dual_alternative,
    _exact_certificate,
    _render_verifier_opb,
    _render_veripb_proof,
)
from horizonlink.pb import PBRow
from horizonlink.root_lp_audit import audit_root_lp_checkpoint


ROOT_LP_CHECKPOINT_SCHEMA_VERSION = "horizonmath.root-lp-checkpoint.v1"
ROOT_LP_MANIFEST_SCHEMA_VERSION = "horizonmath.root-lp-screen.v1"


class RootLPError(ValueError):
    """Raised when the root-LP phase fails closed."""


def _fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _write_checksums(output_directory: Path) -> Path:
    checksum_path = output_directory / "SHA256SUMS"
    targets = sorted(
        (
            path
            for path in output_directory.rglob("*")
            if path.is_file() and path != checksum_path
        ),
        key=lambda path: path.relative_to(output_directory).as_posix(),
    )
    checksum_path.write_text(
        "".join(
            f"{sha256_file(path)}  "
            f"{path.relative_to(output_directory).as_posix()}\n"
            for path in targets
        ),
        encoding="utf-8",
    )
    return checksum_path


def _audit_inputs(
    candidate_checkpoint_directory: Path,
    direct_containment_directory: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    try:
        candidate_audit, candidate_phase, corpus = _audit_candidate_checkpoint(
            candidate_checkpoint_directory
        )
        direct_checksums = _verify_checkpoint_checksums(direct_containment_directory)
        direct_phase_path = direct_containment_directory / "phase.manifest.json"
        direct_phase, direct_phase_hash = _load_json_object(direct_phase_path)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise RootLPError(f"input checkpoint audit failed: {exc}") from exc

    expected = [int(value) for value in candidate_phase["summary"]["orbit_indices"]]
    direct_summary = direct_phase.get("summary", {})
    direct_scope = direct_phase.get("scope_guardrails", {})
    if (
        direct_phase.get("schema_version") != DIRECT_CHECKPOINT_SCHEMA_VERSION
        or direct_phase.get("status") != "ENUMERATED"
        or int(direct_summary.get("direct_contradictions_found", -1)) != 0
        or direct_summary.get("survivor_orbit_indices") != expected
        or direct_scope.get("root_lp_run") is not False
        or direct_scope.get("solver_run") is not False
        or direct_scope.get("verifier_run") is not False
    ):
        raise RootLPError("direct-containment checkpoint boundary is invalid")

    direct_candidate = direct_phase.get("input", {}).get("candidate_checkpoint", {})
    actual_candidate_phase_hash = sha256_file(
        candidate_checkpoint_directory / "phase.manifest.json"
    )
    if (
        direct_candidate.get("phase_manifest", {}).get("sha256")
        != actual_candidate_phase_hash
        or direct_candidate.get("checkpoint_checksums", {}).get("sha256sums_sha256")
        != candidate_audit["checkpoint_checksums"]["sha256sums_sha256"]
    ):
        raise RootLPError(
            "direct-containment checkpoint does not bind the supplied candidate checkpoint"
        )

    input_audit = {
        "candidate_checkpoint": {
            "phase_manifest_sha256": actual_candidate_phase_hash,
            "sha256sums_sha256": candidate_audit["checkpoint_checksums"][
                "sha256sums_sha256"
            ],
            "all_checks_passed": candidate_audit["all_checks_passed"],
        },
        "direct_containment_checkpoint": {
            "phase_manifest_sha256": direct_phase_hash,
            "sha256sums_sha256": direct_checksums["sha256sums_sha256"],
            "status": direct_phase["status"],
            "survivor_orbit_indices": direct_summary["survivor_orbit_indices"],
            "all_recorded_hashes_match": direct_checksums[
                "all_recorded_hashes_match"
            ],
            "every_checkpoint_file_accounted_for": direct_checksums[
                "every_checkpoint_file_accounted_for"
            ],
        },
        "checks": {
            "candidate_checkpoint_passed": True,
            "direct_checkpoint_checksums_passed": True,
            "direct_checkpoint_schema_supported": True,
            "direct_checkpoint_status_enumerated": True,
            "all_candidate_orbits_survived_direct_containment": True,
            "prior_root_lp_not_started": True,
            "prior_solver_and_verifier_not_started": True,
            "direct_checkpoint_binds_candidate_checkpoint": True,
        },
        "all_checks_passed": True,
    }
    return input_audit, candidate_phase, corpus, direct_phase


def _linprog_matrices(rows: tuple[Any, ...], variable_count: int, numpy: Any, sparse: Any):
    matrix = sparse.lil_matrix((len(rows), variable_count), dtype=float)
    rhs = numpy.zeros(len(rows), dtype=float)
    for row_index, row in enumerate(rows):
        sign = -1.0 if row.relation == ">=" else 1.0
        matrix.rows[row_index] = [variable - 1 for variable in row.variables]
        matrix.data[row_index] = [sign] * len(row.variables)
        rhs[row_index] = sign * float(row.rhs)
    return sparse.csr_matrix(matrix), rhs


def _exact_feasible_witness(
    rows: tuple[Any, ...],
    values: Any,
    variable_count: int,
    *,
    bound_tolerance: float = 1e-8,
    active_tolerance: float = 1e-7,
) -> dict[str, Any]:
    zero_variables = {
        index for index, value in enumerate(values) if float(value) < bound_tolerance
    }
    one_variables = {
        index
        for index, value in enumerate(values)
        if float(value) > 1.0 - bound_tolerance
    }
    if zero_variables & one_variables:
        raise RootLPError("floating LP support assigned a variable to both bounds")
    free_variables = [
        index
        for index in range(variable_count)
        if index not in zero_variables and index not in one_variables
    ]
    position = {variable: column for column, variable in enumerate(free_variables)}

    active_row_ids: list[int] = []
    equations: list[dict[int, Fraction]] = []
    rhs: list[Fraction] = []
    equation_source_ids: list[int] = []
    for row_id, row in enumerate(rows, start=1):
        lhs = sum(float(values[variable - 1]) for variable in row.variables)
        if abs(lhs - float(row.rhs)) > active_tolerance:
            continue
        active_row_ids.append(row_id)
        coefficients = {
            position[variable - 1]: Fraction(1)
            for variable in row.variables
            if variable - 1 in position
        }
        fixed_one_count = sum(
            variable - 1 in one_variables for variable in row.variables
        )
        equation_rhs = Fraction(int(row.rhs) - fixed_one_count)
        if coefficients or equation_rhs:
            equations.append(coefficients)
            rhs.append(equation_rhs)
            equation_source_ids.append(row_id)

    pivot_row = 0
    pivot_columns: list[int] = []
    pivot_source_row_ids: list[int] = []
    for column in range(len(free_variables)):
        candidate = next(
            (
                row_index
                for row_index in range(pivot_row, len(equations))
                if equations[row_index].get(column, 0)
            ),
            None,
        )
        if candidate is None:
            continue
        equations[pivot_row], equations[candidate] = (
            equations[candidate],
            equations[pivot_row],
        )
        rhs[pivot_row], rhs[candidate] = rhs[candidate], rhs[pivot_row]
        equation_source_ids[pivot_row], equation_source_ids[candidate] = (
            equation_source_ids[candidate],
            equation_source_ids[pivot_row],
        )
        pivot_value = equations[pivot_row][column]
        if pivot_value != 1:
            equations[pivot_row] = {
                index: value / pivot_value
                for index, value in equations[pivot_row].items()
            }
            rhs[pivot_row] /= pivot_value
        normalized = equations[pivot_row]
        normalized_rhs = rhs[pivot_row]
        for row_index in range(pivot_row + 1, len(equations)):
            factor = equations[row_index].get(column, 0)
            if not factor:
                continue
            reduced = dict(equations[row_index])
            for index, value in normalized.items():
                replacement = reduced.get(index, Fraction(0)) - factor * value
                if replacement:
                    reduced[index] = replacement
                else:
                    reduced.pop(index, None)
            equations[row_index] = reduced
            rhs[row_index] -= factor * normalized_rhs
        pivot_columns.append(column)
        pivot_source_row_ids.append(equation_source_ids[pivot_row])
        pivot_row += 1
        if pivot_row == len(equations):
            break

    if len(pivot_columns) != len(free_variables):
        raise RootLPError(
            "floating LP active system did not determine an exact rational point: "
            f"rank={len(pivot_columns)}, free_variables={len(free_variables)}"
        )
    reduced_solution = [Fraction(0) for _ in free_variables]
    for row_index in range(len(pivot_columns) - 1, -1, -1):
        column = pivot_columns[row_index]
        reduced_solution[column] = rhs[row_index] - sum(
            coefficient * reduced_solution[index]
            for index, coefficient in equations[row_index].items()
            if index != column
        )

    exact_values = [Fraction(0) for _ in range(variable_count)]
    for variable in one_variables:
        exact_values[variable] = Fraction(1)
    for variable, value in zip(free_variables, reduced_solution):
        exact_values[variable] = value

    all_bounds = all(Fraction(0) <= value <= Fraction(1) for value in exact_values)
    violations: list[int] = []
    exact_tight_rows = 0
    minimum_slack: Fraction | None = None
    for row_id, row in enumerate(rows, start=1):
        lhs = sum(exact_values[variable - 1] for variable in row.variables)
        slack = (
            lhs - row.rhs
            if row.relation == ">="
            else Fraction(row.rhs) - lhs
        )
        if slack < 0:
            violations.append(row_id)
        if slack == 0:
            exact_tight_rows += 1
        if minimum_slack is None or slack < minimum_slack:
            minimum_slack = slack
    if not all_bounds or violations:
        raise RootLPError(
            "exact rational reconstruction does not satisfy the LP: "
            f"bounds={all_bounds}, violations={violations[:10]}"
        )

    vector_bytes = json.dumps(
        [[value.numerator, value.denominator] for value in exact_values],
        separators=(",", ":"),
    ).encode("utf-8")
    nonzero = [
        {
            "variable_id_1based": index + 1,
            "numerator": str(value.numerator),
            "denominator": str(value.denominator),
        }
        for index, value in enumerate(exact_values)
        if value
    ]
    return {
        "schema_version": "horizonmath.exact-rational-root-lp-witness.v1",
        "variable_count": variable_count,
        "nonzero_variable_count": len(nonzero),
        "nonzero_values": nonzero,
        "exact_vector_sha256": sha256_bytes(vector_bytes),
        "active_system": {
            "floating_bound_tolerance": bound_tolerance,
            "floating_active_row_tolerance": active_tolerance,
            "floating_zero_variable_count": len(zero_variables),
            "floating_one_variable_count": len(one_variables),
            "floating_free_variable_count": len(free_variables),
            "active_row_count": len(active_row_ids),
            "active_row_ids_1based": active_row_ids,
            "exact_rank": len(pivot_columns),
            "pivot_source_row_ids_1based": pivot_source_row_ids,
        },
        "exact_tight_row_count": exact_tight_rows,
        "minimum_exact_slack": _fraction_text(minimum_slack or Fraction(0)),
        "exact_checks": {
            "active_system_full_column_rank": (
                len(pivot_columns) == len(free_variables)
            ),
            "all_bounds_satisfied_exactly": all_bounds,
            "all_formula_rows_satisfied_exactly": not violations,
        },
        "interpretation": (
            "This is an exact rational witness for the continuous root-LP "
            "relaxation only. It is not a Boolean assignment and is not a SAT "
            "witness for the native pseudo-Boolean formula."
        ),
    }


def _as_pb_rows(rows: tuple[Any, ...]) -> tuple[PBRow, ...]:
    return tuple(
        PBRow(
            tuple(variable - 1 for variable in row.variables),
            row.relation,
            int(row.rhs),
            row.family or "serialized_native",
            None,
        )
        for row in rows
    )


def generate_root_lp_checkpoint(
    candidate_checkpoint_directory: Path,
    direct_containment_directory: Path,
    output_directory: Path,
    *,
    root_lp_time_limit: float = 30.0,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Run root LP only and produce exact evidence for every candidate orbit."""

    try:
        import numpy
        import scipy
        import scipy.optimize
        import scipy.sparse
    except ImportError as exc:
        raise RuntimeError("root-LP screening requires NumPy and SciPy") from exc

    if root_lp_time_limit <= 0:
        raise RootLPError("root LP time limit must be positive")
    if output_directory.exists() and any(output_directory.iterdir()):
        raise RootLPError("root-LP output directory must be empty")

    input_audit, candidate_phase, corpus, direct_phase = _audit_inputs(
        candidate_checkpoint_directory, direct_containment_directory
    )
    class_index = int(candidate_phase["input"]["class_index"])
    expected_indices = [
        int(value) for value in candidate_phase["summary"]["orbit_indices"]
    ]
    corpus_root = candidate_checkpoint_directory / "corpus"
    output_directory.mkdir(parents=True, exist_ok=True)
    instance_directory = output_directory / "instances"
    instance_directory.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for source in corpus["instances"]:
        orbit_index = int(source["orbit_index"])
        if orbit_index not in expected_indices:
            raise RootLPError(f"unexpected candidate orbit {orbit_index}")
        name = source["name"]
        formula_path = _safe_path(corpus_root, source["formula"]["path"])
        if (
            not formula_path.is_file()
            or formula_path.stat().st_size != int(source["formula"]["bytes"])
            or sha256_file(formula_path) != source["formula"]["sha256"]
        ):
            raise RootLPError(f"source formula mismatch for orbit {orbit_index}")
        parsed = _parse_native_opb(
            formula_path, source["formula"]["serialized_family_counts"]
        )
        variable_count = int(parsed["variable_count"])
        if (
            variable_count != int(source["formula"]["variables"])
            or len(parsed["rows"]) != int(source["formula"]["opb_constraints"])
            or int(parsed["declared_constraint_count"]) != len(parsed["rows"])
        ):
            raise RootLPError(f"formula header mismatch for orbit {orbit_index}")

        matrix, rhs = _linprog_matrices(
            parsed["rows"], variable_count, numpy, scipy.sparse
        )
        options = {
            "time_limit": float(root_lp_time_limit),
            "presolve": True,
            "threads": 1,
            "parallel": "off",
            "random_seed": 0,
        }
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = scipy.optimize.linprog(
                numpy.zeros(variable_count),
                A_ub=matrix,
                b_ub=rhs,
                bounds=(0, 1),
                method="highs",
                options=options,
            )
        reported_status = int(result.status)
        solver_status = {
            0: "LP_FEASIBLE",
            1: "TIMEOUT",
            2: "SOLVER_UNSAT",
            3: "ERROR",
            4: "ERROR",
        }.get(reported_status, "ERROR")
        solver_report = {
            "status": solver_status,
            "reported_status": reported_status,
            "reported_message": str(result.message),
            "iterations": (
                None if getattr(result, "nit", None) is None else int(result.nit)
            ),
            "objective": "zero feasibility objective",
        }

        verifier_formula_artifact = None
        proof_artifact = None
        if solver_status == "LP_FEASIBLE":
            if result.x is None:
                raise RootLPError(
                    f"orbit {orbit_index}: LP solver returned no feasible vector"
                )
            feasible = _exact_feasible_witness(
                parsed["rows"], result.x, variable_count
            )
            if not all(feasible["exact_checks"].values()):
                raise RootLPError(
                    f"orbit {orbit_index}: exact feasible witness checks failed"
                )
            exact_result = {
                "status": "EXACT_LP_FEASIBLE",
                "feasible_witness": feasible,
                "farkas_certificate": None,
            }
            disposition = "SURVIVED_ROOT_LP"
            proof_status = "NOT_STARTED"
            reason = (
                "An exact rational vector satisfies every serialized formula "
                "row and every 0<=x<=1 bound, so the root-LP relaxation is "
                "mathematically feasible. This does not imply Boolean SAT."
            )
        elif solver_status == "SOLVER_UNSAT":
            pb_rows = _as_pb_rows(parsed["rows"])
            alternative = _dual_alternative(
                pb_rows,
                variable_count,
                numpy,
                scipy.optimize,
                scipy.sparse,
            )
            exact = _exact_certificate(pb_rows, variable_count, alternative)
            if not all(exact["exact_checks"].values()):
                raise RootLPError(
                    f"orbit {orbit_index}: exact Farkas checks failed"
                )
            verifier_formula_path = (
                instance_directory / f"{name}.root-lp-farkas.opb"
            )
            verifier_formula_path.write_bytes(
                _render_verifier_opb(
                    pb_rows,
                    variable_count=variable_count,
                    class_index=class_index,
                    orbit_index=orbit_index,
                )
            )
            proof_path = instance_directory / f"{name}.root-lp-farkas.pbp"
            proof_path.write_bytes(
                _render_veripb_proof(exact, len(parsed["rows"]))
            )
            verifier_formula_artifact = {
                "path": verifier_formula_path.relative_to(output_directory).as_posix(),
                "bytes": verifier_formula_path.stat().st_size,
                "sha256": sha256_file(verifier_formula_path),
                "constraint_ids_preserved": True,
                "canonical_equivalent_to_source_formula": True,
            }
            proof_artifact = {
                "path": proof_path.relative_to(output_directory).as_posix(),
                "bytes": proof_path.stat().st_size,
                "sha256": sha256_file(proof_path),
                "format": "VeriPB pseudo-Boolean proof version 1.0",
                "requires_requireUnsat_verification": True,
            }
            exact_result = {
                "status": "EXACT_FARKAS_CONTRADICTION",
                "feasible_witness": None,
                "farkas_certificate": exact,
                "floating_support_discovery": {
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
            }
            disposition = "ROOT_LP_INFEASIBLE_PROOF_GENERATED_PENDING_VERIFICATION"
            proof_status = "PROOF_GENERATED"
            reason = (
                "The floating root LP was reported infeasible and an exact "
                "integer Farkas weighted sum cancels every variable with a "
                "strictly positive contradiction RHS. Formal pruning still "
                "waits for VeriPB --requireUnsat verification."
            )
        else:
            raise RootLPError(
                f"orbit {orbit_index}: root LP did not resolve: "
                f"{solver_status}: {result.message}"
            )

        record = {
            "name": name,
            "class_index": class_index,
            "orbit_index": orbit_index,
            "candidate_minimum_points": source["candidate_minimum_points"],
            "source_formula": {
                "path": "corpus/" + source["formula"]["path"],
                "bytes": formula_path.stat().st_size,
                "sha256": sha256_file(formula_path),
                "canonical_formula_sha256": source["formula"][
                    "canonical_formula_sha256"
                ],
                "normalized_native_row_sha256": source["formula"][
                    "normalized_native_row_sha256"
                ],
                "variables": variable_count,
                "constraints": len(parsed["rows"]),
            },
            "solver_report": solver_report,
            "exact_result": exact_result,
            "artifacts": {
                "verifier_normalized_formula": verifier_formula_artifact,
                "proof": proof_artifact,
            },
            "result": {
                "disposition": disposition,
                "mathematical_reason": reason,
            },
            "status_ledger": {
                "formula": "FORMULAS_GENERATED",
                "direct_containment": "ENUMERATED",
                "root_lp": solver_status,
                "solver": solver_status,
                "proof": proof_status,
                "verification": "NOT_STARTED",
            },
            "formal_pruning_authorized": False,
        }
        metadata_path = instance_directory / f"{name}.root-lp.json"
        write_json(metadata_path, record)
        record["metadata"] = {
            "path": metadata_path.relative_to(output_directory).as_posix(),
            "bytes": metadata_path.stat().st_size,
            "sha256": sha256_file(metadata_path),
        }
        records.append(record)

    observed = [record["orbit_index"] for record in records]
    if observed != expected_indices:
        raise RootLPError("root-LP phase lost or reordered a candidate orbit")
    feasible_indices = [
        record["orbit_index"]
        for record in records
        if record["exact_result"]["status"] == "EXACT_LP_FEASIBLE"
    ]
    farkas_indices = [
        record["orbit_index"]
        for record in records
        if record["exact_result"]["status"] == "EXACT_FARKAS_CONTRADICTION"
    ]
    counts = Counter(record["solver_report"]["status"] for record in records)
    root_manifest = {
        "schema_version": ROOT_LP_MANIFEST_SCHEMA_VERSION,
        "status": "PROOF_GENERATED" if farkas_indices else "ENUMERATED",
        "producer": {
            "package": "horizonlink",
            "version": __version__,
            "command": "scan-root-lp",
        },
        "input": {
            "class_index": class_index,
            "numbering_source": candidate_phase["input"]["numbering_source"],
            "canonical_labeled_link_sha256": candidate_phase["input"][
                "canonical_labeled_link_sha256"
            ],
            "candidate_orbit_partition_sha256": candidate_phase["model"][
                "candidate_orbit_partition_sha256"
            ],
            **input_audit,
        },
        "method": {
            "id": "root-lp-exact-evidence-v1",
            "floating_solver": "SciPy linprog / HiGHS, zero objective",
            "floating_solver_options": {
                "time_limit_seconds_per_orbit": root_lp_time_limit,
                "presolve": True,
                "threads": 1,
                "parallel": "off",
                "random_seed": 0,
            },
            "feasible_evidence": (
                "Use the floating basic solution only to identify zero-bound "
                "variables and tight rows; solve the full-rank active system "
                "with Fraction arithmetic and check every inequality exactly."
            ),
            "infeasible_evidence": (
                "Use a floating dual support only to select rows; derive a "
                "primitive positive integer Farkas combination and recompute "
                "all coefficients and the contradiction RHS exactly."
            ),
            "proof_format": "VeriPB pseudo-Boolean proof version 1.0",
            "proof_verification_deferred": True,
        },
        "environment": {
            "numpy": numpy.__version__,
            "scipy": scipy.__version__,
        },
        "instances": records,
        "summary": {
            "candidate_orbits_expected": len(expected_indices),
            "candidate_orbits_scanned": len(records),
            "all_candidate_orbits_accounted_for": observed == expected_indices,
            "orbit_indices": observed,
            "solver_status_counts": dict(sorted(counts.items())),
            "exact_lp_feasible": len(feasible_indices),
            "exact_lp_feasible_orbit_indices": feasible_indices,
            "exact_farkas_contradictions": len(farkas_indices),
            "exact_farkas_orbit_indices": farkas_indices,
            "proofs_generated": len(farkas_indices),
            "proofs_verified": 0,
            "formal_orbits_pruned": 0,
            "survivors_pending_next_method": len(feasible_indices),
        },
        "status_ledger": {
            "candidate_formulas": "FORMULAS_GENERATED",
            "direct_containment": "ENUMERATED",
            "root_lp": "ENUMERATED",
            "proof": "PROOF_GENERATED" if farkas_indices else "NOT_STARTED",
            "verification": "NOT_STARTED",
        },
        "scope_guardrails": {
            "all_candidate_orbits_accounted_for": True,
            "root_lp_run": True,
            "milp_run": False,
            "roundingsat_run": False,
            "proof_generated": bool(farkas_indices),
            "verifier_run": False,
            "formal_orbit_pruning_authorized": False,
            "class_elimination_claimed": False,
            "C_13_7_4_equals_30_claimed": False,
        },
    }
    root_path = output_directory / "root-lp.manifest.json"
    write_json(root_path, root_manifest)
    write_sha256_sidecar(root_path)

    audit = audit_root_lp_checkpoint(
        candidate_checkpoint_directory,
        direct_containment_directory,
        output_directory,
    )
    if audit["status"] != "PASS":
        raise RootLPError("independent root-LP audit failed")
    audit_path = output_directory / "independent-audit.json"
    write_json(audit_path, audit)
    write_sha256_sidecar(audit_path)

    phase = {
        "schema_version": ROOT_LP_CHECKPOINT_SCHEMA_VERSION,
        "status": root_manifest["status"],
        "producer": root_manifest["producer"],
        "input": root_manifest["input"],
        "method": root_manifest["method"],
        "summary": {
            **root_manifest["summary"],
            "independent_comparisons_passed": audit["summary"][
                "comparisons_passed"
            ],
            "all_exact_evidence_independently_confirmed": audit["summary"][
                "all_exact_evidence_confirmed"
            ],
        },
        "status_ledger": root_manifest["status_ledger"],
        "scope_guardrails": root_manifest["scope_guardrails"],
        "artifacts": {
            "root_lp_manifest": {
                "path": "root-lp.manifest.json",
                "bytes": root_path.stat().st_size,
                "sha256": sha256_file(root_path),
            },
            "independent_audit": {
                "path": "independent-audit.json",
                "bytes": audit_path.stat().st_size,
                "sha256": sha256_file(audit_path),
            },
        },
    }
    phase_path = output_directory / "phase.manifest.json"
    write_json(phase_path, phase)
    write_sha256_sidecar(phase_path)
    _write_checksums(output_directory)
    return phase, root_manifest, audit

