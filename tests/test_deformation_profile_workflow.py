"""Compatibility tests for the package-owned deformation-profile workflow."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from geodesy_visualization.workflows.insar import deformation_profile as canonical
from geodesy_visualization.workflows.insar.deformation_profile_plan import (
    compile_profile_figures,
)


class DeformationProfileWorkflowTests(unittest.TestCase):
    """Verify the migrated cfg location and shared track construction."""

    def test_default_cfg_and_tracks(self) -> None:
        """Resolve the migrated cfg and generate every named configured track."""
        expected = (
            REPOSITORY_ROOT
            / "config_examples"
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

    def test_compiles_maps_tracks_markers_and_each_profile_output(self) -> None:
        """Catch lost track order, styles, or outputs during layer-plan migration."""
        cfg = canonical.load_config(str(canonical.DEFAULT_CONFIG))
        tracks = canonical.build_tracks(cfg)
        profiles = {
            name: (
                np.asarray([[0.0, 0.01], [100.0, 0.02]]),
                np.asarray([[0.0, -0.01], [100.0, -0.02]]),
            )
            for name in tracks
        }

        plans = compile_profile_figures(cfg, tracks, profiles)

        self.assertEqual(len(plans), 2 + len(tracks) * 2)
        first_map = plans[0]
        self.assertEqual(
            [layer.handler for layer in first_map.operations],
            [
                "deformation_basemap",
                "deformation_background",
                "deformation_data",
                "profile_tracks",
                "profile_marker",
                "deformation_colorbar",
                "deformation_scale",
                "deformation_rose",
                "savefig",
            ],
        )
        self.assertEqual(
            list(first_map.operations[3].options["tracks"]), list(cfg["track_names"])
        )
        marker = first_map.operations[4].options
        self.assertEqual(marker["longitude"], cfg["marker_lon"])
        self.assertEqual(marker["latitude"], cfg["marker_lat"])
        self.assertEqual(marker["style"], cfg["marker_style"])
        self.assertEqual(first_map.operations[-1].options["fname"], cfg["dataset1"]["output_map"])

        first_profile = plans[2]
        self.assertEqual(
            [layer.handler for layer in first_profile.operations],
            ["profile_basemap", "profile_series", "profile_series", "profile_legend", "savefig"],
        )
        self.assertEqual(first_profile.operations[0].options["padding"], cfg["profile_padding"])
        self.assertEqual(first_profile.operations[1].options["pen"], cfg["dataset1"]["line_pen"])
        self.assertEqual(first_profile.operations[2].options["pen"], cfg["dataset2"]["line_pen"])

        outputs = [plan.operations[-1].options["fname"] for plan in plans]
        expected_profiles = [
            canonical.profile_output_path(cfg, name, mode)
            for name in tracks
            for mode in ("line", "scatter")
        ]
        self.assertEqual(outputs[:2], [cfg["dataset1"]["output_map"], cfg["dataset2"]["output_map"]])
        self.assertEqual(outputs[2:], expected_profiles)

    def test_main_prepares_samples_then_executes_all_compiled_figures(self) -> None:
        """Catch production orchestration bypassing profile FigurePlans."""
        cfg = {
            "output_dir": "/tmp/profile-output",
            "dataset1": {"name": "first"},
            "dataset2": {"name": "second"},
        }
        tracks = {"A": np.asarray([[0.0, 0.0], [1.0, 1.0]])}
        profiles = {"A": (np.asarray([[0.0, 1.0]]), np.asarray([[0.0, 2.0]]))}
        plans = (MagicMock(name="map"), MagicMock(name="profile"))
        executor = MagicMock()
        with (
            patch.object(canonical, "load_config", return_value=cfg),
            patch.object(canonical, "prepare_dataset_grid") as prepare,
            patch.object(canonical, "build_tracks", return_value=tracks),
            patch.object(canonical, "extract_profiles", return_value=profiles),
            patch.object(canonical, "compile_profile_figures", return_value=plans),
            patch.object(canonical, "FigureExecutor", return_value=executor) as factory,
        ):
            canonical.main(["--config", "/tmp/profile.cfg"])

        self.assertEqual(prepare.call_count, 2)
        self.assertEqual(factory.call_count, len(plans))
        self.assertEqual(executor.execute_plan.call_count, len(plans))


if __name__ == "__main__":
    unittest.main()
