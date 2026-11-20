"""
geodesy_visualization.workflows.cartography.study_area
=====================================================

功能概述:
    提供研究区域和数据 footprint 图的正式配置驱动入口，只负责加载
    FigurePlan、输出 dry-run 摘要并委托 FigureExecutor 渲染。

函数说明:
    ``build_parser``:
        构建 study-area workflow 的命令行参数。
    ``load_plan``:
        加载并严格校验一个有序 Figure 操作配置。
    ``main``:
        执行 dry-run 或将完整操作计划交给 FigureExecutor。
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from geodesy_visualization.figure_ops.config import load_figure_plan
from geodesy_visualization.figure_ops.executor import FigureExecutor
from geodesy_visualization.figure_ops.model import FigurePlan
from geodesy_visualization.resources import resource_path


DEFAULT_CONFIG = resource_path(
    "config_examples", "study_area", "footprint.cfg"
)


def build_parser() -> argparse.ArgumentParser:
    """Build the public study-area command-line parser."""
    parser = argparse.ArgumentParser(
        description="Render a PyGMT study-area and data-footprint figure from an ordered CFG."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def load_plan(config_file: str) -> FigurePlan:
    """Load one study-area CFG into a validated ordered FigurePlan."""
    return load_figure_plan(config_file)


def _print_dry_run(plan: FigurePlan) -> None:
    """Print resolved operation order and output without constructing a Figure."""
    print(f"Config: {plan.config_path}")
    print(f"Layout: {plan.figure['layout']}")
    print("Operations:")
    for operation in plan.operations:
        print(f"  {operation.order + 1:02d}. {operation.section}")
    save_operations = [
        operation for operation in plan.operations if operation.handler == "savefig"
    ]
    if save_operations:
        print(f"Output: {save_operations[-1].options['fname']}")


def main(arguments: Sequence[str] | None = None) -> int:
    """Validate and render one configured study-area figure."""
    options = build_parser().parse_args(arguments)
    plan = load_plan(str(options.config))
    if options.dry_run:
        _print_dry_run(plan)
        return 0
    FigureExecutor(plan).execute()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_parser", "load_plan", "main"]
