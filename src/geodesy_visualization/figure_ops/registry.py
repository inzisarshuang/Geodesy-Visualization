"""
geodesy_visualization.figure_ops.registry
=========================================

功能概述:
    声明支持的 ``figure.*`` section 模式、严格参数 schema 和执行器名称，
    为解析器与渲染器提供同一个稳定操作注册表。

函数说明:
    ``OperationSpec``:
        描述一个 section 模式所需、允许和需要类型转换的配置键。
    ``OperationRegistry``:
        按完整 section 名称解析唯一操作 schema。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern


@dataclass(frozen=True)
class OperationSpec:
    """Define validation and dispatch metadata for one operation pattern."""

    pattern: Pattern[str]
    required_keys: frozenset[str]
    allowed_keys: frozenset[str]
    path_keys: frozenset[str] = frozenset()
    bool_keys: frozenset[str] = frozenset()
    int_keys: frozenset[str] = frozenset()
    float_keys: frozenset[str] = frozenset()
    handler: str = ""


class OperationRegistry:
    """Resolve supported dotted Figure sections to one unambiguous spec."""

    def __init__(self, specs: tuple[OperationSpec, ...]):
        """Initialize an ordered registry and reject duplicate pattern strings."""
        patterns = [spec.pattern.pattern for spec in specs]
        if len(patterns) != len(set(patterns)):
            raise ValueError("operation registry contains duplicate patterns")
        self._specs = specs

    def resolve(self, section: str) -> OperationSpec:
        """Return the unique spec matching ``section`` or raise a useful error."""
        matches = [spec for spec in self._specs if spec.pattern.fullmatch(section)]
        if len(matches) == 1:
            return matches[0]
        if section.startswith("figure.plot.coverage."):
            raise ValueError(
                f"unsupported operation section '{section}'; use "
                "'figure.plot.footprint.<id>' instead of coverage"
            )
        if len(matches) > 1:
            raise ValueError(f"ambiguous operation section '{section}'")
        raise ValueError(f"unknown operation section '{section}'")


def _spec(
    pattern: str,
    *,
    required: tuple[str, ...] = (),
    allowed: tuple[str, ...] = (),
    paths: tuple[str, ...] = (),
    bools: tuple[str, ...] = (),
    ints: tuple[str, ...] = (),
    floats: tuple[str, ...] = (),
    handler: str,
) -> OperationSpec:
    """Build one immutable operation spec while including required keys."""
    required_keys = frozenset(required)
    return OperationSpec(
        pattern=re.compile(pattern),
        required_keys=required_keys,
        allowed_keys=required_keys | frozenset(allowed),
        path_keys=frozenset(paths),
        bool_keys=frozenset(bools),
        int_keys=frozenset(ints),
        float_keys=frozenset(floats),
        handler=handler,
    )


DEFAULT_REGISTRY = OperationRegistry(
    (
        _spec(
            r"figure\.basemap",
            required=("region", "projection"),
            allowed=(
                "frame", "title", "transparency", "font_title",
                "font_annot_primary", "font_label",
            ),
            floats=("transparency",),
            handler="basemap",
        ),
        _spec(
            r"figure\.grdimage\.[a-z][a-z0-9_]*",
            required=("grid", "cmap"),
            allowed=(
                "shading", "region", "projection", "frame", "dpi", "monochrome",
                "no_clip", "nan_transparent", "transparency", "series", "continuous",
            ),
            paths=("grid",),
            bools=("monochrome", "no_clip", "continuous"),
            ints=("dpi",),
            floats=("transparency",),
            handler="grdimage",
        ),
        _spec(
            r"figure\.plot\.footprint\.[a-z][a-z0-9_]*",
            required=("data", "pen"),
            allowed=("enabled", "fill", "label", "transparency", "close", "no_clip"),
            paths=("data",),
            bools=("enabled", "close", "no_clip"),
            floats=("transparency",),
            handler="footprint",
        ),
        _spec(
            r"figure\.plot\.faults(?:\.[a-z][a-z0-9_]*)?",
            required=("data", "kinematic_field"),
            allowed=(
                "enabled", "pen", "fallback_pen", "reverse_pen", "reverse_style", "reverse_fill",
                "normal_pen", "normal_style", "normal_fill", "strike_slip_pen",
                "strike_slip_style", "strike_slip_fill", "label_reverse",
                "label_normal", "label_strike_slip", "label_other", "transparency",
            ),
            paths=("data",),
            bools=("enabled",),
            floats=("transparency",),
            handler="faults",
        ),
        _spec(
            r"figure\.meca\.[a-z][a-z0-9_]*",
            required=(
                "longitude", "latitude", "strike", "dip", "rake", "magnitude",
                "depth_km", "scale",
            ),
            allowed=(
                "enabled", "compressionfill", "extensionfill", "pen", "label",
                "transparency",
            ),
            bools=("enabled",),
            floats=(
                "longitude", "latitude", "strike", "dip", "rake", "magnitude",
                "depth_km", "transparency",
            ),
            handler="meca",
        ),
        _spec(
            r"figure\.scalebar",
            required=("position", "length"),
            allowed=(
                "enabled", "height", "scale_loc", "label", "label_alignment", "unit",
                "fancy", "vertical", "box", "transparency", "font_annot_primary",
                "font_label",
            ),
            bools=("enabled", "unit", "fancy", "vertical", "box"),
            floats=("transparency",),
            handler="scalebar",
        ),
        _spec(
            r"figure\.directional_rose",
            required=("position", "width"),
            allowed=(
                "enabled", "kind", "labels", "intervals", "box", "offset",
                "transparency",
            ),
            bools=("enabled", "box"),
            floats=("transparency",),
            handler="directional_rose",
        ),
        _spec(
            r"figure\.colorbar\.[a-z][a-z0-9_]*",
            required=("source", "position"),
            allowed=(
                "enabled", "cmap", "length", "width", "orientation", "label", "unit",
                "annot", "tick", "grid", "reverse", "box", "transparency",
                "font_annot_primary", "font_label",
            ),
            bools=("enabled", "reverse", "box"),
            floats=("annot", "tick", "grid", "transparency"),
            handler="colorbar",
        ),
        _spec(
            r"figure\.inset\.globe",
            required=("position", "width", "highlight"),
            allowed=(
                "enabled", "height", "box", "land", "water", "highlight_fill",
                "show_grid", "marker_style", "marker_fill", "marker_pen",
            ),
            bools=("enabled", "box", "show_grid"),
            handler="globe_inset",
        ),
        _spec(
            r"figure\.inset\.regional",
            required=("position", "width", "regions"),
            allowed=(
                "enabled", "height", "box", "buffer", "land", "water",
                "highlight_fill", "highlight_pen", "marker_style", "marker_fill",
                "marker_pen",
            ),
            bools=("enabled", "box"),
            floats=("buffer",),
            handler="regional_inset",
        ),
        _spec(
            r"figure\.legend",
            required=("position",),
            allowed=(
                "enabled", "box", "width", "font", "mode", "row_gap", "padding",
            ),
            bools=("enabled", "box"),
            handler="legend",
        ),
        _spec(
            r"figure\.savefig",
            required=("fname",),
            allowed=("dpi", "crop", "transparent", "canvas_margin"),
            paths=("fname",),
            bools=("crop", "transparent"),
            ints=("dpi",),
            handler="savefig",
        ),
    )
)


__all__ = ["DEFAULT_REGISTRY", "OperationRegistry", "OperationSpec"]
