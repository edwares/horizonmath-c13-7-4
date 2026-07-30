#!/usr/bin/env python3
"""Rebuild the immutable release's VeriPB 0.3a0 source for CPython 3.12."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from horizonlink.canonical import sha256_file, write_json


ROOT = Path(__file__).resolve().parents[1]
DEPENDENCIES = ROOT / "verifier" / "dependencies"
SETUP = ROOT / "verifier" / "setup.cp312.py"
SOURCE_PREFIX = (
    "Class52_formal_certification_complete/"
    "verifier/VeriPB-master/"
)
PINNED_HASHES = {
    "pybind11-2.13.6-py3-none-any.whl": (
        "237c41e29157b962835d356b370ededd57594a26d5894a795960f0047cb5caf5"
    ),
    "libgmp-dev_6.3.0+dfsg-2ubuntu6.1_amd64.deb": (
        "a9847b5ecfff791a46cb198f29a06d9d23a20afdfdd434812f2b44ccfb61d46a"
    ),
    "libgmpxx4ldbl_6.3.0+dfsg-2ubuntu6.1_amd64.deb": (
        "6f59344240b6dc139ed23ef236b8aa146e5d25e23aa90e79f814e2e4cc4b5752"
    ),
    "libgmp10_6.3.0+dfsg-2ubuntu6.1_amd64.deb": (
        "285f8a505dfa8e1b33f357a9d8d3477ad35bf18c0b34771a6df4c25923f3ae0d"
    ),
}


def _extract_veripb_source(source_archive: Path, output: Path) -> Path:
    with zipfile.ZipFile(source_archive) as archive:
        members = [
            info
            for info in archive.infolist()
            if info.filename.startswith(SOURCE_PREFIX)
        ]
        if not members:
            raise ValueError("VeriPB source prefix is absent from source archive")
        for info in members:
            relative = Path(info.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("unsafe path in source archive")
            archive.extract(info, output)
    source = output / SOURCE_PREFIX
    for path in source.rglob("*"):
        if path.is_file() and (
            path.suffix in {".so", ".o", ".pyc"}
            or ".cpython-313-" in path.name
        ):
            path.unlink()
    return source


def _extract_dependencies(output: Path) -> Path:
    dependency_root = output / "deps"
    pybind_root = dependency_root / "pybind11"
    gmp_root = dependency_root / "gmp"
    pybind_root.mkdir(parents=True)
    gmp_root.mkdir(parents=True)
    pybind_wheel = DEPENDENCIES / (
        "pybind11-2.13.6-py3-none-any.whl"
    )
    with zipfile.ZipFile(pybind_wheel) as archive:
        archive.extractall(pybind_root)
    for name in (
        "libgmp-dev_6.3.0+dfsg-2ubuntu6.1_amd64.deb",
        "libgmpxx4ldbl_6.3.0+dfsg-2ubuntu6.1_amd64.deb",
        "libgmp10_6.3.0+dfsg-2ubuntu6.1_amd64.deb",
    ):
        subprocess.run(
            ["dpkg-deb", "-x", str(DEPENDENCIES / name), str(gmp_root)],
            check=True,
            capture_output=True,
            text=True,
        )
    return dependency_root


def build(source_archive: Path, output: Path) -> dict:
    if output.exists() and any(output.iterdir()):
        raise ValueError("VeriPB build output directory must be empty")
    if sha256_file(source_archive) != (
        "c4c1ddc812affd9bd05c452855bdfcd614a68906f8bf536fab8bcd4b3123ae56"
    ):
        raise ValueError("source archive hash does not match immutable release")
    for name, expected in PINNED_HASHES.items():
        path = DEPENDENCIES / name
        if not path.is_file() or sha256_file(path) != expected:
            raise ValueError(f"dependency hash mismatch: {name}")

    output.mkdir(parents=True, exist_ok=True)
    source = _extract_veripb_source(source_archive, output)
    dependency_root = _extract_dependencies(output)
    gmp_library_directory = (
        dependency_root / "gmp" / "usr" / "lib" / "x86_64-linux-gnu"
    )
    optimized = source / "veripb" / "optimized"
    shutil.copyfile(
        gmp_library_directory / "libgmpxx.so.4.7.0",
        optimized / "libgmpxx.so.4",
    )
    shutil.copyfile(
        gmp_library_directory / "libgmp.so.10.5.0",
        optimized / "libgmp.so.10",
    )
    shutil.copyfile(SETUP, source / "setup.py")
    environment = dict(os.environ)
    environment.update({"CC": "gcc", "CXX": "g++"})
    completed = subprocess.run(
        [sys.executable, "setup.py", "bdist_wheel"],
        cwd=source,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    log_path = output / "build.log"
    log_path.write_text(
        "command_json: "
        + json.dumps(
            [sys.executable, "setup.py", "bdist_wheel"],
            separators=(",", ":"),
        )
        + "\n"
        + f"exit_code: {completed.returncode}\n"
        + "stdout:\n"
        + completed.stdout
        + "\nstderr:\n"
        + completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"VeriPB build failed; see {log_path}")
    wheels = sorted((source / "dist").glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("VeriPB build did not emit exactly one wheel")
    wheel = wheels[0]
    manifest = {
        "schema_version": "horizonmath.veripb-cp312-build.v1",
        "status": "BUILT",
        "source_archive": {
            "path": str(source_archive),
            "sha256": sha256_file(source_archive),
            "source_prefix": SOURCE_PREFIX,
        },
        "build_setup": {
            "path": str(SETUP),
            "sha256": sha256_file(SETUP),
            "notes": (
                "Uses the release's generated C sources for six Cython "
                "extensions and its unmodified C++ optimized source. "
                "rules_multigoal.py remains pure Python because the immutable "
                "archive contains no generated rules_multigoal.c."
            ),
        },
        "dependencies": [
            {
                "path": str(DEPENDENCIES / name),
                "sha256": sha256_file(DEPENDENCIES / name),
            }
            for name in sorted(PINNED_HASHES)
        ],
        "command": [sys.executable, "setup.py", "bdist_wheel"],
        "environment_overrides": {"CC": "gcc", "CXX": "g++"},
        "build_log": {
            "path": str(log_path),
            "sha256": sha256_file(log_path),
        },
        "wheel": {
            "path": str(wheel),
            "sha256": sha256_file(wheel),
            "bytes": wheel.stat().st_size,
        },
    }
    write_json(output / "build.manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = build(args.source_archive, args.output_directory)
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        print(
            json.dumps(
                {"status": "ERROR", "message": str(exc)},
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "wheel_sha256": manifest["wheel"]["sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
