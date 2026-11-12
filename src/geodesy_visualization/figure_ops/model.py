"""
geodesy_visualization.figure_ops.model
======================================

功能概述:
    定义配置驱动 PyGMT 绘图的不可变单操作记录与整图操作计划。

函数说明:
    ``FigureOperation``:
        保存一个有序 Figure 调用的 section、方法、科学语义和规范化参数。
    ``FigurePlan``:
        保存配置来源、项目参数、整图参数和全部有序绘图操作。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class FigureOperation:
    """Describe one validated operation applied to a PyGMT Figure."""

    section: str
    method: str
    semantics: tuple[str, ...]
    options: Mapping[str, object]
    order: int
    handler: str


@dataclass(frozen=True)
class FigurePlan:
    """Contain one complete ordered and validated figure configuration."""

    config_path: Path
    project: Mapping[str, str]
    figure: Mapping[str, str]
    operations: tuple[FigureOperation, ...]


__all__ = ["FigureOperation", "FigurePlan"]
