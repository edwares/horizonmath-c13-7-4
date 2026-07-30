#!/usr/bin/env python3
"""Create the deterministic classification-provenance audit release ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path


RELEASE_NAME = "HorizonMath_classification_provenance_audit_v0.1.0"
FIXED_ZIP_TIME = (2026, 7, 29, 0, 0, 0)
ROOT_FILES = {
    "CLASSIFICATION_PROVENANCE_AUDIT.md",
    "PHASE_MANIFEST.json",
    "README.md",
    "REPRODUCE.md",
    "requirements.txt",
}
INCLUDED_DIRECTORIES = {"audit", "logs", "scripts", "sources", "upstream"}
EXCLUDED_RELATIVE_PATHS = {
    Path("sources/c-12-6-3.pdf"),
}
EXCLUDED_DIRECTORY_NAMES = {"__pycache__"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def selected_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for relative in sorted(ROOT_FILES):
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        files.append(path)
    for directory in sorted(INCLUDED_DIRECTORIES):
        base = root / directory
        if not base.is_dir():
            raise FileNotFoundError(base)
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            relative = path.relative_to(root)
            if relative in EXCLUDED_RELATIVE_PATHS:
                continue
            if any(part in EXCLUDED_DIRECTORY_NAMES for part in relative.parts):
                continue
            files.append(path)
    return sorted(set(files), key=lambda p: p.relative_to(root).as_posix())


def validate_phase_manifest(root: Path) -> None:
    manifest = json.loads((root / "PHASE_MANIFEST.json").read_text(encoding="utf-8"))
    expected = {
        "paper_templates_sha256": root / "audit/paper.templates.json",
        "paper_template_comparison_audit_sha256": (
            root / "audit/paper-template-comparison.audit.json"
        ),
        "classification_provenance_audit_sha256": (
            root / "audit/classification-provenance.audit.json"
        ),
        "literature_to_project_class_map_sha256": (
            root / "audit/literature-to-project-class-map.json"
        ),
        "source_search_audit_sha256": root / "audit/source-search.audit.json",
    }
    for field, path in expected.items():
        actual = sha256_file(path)
        if manifest["outputs"][field] != actual:
            raise ValueError(
                f"PHASE_MANIFEST output hash mismatch for {field}: {actual}"
            )
    if manifest["status"] != "PASS":
        raise ValueError("PHASE_MANIFEST status is not PASS")


def zip_info(archive_name: str, executable: bool) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(archive_name, FIXED_ZIP_TIME)
    info.create_system = 3
    mode = 0o755 if executable else 0o644
    info.external_attr = (stat.S_IFREG | mode) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("artifacts/literature-audit"),
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    validate_phase_manifest(root)
    files = selected_files(root)
    relative_files = [path.relative_to(root) for path in files]
    if Path("sources/c-12-6-3.pdf") in relative_files:
        raise ValueError("primary paper must not be redistributed in the release ZIP")

    checksum_rows = [
        f"{sha256_file(path)}  {path.relative_to(root).as_posix()}"
        for path in files
    ]
    checksum_bytes = ("\n".join(checksum_rows) + "\n").encode("utf-8")
    (root / "SHA256SUMS").write_bytes(checksum_bytes)

    output_directory = args.output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    zip_path = output_directory / f"{RELEASE_NAME}.zip"
    checksum_path = output_directory / f"{RELEASE_NAME}.zip.sha256"

    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for path in files:
            relative = path.relative_to(root)
            archive_name = f"{RELEASE_NAME}/{relative.as_posix()}"
            executable = bool(path.stat().st_mode & stat.S_IXUSR)
            archive.writestr(zip_info(archive_name, executable), path.read_bytes())
        archive.writestr(
            zip_info(f"{RELEASE_NAME}/SHA256SUMS", False),
            checksum_bytes,
        )

    zip_sha256 = sha256_file(zip_path)
    checksum_path.write_text(
        f"{zip_sha256}  {zip_path.name}\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "file_count_excluding_SHA256SUMS": len(files),
                "release_zip": str(zip_path),
                "release_zip_sha256": zip_sha256,
                "status": "PASS",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
