"""
pygmt_visual
============

功能概述:
    为现有工作流和外部调用者保留旧 ``pygmt_visual`` 导入路径，并把绘图行为
    委托给 ``geodesy_visualization.backends.pygmt``；本模块不再拥有绘图实现。

函数说明:
    ``PyGMTPlotter``:
        从正式 PyGMT backend 重新导出兼容绘图器类。
"""

from __future__ import annotations

from geodesy_visualization.backends.pygmt import *  # noqa: F401,F403
from geodesy_visualization.backends.pygmt import __all__  # noqa: F401
