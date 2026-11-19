"""Regression tests for cfg-driven spatial and auxiliary time-series readers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from geodesy_visualization.workflows.insar import timeseries_aux as auxiliary
from geodesy_visualization.workflows.insar import timeseries_map as spatial
from geodesy_visualization.workflows.insar.timeseries_map_plan import (
    compile_timeseries_map,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class SpatialTimeSeriesTests(unittest.TestCase):
    """Verify the plot-ready wide-table contract."""

    def test_default_cfg_is_migrated_example(self) -> None:
        """Use the package workflow and flattened example configuration."""
        parsed = spatial.build_parser().parse_args([])
        self.assertEqual(
            Path(parsed.config),
            REPOSITORY_ROOT / "config_examples" / "timeseries_map" / "timeseries_map.cfg",
        )

    def test_resolves_file_cpt_relative_to_config(self) -> None:
        """Resolve a shared CPT from the cfg directory, independent of cwd."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "map.cfg"
            config.write_text(
                "data_file = data.txt\n"
                "dates_file = dates.txt\n"
                "region_west = 0\nregion_east = 1\n"
                "region_south = 0\nregion_north = 1\n"
                "cpt = palette.cpt\nfont_bold = true\n",
                encoding="utf-8",
            )
            cfg = spatial.load_config(str(config))
            self.assertEqual(cfg["cpt"], str((root / "palette.cpt").resolve()))
            self.assertTrue(cfg["font_bold"])

    def test_selects_epochs_scales_and_preserves_missing_values(self) -> None:
        """Read only requested epochs and treat configured sentinels as missing."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dates = root / "images"
            dates.write_text(
                "epoch_index date_yyyymmdd\n1 20200101\n2 20200113\n3 20200125\n",
                encoding="utf-8",
            )
            table = root / "wide.txt"
            table.write_text(
                "longitude_deg latitude_deg epoch_001_deformation_20200101_mm "
                "epoch_002_deformation_20200113_mm "
                "epoch_003_deformation_20200125_mm\n"
                "10 20 1 2 3\n11 21 4 -9999 6\n",
                encoding="utf-8",
            )
            lon, lat, values, selected_dates = spatial.load_timeseries_table(
                str(table), str(dates), 2, 3, 10.0, 1, ["-9999"]
            )
        np.testing.assert_allclose(lon, [10, 11])
        np.testing.assert_allclose(lat, [20, 21])
        np.testing.assert_allclose(values[0], [20, 30])
        self.assertTrue(np.isnan(values[1, 0]))
        self.assertEqual(selected_dates, ["20200113", "20200125"])

    def test_processing_sources_are_rejected_at_config_boundary(self) -> None:
        """Keep canonical HDF5 conversion in envInSAR instead of envPlot."""
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "canonical.cfg"
            config.write_text(
                "data_source = canonical\ndata_file = values.h5\n"
                "dates_file = dates.txt\n"
                "region_west = 0\nregion_east = 1\n"
                "region_south = 0\nregion_north = 1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "data_source"):
                spatial.load_config(str(config))

    def test_compiles_selected_epochs_into_ordered_subplot_panels(self) -> None:
        """Catch wrong epoch order, coordinate edges, CPT, fonts, or colorbar geometry."""
        cfg = spatial.load_config(str(spatial.DEFAULT_CONFIG))
        epochs = spatial.load_timeseries_table(
            str(cfg["data_file"]),
            str(cfg["dates_file"]),
            int(cfg["start_epoch"]),
            int(cfg["end_epoch"]),
            float(cfg["scale"]),
            int(cfg["chunk_rows"]),
            list(cfg["nan_tokens"]),
        )

        with patch(
            "geodesy_visualization.workflows.insar.timeseries_map_plan._projected_panel_size",
            return_value=("400p", "260p"),
        ):
            plan = compile_timeseries_map(cfg, epochs)

        self.assertEqual(len(plan.panels), 12)
        self.assertEqual([panel.identifier for panel in plan.panels], list(range(12)))
        self.assertEqual(
            [layer.handler for layer in plan.panels[0].layers],
            ["timeseries_frame", "timeseries_background", "timeseries_epoch"],
        )
        self.assertFalse(plan.panels[0].layers[0].options["show_x"])
        self.assertTrue(plan.panels[0].layers[0].options["show_y"])
        self.assertTrue(plan.panels[8].layers[0].options["show_x"])
        self.assertEqual(
            plan.operations[0].options["series"],
            (cfg["bar_min"], cfg["bar_max"], cfg["bar_step"]),
        )
        self.assertEqual(plan.operations[0].options["title_font"], "26p,Helvetica-Bold,black")
        colorbar = plan.figure_layers[0].options
        self.assertEqual(colorbar["width"], cfg["colorbar_width"])
        self.assertEqual(colorbar["offset"], cfg["colorbar_offset"])
        self.assertEqual(
            plan.figure_layers[-1].options["fname"], cfg["output"]
        )
        self.assertEqual(plan.figure["epoch_range"], (1, 12))

    def test_main_reads_epochs_then_executes_the_compiled_subplot(self) -> None:
        """Catch production rendering bypassing the panel-plan executor."""
        cfg = {
            "data_file": "/tmp/data.txt",
            "dates_file": "/tmp/dates.txt",
            "start_epoch": 1,
            "end_epoch": 1,
            "scale": 1.0,
            "chunk_rows": 10,
            "nan_tokens": [],
            "output": "/tmp/out.png",
        }
        epochs = (
            np.asarray([1.0]),
            np.asarray([2.0]),
            np.asarray([[3.0]]),
            ["20200101"],
        )
        plan = MagicMock()
        executor = MagicMock()
        with (
            patch.object(spatial, "load_config", return_value=cfg),
            patch.object(spatial, "load_timeseries_table", return_value=epochs),
            patch.object(spatial, "compile_timeseries_map", return_value=plan) as compile_plan,
            patch.object(spatial, "FigureExecutor", return_value=executor),
        ):
            spatial.main(["--config", "/tmp/map.cfg"])

        compile_plan.assert_called_once_with(cfg, epochs)
        executor.execute_plan.assert_called_once_with()


class AuxiliaryTimeSeriesTests(unittest.TestCase):
    """Verify the auxiliary date/value table contract."""

    def test_default_cfg_is_flattened_example(self) -> None:
        """Keep the CLI bound to the current example directory."""
        parsed = auxiliary.build_parser().parse_args([])
        self.assertEqual(
            Path(parsed.config),
            REPOSITORY_ROOT / "config_examples" / "timeseries_aux" / "timeseries_aux.cfg",
        )

    def test_sorts_dates_and_rejects_duplicates(self) -> None:
        """Normalize unsorted input while rejecting ambiguous repeated dates."""
        with tempfile.TemporaryDirectory() as directory:
            table = Path(directory) / "series.txt"
            table.write_text(
                "date_yyyymmdd deformation_mm\n20200113 2\n20200101 1\n",
                encoding="utf-8",
            )
            result = auxiliary.read_date_value_table(str(table), "deformation_mm")
            self.assertEqual(result["value"].tolist(), [1, 2])
            table.write_text(
                "date_yyyymmdd deformation_mm\n20200101 1\n20200101 2\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                auxiliary.read_date_value_table(str(table), "deformation_mm")


if __name__ == "__main__":
    unittest.main()
