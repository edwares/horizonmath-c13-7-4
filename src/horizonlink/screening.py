"""Validate and apply a complete screening-decision ledger."""

from __future__ import annotations

import copy
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from horizonlink.canonical import canonical_document_sha256, sha256_file
from horizonlink.profiles import (
    compute_exact_minimum_set_orbits,
    compute_extension_degree_profiles,
    degree_budget,
)


SCREENING_SCHEMA_VERSION = "horizonmath.recovered-screening-ledger.v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ScreeningLedgerError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ScreeningLedgerError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_screening_ledger(path: Path) -> dict[str, Any]:
    try:
        ledger = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ScreeningLedgerError(f"cannot load screening ledger: {exc}") from exc
    if not isinstance(ledger, dict):
        raise ScreeningLedgerError("screening ledger must be a JSON object")
    if ledger.get("schema_version") != SCREENING_SCHEMA_VERSION:
        raise ScreeningLedgerError(
            "unsupported screening ledger schema version"
        )
    ledger["_loaded_from"] = {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
    }
    return ledger


def _candidate_screen_checks(
    manifest: dict[str, Any], ledger: dict[str, Any]
) -> tuple[list[int], list[dict[str, Any]]]:
    orbit_manifest = manifest["candidate_minimum_point_sets"]
    rows = ledger.get("candidate_orbit_screening")
    if not isinstance(rows, list):
        raise ScreeningLedgerError(
            "candidate_orbit_screening must be an array"
        )
    expected_indices = set(range(orbit_manifest["orbit_count"]))
    observed_indices = {row.get("orbit") for row in rows}
    if observed_indices != expected_indices or len(rows) != len(expected_indices):
        raise ScreeningLedgerError(
            "candidate screening must contain exactly one row per orbit"
        )

    comparisons = []
    retained = []
    for row in sorted(rows, key=lambda item: item["orbit"]):
        orbit_index = row["orbit"]
        representative_equal = (
            row.get("representative")
            == orbit_manifest["orbits"][orbit_index]["representative"]
        )
        valid_disposition = row.get("disposition") in {
            "RETAINED",
            "DISCARDED",
        }
        reason_present = isinstance(row.get("rule"), str) and bool(row["rule"])
        passed = representative_equal and valid_disposition and reason_present
        comparisons.append(
            {
                "orbit_index": orbit_index,
                "representative_equal": representative_equal,
                "valid_disposition": valid_disposition,
                "reason_present": reason_present,
                "passed": passed,
            }
        )
        if row.get("disposition") == "RETAINED":
            retained.append(orbit_index)
    return retained, comparisons


def _exact_case_checks(
    exact_sets: dict[str, Any], ledger: dict[str, Any]
) -> tuple[list[int], list[dict[str, Any]]]:
    rows = ledger.get("exact_minimum_set_screening")
    if not isinstance(rows, list):
        raise ScreeningLedgerError(
            "exact_minimum_set_screening must be an array"
        )
    expected_ids = set(range(exact_sets["orbit_count"]))
    observed_ids = {row.get("case_id") for row in rows}
    if observed_ids != expected_ids or len(rows) != len(expected_ids):
        raise ScreeningLedgerError(
            "exact-minimum-set screening must contain one row per case"
        )
    cases = {case["case_id"]: case for case in exact_sets["cases"]}
    comparisons = []
    retained = []
    for row in sorted(rows, key=lambda item: item["case_id"]):
        case = cases[row["case_id"]]
        minimum_set_equal = (
            row.get("minimum_set") == case["representative"]
        )
        size_equal = row.get("minimum_set_size") == case["size"]
        source_equal = row.get("source_candidate_orbit_index") == case[
            "source_candidate_orbit_index"
        ]
        valid_disposition = row.get("disposition") in {
            "RETAINED",
            "DISCARDED",
        }
        reason_present = (
            isinstance(row.get("rule_id"), str)
            and bool(row["rule_id"])
            and isinstance(row.get("mathematical_reason"), str)
            and bool(row["mathematical_reason"])
        )
        passed = (
            minimum_set_equal
            and size_equal
            and source_equal
            and valid_disposition
            and reason_present
        )
        comparisons.append(
            {
                "case_id": row["case_id"],
                "minimum_set_equal": minimum_set_equal,
                "minimum_set_size_equal": size_equal,
                "source_candidate_orbit_equal": source_equal,
                "valid_disposition": valid_disposition,
                "reason_present": reason_present,
                "passed": passed,
            }
        )
        if row.get("disposition") == "RETAINED":
            retained.append(row["case_id"])
    return retained, comparisons


def _profile_checks(
    profiles: dict[str, Any], ledger: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = ledger.get("degree_profile_screening")
    if not isinstance(rows, list):
        raise ScreeningLedgerError(
            "degree_profile_screening must be an array"
        )
    generated = {
        (row["case_id"], row["profile_id"]): row
        for row in profiles["profiles"]
    }
    observed_keys = {
        (row.get("case_id"), row.get("profile_id")) for row in rows
    }
    if observed_keys != set(generated) or len(rows) != len(generated):
        raise ScreeningLedgerError(
            "profile screening must contain one row per generated profile"
        )

    comparisons = []
    for row in sorted(
        rows, key=lambda item: (item["case_id"], item["profile_id"])
    ):
        key = (row["case_id"], row["profile_id"])
        generated_row = generated[key]
        vector_equal = (
            row.get("degree_profile") == generated_row["representative"]
        )
        extension_equal = (
            row.get("extension_degrees")
            == generated_row["extension_degrees"]
        )
        valid_disposition = row.get("disposition") in {
            "RETAINED",
            "DISCARDED",
        }
        reason_present = (
            isinstance(row.get("rule_id"), str)
            and bool(row["rule_id"])
            and isinstance(row.get("mathematical_reason"), str)
            and bool(row["mathematical_reason"])
        )
        valid_status = row.get("status") in {
            "SOLVER_UNSAT",
            "FORMULAS_GENERATED",
            "VERIFIED_UNSAT",
            "SAT",
            "TIMEOUT",
            "ERROR",
        }
        passed = (
            vector_equal
            and extension_equal
            and valid_disposition
            and reason_present
            and valid_status
        )
        comparisons.append(
            {
                "case_id": row["case_id"],
                "profile_id": row["profile_id"],
                "degree_profile_equal": vector_equal,
                "extension_degrees_equal": extension_equal,
                "valid_disposition": valid_disposition,
                "valid_status": valid_status,
                "reason_present": reason_present,
                "passed": passed,
            }
        )
    return comparisons


def _formula_metadata_checks(
    ledger: dict[str, Any],
) -> dict[str, Any]:
    profile_rows = ledger["degree_profile_screening"]
    retained_keys = {
        (row["case_id"], row["profile_id"])
        for row in profile_rows
        if row["disposition"] == "RETAINED"
    }
    formula_rows = ledger.get("formula_instances")
    if not isinstance(formula_rows, list):
        raise ScreeningLedgerError("formula_instances must be an array")

    rows = []
    for formula in formula_rows:
        key = (formula.get("case_id"), formula.get("profile_id"))
        hashes_valid = all(
            isinstance(formula.get(field), str)
            and SHA256_RE.fullmatch(formula[field]) is not None
            for field in (
                "native_formula_sha256",
                "canonical_formula_sha256",
                "published_formula_sha256",
                "published_proof_gzip_sha256",
            )
        )
        checks = {
            "profile_is_retained": key in retained_keys,
            "name_present": isinstance(formula.get("name"), str)
            and bool(formula["name"]),
            "hashes_valid": hashes_valid,
            "status_is_verified_unsat": (
                formula.get("status") == "VERIFIED_UNSAT"
            ),
            "canonical_comparison_passed": (
                formula.get("canonical_comparison_passed") is True
            ),
            "certificate_final_audit_passed": (
                formula.get("certificate_final_audit_passed") is True
            ),
        }
        checks["all_checks_passed"] = all(checks.values())
        rows.append(
            {
                "name": formula.get("name"),
                "case_id": formula.get("case_id"),
                "profile_id": formula.get("profile_id"),
                **checks,
            }
        )
    formula_keys = {
        (row.get("case_id"), row.get("profile_id")) for row in formula_rows
    }
    names = [row.get("name") for row in formula_rows]
    accounting = {
        "formula_names_unique": len(names) == len(set(names)),
        "every_retained_profile_has_a_formula": formula_keys == retained_keys,
        "no_discarded_profile_has_a_formula": formula_keys <= retained_keys,
        "all_formula_metadata_rows_pass": all(
            row["all_checks_passed"] for row in rows
        ),
    }
    accounting["all_checks_passed"] = all(accounting.values())
    return {"rows": rows, "accounting": accounting}


def extend_manifest_with_screening(
    structural_manifest: dict[str, Any],
    ledger: dict[str, Any],
) -> dict[str, Any]:
    """Return a copy extended through deterministic degree-profile enumeration."""

    manifest = copy.deepcopy(structural_manifest)
    if manifest.get("status") != "ENUMERATED":
        raise ScreeningLedgerError(
            "structural manifest must pass before screening can be applied"
        )
    expected_hash = manifest["input"]["canonical_labeled_link_sha256"]
    if ledger.get("canonical_labeled_link_sha256") != expected_hash:
        raise ScreeningLedgerError(
            "screening ledger refers to a different labeled link"
        )
    if ledger.get("class_index") != manifest["input"]["class_index"]:
        raise ScreeningLedgerError(
            "screening ledger class index does not match the link input"
        )

    group = tuple(
        tuple(permutation)
        for permutation in manifest["automorphism_group"]["permutations"]
    )
    point_labels = tuple(
        manifest["input"]["normalized_document"]["point_labels"]
    )
    blocks = tuple(
        tuple(block)
        for block in manifest["input"]["normalized_document"]["blocks"]
    )
    budget = degree_budget(point_labels, blocks)
    expected_budget = ledger.get("degree_budget", {})
    budget_checks = {
        "link_point_degrees_equal": (
            budget["link_point_degrees"]
            == expected_budget.get("link_point_degrees")
        ),
        "minimum_extension_degrees_equal": (
            budget["minimum_extension_degrees"]
            == expected_budget.get("minimum_extension_degrees")
        ),
        "extension_degree_sum_equal": (
            budget["derivation"]["extension_degree_sum"]
            == expected_budget.get("extension_degree_sum")
        ),
        "excess_equal": (
            budget["derivation"]["excess"] == expected_budget.get("excess")
        ),
    }
    budget_checks["all_checks_passed"] = all(budget_checks.values())

    retained_orbits, candidate_checks = _candidate_screen_checks(
        manifest, ledger
    )
    exact_sets = compute_exact_minimum_set_orbits(
        point_labels,
        group,
        manifest["candidate_minimum_point_sets"],
        retained_orbits,
    )
    profile_case_ids, exact_checks = _exact_case_checks(exact_sets, ledger)
    profiles = compute_extension_degree_profiles(
        point_labels,
        group,
        exact_sets,
        profile_case_ids,
        budget["minimum_extension_degrees"],
        budget["derivation"]["excess"],
    )
    profile_checks = _profile_checks(profiles, ledger)
    formula_metadata_checks = _formula_metadata_checks(ledger)

    profile_screen_rows = ledger["degree_profile_screening"]
    source_counts = Counter(row["source"] for row in profile_screen_rows)
    disposition_counts = Counter(
        row["disposition"] for row in profile_screen_rows
    )
    status_counts = Counter(row["status"] for row in profile_screen_rows)
    all_checks_passed = (
        budget_checks["all_checks_passed"]
        and all(row["passed"] for row in candidate_checks)
        and all(row["passed"] for row in exact_checks)
        and all(row["passed"] for row in profile_checks)
        and formula_metadata_checks["accounting"]["all_checks_passed"]
        and exact_sets["accounting"]["all_surviving_sets_accounted_for"]
        and profiles["accounting"]["all_raw_profiles_accounted_for"]
    )

    manifest["degree_budget"] = budget
    manifest["screening"] = {
        "ledger": {
            "schema_version": ledger["schema_version"],
            "canonical_document_sha256": canonical_document_sha256(
                {
                    key: value
                    for key, value in ledger.items()
                    if key != "_loaded_from"
                }
            ),
            "loaded_from": ledger.get("_loaded_from"),
            "provenance": ledger.get("provenance"),
        },
        "candidate_orbit_decisions": ledger["candidate_orbit_screening"],
        "exact_minimum_set_decisions": ledger[
            "exact_minimum_set_screening"
        ],
        "degree_profile_decisions": profile_screen_rows,
        "summary": {
            "candidate_orbits_retained": len(retained_orbits),
            "candidate_orbits_discarded": len(candidate_checks)
            - len(retained_orbits),
            "exact_minimum_set_cases_retained": len(profile_case_ids),
            "exact_minimum_set_cases_discarded": len(exact_checks)
            - len(profile_case_ids),
            "profile_sources": dict(sorted(source_counts.items())),
            "profile_dispositions": dict(sorted(disposition_counts.items())),
            "profile_statuses": dict(sorted(status_counts.items())),
        },
        "comparison": {
            "degree_budget": budget_checks,
            "candidate_orbits": candidate_checks,
            "exact_minimum_sets": exact_checks,
            "degree_profiles": profile_checks,
            "prior_formula_metadata": formula_metadata_checks,
            "all_checks_passed": all_checks_passed,
        },
    }
    manifest["exact_minimum_point_sets"] = exact_sets
    manifest["extension_degree_profiles"] = profiles
    manifest["prior_formula_corpus"] = {
        "interpretation": (
            "Historical formula/proof hashes supplied for regression. The "
            "current run has not regenerated or reverified these formulas."
        ),
        "instances": ledger.get("formula_instances", []),
        "comparison": formula_metadata_checks,
        "expected_regression": ledger.get("expected_regression"),
        "status_assessment": ledger.get("status_assessment"),
    }
    manifest["status_ledger"]["extension_degree_profiles"] = (
        "ENUMERATED" if all_checks_passed else "ERROR"
    )
    manifest["status_ledger"]["screening"] = (
        "ENUMERATED" if all_checks_passed else "ERROR"
    )
    manifest["scope_guardrails"]["profiles_computed"] = True
    manifest["scope_guardrails"]["historical_screening_ledger_loaded"] = True
    manifest["scope_guardrails"]["current_run_generated_formulas"] = False
    manifest["scope_guardrails"]["current_run_verified_certificates"] = False
    manifest["provenance_assessment"]["warnings"].extend(
        ledger.get("provenance", {}).get("limitations", [])
    )
    manifest["status"] = "ENUMERATED" if all_checks_passed else "ERROR"
    return manifest
