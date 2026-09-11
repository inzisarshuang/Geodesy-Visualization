"""Tests for bounded canonical-grid ingestion through the Adapter public API."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from insar_data_adapter import CanonicalGridWriter, GridMetadata
from geodesy_visualization.data import (
    iter_canonical_grid_blocks,
    load_canonical_grid_selection,
)


class CanonicalGridDataTests(unittest.TestCase):
    """Verify selection semantics, metadata checks, masks, and bounded row blocks."""

    def setUp(self) -> None:
        """Write one small, fully explicit canonical product for each test."""
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "canonical.h5"
        self.dates = ("20200101", "20200113", "20200125")
        self.x = np.arange(4, dtype=float) + 10.0
        self.y = np.arange(5, dtype=float)[::-1] + 20.0
        self.values = np.arange(60, dtype=np.float32).reshape(3, 5, 4)
        self.valid = np.ones((5, 4), dtype=bool)
        self.valid[1, 2] = False
        self.metadata = GridMetadata(
            source_format="synthetic",
            deformation_unit="mm",
            deformation_quantity="cumulative_displacement",
            los_positive="toward_satellite",
            crs="EPSG:4326",
            nodata_policy="valid_mask is authoritative; zero is valid",
            temporal_reference="20200101",
            spatial_reference="none",
            source_provenance="visualization consumer test",
        )
        with CanonicalGridWriter(
            self.path,
            self.dates,
            rows=5,
            columns=4,
            x=self.x,
            y=self.y,
            metadata=self.metadata,
            chunk_rows=2,
        ) as writer:
            writer.write_geometry_rows(0, np.ones((5, 4)), self.valid)
            for epoch_index, values in enumerate(self.values):
                writer.write_epoch(epoch_index, values)

    def test_selects_one_based_epochs_and_preserves_metadata(self) -> None:
        """Normalize one-based inclusive selection without loading displacement."""
        selection = load_canonical_grid_selection(
            self.path,
            start_epoch=2,
            end_epoch=3,
            expected_unit="mm",
            expected_crs="EPSG:4326",
        )
        self.assertEqual(selection.epoch_indices, (1, 2))
        self.assertEqual(selection.dates, self.dates[1:])
        self.assertEqual(selection.epoch_count, 3)
        self.assertEqual(selection.metadata, self.metadata)
        self.assertEqual(selection.metadata.grid_registration, "pixel")
        self.assertEqual(selection.metadata.los_positive, "toward_satellite")
        self.assertEqual(
            selection.metadata.nodata_policy,
            "valid_mask is authoritative; zero is valid",
        )
        np.testing.assert_array_equal(selection.x, self.x)
        np.testing.assert_array_equal(selection.y, self.y)
        self.assertFalse(selection.x.flags.writeable)
        self.assertFalse(selection.y.flags.writeable)

    def test_iterates_raw_values_and_mask_in_bounded_rows(self) -> None:
        """Read each selected epoch by bounded rows without applying its mask."""
        selection = load_canonical_grid_selection(self.path, 2, 3)
        blocks = list(iter_canonical_grid_blocks(selection, chunk_rows=2))
        self.assertEqual(len(blocks), 6)
        self.assertLessEqual(max(block.row_stop - block.row_start for block in blocks), 2)
        for offset, epoch_index in enumerate(selection.epoch_indices):
            epoch_blocks = [block for block in blocks if block.epoch_index == epoch_index]
            np.testing.assert_array_equal(
                np.vstack([block.values for block in epoch_blocks]),
                self.values[epoch_index],
            )
            np.testing.assert_array_equal(
                np.vstack([block.valid_mask for block in epoch_blocks]),
                self.valid,
            )
            self.assertEqual(epoch_blocks[0].date, selection.dates[offset])

    def test_rejects_ambiguous_selection_and_metadata(self) -> None:
        """Reject invalid one-based ranges, unit/CRS conflicts, and row ceilings."""
        with self.assertRaisesRegex(ValueError, "one-based inclusive"):
            load_canonical_grid_selection(self.path, 0, 2)
        with self.assertRaisesRegex(ValueError, "unit mismatch"):
            load_canonical_grid_selection(self.path, expected_unit="m")
        with self.assertRaisesRegex(ValueError, "CRS mismatch"):
            load_canonical_grid_selection(self.path, expected_crs="EPSG:32628")
        selection = load_canonical_grid_selection(self.path)
        with self.assertRaisesRegex(ValueError, "chunk_rows"):
            list(iter_canonical_grid_blocks(selection, chunk_rows=0))


if __name__ == "__main__":
    unittest.main()
