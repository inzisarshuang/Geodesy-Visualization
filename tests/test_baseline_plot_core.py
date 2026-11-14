"""Behavioral tests for the source-neutral InSAR baseline visualization."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from geodesy_visualization.workflows.insar.baseline_plot_core import (
    _build_baseline_plot,
    _calendar_tick_dates,
    render_baseline_plot,
    read_baseline_manifest,
    read_baseline_network,
)


class _ProductFactory:
    """Create complete local Analysis products shared by behavioral tests."""

    def _product(
        self,
        root: Path,
        *,
        rows: str | None = None,
        manifest_updates: dict[str, object] | None = None,
    ) -> Path:
        """Write one complete Analysis baseline product for a test."""

        product = root / "ANALYSIS/GAMMA/ascending/BASELINE"
        product.mkdir(parents=True)
        network = product / "baseline_select_SBAS"
        network.write_text(
            rows
            if rows is not None
            else (
                "20200101 20200113 10 12\n"
                "20200113 20200125 -3 12\n"
                "20200101 20200125 7 24\n"
            ),
            encoding="utf-8",
        )
        payload: dict[str, object] = {
            "schema_version": 1,
            "status": "complete",
            "reference_date": "20200101",
            "network_path": "baseline_select_SBAS",
            "network_type": "SBAS",
            "plot_path": "legacy_plot_may_not_exist.png",
        }
        payload.update(manifest_updates or {})
        manifest = product / "baseline_manifest.json"
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        return manifest


class BaselineNetworkContractTests(_ProductFactory, unittest.TestCase):
    """Reject unsafe products and preserve the scientific network values."""

    def test_preserves_pair_order_and_solves_signed_node_baselines(self) -> None:
        """Catch reordered pairs or a wrong sign while traversing the network."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = read_baseline_manifest(self._product(root), project_root=root)
            network = read_baseline_network(manifest)

        self.assertEqual(manifest.reference_date, "20200101")
        self.assertEqual(len(network.pairs), 3)
        self.assertEqual(
            [(pair.master, pair.slave) for pair in network.pairs],
            [
                ("20200101", "20200113"),
                ("20200113", "20200125"),
                ("20200101", "20200125"),
            ],
        )
        self.assertEqual(network.dates, ("20200101", "20200113", "20200125"))
        self.assertEqual(
            dict(network.perpendicular_baselines_m),
            {"20200101": 0.0, "20200113": 10.0, "20200125": 7.0},
        )

    def test_rejects_invalid_manifest_identity_and_unsafe_network_paths(self) -> None:
        """Catch incomplete products and paths that escape their publication folder."""

        cases = (
            ({"schema_version": 3}, "schema_version"),
            ({"status": "failed"}, "status"),
            ({"reference_date": "2020-01-01"}, "reference_date"),
            ({"network_path": "/tmp/network"}, "relative"),
            ({"network_path": "../network"}, "traverse"),
        )
        for updates, message in cases:
            with self.subTest(updates=updates):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = self._product(root, manifest_updates=updates)
                    with self.assertRaisesRegex(ValueError, message):
                        read_baseline_manifest(source, project_root=root)

    def test_rejects_manifest_outside_project(self) -> None:
        """Catch a valid-looking manifest selected from another project."""

        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as other:
            source = self._product(Path(other))
            with self.assertRaisesRegex(ValueError, "project"):
                read_baseline_manifest(source, project_root=Path(project))

    def test_pair_count_is_derived_from_network_instead_of_manifest(self) -> None:
        """Allow users to edit pair rows without synchronizing redundant metadata."""

        for updates in ({}, {"pair_count": 999}):
            with self.subTest(updates=updates):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    manifest = read_baseline_manifest(
                        self._product(root, manifest_updates=updates),
                        project_root=root,
                    )
                    network = read_baseline_network(manifest)
                    self.assertEqual(len(network.pairs), 3)

    def test_rejects_missing_or_empty_network(self) -> None:
        """Catch a manifest published without its declared scientific table."""

        for mode in ("missing", "empty"):
            with self.subTest(mode=mode):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = self._product(root)
                    manifest = read_baseline_manifest(source, project_root=root)
                    if mode == "missing":
                        manifest.network_path.unlink()
                    else:
                        manifest.network_path.write_text("", encoding="utf-8")
                    with self.assertRaisesRegex(
                        (FileNotFoundError, ValueError), "network"
                    ):
                        read_baseline_network(manifest)

    def test_rejects_malformed_or_inconsistent_network_rows(self) -> None:
        """Catch rows that would draw scientifically misleading topology."""

        cases = (
            ("2020010X 20200113 10 12\n", {}, "date"),
            ("20200101 20200101 0 0\n", {}, "self"),
            (
                "20200101 20200113 10 12\n20200101 20200113 10 12\n",
                {},
                "duplicate",
            ),
            (
                "20200101 20200113 10 12\n20200113 20200101 -10 -12\n",
                {},
                "reversed",
            ),
            ("20200101 20200113 nan 12\n", {}, "finite"),
            ("20200101 20200113 10 inf\n", {}, "finite"),
            ("20200101 20200113 10\n", {}, "four"),
            (
                "20200101 20200113 10 12\n",
                {"reference_date": "20200125"},
                "reference",
            ),
        )
        for rows, updates, message in cases:
            with self.subTest(message=message):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = self._product(
                        root, rows=rows, manifest_updates=updates
                    )
                    manifest = read_baseline_manifest(source, project_root=root)
                    with self.assertRaisesRegex(ValueError, message):
                        read_baseline_network(manifest)


class BaselineNetworkRenderTests(_ProductFactory, unittest.TestCase):
    """Publish a real PNG atomically from already validated network data."""

    @staticmethod
    def _style() -> dict[str, object]:
        """Return one fully explicit MATLAB-reference publication style."""

        return {
            "title": "Configured title",
            "figsize": (7.0, 5.0),
            "y_top_extra": 20.0,
            "y_bottom_extra": 10.0,
            "font_family": "FreeSans",
            "title_label_font_size": 18.0,
            "tick_font_size": 13.0,
            "legend_font_size": 11.0,
            "font_weight": "bold",
            "xlabel": "Configured date label",
            "ylabel": "Configured baseline label",
            "date_format": "%Y/%m",
            "date_tick_unit": "month",
            "date_tick_interval": 2,
            "date_tick_rotation": 30.0,
            "y_tick_interval": 25.0,
            "line_color": "#112233",
            "slave_color": "#0000FF",
            "reference_color": "#FF0000",
            "grid_color": "#D9D9D9",
            "show_grid": True,
            "line_label": "Configured pairs",
            "slave_label": "Configured slaves",
            "reference_label": "Configured reference",
        }

    def _network(self, root: Path):
        """Build the smallest connected network accepted by the renderer."""

        source = self._product(
            root,
            rows="20200101 20200113 10 12\n",
            manifest_updates={},
        )
        return read_baseline_network(
            read_baseline_manifest(source, project_root=root)
        )

    def test_font_directory_selects_its_single_embedded_family(self) -> None:
        """Avoid a redundant family-name setting when one directory is one family."""

        from geodesy_visualization.backends.matplotlib import configure_plot_font

        repository = Path(__file__).resolve().parents[1]
        selected = configure_plot_font(
            strict=True,
            font_dir=repository / "fonts/LiberationSans",
        )

        self.assertEqual(selected, "Liberation Sans")

    def test_three_month_ticks_use_calendar_quarter_anchors(self) -> None:
        """Keep Python and MATLAB on January/April/July/October anchors."""

        ticks = _calendar_tick_dates(
            datetime(2023, 6, 1), datetime(2024, 2, 1), "month", 3
        )
        self.assertEqual(
            ticks,
            (
                datetime(2023, 7, 1),
                datetime(2023, 10, 1),
                datetime(2024, 1, 1),
            ),
        )

    def test_publishes_a_nonempty_png_and_returns_resolved_path(self) -> None:
        """Catch a renderer that does not create the configured final figure."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "VISUALIZATION/baseline_plot.png"
            result = render_baseline_plot(
                self._network(root),
                destination,
                dpi=90,
                **self._style(),
            )
            self.assertEqual(result, destination.resolve())
            self.assertGreater(destination.stat().st_size, 1000)
            self.assertEqual(destination.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_plot_failure_preserves_previous_destination_and_cleans_temporary(self) -> None:
        """Catch partial replacement of a valid pre-existing scientific figure."""

        import matplotlib.pyplot  # noqa: F401

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "baseline_plot.png"
            destination.write_bytes(b"existing-figure")
            with patch("matplotlib.figure.Figure.savefig", side_effect=RuntimeError("stop")):
                with self.assertRaisesRegex(RuntimeError, "stop"):
                    render_baseline_plot(
                        self._network(root),
                        destination,
                        dpi=90,
                        **self._style(),
                    )
            self.assertEqual(destination.read_bytes(), b"existing-figure")
            self.assertEqual(list(root.glob(".baseline_plot.*.png")), [])

    def test_builds_the_configured_matlab_reference_style(self) -> None:
        """Keep labels, typography, ticks, colors, grid, and legend configurable."""

        import matplotlib.colors as mcolors
        import matplotlib.pyplot as plt
        from matplotlib.collections import LineCollection, PathCollection
        from matplotlib.ticker import FixedLocator, MultipleLocator

        with tempfile.TemporaryDirectory() as directory:
            figure, axis = _build_baseline_plot(
                self._network(Path(directory)), **self._style()
            )
            try:
                figure.canvas.draw()
                self.assertEqual(axis.get_title(), "Configured title")
                self.assertEqual(axis.get_xlabel(), "Configured date label")
                self.assertEqual(axis.get_ylabel(), "Configured baseline label")
                for text in (axis.title, axis.xaxis.label, axis.yaxis.label):
                    self.assertEqual(text.get_fontsize(), 18.0)
                    self.assertEqual(text.get_fontweight(), "bold")
                    self.assertEqual(text.get_fontfamily(), ["FreeSans"])
                self.assertTrue(
                    all(label.get_fontsize() == 13.0 for label in axis.get_xticklabels())
                )
                self.assertTrue(
                    all(label.get_fontsize() == 13.0 for label in axis.get_yticklabels())
                )
                self.assertTrue(
                    all(label.get_rotation() == 30.0 for label in axis.get_xticklabels())
                )
                self.assertIsInstance(axis.xaxis.get_major_locator(), FixedLocator)
                self.assertIsInstance(axis.yaxis.get_major_locator(), MultipleLocator)
                self.assertEqual(axis.xaxis.get_major_formatter().fmt, "%Y/%m")
                self.assertEqual(axis.get_facecolor(), mcolors.to_rgba("white"))

                lines = [
                    item for item in axis.collections if isinstance(item, LineCollection)
                ]
                points = [
                    item for item in axis.collections if isinstance(item, PathCollection)
                ]
                self.assertEqual(len(lines), 1)
                self.assertEqual(
                    tuple(lines[0].get_colors()[0]), mcolors.to_rgba("#112233")
                )
                self.assertEqual(len(points), 2)
                self.assertEqual(
                    tuple(points[0].get_facecolors()[0]), mcolors.to_rgba("#0000FF")
                )
                self.assertEqual(
                    tuple(points[1].get_facecolors()[0]), mcolors.to_rgba("#FF0000")
                )
                self.assertTrue(all(line.get_visible() for line in axis.get_xgridlines()))
                self.assertEqual(
                    mcolors.to_hex(axis.get_xgridlines()[0].get_color()).upper(),
                    "#D9D9D9",
                )
                first_x_tick = axis.xaxis.get_major_ticks()[0]
                first_y_tick = axis.yaxis.get_major_ticks()[0]
                self.assertTrue(first_x_tick.tick2line.get_visible())
                self.assertTrue(first_y_tick.tick2line.get_visible())
                legend = axis.get_legend()
                self.assertIsNotNone(legend)
                assert legend is not None
                self.assertEqual(
                    [text.get_text() for text in legend.get_texts()],
                    ["Configured pairs", "Configured slaves", "Configured reference"],
                )
                self.assertTrue(
                    all(text.get_fontsize() == 11.0 for text in legend.get_texts())
                )
                self.assertGreater(legend.get_bbox_to_anchor().x0, axis.bbox.x1)
            finally:
                plt.close(figure)

    def test_missing_configured_font_preserves_existing_output(self) -> None:
        """Reject silent font substitution before replacing a valid figure."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "baseline_plot.png"
            destination.write_bytes(b"existing-figure")
            style = self._style()
            style["font_family"] = "Definitely Missing Baseline Font"
            with self.assertRaisesRegex(ValueError, "Definitely Missing Baseline Font"):
                render_baseline_plot(
                    self._network(root), destination, dpi=90, **style
                )
            self.assertEqual(destination.read_bytes(), b"existing-figure")
            self.assertEqual(list(root.glob(".baseline_plot.*.png")), [])


if __name__ == "__main__":
    unittest.main()
