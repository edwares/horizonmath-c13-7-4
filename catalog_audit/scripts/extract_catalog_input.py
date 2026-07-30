#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from hashlib import sha256
from itertools import combinations
import json
from math import prod
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from catalog_audit.core import canonical_json_bytes, link_sha256, normalize_link


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def literal_assignments(path: Path, names: set[str]) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id in names:
            found[target.id] = ast.literal_eval(node.value)
    missing = names - set(found)
    if missing:
        raise ValueError(f"missing literal assignments: {sorted(missing)}")
    return found


def find_early_stop(path: Path) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matches: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        compare = node.test
        if not (
            isinstance(compare, ast.Compare)
            and isinstance(compare.left, ast.Call)
            and isinstance(compare.left.func, ast.Name)
            and compare.left.func.id == "len"
            and len(compare.left.args) == 1
            and isinstance(compare.left.args[0], ast.Name)
            and compare.left.args[0].id == "reps"
            and len(compare.ops) == 1
            and isinstance(compare.ops[0], ast.Eq)
            and len(compare.comparators) == 1
            and isinstance(compare.comparators[0], ast.Constant)
        ):
            continue
        has_break = any(isinstance(descendant, ast.Break) for descendant in node.body)
        matches.append(
            {
                "line": node.lineno,
                "comparison": f"len(reps) == {compare.comparators[0].value}",
                "body_contains_break": has_break,
            }
        )
    return {
        "detected": bool(matches),
        "matches": matches,
    }


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return sorted(modules)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    bundle = args.bundle_root.resolve()
    classify_path = bundle / "source" / "classify_links.py"
    extension_path = bundle / "source" / "link_extension.py"
    catalog_path = bundle / "metadata" / "link_classes.json"
    readme_path = bundle / "README.md"
    manifest_path = bundle / "SHA256SUMS"
    for path in (
        classify_path,
        extension_path,
        catalog_path,
        readme_path,
        manifest_path,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    constants = literal_assignments(
        extension_path, {"FIG1_FULL", "FILES", "FIG6"}
    )
    historical = json.loads(catalog_path.read_text(encoding="utf-8"))
    fixed_blocks = normalize_link(constants["FIG1_FULL"])
    files = tuple(tuple(int(point) for point in file) for file in constants["FILES"])
    fig6 = normalize_link(constants["FIG6"])
    point_count = 12
    choice_domains = [
        [
            list(pair)
            for pair in combinations(
                [point for point in range(point_count) if point not in file], 2
            )
        ]
        for file in files
    ]

    source_files = {}
    for relative in (
        "SHA256SUMS",
        "README.md",
        "source/classify_links.py",
        "source/link_extension.py",
        "metadata/link_classes.json",
        "metadata/manifest.tsv",
        "scripts/validate_bundle.py",
    ):
        path = bundle / relative
        source_files[relative] = {
            "bytes": path.stat().st_size,
            "sha256": digest(path),
        }

    historical_representatives = [
        [list(block) for block in normalize_link(link)]
        for link in historical["representatives"]
    ]
    spec = {
        "schema_version": "horizonmath.link-catalog-input.v1",
        "parameters": {
            "point_count": point_count,
            "block_size": 6,
            "link_block_count": 15,
            "cover_strength": 3,
        },
        "first_template": {
            "name_in_recovered_source": "FIG1_FULL plus one completion block per FILE",
            "fixed_blocks": [list(block) for block in fixed_blocks],
            "files": [list(file) for file in files],
            "choice_rule": (
                "For each file, choose every 2-subset of its point-complement; "
                "append the sorted union of that file and the chosen pair."
            ),
            "choice_domains": choice_domains,
            "expected_completion_count": (
                prod(len(domain) for domain in choice_domains)
            ),
        },
        "second_template": {
            "name_in_recovered_source": "FIG6",
            "representatives": [[list(block) for block in fig6]],
        },
        "historical_catalog": {
            "archived_num_completions": int(historical["num_completions"]),
            "archived_num_classes_fig1": int(historical["num_classes_fig1"]),
            "archived_prefix_counts": [int(value) for value in historical["counts"]],
            "archived_examples": historical["examples"],
            "archived_representatives": historical_representatives,
            "archived_representative_labeled_hashes": [
                link_sha256(link, point_count=point_count)
                for link in historical_representatives
            ],
            "archived_fig6_labeled_hash": link_sha256(
                fig6, point_count=point_count
            ),
            "archived_fig6_isomorphic_to_fig1": bool(
                historical["fig6_isomorphic_to_fig1"]
            ),
            "archived_elapsed_is_nondeterministic_and_excluded": True,
        },
        "source_provenance": {
            "archive_name": "HorizonMath_C13_7_4_sat_bundle.zip",
            "archive_sha256": (
                "06ae94d3fd8a7e7f91d8022bd8f0a05a87775ef65eca1bd8cb6460c3cbca18e1"
            ),
            "internal_sha256sum_entries_verified": 148,
            "files": source_files,
            "ast_extraction": {
                "source": "source/link_extension.py",
                "literal_assignments": ["FIG1_FULL", "FILES", "FIG6"],
                "executed_recovered_source": False,
            },
            "archived_classifier_early_stop": find_early_stop(classify_path),
            "archived_imports": {
                "source/classify_links.py": imported_modules(classify_path),
                "source/link_extension.py": imported_modules(extension_path),
            },
            "dependency_lock_present": False,
            "networkx_version_recorded": False,
        },
        "claim_boundary": {
            "audit_scope": (
                "Complete classification of every completion defined by the "
                "recovered first template, plus exact comparison of the separate "
                "recovered FIG6 representative."
            ),
            "template_exhaustiveness_proved_by_this_input": False,
            "authoritative_classification_citation_present": False,
            "literature_to_numbering_map_present": False,
            "global_68_class_exhaustiveness_claim_authorized": False,
            "missing_evidence": [
                "A proof or authoritative source that the recovered two templates exhaust all minimum C(12,6,3) covers.",
                "An independently audited literature-to-project 1-through-68 numbering map.",
                "The original NetworkX version or a dependency lock for the archived classifier.",
            ],
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_json_bytes(spec))
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "sha256": digest(args.output),
                "expected_completions": spec["first_template"][
                    "expected_completion_count"
                ],
                "archived_prefix_completions": historical["num_completions"],
                "historical_first_template_classes": len(
                    historical_representatives
                ),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
