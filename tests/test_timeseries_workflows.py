"""Regression tests for the cfg-driven spatial and auxiliary time-series readers."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from geodesy_visualization.workflows.insar import timeseries_aux as canonical_aux
from geodesy_visualization.workflows.insar import timeseries_map as canonical_map
from insar_data_adapter import CanonicalGridWriter, GridMetadata


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
        self.assertIs(SPATIAL.render_canonical, canonical_map.render_canonical)
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

    def test_canonical_source_streams_masked_rows_without_dates_table(self) -> None:
        """Route canonical cfg input through bounded blocks and preserve its mask."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            product = root / "canonical.h5"
            metadata = GridMetadata(
                source_format="synthetic",
                deformation_unit="mm",
                deformation_quantity="cumulative_displacement",
                los_positive="toward_satellite",
                crs="EPSG:4326",
                nodata_policy="valid_mask is authoritative; zero is valid",
                temporal_reference="20200101",
                spatial_reference="none",
                source_provenance="timeseries map test",
            )
            valid = np.ones((3, 2), dtype=bool)
            valid[1, 1] = False
            values = np.arange(12, dtype=np.float32).reshape(2, 3, 2)
            with CanonicalGridWriter(
                product,
                ("20200101", "20200113"),
                rows=3,
                columns=2,
                x=(10.0, 11.0),
                y=(22.0, 21.0, 20.0),
                metadata=metadata,
                chunk_rows=1,
            ) as writer:
                writer.write_geometry_rows(0, np.ones((3, 2)), valid)
                writer.write_epoch(0, values[0])
                writer.write_epoch(1, values[1])
            config = root / "canonical.cfg"
            config.write_text(
                "data_source = canonical\n"
                "data_file = canonical.h5\n"
                "canonical_unit = mm\n"
                "canonical_crs = EPSG:4326\n"
                "region_west = 9\nregion_east = 12\n"
                "region_south = 19\nregion_north = 23\n"
                "subplot_rows = 1\nsubplot_columns = 2\n"
                "start_epoch = 1\nend_epoch = 2\n"
                "data_scale = 2\nchunk_rows = 1\n",
                encoding="utf-8",
            )
            cfg = canonical_map.load_config(str(config))
            self.assertEqual(cfg["data_source"], "canonical")
            self.assertEqual(cfg["dates_file"], "")
            selection = canonical_map.load_canonical_grid_selection(
                str(cfg["data_file"]),
                int(cfg["start_epoch"]),
                int(cfg["end_epoch"]),
                expected_unit=str(cfg["canonical_unit"]),
                expected_crs=str(cfg["canonical_crs"]),
            )
            calls: list[dict[str, object]] = []

            class RecordingFigure:
                """Capture bounded scatter calls without starting GMT."""

                def plot(self, **kwargs: object) -> None:
                    """Retain one scatter batch for numerical assertions."""
                    calls.append(kwargs)

            def fake_render_panels(cfg_value, dates, draw_data):
                """Invoke the real canonical data callback for every fake panel."""
                figure = RecordingFigure()
                for index in range(len(dates)):
                    draw_data(figure, index)
                return Path(str(cfg_value["output"]))

            with mock.patch.object(
                canonical_map, "_render_panels", side_effect=fake_render_panels
            ):
                destination = canonical_map.render_canonical(cfg, selection)

        self.assertEqual(destination, Path(str(cfg["output"])))
        self.assertEqual(len(calls), 6)
        first_epoch = calls[:3]
        np.testing.assert_allclose(
            np.concatenate([call["fill"] for call in first_epoch]),
            np.array([0, 1, 2, 4, 5], dtype=float) * 2,
        )
        np.testing.assert_allclose(
            np.concatenate([call["x"] for call in first_epoch]),
            [10, 11, 10, 10, 11],
        )
        np.testing.assert_allclose(
            np.concatenate([call["y"] for call in first_epoch]),
            [22, 22, 21, 20, 20],
        )

    def test_table_source_still_requires_dates_file(self) -> None:
        """Keep the legacy table contract strict while canonical owns its dates."""
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "missing_dates.cfg"
            config.write_text(
                "data_source = table\ndata_file = values.txt\n"
                "region_west = 0\nregion_east = 1\n"
                "region_south = 0\nregion_north = 1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "dates_file is required"):
                canonical_map.load_config(str(config))

    def test_canonical_scatter_rejects_projected_crs(self) -> None:
        """Reject projected axes because this workflow does not reproject them."""
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "projected.cfg"
            config.write_text(
                "data_source = canonical\ndata_file = values.h5\n"
                "canonical_crs = EPSG:32628\n"
                "region_west = 0\nregion_east = 1\n"
                "region_south = 0\nregion_north = 1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "geographic CRS"):
                canonical_map.load_config(str(config))


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
