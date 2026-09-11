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

from pathlib import Path
import sys


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from geodesy_visualization.backends.pygmt import *  # noqa: E402,F401,F403
from geodesy_visualization.backends.pygmt import __all__  # noqa: E402,F401
