"""
geodesy_visualization.figure_ops.direct_operations
=================================================

功能概述:
    实现与 PyGMT Figure 公共方法直接对应的操作，并在适配边界兼容当前
    独立 scalebar/directional_rose 接口与 envPlot 的 PyGMT v0.10 接口。

函数说明:
    ``render_basemap`` / ``render_grdimage``:
        建立主地图状态并绘制栅格，同时发布后续 colorbar 可引用的资源。
    ``render_scalebar`` / ``render_directional_rose``:
        优先调用当前独立方法，旧版回退到 basemap 原始参数。
    ``render_colorbar``:
        从 source 栅格资源构造兼容新旧 PyGMT 的色标调用。
    ``render_savefig``:
        创建输出目录并调用 Figure.savefig。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .executor import RenderContext
    from .model import FigureOperation


def _without(options: dict[str, object], *keys: str) -> dict[str, object]:
    """Return a shallow option copy without workflow-only keys."""
    return {key: value for key, value in options.items() if key not in keys}


def _position_code(value: object, prefix: str = "j") -> str:
    """Convert a two-letter current position into a legacy GMT reference code."""
    text = str(value)
    if len(text) == 2 and all(character in "TMBLCR" for character in text):
        return f"{prefix}{text}"
    return text


def _reject_unsupported_legacy(
    operation: "FigureOperation",
    options: dict[str, object],
    supported: frozenset[str],
) -> None:
    """Reject CFG keys that the PyGMT v0.10 basemap fallback cannot preserve."""
    unsupported = sorted(set(options) - supported)
    if unsupported:
        raise ValueError(
            f"[{operation.section}] {', '.join(unsupported)} cannot be translated "
            "by the installed PyGMT v0.10 fallback"
        )


def render_basemap(context: "RenderContext", operation: "FigureOperation") -> None:
    """Render a basemap and publish its region and projection in the context."""
    options = dict(operation.options)
    context.region = tuple(options["region"])
    context.projection = str(options["projection"])
    title = options.pop("title", None)
    if title:
        frame = options.get("frame", "af")
        if isinstance(frame, (list, tuple)):
            options["frame"] = [*frame, f'+t"{title}"']
        else:
            options["frame"] = [frame, f'+t"{title}"']
    context.figure.basemap(**options)


def render_grdimage(context: "RenderContext", operation: "FigureOperation") -> None:
    """Render one grid and publish its grid/CPT metadata for dependent operations."""
    options = dict(operation.options)
    if "region" not in options and context.region is not None:
        options["region"] = context.region
    if "projection" not in options and context.projection is not None:
        options["projection"] = context.projection
    context.figure.grdimage(**options)
    context.resources[operation.section] = {
        "grid": options["grid"],
        "cmap": options["cmap"],
    }
    context.active_cpt_source = operation.section


def render_scalebar(context: "RenderContext", operation: "FigureOperation") -> None:
    """Render a scale bar through the current method or the v0.10 basemap fallback."""
    options = _without(dict(operation.options), "enabled")
    method = getattr(context.figure, "scalebar", None)
    if callable(method):
        method(**options)
        return
    _reject_unsupported_legacy(
        operation,
        options,
        frozenset({"position", "length", "fancy", "unit", "label", "box"}),
    )
    raw = f"{_position_code(options.pop('position'))}+w{options.pop('length')}"
    if options.pop("fancy", False):
        raw += "+f"
    if options.pop("unit", False):
        raw += "+u"
    label = options.pop("label", False)
    if isinstance(label, str) and label:
        raw += f"+l{label}"
    box = options.pop("box", False)
    context.figure.basemap(map_scale=raw, box=box or None)


def render_directional_rose(
    context: "RenderContext",
    operation: "FigureOperation",
) -> None:
    """Render a directional rose through the current method or legacy basemap."""
    options = _without(dict(operation.options), "enabled")
    method = getattr(context.figure, "directional_rose", None)
    if callable(method):
        method(**options)
        return
    _reject_unsupported_legacy(
        operation,
        options,
        frozenset({"position", "width", "kind", "box"}),
    )
    raw = f"{_position_code(options.pop('position'))}+w{options.pop('width')}"
    kind = options.pop("kind", "")
    if kind:
        raw += f"+{kind}"
    box = options.pop("box", False)
    context.figure.basemap(rose=raw, box=box or None)


def render_colorbar(context: "RenderContext", operation: "FigureOperation") -> None:
    """Render a source-linked colorbar using arguments compatible with PyGMT v0.10."""
    options = _without(dict(operation.options), "enabled")
    source = str(options.pop("source"))
    if context.active_cpt_source != source:
        raise ValueError(
            f"[{operation.section}] source {source!r} is not the active CPT; "
            "place its colorbar before a later figure.grdimage operation"
        )
    options.setdefault("cmap", True)
    position = _position_code(options.pop("position"), prefix="J")
    length = options.pop("length", None)
    width = options.pop("width", None)
    orientation = str(options.pop("orientation", "horizontal")).lower()
    if length or width:
        position += f"+w{length or '80%'}"
        if width:
            position += f"/{width}"
    position += "+v" if orientation == "vertical" else "+h"
    options["position"] = position
    label = options.pop("label", None)
    unit = options.pop("unit", None)
    frame: list[str] = []
    if label:
        frame.append(f"x+l{label}")
    if unit:
        frame.append(f"y+l{unit}")
    if frame:
        options["frame"] = frame
    context.figure.colorbar(**options)


def render_savefig(context: "RenderContext", operation: "FigureOperation") -> None:
    """Create the destination directory and save the configured Figure output."""
    options = dict(operation.options)
    output = Path(str(options.pop("fname"))).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas_margin = options.pop("canvas_margin", None)
    if canvas_margin:
        options["resize"] = f"+m{canvas_margin}"
    context.figure.savefig(str(output), **options)
    context.resources[operation.section] = {"output": str(output)}


DIRECT_HANDLERS: dict[str, Callable] = {
    "basemap": render_basemap,
    "grdimage": render_grdimage,
    "scalebar": render_scalebar,
    "directional_rose": render_directional_rose,
    "colorbar": render_colorbar,
    "savefig": render_savefig,
}


__all__ = [
    "DIRECT_HANDLERS",
    "render_basemap",
    "render_colorbar",
    "render_directional_rose",
    "render_grdimage",
    "render_savefig",
    "render_scalebar",
]
