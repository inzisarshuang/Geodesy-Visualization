import unittest
from pathlib import Path

from geodesy_visualization.resources import resource_path, resource_root
from geodesy_visualization.styles import resolve_cpt_reference


class ResourceTests(unittest.TestCase):
    def test_checkout_resources_resolve_from_repository_root(self) -> None:
        self.assertEqual(resource_root(), Path(__file__).resolve().parents[1])
        self.assertTrue(resource_path("cpt").is_dir())
        self.assertTrue(
            resource_path(
                "config_examples", "deformation_map", "deformation_map.cfg"
            ).is_file()
        )

    def test_example_cpt_paths_reach_the_bundled_palettes(self) -> None:
        for workflow, key, palette in (
            ("deformation_map", "defo_cpt", "saga-01.cpt"),
            ("deformation_profile", "defo_cpt", "seismic.cpt"),
            ("timeseries_map", "cpt", "jet.cpt"),
        ):
            with self.subTest(workflow=workflow):
                cfg = resource_path("config_examples", workflow, f"{workflow}.cfg")
                value = next(
                    line.split("=", 1)[1].strip()
                    for line in cfg.read_text(encoding="utf-8").splitlines()
                    if line.startswith(f"{key} =")
                )
                resolved = Path(resolve_cpt_reference(value, cfg.parent))
                self.assertEqual(resolved, resource_path("cpt", palette))
                self.assertTrue(resolved.is_file())
