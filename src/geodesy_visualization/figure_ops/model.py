"""
geodesy_visualization.figure_ops.model
======================================

功能概述:
    定义配置驱动 PyGMT 绘图的不可变图层、面板与整图操作计划。

函数说明:
    ``LayerOperation``:
        保存一个有序 Figure 图层调用的 section、方法、科学语义和规范化参数。
    ``PanelPlan``:
        保存一个子图面板的标识、区域、投影和有序图层。
    ``FigurePlan``:
        保存配置来源、项目参数、整图参数和全部有序绘图操作。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class LayerOperation:
    """Describe one validated layer operation applied to a PyGMT Figure."""

    section: str
    method: str
    semantics: tuple[str, ...]
    options: Mapping[str, object]
    order: int
    handler: str


# Compatibility name retained for the established footprint workflow.
FigureOperation = LayerOperation


@dataclass(frozen=True)
class PanelPlan:
    """Describe one independently scoped map or Cartesian figure panel."""

    identifier: int | str
    region: tuple[float, float, float, float] | None
    projection: str | None
    layers: tuple[LayerOperation, ...]


@dataclass(frozen=True)
class FigurePlan:
    """Contain one complete ordered and validated figure configuration."""

    config_path: Path
    project: Mapping[str, str]
    figure: Mapping[str, str]
    operations: tuple[LayerOperation, ...] = ()
    panels: tuple[PanelPlan, ...] = ()
    figure_layers: tuple[LayerOperation, ...] = ()


__all__ = ["FigureOperation", "FigurePlan", "LayerOperation", "PanelPlan"]
