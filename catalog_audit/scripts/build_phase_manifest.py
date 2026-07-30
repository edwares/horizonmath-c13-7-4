#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def pretty_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def artifact(path: Path, *, status: str | None = None) -> dict[str, object]:
    result: dict[str, object] = {
        "path": path.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }
    if status is not None:
        result["status"] = status
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    source_archive = args.source_archive.resolve()
    run = root / "build" / "run2"

    catalog = json.loads(
        (run / "catalog.audit.manifest.json").read_text(encoding="utf-8")
    )
    independent = json.loads(
        (run / "catalog.independent-audit.json").read_text(encoding="utf-8")
    )
    bundle = json.loads(
        (run / "bundle-numbering.audit.json").read_text(encoding="utf-8")
    )
    determinism = json.loads(
        (run / "determinism.audit.json").read_text(encoding="utf-8")
    )
    source_inventory = json.loads(
        (root / "SOURCE_INVENTORY.json").read_text(encoding="utf-8")
    )
    statuses = {
        "catalog_audit": catalog["status"],
        "independent_audit": independent["status"],
        "bundle_numbering_audit": bundle["status"],
        "determinism_audit": determinism["status"],
    }
    status = "PASS" if set(statuses.values()) == {"PASS"} else "FAIL"

    manifest = {
        "schema_version": "horizonmath.link-catalog-phase-manifest.v1",
        "release_version": "0.1.0",
        "status": status,
        "statuses": statuses,
        "source": {
            "archive": {
                "path": f"source_archives/{source_archive.name}",
                "bytes": source_archive.stat().st_size,
                "sha256": digest(source_archive),
            },
            "expected_archive_sha256": (
                "06ae94d3fd8a7e7f91d8022bd8f0a05a87775ef65eca1bd8cb6460c3cbca18e1"
            ),
            "archive_hash_matches_expected": digest(source_archive)
            == "06ae94d3fd8a7e7f91d8022bd8f0a05a87775ef65eca1bd8cb6460c3cbca18e1",
            "internal_sha256_entries_checked": bundle["internal_integrity"][
                "sha256_entries_checked"
            ],
            "internal_sha256_mismatch_count": bundle["internal_integrity"][
                "sha256_mismatch_count"
            ],
        },
        "upstream_checkpoint": {
            "name": "HorizonMath_horizonlink_frontend_v0.4.0.zip",
            "sha256": (
                "1eb19f63c94f303e9a275d5c82444cfc34ff3ce47f48f7063361310858dac4de"
            ),
            "purpose": (
                "Previously audited class-52 link-to-formula and candidate "
                "certificate checkpoint; not embedded in this phase archive."
            ),
        },
        "environment": {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "production_classifier_external_dependencies": [],
            "independent_auditor_external_dependencies": [],
        },
        "results": {
            "first_template_completions": catalog["enumeration"][
                "enumerated_completion_count"
            ],
            "invalid_completions": catalog["enumeration"][
                "invalid_completion_count"
            ],
            "first_template_classes": catalog["enumeration"][
                "discovered_first_template_class_count"
            ],
            "classes_first_seen_after_archived_prefix": catalog["enumeration"][
                "classes_first_seen_after_archived_prefix"
            ],
            "explicit_numbering_entries": independent["audited"][
                "numbering_entries"
            ],
            "independent_completion_rows": independent["audited"][
                "completion_rows"
            ],
            "independent_ambiguous_assignments": independent["audited"][
                "ambiguous_completion_count"
            ],
            "independent_wrong_assignments": independent["audited"][
                "wrong_assignment_count"
            ],
            "numbered_classes_checked_against_bundle": bundle["summary"][
                "classes_checked"
            ],
            "numbered_classes_passed_against_bundle": bundle["summary"][
                "classes_passed"
            ],
            "residual_coverage_clauses_checked": bundle["summary"][
                "cnf_residual_coverage_clauses_checked"
            ],
            "class52_canonical_labeled_link_sha256": independent["audited"][
                "class52_canonical_labeled_link_sha256"
            ],
        },
        "artifacts": {
            "catalog_input": artifact(root / "data" / "catalog-input.json"),
            "catalog_manifest": artifact(
                run / "catalog.audit.manifest.json", status=catalog["status"]
            ),
            "completion_ledger": artifact(run / "completion-ledger.jsonl"),
            "numbering_manifest": artifact(
                run / "numbering.manifest.json", status=catalog["status"]
            ),
            "independent_audit": artifact(
                run / "catalog.independent-audit.json",
                status=independent["status"],
            ),
            "bundle_numbering_audit": artifact(
                run / "bundle-numbering.audit.json", status=bundle["status"]
            ),
            "determinism_audit": artifact(
                run / "determinism.audit.json", status=determinism["status"]
            ),
            "source_inventory": artifact(root / "SOURCE_INVENTORY.json"),
            "phase_report": artifact(root / "NUMBERING_PHASE_AUDIT.md"),
        },
        "source_status": source_inventory["status"],
        "claim_authorization": {
            "complete_recovered_first_template_enumeration": status == "PASS",
            "internal_project_numbering_map_1_through_68": status == "PASS",
            "two_template_mathematical_exhaustiveness": False,
            "global_68_class_exhaustiveness": False,
            "another_link_class_analyzed": False,
            "another_link_class_eliminated": False,
            "C_13_7_4_equals_30": False,
        },
        "next_bounded_task": (
            "Audit the authoritative classification theorem/template derivation "
            "and build a literature-to-project representative map before running "
            "the front end on another class."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(pretty_bytes(manifest))
    print(
        json.dumps(
            {
                "status": status,
                "output": str(args.output.resolve()),
                "sha256": digest(args.output),
            },
            sort_keys=True,
        )
    )
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
