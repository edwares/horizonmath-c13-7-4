#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from catalog_audit.core import (
    canonical_json_bytes,
    classify_completions,
    exact_isomorphism,
    expected_completion_count,
    invariant_sha256,
    link_sha256,
    link_statistics,
    normalize_link,
    validate_link,
)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    input_path = args.input.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    spec = json.loads(input_path.read_text(encoding="utf-8"))
    parameters = spec["parameters"]
    point_count = int(parameters["point_count"])
    block_size = int(parameters["block_size"])
    block_count = int(parameters["link_block_count"])
    cover_strength = int(parameters["cover_strength"])
    historical = spec["historical_catalog"]
    historical_reps = [
        normalize_link(link) for link in historical["archived_representatives"]
    ]

    result = classify_completions(spec)

    discovery_to_historical: list[int | None] = []
    comparison_rows: list[dict[str, object]] = []
    for discovery_index, representative in enumerate(result.representatives, 1):
        matches = [
            index
            for index, historical_rep in enumerate(historical_reps, 1)
            if exact_isomorphism(
                representative, historical_rep, point_count=point_count
            )
        ]
        historical_index = matches[0] if len(matches) == 1 else None
        discovery_to_historical.append(historical_index)
        comparison_rows.append(
            {
                "discovered_class_index": discovery_index,
                "historical_class_index": historical_index,
                "historical_match_count": len(matches),
                "first_occurrence": result.first_occurrences[discovery_index - 1],
                "first_choices": [
                    list(choice)
                    for choice in result.first_choices[discovery_index - 1]
                ],
                "discovered_labeled_hash": link_sha256(
                    representative, point_count=point_count
                ),
                "historical_labeled_hash": (
                    link_sha256(
                        historical_reps[historical_index - 1],
                        point_count=point_count,
                    )
                    if historical_index is not None
                    else None
                ),
                "labeled_representative_identical": (
                    historical_index is not None
                    and representative == historical_reps[historical_index - 1]
                ),
                "prefix_count": result.prefix_counts[discovery_index - 1],
                "full_count": result.full_counts[discovery_index - 1],
            }
        )

    historical_to_discovery = {
        historical_index: discovery_index
        for discovery_index, historical_index in enumerate(
            discovery_to_historical, 1
        )
        if historical_index is not None
    }
    fig6 = normalize_link(spec["second_template"]["representatives"][0])
    fig6_matches = [
        index
        for index, representative in enumerate(result.representatives, 1)
        if exact_isomorphism(fig6, representative, point_count=point_count)
    ]

    pairwise_collisions: list[tuple[int, int]] = []
    for left in range(len(result.representatives)):
        for right in range(left):
            if exact_isomorphism(
                result.representatives[left],
                result.representatives[right],
                point_count=point_count,
            ):
                pairwise_collisions.append((right + 1, left + 1))

    numbering_entries: list[dict[str, object]] = []
    for historical_index, historical_rep in enumerate(historical_reps, 1):
        discovery_index = historical_to_discovery.get(historical_index)
        validation = validate_link(
            historical_rep,
            point_count=point_count,
            block_size=block_size,
            block_count=block_count,
            cover_strength=cover_strength,
        )
        numbering_entries.append(
            {
                "class_index": historical_index,
                "numbering_source": (
                    "metadata/link_classes.json representatives"
                    f"[{historical_index - 1}]"
                ),
                "template": "first_template",
                "normalized_labeled_link": [
                    list(block) for block in historical_rep
                ],
                "canonical_labeled_link_sha256": link_sha256(
                    historical_rep, point_count=point_count
                ),
                "isomorphism_invariant_sha256": invariant_sha256(
                    historical_rep, point_count
                ),
                "validation": validation,
                "statistics": link_statistics(historical_rep, point_count),
                "full_completion_multiplicity": (
                    result.full_counts[discovery_index - 1]
                    if discovery_index is not None
                    else None
                ),
                "historical_prefix_multiplicity": historical[
                    "archived_prefix_counts"
                ][historical_index - 1],
                "full_discovery_index": discovery_index,
                "full_first_occurrence": (
                    result.first_occurrences[discovery_index - 1]
                    if discovery_index is not None
                    else None
                ),
            }
        )

    fig6_validation = validate_link(
        fig6,
        point_count=point_count,
        block_size=block_size,
        block_count=block_count,
        cover_strength=cover_strength,
    )
    numbering_entries.append(
        {
            "class_index": 68,
            "numbering_source": "metadata/link_classes.json fig6",
            "template": "second_template",
            "normalized_labeled_link": [list(block) for block in fig6],
            "canonical_labeled_link_sha256": link_sha256(
                fig6, point_count=point_count
            ),
            "isomorphism_invariant_sha256": invariant_sha256(fig6, point_count),
            "validation": fig6_validation,
            "statistics": link_statistics(fig6, point_count),
            "full_completion_multiplicity": None,
            "historical_prefix_multiplicity": None,
            "full_discovery_index": None,
            "full_first_occurrence": None,
        }
    )

    expected = expected_completion_count(spec)
    historical_count = int(historical["archived_num_classes_fig1"])
    archived_prefix_counts = [int(x) for x in historical["archived_prefix_counts"]]
    prefix_exact = (
        result.prefix_counts[:historical_count] == archived_prefix_counts
        and all(count == 0 for count in result.prefix_counts[historical_count:])
    )
    comparison_exact = (
        len(result.representatives) == historical_count
        and discovery_to_historical == list(range(1, historical_count + 1))
        and all(row["labeled_representative_identical"] for row in comparison_rows)
    )
    checks = {
        "expected_completion_count_enumerated": len(result.ledger) == expected,
        "every_completion_is_valid_cover": not result.invalid_completions,
        "completion_counts_sum_to_expected": sum(result.full_counts) == expected,
        "historical_prefix_counts_exact": prefix_exact,
        "historical_representative_order_and_labels_exact": comparison_exact,
        "no_new_first_template_class_after_archived_early_stop": (
            len(result.representatives) == historical_count
        ),
        "first_template_representatives_pairwise_nonisomorphic": (
            not pairwise_collisions
        ),
        "fig6_valid_cover": bool(fig6_validation["valid"]),
        "fig6_nonisomorphic_to_every_first_template_class": not fig6_matches,
        "explicit_numbering_has_68_entries": len(numbering_entries) == 68,
    }
    conditional_status = "PASS" if all(checks.values()) else "FAIL"

    ledger_path = output / "completion-ledger.jsonl"
    with ledger_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in result.ledger:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )

    numbering_manifest = {
        "schema_version": "horizonmath.link-numbering-manifest.v1",
        "input_sha256": digest(input_path),
        "status": conditional_status,
        "status_scope": (
            "Conditional on the recovered first- and second-template input; "
            "not a proof that those templates exhaust all minimum C(12,6,3) covers."
        ),
        "entries": numbering_entries,
    }
    numbering_path = output / "numbering.manifest.json"
    write_json(numbering_path, numbering_manifest)

    run_manifest = {
        "schema_version": "horizonmath.link-catalog-audit.v1",
        "status": conditional_status,
        "checks": checks,
        "claim_authorization": {
            "recovered_template_catalog_consistency": conditional_status == "PASS",
            "project_numbering_map_1_through_68": conditional_status == "PASS",
            "two_template_exhaustiveness": False,
            "global_68_class_exhaustiveness": False,
            "analyze_another_link_class": False,
            "claim_C_13_7_4_equals_30": False,
        },
        "input": {
            "path": input_path.name,
            "sha256": digest(input_path),
            "source_archive": spec["source_provenance"]["archive_name"],
            "source_archive_sha256": spec["source_provenance"]["archive_sha256"],
        },
        "environment": {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "classifier_dependencies": ["Python standard library"],
        },
        "enumeration": {
            "expected_completion_count": expected,
            "enumerated_completion_count": len(result.ledger),
            "invalid_completion_count": len(result.invalid_completions),
            "discovered_first_template_class_count": len(result.representatives),
            "full_class_counts": result.full_counts,
            "first_occurrences": result.first_occurrences,
            "classes_first_seen_after_archived_prefix": [
                index
                for index, first in enumerate(result.first_occurrences, 1)
                if first > int(historical["archived_num_completions"])
            ],
        },
        "historical_comparison": {
            "archived_prefix_completion_count": historical[
                "archived_num_completions"
            ],
            "archived_first_template_class_count": historical_count,
            "archived_prefix_counts": archived_prefix_counts,
            "recomputed_prefix_counts": result.prefix_counts,
            "discovery_to_historical_class": discovery_to_historical,
            "rows": comparison_rows,
            "pairwise_first_template_collisions": [
                list(pair) for pair in pairwise_collisions
            ],
            "fig6_first_template_matches": fig6_matches,
        },
        "outputs": {
            "completion_ledger": {
                "path": ledger_path.name,
                "rows": len(result.ledger),
                "sha256": digest(ledger_path),
            },
            "numbering_manifest": {
                "path": numbering_path.name,
                "entries": len(numbering_entries),
                "sha256": digest(numbering_path),
            },
        },
        "unresolved_provenance": spec["claim_boundary"]["missing_evidence"],
    }
    run_path = output / "catalog.audit.manifest.json"
    write_json(run_path, run_manifest)
    print(
        json.dumps(
            {
                "status": conditional_status,
                "checks": checks,
                "catalog_manifest": str(run_path),
                "catalog_manifest_sha256": digest(run_path),
                "numbering_manifest_sha256": digest(numbering_path),
                "completion_ledger_sha256": digest(ledger_path),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
