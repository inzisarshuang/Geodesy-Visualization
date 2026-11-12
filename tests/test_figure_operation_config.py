"""Contract tests for ordered PyGMT figure-operation configurations."""

from __future__ import annotations

import configparser
import tempfile
import textwrap
import unittest
from pathlib import Path

from geodesy_visualization.figure_ops.config import load_figure_plan


class FigureOperationConfigTests(unittest.TestCase):
    """Verify strict parsing of ordered ``figure.*`` operation sections."""

    def write_cfg(self, directory: Path, content: str) -> Path:
        """Write one dedented configuration fixture and return its path."""
        path = directory / "study_area.cfg"
        path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
        return path

    def test_preserves_operation_order_semantics_paths_and_types(self) -> None:
        """Compile human-readable sections into one typed ordered figure plan."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data/dem.grd").touch()
            (root / "data/reference.kml").touch()
            cfg = self.write_cfg(
                root,
                """
                [project]
                processing_root = .

                [figure]
                layout = publication_sidecar

                [figure.basemap]
                region = 102, 103.6, 35.2, 36.5
                projection = M8i
                title = Study Area Jishishan

                [figure.grdimage.dem]
                grid = data/dem.grd
                cmap = gray
                shading = +d

                [figure.plot.footprint.reference]
                data = data/reference.kml
                pen = 4p,red
                label = LT-1 reference image
                transparency = 15

                [figure.meca.mainshock]
                longitude = 102.79
                latitude = 35.758
                strike = 353
                dip = 78
                rake = -124
                magnitude = 5.9
                depth_km = 18.281
                scale = 0.6c

                [figure.scalebar]
                enabled = yes
                position = BR
                length = 50k
                fancy = yes

                [figure.colorbar.dem]
                source = figure.grdimage.dem
                position = BC
                label = Elevation
                unit = m

                [figure.savefig]
                fname = result/study_area.png
                dpi = 300
                crop = yes
                """,
            )

            plan = load_figure_plan(cfg)

            self.assertEqual(plan.config_path, cfg.resolve())
            self.assertEqual(plan.figure["layout"], "publication_sidecar")
            self.assertEqual(
                [operation.section for operation in plan.operations],
                [
                    "figure.basemap",
                    "figure.grdimage.dem",
                    "figure.plot.footprint.reference",
                    "figure.meca.mainshock",
                    "figure.scalebar",
                    "figure.colorbar.dem",
                    "figure.savefig",
                ],
            )
            footprint = plan.operations[2]
            self.assertEqual(footprint.method, "plot")
            self.assertEqual(footprint.semantics, ("footprint", "reference"))
            self.assertEqual(
                footprint.options["data"], str((root / "data/reference.kml").resolve())
            )
            self.assertEqual(footprint.options["transparency"], 15.0)
            self.assertIs(plan.operations[4].options["enabled"], True)
            self.assertIs(plan.operations[4].options["fancy"], True)
            self.assertEqual(plan.operations[-1].options["dpi"], 300)
            self.assertIs(plan.operations[-1].options["crop"], True)
            self.assertEqual(
                plan.operations[-1].options["fname"],
                str((root / "result/study_area.png").resolve()),
            )

    def test_rejects_duplicate_sections(self) -> None:
        """Reject an ambiguous chain containing the same operation identifier twice."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.write_cfg(
                Path(tmp),
                """
                [figure]
                layout = publication_sidecar
                [figure.basemap]
                region = 0, 1, 0, 1
                projection = M8c
                [figure.basemap]
                region = 0, 2, 0, 2
                projection = M8c
                """,
            )
            with self.assertRaises(configparser.DuplicateSectionError):
                load_figure_plan(cfg)

    def test_rejects_unknown_key_with_section_name(self) -> None:
        """Reject misspelled PyGMT parameters instead of silently ignoring them."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.write_cfg(
                Path(tmp),
                """
                [figure]
                layout = publication_sidecar
                [figure.basemap]
                region = 0, 1, 0, 1
                projection = M8c
                projction = M9c
                """,
            )
            with self.assertRaisesRegex(ValueError, r"figure\.basemap.*projction"):
                load_figure_plan(cfg)

    def test_rejects_deprecated_coverage_section(self) -> None:
        """Keep ``footprint`` as the only accepted spatial-footprint term."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.write_cfg(
                Path(tmp),
                """
                [figure]
                layout = publication_sidecar
                [figure.plot.coverage.reference]
                data = reference.kml
                pen = 2p,red
                """,
            )
            with self.assertRaisesRegex(ValueError, r"coverage.*footprint"):
                load_figure_plan(cfg)

    def test_rejects_missing_source_reference(self) -> None:
        """Reject a colorbar that names no configured raster operation."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.write_cfg(
                Path(tmp),
                """
                [figure]
                layout = publication_sidecar
                [figure.colorbar.dem]
                source = figure.grdimage.dem
                position = BC
                """,
            )
            with self.assertRaisesRegex(ValueError, r"figure\.colorbar\.dem.*source"):
                load_figure_plan(cfg)

    def test_accepts_forward_source_reference_after_complete_parse(self) -> None:
        """Resolve a source identifier after all configured sections are known."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dem.grd").touch()
            cfg = self.write_cfg(
                root,
                """
                [figure]
                layout = publication_sidecar
                [figure.colorbar.dem]
                source = figure.grdimage.dem
                position = BC
                [figure.grdimage.dem]
                grid = dem.grd
                cmap = gray
                """,
            )
            plan = load_figure_plan(cfg)
            self.assertEqual(plan.operations[0].options["source"], "figure.grdimage.dem")


if __name__ == "__main__":
    unittest.main()
