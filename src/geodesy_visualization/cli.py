"""geodesy_visualization.cli
===========================

功能概述:
    提供 Geodesy-Visualization 的统一 workflow 编排入口，将地图、剖面、
    时序和基线图统一为同一个配置驱动命令。

函数说明:
    ``build_parser``:
        构建统一 workflow 子命令解析器。
    ``main``:
        根据子命令分派到正式 workflow 入口。
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from geodesy_visualization.batch import BatchSummary, load_job_list, run_job_batch

def build_parser() -> argparse.ArgumentParser:
    """Build the unified configuration-driven visualization CLI."""
    parser = argparse.ArgumentParser(prog="geodesy-visualization")
    subparsers = parser.add_subparsers(dest="workflow", required=True)
    for name, description in (
        ("study-area", "Render study-area maps with ordered PyGMT figure operations."),
        ("deformation-map", "Render deformation maps over DEM or optical basemaps."),
        ("deformation-profile", "Render deformation maps and profile comparisons."),
        ("timeseries-map", "Render geographic time-series panels."),
        ("timeseries-aux", "Render deformation and auxiliary time series."),
    ):
        command = subparsers.add_parser(name, help=description)
        source = command.add_mutually_exclusive_group(required=True)
        source.add_argument("--config", type=Path)
        source.add_argument("--list", dest="job_list", type=Path)
        command.add_argument("--dry-run", action="store_true")
    baseline = subparsers.add_parser(
        "baseline_plot",
        help="Render an Analysis temporal-perpendicular baseline plot.",
    )
    source = baseline.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path)
    source.add_argument("--list", dest="job_list", type=Path)
    baseline.add_argument("--case")
    baseline.add_argument("--dry-run", action="store_true")
    return parser


def _load_workflow_main(workflow: str):
    """Import and return one workflow entry point only after CLI validation."""
    if workflow == "baseline_plot":
        from geodesy_visualization.workflows.insar.baseline_plot import main
    elif workflow == "study-area":
        from geodesy_visualization.workflows.cartography.study_area import main
    elif workflow == "deformation-map":
        from geodesy_visualization.workflows.insar.deformation_map import main
    elif workflow == "deformation-profile":
        from geodesy_visualization.workflows.insar.deformation_profile import main
    elif workflow == "timeseries-map":
        from geodesy_visualization.workflows.insar.timeseries_map import main
    else:
        from geodesy_visualization.workflows.insar.timeseries_aux import main
    return main


def _forwarded_arguments(config: Path, options: argparse.Namespace) -> list[str]:
    """Build one workflow argument vector from a resolved CFG path."""
    forwarded = ["--config", str(config)]
    if options.dry_run:
        forwarded.append("--dry-run")
    if options.workflow == "baseline_plot" and options.case is not None:
        forwarded.extend(["--case", options.case])
    return forwarded


def _print_batch_summary(summary: BatchSummary) -> None:
    """Print each visible job outcome followed by deterministic totals."""
    for result in summary.results:
        if result.status == 0:
            print(f"[OK] {result.path}")
        else:
            print(f"[FAILED] {result.path}: {result.error}")
    print(f"Total: {summary.total}")
    print(f"Succeeded: {summary.succeeded}")
    print(f"Failed: {summary.failed}")


def main(arguments: Sequence[str] | None = None) -> int:
    """Dispatch one configured visualization workflow."""
    options = build_parser().parse_args(arguments)
    workflow_main = _load_workflow_main(options.workflow)
    if options.config is not None:
        returned = workflow_main(_forwarded_arguments(options.config, options))
        return 0 if returned is None else int(returned)

    paths = load_job_list(options.job_list)

    def run_one(config: Path) -> int | None:
        """Dispatch one list item through the selected workflow entry point."""
        return workflow_main(_forwarded_arguments(config, options))

    summary = run_job_batch(paths, run_one)
    _print_batch_summary(summary)
    return 0 if summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_parser", "main"]
