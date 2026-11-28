"""Compatibility tests for the package-owned deformation-map workflow."""

from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from geodesy_visualization.workflows.insar import deformation_map as canonical
from geodesy_visualization.workflows.insar.deformation_map_plan import (
    compile_deformation_maps,
)
from geodesy_visualization.figure_ops.deformation_layers import (
    render_deformation_basemap,
    render_deformation_grid,
    render_deformation_targets,
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

    def test_cfg_choices_control_map_layers(self) -> None:
        """Carry case-insensitive choices, Boolean aliases, and GMT settings to the plan."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "map.cfg"
            contents = (
                "map_mode = DeFoRMaTion\n"
                "sbas_input_path = deformation.txt\n"
                "sbas_input_type = TXT\n"
                "sbas_basemap_mode = DEM\n"
                "dem_tif = topography.tif\n"
                "sbas_defo_mode = SCATTER\n"
                "target_regions = A\n"
                "target_A_west = 0\ntarget_A_east = 1\n"
                "target_A_south = 0\ntarget_A_north = 1\n"
                "target_A_label_position = NE\n"
                "map_show_grid = Y\n"
                "map_frame_type = fancy-rounded\n"
                "map_frame_width = auto\n"
                "add_colorbar = N\n"
                "defo_colorbar_tick_interval = 0\n"
            )
            path.write_text(contents, encoding="utf-8")
            cfg = canonical.load_config(str(path))
            (plan,) = compile_deformation_maps(cfg)
            layers = {operation.handler: operation.options for operation in plan.operations}

            self.assertEqual(cfg["sbas"]["input_type"], "txt")
            frame = layers["deformation_basemap"]["map_frame"]
            self.assertEqual((frame["frame_type"], frame["frame_width"]), ("fancy-rounded", "auto"))
            self.assertEqual(layers["deformation_background"]["mode"], "dem")
            self.assertEqual(layers["deformation_data"]["mode"], "scatter")
            self.assertTrue(layers["deformation_grid"]["enabled"])
            self.assertEqual(layers["deformation_targets"]["targets"][0]["label_position"], "ne")
            self.assertFalse(layers["deformation_colorbar"]["enabled"])
            self.assertIsNone(layers["deformation_colorbar"]["tick_interval"])

            path.write_text(contents.replace("sbas_defo_mode = SCATTER", "sbas_defo_mode = auto"), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sbas_defo_mode"):
                canonical.load_config(str(path))

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
                "deformation_grid",
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
            plans[0].operations[5].options["unit"],
            cfg["defo_colorbar_unit"],
        )
        self.assertEqual(
            plans[0].operations[6].options["map_scale"], cfg["map_scale"]
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

    def test_coverage_basemap_honors_cfg_fonts_and_optional_axis_labels(self) -> None:
        """Keep font precedence and frame annotations configurable through the backend."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "coverage.cfg"
            path.write_text(
                """map_mode = coverage
optic_tif = optic.tif
coverage_kml = footprint.kml
gnss_kml = stations.kml
region_west = 12.8
region_east = 12.95
region_south = 49.11
region_north = 49.18
default_font_title = 26p,Helvetica-Bold
default_font_annot_primary = 12p,Helvetica
map_font_annot_primary = 19p,Helvetica-Bold
map_font_label = 15p,Helvetica-Bold
map_x_label = Longitude
map_show_grid = true
map_longitude_interval = 0.025
map_latitude_interval = 0.02
map_grid_pen = 1p,gray40
""",
                encoding="utf-8",
            )
            cfg = canonical.load_config(str(path))
        (plan,) = compile_deformation_maps(cfg)
        figure = MagicMock()
        context = SimpleNamespace(figure=figure)

        with patch("pygmt.config") as gmt_config:
            render_deformation_basemap(context, plan.operations[0])
            render_deformation_grid(context, plan.operations[2])

        gmt_config.assert_any_call(
            FONT_TITLE="26p,Helvetica-Bold",
            FONT_ANNOT_PRIMARY="19p,Helvetica-Bold",
            FONT_LABEL="15p,Helvetica-Bold",
        )
        self.assertFalse(
            any("FONT_ANNOT" in call.kwargs for call in gmt_config.call_args_list)
        )
        figure.text.assert_called_once_with(
            position="BC", text="Longitude", font="15p,Helvetica-Bold",
            justify="TC", offset="0c/-1c", no_clip=True,
        )
        self.assertEqual(figure.basemap.call_args_list[0].kwargs["frame"][0], "xa0.025f")
        self.assertEqual(figure.basemap.call_args.kwargs["frame"], ["+n", "xg0.025", "yg0.02"])
        gmt_config.assert_any_call(MAP_GRID_PEN_PRIMARY="1p,gray40")

    def test_target_layer_owns_ellipse_center_and_label_rendering(self) -> None:
        """Keep target annotations in the registered layer instead of the workflow."""
        figure = MagicMock()
        context = SimpleNamespace(figure=figure)
        operation = SimpleNamespace(
            section="figure.plot.targets.sbas",
            options={
                "targets": (
                    {
                        "west": 1.0,
                        "east": 3.0,
                        "south": 2.0,
                        "north": 4.0,
                        "label": "A",
                        "label_position": "top",
                    },
                ),
                "pen": "1p,black",
                "label_font": "10p,Helvetica",
                "label_offset": 0.1,
                "center_style": "c0.1c",
            },
        )

        render_deformation_targets(context, operation)

        self.assertEqual(figure.plot.call_count, 2)
        figure.text.assert_called_once_with(
            x=2.0,
            y=4.1,
            text="A",
            font="10p,Helvetica",
            justify="BC",
        )


if __name__ == "__main__":
    unittest.main()
