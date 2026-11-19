"""
geodesy_visualization.figure_ops.timeseries_layers
=================================================

功能概述:
    实现空间与辅助时序 FigurePlan 使用的共享 PyGMT 图层 handlers。

函数说明:
    ``render_timeseries_setup``:
        应用整图样式并创建共享连续 CPT。
    ``render_timeseries_frame`` / ``render_timeseries_background`` /
    ``render_timeseries_epoch``:
        绘制单个时期面板的边框、底图和散点形变。
    ``render_timeseries_colorbar``:
        在 subplot 结束后绘制共享色标。
    ``render_aux_setup`` / ``render_aux_axis`` / ``render_aux_series`` /
    ``render_aux_legend``:
        绘制辅助时序图的三套坐标轴、四个序列和可选图例。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from geodesy_visualization.backends.pygmt import PyGMTPlotter

if TYPE_CHECKING:
    from geodesy_visualization.figure_ops.executor import RenderContext
    from geodesy_visualization.figure_ops.model import LayerOperation


def _plotter(context: "RenderContext") -> PyGMTPlotter:
    """Bind canonical map primitives to the executor-owned Figure."""
    plotter = PyGMTPlotter()
    plotter.fig = context.figure
    return plotter


def render_timeseries_setup(
    context: "RenderContext", operation: "LayerOperation"
) -> None:
    """Apply figure defaults and build the continuous CPT exactly once."""
    options = dict(operation.options)
    import pygmt

    defaults = dict(options["defaults"])
    defaults["FONT_TAG"] = str(options["tag_font"])
    pygmt.config(**defaults)
    pygmt.makecpt(
        cmap=str(options["cpt"]),
        series=list(options["series"]),
        reverse=bool(options["reverse"]),
        continuous=bool(options["continuous"]),
    )
    context.figure_resources[operation.section] = {"cpt": options["cpt"]}


def render_timeseries_frame(
    context: "RenderContext", operation: "LayerOperation"
) -> None:
    """Draw one panel border, selected outer coordinates, and date title."""
    options = dict(operation.options)
    figure = context.figure
    region = tuple(options["region"])
    projection = str(options["projection"])
    figure.basemap(region=region, projection=projection, frame="0")
    if options["show_x"] or options["show_y"]:
        axes = ("W" if options["show_y"] else "") + (
            "S" if options["show_x"] else ""
        )
        frame = [axes]
        if options["show_x"]:
            interval = float(options["longitude_interval"])
            grid = f"g{interval:g}" if options["show_grid"] else ""
            frame.append(f"xaf{interval:g}{grid}")
        if options["show_y"]:
            interval = float(options["latitude_interval"])
            grid = f"g{interval:g}" if options["show_grid"] else ""
            frame.append(f"yaf{interval:g}{grid}")
        from pygmt import config as pygmt_config

        with pygmt_config(
            FONT_ANNOT_PRIMARY=str(options["coordinate_font"]),
            FORMAT_GEO_MAP=str(options["coordinate_format"]),
            MAP_FRAME_TYPE="plain",
            MAP_FRAME_PEN="0.7p,black",
        ):
            figure.basemap(region=region, projection=projection, frame=frame)
    west, east, south, north = region
    figure.plot(
        x=[west, east, east, west, west],
        y=[south, south, north, north, south],
        pen="0.7p,black",
    )
    if options["show_title"]:
        figure.text(
            x=(west + east) / 2,
            y=north,
            text=str(options["title"]),
            justify="BC",
            offset="0p/6p",
            no_clip=True,
            font=str(options["title_font"]),
        )


def render_timeseries_background(
    context: "RenderContext", operation: "LayerOperation"
) -> None:
    """Draw the optional optical or DEM background for one epoch panel."""
    options = dict(operation.options)
    plotter = _plotter(context)
    if options["mode"] == "optic":
        plotter.draw_optic(
            str(options["tif"]), list(context.region or ()), context.projection or ""
        )
    elif options["mode"] == "dem":
        plotter.draw_dem(
            str(options["tif"]),
            list(context.region or ()),
            context.projection or "",
            cpt=str(options["dem_cpt"]),
            bar_min=float(options["dem_min"]),
            bar_max=float(options["dem_max"]),
        )
    elif options["mode"] != "none":
        raise ValueError(f"[{operation.section}] unsupported background mode")


def render_timeseries_epoch(
    context: "RenderContext", operation: "LayerOperation"
) -> None:
    """Draw one selected epoch using the shared CPT and configured point style."""
    options = dict(operation.options)
    kwargs = {
        "x": options["longitude"],
        "y": options["latitude"],
        "fill": options["values"],
        "cmap": True,
        "style": str(options["style"]),
    }
    if options["pen"]:
        kwargs["pen"] = str(options["pen"])
    context.figure.plot(**kwargs)


def render_timeseries_colorbar(
    context: "RenderContext", operation: "LayerOperation"
) -> None:
    """Draw one shared horizontal colorbar after all epoch panels."""
    options = dict(operation.options)
    from pygmt import config as pygmt_config

    with pygmt_config(
        FONT_ANNOT_PRIMARY=str(options["annotation_font"]),
        FONT_ANNOT_SECONDARY=str(options["annotation_font"]),
        FONT_LABEL=str(options["label_font"]),
    ):
        context.figure.colorbar(
            cmap=True,
            position=(
                f"JBC+o{options['offset']}+w{options['width']}"
                f"/{options['height']}+h"
            ),
            frame=[
                f"xa{float(options['interval']):g}+l{options['label']}",
                f"y+l{options['unit']}",
            ],
            box=str(options["box"]),
        )


def render_aux_setup(context: "RenderContext", operation: "LayerOperation") -> None:
    """Apply the auxiliary figure's shared Cartesian typography and frame style."""
    from pygmt import config as pygmt_config

    pygmt_config(**dict(operation.options["defaults"]))


def render_aux_axis(context: "RenderContext", operation: "LayerOperation") -> None:
    """Draw one of the temperature, precipitation, or deformation axis variants."""
    options = dict(operation.options)
    region = [*options["date_range"], *options["range"]]
    projection = context.projection or ""
    variant = str(options["variant"])
    from pygmt import config as pygmt_config

    if variant == "temperature":
        with pygmt_config(
            FONT_LABEL=str(options["color"]),
            FONT_ANNOT_PRIMARY=str(options["color"]),
        ):
            context.figure.basemap(
                region=region,
                projection=projection,
                frame=["E", f"{options['frame']}+l{options['axis_label']}"],
            )
    elif variant == "precipitation":
        with pygmt_config(
            FONT_LABEL=str(options["color"]),
            FONT_ANNOT_PRIMARY=str(options["color"]),
            MAP_ANNOT_OFFSET_PRIMARY="1.4c",
        ):
            context.figure.basemap(
                region=region,
                projection=projection,
                frame=["E", f"{options['frame']}+l{options['axis_label']}"],
            )
    elif variant == "deformation_primary":
        with pygmt_config(FONT_ANNOT_PRIMARY=str(options["font"])):
            context.figure.basemap(
                region=region,
                projection=projection,
                frame=["WSrt", str(options["frame"])],
            )
    elif variant == "deformation_secondary":
        with pygmt_config(
            MAP_TICK_LENGTH_SECONDARY=str(options["secondary_tick_length"]),
            MAP_ANNOT_OFFSET_SECONDARY=str(options["secondary_annot_offset"]),
        ):
            context.figure.basemap(
                region=region,
                projection=projection,
                frame=[
                    "WSrt",
                    f"{options['frame']}+l{options['time_label']}",
                    f"{options['y_frame']}+l{options['axis_label']}",
                ],
            )
    else:
        raise ValueError(f"[{operation.section}] unsupported auxiliary axis")


def render_aux_series(context: "RenderContext", operation: "LayerOperation") -> None:
    """Draw one auxiliary line or deformation point series on its own Y range."""
    options = dict(operation.options)
    kwargs = {
        "x": options["dates"],
        "y": options["values"],
        "region": [*options["date_range"], *options["range"]],
        "projection": context.projection or "",
        "pen": str(options["pen"]),
        "label": str(options["label"]),
    }
    if options["variant"] == "point":
        kwargs["style"] = str(options["style"])
        kwargs["fill"] = str(options["fill"])
    elif options["variant"] != "line":
        raise ValueError(f"[{operation.section}] unsupported auxiliary series")
    context.figure.plot(**kwargs)


def render_aux_legend(context: "RenderContext", operation: "LayerOperation") -> None:
    """Draw the optional combined auxiliary-series legend."""
    options = dict(operation.options)
    context.figure.legend(
        position=str(options["position"]),
        box=str(options["box"]),
    )


TIMESERIES_HANDLERS: dict[str, Callable] = {
    "timeseries_setup": render_timeseries_setup,
    "timeseries_frame": render_timeseries_frame,
    "timeseries_background": render_timeseries_background,
    "timeseries_epoch": render_timeseries_epoch,
    "timeseries_colorbar": render_timeseries_colorbar,
    "aux_setup": render_aux_setup,
    "aux_axis": render_aux_axis,
    "aux_series": render_aux_series,
    "aux_legend": render_aux_legend,
}


__all__ = [
    "TIMESERIES_HANDLERS",
    "render_aux_axis",
    "render_aux_legend",
    "render_aux_series",
    "render_aux_setup",
    "render_timeseries_background",
    "render_timeseries_colorbar",
    "render_timeseries_epoch",
    "render_timeseries_frame",
    "render_timeseries_setup",
]
