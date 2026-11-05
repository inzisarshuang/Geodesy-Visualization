"""Method-root publication output tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from geodesy_visualization.project_layout import VisualizationProjectLayout
from geodesy_visualization.io import resolve_publication_output_dir


class VisualizationProjectLayoutTests(unittest.TestCase):
    def test_derives_publication_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layout = VisualizationProjectLayout.bind(
                root, "S1/ASCENDING_128", "S1/ASCENDING_128/GAMMA"
            )
            self.assertEqual(
                layout.publication("deformation_map"),
                root
                / "S1/ASCENDING_128/GAMMA/FIGURES/PUBLICATION/DEFORMATION_MAP",
            )

    def test_rejects_cross_case_method_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "processing_root"):
                VisualizationProjectLayout.bind(
                    directory,
                    "S1/ASCENDING_128",
                    "S1/DESCENDING_135/GAMMA",
                )

    def test_cfg_context_derives_default_and_explicit_output_wins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config/4visualization/map.cfg"
            config.parent.mkdir(parents=True)
            values = {
                "project_root": str(root),
                "project": "S1/ASCENDING_128",
                "processing_root": "S1/ASCENDING_128/GAMMA",
            }
            self.assertEqual(
                resolve_publication_output_dir(values, config, "deformation_map"),
                root
                / "S1/ASCENDING_128/GAMMA/FIGURES/PUBLICATION/DEFORMATION_MAP",
            )
            values["output_dir"] = "manual/figures"
            self.assertEqual(
                resolve_publication_output_dir(values, config, "deformation_map"),
                root / "S1/ASCENDING_128/manual/figures",
            )


if __name__ == "__main__":
    unittest.main()
