"""Compatibility tests for the package-owned deformation-map workflow."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from geodesy_visualization.workflows.insar import deformation_map as canonical
from geodesy_visualization.workflows.insar.deformation_map_plan import (
    compile_deformation_maps,
)


class DeformationMapWorkflowTests(unittest.TestCase):
    """Verify the package-owned workflow and its project-relative example."""

    def test_default_cli_and_cfg_location(self) -> None:
        """Resolve the migrated example cfg and its input/output paths."""
        expected = (
            REPOSITORY_ROOT
            / "config_examples"
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
        self.assertEqual(Path(cfg["output_dir"]), expected.parent / "result")

    def test_compiles_sbas_and_psi_into_visible_ordered_layer_plans(self) -> None:
        """Catch hidden renderer defaults or one dataset overwriting another plan."""
        cfg = canonical.load_config(str(canonical.DEFAULT_CONFIG))

        plans = compile_deformation_maps(cfg)

        self.assertEqual(len(plans), 2)
        self.assertEqual(
            [layer.handler for layer in plans[0].operations],
            [
                "deformation_basemap",
                "deformation_background",
                "deformation_data",
                "deformation_targets",
                "deformation_colorbar",
                "deformation_scale",
                "deformation_rose",
                "savefig",
            ],
        )
        self.assertEqual(plans[0].figure["dataset"], "sbas")
        self.assertEqual(plans[1].figure["dataset"], "psi")
        sbas_deformation = plans[0].operations[2].options
        psi_deformation = plans[1].operations[2].options
        self.assertEqual(sbas_deformation["mode"], "grd")
        self.assertEqual(psi_deformation["mode"], "scatter")
        self.assertEqual(sbas_deformation["grid"], cfg["sbas"]["grd_path"])
        self.assertEqual(psi_deformation["grid"], cfg["psi"]["grd_path"])
        self.assertEqual(sbas_deformation["cpt"], cfg["defo_cpt"])
        self.assertEqual(
            plans[0].operations[4].options["unit"],
            cfg["defo_colorbar_unit"],
        )
        self.assertEqual(
            plans[0].operations[5].options["map_scale"], cfg["map_scale"]
        )
        self.assertEqual(
            plans[0].operations[-1].options["fname"], cfg["sbas"]["output"]
        )
        self.assertEqual(
            plans[1].operations[-1].options["fname"], cfg["psi"]["output"]
        )

    def test_main_prepares_inputs_then_executes_each_compiled_plan(self) -> None:
        """Catch a regression back to the monolithic PyGMTPlotter render loop."""
        cfg = {
            "map_mode": "deformation",
            "output_dir": "/tmp/publication",
            "sbas": {"name": "sbas"},
            "psi": {"name": "psi"},
        }
        plans = (MagicMock(name="sbas_plan"), MagicMock(name="psi_plan"))
        executor = MagicMock()
        with (
            patch.object(canonical, "load_config", return_value=cfg),
            patch(
                "geodesy_visualization.grid_preparation.prepare_dataset_grid"
            ) as prepare,
            patch.object(canonical, "compile_deformation_maps", return_value=plans),
            patch.object(canonical, "FigureExecutor", return_value=executor) as factory,
        ):
            canonical.main(["--config", "/tmp/map.cfg"])

        self.assertEqual(
            prepare.call_args_list,
            [unittest.mock.call(cfg["sbas"]), unittest.mock.call(cfg["psi"])],
        )
        self.assertEqual(factory.call_count, 2)
        self.assertEqual(executor.execute_plan.call_count, 2)


if __name__ == "__main__":
    unittest.main()
