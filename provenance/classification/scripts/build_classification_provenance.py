#!/usr/bin/env python3
"""Build the literature-to-project classification provenance bridge.

This script combines:

* text anchors and incidence matrices extracted from the primary paper;
* the complete first-template enumeration audit;
* the independent isomorphism audit; and
* the project numbering/bundle audit.

It does not attempt to formalize the published mathematical proof.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
from pathlib import Path
from typing import Any

import pdfplumber


SCHEMA_VERSION = "1"


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_text(text: str) -> str:
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def normalized_block_set(blocks: list[list[int]]) -> list[list[int]]:
    return sorted(sorted(int(x) for x in block) for block in blocks)


def check_text_anchors(pdf_path: Path) -> dict[str, Any]:
    specifications = [
        {
            "anchor_id": "lemma_2_1_figure1_covers",
            "pdf_page_number": 2,
            "section": "Lemma 2.1",
            "patterns": [
                r"Lemma 2\.1",
                r"fifteen blocks in Figure 1",
                r"element-minimal \(12,6,3\) covering family",
            ],
            "role": "Establishes the Figure 1 partial-block family used by the classification.",
        },
        {
            "anchor_id": "theorem_4_4_minimum_size",
            "pdf_page_number": 7,
            "section": "Theorem 4.4",
            "patterns": [
                r"Theorem 4\.4",
                r"covering number C\(12,6,3\) = 15",
            ],
            "role": "Identifies 15-block covers as minimum covers.",
        },
        {
            "anchor_id": "lemma_5_7_no_duplicate_case",
            "pdf_page_number": 11,
            "section": "Lemma 5.7",
            "patterns": [
                r"Lemma 5\.7",
                r"without a duplicate 777-triple",
                r"completion of the covering family in Figure 1",
            ],
            "role": "Routes the no-duplicate-777 case to Figure 1 completions.",
        },
        {
            "anchor_id": "lemma_5_8_duplicate_case",
            "pdf_page_number": 13,
            "section": "Lemma 5.8",
            "patterns": [
                r"Lemma 5\.8",
                r"containing a duplicate 777-triple",
                r"Figure 1 or to the cover of Figure 6",
            ],
            "role": "Routes the duplicate-777 case to Figure 1 completions or Figure 6.",
        },
        {
            "anchor_id": "theorem_5_9_two_template_exhaustiveness",
            "pdf_page_number": 15,
            "section": "Theorem 5.9",
            "patterns": [
                r"Theorem 5\.9",
                r"Any minimum \(12,6,3\) cover is isomorphic to a completion",
                r"Figure 1 or to the element-minimal cover of Figure 6, but not both",
            ],
            "role": "Published mathematical exhaustiveness and disjointness theorem.",
        },
        {
            "anchor_id": "published_computational_count",
            "pdf_page_number": 15,
            "section": "Remarks following Theorem 5.9",
            "patterns": [
                r"computer calculations",
                r"Figure 1 has exactly 67 nonisomorphic completions",
                r"exactly 68 nonisomorphic minimum \(12,6,3\) covers in all",
            ],
            "role": "Published computational count independently audited by the project enumeration.",
        },
    ]

    with pdfplumber.open(pdf_path) as pdf:
        pages = [
            normalize_text(page.extract_text(x_tolerance=2, y_tolerance=3) or "")
            for page in pdf.pages
        ]

    anchors = []
    for spec in specifications:
        page_text = pages[spec["pdf_page_number"] - 1]
        pattern_results = [
            {
                "pattern": pattern,
                "matched": re.search(pattern, page_text) is not None,
            }
            for pattern in spec["patterns"]
        ]
        anchors.append(
            {
                "anchor_id": spec["anchor_id"],
                "pdf_page_number": spec["pdf_page_number"],
                "section": spec["section"],
                "role": spec["role"],
                "normalized_page_text_sha256": hashlib.sha256(
                    (page_text + "\n").encode("utf-8")
                ).hexdigest(),
                "pattern_results": pattern_results,
                "status": (
                    "PASS"
                    if all(result["matched"] for result in pattern_results)
                    else "FAIL"
                ),
            }
        )
    return {
        "method": (
            "Extract page text with pdfplumber, dehyphenate line wraps, normalize "
            "whitespace, and require all section-specific regular-expression anchors."
        ),
        "anchors": anchors,
        "status": "PASS" if all(a["status"] == "PASS" for a in anchors) else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--paper-templates", type=Path, required=True)
    parser.add_argument("--template-comparison", type=Path, required=True)
    parser.add_argument("--catalog-input", type=Path, required=True)
    parser.add_argument("--catalog-audit", type=Path, required=True)
    parser.add_argument("--independent-audit", type=Path, required=True)
    parser.add_argument("--numbering-manifest", type=Path, required=True)
    parser.add_argument("--bundle-numbering-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    input_paths = {
        name: path.resolve()
        for name, path in {
            "paper_pdf": args.pdf,
            "paper_templates": args.paper_templates,
            "template_comparison": args.template_comparison,
            "catalog_input": args.catalog_input,
            "catalog_audit": args.catalog_audit,
            "independent_audit": args.independent_audit,
            "numbering_manifest": args.numbering_manifest,
            "bundle_numbering_audit": args.bundle_numbering_audit,
        }.items()
    }
    inputs = {name: load_json(path) for name, path in input_paths.items() if name != "paper_pdf"}
    paper_templates = inputs["paper_templates"]
    template_comparison = inputs["template_comparison"]
    catalog_input = inputs["catalog_input"]
    catalog_audit = inputs["catalog_audit"]
    independent_audit = inputs["independent_audit"]
    numbering = inputs["numbering_manifest"]
    bundle_audit = inputs["bundle_numbering_audit"]

    figure1 = paper_templates["figures"]["figure1"]["blocks_in_published_row_order"]
    figure6 = paper_templates["figures"]["figure6"]["blocks_in_published_row_order"]
    fixed_blocks = catalog_input["first_template"]["fixed_blocks"]
    files = catalog_input["first_template"]["files"]
    domains = catalog_input["first_template"]["choice_domains"]

    expected_domains = [
        [
            list(pair)
            for pair in itertools.combinations(
                sorted(set(range(12)) - set(file_block)), 2
            )
        ]
        for file_block in files
    ]
    entries = numbering["entries"]
    figure1_entries = entries[:67]
    figure6_entry = entries[67]

    checks = {
        "primary_pdf_hash_matches_template_extraction": (
            sha256_file(input_paths["paper_pdf"])
            == paper_templates["primary_source"]["pdf_sha256"]
        ),
        "all_published_text_anchors_present": False,
        "paper_template_comparison_pass": (
            template_comparison["overall_status"] == "PASS"
        ),
        "paper_figure1_fixed_blocks_equal_catalog_fixed_blocks": (
            normalized_block_set(figure1[:12])
            == normalized_block_set(fixed_blocks)
        ),
        "paper_figure1_files_equal_catalog_files_in_order": (
            figure1[12:] == files
        ),
        "catalog_choice_domains_are_all_two_subsets_of_each_file_complement": (
            domains == expected_domains
        ),
        "catalog_expected_completion_count_is_28_cubed": (
            catalog_input["first_template"]["expected_completion_count"]
            == 28**3
            == 21952
        ),
        "complete_catalog_audit_pass": catalog_audit["status"] == "PASS",
        "complete_catalog_checks_all_true": all(catalog_audit["checks"].values()),
        "complete_first_template_class_count_is_67": (
            catalog_audit["enumeration"]["discovered_first_template_class_count"]
            == 67
        ),
        "complete_first_template_rows_are_21952": (
            catalog_audit["enumeration"]["enumerated_completion_count"] == 21952
        ),
        "independent_isomorphism_audit_pass": (
            independent_audit["status"] == "PASS"
            and independent_audit["errors"] == []
        ),
        "numbering_manifest_pass_and_has_68_entries": (
            numbering["status"] == "PASS" and len(entries) == 68
        ),
        "classes_1_through_67_are_first_template": (
            [e["class_index"] for e in figure1_entries] == list(range(1, 68))
            and all(e["template"] == "first_template" for e in figure1_entries)
        ),
        "class_68_is_second_template": (
            figure6_entry["class_index"] == 68
            and figure6_entry["template"] == "second_template"
        ),
        "paper_figure6_equals_class_68_labeled_link": (
            normalized_block_set(figure6)
            == figure6_entry["normalized_labeled_link"]
        ),
        "figure6_is_distinct_from_all_67_first_template_classes": (
            catalog_audit["checks"][
                "fig6_nonisomorphic_to_every_first_template_class"
            ]
            and independent_audit["audited"]["pairwise_numbered_link_collisions"]
            == []
        ),
        "numbering_to_metadata_and_cnf_audit_pass": (
            bundle_audit["status"] == "PASS"
            and bundle_audit["summary"]["classes_checked"] == 68
            and bundle_audit["summary"]["classes_failed"] == 0
        ),
    }
    text_anchor_audit = check_text_anchors(input_paths["paper_pdf"])
    checks["all_published_text_anchors_present"] = text_anchor_audit["status"] == "PASS"

    class_map = []
    for entry in entries:
        index = entry["class_index"]
        family = (
            "published_Figure_1_completion"
            if index <= 67
            else "published_Figure_6"
        )
        class_map.append(
            {
                "project_class_index": index,
                "project_numbering_source": entry["numbering_source"],
                "canonical_labeled_link_sha256": entry[
                    "canonical_labeled_link_sha256"
                ],
                "published_family": family,
                "published_individual_class_identifier": None,
                "published_individual_numbering_status": (
                    "NOT_PRESENT_IN_PRIMARY_SOURCE"
                ),
                "full_completion_first_occurrence": entry.get(
                    "full_first_occurrence"
                ),
                "full_completion_multiplicity": entry.get(
                    "full_completion_multiplicity"
                ),
            }
        )

    individual_numbering_note = (
        "The primary paper identifies Figure 1 completions and the Figure 6 "
        "singleton but does not publish identifiers or a 1-through-67 list for "
        "the nonisomorphic Figure 1 completions. Project indices are therefore "
        "project-local, while their family membership and representatives are audited."
    )
    mapping = {
        "schema": "horizonmath.literature_to_project_class_map",
        "schema_version": SCHEMA_VERSION,
        "primary_source": {
            "title_as_printed": "Minimum (12, 6, 3) Covers",
            "author_publications_page_link_text": "C(12,6,3)=15",
            "journal": "Ars Combinatorica",
            "volume": 40,
            "year": 1995,
            "pages": "161-177",
            "author_hosted_url": "https://www.dmgordon.org/papers/c-12-6-3.pdf",
            "pdf_sha256": sha256_file(input_paths["paper_pdf"]),
        },
        "mapping_scope": {
            "published_family_map": "AUDITED",
            "project_numbering_1_through_68": "AUDITED_BY_PRIOR_PHASE",
            "published_individual_numbering_1_through_67": (
                "NOT_PRESENT_IN_PRIMARY_SOURCE"
            ),
            "note": individual_numbering_note,
        },
        "classes": class_map,
    }

    overall_pass = all(checks.values())
    provenance = {
        "schema": "horizonmath.classification_provenance_audit",
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            name: {
                "filename": path.name,
                "sha256": sha256_file(path),
            }
            for name, path in input_paths.items()
        },
        "primary_source_text_anchor_audit": text_anchor_audit,
        "derivation_map": [
            {
                "step": 1,
                "source_section": "Lemma 2.1",
                "role": "Figure 1 is the classified element-minimal covering family.",
            },
            {
                "step": 2,
                "source_section": "Lemma 5.7",
                "role": "No duplicate 777-triple implies a Figure 1 completion.",
            },
            {
                "step": 3,
                "source_section": "Lemma 5.8",
                "role": "A duplicate 777-triple implies a Figure 1 completion or Figure 6.",
            },
            {
                "step": 4,
                "source_section": "Theorem 5.9",
                "role": "The two cases are exhaustive and the two published families are disjoint.",
            },
            {
                "step": 5,
                "source_section": "Remarks after Theorem 5.9",
                "role": "The paper reports 67 Figure 1 isomorphism classes; the project independently recomputed this count over all 21,952 completions.",
            },
        ],
        "checks": checks,
        "conclusions": {
            "authoritative_classification_source": "AUDITED",
            "published_template_identity_to_recovered_source": "AUDITED",
            "published_two_template_exhaustiveness": (
                "AUDITED_AS_A_PRIMARY_LITERATURE_THEOREM"
            ),
            "first_template_67_class_computational_count": (
                "INDEPENDENTLY_RECOMPUTED_AND_AUDITED"
            ),
            "global_68_class_catalog_exhaustiveness": (
                "AUDITED_AGAINST_PUBLISHED_THEOREM"
                if overall_pass
                else "NOT_AUDITED"
            ),
            "formal_machine_verification_of_theorem_5_9": "NOT_PERFORMED",
            "published_individual_class_numbering": (
                "NOT_PRESENT_IN_PRIMARY_SOURCE"
            ),
            "another_link_class_profile_or_formula_analysis": "NOT_PERFORMED",
            "new_solver_or_certificate_runs": "NOT_PERFORMED",
            "claim_C_13_7_4_equals_30": "NOT_AUTHORIZED",
        },
        "overall_status": "PASS" if overall_pass else "FAIL",
    }

    output_dir = args.output_dir.resolve()
    write_json(output_dir / "classification-provenance.audit.json", provenance)
    write_json(output_dir / "literature-to-project-class-map.json", mapping)
    print(
        json.dumps(
            {
                "classification_provenance": str(
                    output_dir / "classification-provenance.audit.json"
                ),
                "class_map": str(
                    output_dir / "literature-to-project-class-map.json"
                ),
                "checks_passed": sum(checks.values()),
                "checks_total": len(checks),
                "overall_status": provenance["overall_status"],
            },
            sort_keys=True,
        )
    )
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
