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

from geodesy_visualization.workflows.insar.baseline_cli import main as baseline_main
from geodesy_visualization.workflows.insar.deformation_map import (
    main as deformation_map_main,
)
from geodesy_visualization.workflows.insar.deformation_profile import (
    main as deformation_profile_main,
)
from geodesy_visualization.workflows.insar.timeseries_aux import (
    main as timeseries_aux_main,
)
from geodesy_visualization.workflows.insar.timeseries_map import (
    main as timeseries_map_main,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the unified configuration-driven visualization CLI."""
    parser = argparse.ArgumentParser(prog="geodesy-visualization")
    subparsers = parser.add_subparsers(dest="workflow", required=True)
    for name, description in (
        ("deformation-map", "Render deformation maps over DEM or optical basemaps."),
        ("deformation-profile", "Render deformation maps and profile comparisons."),
        ("timeseries-map", "Render geographic time-series panels."),
        ("timeseries-aux", "Render deformation and auxiliary time series."),
    ):
        command = subparsers.add_parser(name, help=description)
        command.add_argument("--config", required=True, type=Path)
        command.add_argument("--dry-run", action="store_true")
    baseline = subparsers.add_parser(
        "baseline-network",
        help="Render an Analysis temporal-perpendicular baseline network.",
    )
    baseline.add_argument("--config", required=True, type=Path)
    baseline.add_argument("--case")
    baseline.add_argument("--dry-run", action="store_true")
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Dispatch one configured visualization workflow."""
    options = build_parser().parse_args(arguments)
    forwarded = ["--config", str(options.config)]
    if options.dry_run:
        forwarded.append("--dry-run")
    if options.workflow == "baseline-network":
        if options.case is not None:
            forwarded.extend(["--case", options.case])
        return baseline_main(forwarded)
    dispatch = {
        "deformation-map": deformation_map_main,
        "deformation-profile": deformation_profile_main,
        "timeseries-map": timeseries_map_main,
        "timeseries-aux": timeseries_aux_main,
    }
    dispatch[options.workflow](forwarded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_parser", "main"]
