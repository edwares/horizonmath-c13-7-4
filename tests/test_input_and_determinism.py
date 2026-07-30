from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from horizonlink.canonical import pretty_json_bytes, sha256_file
from horizonlink.cli import main
from horizonlink.input import InputFormatError, load_link, parse_link_bytes
from horizonlink.manifest import build_manifest


ROOT = Path(__file__).resolve().parents[1]
CLASS52 = ROOT / "data" / "class52.link.json"


class InputAndDeterminismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline = load_link(CLASS52)

    def test_noncanonical_order_normalizes_to_same_link(self) -> None:
        scrambled = copy.deepcopy(self.baseline.canonical_document)
        scrambled["point_labels"].reverse()
        scrambled["blocks"] = [
            list(reversed(block)) for block in reversed(scrambled["blocks"])
        ]
        scrambled["provenance"]["source_artifacts"].reverse()
        parsed = parse_link_bytes(
            json.dumps(scrambled, separators=(",", ":")).encode("utf-8")
        )

        self.assertEqual(
            parsed.canonical_labeled_link_sha256,
            self.baseline.canonical_labeled_link_sha256,
        )
        self.assertEqual(
            parsed.canonical_document, self.baseline.canonical_document
        )
        self.assertFalse(parsed.content_was_canonical)
        self.assertFalse(parsed.bytes_were_canonical_serialization)

    def test_canonical_bytes_are_recognized(self) -> None:
        parsed = parse_link_bytes(
            pretty_json_bytes(self.baseline.canonical_document)
        )
        self.assertTrue(parsed.content_was_canonical)
        self.assertTrue(parsed.bytes_were_canonical_serialization)

    def test_manifest_is_exactly_deterministic(self) -> None:
        first = build_manifest(self.baseline)
        second = build_manifest(load_link(CLASS52))
        self.assertEqual(first, second)
        self.assertEqual(pretty_json_bytes(first), pretty_json_bytes(second))

    def test_duplicate_json_key_is_rejected(self) -> None:
        with self.assertRaises(InputFormatError) as caught:
            parse_link_bytes(b'{"schema_version":"a","schema_version":"b"}')
        self.assertEqual(caught.exception.errors[0]["code"], "JSON")
        self.assertIn("duplicate JSON key", caught.exception.errors[0]["message"])

    def test_wrong_block_count_is_rejected(self) -> None:
        malformed = copy.deepcopy(self.baseline.canonical_document)
        malformed["blocks"].pop()
        with self.assertRaises(InputFormatError) as caught:
            parse_link_bytes(pretty_json_bytes(malformed))
        self.assertIn(
            "BLOCK_COUNT",
            {error["code"] for error in caught.exception.errors},
        )

    def test_duplicate_block_is_rejected(self) -> None:
        malformed = copy.deepcopy(self.baseline.canonical_document)
        malformed["blocks"][-1] = malformed["blocks"][0]
        with self.assertRaises(InputFormatError) as caught:
            parse_link_bytes(pretty_json_bytes(malformed))
        self.assertIn(
            "DUPLICATE_BLOCK",
            {error["code"] for error in caught.exception.errors},
        )

    def test_cli_writes_correct_hash_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            normalized = root / "normalized.json"
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(
                    [
                        "analyze",
                        str(CLASS52),
                        "--manifest",
                        str(manifest),
                        "--normalized-link",
                        str(normalized),
                    ]
                )
            self.assertEqual(exit_code, 0)
            for path in (manifest, normalized):
                sidecar = path.with_name(path.name + ".sha256")
                self.assertTrue(sidecar.is_file())
                expected = f"{sha256_file(path)}  {path.name}\n"
                self.assertEqual(sidecar.read_text(encoding="utf-8"), expected)


if __name__ == "__main__":
    unittest.main()
