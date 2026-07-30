"""Deterministic solver-free census of the audited 68-link catalog."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from horizonlink.canonical import (
    compact_json_bytes,
    pretty_json_bytes,
    sha256_bytes,
    sha256_file,
    write_json,
)
from horizonlink.input import LinkDocument, parse_link_bytes
from horizonlink.manifest import build_manifest
from horizonlink.profiles import (
    compute_unscreened_degree_profile_orbit_census,
    degree_budget,
)


NUMBERING_SCHEMA_VERSION = "horizonmath.link-numbering-manifest.v1"
CLASS_CENSUS_SCHEMA_VERSION = (
    "horizonmath.structural-census-class.v1"
)
CENSUS_SCHEMA_VERSION = "horizonmath.structural-census.v1"
RANKING_SCHEMA_VERSION = "horizonmath.structural-ranking.v1"
EXPECTED_CLASS_COUNT = 68
STRUCTURAL_CENSUS_PRODUCER_VERSION = "0.5.0"
NUMBERING_LOGICAL_PATH = (
    "catalog_audit/build/authoritative/numbering.manifest.json"
)
CLASSIFICATION_LOGICAL_PATH = (
    "provenance/classification/audit/"
    "classification-provenance.audit.json"
)
CATALOG_INPUT_LOGICAL_PATH = "catalog_audit/data/catalog-input.json"
PAPER_CITATION = (
    "Gordon, Patashnik, Petro, and Taylor, "
    "Minimum (12, 6, 3) Covers, Theorem 5.9 and remarks"
)
PAPER_URI = "https://www.dmgordon.org/papers/c-12-6-3.pdf"


class CensusError(ValueError):
    """Raised when census provenance or accounting fails closed."""


class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load_json_object(path: Path) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        _DuplicateKeyError,
    ) as exc:
        raise CensusError(f"cannot load {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise CensusError(f"{path.name} must contain a JSON object")
    return value, sha256_bytes(raw)


def _audit_catalog_sources(
    numbering: dict[str, Any],
    numbering_sha256: str,
    classification: dict[str, Any],
) -> dict[str, Any]:
    entries = numbering.get("entries")
    indices = (
        [entry.get("class_index") for entry in entries]
        if isinstance(entries, list)
        and all(isinstance(entry, dict) for entry in entries)
        else []
    )
    labeled_hashes = (
        [
            entry.get("canonical_labeled_link_sha256")
            for entry in entries
        ]
        if isinstance(entries, list)
        and all(isinstance(entry, dict) for entry in entries)
        else []
    )
    invariant_hashes = (
        [entry.get("isomorphism_invariant_sha256") for entry in entries]
        if isinstance(entries, list)
        and all(isinstance(entry, dict) for entry in entries)
        else []
    )
    classification_checks = classification.get("checks")
    classification_inputs = classification.get("inputs", {})
    conclusions = classification.get("conclusions", {})
    checks = {
        "numbering_schema_supported": (
            numbering.get("schema_version")
            == NUMBERING_SCHEMA_VERSION
        ),
        "numbering_status_pass": numbering.get("status") == "PASS",
        "numbering_has_68_entries": (
            isinstance(entries, list)
            and len(entries) == EXPECTED_CLASS_COUNT
        ),
        "class_indices_are_exactly_1_through_68": (
            indices == list(range(1, EXPECTED_CLASS_COUNT + 1))
        ),
        "labeled_link_hashes_unique": (
            len(labeled_hashes) == EXPECTED_CLASS_COUNT
            and len(set(labeled_hashes)) == EXPECTED_CLASS_COUNT
        ),
        "isomorphism_invariant_hashes_present": (
            len(invariant_hashes) == EXPECTED_CLASS_COUNT
            and all(
                isinstance(value, str) and len(value) == 64
                for value in invariant_hashes
            )
        ),
        "every_numbering_entry_reports_valid": (
            isinstance(entries, list)
            and all(
                entry.get("validation", {}).get("valid") is True
                for entry in entries
            )
        ),
        "classification_audit_pass": (
            classification.get("overall_status") == "PASS"
        ),
        "classification_checks_all_true": (
            isinstance(classification_checks, dict)
            and bool(classification_checks)
            and all(classification_checks.values())
        ),
        "classification_references_numbering_hash": (
            classification_inputs.get("numbering_manifest", {}).get(
                "sha256"
            )
            == numbering_sha256
        ),
        "numbering_references_catalog_input_hash": (
            numbering.get("input_sha256")
            == classification_inputs.get("catalog_input", {}).get(
                "sha256"
            )
        ),
        "global_catalog_audited_against_published_theorem": (
            conclusions.get("global_68_class_catalog_exhaustiveness")
            == "AUDITED_AGAINST_PUBLISHED_THEOREM"
        ),
        "published_theorem_not_claimed_machine_formalized": (
            conclusions.get("formal_machine_verification_of_theorem_5_9")
            == "NOT_PERFORMED"
        ),
    }
    failed = [key for key, passed in checks.items() if not passed]
    if failed:
        raise CensusError(
            "catalog provenance audit failed: " + ", ".join(failed)
        )
    return {
        "checks": checks,
        "all_checks_passed": True,
        "numbering_status_scope": numbering.get("status_scope"),
    }


def _link_document_for_entry(
    entry: dict[str, Any],
    entry_index: int,
    *,
    numbering_sha256: str,
    classification_sha256: str,
    classification: dict[str, Any],
) -> LinkDocument:
    class_index = int(entry["class_index"])
    template = entry.get("template")
    paper_sha256 = classification["inputs"]["paper_pdf"]["sha256"]
    catalog_input_sha256 = classification["inputs"]["catalog_input"][
        "sha256"
    ]
    document = {
        "schema_version": "horizonmath.link-input.v1",
        "parameters": {
            "v": 12,
            "k": 6,
            "t": 3,
            "block_count": 15,
        },
        "point_labels": list(range(12)),
        "blocks": entry["normalized_labeled_link"],
        "identity": {
            "representative_id": (
                f"audited-catalog-class{class_index:02d}"
            ),
            "class_index": class_index,
            "numbering_source": {
                "status": "AUDITED",
                "citation": (
                    f"{PAPER_CITATION}; "
                    f"{NUMBERING_LOGICAL_PATH}"
                ),
                "selection": (
                    f"{NUMBERING_LOGICAL_PATH}: entries[{entry_index}]"
                ),
                "artifact_sha256": numbering_sha256,
                "notes": (
                    "The 1-through-68 labels are project-local. "
                    "Classes 1-67 are the independently audited Figure 1 "
                    "completion classes; class 68 is the distinct Figure 6 "
                    f"class. This entry is tagged {template!r}."
                ),
            },
        },
        "provenance": {
            "source_artifacts": [
                {
                    "name": NUMBERING_LOGICAL_PATH,
                    "sha256": numbering_sha256,
                },
                {
                    "name": CLASSIFICATION_LOGICAL_PATH,
                    "sha256": classification_sha256,
                },
                {
                    "name": CATALOG_INPUT_LOGICAL_PATH,
                    "sha256": catalog_input_sha256,
                },
                {
                    "name": "Minimum (12, 6, 3) Covers",
                    "uri": PAPER_URI,
                    "sha256": paper_sha256,
                },
            ],
            "extraction_rule": (
                f"Read entries[{entry_index}].normalized_labeled_link "
                "from the audited numbering manifest without relabeling; "
                "sort points within blocks and blocks lexicographically."
            ),
            "notes": (
                "The classification audit connects the project templates "
                "and 68-entry numbering map to the published exhaustive "
                "classification. The published theorem itself has not been "
                "machine-formalized."
            ),
        },
    }
    return parse_link_bytes(pretty_json_bytes(document))


def _compact_multiplicities(
    structural: dict[str, Any],
) -> dict[str, Any]:
    source = structural["multiplicities"]
    result: dict[str, Any] = {}
    for name in ("points", "pairs", "triples", "four_sets"):
        section = source[name]
        result[name] = {
            "subset_size": section["subset_size"],
            "subset_count": section["subset_count"],
            "total_incidence": section["total_incidence"],
            "expected_total_incidence": section[
                "expected_total_incidence"
            ],
            "histogram": section["histogram"],
            "table_sha256": section["table_sha256"],
        }
    result["point_multiplicities"] = [
        row["multiplicity"] for row in source["points"]["rows"]
    ]
    residual_sets = source["residual_four_sets"]["sets"]
    result["residual_four_sets"] = {
        "count": source["residual_four_sets"]["count"],
        "sets_sha256": sha256_bytes(
            compact_json_bytes(residual_sets)
        ),
    }
    return result


def _compact_candidate_orbits(
    structural: dict[str, Any],
) -> dict[str, Any]:
    source = structural["candidate_minimum_point_sets"]
    return {
        "interpretation": source["interpretation"],
        "algorithm": source["algorithm"],
        "subset_size": source["subset_size"],
        "universe_count": source["universe_count"],
        "orbit_count": source["orbit_count"],
        "member_count": source["member_count"],
        "orbit_sizes": source["orbit_sizes"],
        "representatives": source["representatives"],
        "partition_sha256": source["partition_sha256"],
        "orbits": [
            {
                "id": orbit["id"],
                "representative": orbit["representative"],
                "size": orbit["size"],
                "stabilizer_order": orbit["stabilizer_order"],
                "orbit_stabilizer_check": orbit[
                    "orbit_stabilizer_check"
                ],
            }
            for orbit in source["orbits"]
        ],
        "accounting": source["accounting"],
    }


def _catalog_comparison(
    entry: dict[str, Any],
    structural: dict[str, Any],
) -> dict[str, Any]:
    multiplicities = structural["multiplicities"]
    statistics = entry["statistics"]
    observed_points = [
        row["multiplicity"]
        for row in multiplicities["points"]["rows"]
    ]
    checks = {
        "class_index_equal": (
            structural["input"]["class_index"]
            == entry["class_index"]
        ),
        "canonical_labeled_link_sha256_equal": (
            structural["input"]["canonical_labeled_link_sha256"]
            == entry["canonical_labeled_link_sha256"]
        ),
        "catalog_entry_validation_passed": (
            entry["validation"]["valid"] is True
        ),
        "cover_validation_passed": (
            structural["mathematical_validation"][
                "valid_15_block_C_12_6_3_cover"
            ]
            is True
        ),
        "point_multiplicities_equal": (
            observed_points == statistics["point_multiplicities"]
        ),
        "pair_histogram_equal": (
            multiplicities["pairs"]["histogram"]
            == statistics["pair_multiplicity_histogram"]
        ),
        "triple_histogram_equal": (
            multiplicities["triples"]["histogram"]
            == statistics["triple_multiplicity_histogram"]
        ),
        "covered_four_set_count_equal": (
            495 - multiplicities["residual_four_sets"]["count"]
            == statistics["covered_four_set_count"]
        ),
        "residual_four_set_count_equal": (
            multiplicities["residual_four_sets"]["count"]
            == statistics["residual_four_set_count"]
        ),
    }
    return {
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def _build_class_record(
    entry: dict[str, Any],
    entry_index: int,
    link: LinkDocument,
) -> dict[str, Any]:
    structural = build_manifest(link, 4)
    if structural.get("status") != "ENUMERATED":
        raise CensusError(
            f"class {entry['class_index']} structural analysis failed"
        )
    comparison = _catalog_comparison(entry, structural)
    if not comparison["all_checks_passed"]:
        failed = [
            key
            for key, passed in comparison["checks"].items()
            if not passed
        ]
        raise CensusError(
            f"class {entry['class_index']} catalog comparison failed: "
            + ", ".join(failed)
        )

    point_labels = tuple(
        structural["input"]["normalized_document"]["point_labels"]
    )
    blocks = tuple(
        tuple(block)
        for block in structural["input"]["normalized_document"]["blocks"]
    )
    group = tuple(
        tuple(permutation)
        for permutation in structural["automorphism_group"][
            "permutations"
        ]
    )
    budget = degree_budget(point_labels, blocks)
    profile_census = (
        compute_unscreened_degree_profile_orbit_census(
            group,
            total_excess=budget["derivation"]["excess"],
            point_count=len(point_labels),
        )
    )
    candidate_orbits = _compact_candidate_orbits(structural)
    residual_count = structural["multiplicities"][
        "residual_four_sets"
    ]["count"]
    automorphisms = structural["automorphism_group"]
    ranking_metrics = {
        "unscreened_degree_profile_orbit_count": profile_census[
            "profile_orbit_count"
        ],
        "candidate_minimum_point_orbit_count": candidate_orbits[
            "orbit_count"
        ],
        "residual_four_set_count": residual_count,
        "automorphism_group_order": automorphisms["order"],
    }
    return {
        "schema_version": CLASS_CENSUS_SCHEMA_VERSION,
        "producer": {
            "name": "horizonlink",
            "version": STRUCTURAL_CENSUS_PRODUCER_VERSION,
        },
        "status": "ENUMERATED",
        "class_index": entry["class_index"],
        "catalog_entry_index": entry_index,
        "template": entry["template"],
        "input": {
            "path": f"inputs/class{entry['class_index']:02d}.link.json",
            "canonical_document_sha256": link.canonical_document_sha256,
            "canonical_labeled_link_sha256": (
                link.canonical_labeled_link_sha256
            ),
            "numbering_source": link.numbering_source,
        },
        "catalog_metadata": {
            key: entry.get(key)
            for key in (
                "full_completion_multiplicity",
                "full_discovery_index",
                "full_first_occurrence",
                "historical_prefix_multiplicity",
                "isomorphism_invariant_sha256",
                "numbering_source",
            )
        },
        "catalog_comparison": comparison,
        "mathematical_validation": structural[
            "mathematical_validation"
        ],
        "multiplicities": _compact_multiplicities(structural),
        "automorphism_group": {
            "algorithm": automorphisms["algorithm"],
            "order": automorphisms["order"],
            "group_sha256": automorphisms["group_sha256"],
            "generator_selection": automorphisms[
                "generator_selection"
            ],
            "generator_count": automorphisms["generator_count"],
            "generators": automorphisms["generators"],
            "audit_checks": automorphisms["audit_checks"],
            "search_statistics": automorphisms[
                "search_statistics"
            ],
        },
        "candidate_minimum_point_sets": candidate_orbits,
        "degree_budget": budget,
        "unscreened_degree_profile_orbit_census": profile_census,
        "ranking_metrics": ranking_metrics,
        "unavailable_difficulty_metrics": {
            "retained_profile_count": {
                "status": "NOT_STARTED",
                "value": None,
            },
            "root_lp_feasibility": {
                "status": "NOT_STARTED",
                "value": None,
            },
            "quick_solver_runtime": {
                "status": "NOT_STARTED",
                "value": None,
            },
            "estimated_proof_size": {
                "status": "NOT_STARTED",
                "value": None,
            },
        },
        "status_ledger": {
            "link": "ENUMERATED",
            "multiplicities": "ENUMERATED",
            "automorphism_group": "ENUMERATED",
            "candidate_minimum_point_set_orbits": "ENUMERATED",
            "unscreened_profile_orbit_count": "ENUMERATED",
            "screening": "NOT_STARTED",
            "extension_degree_profiles": "NOT_STARTED",
            "formulas": "NOT_STARTED",
            "root_lp": "NOT_STARTED",
            "solver": "NOT_STARTED",
            "proof": "NOT_STARTED",
            "verification": "NOT_STARTED",
        },
        "scope_guardrails": {
            "structural_census_completed": True,
            "every_candidate_orbit_representative_recorded": True,
            "profile_orbits_counted_by_burnside": True,
            "profile_representatives_generated": False,
            "screening_run": False,
            "formulas_generated": False,
            "root_lp_run": False,
            "solver_run": False,
            "proof_generated": False,
            "verifier_run": False,
            "class_elimination_claimed": False,
            "global_covering_number_claimed": False,
        },
    }


def _difficulty_key(record: dict[str, Any]) -> tuple[int, ...]:
    metrics = record["ranking_metrics"]
    return (
        metrics["unscreened_degree_profile_orbit_count"],
        metrics["candidate_minimum_point_orbit_count"],
        metrics["residual_four_set_count"],
        -metrics["automorphism_group_order"],
    )


def _difficulty_band(position: int) -> str:
    if position <= 23:
        return "EASIER_STRUCTURAL_THIRD"
    if position <= 45:
        return "MEDIAN_STRUCTURAL_THIRD"
    return "HARDER_STRUCTURAL_THIRD"


def _build_ranking(
    class_records: list[dict[str, Any]],
    class_artifacts: dict[int, dict[str, Any]],
    *,
    numbering_sha256: str,
    classification_sha256: str,
) -> dict[str, Any]:
    ordered = sorted(
        class_records,
        key=lambda record: (
            _difficulty_key(record),
            record["class_index"],
        ),
    )
    tie_groups: list[list[dict[str, Any]]] = []
    for record in ordered:
        if (
            not tie_groups
            or _difficulty_key(tie_groups[-1][0])
            != _difficulty_key(record)
        ):
            tie_groups.append([])
        tie_groups[-1].append(record)

    position_by_class: dict[int, dict[str, Any]] = {}
    position = 1
    for tie_group_index, group in enumerate(tie_groups):
        start = position
        end = position + len(group) - 1
        for record in group:
            position_by_class[record["class_index"]] = {
                "ordinal_position": position,
                "structural_rank": start,
                "tie_span": [start, end],
                "tie_group_id": f"tie{tie_group_index + 1:03d}",
                "tie_group_size": len(group),
                "difficulty_band": _difficulty_band(position),
            }
            position += 1

    rows = []
    for record in ordered:
        class_index = record["class_index"]
        rows.append(
            {
                **position_by_class[class_index],
                "class_index": class_index,
                "template": record["template"],
                **record["ranking_metrics"],
                "class_record": class_artifacts[class_index],
                "solver_dependent_metrics_status": "NOT_STARTED",
            }
        )

    easiest = rows[0]
    middle_seed = min(
        rows,
        key=lambda row: (
            abs(row["ordinal_position"] - 34.5),
            row["ordinal_position"],
        ),
    )
    middle_group = [
        row
        for row in rows
        if row["tie_group_id"] == middle_seed["tie_group_id"]
    ]
    median = min(middle_group, key=lambda row: row["class_index"])
    hardest_group = [
        row
        for row in rows
        if row["tie_group_id"] == rows[-1]["tie_group_id"]
    ]
    hardest = min(hardest_group, key=lambda row: row["class_index"])

    class_metric_index = [
        {
            "class_index": row["class_index"],
            "difficulty_key": [
                row["unscreened_degree_profile_orbit_count"],
                row["candidate_minimum_point_orbit_count"],
                row["residual_four_set_count"],
                -row["automorphism_group_order"],
            ],
        }
        for row in rows
    ]
    return {
        "schema_version": RANKING_SCHEMA_VERSION,
        "producer": {
            "name": "horizonlink",
            "version": STRUCTURAL_CENSUS_PRODUCER_VERSION,
        },
        "status": "ENUMERATED",
        "input": {
            "numbering_manifest_sha256": numbering_sha256,
            "classification_audit_sha256": classification_sha256,
            "class_metric_index_sha256": sha256_bytes(
                compact_json_bytes(class_metric_index)
            ),
        },
        "method": {
            "id": "solver-free-lexicographic-structural-proxy-v1",
            "direction": (
                "Ordinal position 1 is structurally easiest; position 68 "
                "is structurally hardest."
            ),
            "ordered_key": [
                {
                    "field": (
                        "unscreened_degree_profile_orbit_count"
                    ),
                    "direction": "ascending",
                    "reason": (
                        "Primary exact symmetry-reduced branching proxy "
                        "before screening."
                    ),
                },
                {
                    "field": (
                        "candidate_minimum_point_orbit_count"
                    ),
                    "direction": "ascending",
                    "reason": (
                        "Number of first-stage candidate cases."
                    ),
                },
                {
                    "field": "residual_four_set_count",
                    "direction": "ascending",
                    "reason": (
                        "Coverage-row count proxy in later PB models."
                    ),
                },
                {
                    "field": "automorphism_group_order",
                    "direction": "descending",
                    "reason": (
                        "Larger symmetry groups generally reduce distinct "
                        "branches."
                    ),
                },
                {
                    "field": "class_index",
                    "direction": "ascending",
                    "reason": (
                        "Deterministic ordering only; excluded from "
                        "structural tie groups."
                    ),
                },
            ],
            "limitations": [
                (
                    "This is a structural pre-ranking, not a measured solver "
                    "or proof difficulty result."
                ),
                (
                    "Retained-profile counts, root-LP feasibility, quick "
                    "solver runtimes, and proof-size estimates remain "
                    "NOT_STARTED."
                ),
                (
                    "Classes in the same tie group are indistinguishable "
                    "under the recorded structural key."
                ),
            ],
        },
        "summary": {
            "class_count": len(rows),
            "tie_group_count": len(tie_groups),
            "automorphism_group_order_histogram": {
                str(key): value
                for key, value in sorted(
                    Counter(
                        row["automorphism_group_order"] for row in rows
                    ).items()
                )
            },
            "profile_orbit_count_range": [
                min(
                    row["unscreened_degree_profile_orbit_count"]
                    for row in rows
                ),
                max(
                    row["unscreened_degree_profile_orbit_count"]
                    for row in rows
                ),
            ],
            "candidate_orbit_count_range": [
                min(
                    row["candidate_minimum_point_orbit_count"]
                    for row in rows
                ),
                max(
                    row["candidate_minimum_point_orbit_count"]
                    for row in rows
                ),
            ],
            "residual_four_set_count_range": [
                min(row["residual_four_set_count"] for row in rows),
                max(row["residual_four_set_count"] for row in rows),
            ],
        },
        "classes": rows,
        "provisional_three_class_pilot": {
            "status": "STRUCTURAL_ONLY_PRESELECTION",
            "solver_runs_authorized": False,
            "easy_high_symmetry": {
                "class_index": easiest["class_index"],
                "ordinal_position": easiest["ordinal_position"],
                "reason": (
                    "First in the solver-free structural ranking."
                ),
            },
            "median": {
                "class_index": median["class_index"],
                "ordinal_position": median["ordinal_position"],
                "tie_span": median["tie_span"],
                "reason": (
                    "Smallest class index in the structural tie group "
                    "intersecting the catalog midpoint."
                ),
            },
            "difficult_low_symmetry": {
                "class_index": hardest["class_index"],
                "ordinal_position": hardest["ordinal_position"],
                "tie_span": hardest["tie_span"],
                "reason": (
                    "Smallest class index in the hardest structural tie "
                    "group."
                ),
            },
            "guardrail": (
                "This preselection launches no formulas, LPs, solvers, "
                "proof generation, or verification."
            ),
        },
        "scope": {
            "structural_ranking_completed": True,
            "retained_profile_counts_computed": False,
            "root_lp_run": False,
            "solver_run": False,
            "proof_size_estimated": False,
            "pilot_solver_runs_launched": False,
        },
    }


def _write_ranking_csv(path: Path, ranking: dict[str, Any]) -> None:
    fieldnames = [
        "ordinal_position",
        "structural_rank",
        "tie_group_id",
        "tie_group_size",
        "tie_span_start",
        "tie_span_end",
        "difficulty_band",
        "class_index",
        "template",
        "automorphism_group_order",
        "residual_four_set_count",
        "candidate_minimum_point_orbit_count",
        "unscreened_degree_profile_orbit_count",
        "solver_dependent_metrics_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        for row in ranking["classes"]:
            writer.writerow(
                {
                    key: row[key]
                    for key in fieldnames
                    if key not in {"tie_span_start", "tie_span_end"}
                }
                | {
                    "tie_span_start": row["tie_span"][0],
                    "tie_span_end": row["tie_span"][1],
                }
            )


def _write_checksums(output_directory: Path) -> Path:
    targets = sorted(
        (
            path
            for path in output_directory.rglob("*")
            if path.is_file() and path.name != "SHA256SUMS"
        ),
        key=lambda path: path.relative_to(
            output_directory
        ).as_posix(),
    )
    checksum_path = output_directory / "SHA256SUMS"
    checksum_path.write_text(
        "".join(
            f"{sha256_file(path)}  "
            f"{path.relative_to(output_directory).as_posix()}\n"
            for path in targets
        ),
        encoding="utf-8",
    )
    return checksum_path


def generate_structural_census(
    numbering_manifest_path: Path,
    classification_audit_path: Path,
    output_directory: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate the complete audited 68-class solver-free census."""

    if output_directory.exists() and any(output_directory.iterdir()):
        raise CensusError(
            "structural census output directory must be empty"
        )
    numbering, numbering_sha256 = _load_json_object(
        numbering_manifest_path
    )
    classification, classification_sha256 = _load_json_object(
        classification_audit_path
    )
    provenance_audit = _audit_catalog_sources(
        numbering,
        numbering_sha256,
        classification,
    )

    prepared: list[
        tuple[dict[str, Any], LinkDocument, dict[str, Any]]
    ] = []
    for entry_index, entry in enumerate(numbering["entries"]):
        link = _link_document_for_entry(
            entry,
            entry_index,
            numbering_sha256=numbering_sha256,
            classification_sha256=classification_sha256,
            classification=classification,
        )
        class_record = _build_class_record(
            entry,
            entry_index,
            link,
        )
        prepared.append((entry, link, class_record))

    observed_indices = [
        record["class_index"] for _, _, record in prepared
    ]
    if observed_indices != list(range(1, EXPECTED_CLASS_COUNT + 1)):
        raise CensusError("a class disappeared from census preparation")
    if not all(
        record["scope_guardrails"]["solver_run"] is False
        and record["scope_guardrails"]["root_lp_run"] is False
        and record["scope_guardrails"]["formulas_generated"] is False
        for _, _, record in prepared
    ):
        raise CensusError("no-solver census scope guardrail failed")

    output_directory.mkdir(parents=True, exist_ok=True)
    inputs_directory = output_directory / "inputs"
    classes_directory = output_directory / "classes"
    inputs_directory.mkdir()
    classes_directory.mkdir()

    class_artifacts: dict[int, dict[str, Any]] = {}
    input_artifacts: dict[int, dict[str, Any]] = {}
    class_records: list[dict[str, Any]] = []
    for entry, link, class_record in prepared:
        class_index = int(entry["class_index"])
        input_path = (
            inputs_directory / f"class{class_index:02d}.link.json"
        )
        write_json(input_path, link.canonical_document)
        input_artifacts[class_index] = {
            "path": input_path.relative_to(
                output_directory
            ).as_posix(),
            "bytes": input_path.stat().st_size,
            "sha256": sha256_file(input_path),
        }
        class_record["input"]["file"] = input_artifacts[class_index]

        class_path = (
            classes_directory
            / f"class{class_index:02d}.structural-census.json"
        )
        write_json(class_path, class_record)
        class_artifacts[class_index] = {
            "path": class_path.relative_to(
                output_directory
            ).as_posix(),
            "bytes": class_path.stat().st_size,
            "sha256": sha256_file(class_path),
        }
        class_records.append(class_record)

    ranking = _build_ranking(
        class_records,
        class_artifacts,
        numbering_sha256=numbering_sha256,
        classification_sha256=classification_sha256,
    )
    ranking_path = output_directory / "ranking.json"
    write_json(ranking_path, ranking)
    ranking_csv_path = output_directory / "ranking.csv"
    _write_ranking_csv(ranking_csv_path, ranking)

    class_index_payload = [
        {
            "class_index": record["class_index"],
            "input": input_artifacts[record["class_index"]],
            "class_record": class_artifacts[record["class_index"]],
            "ranking_metrics": record["ranking_metrics"],
        }
        for record in class_records
    ]
    group_order_histogram = Counter(
        record["ranking_metrics"]["automorphism_group_order"]
        for record in class_records
    )
    census = {
        "schema_version": CENSUS_SCHEMA_VERSION,
        "producer": {
            "name": "horizonlink",
            "version": STRUCTURAL_CENSUS_PRODUCER_VERSION,
        },
        "status": "ENUMERATED",
        "input": {
            "numbering_manifest": {
                "logical_path": NUMBERING_LOGICAL_PATH,
                "sha256": numbering_sha256,
                "schema_version": numbering["schema_version"],
                "status": numbering["status"],
                "status_scope": numbering.get("status_scope"),
            },
            "classification_audit": {
                "logical_path": CLASSIFICATION_LOGICAL_PATH,
                "sha256": classification_sha256,
                "overall_status": classification["overall_status"],
            },
            "catalog_input_sha256": numbering["input_sha256"],
        },
        "provenance_audit": provenance_audit,
        "algorithm": {
            "id": "all-68-solver-free-structural-census-v1",
            "class_order": "ascending project class index 1 through 68",
            "per_class_stages": [
                "canonical labeled-link extraction",
                "15-block C(12,6,3) validation",
                "point/pair/triple/four-set multiplicities",
                "complete automorphism-group enumeration",
                "candidate minimum-point four-set orbits",
                "degree-budget derivation",
                "exact Burnside count of unscreened degree-profile orbits",
            ],
        },
        "summary": {
            "expected_class_count": EXPECTED_CLASS_COUNT,
            "enumerated_class_count": len(class_records),
            "class_indices": observed_indices,
            "all_classes_accounted_for": (
                observed_indices
                == list(range(1, EXPECTED_CLASS_COUNT + 1))
            ),
            "all_class_records_enumerated": all(
                record["status"] == "ENUMERATED"
                for record in class_records
            ),
            "automorphism_group_order_histogram": {
                str(key): value
                for key, value in sorted(
                    group_order_histogram.items()
                )
            },
            "class_index_sha256": sha256_bytes(
                compact_json_bytes(class_index_payload)
            ),
        },
        "classes": class_index_payload,
        "ranking": {
            "json": {
                "path": ranking_path.relative_to(
                    output_directory
                ).as_posix(),
                "bytes": ranking_path.stat().st_size,
                "sha256": sha256_file(ranking_path),
            },
            "csv": {
                "path": ranking_csv_path.relative_to(
                    output_directory
                ).as_posix(),
                "bytes": ranking_csv_path.stat().st_size,
                "sha256": sha256_file(ranking_csv_path),
            },
        },
        "status_ledger": {
            "catalog_provenance": "ENUMERATED",
            "link_inputs": "ENUMERATED",
            "structural_census": "ENUMERATED",
            "structural_ranking": "ENUMERATED",
            "screening": "NOT_STARTED",
            "formulas": "NOT_STARTED",
            "root_lp": "NOT_STARTED",
            "solver": "NOT_STARTED",
            "proof": "NOT_STARTED",
            "verification": "NOT_STARTED",
        },
        "scope_guardrails": {
            "all_68_classes_enumerated": True,
            "all_candidate_orbit_representatives_recorded": True,
            "profile_orbit_counts_are_unscreened": True,
            "retained_profile_counts_computed": False,
            "formulas_generated": False,
            "root_lp_run": False,
            "solver_run": False,
            "proof_generated": False,
            "verifier_run": False,
            "another_class_eliminated": False,
            "class52_elimination_reverified_in_this_stage": False,
            "C_13_7_4_equals_30_claimed": False,
        },
    }
    census_path = output_directory / "census.manifest.json"
    write_json(census_path, census)
    _write_checksums(output_directory)
    return census, ranking
