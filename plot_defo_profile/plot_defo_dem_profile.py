"""
plot_defo_dem_profile
=====================

功能概述:
    保留原有形变剖面脚本路径和命令行入口，并把工作流行为委托给
    ``geodesy_visualization.workflows.insar.deformation_profile``。

函数说明:
    ``build_parser`` / ``load_dataset_cfg`` / ``load_config``:
        兼容重导出正式模块中的配置接口。
    ``build_tracks`` / ``extract_profiles``:
        兼容重导出正式模块中的轨迹和采样接口。
    ``render_map`` / ``profile_output_path`` / ``render_profiles``:
        兼容重导出正式模块中的图件编排接口。
    ``main``:
        调用正式工作流入口。
"""

from __future__ import annotations

from pathlib import Path
import sys


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from geodesy_visualization.workflows.insar.deformation_profile import (  # noqa: E402
    ALLOWED_KEYS,
    build_parser,
    build_tracks,
    extract_profiles,
    load_config,
    load_dataset_cfg,
    main,
    profile_output_path,
    render_map,
    render_profiles,
)


__all__ = [
    "ALLOWED_KEYS",
    "build_parser",
    "build_tracks",
    "extract_profiles",
    "load_config",
    "load_dataset_cfg",
    "main",
    "profile_output_path",
    "render_map",
    "render_profiles",
]


if __name__ == "__main__":
    main()
