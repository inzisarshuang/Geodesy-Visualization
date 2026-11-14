"""
geodesy_visualization.figure_ops.cartography_operations
======================================================

功能概述:
    实现研究区地图所需的复合 PyGMT 操作，包括 footprint、多类型断层、
    震源机制、全球/区域定位 inset 和按操作顺序汇总的自动图例。

函数说明:
    ``render_footprint``:
        绘制 KML 中的全部 footprint 多边形并贡献一个科学图例项。
    ``render_faults``:
        按运动学类别绘制断层并贡献固定顺序的断层图例项。
    ``render_meca``:
        以 Aki strike/dip/rake 约定绘制震源机制。
    ``render_globe_inset`` / ``render_regional_inset``:
        在独立 inset 上下文绘制全球与行政区定位图。
    ``render_legend``:
        将前序操作贡献的规范化条目写为临时 GMT legend spec 并绘制。
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from .cartography_inputs import (
    classify_fault_kinematics,
    parse_kml_footprints,
    read_fault_features,
)

if TYPE_CHECKING:
    from .executor import RenderContext
    from .model import FigureOperation


def _inset_position(position: object, width: object, height: object | None = None) -> str:
    """Build one raw GMT inset position compatible with PyGMT v0.10 and current APIs."""
    text = str(position)
    if len(text) == 2 and all(character in "TMBLCR" for character in text):
        text = f"j{text}"
    if "+w" not in text:
        text += f"+w{width}"
        if height:
            text += f"/{height}"
    return text


def _marker_options(options: dict[str, object]) -> dict[str, object]:
    """Extract configurable study-location marker options for an inset."""
    return {
        "style": options.pop("marker_style", "a0.3c"),
        "fill": options.pop("marker_fill", "red"),
        "pen": options.pop("marker_pen", "0.4p,white"),
    }


def render_footprint(context: "RenderContext", operation: "FigureOperation") -> None:
    """Draw every KML footprint polygon and append one operation-level legend item."""
    options = dict(operation.options)
    options.pop("enabled", None)
    data = str(options.pop("data"))
    label = str(options.pop("label", "")).strip()
    pen = str(options.get("pen", "1.5p,black"))
    for polygon in parse_kml_footprints(data):
        context.figure.plot(x=polygon[:, 0], y=polygon[:, 1], **options)
    if label:
        context.legend_items.append(
            {
                "section": operation.section,
                "label": label,
                "kind": "line",
                "pen": pen,
            }
        )


def _fault_style(kind: str, options: dict[str, object]) -> dict[str, object]:
    """Return the configured or legacy-compatible style for one fault category."""
    defaults: dict[str, dict[str, object]] = {
        "reverse": {
            "pen": options.get("reverse_pen", options.get("pen", "1.5p,black")),
            "style": options.get("reverse_style", "f0.8c/0.3c+r+t"),
            "fill": options.get("reverse_fill", "white"),
        },
        "normal": {
            "pen": options.get("normal_pen", options.get("pen", "1.5p,black")),
            "style": options.get("normal_style", "f0.8c/0.3c+l+t"),
            "fill": options.get("normal_fill", "black"),
        },
        "strike_slip": {
            "pen": options.get("strike_slip_pen", options.get("pen", "1.5p,black")),
            "style": options.get("strike_slip_style", "f0.8c/0.3c+l+s"),
            "fill": options.get("strike_slip_fill", "white"),
        },
        "other": {"pen": options.get("fallback_pen", "1p,gray50")},
    }
    style = dict(defaults[kind])
    if "transparency" in options:
        style["transparency"] = options["transparency"]
    return style


def _fault_legend_items(operation: "FigureOperation", options: dict[str, object]) -> list[dict]:
    """Build fixed-order legend entries for every supported fault category."""
    labels = {
        "reverse": str(options.get("label_reverse", "Reverse fault")),
        "normal": str(options.get("label_normal", "Normal fault")),
        "strike_slip": str(options.get("label_strike_slip", "Strike-slip fault")),
        "other": str(options.get("label_other", "Other fault")),
    }
    styles = {
        "reverse": {
            "symbol": "f+l+t",
            "fill": options.get("reverse_fill", "white"),
            "pen": options.get("reverse_pen", options.get("pen", "1.5p,black")),
        },
        "normal": {
            "symbol": "f+l+t",
            "fill": options.get("normal_fill", "black"),
            "pen": options.get("normal_pen", options.get("pen", "1.5p,black")),
        },
        "strike_slip": {
            "symbol": "f+l+s",
            "fill": options.get("strike_slip_fill", "black"),
            "pen": options.get(
                "strike_slip_pen", options.get("pen", "1.5p,black")
            ),
        },
        "other": {
            "symbol": "-",
            "fill": "-",
            "pen": options.get("fallback_pen", "1p,gray50"),
        },
    }
    return [
        {
            "section": operation.section,
            "label": labels[kind],
            "kind": kind,
            **styles[kind],
        }
        for kind in ("reverse", "normal", "strike_slip", "other")
    ]


def _legend_item_spec(
    item: dict[str, object],
    geometry: dict[str, object],
) -> str:
    """Format one structured legend item with shared publication geometry."""
    if "spec" in item:
        return str(item["spec"])
    symbol_offset = geometry["symbol_offset"]
    line_length = geometry["line_length"]
    text_offset = geometry["text_offset"]
    label = item["label"]
    if item["kind"] in {"reverse", "normal", "strike_slip"}:
        size = (
            f"{line_length}/{geometry['front_spacing']}/{geometry['front_size']}"
        )
        return (
            f"S {symbol_offset} {item['symbol']} {size} {item['fill']} "
            f"{item['pen']} {text_offset} {label}"
        )
    return (
        f"S {symbol_offset} - {line_length} - {item['pen']} "
        f"{text_offset} {label}"
    )


def render_faults(context: "RenderContext", operation: "FigureOperation") -> None:
    """Draw fault lines using deterministic kinematic fronts and fallback styling."""
    options = dict(operation.options)
    options.pop("enabled", None)
    data = str(options.pop("data"))
    field = str(options.pop("kinematic_field"))
    for feature in read_fault_features(data, field):
        kind = classify_fault_kinematics(feature.kinematics)
        context.figure.plot(
            x=feature.coordinates[:, 0],
            y=feature.coordinates[:, 1],
            **_fault_style(kind, options),
        )
    context.legend_items.extend(_fault_legend_items(operation, options))


def render_meca(context: "RenderContext", operation: "FigureOperation") -> None:
    """Draw one configured focal mechanism using the Aki strike/dip/rake convention."""
    options = dict(operation.options)
    options.pop("enabled", None)
    spec = {
        "strike": options.pop("strike"),
        "dip": options.pop("dip"),
        "rake": options.pop("rake"),
        "magnitude": options.pop("magnitude"),
    }
    kwargs = {
        "spec": spec,
        "longitude": options.pop("longitude"),
        "latitude": options.pop("latitude"),
        "depth": options.pop("depth_km"),
        "scale": options.pop("scale"),
        "compressionfill": options.pop("compressionfill", "black"),
        "extensionfill": options.pop("extensionfill", "white"),
        "pen": options.pop("pen", "1p,black"),
    }
    options.pop("label", None)
    kwargs.update(options)
    context.figure.meca(**kwargs)


def _map_center(context: "RenderContext", section: str) -> tuple[float, float]:
    """Return the active geographic center or fail for an inset before basemap."""
    if context.region is None:
        raise ValueError(f"[{section}] requires an earlier figure.basemap region")
    west, east, south, north = context.region
    return (west + east) / 2.0, (south + north) / 2.0


def render_globe_inset(context: "RenderContext", operation: "FigureOperation") -> None:
    """Draw a global orthographic locator and mark the current map center."""
    options = dict(operation.options)
    options.pop("enabled", None)
    longitude, latitude = _map_center(context, operation.section)
    position = _inset_position(
        options.pop("position"), options.pop("width"), options.pop("height", None)
    )
    box = options.pop("box", False)
    highlight = options.pop("highlight")
    fill = options.pop("highlight_fill", "gray")
    land = options.pop("land", "gray90")
    water = options.pop("water", "white")
    show_grid = options.pop("show_grid", True)
    marker = _marker_options(options)
    with context.figure.inset(position=position, box=box):
        context.figure.coast(
            region="g",
            projection=f"G{longitude}/{latitude}/?",
            land=land,
            water=water,
            dcw=f"{highlight}+g{fill}",
            frame="g" if show_grid else None,
            shorelines="0.25p,gray60",
            area_thresh=5000,
        )
        context.figure.plot(x=longitude, y=latitude, **marker)


def render_regional_inset(context: "RenderContext", operation: "FigureOperation") -> None:
    """Draw selected DCW administrative regions and mark the current map center."""
    options = dict(operation.options)
    options.pop("enabled", None)
    longitude, latitude = _map_center(context, operation.section)
    position = _inset_position(
        options.pop("position"), options.pop("width"), options.pop("height", None)
    )
    box = options.pop("box", False)
    regions = options.pop("regions")
    buffer = options.pop("buffer", 3.0)
    land = options.pop("land", "gray90")
    water = options.pop("water", "white")
    highlight_fill = options.pop("highlight_fill", "gray")
    highlight_pen = options.pop("highlight_pen", "0.8p,white")
    marker = _marker_options(options)
    with context.figure.inset(position=position, box=box):
        context.figure.coast(
            region=f"{regions}+r{buffer}",
            projection="M?",
            land=land,
            water=water,
            borders=["1/0.1p,gray50", "2/0.1p,gray50"],
            dcw=f"{regions}+p{highlight_pen}+g{highlight_fill}",
            shorelines="0.1p,gray80",
            area_thresh=5000,
        )
        context.figure.plot(x=longitude, y=latitude, **marker)


def _legend_position(value: object, width: object | None) -> str:
    """Convert a short anchor into a legacy-compatible legend position string."""
    text = str(value)
    if len(text) == 2 and all(character in "TMBLCR" for character in text):
        text = f"J{text}+j{text}"
    if width and "+w" not in text:
        text += f"+w{width}"
    return text


def render_legend(context: "RenderContext", operation: "FigureOperation") -> None:
    """Render operation-contributed entries through a temporary GMT legend spec."""
    options = dict(operation.options)
    options.pop("enabled", None)
    mode = str(options.pop("mode", "automatic"))
    if mode != "automatic":
        raise ValueError(f"[{operation.section}] only mode=automatic is currently supported")
    position = _legend_position(options.pop("position"), options.pop("width", None))
    box_value = options.pop("box", True)
    padding = options.pop("padding", None)
    box = "+gwhite+p1p" if box_value is True else box_value
    if padding and isinstance(box, str):
        box += f"+c{padding}"
    font = options.pop("font", None)
    row_gap = options.pop("row_gap", None)
    geometry = {
        "symbol_offset": options.pop("symbol_offset", "0.3c"),
        "line_length": options.pop("line_length", "1.2c"),
        "front_spacing": options.pop("front_spacing", "0.4c"),
        "front_size": options.pop("front_size", "0.16c"),
        "text_offset": options.pop("text_offset", "1.5c"),
    }
    if not context.legend_items:
        context.warnings.append(f"[{operation.section}] skipped empty automatic legend")
        return
    descriptor = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".legend",
        prefix="geodesy_visualization_",
        encoding="utf-8",
        delete=False,
    )
    path = Path(descriptor.name)
    try:
        with descriptor:
            separator = f"\nG {row_gap}\n" if row_gap else "\n"
            descriptor.write(
                separator.join(
                    _legend_item_spec(item, geometry) for item in context.legend_items
                )
            )
            descriptor.write("\n")
        if font:
            from pygmt import config as pygmt_config

            with pygmt_config(FONT_ANNOT_PRIMARY=str(font)):
                context.figure.legend(spec=str(path), position=position, box=box, **options)
        else:
            context.figure.legend(spec=str(path), position=position, box=box, **options)
    finally:
        path.unlink(missing_ok=True)


CARTOGRAPHY_HANDLERS: dict[str, Callable] = {
    "footprint": render_footprint,
    "faults": render_faults,
    "meca": render_meca,
    "globe_inset": render_globe_inset,
    "regional_inset": render_regional_inset,
    "legend": render_legend,
}


__all__ = [
    "CARTOGRAPHY_HANDLERS",
    "render_faults",
    "render_footprint",
    "render_globe_inset",
    "render_legend",
    "render_meca",
    "render_regional_inset",
]
