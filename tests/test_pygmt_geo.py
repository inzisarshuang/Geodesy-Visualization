"""Tests for bounded-memory geospatial conversion and processing."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import rasterio
from insar_data_adapter import PointValueMetadata
from rasterio.transform import from_origin


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "lib"))

import pygmt_geo as legacy_geo
from lib import pygmt_geo as package_geo
from geodesy_visualization.geo import (
    extract_profile as canonical_extract_profile,
    generate_tracks as canonical_generate_tracks,
    region_from_grd as canonical_region_from_grd,
)
from geodesy_visualization import grid_preparation as canonical_grid_preparation
from pygmt_geo import add_tifs, defsour2grd, generate_tracks, tif2grd, txt2grd


class AddTifsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write_raster(self, name: str, data: np.ndarray, x_origin: float = 0.0) -> Path:
        path = self.root / name
        profile = {
            "driver": "GTiff",
            "width": data.shape[1],
            "height": data.shape[0],
            "count": 1,
            "dtype": "float32",
            "crs": "EPSG:4326",
            "transform": from_origin(x_origin, 2.0, 1.0, 1.0),
            "nodata": -9999.0,
        }
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(data.astype("float32"), 1)
        return path

    def test_mask_modes_have_distinct_documented_behavior(self) -> None:
        first = self.write_raster("first.tif", np.array([[1, -9999], [-9999, -9999]]))
        second = self.write_raster("second.tif", np.array([[2, 3], [4, -9999]]))

        any_output = self.root / "any.tif"
        with self.assertWarnsRegex(DeprecationWarning, "no production Visualization caller"):
            add_tifs(str(first), str(second), str(any_output), mask_any=True)
        with rasterio.open(any_output) as src:
            any_result = src.read(1)
        np.testing.assert_allclose(any_result[0, 0], 3.0)
        self.assertTrue(np.isnan(any_result[0, 1]))
        self.assertTrue(np.isnan(any_result[1, 0]))

        all_output = self.root / "all.tif"
        add_tifs(str(first), str(second), str(all_output), mask_any=False)
        with rasterio.open(all_output) as src:
            all_result = src.read(1)
        np.testing.assert_allclose(all_result[0, 1], 3.0)
        np.testing.assert_allclose(all_result[1, 0], 4.0)
        self.assertTrue(np.isnan(all_result[1, 1]))

    def test_rejects_misaligned_rasters_without_creating_output(self) -> None:
        first = self.write_raster("first.tif", np.ones((2, 2)))
        second = self.write_raster("second.tif", np.ones((2, 2)), x_origin=1.0)
        output = self.root / "output.tif"

        with self.assertRaisesRegex(ValueError, "transform"):
            add_tifs(str(first), str(second), str(output))

        self.assertFalse(output.exists())


class TrackTests(unittest.TestCase):
    def test_transitional_module_reexports_grid_preparation(self) -> None:
        """Keep legacy preparation names bound to their canonical package functions."""
        for name in canonical_grid_preparation.__all__:
            self.assertIs(getattr(package_geo, name), getattr(canonical_grid_preparation, name))
        self.assertIs(package_geo.region_from_grd, canonical_region_from_grd)

    def test_legacy_module_reexports_canonical_view_functions(self) -> None:
        """Keep all three old geo imports bound to the canonical package functions."""
        self.assertIs(legacy_geo.extract_profile, canonical_extract_profile)
        self.assertIs(legacy_geo.generate_tracks, canonical_generate_tracks)
        self.assertIs(legacy_geo.region_from_grd, canonical_region_from_grd)

    def test_generates_named_tracks(self) -> None:
        """Generate the requested number of points under the requested track name."""
        tracks = generate_tracks(
            start_coords=[(0.0, 1.0)],
            end_coords=[(2.0, 3.0)],
            num_points=3,
            pointnames=["A"],
        )
        np.testing.assert_allclose(tracks["A"], [[0, 1], [1, 2], [2, 3]])

    def test_rejects_silent_zip_truncation_and_duplicate_names(self) -> None:
        """Reject mismatched coordinate lists and ambiguous duplicate names."""
        with self.assertRaisesRegex(ValueError, "same length"):
            generate_tracks([(0, 0)], [], num_points=3)
        with self.assertRaisesRegex(ValueError, "unique"):
            generate_tracks(
                [(0, 0), (1, 1)], [(1, 1), (2, 2)], num_points=3, pointnames=["A", "A"]
            )


class GridConversionTests(unittest.TestCase):
    def setUp(self) -> None:
        """Create one isolated directory for generated conversion products."""
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_converts_tif_through_adapter(self) -> None:
        """Convert a raster through Adapter without leaving temporary files behind."""
        tif_path = self.root / "input.tif"
        with rasterio.open(
            tif_path,
            "w",
            driver="GTiff",
            width=2,
            height=2,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=from_origin(10.0, 12.0, 1.0, 1.0),
            nodata=-9999.0,
        ) as dst:
            dst.write(np.array([[1.0, 2.0], [3.0, -9999.0]], dtype="float32"), 1)

        tif_grid = self.root / "from_tif.grd"
        region = tif2grd(str(tif_path), str(tif_grid), scale=2.0, nan_to_zero=False)
        self.assertEqual(region, [10.0, 12.0, 10.0, 12.0])
        self.assertTrue(tif_grid.is_file())

    def test_converts_headered_text_by_chunks(self) -> None:
        """Convert a headered point table without leaving temporary files behind."""

        text_path = self.root / "points.txt"
        text_path.write_text("lon lat value\n0 0 1\n1 0 2\n0 1 3\n1 1 4\n", encoding="utf-8")
        text_grid = self.root / "from_text.grd"
        text_region = txt2grd(
            str(text_path), str(text_grid), scale=0.5, space=1.0, chunk_rows=2
        )
        self.assertEqual(text_region, [0.0, 1.0, 0.0, 1.0])
        self.assertTrue(text_grid.is_file())
        self.assertEqual(list(self.root.glob(".pygmt_*")), [])

    def test_converts_headerless_projected_defsour_fourth_column(self) -> None:
        """Transform Defsour UTM coordinates and select deformation rather than elevation."""
        source = self.root / "D20200101"
        source.write_text(
            "166021.443 0.000 123.000 4.500000\n"
            "277404.560 110597.973 456.000 -2.000000\n",
            encoding="utf-8",
        )
        output = self.root / "defsour.grd"

        def fake_xyz2grd(*, data, region, spacing, outgrid):
            """Capture the generated geographic XYZ table and emulate GMT output."""
            generated = pd.read_csv(data, sep=r"\s+", header=None)
            self.assertTrue(np.allclose(generated.iloc[:, 2], [4.5, -2.0]))
            self.assertTrue(np.allclose(generated.iloc[:, 0], [0.0, 0.999697], atol=1.0e-4))
            self.assertTrue(np.allclose(generated.iloc[:, 1], [0.0, 1.0], atol=1.0e-4))
            Path(outgrid).write_bytes(b"grid")

        with patch(
            "geodesy_visualization.grid_preparation.pygmt.xyz2grd",
            side_effect=fake_xyz2grd,
        ):
            region = defsour2grd(
                str(source), str(output), "EPSG:32631", space=0.5, chunk_rows=1
            )
        self.assertTrue(np.allclose(region, [-7.3e-10, 0.9999999993, 0.0, 1.0], atol=1.0e-6))
        self.assertTrue(output.is_file())
        self.assertEqual(list(self.root.glob(".pygmt_*")), [])

    def test_converts_named_headered_points_through_adapter(self) -> None:
        """Delegate named non-positional TXT roles while preserving display scaling."""
        source = self.root / "named_points.txt"
        source.write_text(
            "id lat velocity lon quality\n"
            "1 10.0 4.0 20.0 0.9\n"
            "2 11.0 -2.0 21.0 0.8\n",
            encoding="utf-8",
        )
        output = self.root / "named_points.grd"
        metadata = PointValueMetadata(
            source_format="headered_text_points",
            value_unit="cm/yr",
            value_quantity="velocity",
            los_positive="toward_satellite",
            crs="EPSG:4326",
            nodata_policy="NaN is nodata; zero is valid",
            temporal_reference="source velocity interval",
            spatial_reference="none",
            source_provenance=str(source),
        )

        def fake_xyz2grd(*, data, region, spacing, outgrid):
            """Verify named roles and scaling, then emulate one GMT output."""
            generated = pd.read_csv(data, sep=r"\s+", header=None)
            np.testing.assert_allclose(generated.iloc[:, 0], [20.0, 21.0])
            np.testing.assert_allclose(generated.iloc[:, 1], [10.0, 11.0])
            np.testing.assert_allclose(generated.iloc[:, 2], [0.04, -0.02])
            Path(outgrid).write_bytes(b"grid")

        with patch(
            "geodesy_visualization.grid_preparation.pygmt.xyz2grd",
            side_effect=fake_xyz2grd,
        ):
            region = txt2grd(
                str(source),
                str(output),
                scale=0.01,
                space=0.5,
                chunk_rows=1,
                value_column="velocity",
                metadata=metadata,
            )
        self.assertEqual(region, [20.0, 21.0, 10.0, 11.0])
        self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
