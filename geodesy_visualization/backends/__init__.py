"""
geodesy_visualization.backends
==============================

功能概述:
    汇集具体绘图引擎的实现，并与工作流编排和科学数据转换保持分离；当前提供
    PyGMT backend，后续 backend 必须遵守相同输出安全约定。

函数说明:
    ``PyGMTPlotter``:
        从 PyGMT backend 重新导出当前公共绘图器。
"""

from .pygmt import PyGMTPlotter


__all__ = ["PyGMTPlotter"]
