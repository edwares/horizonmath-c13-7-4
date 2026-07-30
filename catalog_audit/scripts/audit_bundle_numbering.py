#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
from typing import Iterable


def normalize(link: Iterable[Iterable[int]]) -> tuple[tuple[int, ...], ...]:
    return tuple(sorted(tuple(sorted(int(x) for x in block)) for block in link))


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def pretty_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def parse_cnf(path: Path) -> tuple[int, list[list[int]]]:
    variables = None
    expected_clauses = None
    clauses: list[list[int]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not raw or raw.startswith("c"):
            continue
        if raw.startswith("p "):
            fields = raw.split()
            if len(fields) != 4 or fields[:2] != ["p", "cnf"]:
                raise ValueError(f"{path}:{line_number}: malformed header")
            variables = int(fields[2])
            expected_clauses = int(fields[3])
            continue
        values = [int(field) for field in raw.split()]
        if not values or values[-1] != 0:
            raise ValueError(f"{path}:{line_number}: clause lacks final zero")
        clauses.append(values[:-1])
    if variables is None or expected_clauses is None:
        raise ValueError(f"{path}: missing header")
    if len(clauses) != expected_clauses:
        raise ValueError(
            f"{path}: header says {expected_clauses}, parsed {len(clauses)}"
        )
    return variables, clauses


def verify_internal_sha256s(bundle: Path) -> tuple[int, list[dict[str, str]]]:
    sidecar = bundle / "SHA256SUMS"
    mismatches: list[dict[str, str]] = []
    checked = 0
    for line_number, raw in enumerate(sidecar.read_text(encoding="utf-8").splitlines(), 1):
        if not raw:
            continue
        expected, relative = raw.split(maxsplit=1)
        relative = relative.removeprefix("*")
        path = bundle / relative
        actual = digest(path) if path.is_file() else None
        checked += 1
        if actual != expected:
            mismatches.append(
                {
                    "line": str(line_number),
                    "path": relative,
                    "expected": expected,
                    "actual": actual or "MISSING",
                }
            )
    return checked, mismatches


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--numbering-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    bundle = args.bundle_root.resolve()
    numbering_path = args.numbering_manifest.resolve()
    numbering = json.loads(numbering_path.read_text(encoding="utf-8"))
    entries = numbering["entries"]
    errors: list[dict[str, object]] = []
    checked_sha_rows, sha_mismatches = verify_internal_sha256s(bundle)
    if sha_mismatches:
        errors.append({"code": "INTERNAL_SHA256_MISMATCH", "rows": sha_mismatches})

    manifest_rows: dict[str, dict[str, str]] = {}
    with (bundle / "metadata" / "manifest.tsv").open(
        encoding="utf-8", newline=""
    ) as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            manifest_rows[row["file"]] = row

    sevens = list(combinations(range(12), 7))
    all_fours = set(combinations(range(12), 4))
    class_rows: list[dict[str, object]] = []
    for class_index in range(1, 69):
        entry = entries[class_index - 1]
        metadata_path = bundle / "metadata" / f"class_{class_index:02d}.json"
        cnf_path = bundle / "cnf" / f"class_{class_index:02d}.cnf"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        numbered_link = normalize(entry["normalized_labeled_link"])
        metadata_link = normalize(metadata["link"])
        link_equal = numbered_link == metadata_link

        covered_fours = {
            four for block in metadata_link for four in combinations(block, 4)
        }
        residual = sorted(all_fours - covered_fours)
        residual_equal = residual == [
            tuple(four) for four in metadata["residual"]
        ]
        variables, clauses = parse_cnf(cnf_path)
        coverage_clause_mismatches = 0
        for four, clause in zip(residual, clauses[: len(residual)]):
            expected_clause = [
                index + 1
                for index, seven in enumerate(sevens)
                if set(four) <= set(seven)
            ]
            if clause != expected_clause:
                coverage_clause_mismatches += 1

        manifest_row = manifest_rows.get(cnf_path.name)
        manifest_equal = bool(
            manifest_row
            and int(manifest_row["residual_quadruples"]) == len(residual)
            and int(manifest_row["variables"]) == variables
            and int(manifest_row["clauses"]) == len(clauses)
            and int(manifest_row["bytes"]) == cnf_path.stat().st_size
        )
        row_errors = []
        if metadata["class"] != class_index:
            row_errors.append("metadata class index")
        if entry["class_index"] != class_index:
            row_errors.append("numbering class index")
        if not link_equal:
            row_errors.append("metadata/numbering link")
        if not residual_equal:
            row_errors.append("metadata residual")
        if len(residual) != entry["statistics"]["residual_four_set_count"]:
            row_errors.append("numbering residual count")
        if variables != metadata["variables"] or len(clauses) != metadata["clauses"]:
            row_errors.append("CNF header/metadata dimensions")
        if coverage_clause_mismatches:
            row_errors.append("CNF residual coverage clauses")
        if not manifest_equal:
            row_errors.append("manifest.tsv row")
        if row_errors:
            errors.append(
                {
                    "code": "CLASS_NUMBERING_MISMATCH",
                    "class_index": class_index,
                    "fields": row_errors,
                }
            )

        class_rows.append(
            {
                "class_index": class_index,
                "numbering_source": entry["numbering_source"],
                "metadata_path": f"metadata/{metadata_path.name}",
                "metadata_sha256": digest(metadata_path),
                "cnf_path": f"cnf/{cnf_path.name}",
                "cnf_sha256": digest(cnf_path),
                "canonical_labeled_link_sha256": entry[
                    "canonical_labeled_link_sha256"
                ],
                "metadata_link_equals_numbered_link": link_equal,
                "residual_four_set_count": len(residual),
                "metadata_residual_exact": residual_equal,
                "cnf_variables": variables,
                "cnf_clauses": len(clauses),
                "residual_coverage_clauses_checked": len(residual),
                "residual_coverage_clause_mismatches": coverage_clause_mismatches,
                "manifest_tsv_row_exact": manifest_equal,
                "status": "PASS" if not row_errors else "FAIL",
            }
        )

    missing_manifest_rows = sorted(
        set(manifest_rows) - {f"class_{index:02d}.cnf" for index in range(1, 69)}
    )
    if missing_manifest_rows:
        errors.append(
            {
                "code": "UNEXPECTED_MANIFEST_ROWS",
                "rows": missing_manifest_rows,
            }
        )

    audit = {
        "schema_version": "horizonmath.bundle-numbering-audit.v1",
        "status": "PASS" if not errors else "FAIL",
        "inputs": {
            "bundle_name": bundle.name,
            "bundle_archive_sha256": (
                "06ae94d3fd8a7e7f91d8022bd8f0a05a87775ef65eca1bd8cb6460c3cbca18e1"
            ),
            "numbering_manifest_sha256": digest(numbering_path),
        },
        "internal_integrity": {
            "sha256_entries_checked": checked_sha_rows,
            "sha256_mismatch_count": len(sha_mismatches),
        },
        "summary": {
            "classes_checked": len(class_rows),
            "classes_passed": sum(row["status"] == "PASS" for row in class_rows),
            "classes_failed": sum(row["status"] != "PASS" for row in class_rows),
            "cnf_residual_coverage_clauses_checked": sum(
                row["residual_coverage_clauses_checked"] for row in class_rows
            ),
        },
        "classes": class_rows,
        "claim_boundary": {
            "numbering_to_metadata_and_cnf_consistency": not errors,
            "cnf_unsatisfiability_checked": False,
            "another_link_class_analyzed": False,
            "two_template_exhaustiveness_proved": False,
        },
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(pretty_bytes(audit))
    print(
        json.dumps(
            {
                "status": audit["status"],
                "output": str(args.output.resolve()),
                "sha256": digest(args.output),
                "classes_checked": len(class_rows),
                "internal_sha256_entries_checked": checked_sha_rows,
                "errors": len(errors),
            },
            sort_keys=True,
        )
    )
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

