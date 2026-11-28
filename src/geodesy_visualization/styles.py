"""
geodesy_visualization.styles
============================

功能概述:
    定义跨工作流共享的 cfg 样式解析契约。当前阶段统一 GMT 标题、主/次注记和
    标签字体，不改变各工作流既有默认值，也不负责图件绘制。

函数说明:
    ``font_style_keys``:
        返回一个具名前缀支持的标准字体 cfg 键集合。
    ``parse_font_style``:
        将具名前缀的字体 cfg 解析为 GMT 配置字典。
    ``resolve_cpt_reference``:
        区分 GMT 内置色标名称与相对 cfg 的 CPT 文件引用。
    ``colorbar_metadata_keys`` / ``parse_colorbar_metadata``:
        定义并解析共享色标开关、标签和单位，不接管工作流专用几何。
    ``parse_scoped_font_style`` / ``parse_deformation_map_style``:
        解析字体优先级，以及形变地图和剖面地图共有的版式参数。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Mapping


_MAP_FRAME_DEFAULTS = {
    "frame_type": "fancy",
    "frame_width": "6p",
    "frame_pen": "3p",
    "tick_pen": "3p",
    "coordinate_format": "ddd:mm:ss",
    "x_label": "",
    "y_label": "",
    "x_label_offset": "0c/-1c",
    "y_label_offset": "-2.3c/0c",
}
_DEFO_COLORBAR_DEFAULTS = {
    "position": "JBC+o0c/4c+w12c/0.6c+h",
    "box": "F+gWHITE+p2p+c20p/20p",
    "font_annot_primary": "20p",
    "font_label": "",
}
DEFORMATION_MAP_STYLE_KEYS = {
    *(f"map_{key}" for key in _MAP_FRAME_DEFAULTS),
    *(f"defo_colorbar_{key}" for key in _DEFO_COLORBAR_DEFAULTS),
    "map_longitude_interval", "map_latitude_interval", "map_show_grid", "map_grid_pen",
    "map_rose", "map_rose_box", "map_rose_label_size",
    "defo_colorbar_tick_interval", "output_dpi",
}


def font_style_keys(prefix: str, *, include_secondary: bool = False) -> set[str]:
    """Return canonical cfg keys for one named GMT font-style block."""
    normalized = str(prefix).strip()
    if not normalized:
        raise ValueError("font style prefix must not be empty")
    keys = {
        f"{normalized}_font_title",
        f"{normalized}_font_annot_primary",
        f"{normalized}_font_label",
    }
    if include_secondary:
        keys.add(f"{normalized}_font_annot_secondary")
    return keys


def parse_font_style(
    cfg: Mapping[str, str],
    prefix: str,
    default_title: str,
    default_annot: str,
    default_label: str,
    *,
    default_secondary: str | None = None,
) -> dict[str, str]:
    """Parse one canonical cfg font block without changing workflow defaults."""
    normalized = str(prefix).strip()
    font_style_keys(normalized, include_secondary=default_secondary is not None)
    key_defaults = {
        "FONT_TITLE": (f"{normalized}_font_title", default_title),
        "FONT_ANNOT_PRIMARY": (f"{normalized}_font_annot_primary", default_annot),
        "FONT_LABEL": (f"{normalized}_font_label", default_label),
    }
    if default_secondary is not None:
        key_defaults["FONT_ANNOT_SECONDARY"] = (
            f"{normalized}_font_annot_secondary",
            default_secondary,
        )
    values: dict[str, str] = {}
    for gmt_key, (cfg_key, default) in key_defaults.items():
        value = str(cfg.get(cfg_key, default)).strip()
        if not value:
            raise ValueError(f"font style key must not be empty: {cfg_key}")
        values[gmt_key] = value
    return values


def parse_scoped_font_style(
    cfg: Mapping[str, str], prefix: str, defaults: tuple[str, str, str]
) -> dict[str, str]:
    """Resolve each scoped font through its explicit default key and workflow fallback."""
    base = parse_font_style(cfg, "default", *defaults)
    return parse_font_style(
        cfg, prefix, base["FONT_TITLE"], base["FONT_ANNOT_PRIMARY"], base["FONT_LABEL"]
    )


def parse_deformation_map_style(cfg: Mapping[str, str]) -> dict:
    """Normalize frame, rose, and colorbar style settings shared by both map workflows."""
    from geodesy_visualization.io import parse_bool

    frame = {key: cfg.get(f"map_{key}", value) for key, value in _MAP_FRAME_DEFAULTS.items()}
    colorbar = {
        key: cfg.get(f"defo_colorbar_{key}", value)
        for key, value in _DEFO_COLORBAR_DEFAULTS.items()
    }
    for target, prefix, keys in (
        (frame, "map", ("longitude_interval", "latitude_interval")),
        (colorbar, "defo_colorbar", ("tick_interval",)),
    ):
        for key in keys:
            name = f"{prefix}_{key}"
            raw = cfg.get(name, "")
            interval = float(raw) if raw else None
            if interval is not None and (not math.isfinite(interval) or interval <= 0):
                if key == "tick_interval" and interval == 0:
                    interval = None
                else:
                    raise ValueError(f"{name} must be positive")
            target[key] = interval
    frame["show_grid"] = False
    dpi = int(cfg.get("output_dpi") or 300)
    if dpi < 1:
        raise ValueError("output_dpi must be positive")
    return {
        "map_frame": frame,
        "map_grid_options": {
            "enabled": parse_bool(cfg.get("map_show_grid"), False),
            "pen": cfg.get("map_grid_pen", "0.5p,gray45"),
            "longitude_interval": frame["longitude_interval"],
            "latitude_interval": frame["latitude_interval"],
        },
        "map_rose_options": {
            "rose": cfg.get("map_rose", "JMR+jCM+o10c/0c+w5c+l+f1"),
            "box": cfg.get("map_rose_box", "F+gwhite+p2p+c1.5c"),
            "label_size": cfg.get("map_rose_label_size", ""),
        },
        "defo_colorbar_style": colorbar,
        "output_dpi": dpi,
    }


def resolve_cpt_reference(value: str, base_dir: str | Path) -> str:
    """Resolve a CPT file relative to its cfg while preserving GMT palette names."""
    normalized = str(value).strip()
    if not normalized:
        raise ValueError("CPT reference must not be empty")
    path = Path(normalized).expanduser()
    if path.suffix.lower() != ".cpt" and path.parent == Path("."):
        return normalized
    if not path.is_absolute():
        path = Path(base_dir) / path
    return str(path.resolve())


def colorbar_metadata_keys(prefix: str = "") -> set[str]:
    """Return shared cfg keys for one optionally prefixed colorbar identity."""
    normalized = str(prefix).strip()
    scoped = f"{normalized}_" if normalized else ""
    return {"add_colorbar", f"{scoped}colorbar_label", f"{scoped}colorbar_unit"}


def parse_colorbar_metadata(
    cfg: Mapping[str, str],
    prefix: str,
    *,
    enabled: bool,
    default_label: str,
    default_unit: str,
) -> dict[str, str | bool]:
    """Parse shared colorbar identity while leaving geometry workflow-owned."""
    normalized = str(prefix).strip()
    scoped = f"{normalized}_" if normalized else ""
    label_key = f"{scoped}colorbar_label"
    unit_key = f"{scoped}colorbar_unit"
    return {
        "add_colorbar": bool(enabled),
        label_key: str(cfg.get(label_key, default_label)).strip(),
        unit_key: str(cfg.get(unit_key, default_unit)).strip(),
    }


__all__ = [
    "DEFORMATION_MAP_STYLE_KEYS",
    "colorbar_metadata_keys",
    "font_style_keys",
    "parse_colorbar_metadata",
    "parse_font_style",
    "parse_scoped_font_style",
    "parse_deformation_map_style",
    "resolve_cpt_reference",
]
