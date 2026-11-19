"""
geodesy_visualization.figure_ops.profile_layers
===============================================

功能概述:
    实现 deformation-profile 的地图轨迹、标记和 Cartesian 剖面图层 handlers。

函数说明:
    ``render_profile_tracks`` / ``render_profile_marker``:
        在形变地图上绘制公共剖线和可选标记。
    ``render_profile_basemap`` / ``render_profile_series``:
        建立二维剖面坐标框并绘制折线或散点数据。
    ``render_profile_legend``:
        绘制剖面对比图图例。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from geodesy_visualization.backends.pygmt import PyGMTPlotter

if TYPE_CHECKING:
    from geodesy_visualization.figure_ops.executor import RenderContext
    from geodesy_visualization.figure_ops.model import LayerOperation


def _plotter(context: "RenderContext") -> PyGMTPlotter:
    """Bind canonical profile primitives to the executor-owned Figure."""
    plotter = PyGMTPlotter()
    plotter.fig = context.figure
    return plotter


def render_profile_tracks(context: "RenderContext", operation: "LayerOperation") -> None:
    """Draw named tracks in their preserved configuration order."""
    options = dict(operation.options)
    _plotter(context).draw_profile_tracks(
        tracks=dict(options["tracks"]),
        line_pen=str(options["line_pen"]),
        start_label_font=str(options["label_font"]),
        start_justify=str(options["start_justify"]),
        end_justify=str(options["end_justify"]),
        end_suffix=str(options["end_suffix"]),
    )


def render_profile_marker(context: "RenderContext", operation: "LayerOperation") -> None:
    """Draw the optional configured reference marker on a dataset map."""
    options = dict(operation.options)
    _plotter(context).add_marker(
        lon=float(options["longitude"]),
        lat=float(options["latitude"]),
        style=str(options["style"]),
        pen=str(options["pen"]),
        fill=options["fill"],
    )


def render_profile_basemap(context: "RenderContext", operation: "LayerOperation") -> None:
    """Apply profile typography and establish one Cartesian comparison frame."""
    options = dict(operation.options)
    from pygmt import config as pygmt_config

    pygmt_config(**dict(options["style"]))
    context.projection = str(options["projection"])
    _plotter(context).draw_math_basemap(
        profiles=list(options["profiles"]),
        title=str(options["title"]),
        x_label=str(options["x_label"]),
        y_label=str(options["y_label"]),
        padding=float(options["padding"]),
        projection=context.projection,
    )


def render_profile_series(context: "RenderContext", operation: "LayerOperation") -> None:
    """Draw one dataset as the configured line or scatter profile variant."""
    options = dict(operation.options)
    plotter = _plotter(context)
    if options["mode"] == "line":
        plotter.draw_line_2d(
            profile=options["profile"],
            label=str(options["label"]),
            pen=str(options["pen"]),
        )
    elif options["mode"] == "scatter":
        plotter.draw_scatter_2d(
            profile=options["profile"],
            label=str(options["label"]),
            style=str(options["style"]),
            pen=str(options["pen"]),
            fill=str(options["fill"]),
            transparency=int(options["transparency"]),
        )
    else:
        raise ValueError(f"[{operation.section}] unsupported profile mode")


def render_profile_legend(context: "RenderContext", operation: "LayerOperation") -> None:
    """Draw the configured dataset legend for one profile comparison."""
    options = dict(operation.options)
    _plotter(context).add_legend(
        position=str(options["position"]),
        box=str(options["box"]),
    )


PROFILE_HANDLERS: dict[str, Callable] = {
    "profile_tracks": render_profile_tracks,
    "profile_marker": render_profile_marker,
    "profile_basemap": render_profile_basemap,
    "profile_series": render_profile_series,
    "profile_legend": render_profile_legend,
}


__all__ = [
    "PROFILE_HANDLERS",
    "render_profile_basemap",
    "render_profile_legend",
    "render_profile_marker",
    "render_profile_series",
    "render_profile_tracks",
]
