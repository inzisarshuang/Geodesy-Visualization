"""Focused tests for the shared cfg style contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from geodesy_visualization.styles import font_style_keys, parse_font_style
from geodesy_visualization.io import parse_style_block


class FontStyleContractTests(unittest.TestCase):
    """Verify canonical keys, workflow defaults, overrides, and strict blanks."""

    def test_declares_primary_and_optional_secondary_keys(self) -> None:
        """Expose one stable cfg vocabulary for every named font block."""
        self.assertEqual(
            font_style_keys("default"),
            {"default_font_title", "default_font_annot_primary", "default_font_label"},
        )
        self.assertIn(
            "default_font_annot_secondary",
            font_style_keys("default", include_secondary=True),
        )
        self.assertIs(parse_style_block, parse_font_style)

    def test_preserves_defaults_and_applies_explicit_overrides(self) -> None:
        """Return GMT keys while keeping caller-owned defaults unchanged."""
        style = parse_font_style(
            {"map_font_title": "30p,Helvetica-Bold"},
            "map",
            "20p,Helvetica",
            "10p,Helvetica",
            "12p,Helvetica",
        )
        self.assertEqual(style["FONT_TITLE"], "30p,Helvetica-Bold")
        self.assertEqual(style["FONT_ANNOT_PRIMARY"], "10p,Helvetica")

    def test_rejects_empty_prefix_and_explicit_blank_font(self) -> None:
        """Reject ambiguous style blocks and blank values before rendering."""
        with self.assertRaisesRegex(ValueError, "prefix"):
            font_style_keys(" ")
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            parse_font_style(
                {"default_font_label": " "},
                "default",
                "20p,Helvetica",
                "10p,Helvetica",
                "12p,Helvetica",
            )


if __name__ == "__main__":
    unittest.main()
