"""
pygmt_io
========

功能概述:
    为现有工作流和外部调用者保留旧 ``pygmt_io`` 导入路径，并把全部行为委托给
    ``geodesy_visualization.io``；本模块不再拥有配置或文件处理实现。

函数说明:
    所有公共函数均从 ``geodesy_visualization.io`` 重新导出，不在本模块重复定义。
"""

from __future__ import annotations

from pathlib import Path
import sys


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from geodesy_visualization.io import *  # noqa: E402,F401,F403
from geodesy_visualization.io import __all__  # noqa: E402,F401
