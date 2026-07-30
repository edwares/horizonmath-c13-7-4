#!/usr/bin/env python3
"""Create a deterministic, self-checksummed source-and-results ZIP."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / "HorizonMath_horizonlink_frontend_v0.4.0.zip"
SIDECAR = OUTPUT.with_name(OUTPUT.name + ".sha256")
CHECKSUMS = ROOT / "SHA256SUMS"
ARCHIVE_PREFIX = "horizonlink_frontend"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def included_files(*, include_checksums: bool) -> list[Path]:
    result = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if not include_checksums and path == CHECKSUMS:
            continue
        result.append(path)
    return sorted(result, key=lambda path: path.relative_to(ROOT).as_posix())


def write_checksums() -> None:
    lines = [
        f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}"
        for path in included_files(include_checksums=False)
    ]
    CHECKSUMS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_zip() -> None:
    temporary = OUTPUT.with_name(OUTPUT.name + ".tmp")
    with zipfile.ZipFile(
        temporary,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in included_files(include_checksums=True):
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(
                f"{ARCHIVE_PREFIX}/{relative}",
                date_time=(1980, 1, 1, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    temporary.replace(OUTPUT)
    SIDECAR.write_text(f"{sha256(OUTPUT)}  {OUTPUT.name}\n", encoding="utf-8")


def main() -> int:
    write_checksums()
    write_zip()
    print(f"{sha256(OUTPUT)}  {OUTPUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
