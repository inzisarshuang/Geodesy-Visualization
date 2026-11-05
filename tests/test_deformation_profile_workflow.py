"""Compatibility tests for the package-owned deformation-profile workflow."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from geodesy_visualization.workflows.insar import deformation_profile as canonical


class DeformationProfileWorkflowTests(unittest.TestCase):
    """Verify the migrated cfg location and shared track construction."""

    def test_default_cfg_and_tracks(self) -> None:
        """Resolve the migrated cfg and generate every named configured track."""
        expected = (
            REPOSITORY_ROOT
            / "config_examples"
            / "visualization"
            / "deformation_profile"
            / "deformation_profile.cfg"
        )
        self.assertEqual(Path(canonical.build_parser().parse_args([]).config), expected)
        cfg = canonical.load_config(str(expected))
        tracks = canonical.build_tracks(cfg)
        self.assertEqual(list(tracks), cfg["track_names"])
        for name, start, end in zip(
            cfg["track_names"], cfg["track_start_coords"], cfg["track_end_coords"]
        ):
            self.assertEqual(tracks[name].shape, (cfg["num_points"], 2))
            self.assertEqual(tuple(tracks[name][0]), start)
            self.assertEqual(tuple(tracks[name][-1]), end)


if __name__ == "__main__":
    unittest.main()
