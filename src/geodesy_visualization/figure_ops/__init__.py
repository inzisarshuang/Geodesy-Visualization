"""
geodesy_visualization.figure_ops
================================

功能概述:
    提供以 ``figure.<pygmt_method>.<semantic_id>`` 配置为入口的有序
    PyGMT Figure 操作计划、严格解析和后续执行接口。

函数说明:
    本包的公开数据模型和解析函数由子模块导出；包根不定义额外函数或类。
"""

from .config import load_figure_plan
from .model import FigureOperation, FigurePlan
from .registry import DEFAULT_REGISTRY, OperationRegistry, OperationSpec

__all__ = [
    "DEFAULT_REGISTRY",
    "FigureOperation",
    "FigurePlan",
    "OperationRegistry",
    "OperationSpec",
    "load_figure_plan",
]
