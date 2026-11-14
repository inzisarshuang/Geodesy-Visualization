"""Tests for the cfg-driven baseline visualization command."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from geodesy_visualization.workflows.insar.baseline_plot import main
from geodesy_visualization.workflows.insar.baseline_plot_config import (
    load_baseline_plot_config,
    select_baseline_plot_case,
)
from geodesy_visualization.workflows.insar.baseline_plot_core import (
    read_baseline_manifest,
    read_baseline_network,
)


class BaselinePlotConfigTests(unittest.TestCase):
    """Keep every plot request explicit, project-confined, and reproducible."""

    def _project(self, directory: str) -> tuple[Path, Path, Path]:
        """Create one project with a non-empty baseline manifest and cfg path."""

        root = Path(directory) / "PROJECT"
        manifest = root / "ANALYSIS/GAMMA/ascending/BASELINE/baseline_manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}\n", encoding="utf-8")
        config = root / "config/visualization/baseline_plot.cfg"
        config.parent.mkdir(parents=True)
        return root, manifest, config

    def test_loads_cases_in_order_and_case_values_override_defaults(self) -> None:
        """Catch wrong precedence, path base, case order, or style conversion."""

        with tempfile.TemporaryDirectory() as directory:
            root, manifest, config = self._project(directory)
            config.write_text(
                """[project]
root = ../..

[defaults]
dpi = 180
figsize = 12, 6
y_top_extra = 60
y_bottom_extra = 5
matlab_font_family = Helvetica
title_label_font_size = 20
tick_font_size = 15
legend_font_size = 13
font_weight = normal
xlabel = Acquisition month
ylabel = Bperp (m)
date_format = %Y/%m
date_tick_unit = year
date_tick_interval = 2
date_tick_rotation = -15
y_tick_interval = 125
line_color = #112233
slave_color = #2244AA
reference_color = #CC2200
grid_color = #DDDDDD
show_grid = no
line_label = Selected pairs
slave_label = Secondary acquisitions
reference_label = Reference acquisition
title = Default title

[case:ascending]
baseline_manifest = ANALYSIS/GAMMA/ascending/BASELINE/baseline_manifest.json
output = VISUALIZATION/ascending/baseline.png
matlab_output = VISUALIZATION/ascending/baseline_matlab.png
title = Ascending network

[case:second]
baseline_manifest = ANALYSIS/GAMMA/ascending/BASELINE/baseline_manifest.json
output = VISUALIZATION/second/baseline.png
dpi = 240
figsize = 9 5
""",
                encoding="utf-8",
            )
            cases = load_baseline_plot_config(config)

        self.assertEqual([case.name for case in cases], ["ascending", "second"])
        first, second = cases
        self.assertEqual(first.project_root, root.resolve())
        self.assertEqual(first.baseline_manifest, manifest.resolve())
        self.assertEqual(
            first.output, (root / "VISUALIZATION/ascending/baseline.png").resolve()
        )
        self.assertEqual(first.title, "Ascending network")
        self.assertEqual(first.dpi, 180)
        self.assertEqual(first.figsize, (12.0, 6.0))
        self.assertEqual(first.y_top_extra, 60.0)
        self.assertEqual(first.y_bottom_extra, 5.0)
        self.assertEqual(first.matlab_font_family, "Helvetica")
        self.assertEqual(first.title_label_font_size, 20.0)
        self.assertEqual(first.tick_font_size, 15.0)
        self.assertEqual(first.legend_font_size, 13.0)
        self.assertEqual(first.font_weight, "normal")
        self.assertEqual(first.xlabel, "Acquisition month")
        self.assertEqual(first.ylabel, "Bperp (m)")
        self.assertEqual(first.date_format, "%Y/%m")
        self.assertEqual(first.date_tick_unit, "year")
        self.assertEqual(first.date_tick_interval, 2)
        self.assertEqual(first.date_tick_rotation, -15.0)
        self.assertEqual(first.y_tick_interval, 125.0)
        self.assertEqual(first.line_color, "#112233")
        self.assertEqual(first.slave_color, "#2244AA")
        self.assertEqual(first.reference_color, "#CC2200")
        self.assertEqual(first.grid_color, "#DDDDDD")
        self.assertFalse(first.show_grid)
        self.assertEqual(first.line_label, "Selected pairs")
        self.assertEqual(first.slave_label, "Secondary acquisitions")
        self.assertEqual(first.reference_label, "Reference acquisition")
        self.assertEqual(
            first.matlab_output,
            (root / "VISUALIZATION/ascending/baseline_matlab.png").resolve(),
        )
        self.assertEqual(second.dpi, 240)
        self.assertEqual(second.figsize, (9.0, 5.0))
        self.assertIsNone(second.matlab_output)
        self.assertEqual(select_baseline_plot_case(cases, "second"), second)

    def test_legacy_python_only_case_uses_publication_defaults(self) -> None:
        """Keep existing CFG files valid while adopting the MATLAB reference style."""

        with tempfile.TemporaryDirectory() as directory:
            _, _, config = self._project(directory)
            config.write_text(
                """[project]
root = ../..
[case:main]
baseline_manifest = ANALYSIS/GAMMA/ascending/BASELINE/baseline_manifest.json
output = VISUALIZATION/baseline.png
""",
                encoding="utf-8",
            )
            (case,) = load_baseline_plot_config(config)

        self.assertIsNone(case.matlab_output)
        self.assertIsNone(case.python_font_dir)
        self.assertEqual(case.matlab_font_family, "FreeSans")
        self.assertEqual(case.title, "Baselines Distribution")
        self.assertEqual(case.xlabel, "SLC Images Acquire Date")
        self.assertEqual(case.ylabel, "Perpendicular Baselines (m)")
        self.assertEqual(case.title_label_font_size, 18.0)
        self.assertEqual(case.tick_font_size, 16.0)
        self.assertEqual(case.legend_font_size, 14.0)
        self.assertEqual(case.font_weight, "bold")
        self.assertEqual(case.date_format, "%Y-%m")
        self.assertEqual(case.date_tick_unit, "month")
        self.assertEqual(case.date_tick_interval, 1)
        self.assertEqual(case.date_tick_rotation, 45.0)
        self.assertEqual(case.y_tick_interval, 100.0)
        self.assertTrue(case.show_grid)

    def test_single_case_does_not_require_name_but_multiple_cases_do(self) -> None:
        """Catch silently selecting an arbitrary case from a multi-case cfg."""

        with tempfile.TemporaryDirectory() as directory:
            _, _, config = self._project(directory)
            config.write_text(
                """[project]
root = ../..
[case:main]
baseline_manifest = ANALYSIS/GAMMA/ascending/BASELINE/baseline_manifest.json
output = VISUALIZATION/baseline.png
""",
                encoding="utf-8",
            )
            one = load_baseline_plot_config(config)
            self.assertEqual(select_baseline_plot_case(one, None).name, "main")
            with self.assertRaisesRegex(ValueError, "unknown case"):
                select_baseline_plot_case(one, "missing")
            config.write_text(
                config.read_text(encoding="utf-8")
                + "\n[case:other]\n"
                + "baseline_manifest = ANALYSIS/GAMMA/ascending/BASELINE/baseline_manifest.json\n"
                + "output = VISUALIZATION/other.png\n",
                encoding="utf-8",
            )
            many = load_baseline_plot_config(config)
            with self.assertRaisesRegex(ValueError, "--case"):
                select_baseline_plot_case(many, None)

    def test_method_root_derives_publication_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root, manifest, config = self._project(directory)
            config.write_text(
                "[project]\n"
                "root = ../..\n"
                "[case:main]\n"
                "project = S1/ASCENDING_128\n"
                "processing_root = S1/ASCENDING_128/GAMMA\n"
                f"baseline_manifest = {manifest.relative_to(root).as_posix()}\n",
                encoding="utf-8",
            )
            (case,) = load_baseline_plot_config(config)
            self.assertEqual(
                case.output,
                root
                / "S1/ASCENDING_128/GAMMA/FIGURES/PUBLICATION/BASELINE_PLOT/baseline_plot.png",
            )

    def test_rejects_structural_and_required_value_errors(self) -> None:
        """Catch ambiguous or incomplete configuration before plotting imports."""

        cases = (
            (
                "[project]\nroot=../..\nroot=../..\n",
                "duplicate|strict|option",
            ),
            (
                "[project]\nroot=../..\nunknown=x\n[case:main]\n"
                "baseline_manifest=ANALYSIS/GAMMA/ascending/BASELINE/baseline_manifest.json\n"
                "output=VISUALIZATION/a.png\n",
                "unknown",
            ),
            (
                "[project]\nroot=../..\n[other]\nx=y\n",
                "unsupported",
            ),
            (
                "[project]\nroot=../..\n[case:../bad]\n"
                "baseline_manifest=ANALYSIS/GAMMA/ascending/BASELINE/baseline_manifest.json\n"
                "output=VISUALIZATION/a.png\n",
                "unsafe",
            ),
            (
                "[project]\nroot=../..\n[case:main]\noutput=VISUALIZATION/a.png\n",
                "baseline_manifest",
            ),
            (
                "[project]\nroot=../..\n[case:main]\n"
                "baseline_manifest=ANALYSIS/GAMMA/ascending/BASELINE/baseline_manifest.json\n",
                "output",
            ),
        )
        for content, message in cases:
            with self.subTest(message=message):
                with tempfile.TemporaryDirectory() as directory:
                    _, _, config = self._project(directory)
                    config.write_text(content, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        load_baseline_plot_config(config)

    def test_rejects_missing_manifest_invalid_numbers_and_path_escape(self) -> None:
        """Catch missing inputs, invalid styles, and writes outside the project."""

        cases = (
            ("baseline_manifest = missing.json", "manifest"),
            ("dpi = 0", "dpi"),
            ("figsize = 10, 0", "figsize"),
            ("y_top_extra = -1", "y_top_extra"),
            ("y_bottom_extra = -1", "y_bottom_extra"),
            ("python_font_dir = .", "TTF or OTF"),
            ("title_label_font_size = 0", "title_label_font_size"),
            ("tick_font_size = nan", "tick_font_size"),
            ("legend_font_size = -1", "legend_font_size"),
            ("font_weight = heavy", "font_weight"),
            ("font_family = FreeSans", "unknown"),
            ("python_font_family = FreeSans", "unknown"),
            ("date_tick_unit = quarter", "date_tick_unit"),
            ("date_tick_interval = 0", "date_tick_interval"),
            ("date_tick_rotation = inf", "date_tick_rotation"),
            ("y_tick_interval = 0", "y_tick_interval"),
            ("line_color = red", "line_color"),
            ("slave_color = #12345", "slave_color"),
            ("reference_color = #GG0000", "reference_color"),
            ("grid_color = 112233", "grid_color"),
            ("show_grid = perhaps", "show_grid"),
            ("date_format = %Y-%q", "date_format"),
            ("date_format = %Y_%m", "date_format"),
            ("matlab_output = /tmp/outside-matlab.png", "project"),
            ("unknown_style = value", "unknown"),
            ("output = /tmp/outside-baseline.png", "project"),
        )
        for override, message in cases:
            with self.subTest(override=override):
                with tempfile.TemporaryDirectory() as directory:
                    _, _, config = self._project(directory)
                    manifest_value = (
                        override.split("=", 1)[1].strip()
                        if override.startswith("baseline_manifest")
                        else "ANALYSIS/GAMMA/ascending/BASELINE/baseline_manifest.json"
                    )
                    output_value = (
                        override.split("=", 1)[1].strip()
                        if override.startswith("output")
                        else "VISUALIZATION/baseline.png"
                    )
                    style_override = (
                        ""
                        if override.startswith(("baseline_manifest", "output"))
                        else override + "\n"
                    )
                    config.write_text(
                        f"""[project]
root = ../..
[case:main]
baseline_manifest = {manifest_value}
output = {output_value}
{style_override}""",
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        (FileNotFoundError, ValueError), message
                    ):
                        load_baseline_plot_config(config)


class BaselinePlotCliTests(unittest.TestCase):
    """Exercise the installed workflow boundary with real local products."""

    def _configured_project(self, directory: str, *, two_cases: bool = False) -> tuple[Path, Path]:
        """Create one executable manifest-based plotting case."""

        root = Path(directory) / "PROJECT"
        product = root / "ANALYSIS/GAMMA/ascending/BASELINE"
        product.mkdir(parents=True)
        (product / "baseline_select_SBAS").write_text(
            "20200101 20200113 10 12\n", encoding="utf-8"
        )
        (product / "baseline_manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "complete",
                    "reference_date": "20200101",
                    "pair_count": 1,
                    "network_path": "baseline_select_SBAS",
                }
            ),
            encoding="utf-8",
        )
        config = root / "config/visualization/baseline_plot.cfg"
        config.parent.mkdir(parents=True)
        extra = (
            "\n[case:other]\n"
            "baseline_manifest = ANALYSIS/GAMMA/ascending/BASELINE/baseline_manifest.json\n"
            "output = VISUALIZATION/other.png\n"
            if two_cases
            else ""
        )
        config.write_text(
            """[project]
root = ../..
[case:ascending]
baseline_manifest = ANALYSIS/GAMMA/ascending/BASELINE/baseline_manifest.json
output = VISUALIZATION/ascending/baseline.png
title = Test baseline network
dpi = 90
figsize = 6, 4
"""
            + extra,
            encoding="utf-8",
        )
        return root, config

    def test_config_is_required_by_the_public_command(self) -> None:
        """Catch an invocation that proceeds without a reproducible cfg."""

        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, "2"):
                main([])

    def test_selected_case_publishes_real_png_without_external_commands(self) -> None:
        """Catch a CLI that bypasses manifest validation or invokes GAMMA."""

        with tempfile.TemporaryDirectory() as directory:
            root, config = self._configured_project(directory, two_cases=True)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = main(["--config", str(config), "--case", "ascending"])
            output = root / "VISUALIZATION/ascending/baseline.png"
            self.assertEqual(result, 0)
            self.assertGreater(output.stat().st_size, 1000)
            self.assertIn(str(output.resolve()), stdout.getvalue())

    def test_validation_errors_return_two_without_publishing(self) -> None:
        """Catch raw exceptions or partial figures for an invalid product."""

        with tempfile.TemporaryDirectory() as directory:
            root, config = self._configured_project(directory, two_cases=True)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = main(["--config", str(config)])
            self.assertEqual(result, 2)
            self.assertIn("--case", stderr.getvalue())
            self.assertFalse((root / "VISUALIZATION/ascending/baseline.png").exists())

    def test_package_exposes_the_visualization_command_and_example(self) -> None:
        """Catch an implemented workflow that cannot be installed or configured."""

        repository = Path(__file__).resolve().parents[1]
        project = (repository / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(
            'geodesy-visualization = "geodesy_visualization.cli:main"',
            project,
        )
        self.assertNotIn("geodesy-visualization-insar-baseline", project)
        self.assertIn(
            '"share/geodesy-visualization/config_examples/baseline_plot" = '
            '["config_examples/baseline_plot/*.cfg"]',
            project,
        )
        examples = repository / "config_examples/baseline_plot/baseline_plot.cfg"
        self.assertTrue(examples.is_file())
        self.assertGreater(examples.stat().st_size, 0)
        self.assertFalse((repository / "config_examples/visualization").exists())


class BaselinePlotDependencyTests(unittest.TestCase):
    """Keep pure configuration loading independent from plotting libraries."""

    def test_configuration_module_does_not_import_matplotlib(self) -> None:
        """Catch an environment-heavy import before configuration validation."""

        script = (
            "import sys; "
            "import geodesy_visualization.workflows.insar.baseline_plot_config; "
            "assert 'matplotlib' not in sys.modules"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


class BaselineExampleTests(unittest.TestCase):
    """Keep the packaged LT-1 reference scientifically exact and runnable."""

    def test_lt1_example_preserves_the_historical_three_pair_network(self) -> None:
        """Catch a demo that drifts away from the accepted MATLAB source values."""

        repository = Path(__file__).resolve().parents[1]
        config = repository / "config_examples/baseline_plot/baseline_plot.cfg"
        (case,) = load_baseline_plot_config(config)
        manifest = read_baseline_manifest(
            case.baseline_manifest, project_root=case.project_root
        )
        network = read_baseline_network(manifest)

        self.assertEqual(manifest.reference_date, "20231222")
        self.assertEqual(manifest.pair_count, 3)
        self.assertEqual(
            [
                (pair.master, pair.slave, pair.perpendicular_baseline_m)
                for pair in network.pairs
            ],
            [
                ("20231222", "20230629", -603.5297),
                ("20231222", "20230731", -808.2997),
                ("20231222", "20231218", -742.2232),
            ],
        )
        self.assertEqual(
            case.python_font_dir,
            (repository / "fonts/TeXGyreHeros").resolve(),
        )
        self.assertEqual(case.matlab_font_family, "FreeSans")
        self.assertIsNotNone(case.matlab_output)


if __name__ == "__main__":
    unittest.main()
