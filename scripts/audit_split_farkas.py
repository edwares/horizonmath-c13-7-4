#!/usr/bin/env python3
"""Independent integer audit of LP split-tree/Farkas proof artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from horizonlink.canonical import (
    sha256_file,
    write_json,
    write_sha256_sidecar,
)


TERM_RE = re.compile(r"([+-]?\d+)\s+x(\d+)")
REL_RE = re.compile(r"\s(>=|<=|=)\s*(-?\d+)\s*;\s*$")
HEADER_RE = re.compile(r"#variable=\s*(\d+)\s+#constraint=\s*(\d+)")


def _parse_opb(path: Path) -> dict[str, Any]:
    rows = []
    variable_count = None
    constraint_count = None
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("*"):
            header = HEADER_RE.search(line)
            if header:
                variable_count = int(header.group(1))
                constraint_count = int(header.group(2))
            continue
        relation = REL_RE.search(line)
        if relation is None:
            raise ValueError(f"cannot parse OPB line {line_number}: {line}")
        coefficients: dict[int, int] = {}
        for coefficient, variable in TERM_RE.findall(
            line[: relation.start()]
        ):
            index = int(variable)
            coefficients[index] = (
                coefficients.get(index, 0) + int(coefficient)
            )
        rows.append(
            {
                "coefficients": {
                    variable: coefficient
                    for variable, coefficient in coefficients.items()
                    if coefficient
                },
                "relation": relation.group(1),
                "rhs": int(relation.group(2)),
            }
        )
    if variable_count is None or constraint_count is None:
        raise ValueError(f"missing OPB header in {path}")
    if constraint_count != len(rows):
        raise ValueError(f"OPB constraint count mismatch in {path}")
    return {
        "variable_count": variable_count,
        "constraint_count": constraint_count,
        "rows": rows,
    }


def _normalize(row: dict[str, Any]) -> tuple[dict[int, int], int]:
    if row["relation"] == ">=":
        return dict(row["coefficients"]), int(row["rhs"])
    if row["relation"] == "<=":
        return (
            {
                variable: -coefficient
                for variable, coefficient in row["coefficients"].items()
            },
            -int(row["rhs"]),
        )
    raise ValueError("equality is not expected in the candidate corpus")


def _literal(variable: int, value: int) -> str:
    return f"x{variable}" if value == 0 else f"~x{variable}"


def _literal_matches(literal: str, assignments: dict[int, int]) -> bool:
    negated = literal.startswith("~")
    variable = int(literal[2:] if negated else literal[1:])
    return (
        variable in assignments
        and assignments[variable] == (1 if negated else 0)
    )


def _add_term(
    tokens: list[str], operand: str, multiplier: int, first: bool
) -> bool:
    if multiplier <= 0:
        raise ValueError("nonpositive proof multiplier")
    tokens.extend([operand, str(multiplier), "*"])
    if not first:
        tokens.append("+")
    return False


def _audit_tree(tree: dict[str, Any]) -> tuple[dict[str, bool], dict[int, dict[int, int]]]:
    nodes = tree["nodes"]
    node_map = {int(node["id"]): node for node in nodes}
    children: dict[int, dict[int, int]] = {}
    assignments_extend = True
    incoming_matches_parent_split = True
    for node in nodes:
        node_id = int(node["id"])
        if node["parent"] is None:
            continue
        parent_id = int(node["parent"])
        value = int(node["branch_value"])
        children.setdefault(parent_id, {})[value] = node_id
        parent = node_map[parent_id]
        parent_assignments = {
            int(key): int(item)
            for key, item in parent["assignments"].items()
        }
        expected = dict(parent_assignments)
        expected[int(parent["chosen_variable"])] = value
        observed = {
            int(key): int(item)
            for key, item in node["assignments"].items()
        }
        assignments_extend &= observed == expected
        incoming_matches_parent_split &= (
            int(node["branch_variable"])
            == int(parent["chosen_variable"])
        )
    branch_ids = {
        int(node["id"]) for node in nodes if node["type"] == "BRANCH"
    }
    leaf_ids = {
        int(node["id"])
        for node in nodes
        if node["type"] == "LP_INFEASIBLE_LEAF"
    }
    checks = {
        "tree_marked_complete": tree.get("complete") is True,
        "node_ids_contiguous": sorted(node_map) == list(range(len(nodes))),
        "root_is_unique_and_empty": (
            len(
                [
                    node
                    for node in nodes
                    if node["parent"] is None
                    and int(node["id"]) == 0
                    and node["assignments"] == {}
                ]
            )
            == 1
        ),
        "every_branch_has_children_zero_and_one": all(
            set(children.get(node_id, {})) == {0, 1}
            for node_id in branch_ids
        ),
        "every_nonroot_assignment_extends_parent": assignments_extend,
        "incoming_branch_variable_matches_parent": (
            incoming_matches_parent_split
        ),
        "leaf_list_exact": leaf_ids == set(map(int, tree["leaves"])),
        "node_count_exact": int(tree["node_count"]) == len(nodes),
        "leaf_count_exact": int(tree["leaf_count"]) == len(leaf_ids),
        "branch_count_exact": int(tree["branch_count"]) == len(branch_ids),
        "solve_count_exact": int(tree["solve_count"]) == len(nodes),
        "max_depth_exact": (
            int(tree["max_depth"])
            == max(int(node["depth"]) for node in nodes)
        ),
        "all_leaf_lp_statuses_unsat": all(
            node["lp_status"] == "SOLVER_UNSAT"
            and int(node["lp_reported_status"]) == 2
            for node in nodes
            if node["type"] == "LP_INFEASIBLE_LEAF"
        ),
    }
    return checks, children


def _audit_leaf(
    leaf: dict[str, Any],
    node: dict[str, Any],
    normalized_rows: list[tuple[dict[int, int], int]],
    variable_count: int,
) -> tuple[dict[str, bool], set[str]]:
    coefficients = [0] * variable_count
    rhs = 0
    row_ids_unique = len(
        {int(item["row_id_1based"]) for item in leaf["row_multipliers"]}
    ) == len(leaf["row_multipliers"])
    for item in leaf["row_multipliers"]:
        row_id = int(item["row_id_1based"])
        multiplier = int(item["multiplier"])
        row_coefficients, row_rhs = normalized_rows[row_id - 1]
        for variable, coefficient in row_coefficients.items():
            coefficients[variable - 1] += coefficient * multiplier
        rhs += row_rhs * multiplier
    for item in leaf["global_bound_multipliers"]:
        variable = int(item["variable"])
        multiplier = int(item["multiplier"])
        if item["kind"] == "lower":
            coefficients[variable - 1] += multiplier
        elif item["kind"] == "upper":
            coefficients[variable - 1] -= multiplier
            rhs -= multiplier
        else:
            raise ValueError("unknown global bound kind")
    global_coefficients = list(coefficients)
    global_rhs = rhs
    assignments = {
        int(key): int(value)
        for key, value in node["assignments"].items()
    }
    expected_clause = set()
    assumptions_unique = len(
        {int(item["variable"]) for item in leaf["assumption_multipliers"]}
    ) == len(leaf["assumption_multipliers"])
    assumptions_match = True
    for item in leaf["assumption_multipliers"]:
        variable = int(item["variable"])
        multiplier = int(item["multiplier"])
        kind = item["kind"]
        if kind == "assume0":
            coefficients[variable - 1] -= multiplier
            expected_value = 0
        elif kind == "assume1":
            coefficients[variable - 1] += multiplier
            rhs += multiplier
            expected_value = 1
        else:
            raise ValueError("unknown assumption kind")
        assumptions_match &= assignments.get(variable) == expected_value
        expected_clause.add(_literal(variable, expected_value))
    declared_clause = set(leaf["clause_literals_after_division"])

    expected_global_coefficients = [0] * variable_count
    assumed_one_weight = 0
    for item in leaf["assumption_multipliers"]:
        variable = int(item["variable"])
        multiplier = int(item["multiplier"])
        if item["kind"] == "assume0":
            expected_global_coefficients[variable - 1] += multiplier
        else:
            expected_global_coefficients[variable - 1] -= multiplier
            assumed_one_weight += multiplier
    expected_global_rhs = int(leaf["exact_margin"]) - assumed_one_weight
    checks = {
        "leaf_id_matches_tree": int(leaf["leaf_id"]) == int(node["id"]),
        "leaf_depth_matches_tree": int(leaf["depth"]) == int(node["depth"]),
        "leaf_assignments_match_tree": leaf["assignments"] == node["assignments"],
        "row_ids_unique_and_in_range": (
            row_ids_unique
            and all(
                1
                <= int(item["row_id_1based"])
                <= len(normalized_rows)
                for item in leaf["row_multipliers"]
            )
        ),
        "assumption_variables_unique": assumptions_unique,
        "all_multipliers_positive": all(
            int(item["multiplier"]) > 0
            for family in (
                leaf["row_multipliers"],
                leaf["global_bound_multipliers"],
                leaf["assumption_multipliers"],
            )
            for item in family
        ),
        "all_coefficients_cancel_with_assumptions": not any(coefficients),
        "exact_margin_recomputed": (
            rhs == int(leaf["exact_margin"]) and rhs > 0
        ),
        "assumptions_match_path": assumptions_match,
        "declared_clause_exact": declared_clause == expected_clause,
        "clause_nonempty": bool(declared_clause),
        "clause_falsified_by_path": all(
            _literal_matches(literal, assignments)
            for literal in declared_clause
        ),
        "global_cut_coefficients_exact": (
            global_coefficients == expected_global_coefficients
        ),
        "global_cut_rhs_exact": global_rhs == expected_global_rhs,
        "recorded_exact_checks_all_true": all(
            leaf["exact_checks"].values()
        ),
    }
    return checks, declared_clause


def _rebuild_proof(
    tree: dict[str, Any],
    leaves: dict[int, dict[str, Any]],
    constraint_count: int,
    children: dict[int, dict[int, int]],
) -> tuple[bytes, dict[str, Any]]:
    lines = [
        "pseudo-Boolean proof version 1.0",
        f"f {constraint_count}",
    ]
    next_id = constraint_count + 1
    node_constraint: dict[int, int] = {}
    node_clause: dict[int, set[str]] = {}
    for leaf_id in sorted(map(int, tree["leaves"])):
        leaf = leaves[leaf_id]
        tokens: list[str] = []
        first = True
        for item in leaf["row_multipliers"]:
            first = _add_term(
                tokens,
                str(item["row_id_1based"]),
                int(item["multiplier"]),
                first,
            )
        for item in leaf["global_bound_multipliers"]:
            operand = (
                f"x{item['variable']}"
                if item["kind"] == "lower"
                else f"~x{item['variable']}"
            )
            first = _add_term(
                tokens, operand, int(item["multiplier"]), first
            )
        tokens.extend([str(int(leaf["exact_margin"])), "d", "s"])
        lines.append("p " + " ".join(tokens))
        node_constraint[leaf_id] = next_id
        node_clause[leaf_id] = set(
            leaf["clause_literals_after_division"]
        )
        next_id += 1
    resolution_steps = 0
    propagations = 0
    for node in sorted(
        tree["nodes"],
        key=lambda item: (-int(item["depth"]), int(item["id"])),
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
            propagations += 1
        elif negative not in clause1:
            node_constraint[node_id] = id1
            node_clause[node_id] = set(clause1)
            propagations += 1
        else:
            lines.append(f"p {id0} {id1} + s")
            node_constraint[node_id] = next_id
            node_clause[node_id] = (
                clause0 - {positive}
            ) | (clause1 - {negative})
            next_id += 1
            resolution_steps += 1
        assignments = {
            int(key): int(value)
            for key, value in node["assignments"].items()
        }
        if not all(
            _literal_matches(literal, assignments)
            for literal in node_clause[node_id]
        ):
            raise AssertionError("intermediate clause is not path-falsified")
    lines.append(f"c {node_constraint[0]}")
    return (
        ("\n".join(lines) + "\n").encode("utf-8"),
        {
            "root_clause_empty": not node_clause[0],
            "final_contradiction_id": node_constraint[0],
            "resolution_steps": resolution_steps,
            "propagations": propagations,
            "proof_lines": len(lines),
        },
    )


def _audit_instance(
    record: dict[str, Any],
    candidate_directory: Path,
    split_directory: Path,
) -> dict[str, Any]:
    source_formula_path = (
        candidate_directory / record["source_formula"]["path"]
    )
    formula_path = split_directory / record["formula"]["path"]
    tree_path = split_directory / record["tree"]["path"]
    proof_path = split_directory / record["proof"]["path"]
    metadata_path = (
        split_directory / record["proof"]["metadata"]["path"]
    )
    certificate_path = (
        split_directory / record["certificate_artifact"]["path"]
    )
    source = _parse_opb(source_formula_path)
    formula = _parse_opb(formula_path)
    normalized_source = [_normalize(row) for row in source["rows"]]
    normalized_formula = [_normalize(row) for row in formula["rows"]]
    tree = json.loads(tree_path.read_text(encoding="utf-8"))
    tree_checks, children = _audit_tree(tree)
    node_map = {int(node["id"]): node for node in tree["nodes"]}
    leaf_documents: dict[int, dict[str, Any]] = {}
    leaf_audits = []
    for leaf_record in record["leaf_certificates"]:
        leaf_path = split_directory / leaf_record["path"]
        leaf = json.loads(leaf_path.read_text(encoding="utf-8"))
        leaf_id = int(leaf_record["leaf_id"])
        leaf_documents[leaf_id] = leaf
        checks, clause = _audit_leaf(
            leaf,
            node_map[leaf_id],
            normalized_formula,
            formula["variable_count"],
        )
        checks["leaf_hash_matches"] = (
            sha256_file(leaf_path) == leaf_record["sha256"]
        )
        checks["leaf_summary_exact_checks_passed"] = (
            leaf_record["all_exact_checks_passed"] is True
        )
        leaf_audits.append(
            {
                "leaf_id": leaf_id,
                "clause": sorted(clause),
                "checks": checks,
                "passed": all(checks.values()),
            }
        )
    rebuilt_proof, resolution = _rebuild_proof(
        tree,
        leaf_documents,
        formula["constraint_count"],
        children,
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    top_checks = {
        "source_formula_hash_matches": (
            sha256_file(source_formula_path)
            == record["source_formula"]["sha256"]
        ),
        "formula_hash_matches": (
            sha256_file(formula_path) == record["formula"]["sha256"]
        ),
        "tree_hash_matches": (
            sha256_file(tree_path) == record["tree"]["sha256"]
        ),
        "proof_hash_matches": (
            sha256_file(proof_path) == record["proof"]["sha256"]
        ),
        "proof_metadata_hash_matches": (
            sha256_file(metadata_path)
            == record["proof"]["metadata"]["sha256"]
        ),
        "certificate_hash_matches": (
            sha256_file(certificate_path)
            == record["certificate_artifact"]["sha256"]
        ),
        "native_and_verifier_rows_canonically_equal": (
            normalized_source == normalized_formula
        ),
        "formula_counts_equal": (
            source["variable_count"] == formula["variable_count"]
            and source["constraint_count"] == formula["constraint_count"]
        ),
        "proof_byte_identical_to_independent_rebuild": (
            proof_path.read_bytes() == rebuilt_proof
        ),
        "root_clause_empty": resolution["root_clause_empty"],
        "final_contradiction_id_matches": (
            resolution["final_contradiction_id"]
            == record["proof"]["expected_contradiction_id"]
            == metadata["final_contradiction_id"]
        ),
        "proof_metadata_counts_match": (
            resolution["resolution_steps"]
            == metadata["resolution_step_count"]
            and resolution["propagations"]
            == metadata["propagation_count"]
            and resolution["proof_lines"] == metadata["proof_line_count"]
        ),
        "certificate_status_proof_generated": (
            certificate["status"] == "PROOF_GENERATED"
            and certificate["formal_pruning_authorized"] is False
            and certificate["status_ledger"]["verification"]
            == "NOT_STARTED"
        ),
        "orbit_and_points_match_certificate": (
            certificate["orbit_index"] == record["orbit_index"]
            and certificate["candidate_minimum_points"]
            == record["candidate_minimum_points"]
        ),
    }
    passed = (
        all(tree_checks.values())
        and all(item["passed"] for item in leaf_audits)
        and all(top_checks.values())
    )
    return {
        "orbit_index": record["orbit_index"],
        "tree_checks": tree_checks,
        "leaf_audits": leaf_audits,
        "top_level_checks": top_checks,
        "resolution": resolution,
        "passed": passed,
    }


def _audit_checksums(directory: Path) -> dict[str, Any]:
    rows = []
    for line in (directory / "SHA256SUMS").read_text(
        encoding="utf-8"
    ).splitlines():
        expected, relative = line.split("  ", 1)
        path = directory / relative
        rows.append(
            {
                "path": relative,
                "expected_sha256": expected,
                "actual_sha256": sha256_file(path),
                "passed": sha256_file(path) == expected,
            }
        )
    expected_paths = sorted(
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file()
        and path.name != "SHA256SUMS"
        and not path.name.endswith(".sha256")
    )
    return {
        "entries": rows,
        "all_hashes_match": all(row["passed"] for row in rows),
        "path_set_exact": sorted(row["path"] for row in rows)
        == expected_paths,
    }


def audit(
    candidate_directory: Path,
    split_directory: Path,
    reference_release: Path,
) -> dict[str, Any]:
    manifest_path = split_directory / "farkas_corpus.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    instances = [
        _audit_instance(record, candidate_directory, split_directory)
        for record in manifest["instances"]
    ]
    provenance = manifest["reference_provenance"]
    with zipfile.ZipFile(reference_release) as archive:
        source_hash_checks = [
            {
                "archive_member": item["archive_member"],
                "expected_sha256": item["sha256"],
                "actual_sha256": hashlib.sha256(
                    archive.read(item["archive_member"])
                ).hexdigest(),
            }
            for item in provenance["source_scripts"]
        ]
    checksums = _audit_checksums(split_directory)
    sidecar_text = (
        manifest_path.with_name(manifest_path.name + ".sha256")
        .read_text(encoding="utf-8")
        .strip()
    )
    top_checks = {
        "manifest_status_proof_generated": (
            manifest["status"] == "PROOF_GENERATED"
        ),
        "orbit_indices_unique": (
            len({item["orbit_index"] for item in manifest["instances"]})
            == len(manifest["instances"])
        ),
        "all_instances_pass": all(item["passed"] for item in instances),
        "reference_archive_hash_matches": (
            sha256_file(reference_release)
            == provenance["archive_sha256"]
        ),
        "reference_script_hashes_match": all(
            item["expected_sha256"] == item["actual_sha256"]
            for item in source_hash_checks
        ),
        "manifest_sidecar_matches": sidecar_text
        == f"{sha256_file(manifest_path)}  {manifest_path.name}",
        "checksum_entries_all_match": checksums["all_hashes_match"],
        "checksum_path_set_exact": checksums["path_set_exact"],
        "summary_counts_match": (
            manifest["summary"]["proofs_generated"] == len(instances)
            and manifest["summary"]["complete_split_trees"] == len(instances)
            and manifest["summary"]["exact_leaf_certificates"]
            == sum(
                len(instance["leaf_audits"]) for instance in instances
            )
        ),
        "no_formal_pruning_before_verification": (
            manifest["summary"]["verified_unsat"] == 0
            and manifest["summary"]["formal_pruning_authorized"] == 0
            and manifest["scope"]["formal_orbit_pruning_authorized"]
            is False
        ),
    }
    return {
        "schema_version": "horizonmath.split-farkas-independent-audit.v1",
        "status": "PASS" if all(top_checks.values()) else "FAIL",
        "input": {
            "candidate_directory": str(candidate_directory),
            "split_directory": str(split_directory),
            "manifest_sha256": sha256_file(manifest_path),
            "reference_release_file": reference_release.name,
            "reference_release_sha256": sha256_file(reference_release),
        },
        "top_level_checks": top_checks,
        "instances": instances,
        "reference_source_hash_checks": source_hash_checks,
        "checksum_audit": checksums,
        "summary": {
            "instances": len(instances),
            "instances_passed": sum(item["passed"] for item in instances),
            "leaf_certificates": sum(
                len(item["leaf_audits"]) for item in instances
            ),
            "leaf_certificates_passed": sum(
                leaf["passed"]
                for item in instances
                for leaf in item["leaf_audits"]
            ),
            "proofs_byte_identical_to_independent_rebuild": sum(
                item["top_level_checks"][
                    "proof_byte_identical_to_independent_rebuild"
                ]
                for item in instances
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate-directory", type=Path, required=True
    )
    parser.add_argument("--split-directory", type=Path, required=True)
    parser.add_argument("--reference-release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(
            args.candidate_directory,
            args.split_directory,
            args.reference_release,
        )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "message": str(exc)}, indent=2))
        return 2
    write_json(args.output, report)
    write_sha256_sidecar(args.output)
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
