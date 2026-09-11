"""
plot_defo_timeseries_aux
=======================

功能概述:
    保留原有辅助时序绘图脚本路径和命令行入口，并把全部工作流行为委托给
    ``geodesy_visualization.workflows.insar.timeseries_aux``。

函数说明:
    ``build_parser`` / ``load_config``:
        兼容重导出正式模块中的命令行与配置接口。
    ``read_date_value_table`` / ``render``:
        兼容重导出正式模块中的表格读取与绘图接口。
    ``main``:
        调用正式工作流入口。
"""

from __future__ import annotations

from pathlib import Path
import sys


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from geodesy_visualization.workflows.insar.timeseries_aux import (  # noqa: E402
    ALLOWED_KEYS,
    build_parser,
    load_config,
    main,
    read_date_value_table,
    render,
)


__all__ = [
    "ALLOWED_KEYS",
    "build_parser",
    "load_config",
    "main",
    "read_date_value_table",
    "render",
]


if __name__ == "__main__":
    main()
