"""
plot_defo_dem_optic
===================

功能概述:
    保留原有形变地图脚本路径和命令行入口，并把工作流行为委托给
    ``geodesy_visualization.workflows.insar.deformation_map``。

函数说明:
    ``validate_raw_config`` / ``optional_path`` / ``parse_manual_region`` /
    ``parse_target_regions``:
        兼容重导出正式模块中的配置辅助接口。
    ``build_parser`` / ``load_config``:
        兼容重导出正式模块中的命令行与配置接口。
    ``draw_basemap`` / ``draw_deformation`` / ``draw_target_regions`` /
    ``render_map``:
        兼容重导出正式模块中的地图编排接口。
    ``main``:
        调用正式工作流入口。
"""

from __future__ import annotations

from pathlib import Path
import sys


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from geodesy_visualization.workflows.insar.deformation_map import (  # noqa: E402
    ALLOWED_KEYS,
    build_parser,
    draw_basemap,
    draw_deformation,
    draw_target_regions,
    load_config,
    main,
    optional_path,
    parse_manual_region,
    parse_target_regions,
    render_map,
    validate_raw_config,
)


__all__ = [
    "ALLOWED_KEYS",
    "build_parser",
    "draw_basemap",
    "draw_deformation",
    "draw_target_regions",
    "load_config",
    "main",
    "optional_path",
    "parse_manual_region",
    "parse_target_regions",
    "render_map",
    "validate_raw_config",
]


if __name__ == "__main__":
    main()
