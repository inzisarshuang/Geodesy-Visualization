"""Tests for shared plotting configuration and I/O helpers."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "lib"))

import pygmt_io as legacy_io
from geodesy_visualization.io import load_key_value_config, validate_config_keys


class PlotConfigTests(unittest.TestCase):
    def test_legacy_module_reexports_canonical_implementation(self) -> None:
        """Keep existing imports working without maintaining duplicate behavior."""
        self.assertIs(legacy_io.load_key_value_config, load_key_value_config)
        self.assertIs(legacy_io.validate_config_keys, validate_config_keys)

    def write_config(self, text: str) -> Path:
        """Write one temporary cfg used by a parser regression test."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "test.cfg"
        path.write_text(text, encoding="utf-8")
        return path

    def test_preserves_hex_colors_and_expands_config_references(self) -> None:
        """Preserve hexadecimal colors while expanding cfg references."""
        path = self.write_config(
            "output_dir = result\n"
            "output = ${output_dir}/map.png\n"
            "color = #1f77b4\n"
            "pen = 1p,#33147d  # inline comment\n"
        )

        cfg = load_key_value_config(str(path))

        self.assertEqual(cfg["output"], "result/map.png")
        self.assertEqual(cfg["color"], "#1f77b4")
        self.assertEqual(cfg["pen"], "1p,#33147d")

    def test_rejects_duplicate_and_malformed_lines(self) -> None:
        """Reject ambiguous duplicate keys and lines without a delimiter."""
        duplicate = self.write_config("key = one\nkey = two\n")
        with self.assertRaisesRegex(ValueError, "duplicate configuration key"):
            load_key_value_config(str(duplicate))

        malformed = self.write_config("this line has no delimiter\n")
        with self.assertRaisesRegex(ValueError, "expected key=value"):
            load_key_value_config(str(malformed))

    def test_rejects_cycles_and_unknown_keys_with_suggestion(self) -> None:
        """Report cyclic references and suggest corrections for unknown keys."""
        cyclic = self.write_config("first = ${second}\nsecond = ${first}\n")
        with self.assertRaisesRegex(ValueError, "cyclic configuration reference"):
            load_key_value_config(str(cyclic))

        with self.assertRaisesRegex(ValueError, "did you mean 'projection'"):
            validate_config_keys({"projetion": "M8i"}, {"projection"}, str(cyclic))


if __name__ == "__main__":
    unittest.main()
