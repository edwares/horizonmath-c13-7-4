#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path


FILES = (
    "catalog.audit.manifest.json",
    "completion-ledger.jsonl",
    "numbering.manifest.json",
)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def pretty_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    left = args.left.resolve()
    right = args.right.resolve()
    rows = []
    for relative in FILES:
        left_path = left / relative
        right_path = right / relative
        left_hash = digest(left_path)
        right_hash = digest(right_path)
        rows.append(
            {
                "path": relative,
                "left_sha256": left_hash,
                "right_sha256": right_hash,
                "byte_identical": left_path.read_bytes() == right_path.read_bytes(),
            }
        )
    audit = {
        "schema_version": "horizonmath.link-catalog-determinism-audit.v1",
        "status": "PASS" if all(row["byte_identical"] for row in rows) else "FAIL",
        "invocations": [
            {
                "command": (
                    "PYTHONPATH=src python3 scripts/run_catalog_audit.py "
                    "--input data/catalog-input.json --output-dir build/run2"
                ),
                "output_directory_label": "run2",
            },
            {
                "command": (
                    "PYTHONPATH=src python3 scripts/run_catalog_audit.py "
                    "--input data/catalog-input.json --output-dir build/run3"
                ),
                "output_directory_label": "run3",
            },
        ],
        "files": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(pretty_bytes(audit))
    print(
        json.dumps(
            {
                "status": audit["status"],
                "files_compared": len(rows),
                "output": str(args.output.resolve()),
                "sha256": digest(args.output),
            },
            sort_keys=True,
        )
    )
    if audit["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

