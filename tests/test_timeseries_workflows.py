"""Regression tests for cfg-driven spatial and auxiliary time-series readers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from geodesy_visualization.workflows.insar import timeseries_aux as auxiliary
from geodesy_visualization.workflows.insar import timeseries_map as spatial


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
