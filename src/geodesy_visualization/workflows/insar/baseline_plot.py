"""
geodesy_visualization.workflows.insar.baseline_plot
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

from geodesy_visualization.workflows.insar.baseline_plot_config import (
    load_baseline_plot_config,
    select_baseline_plot_case,
)
from geodesy_visualization.workflows.insar.baseline_plot_core import (
    render_baseline_plot,
    read_baseline_manifest,
    read_baseline_network,
)


def _parser() -> argparse.ArgumentParser:
    """Build the single public configuration-driven command interface."""

    parser = argparse.ArgumentParser(
        prog="geodesy-visualization baseline_plot",
        description="Render an Analysis temporal-perpendicular baseline plot.",
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
        output = render_baseline_plot(
            network,
            case.output,
            title=case.title,
            dpi=case.dpi,
            figsize=case.figsize,
            y_top_extra=case.y_top_extra,
            y_bottom_extra=case.y_bottom_extra,
            font_dir=case.python_font_dir,
            title_label_font_size=case.title_label_font_size,
            tick_font_size=case.tick_font_size,
            legend_font_size=case.legend_font_size,
            font_weight=case.font_weight,
            xlabel=case.xlabel,
            ylabel=case.ylabel,
            date_format=case.date_format,
            date_tick_unit=case.date_tick_unit,
            date_tick_interval=case.date_tick_interval,
            date_tick_rotation=case.date_tick_rotation,
            y_tick_interval=case.y_tick_interval,
            line_color=case.line_color,
            slave_color=case.slave_color,
            reference_color=case.reference_color,
            grid_color=case.grid_color,
            show_grid=case.show_grid,
            line_label=case.line_label,
            slave_label=case.slave_label,
            reference_label=case.reference_label,
        )
    except (FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(f"[baseline_plot] wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
