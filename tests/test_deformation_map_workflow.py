"""Compatibility tests for the package-owned deformation-map workflow."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from geodesy_visualization.workflows.insar import deformation_map as canonical


def load_legacy_workflow():
    """Load the compatibility script without requiring a package marker."""
    path = REPOSITORY_ROOT / "plot_defo_dem_optic" / "plot_defo_dem_optic.py"
    specification = importlib.util.spec_from_file_location(
        "plot_defo_dem_optic_test_module", path
    )
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


LEGACY = load_legacy_workflow()


class DeformationMapWorkflowTests(unittest.TestCase):
    """Verify the old entry path delegates to the package-owned implementation."""

    def test_legacy_script_reexports_complete_public_workflow(self) -> None:
        """Bind every compatibility name to the same canonical function object."""
        self.assertEqual(LEGACY.__all__, canonical.__all__)
        for name in canonical.__all__:
            self.assertIs(getattr(LEGACY, name), getattr(canonical, name))

    def test_default_cli_and_cfg_location_remain_unchanged(self) -> None:
        """Resolve the historical example cfg from both legacy and module entry paths."""
        expected = (
            REPOSITORY_ROOT
            / "plot_defo_dem_optic"
            / "plot_defo_dem_optic.cfg"
        )
        parsed = canonical.build_parser().parse_args([])
        self.assertEqual(Path(parsed.config), expected)
        cfg = canonical.load_config(str(expected))
        self.assertEqual(
            Path(cfg["sbas"]["input_path"]), expected.parent / "data/SBAS.tif"
        )
        self.assertEqual(
            Path(cfg["sbas"]["output"]), expected.parent / "result/SBAS.png"
        )


if __name__ == "__main__":
    unittest.main()
