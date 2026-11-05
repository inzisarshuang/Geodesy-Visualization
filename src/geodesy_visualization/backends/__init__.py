"""
geodesy_visualization.backends
==============================

功能概述:
    汇集具体绘图引擎的实现，并与工作流编排和科学数据转换保持分离；按需加载
    PyGMT backend，使 Matplotlib 使用方不必安装 GMT/PyGMT。

函数说明:
    ``PyGMTPlotter``:
        从 PyGMT backend 重新导出当前公共绘图器。
"""

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from .pygmt import PyGMTPlotter


__all__ = ["PyGMTPlotter"]


def __getattr__(name: str) -> Any:
    """Lazily expose backend classes without importing optional engines eagerly."""
    if name == "PyGMTPlotter":
        from .pygmt import PyGMTPlotter

        return PyGMTPlotter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
