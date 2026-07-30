#!/usr/bin/env python3
"""Independently audit generated direct root-LP Farkas proof artifacts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from horizonlink.canonical import sha256_file, write_json, write_sha256_sidecar


HEADER_RE = re.compile(
    r"^\* #variable= (?P<variables>[0-9]+) "
    r"#constraint= (?P<constraints>[0-9]+)$"
)
ROW_RE = re.compile(
    r"^(?P<terms>(?:[+-][0-9]+ x[1-9][0-9]* ?)+)"
    r"(?P<relation>>=|<=) (?P<rhs>-?[0-9]+) ;$"
)
TERM_RE = re.compile(r"([+-][0-9]+) x([1-9][0-9]*)")


def _parse_opb(path: Path) -> dict[str, Any]:
    variable_count = None
    declared_constraint_count = None
    rows = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("*"):
            header = HEADER_RE.fullmatch(line)
            if header is not None:
                variable_count = int(header.group("variables"))
                declared_constraint_count = int(
                    header.group("constraints")
                )
            continue
        match = ROW_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"{path}:{line_number}: unsupported OPB row")
        coefficients: dict[int, int] = {}
        for coefficient_text, variable_text in TERM_RE.findall(
            match.group("terms")
        ):
            variable = int(variable_text)
            coefficients[variable] = (
                coefficients.get(variable, 0) + int(coefficient_text)
            )
        relation = match.group("relation")
        rhs = int(match.group("rhs"))
        if relation == "<=":
            coefficients = {
                variable: -coefficient
                for variable, coefficient in coefficients.items()
            }
            rhs = -rhs
        rows.append({"coefficients": coefficients, "rhs": rhs})
    if variable_count is None or declared_constraint_count is None:
        raise ValueError(f"{path}: missing OPB variable/constraint header")
    if declared_constraint_count != len(rows):
        raise ValueError(
            f"{path}: declared {declared_constraint_count} constraints, "
            f"parsed {len(rows)}"
        )
    if any(
        variable < 1 or variable > variable_count
        for row in rows
        for variable in row["coefficients"]
    ):
        raise ValueError(f"{path}: variable outside declared range")
    return {
        "variable_count": variable_count,
        "constraint_count": len(rows),
        "rows": rows,
    }


def _expected_proof_tokens(
    row_multipliers: list[dict[str, int]],
    lower_bounds: list[dict[str, int]],
    upper_bounds: list[dict[str, int]],
) -> list[str]:
    operands = [
        (str(item["row_id_1based"]), item["multiplier"])
        for item in row_multipliers
    ]
    operands.extend(
        (f"x{item['variable']}", item["multiplier"])
        for item in lower_bounds
    )
    operands.extend(
        (f"~x{item['variable']}", item["multiplier"])
        for item in upper_bounds
    )
    tokens = ["p"]
    for index, (operand, multiplier) in enumerate(operands):
        tokens.extend([operand, str(multiplier), "*"])
        if index:
            tokens.append("+")
    return tokens


def _audit_instance(
    record: dict[str, Any],
    corpus_record: dict[str, Any],
    solver_record: dict[str, Any],
    candidate_corpus_directory: Path,
    farkas_directory: Path,
) -> dict[str, Any]:
    orbit_index = int(record["orbit_index"])
    certificate_path = (
        farkas_directory / record["certificate_artifact"]["path"]
    )
    certificate = json.loads(
        certificate_path.read_text(encoding="utf-8")
    )
    source_formula_path = (
        candidate_corpus_directory / corpus_record["formula"]["path"]
    )
    formula_path = farkas_directory / certificate["formula"]["path"]
    proof_path = farkas_directory / certificate["proof"]["path"]
    parsed = _parse_opb(formula_path)
    parsed_source = _parse_opb(source_formula_path)
    exact = certificate["exact_certificate"]
    row_multipliers = exact["row_multipliers"]
    lower_bounds = exact["lower_bound_multipliers"]
    upper_bounds = exact["upper_bound_multipliers"]

    row_ids = [item["row_id_1based"] for item in row_multipliers]
    lower_variables = [item["variable"] for item in lower_bounds]
    upper_variables = [item["variable"] for item in upper_bounds]
    combined = [0] * parsed["variable_count"]
    combined_rhs_before_bounds = 0
    invalid_row_reference = False
    for item in row_multipliers:
        row_id = item["row_id_1based"]
        if row_id < 1 or row_id > parsed["constraint_count"]:
            invalid_row_reference = True
            continue
        row = parsed["rows"][row_id - 1]
        multiplier = item["multiplier"]
        for variable, coefficient in row["coefficients"].items():
            combined[variable - 1] += multiplier * coefficient
        combined_rhs_before_bounds += multiplier * row["rhs"]

    observed_sparse_before_bounds = [
        {"variable": variable, "coefficient": coefficient}
        for variable, coefficient in enumerate(combined, 1)
        if coefficient
    ]
    final_coefficients = list(combined)
    combined_rhs_after_bounds = combined_rhs_before_bounds
    for item in lower_bounds:
        variable = item["variable"]
        if 1 <= variable <= parsed["variable_count"]:
            final_coefficients[variable - 1] += item["multiplier"]
    for item in upper_bounds:
        variable = item["variable"]
        if 1 <= variable <= parsed["variable_count"]:
            final_coefficients[variable - 1] -= item["multiplier"]
            combined_rhs_after_bounds -= item["multiplier"]

    proof_lines = proof_path.read_text(encoding="utf-8").splitlines()
    proof_shape_ok = len(proof_lines) == 4
    expected_tokens = _expected_proof_tokens(
        row_multipliers, lower_bounds, upper_bounds
    )
    proof_tokens_equal = (
        proof_shape_ok and proof_lines[2].split() == expected_tokens
    )
    checks = {
        "manifest_certificate_hash_equal": (
            sha256_file(certificate_path)
            == record["certificate_artifact"]["sha256"]
        ),
        "certificate_orbit_equal": certificate["orbit_index"] == orbit_index,
        "certificate_status_proof_generated": (
            certificate["status"] == "PROOF_GENERATED"
        ),
        "certificate_verification_not_started": (
            certificate["status_ledger"]["verification"] == "NOT_STARTED"
        ),
        "formal_pruning_not_authorized": (
            certificate["formal_pruning_authorized"] is False
        ),
        "source_formula_path_equal": (
            certificate["source_formula"]["path"]
            == corpus_record["formula"]["path"]
        ),
        "source_formula_hash_equal": (
            sha256_file(source_formula_path)
            == certificate["source_formula"]["sha256"]
            == corpus_record["formula"]["sha256"]
            == solver_record["formula"]["actual_sha256"]
        ),
        "verifier_formula_hash_equal": (
            sha256_file(formula_path) == certificate["formula"]["sha256"]
        ),
        "verifier_formula_uses_only_greater_equal": (
            " <= " not in formula_path.read_text(encoding="utf-8")
        ),
        "source_and_verifier_rows_canonically_equal_in_order": (
            parsed_source["variable_count"] == parsed["variable_count"]
            and parsed_source["constraint_count"]
            == parsed["constraint_count"]
            and parsed_source["rows"] == parsed["rows"]
        ),
        "formula_constraint_count_equal": (
            parsed["constraint_count"]
            == certificate["formula"]["constraint_count"]
        ),
        "formula_variable_count_equal": (
            parsed["variable_count"]
            == certificate["formula"]["variable_count"]
        ),
        "solver_root_lp_status_unsat": (
            solver_record["root_lp"]["status"] == "SOLVER_UNSAT"
        ),
        "row_references_in_range": not invalid_row_reference,
        "row_references_unique": len(row_ids) == len(set(row_ids)),
        "row_multipliers_strictly_positive": all(
            item["multiplier"] > 0 for item in row_multipliers
        ),
        "lower_bound_variables_unique_and_in_range": (
            len(lower_variables) == len(set(lower_variables))
            and all(
                1 <= variable <= parsed["variable_count"]
                for variable in lower_variables
            )
        ),
        "upper_bound_variables_unique_and_in_range": (
            len(upper_variables) == len(set(upper_variables))
            and all(
                1 <= variable <= parsed["variable_count"]
                for variable in upper_variables
            )
        ),
        "bound_multiplier_sets_disjoint": not (
            set(lower_variables) & set(upper_variables)
        ),
        "bound_multipliers_strictly_positive": all(
            item["multiplier"] > 0
            for item in lower_bounds + upper_bounds
        ),
        "recorded_coefficients_before_bounds_equal": (
            observed_sparse_before_bounds
            == exact["combined_lhs_coefficients_before_bounds"]
        ),
        "recorded_rhs_before_bounds_equal": (
            combined_rhs_before_bounds
            == exact["combined_rhs_before_bounds"]
        ),
        "all_coefficients_cancel_exactly": not any(final_coefficients),
        "recorded_rhs_after_bounds_equal": (
            combined_rhs_after_bounds
            == exact["combined_rhs_after_bounds"]
        ),
        "contradiction_rhs_strictly_positive": (
            combined_rhs_after_bounds > 0
        ),
        "proof_hash_equal": (
            sha256_file(proof_path) == certificate["proof"]["sha256"]
        ),
        "proof_has_four_lines": proof_shape_ok,
        "proof_header_equal": (
            proof_shape_ok
            and proof_lines[0] == "pseudo-Boolean proof version 1.0"
        ),
        "proof_formula_count_equal": (
            proof_shape_ok
            and proof_lines[1] == f"f {parsed['constraint_count']}"
        ),
        "proof_weighted_sum_tokens_equal": proof_tokens_equal,
        "proof_contradiction_id_equal": (
            proof_shape_ok
            and proof_lines[3]
            == f"c {parsed['constraint_count'] + 1}"
        ),
    }
    return {
        "orbit_index": orbit_index,
        "source_formula_sha256": sha256_file(source_formula_path),
        "formula_sha256": sha256_file(formula_path),
        "proof_sha256": sha256_file(proof_path),
        "certificate_sha256": sha256_file(certificate_path),
        "formula_constraints": parsed["constraint_count"],
        "formula_variables": parsed["variable_count"],
        "formula_rows_used": len(row_multipliers),
        "lower_bounds_used": len(lower_bounds),
        "upper_bounds_used": len(upper_bounds),
        "independently_recomputed_contradiction_rhs": (
            combined_rhs_after_bounds
        ),
        "checks": checks,
        "passed": all(checks.values()),
    }


def audit(
    candidate_corpus_directory: Path,
    solver_manifest_path: Path,
    farkas_directory: Path,
) -> dict[str, Any]:
    corpus_path = candidate_corpus_directory / "corpus.manifest.json"
    farkas_manifest_path = farkas_directory / "farkas_corpus.manifest.json"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    solver = json.loads(
        solver_manifest_path.read_text(encoding="utf-8")
    )
    farkas = json.loads(
        farkas_manifest_path.read_text(encoding="utf-8")
    )
    corpus_records = {
        int(record["orbit_index"]): record
        for record in corpus["instances"]
    }
    solver_records = {
        int(record["orbit_index"]): record
        for record in solver["instances"]
    }
    manifest_records = {
        int(record["orbit_index"]): record
        for record in farkas["instances"]
    }
    selected_orbits = [int(index) for index in farkas["input"]["selected_orbits"]]
    comparisons = []
    missing_orbits = []
    for orbit_index in selected_orbits:
        if (
            orbit_index not in corpus_records
            or orbit_index not in solver_records
            or orbit_index not in manifest_records
        ):
            missing_orbits.append(orbit_index)
            continue
        comparisons.append(
            _audit_instance(
                manifest_records[orbit_index],
                corpus_records[orbit_index],
                solver_records[orbit_index],
                candidate_corpus_directory,
                farkas_directory,
            )
        )

    top_level_checks = {
        "farkas_manifest_status_proof_generated": (
            farkas["status"] == "PROOF_GENERATED"
        ),
        "farkas_manifest_verifier_not_run": (
            farkas["scope"]["verifier_run"] is False
        ),
        "farkas_manifest_no_verified_unsat": (
            farkas["summary"]["verified_unsat"] == 0
        ),
        "farkas_manifest_no_formal_pruning": (
            farkas["scope"]["formal_orbit_pruning_authorized"] is False
        ),
        "candidate_corpus_hash_equal": (
            sha256_file(corpus_path)
            == farkas["input"]["candidate_corpus_manifest"]["sha256"]
            == solver["input"]["corpus_manifest_sha256"]
        ),
        "solver_manifest_hash_equal": (
            sha256_file(solver_manifest_path)
            == farkas["input"]["solver_manifest"]["sha256"]
        ),
        "selected_orbits_unique_and_sorted": (
            selected_orbits == sorted(set(selected_orbits))
        ),
        "every_selected_orbit_has_one_manifest_record": (
            sorted(manifest_records) == selected_orbits
        ),
        "no_selected_orbit_missing": not missing_orbits,
    }
    all_passed = all(top_level_checks.values()) and all(
        comparison["passed"] for comparison in comparisons
    )
    return {
        "schema_version": (
            "horizonmath.independent-root-lp-farkas-audit.v1"
        ),
        "status": "PASS" if all_passed else "ERROR",
        "input": {
            "candidate_corpus_manifest": {
                "path": str(corpus_path),
                "sha256": sha256_file(corpus_path),
            },
            "solver_manifest": {
                "path": str(solver_manifest_path),
                "sha256": sha256_file(solver_manifest_path),
            },
            "farkas_manifest": {
                "path": str(farkas_manifest_path),
                "sha256": sha256_file(farkas_manifest_path),
            },
        },
        "method": {
            "description": (
                "Parse each generated OPB independently; normalize every "
                "constraint to >=; recompute the weighted integer sum and "
                "Boolean-bound additions; require exact coefficient "
                "cancellation and a positive contradiction RHS; independently "
                "reconstruct and compare every token in the four-line PBP."
            ),
            "imports_farkas_generator": False,
            "imports_pb_formula_builder": False,
            "arithmetic": "Python arbitrary-precision integers",
        },
        "top_level_checks": top_level_checks,
        "comparisons": comparisons,
        "summary": {
            "selected_orbits": len(selected_orbits),
            "proofs_audited": len(comparisons),
            "proofs_passing_exact_audit": sum(
                comparison["passed"] for comparison in comparisons
            ),
            "veripb_runs": 0,
            "verified_unsat": 0,
            "formal_pruning_authorized": 0,
        },
        "scope": {
            "exact_arithmetic_and_serialization_audited": True,
            "veripb_run": False,
            "verified_unsat_claimed": False,
            "formal_orbit_pruning_authorized": False,
            "class_elimination_claimed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate-corpus-directory", type=Path, required=True
    )
    parser.add_argument("--solver-manifest", type=Path, required=True)
    parser.add_argument("--farkas-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(
        args.candidate_corpus_directory,
        args.solver_manifest,
        args.farkas_directory,
    )
    write_json(args.output, report)
    write_sha256_sidecar(args.output)
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
