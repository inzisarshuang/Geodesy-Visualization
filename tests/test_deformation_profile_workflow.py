"""Compatibility tests for the package-owned deformation-profile workflow."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from geodesy_visualization.workflows.insar import deformation_profile as canonical


def load_legacy_workflow():
    """Load the compatibility script without requiring a package marker."""
    path = REPOSITORY_ROOT / "plot_defo_profile" / "plot_defo_dem_profile.py"
    specification = importlib.util.spec_from_file_location(
        "plot_defo_profile_test_module", path
    )
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


LEGACY = load_legacy_workflow()


class DeformationProfileWorkflowTests(unittest.TestCase):
    """Verify compatibility identity, cfg location, and shared track construction."""

    def test_legacy_script_reexports_complete_public_workflow(self) -> None:
        """Bind every compatibility name to the same canonical object."""
        self.assertEqual(LEGACY.__all__, canonical.__all__)
        for name in canonical.__all__:
            self.assertIs(getattr(LEGACY, name), getattr(canonical, name))

    def test_default_cfg_and_tracks_remain_unchanged(self) -> None:
        """Resolve the historical cfg and generate every named configured track."""
        expected = (
            REPOSITORY_ROOT / "plot_defo_profile" / "plot_defo_dem_profile.cfg"
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
