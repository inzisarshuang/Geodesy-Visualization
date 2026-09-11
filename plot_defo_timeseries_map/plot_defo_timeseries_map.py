"""
plot_defo_timeseries_map
=======================

功能概述:
    保留原有空间时序子图脚本路径和命令行入口，并把全部工作流行为委托给
    ``geodesy_visualization.workflows.insar.timeseries_map``。

函数说明:
    ``build_parser`` / ``load_config``:
        兼容重导出正式模块中的命令行与配置接口。
    ``load_timeseries_table``:
        兼容重导出正式模块中的分块时序读取接口。
    ``draw_panel_basemap`` / ``render``:
        兼容重导出正式模块中的子图底图与绘图接口。
    ``main``:
        调用正式工作流入口。
"""

from __future__ import annotations

from pathlib import Path
import sys


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from geodesy_visualization.workflows.insar.timeseries_map import (  # noqa: E402
    ALLOWED_KEYS,
    build_parser,
    draw_panel_basemap,
    load_config,
    load_timeseries_table,
    main,
    render,
)


__all__ = [
    "ALLOWED_KEYS",
    "build_parser",
    "draw_panel_basemap",
    "load_config",
    "load_timeseries_table",
    "main",
    "render",
]


if __name__ == "__main__":
    main()
