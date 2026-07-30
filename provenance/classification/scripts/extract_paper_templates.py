#!/usr/bin/env python3
"""Extract Figures 1 and 6 from the primary paper and audit source constants.

The extraction is geometric: it reads the incidence-matrix column headers,
row labels, and bullet glyphs from fixed PDF pages, then assigns every bullet
to its nearest row and column.  It does not contain a transcription of either
published template.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import pdfplumber


FORMAT_VERSION = "1"
COLUMN_LABELS = tuple(str(i) for i in range(10)) + ("T", "E")
COLUMN_VALUES = {label: i for i, label in enumerate(COLUMN_LABELS)}
FIGURES = {
    "figure1": {"page_index": 2, "caption_tokens": ("Figure", "1:")},
    "figure6": {"page_index": 12, "caption_tokens": ("Figure", "6:")},
}
EXTRACTION_BOUNDS = {
    "header_top_min": 130.0,
    "header_top_max": 145.0,
    "row_top_min": 145.0,
    "row_top_max": 325.0,
    "row_label_x1_max": 210.0,
    "matrix_x0_min": 210.0,
    "row_assignment_tolerance": 1.0,
    "column_assignment_tolerance": 4.0,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def write_canonical_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def word_record(word: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": word["text"],
        "x0": round(float(word["x0"]), 6),
        "x1": round(float(word["x1"]), 6),
        "top": round(float(word["top"]), 6),
        "bottom": round(float(word["bottom"]), 6),
        "center_x": round((float(word["x0"]) + float(word["x1"])) / 2.0, 6),
    }


def exactly_one(items: list[dict[str, Any]], description: str) -> dict[str, Any]:
    if len(items) != 1:
        raise ValueError(f"expected exactly one {description}; found {len(items)}")
    return items[0]


def extract_figure(page: Any, figure_name: str) -> dict[str, Any]:
    words = page.extract_words(
        x_tolerance=1,
        y_tolerance=1,
        keep_blank_chars=False,
    )
    bounds = EXTRACTION_BOUNDS

    headers: list[dict[str, Any]] = []
    for label in COLUMN_LABELS:
        matches = [
            w
            for w in words
            if w["text"] == label
            and bounds["header_top_min"] <= float(w["top"]) <= bounds["header_top_max"]
            and float(w["x0"]) >= bounds["matrix_x0_min"]
        ]
        headers.append(word_record(exactly_one(matches, f"column header {label!r}")))

    header_centers = {
        COLUMN_VALUES[h["text"]]: float(h["center_x"]) for h in headers
    }
    if sorted(header_centers) != list(range(12)):
        raise ValueError("column headers do not define the universe 0..11")
    if list(header_centers.values()) != sorted(header_centers.values()):
        raise ValueError("column headers are not ordered left-to-right")

    row_labels: list[dict[str, Any]] = []
    for row_number in range(1, 16):
        label = str(row_number)
        matches = [
            w
            for w in words
            if w["text"] == label
            and bounds["row_top_min"] <= float(w["top"]) <= bounds["row_top_max"]
            and float(w["x1"]) <= bounds["row_label_x1_max"]
        ]
        record = word_record(exactly_one(matches, f"row label {label!r}"))
        record["row_number"] = row_number
        row_labels.append(record)

    row_tops = {r["row_number"]: float(r["top"]) for r in row_labels}
    if list(row_tops.values()) != sorted(row_tops.values()):
        raise ValueError("row labels are not ordered top-to-bottom")

    bullet_words = [
        word_record(w)
        for w in words
        if w["text"] == "•"
        and bounds["row_top_min"] <= float(w["top"]) <= bounds["row_top_max"] + 5.0
        and float(w["x0"]) >= bounds["matrix_x0_min"]
    ]
    assignments: list[dict[str, Any]] = []
    cells: dict[int, list[int]] = {row: [] for row in range(1, 16)}
    occupied: set[tuple[int, int]] = set()
    for bullet in bullet_words:
        row = min(row_tops, key=lambda i: abs(float(bullet["top"]) - row_tops[i]))
        row_error = abs(float(bullet["top"]) - row_tops[row])
        column = min(
            header_centers,
            key=lambda i: abs(float(bullet["center_x"]) - header_centers[i]),
        )
        column_error = abs(float(bullet["center_x"]) - header_centers[column])
        if row_error > bounds["row_assignment_tolerance"]:
            raise ValueError(
                f"{figure_name}: bullet at top={bullet['top']} is not near a row"
            )
        if column_error > bounds["column_assignment_tolerance"]:
            raise ValueError(
                f"{figure_name}: bullet at x={bullet['center_x']} is not near a column"
            )
        if (row, column) in occupied:
            raise ValueError(f"{figure_name}: duplicate bullet in cell {(row, column)}")
        occupied.add((row, column))
        cells[row].append(column)
        assignments.append(
            {
                "row_number": row,
                "column_value": column,
                "row_error": round(row_error, 6),
                "column_error": round(column_error, 6),
                "glyph": bullet,
            }
        )

    blocks = [sorted(cells[row]) for row in range(1, 16)]
    caption_tokens = FIGURES[figure_name]["caption_tokens"]
    caption_matches = [
        exactly_one(
            [
                w
                for w in words
                if w["text"] == token and 330.0 <= float(w["top"]) <= 355.0
            ],
            f"caption token {token!r}",
        )
        for token in caption_tokens
    ]

    return {
        "pdf_page_number": FIGURES[figure_name]["page_index"] + 1,
        "expected_caption_prefix": " ".join(caption_tokens),
        "caption_tokens": [word_record(w) for w in caption_matches],
        "column_headers": headers,
        "row_labels": row_labels,
        "bullet_count": len(bullet_words),
        "bullet_assignments": sorted(
            assignments, key=lambda a: (a["row_number"], a["column_value"])
        ),
        "blocks_in_published_row_order": blocks,
        "block_sizes": [len(block) for block in blocks],
        "blocks_canonical_sha256": sha256_bytes(canonical_json_bytes(blocks)),
    }


def literal_assignments(source_path: Path, names: set[str]) -> dict[str, Any]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    found: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        if isinstance(node, ast.Assign):
            targets = node.targets
            value_node = node.value
        else:
            targets = [node.target]
            value_node = node.value
        for target in targets:
            if isinstance(target, ast.Name) and target.id in names:
                found[target.id] = ast.literal_eval(value_node)
    missing = names - found.keys()
    if missing:
        raise ValueError(f"missing literal assignments in source: {sorted(missing)}")
    return found


def normalized_blocks(value: Any) -> list[list[int]]:
    return [[int(x) for x in block] for block in value]


def comparison_record(
    comparison_id: str,
    paper_blocks: list[list[int]],
    source_blocks: list[list[int]],
) -> dict[str, Any]:
    row_results = []
    max_rows = max(len(paper_blocks), len(source_blocks))
    for i in range(max_rows):
        paper_row = paper_blocks[i] if i < len(paper_blocks) else None
        source_row = source_blocks[i] if i < len(source_blocks) else None
        row_results.append(
            {
                "row_number": i + 1,
                "paper": paper_row,
                "source": source_row,
                "exact_ordered_match": paper_row == source_row,
            }
        )
    exact = paper_blocks == source_blocks
    return {
        "comparison_id": comparison_id,
        "criterion": "same row count and exact element sequence in every row",
        "paper_blocks": paper_blocks,
        "source_blocks": source_blocks,
        "paper_canonical_sha256": sha256_bytes(canonical_json_bytes(paper_blocks)),
        "source_canonical_sha256": sha256_bytes(canonical_json_bytes(source_blocks)),
        "row_results": row_results,
        "exact_ordered_match": exact,
        "status": "PASS" if exact else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    pdf_path = args.pdf.resolve()
    source_path = args.source.resolve()
    output_dir = args.output_dir.resolve()

    with pdfplumber.open(pdf_path) as pdf:
        extracted = {
            name: extract_figure(pdf.pages[meta["page_index"]], name)
            for name, meta in FIGURES.items()
        }

    template_manifest = {
        "schema": "horizonmath.paper_templates",
        "schema_version": FORMAT_VERSION,
        "extraction_method": {
            "description": (
                "Geometric extraction of column headers, row labels, and bullet "
                "glyphs from the incidence matrices; no block transcription is "
                "embedded in this program."
            ),
            "library": "pdfplumber",
            "bounds": EXTRACTION_BOUNDS,
            "column_label_map": COLUMN_VALUES,
        },
        "primary_source": {
            "title_as_printed": "Minimum (12, 6, 3) Covers",
            "authors": [
                "Daniel M. Gordon",
                "Oren Patashnik",
                "John Petro",
                "Herbert Taylor",
            ],
            "author_hosted_url": "https://www.dmgordon.org/papers/c-12-6-3.pdf",
            "pdf_filename": pdf_path.name,
            "pdf_size_bytes": pdf_path.stat().st_size,
            "pdf_sha256": sha256_file(pdf_path),
        },
        "figures": extracted,
    }

    source_literals = literal_assignments(
        source_path, {"FIG1_FULL", "FILES", "FIG6"}
    )
    figure1_blocks = extracted["figure1"]["blocks_in_published_row_order"]
    figure6_blocks = extracted["figure6"]["blocks_in_published_row_order"]
    comparisons = [
        comparison_record(
            "paper_figure1_rows_1_12_vs_source_FIG1_FULL",
            figure1_blocks[:12],
            normalized_blocks(source_literals["FIG1_FULL"]),
        ),
        comparison_record(
            "paper_figure1_rows_13_15_vs_source_FILES",
            figure1_blocks[12:],
            normalized_blocks(source_literals["FILES"]),
        ),
        comparison_record(
            "paper_figure6_rows_1_15_vs_source_FIG6",
            figure6_blocks,
            normalized_blocks(source_literals["FIG6"]),
        ),
    ]
    overall_pass = all(c["exact_ordered_match"] for c in comparisons)
    audit = {
        "schema": "horizonmath.paper_template_comparison_audit",
        "schema_version": FORMAT_VERSION,
        "criterion": (
            "All three comparisons must match exactly, row-for-row and "
            "element-for-element, in published/source order."
        ),
        "inputs": {
            "paper_pdf": {
                "filename": pdf_path.name,
                "sha256": sha256_file(pdf_path),
            },
            "recovered_source": {
                "filename": source_path.name,
                "sha256": sha256_file(source_path),
            },
        },
        "comparisons": comparisons,
        "overall_status": "PASS" if overall_pass else "FAIL",
    }

    write_canonical_json(output_dir / "paper.templates.json", template_manifest)
    write_canonical_json(
        output_dir / "paper-template-comparison.audit.json", audit
    )
    print(
        json.dumps(
            {
                "paper_templates": str(output_dir / "paper.templates.json"),
                "comparison_audit": str(
                    output_dir / "paper-template-comparison.audit.json"
                ),
                "overall_status": audit["overall_status"],
                "figure1_block_sizes": extracted["figure1"]["block_sizes"],
                "figure6_block_sizes": extracted["figure6"]["block_sizes"],
            },
            sort_keys=True,
        )
    )
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
