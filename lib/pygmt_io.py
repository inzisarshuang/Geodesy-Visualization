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

from geodesy_visualization.io import *  # noqa: F401,F403
from geodesy_visualization.io import __all__  # noqa: F401
