"""Tests for the public configuration-driven study-area workflow."""

from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from geodesy_visualization import cli
from geodesy_visualization.workflows.cartography import study_area


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = (
    REPOSITORY_ROOT
    / "config_examples"
    / "visualization"
    / "study_area"
    / "study_area.cfg"
)


class StudyAreaWorkflowTests(unittest.TestCase):
    """Verify the example, direct workflow, and unified CLI contract."""

    def test_documented_example_loads_in_expected_order(self) -> None:
        """Resolve the distributable CFG and every text fixture from its directory."""
        plan = study_area.load_plan(str(EXAMPLE))
        self.assertEqual(
            [operation.section for operation in plan.operations],
            [
                "figure.basemap",
                "figure.grdimage.dem",
                "figure.plot.faults",
                "figure.plot.footprint.reference",
                "figure.plot.footprint.slaves",
                "figure.meca.mainshock",
                "figure.scalebar",
                "figure.directional_rose",
                "figure.colorbar.dem",
                "figure.inset.globe",
                "figure.inset.regional",
                "figure.legend",
                "figure.savefig",
            ],
        )
        by_section = {operation.section: operation for operation in plan.operations}
        self.assertEqual(
            by_section["figure.plot.footprint.reference"].options["data"],
            str((EXAMPLE.parent / "data/reference_footprint.kml").resolve()),
        )
        self.assertEqual(
            by_section["figure.grdimage.dem"].options["grid"],
            str((EXAMPLE.parent / "../deformation_map/data/dem.tif").resolve()),
        )

    def test_dry_run_prints_order_and_does_not_create_executor(self) -> None:
        """Validate and report a plan without importing PyGMT or creating a Figure."""
        output = io.StringIO()
        with patch.object(study_area, "FigureExecutor") as executor:
            with contextlib.redirect_stdout(output):
                status = study_area.main(["--config", str(EXAMPLE), "--dry-run"])
        self.assertEqual(status, 0)
        executor.assert_not_called()
        report = output.getvalue()
        self.assertIn("figure.basemap", report)
        self.assertIn("figure.plot.footprint.reference", report)
        self.assertIn("figure.savefig", report)
        self.assertIn("study_area.png", report)

    def test_normal_execution_delegates_once_to_executor(self) -> None:
        """Keep workflow orchestration separate from rendering implementation."""
        with patch.object(study_area, "FigureExecutor") as executor_class:
            executor = executor_class.return_value
            status = study_area.main(["--config", str(EXAMPLE)])
        self.assertEqual(status, 0)
        executor_class.assert_called_once()
        executor.execute.assert_called_once_with()

    def test_unified_cli_exposes_and_lazily_dispatches_study_area(self) -> None:
        """Route the new command without changing the existing lazy-import design."""
        parser = cli.build_parser()
        parsed = parser.parse_args(["study-area", "--config", str(EXAMPLE), "--dry-run"])
        self.assertEqual(parsed.workflow, "study-area")
        with patch.object(study_area, "main", return_value=0) as workflow_main:
            status = cli.main(["study-area", "--config", str(EXAMPLE), "--dry-run"])
        self.assertEqual(status, 0)
        workflow_main.assert_called_once_with(["--config", str(EXAMPLE), "--dry-run"])


if __name__ == "__main__":
    unittest.main()
