"""Regression tests for the cfg-driven spatial and auxiliary time-series readers."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from geodesy_visualization.workflows.insar import timeseries_aux as canonical_aux
from geodesy_visualization.workflows.insar import timeseries_map as canonical_map


def load_workflow(name: str, relative_path: str):
    """Load one workflow script without requiring it to be a Python package."""
    specification = importlib.util.spec_from_file_location(name, REPOSITORY_ROOT / relative_path)
    if specification is None or specification.loader is None:
        raise ImportError(relative_path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


SPATIAL = load_workflow(
    "plot_defo_timeseries_map_test_module",
    "plot_defo_timeseries_map/plot_defo_timeseries_map.py",
)
AUXILIARY = load_workflow(
    "plot_defo_timeseries_aux_test_module",
    "plot_defo_timeseries_aux/plot_defo_timeseries_aux.py",
)


class SpatialTimeSeriesTests(unittest.TestCase):
    def test_legacy_script_reexports_canonical_workflow(self) -> None:
        """Keep the old map script API and default cfg bound to the package workflow."""
        self.assertIs(SPATIAL.load_config, canonical_map.load_config)
        self.assertIs(SPATIAL.load_timeseries_table, canonical_map.load_timeseries_table)
        self.assertIs(SPATIAL.render, canonical_map.render)
        parsed = canonical_map.build_parser().parse_args([])
        self.assertEqual(
            Path(parsed.config),
            REPOSITORY_ROOT / "plot_defo_timeseries_map" / "plot_defo_timeseries_map.cfg",
        )

    def test_resolves_file_cpt_relative_to_config(self) -> None:
        """Resolve a shared CPT from the cfg directory, independent of cwd."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "map.cfg"
            config.write_text(
                "data_file = data.txt\n"
                "dates_file = dates.txt\n"
                "region_west = 0\n"
                "region_east = 1\n"
                "region_south = 0\n"
                "region_north = 1\n"
                "cpt = palette.cpt\n"
                "font_bold = true\n",
                encoding="utf-8",
            )
            cfg = SPATIAL.load_config(str(config))
            self.assertEqual(cfg["cpt"], str((root / "palette.cpt").resolve()))
            self.assertTrue(cfg["font_bold"])

    def test_selects_one_based_epochs_scales_and_preserves_missing_values(self) -> None:
        """Read only requested epochs and treat configured sentinels as missing."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dates = root / "images"
            dates.write_text(
                "epoch_index date_yyyymmdd\n"
                "1 20200101\n2 20200113\n3 20200125\n",
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
            lon, lat, values, selected_dates = SPATIAL.load_timeseries_table(
                str(table), str(dates), 2, 3, 10.0, 1, ["-9999"]
            )
        np.testing.assert_allclose(lon, [10, 11])
        np.testing.assert_allclose(lat, [20, 21])
        np.testing.assert_allclose(values[0], [20, 30])
        self.assertTrue(np.isnan(values[1, 0]))
        self.assertEqual(selected_dates, ["20200113", "20200125"])


class AuxiliaryTimeSeriesTests(unittest.TestCase):
    def test_legacy_script_reexports_canonical_workflow(self) -> None:
        """Keep the old script API and default cfg bound to the package workflow."""
        self.assertIs(AUXILIARY.load_config, canonical_aux.load_config)
        self.assertIs(AUXILIARY.read_date_value_table, canonical_aux.read_date_value_table)
        self.assertIs(AUXILIARY.render, canonical_aux.render)
        parsed = canonical_aux.build_parser().parse_args([])
        self.assertEqual(
            Path(parsed.config),
            REPOSITORY_ROOT / "plot_defo_timeseries_aux" / "plot_defo_timeseries_aux.cfg",
        )

    def test_sorts_dates_and_rejects_duplicates(self) -> None:
        """Normalize unsorted input while rejecting ambiguous repeated dates."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            table = root / "series.txt"
            table.write_text(
                "date_yyyymmdd deformation_mm\n20200113 2\n20200101 1\n",
                encoding="utf-8",
            )
            result = AUXILIARY.read_date_value_table(str(table), "deformation_mm")
            self.assertEqual(result["value"].tolist(), [1, 2])
            table.write_text(
                "date_yyyymmdd deformation_mm\n20200101 1\n20200101 2\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                AUXILIARY.read_date_value_table(str(table), "deformation_mm")


if __name__ == "__main__":
    unittest.main()
