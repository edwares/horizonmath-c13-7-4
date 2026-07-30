from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_source_manifest import build_manifest


class SourceManifestTests(unittest.TestCase):
    def test_editable_install_metadata_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="horizonmath-source-manifest-"
        ) as temporary:
            root = Path(temporary)
            tracked = root / "src" / "horizonlink" / "__init__.py"
            tracked.parent.mkdir(parents=True)
            tracked.write_text("__version__ = 'test'\n", encoding="utf-8")

            generated = (
                root
                / "src"
                / "horizonlink.egg-info"
                / "PKG-INFO"
            )
            generated.parent.mkdir(parents=True)
            generated.write_text("generated\n", encoding="utf-8")

            output = root / "SOURCE_MANIFEST.json"
            manifest = build_manifest(root, output)
            paths = {
                record["path"] for record in manifest["files"]
            }

            self.assertIn("src/horizonlink/__init__.py", paths)
            self.assertNotIn(
                "src/horizonlink.egg-info/PKG-INFO", paths
            )
            self.assertEqual(
                manifest["excluded_directory_suffixes"],
                [".egg-info"],
            )


if __name__ == "__main__":
    unittest.main()
