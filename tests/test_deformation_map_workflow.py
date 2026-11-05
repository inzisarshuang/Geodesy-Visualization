"""Compatibility tests for the package-owned deformation-map workflow."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from geodesy_visualization.workflows.insar import deformation_map as canonical


class DeformationMapWorkflowTests(unittest.TestCase):
    """Verify the package-owned workflow and its project-relative example."""

    def test_default_cli_and_cfg_location(self) -> None:
        """Resolve the migrated example cfg and its input/output paths."""
        expected = (
            REPOSITORY_ROOT
            / "config_examples"
            / "visualization"
            / "deformation_map"
            / "deformation_map.cfg"
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
