"""Focused tests for the shared cfg style contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from geodesy_visualization.styles import (
    colorbar_metadata_keys,
    font_style_keys,
    parse_colorbar_metadata,
    parse_font_style,
    resolve_cpt_reference,
)
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

    def test_resolves_cpt_files_but_preserves_gmt_palette_names(self) -> None:
        """Keep built-in GMT names portable and anchor file references to cfg."""
        base = Path("/tmp/example_cfg").resolve()
        self.assertEqual(resolve_cpt_reference("vik", base), "vik")
        self.assertEqual(
            resolve_cpt_reference("../cpt/custom.cpt", base),
            str((base / "../cpt/custom.cpt").resolve()),
        )
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            resolve_cpt_reference(" ", base)

    def test_parses_prefixed_and_unprefixed_colorbar_metadata(self) -> None:
        """Share identity keys without absorbing workflow-specific geometry."""
        self.assertEqual(
            colorbar_metadata_keys("defo"),
            {"add_colorbar", "defo_colorbar_label", "defo_colorbar_unit"},
        )
        self.assertEqual(
            parse_colorbar_metadata(
                {"colorbar_label": "Velocity", "colorbar_unit": "mm/yr"},
                "",
                enabled=False,
                default_label="Deformation",
                default_unit="mm",
            ),
            {
                "add_colorbar": False,
                "colorbar_label": "Velocity",
                "colorbar_unit": "mm/yr",
            },
        )


if __name__ == "__main__":
    unittest.main()
