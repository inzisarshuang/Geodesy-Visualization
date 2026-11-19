"""Behavior tests for list-controlled visualization workflow batches."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from geodesy_visualization import cli
from geodesy_visualization.batch import load_job_list, run_job_batch


class JobListTests(unittest.TestCase):
    """Verify portable list parsing and failure-isolated batch execution."""

    def test_resolves_relative_paths_ignores_comments_and_preserves_duplicates(self) -> None:
        """Catch cwd-dependent paths or accidental de-duplication of requested jobs."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = root / "lists" / "figures.list"
            jobs.parent.mkdir()
            jobs.write_text(
                "# first publication group\n\n../a.cfg\n../b.cfg\n../a.cfg\n",
                encoding="utf-8",
            )

            loaded = load_job_list(jobs)

            self.assertEqual(
                loaded,
                (
                    (root / "a.cfg").resolve(),
                    (root / "b.cfg").resolve(),
                    (root / "a.cfg").resolve(),
                ),
            )

    def test_continues_after_failure_and_reports_every_job(self) -> None:
        """Catch one bad figure preventing later independent figures from running."""
        paths = tuple(Path(f"/tmp/{name}.cfg") for name in ("first", "bad", "last"))
        called: list[Path] = []

        def runner(path: Path) -> int:
            """Fail only the middle fixture while recording dispatch order."""
            called.append(path)
            if path.name == "bad.cfg":
                raise ValueError("invalid plot settings")
            return 0

        summary = run_job_batch(paths, runner)

        self.assertEqual(called, list(paths))
        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.succeeded, 2)
        self.assertEqual(summary.failed, 1)
        self.assertFalse(summary.ok)
        self.assertEqual(summary.results[1].path, paths[1])
        self.assertIn("invalid plot settings", summary.results[1].error or "")


class UnifiedBatchCliTests(unittest.TestCase):
    """Verify one consistent ``--config``/``--list`` public CLI contract."""

    def test_every_workflow_requires_exactly_one_config_source(self) -> None:
        """Catch ambiguous or missing job sources before importing a renderer."""
        workflows = (
            "study-area",
            "deformation-map",
            "deformation-profile",
            "timeseries-map",
            "timeseries-aux",
            "baseline_plot",
        )
        for workflow in workflows:
            parser = cli.build_parser()
            with self.subTest(workflow=workflow), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    parser.parse_args([workflow])
                with self.assertRaises(SystemExit):
                    parser.parse_args(
                        [workflow, "--config", "one.cfg", "--list", "jobs.list"]
                    )

    def test_list_dispatches_every_cfg_and_returns_nonzero_summary(self) -> None:
        """Catch a public batch command hiding failures or stopping before later jobs."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.cfg"
            second = root / "second.cfg"
            first.touch()
            second.touch()
            jobs = root / "jobs.list"
            jobs.write_text("first.cfg\nsecond.cfg\n", encoding="utf-8")
            output = io.StringIO()

            with patch(
                "geodesy_visualization.workflows.cartography.study_area.main",
                side_effect=[0, ValueError("bad second figure")],
            ) as workflow_main, redirect_stdout(output):
                status = cli.main(
                    ["study-area", "--list", str(jobs), "--dry-run"]
                )

            self.assertEqual(status, 1)
            self.assertEqual(
                workflow_main.call_args_list,
                [
                    unittest.mock.call(
                        ["--config", str(first.resolve()), "--dry-run"]
                    ),
                    unittest.mock.call(
                        ["--config", str(second.resolve()), "--dry-run"]
                    ),
                ],
            )
            report = output.getvalue()
            self.assertIn("Succeeded: 1", report)
            self.assertIn("Failed: 1", report)
            self.assertIn("bad second figure", report)


if __name__ == "__main__":
    unittest.main()
