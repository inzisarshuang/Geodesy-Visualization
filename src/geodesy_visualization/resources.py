"""
geodesy_visualization.resources
================================

功能概述:
    统一解析源码检出与安装包中的配置、CPT 和字体资源。

函数说明:
    ``resource_root``:
        返回可用的 Visualization 共享资源根目录。
    ``resource_path``:
        返回共享资源根下的指定路径。
"""

from __future__ import annotations

import sys
from pathlib import Path


def resource_root() -> Path:
    """Return the checkout or installed shared-resource directory."""
    checkout = Path(__file__).resolve().parents[2]
    if (checkout / "config_examples").is_dir() and (checkout / "cpt").is_dir():
        return checkout

    installed = Path(sys.prefix).resolve() / "share" / "geodesy-visualization"
    if installed.is_dir():
        return installed
    raise FileNotFoundError(
        "geodesy-visualization shared resources were not found; "
        f"checked {checkout} and {installed}"
    )


def resource_path(*parts: str) -> Path:
    """Return a path below the active shared-resource directory."""
    return resource_root().joinpath(*parts)


__all__ = ["resource_path", "resource_root"]
