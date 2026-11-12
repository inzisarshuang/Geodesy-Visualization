"""Tests for study-area footprint and fault input preparation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from geodesy_visualization.figure_ops.cartography_inputs import (
    classify_fault_kinematics,
    parse_kml_footprints,
    read_fault_features,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "study_area"


class FootprintInputTests(unittest.TestCase):
    """Verify KML footprint parsing without an optional GDAL KML driver."""

    def test_parses_and_closes_one_polygon(self) -> None:
        """Return an explicitly closed longitude/latitude array."""
        polygons = parse_kml_footprints(FIXTURES / "reference_footprint.kml")
        self.assertEqual(len(polygons), 1)
        self.assertEqual(polygons[0].shape, (5, 2))
        np.testing.assert_allclose(polygons[0][0], polygons[0][-1])

    def test_parses_every_polygon_inside_multigeometry(self) -> None:
        """Preserve both slave footprints from one KML MultiGeometry."""
        polygons = parse_kml_footprints(FIXTURES / "slave_footprints.kml")
        self.assertEqual(len(polygons), 2)
        self.assertTrue(all(polygon.shape == (5, 2) for polygon in polygons))

    def test_rejects_empty_or_malformed_coordinates(self) -> None:
        """Fail clearly instead of silently dropping an invalid configured footprint."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            empty = root / "empty.kml"
            empty.write_text(
                "<kml><Polygon><coordinates>  </coordinates></Polygon></kml>",
                encoding="utf-8",
            )
            malformed = root / "malformed.kml"
            malformed.write_text(
                "<kml><Polygon><coordinates>102,35 invalid 103,36</coordinates></Polygon></kml>",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "no non-empty Polygon"):
                parse_kml_footprints(empty)
            with self.assertRaisesRegex(ValueError, "malformed coordinate"):
                parse_kml_footprints(malformed)


class FaultInputTests(unittest.TestCase):
    """Verify GDAL-backed line extraction and deterministic fault classification."""

    def test_flattens_line_and_multiline_features(self) -> None:
        """Convert each line member into an independent drawable fault feature."""
        features = read_fault_features(FIXTURES / "faults.geojson", "Fea_En")
        self.assertEqual(len(features), 3)
        self.assertEqual(features[0].coordinates.shape, (3, 2))
        self.assertEqual(features[0].kinematics, "reverse")
        self.assertEqual(features[1].kinematics, "left lateral reverse fault")
        self.assertEqual(features[2].kinematics, "left lateral reverse fault")

    def test_rejects_missing_kinematic_field(self) -> None:
        """Require the configured scientific classification field on every feature."""
        with self.assertRaisesRegex(ValueError, "MissingField.*kinematic field"):
            read_fault_features(FIXTURES / "faults.geojson", "MissingField")

    def test_classification_prioritizes_strike_slip_and_has_fallback(self) -> None:
        """Classify oblique faults consistently before reverse or normal matches."""
        self.assertEqual(
            classify_fault_kinematics("left lateral reverse fault"), "strike_slip"
        )
        self.assertEqual(classify_fault_kinematics("right lateral"), "strike_slip")
        self.assertEqual(classify_fault_kinematics("thrust fault"), "reverse")
        self.assertEqual(classify_fault_kinematics("normal fault"), "normal")
        self.assertEqual(classify_fault_kinematics("unknown"), "other")


if __name__ == "__main__":
    unittest.main()
