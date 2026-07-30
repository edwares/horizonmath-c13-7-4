"""Canonical JSON and link hashing helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def compact_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def canonical_blocks(blocks: Iterable[Iterable[int]]) -> tuple[tuple[int, ...], ...]:
    return tuple(sorted(tuple(sorted(block)) for block in blocks))


def canonical_labeled_link_payload(
    point_labels: Iterable[int], blocks: Iterable[Iterable[int]]
) -> dict[str, Any]:
    return {
        "blocks": [list(block) for block in canonical_blocks(blocks)],
        "points": sorted(point_labels),
    }


def canonical_labeled_link_sha256(
    point_labels: Iterable[int], blocks: Iterable[Iterable[int]]
) -> str:
    return sha256_bytes(
        compact_json_bytes(canonical_labeled_link_payload(point_labels, blocks))
    )


def canonical_document_sha256(document: dict[str, Any]) -> str:
    return sha256_bytes(compact_json_bytes(document))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(pretty_json_bytes(value))
    temporary.replace(path)


def write_sha256_sidecar(path: Path) -> Path:
    sidecar = path.with_name(path.name + ".sha256")
    sidecar.write_text(f"{sha256_file(path)}  {path.name}\n", encoding="utf-8")
    return sidecar
