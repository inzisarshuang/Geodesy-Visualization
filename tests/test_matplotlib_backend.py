from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from geodesy_visualization.backends.matplotlib import (
    plot_array_cube,
    plot_insar_gnss_comparison,
    plot_multitrack_timeseries,
    plot_target_timeseries,
)
from geodesy_visualization.io import atomic_output_path


class AtomicOutputPathTests(unittest.TestCase):
    """Verify successful publication and failed-write cleanup."""

    def test_failure_preserves_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "figure.png"
            destination.write_bytes(b"existing")
            with self.assertRaisesRegex(RuntimeError, "stop"):
                with atomic_output_path(destination) as temporary:
                    temporary.write_bytes(b"partial")
                    raise RuntimeError("stop")
            self.assertEqual(destination.read_bytes(), b"existing")
            self.assertEqual(list(destination.parent.glob(".figure.*.png")), [])


class MatplotlibBackendTests(unittest.TestCase):
    """Verify the engine-neutral Matplotlib plotting contracts."""

    def test_array_cube_preserves_panel_order_limits_and_mask(self) -> None:
        cube = np.dstack(
            (
                np.array([[0.0, 1.0], [np.nan, 3.0]]),
                np.array([[4.0, 5.0], [6.0, 7.0]]),
            )
        )
        figure, axes, colorbars = plot_array_cube(
            cube,
            limits=[0.0, 7.0],
            colorbars=True,
            tick_labels=False,
            layout=(1, 3),
            panel_positions=(1, 3),
            titles=("first", "second"),
        )
        try:
            self.assertEqual([axis.get_title() for axis in axes], ["first", "second"])
            self.assertEqual(len(colorbars), 2)
            self.assertEqual(tuple(axes[0].images[0].get_clim()), (0.0, 7.0))
            self.assertTrue(np.ma.getmaskarray(axes[0].images[0].get_array())[1, 0])
        finally:
            plt.close(figure)

    def test_series_protocol_does_not_require_analysis_package(self) -> None:
        first = SimpleNamespace(
            dates=("20240101", "20240113"),
            values={"P1": np.array([0.0, 2.0]), "P2": np.array([1.0, -1.0])},
            unit="mm",
        )
        second = SimpleNamespace(
            dates=("20240107", "20240119"),
            values={"P1": np.array([0.0, 1.0]), "P2": np.array([0.5, -0.5])},
            unit="mm",
        )
        target_figure, target_axes = plot_target_timeseries(first, columns=2)
        track_figure, track_axes = plot_multitrack_timeseries(
            {"ASC": first, "DES": second}, columns=2
        )
        try:
            self.assertEqual([axis.get_title() for axis in target_axes], ["P1", "P2"])
            self.assertEqual([len(axis.lines) for axis in track_axes], [2, 2])
            self.assertEqual(track_axes[0].get_legend_handles_labels()[1], ["ASC", "DES"])
        finally:
            plt.close(target_figure)
            plt.close(track_figure)

    def test_bundled_font_and_comparison_marker_semantics(self) -> None:
        figure, axis = plot_insar_gnss_comparison(
            ["20240101", "20240113"],
            [0.0, 2.0],
            ["20240101", "20240107", "20240113"],
            [0.0, 1.0, 2.0],
            insar_marker="s",
            gnss_marker="D",
        )
        try:
            bundled = (REPOSITORY_ROOT / "fonts").resolve()
            registered = {
                Path(entry.fname).resolve()
                for entry in font_manager.fontManager.ttflist
                if Path(entry.fname).is_file()
            }
            self.assertTrue(any(bundled in path.parents for path in registered))
            self.assertEqual([line.get_linestyle() for line in axis.lines], ["None", "None"])
            self.assertEqual([line.get_marker() for line in axis.lines], ["s", "D"])
            self.assertEqual(axis.title.get_fontfamily(), ["TeX Gyre Heros"])
        finally:
            plt.close(figure)


if __name__ == "__main__":
    unittest.main()
