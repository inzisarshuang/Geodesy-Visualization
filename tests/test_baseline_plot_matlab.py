"""Static contract tests for the optional shared-CFG MATLAB baseline backend."""

from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
MATLAB_DIR = REPOSITORY / "config_examples/baseline_plot/matlab"


class BaselineMatlabExampleTests(unittest.TestCase):
    """Keep the MATLAB adapter portable and aligned with the shared CFG."""

    def test_shared_cfg_reader_and_renderer_are_packaged(self) -> None:
        """Require both MATLAB entry files and installed package metadata."""

        reader = MATLAB_DIR / "read_baseline_plot_cfg.m"
        renderer = MATLAB_DIR / "baseline_plot_from_cfg.m"
        self.assertTrue(reader.is_file())
        self.assertTrue(renderer.is_file())
        project = (REPOSITORY / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(
            '"share/geodesy-visualization/config_examples/baseline_plot/matlab"',
            project,
        )

    def test_renderer_consumes_shared_paths_and_publication_controls(self) -> None:
        """Reject hard-coded LT paths or a second independent MATLAB config."""

        source = (MATLAB_DIR / "baseline_plot_from_cfg.m").read_text(
            encoding="utf-8"
        )
        self.assertIn("function outputPath = baseline_plot_from_cfg(cfgPath, caseName)", source)
        for token in (
            "baseline_manifest",
            "matlab_output",
            "matlab_font_family",
            "title_label_font_size",
            "tick_font_size",
            "legend_font_size",
            "date_format",
            "date_tick_unit",
            "date_tick_interval",
            "date_tick_rotation",
            "y_tick_interval",
            "line_color",
            "slave_color",
            "reference_color",
            "grid_color",
            "show_grid",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        self.assertNotIn("/mnt/beegfs", source)
        self.assertNotIn("Gansu_Jishishan", source)
        self.assertNotIn("listfonts", source)

    def test_reader_preserves_hex_colors_and_rejects_duplicate_keys(self) -> None:
        """Pin the two INI details most likely to diverge from ConfigParser."""

        source = (MATLAB_DIR / "read_baseline_plot_cfg.m").read_text(encoding="utf-8")
        self.assertIn("startsWith(line, '#')", source)
        self.assertIn("isfield(sections.(sectionField), key)", source)
        self.assertNotIn("extractBefore(line, '#')", source)

    def test_date_tick_limits_do_not_shadow_matlab_lower_function(self) -> None:
        """Keep date-limit names distinct from MATLAB's lower() function."""

        source = (MATLAB_DIR / "baseline_plot_from_cfg.m").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "function ticks = date_ticks(lowerLimit, upperLimit, unit, interval)",
            source,
        )
        self.assertNotIn(
            "function ticks = date_ticks(lower, upper, unit, interval)", source
        )

    def test_grid_is_drawn_below_baseline_segments_and_markers(self) -> None:
        """Keep the grid behind the scientific data instead of covering it."""

        source = (MATLAB_DIR / "baseline_plot_from_cfg.m").read_text(
            encoding="utf-8"
        )
        self.assertIn("'Layer', 'bottom'", source)
        self.assertNotIn("'Layer', 'top'", source)

    def test_month_ticks_use_the_same_global_calendar_anchor_as_python(self) -> None:
        """Keep three-month ticks on January/April/July/October in MATLAB."""

        source = (MATLAB_DIR / "baseline_plot_from_cfg.m").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "monthSerial = year(startDate) * 12 + month(startDate) - 1;", source
        )
        self.assertIn(
            "firstSerial = ceil(monthSerial / interval) * interval;", source
        )


if __name__ == "__main__":
    unittest.main()
