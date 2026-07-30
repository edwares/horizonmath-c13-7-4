#!/usr/bin/env python3
"""Build or verify the deterministic source-tree integrity manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "horizonmath.source-tree-manifest.v1"
DEFAULT_OUTPUT = "SOURCE_MANIFEST.json"
EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
}
EXCLUDED_DIRECTORY_SUFFIXES = {".egg-info"}
EXCLUDED_ROOT_DIRECTORIES = {"build"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path, output: Path) -> dict[str, Any]:
    output_relative = output.relative_to(root)
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative == output_relative:
            continue
        if relative.parts[0] in EXCLUDED_ROOT_DIRECTORIES:
            continue
        if any(
            part in EXCLUDED_DIRECTORY_NAMES
            or any(
                part.endswith(suffix)
                for suffix in EXCLUDED_DIRECTORY_SUFFIXES
            )
            for part in relative.parts
        ):
            continue
        files.append(
            {
                "path": relative.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "AUDITED_CHECKPOINT",
        "root": ".",
        "manifest_path": output_relative.as_posix(),
        "manifest_self_included": False,
        "excluded_directory_names": sorted(EXCLUDED_DIRECTORY_NAMES),
        "excluded_directory_suffixes": sorted(
            EXCLUDED_DIRECTORY_SUFFIXES
        ),
        "excluded_root_directories": sorted(EXCLUDED_ROOT_DIRECTORIES),
        "summary": {
            "file_count": len(files),
            "total_bytes": sum(record["bytes"] for record in files),
        },
        "files": files,
    }


def serialize(manifest: dict[str, Any]) -> str:
    return json.dumps(
        manifest,
        indent=2,
        sort_keys=True,
        ensure_ascii=True,
    ) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else root / DEFAULT_OUTPUT
    )
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise SystemExit("output must be inside the source root") from exc

    rendered = serialize(build_manifest(root, output))
    if args.check:
        if not output.is_file():
            raise SystemExit(f"missing source manifest: {output}")
        if output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(
                "SOURCE_MANIFEST.json is stale; regenerate it with "
                "scripts/build_source_manifest.py"
            )
        return 0

    output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
