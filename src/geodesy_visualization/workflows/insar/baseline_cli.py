"""
geodesy_visualization.workflows.insar.baseline_cli
=================================================

功能概述:
    提供基于 cfg 的 InSAR 基线网络图入口，连接配置、Analysis 清单
    校验和 Visualization 原子绘图；不提供文件位置参数的第二套入口。

函数说明:
    ``main``:
        选择一个配置 case，验证基线产品并发布 PNG 图件。
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from geodesy_visualization.workflows.insar.baseline_config import (
    load_baseline_plot_config,
    select_baseline_plot_case,
)
from geodesy_visualization.workflows.insar.baseline_network import (
    plot_baseline_network,
    read_baseline_manifest,
    read_baseline_network,
)


def _parser() -> argparse.ArgumentParser:
    """Build the single public configuration-driven command interface."""

    parser = argparse.ArgumentParser(
        prog="geodesy-visualization-insar-baseline",
        description="Plot an Analysis temporal-perpendicular baseline network.",
    )
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--case")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Validate one configured Analysis product and atomically publish its PNG."""

    options = _parser().parse_args(arguments)
    try:
        case = select_baseline_plot_case(
            load_baseline_plot_config(options.config), options.case
        )
        manifest = read_baseline_manifest(
            case.baseline_manifest, project_root=case.project_root
        )
        network = read_baseline_network(manifest)
        if options.dry_run:
            print(f"dry-run: output={case.output}")
            return 0
        output = plot_baseline_network(
            network,
            case.output,
            title=case.title,
            dpi=case.dpi,
            figsize=case.figsize,
            y_top_extra=case.y_top_extra,
            y_bottom_extra=case.y_bottom_extra,
            font_family=case.font_family,
        )
    except (FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(f"[baselineplot] wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
