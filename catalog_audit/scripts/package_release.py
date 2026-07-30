#!/usr/bin/env python3
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import shutil
import tempfile
import zipfile


RELEASE_NAME = "HorizonMath_link_catalog_audit_v0.1.0"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    source_archive = args.source_archive.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="horizonmath-catalog-release-") as tmp:
        stage = Path(tmp) / RELEASE_NAME
        direct_files = [
            "README.md",
            "NUMBERING_PHASE_AUDIT.md",
            "SOURCE_INVENTORY.json",
            "PHASE_MANIFEST.json",
            "pyproject.toml",
            "data/catalog-input.json",
        ]
        for relative in direct_files:
            copy(root / relative, stage / relative)

        for base in ("src", "scripts", "tests", "logs"):
            for path in sorted((root / base).rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    copy(path, stage / path.relative_to(root))

        authoritative = root / "build" / "run2"
        for path in sorted(authoritative.iterdir()):
            if path.is_file():
                copy(path, stage / "build" / "authoritative" / path.name)

        copied_archive = stage / "source_archives" / source_archive.name
        copy(source_archive, copied_archive)
        copied_archive.with_name(copied_archive.name + ".sha256").write_text(
            f"{digest(copied_archive)}  {copied_archive.name}\n",
            encoding="utf-8",
        )

        sum_rows = []
        for path in sorted(stage.rglob("*")):
            if path.is_file() and path.name != "SHA256SUMS":
                sum_rows.append(
                    f"{digest(path)}  {path.relative_to(stage).as_posix()}"
                )
        (stage / "SHA256SUMS").write_text(
            "\n".join(sum_rows) + "\n", encoding="utf-8"
        )

        archive = output_dir / f"{RELEASE_NAME}.zip"
        with zipfile.ZipFile(
            archive,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as handle:
            for path in sorted(stage.rglob("*")):
                if not path.is_file():
                    continue
                relative = Path(RELEASE_NAME) / path.relative_to(stage)
                info = zipfile.ZipInfo(relative.as_posix())
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                info.create_system = 3
                handle.writestr(info, path.read_bytes(), compresslevel=9)

    archive_hash = digest(archive)
    sidecar = archive.with_name(archive.name + ".sha256")
    sidecar.write_text(f"{archive_hash}  {archive.name}\n", encoding="utf-8")
    print(f"{archive_hash}  {archive}")
    print(sidecar)


if __name__ == "__main__":
    main()

