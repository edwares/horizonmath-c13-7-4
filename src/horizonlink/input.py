"""Strict parsing and canonicalization for horizonmath.link-input.v1."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from horizonlink.canonical import (
    canonical_blocks,
    canonical_document_sha256,
    canonical_labeled_link_sha256,
    pretty_json_bytes,
    sha256_bytes,
)


SCHEMA_VERSION = "horizonmath.link-input.v1"
POINTS = tuple(range(12))
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
NUMBERING_STATUSES = {"AUDITED", "PARTIAL", "UNAVAILABLE"}


class InputFormatError(ValueError):
    def __init__(self, errors: list[dict[str, str]]):
        super().__init__("invalid link input")
        self.errors = errors


class DuplicateKeyError(ValueError):
    pass


@dataclass(frozen=True)
class LinkDocument:
    raw_sha256: str
    raw_bytes: bytes
    canonical_document: dict[str, Any]
    canonical_document_sha256: str
    canonical_labeled_link_sha256: str
    point_labels: tuple[int, ...]
    blocks: tuple[tuple[int, ...], ...]
    class_index: int | None
    representative_id: str
    numbering_source: dict[str, Any]
    provenance: dict[str, Any]
    content_was_canonical: bool
    bytes_were_canonical_serialization: bool


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _error(errors: list[dict[str, str]], path: str, code: str, message: str) -> None:
    errors.append({"path": path, "code": code, "message": message})


def _check_keys(
    value: Any,
    path: str,
    required: set[str],
    optional: set[str],
    errors: list[dict[str, str]],
) -> bool:
    if not isinstance(value, dict):
        _error(errors, path, "TYPE", "must be an object")
        return False
    keys = set(value)
    for key in sorted(required - keys):
        _error(errors, f"{path}.{key}", "MISSING", "required property is missing")
    for key in sorted(keys - required - optional):
        _error(errors, f"{path}.{key}", "UNKNOWN", "unknown property")
    return required <= keys


def _is_int(value: Any) -> bool:
    return type(value) is int


def _validate_sha256(
    value: Any, path: str, errors: list[dict[str, str]], *, nullable: bool = False
) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        _error(errors, path, "SHA256", "must be 64 lowercase hexadecimal digits")


def _canonical_numbering_source(
    value: Any, errors: list[dict[str, str]]
) -> dict[str, Any]:
    required = {"status", "citation", "selection"}
    optional = {"artifact_sha256", "notes"}
    if not _check_keys(value, "$.identity.numbering_source", required, optional, errors):
        return {}
    result: dict[str, Any] = {}
    status = value.get("status")
    if status not in NUMBERING_STATUSES:
        _error(
            errors,
            "$.identity.numbering_source.status",
            "ENUM",
            f"must be one of {sorted(NUMBERING_STATUSES)}",
        )
    else:
        result["status"] = status
    for key in ("citation", "selection"):
        item = value.get(key)
        if not isinstance(item, str) or not item:
            _error(
                errors,
                f"$.identity.numbering_source.{key}",
                "STRING",
                "must be a nonempty string",
            )
        else:
            result[key] = item
    if "artifact_sha256" in value:
        _validate_sha256(
            value["artifact_sha256"],
            "$.identity.numbering_source.artifact_sha256",
            errors,
            nullable=True,
        )
        result["artifact_sha256"] = value["artifact_sha256"]
    if "notes" in value:
        if not isinstance(value["notes"], str):
            _error(
                errors,
                "$.identity.numbering_source.notes",
                "STRING",
                "must be a string",
            )
        else:
            result["notes"] = value["notes"]
    return result


def _canonical_identity(
    value: Any, errors: list[dict[str, str]]
) -> tuple[dict[str, Any], int | None, str, dict[str, Any]]:
    required = {"representative_id", "class_index", "numbering_source"}
    if not _check_keys(value, "$.identity", required, set(), errors):
        return {}, None, "", {}
    representative_id = value.get("representative_id")
    if not isinstance(representative_id, str) or not representative_id:
        _error(
            errors,
            "$.identity.representative_id",
            "STRING",
            "must be a nonempty string",
        )
        representative_id = ""
    class_index = value.get("class_index")
    if class_index is not None and (
        not _is_int(class_index) or not 1 <= class_index <= 68
    ):
        _error(
            errors,
            "$.identity.class_index",
            "RANGE",
            "must be null or an integer from 1 through 68",
        )
        class_index = None
    numbering_source = _canonical_numbering_source(
        value.get("numbering_source"), errors
    )
    return (
        {
            "class_index": class_index,
            "numbering_source": numbering_source,
            "representative_id": representative_id,
        },
        class_index,
        representative_id,
        numbering_source,
    )


def _canonical_provenance(
    value: Any, errors: list[dict[str, str]]
) -> dict[str, Any]:
    required = {"source_artifacts", "extraction_rule"}
    optional = {"notes"}
    if not _check_keys(value, "$.provenance", required, optional, errors):
        return {}
    source_artifacts = value.get("source_artifacts")
    canonical_sources = []
    if not isinstance(source_artifacts, list) or not source_artifacts:
        _error(
            errors,
            "$.provenance.source_artifacts",
            "ARRAY",
            "must be a nonempty array",
        )
    else:
        for index, source in enumerate(source_artifacts):
            path = f"$.provenance.source_artifacts[{index}]"
            if not _check_keys(source, path, {"name", "sha256"}, {"uri"}, errors):
                continue
            name = source.get("name")
            if not isinstance(name, str) or not name:
                _error(errors, f"{path}.name", "STRING", "must be a nonempty string")
                name = ""
            _validate_sha256(source.get("sha256"), f"{path}.sha256", errors)
            uri = source.get("uri") if "uri" in source else None
            if uri is not None and not isinstance(uri, str):
                _error(errors, f"{path}.uri", "STRING", "must be a string or null")
                uri = None
            canonical_source = {"name": name, "sha256": source.get("sha256")}
            if "uri" in source:
                canonical_source["uri"] = uri
            canonical_sources.append(canonical_source)
    extraction_rule = value.get("extraction_rule")
    if not isinstance(extraction_rule, str) or not extraction_rule:
        _error(
            errors,
            "$.provenance.extraction_rule",
            "STRING",
            "must be a nonempty string",
        )
        extraction_rule = ""
    result: dict[str, Any] = {
        "extraction_rule": extraction_rule,
        "source_artifacts": sorted(
            canonical_sources,
            key=lambda item: (
                item.get("name", ""),
                item.get("sha256", ""),
                item.get("uri") or "",
            ),
        ),
    }
    if "notes" in value:
        if not isinstance(value["notes"], str):
            _error(errors, "$.provenance.notes", "STRING", "must be a string")
        else:
            result["notes"] = value["notes"]
    return result


def parse_link_bytes(raw: bytes) -> LinkDocument:
    raw_sha256 = sha256_bytes(raw)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputFormatError(
            [
                {
                    "path": "$",
                    "code": "UTF8",
                    "message": f"input is not valid UTF-8: {exc}",
                }
            ]
        ) from exc
    try:
        document = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, DuplicateKeyError) as exc:
        raise InputFormatError(
            [{"path": "$", "code": "JSON", "message": str(exc)}]
        ) from exc

    errors: list[dict[str, str]] = []
    required = {
        "schema_version",
        "parameters",
        "point_labels",
        "blocks",
        "identity",
        "provenance",
    }
    if not _check_keys(document, "$", required, set(), errors):
        raise InputFormatError(errors)

    if document.get("schema_version") != SCHEMA_VERSION:
        _error(
            errors,
            "$.schema_version",
            "SCHEMA_VERSION",
            f"must equal {SCHEMA_VERSION!r}",
        )

    parameters = document.get("parameters")
    if _check_keys(
        parameters,
        "$.parameters",
        {"v", "k", "t", "block_count"},
        set(),
        errors,
    ):
        expected = {"v": 12, "k": 6, "t": 3, "block_count": 15}
        for key, expected_value in expected.items():
            if parameters.get(key) != expected_value or not _is_int(
                parameters.get(key)
            ):
                _error(
                    errors,
                    f"$.parameters.{key}",
                    "PARAMETER",
                    f"must equal integer {expected_value}",
                )

    raw_points = document.get("point_labels")
    point_labels: tuple[int, ...] = ()
    if not isinstance(raw_points, list):
        _error(errors, "$.point_labels", "TYPE", "must be an array")
    elif (
        len(raw_points) != 12
        or any(not _is_int(point) for point in raw_points)
        or set(raw_points) != set(POINTS)
    ):
        _error(
            errors,
            "$.point_labels",
            "POINT_LABELS",
            "must contain every integer from 0 through 11 exactly once",
        )
    else:
        point_labels = tuple(sorted(raw_points))

    raw_blocks = document.get("blocks")
    parsed_blocks: list[tuple[int, ...]] = []
    if not isinstance(raw_blocks, list):
        _error(errors, "$.blocks", "TYPE", "must be an array")
    else:
        if len(raw_blocks) != 15:
            _error(
                errors,
                "$.blocks",
                "BLOCK_COUNT",
                "must contain exactly 15 blocks",
            )
        for block_index, block in enumerate(raw_blocks):
            path = f"$.blocks[{block_index}]"
            if not isinstance(block, list):
                _error(errors, path, "TYPE", "must be an array")
                continue
            if len(block) != 6:
                _error(errors, path, "BLOCK_SIZE", "must contain exactly 6 points")
                continue
            if any(not _is_int(point) for point in block):
                _error(errors, path, "POINT_TYPE", "all points must be integers")
                continue
            if len(set(block)) != 6:
                _error(errors, path, "BLOCK_DUPLICATE", "block points must be distinct")
                continue
            if any(point not in POINTS for point in block):
                _error(
                    errors,
                    path,
                    "POINT_RANGE",
                    "all points must be between 0 and 11",
                )
                continue
            parsed_blocks.append(tuple(sorted(block)))
        if len(parsed_blocks) == len(raw_blocks) and len(set(parsed_blocks)) != len(
            parsed_blocks
        ):
            _error(
                errors,
                "$.blocks",
                "DUPLICATE_BLOCK",
                "blocks must be distinct",
            )

    canonical_identity, class_index, representative_id, numbering_source = (
        _canonical_identity(document.get("identity"), errors)
    )
    canonical_provenance = _canonical_provenance(
        document.get("provenance"), errors
    )

    if errors:
        raise InputFormatError(sorted(errors, key=lambda item: (item["path"], item["code"])))

    blocks = canonical_blocks(parsed_blocks)
    canonical_document = {
        "blocks": [list(block) for block in blocks],
        "identity": canonical_identity,
        "parameters": {"block_count": 15, "k": 6, "t": 3, "v": 12},
        "point_labels": list(point_labels),
        "provenance": canonical_provenance,
        "schema_version": SCHEMA_VERSION,
    }
    return LinkDocument(
        raw_sha256=raw_sha256,
        raw_bytes=raw,
        canonical_document=canonical_document,
        canonical_document_sha256=canonical_document_sha256(canonical_document),
        canonical_labeled_link_sha256=canonical_labeled_link_sha256(
            point_labels, blocks
        ),
        point_labels=point_labels,
        blocks=blocks,
        class_index=class_index,
        representative_id=representative_id,
        numbering_source=numbering_source,
        provenance=canonical_provenance,
        content_was_canonical=document == canonical_document,
        bytes_were_canonical_serialization=raw
        == pretty_json_bytes(canonical_document),
    )


def load_link(path: Path) -> LinkDocument:
    return parse_link_bytes(path.read_bytes())
