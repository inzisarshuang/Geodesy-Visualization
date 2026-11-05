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
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping


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
    "colorbar_metadata_keys",
    "font_style_keys",
    "parse_colorbar_metadata",
    "parse_font_style",
    "resolve_cpt_reference",
]
