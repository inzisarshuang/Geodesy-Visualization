"""
geodesy_visualization.figure_ops.deformation_layers
===================================================

功能概述:
    实现 deformation-map 编译计划使用的专用 PyGMT 图层 handler，复用正式
    PyGMTPlotter 绘图原语，同时由 FigureExecutor 管理顺序与原子输出。

函数说明:
    ``render_deformation_basemap`` / ``render_deformation_background``:
        建立地图范围与底图。
    ``render_deformation_data`` / ``render_deformation_targets``:
        绘制形变网格或散点以及目标区域标注。
    ``render_deformation_grid``:
        在栅格和形变图层之上叠加经纬格网。
    ``render_deformation_coverage``:
        绘制兼容 coverage 模式的影像 footprint 与 GNSS 点。
    ``render_deformation_colorbar`` / ``render_deformation_scale`` /
    ``render_deformation_rose``:
        绘制地图出版组件。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from geodesy_visualization.backends.pygmt import PyGMTPlotter

if TYPE_CHECKING:
    from geodesy_visualization.figure_ops.executor import RenderContext
    from geodesy_visualization.figure_ops.model import LayerOperation


def _plotter(context: "RenderContext") -> PyGMTPlotter:
    """Bind the canonical plotting primitives to the executor-owned Figure."""
    plotter = PyGMTPlotter()
    plotter.fig = context.figure
    return plotter


def render_deformation_basemap(
    context: "RenderContext", operation: "LayerOperation"
) -> None:
    """Resolve the map extent, apply visible style defaults, and draw its frame."""
    options = dict(operation.options)
    region = options["region"]
    if region is None:
        grid = str(options["region_grid"])
        if not grid:
            raise ValueError(f"[{operation.section}] requires an explicit region")
        from geodesy_visualization.geo import region_from_grd

        region = tuple(region_from_grd(grid))
    context.region = tuple(region)
    context.projection = str(options["projection"])
    from pygmt import config as pygmt_config

    style = dict(options["style"])
    pygmt_config(**style)
    _plotter(context).draw_geo_basemap(
        region=list(context.region),
        projection=context.projection,
        title=str(options["title"]),
        label_font=style.get("FONT_LABEL"),
        **options["map_frame"],
    )


def render_deformation_background(
    context: "RenderContext", operation: "LayerOperation"
) -> None:
    """Draw the selected DEM or optical background in the active map scope."""
    options = dict(operation.options)
    plotter = _plotter(context)
    region = list(context.region or ())
    projection = context.projection or ""
    if options["mode"] == "optic":
        plotter.draw_optic(str(options["optic_tif"]), region, projection)
    elif options["mode"] == "dem":
        plotter.draw_dem(
            str(options["dem_tif"]),
            region,
            projection,
            cpt=str(options["dem_cpt"]),
            bar_min=float(options["dem_min"]),
            bar_max=float(options["dem_max"]),
        )
    else:
        raise ValueError(f"[{operation.section}] unsupported background mode")


def render_deformation_data(
    context: "RenderContext", operation: "LayerOperation"
) -> None:
    """Draw one prepared deformation grid or scatter layer with optional KML clip."""
    options = dict(operation.options)
    from geodesy_visualization.workflows.insar.deformation_map import (
        clip_grid_with_kml,
        parse_kml_clip,
    )

    grid = str(options["grid"])
    clip_kml = str(options["clip_kml"])
    native_clip = getattr(context.figure, "clip", None)
    if clip_kml and callable(native_clip):
        x, y = parse_kml_clip(clip_kml)
        native_clip(x=x, y=y, region=context.region, projection=context.projection)
    elif clip_kml:
        grid = clip_grid_with_kml(grid, clip_kml)

    plotter = _plotter(context)
    common = {
        "data_grd": grid,
        "cpt": str(options["cpt"]),
        "region": list(context.region or ()),
        "projection": context.projection or "",
        "bar_min": float(options["minimum"]),
        "bar_max": float(options["maximum"]),
        "transparency": int(options["transparency"]),
        "cpt_reverse": bool(options["cpt_reverse"]),
    }
    try:
        if options["mode"] == "grd":
            plotter.draw_defo_grd(**common)
        elif options["mode"] == "scatter":
            plotter.draw_defo_scatter(
                **common,
                style=str(options["scatter_style"]),
                pen=str(options["scatter_pen"]),
            )
        else:
            raise ValueError(f"[{operation.section}] unsupported deformation mode")
    finally:
        if clip_kml and callable(native_clip):
            native_clip(c=True)


def render_deformation_targets(
    context: "RenderContext", operation: "LayerOperation"
) -> None:
    """Draw configured target ellipses, centers, and labels as one semantic layer."""
    options = dict(operation.options)
    if not options["targets"]:
        return
    import numpy as np

    theta = np.linspace(0, 2 * np.pi, 181)
    for target in options["targets"]:
        west, east = target["west"], target["east"]
        south, north = target["south"], target["north"]
        center_x = (west + east) / 2.0
        center_y = (south + north) / 2.0
        x = center_x + (east - west) / 2.0 * np.cos(theta)
        y = center_y + (north - south) / 2.0 * np.sin(theta)
        context.figure.plot(x=x, y=y, pen=options["pen"])
        context.figure.plot(
            x=[center_x],
            y=[center_y],
            style=options["center_style"],
            fill="black",
            pen="0.5p,white",
        )
        offset = float(options["label_offset"])
        position = target["label_position"]
        if position == "bottom":
            label_x, label_y, justify = center_x, south - offset, "TC"
        elif position == "right":
            label_x, label_y, justify = east + offset, center_y, "ML"
        elif position == "left":
            label_x, label_y, justify = west - offset, center_y, "MR"
        elif position in {"northeast", "ne"}:
            label_x, label_y, justify = east + offset, north + offset, "BL"
        else:
            label_x, label_y, justify = center_x, north + offset, "BC"
        context.figure.text(
            x=label_x,
            y=label_y,
            text=target["label"],
            font=options["label_font"],
            justify=justify,
        )


def render_deformation_coverage(
    context: "RenderContext", operation: "LayerOperation"
) -> None:
    """Draw coverage geometry and GNSS stations without owning input conversion."""
    options = dict(operation.options)
    from geodesy_visualization.workflows.insar.deformation_map import parse_kml_features

    pens = list(options["coverage_pen"])
    kml_files = list(options["coverage_kml"])
    if len(pens) not in {1, len(kml_files)}:
        raise ValueError("coverage_pen requires one value or one per coverage KML")
    for index, path in enumerate(kml_files):
        geometries, _ = parse_kml_features(str(path))
        pen = pens[0] if len(pens) == 1 else pens[index]
        for x, y in geometries:
            context.figure.plot(x=x, y=y, pen=pen)
    _, stations = parse_kml_features(str(options["gnss_kml"]))
    for station in stations:
        context.figure.plot(
            x=[station["x"]],
            y=[station["y"]],
            style=options["gnss_style"],
            fill="yellow",
            pen=options["gnss_pen"],
        )
        if options["gnss_labels"]:
            offset = float(options["gnss_label_offset"])
            context.figure.text(
                x=station["x"] + offset,
                y=station["y"] + offset,
                text=station["name"],
                font=options["gnss_label_font"],
                justify="BL",
            )


def render_deformation_grid(context: "RenderContext", operation: "LayerOperation") -> None:
    """Draw geographic gridlines above the map data."""
    options = dict(operation.options)
    options.pop("enabled", None)
    _plotter(context).draw_geo_grid(
        region=list(context.region or ()),
        projection=context.projection or "",
        **options,
    )


def render_deformation_colorbar(
    context: "RenderContext", operation: "LayerOperation"
) -> None:
    """Draw the configured deformation colorbar against the active CPT."""
    options = dict(operation.options)
    options.pop("enabled", None)
    _plotter(context).add_colorbar(**options)


def render_deformation_scale(
    context: "RenderContext", operation: "LayerOperation"
) -> None:
    """Draw the configured scale with all publication typography visible in CFG."""
    options = dict(operation.options)
    _plotter(context).add_scale(
        region=list(context.region or ()),
        projection=context.projection or "",
        map_scale=str(options["map_scale"]),
        box=str(options["box"]),
        scale_height=str(options["height"]),
        font_annot=str(options["font_annot"]),
        font_label=str(options["font_label"]),
    )


def render_deformation_rose(
    context: "RenderContext", operation: "LayerOperation"
) -> None:
    """Draw the standard directional rose in the active map scope."""
    options = dict(operation.options)
    options.pop("enabled", None)
    _plotter(context).add_rose(
        region=list(context.region or ()),
        projection=context.projection or "",
        **options,
    )


DEFORMATION_HANDLERS: dict[str, Callable] = {
    "deformation_basemap": render_deformation_basemap,
    "deformation_background": render_deformation_background,
    "deformation_data": render_deformation_data,
    "deformation_targets": render_deformation_targets,
    "deformation_coverage": render_deformation_coverage,
    "deformation_grid": render_deformation_grid,
    "deformation_colorbar": render_deformation_colorbar,
    "deformation_scale": render_deformation_scale,
    "deformation_rose": render_deformation_rose,
}


__all__ = [
    "DEFORMATION_HANDLERS",
    "render_deformation_background",
    "render_deformation_basemap",
    "render_deformation_colorbar",
    "render_deformation_coverage",
    "render_deformation_data",
    "render_deformation_grid",
    "render_deformation_rose",
    "render_deformation_scale",
    "render_deformation_targets",
]
