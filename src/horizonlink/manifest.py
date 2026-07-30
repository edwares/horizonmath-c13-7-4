"""Build deterministic structural-analysis manifests."""

from __future__ import annotations

from typing import Any

from horizonlink import __version__
from horizonlink.automorphisms import automorphism_manifest
from horizonlink.canonical import sha256_bytes
from horizonlink.input import InputFormatError, LinkDocument
from horizonlink.multiplicities import compute_multiplicities
from horizonlink.orbits import compute_subset_orbits
from horizonlink.validation import validate_cover


MANIFEST_SCHEMA_VERSION = "horizonmath.link-frontend-manifest.v1"


def _base_status_ledger() -> dict[str, str]:
    return {
        "link": "NOT_STARTED",
        "multiplicities": "NOT_STARTED",
        "automorphism_group": "NOT_STARTED",
        "candidate_minimum_point_set_orbits": "NOT_STARTED",
        "extension_degree_profiles": "NOT_STARTED",
        "screening": "NOT_STARTED",
        "formulas": "NOT_STARTED",
        "solver": "NOT_STARTED",
        "proof": "NOT_STARTED",
        "verification": "NOT_STARTED",
    }


def build_format_error_manifest(raw: bytes, error: InputFormatError) -> dict[str, Any]:
    status = _base_status_ledger()
    status["link"] = "ERROR"
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "tool": {
            "name": "horizonlink",
            "version": __version__,
            "stage": "structural-front-end",
        },
        "status": "ERROR",
        "input": {
            "raw_sha256": sha256_bytes(raw),
            "format_valid": False,
        },
        "format_validation": {
            "valid": False,
            "errors": error.errors,
        },
        "status_ledger": status,
    }


def build_manifest(link: LinkDocument, subset_size: int = 4) -> dict[str, Any]:
    multiplicities = compute_multiplicities(link.point_labels, link.blocks)
    validation = validate_cover(link, multiplicities)
    status_ledger = _base_status_ledger()
    status_ledger["multiplicities"] = "ENUMERATED"
    warnings = []
    if link.numbering_source.get("status") != "AUDITED":
        warnings.append(
            "Class numbering provenance is not AUDITED; structural results do "
            "not establish an exhaustive numbered catalog."
        )

    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "tool": {
            "name": "horizonlink",
            "version": __version__,
            "stage": "structural-front-end",
            "runtime_dependencies": [],
        },
        "status": "ERROR",
        "input": {
            "schema_version": link.canonical_document["schema_version"],
            "raw_sha256": link.raw_sha256,
            "canonical_document_sha256": link.canonical_document_sha256,
            "canonical_labeled_link_sha256": link.canonical_labeled_link_sha256,
            "content_was_canonical": link.content_was_canonical,
            "bytes_were_canonical_serialization": (
                link.bytes_were_canonical_serialization
            ),
            "class_index": link.class_index,
            "representative_id": link.representative_id,
            "numbering_source": link.numbering_source,
            "provenance": link.provenance,
            "normalized_document": link.canonical_document,
        },
        "format_validation": {"valid": True, "errors": []},
        "mathematical_validation": validation,
        "multiplicities": multiplicities,
        "automorphism_group": None,
        "candidate_minimum_point_sets": None,
        "provenance_assessment": {
            "numbering_source_status": link.numbering_source.get("status"),
            "ready_for_exhaustive_numbered_catalog_claim": (
                link.numbering_source.get("status") == "AUDITED"
            ),
            "warnings": warnings,
        },
        "status_ledger": status_ledger,
        "scope_guardrails": {
            "profiles_computed": False,
            "formulas_generated": False,
            "solver_run": False,
            "proof_generated": False,
            "certificate_verified": False,
            "class_elimination_claimed": False,
        },
    }

    if not validation["valid_15_block_C_12_6_3_cover"]:
        status_ledger["link"] = "ERROR"
        return manifest

    status_ledger["link"] = "ENUMERATED"
    automorphisms = automorphism_manifest(link.point_labels, link.blocks)
    group = tuple(
        tuple(permutation) for permutation in automorphisms["permutations"]
    )
    subset_orbits = compute_subset_orbits(
        link.point_labels, group, subset_size
    )
    candidate_minimum_point_sets = {
        "interpretation": (
            "Candidate subsets of full-degree-15 points. A hypothetical "
            "29-block C(13,7,4) cover has total degree excess 8 above 15, so "
            "at least four of its 12 non-link points have zero excess."
        ),
        **subset_orbits,
    }
    manifest["automorphism_group"] = automorphisms
    manifest["candidate_minimum_point_sets"] = candidate_minimum_point_sets
    status_ledger["automorphism_group"] = "ENUMERATED"
    status_ledger["candidate_minimum_point_set_orbits"] = "ENUMERATED"

    group_checks = automorphisms["audit_checks"]
    subset_checks = candidate_minimum_point_sets["accounting"]
    structural_checks_passed = (
        group_checks["identity_present"]
        and group_checks["permutations_unique"]
        and group_checks["generators_reproduce_group"]
        and group_checks["generated_group_order"] == automorphisms["order"]
        and subset_checks["all_candidates_accounted_for"]
        and subset_checks["members_unique"]
        and subset_checks["all_orbit_stabilizer_checks_pass"]
        and not subset_checks["unaccounted_candidates"]
        and subset_checks["duplicate_member_count"] == 0
    )
    manifest["structural_audit"] = {
        "all_checks_passed": structural_checks_passed,
        "checks": {
            "automorphism_group": automorphisms["audit_checks"],
            "candidate_minimum_point_set_accounting": (
                candidate_minimum_point_sets["accounting"]
            ),
        },
    }
    if structural_checks_passed:
        manifest["status"] = "ENUMERATED"
    else:
        manifest["status"] = "ERROR"
        status_ledger["automorphism_group"] = "ERROR"
        status_ledger["candidate_minimum_point_set_orbits"] = "ERROR"
    return manifest
