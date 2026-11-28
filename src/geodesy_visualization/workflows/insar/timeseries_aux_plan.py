"""
geodesy_visualization.workflows.insar.timeseries_aux_plan
========================================================

功能概述:
    将辅助时序 cfg 和四套日期序列编译为一个 Cartesian PanelPlan，显式保留
    三套 Y 轴、两级时间轴、四个数据图层、可选图例和原子输出。

函数说明:
    ``compile_aux_timeseries``:
        编译辅助时序图的整图设置、单面板图层和输出计划。
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

import pandas as pd

from geodesy_visualization.figure_ops.model import (
    FigurePlan,
    LayerOperation,
    PanelPlan,
)


def _layer(
    section: str,
    handler: str,
    options: dict[str, object],
    order: int,
) -> LayerOperation:
    """Create one immutable auxiliary time-series layer."""
    tokens = section.split(".")
    return LayerOperation(
        section=section,
        method=tokens[1],
        semantics=tuple(tokens[2:]),
        options=MappingProxyType(options),
        order=order,
        handler=handler,
    )


def compile_aux_timeseries(
    cfg: dict[str, object],
    series: dict[str, pd.DataFrame],
) -> FigurePlan:
    """Compile all axes and series into one direct Cartesian panel plan."""
    start = pd.to_datetime(cfg["date_start"], format="%Y%m%d")
    end = pd.to_datetime(cfg["date_end"], format="%Y%m%d")
    projection = str(cfg["projection"])
    layers: list[LayerOperation] = []

    def add(section: str, handler: str, options: dict[str, object]) -> None:
        """Append one layer with deterministic order."""
        layers.append(_layer(section, handler, options, len(layers)))

    add(
        "figure.basemap.temperature_axis",
        "aux_axis",
        {
            "variant": "temperature",
            "date_range": (start, end),
            "range": tuple(cfg["temperature_range"]),
            "frame": cfg["temperature_y_frame"],
            "axis_label": cfg["temperature_label"],
            "font_annot_primary": cfg["temperature_font_annot_primary"] or cfg["temperature_color"],
            "font_label": cfg["temperature_font_label"] or cfg["temperature_color"],
            "annot_offset": cfg["temperature_annot_offset"],
        },
    )
    add(
        "figure.plot.temperature",
        "aux_series",
        {
            "variant": "line",
            "dates": series["temperature"]["date"],
            "values": series["temperature"]["value"],
            "range": tuple(cfg["temperature_range"]),
            "date_range": (start, end),
            "pen": cfg["temperature_pen"],
            "style": "",
            "fill": "",
            "label": cfg["temperature_legend_label"],
        },
    )
    add(
        "figure.basemap.precipitation_axis",
        "aux_axis",
        {
            "variant": "precipitation",
            "date_range": (start, end),
            "range": tuple(cfg["precip_range"]),
            "frame": cfg["precip_y_frame"],
            "axis_label": cfg["precip_label"],
            "font_annot_primary": cfg["precip_font_annot_primary"] or cfg["precip_color"],
            "font_label": cfg["precip_font_label"] or cfg["precip_color"],
            "annot_offset": cfg["precip_annot_offset"],
        },
    )
    add(
        "figure.plot.precipitation",
        "aux_series",
        {
            "variant": "line",
            "dates": series["precipitation"]["date"],
            "values": series["precipitation"]["value"],
            "range": tuple(cfg["precip_range"]),
            "date_range": (start, end),
            "pen": cfg["precip_pen"],
            "style": "",
            "fill": "",
            "label": cfg["precip_legend_label"],
        },
    )
    add(
        "figure.basemap.deformation_primary_axis",
        "aux_axis",
        {
            "variant": "deformation_primary",
            "date_range": (start, end),
            "range": tuple(cfg["defo_range"]),
            "frame": cfg["x_primary_frame"],
            "axis_label": cfg["defo_label"],
            "color": cfg["defo_color"],
            "font": cfg["primary_time_font"],
        },
    )
    add(
        "figure.basemap.deformation_secondary_axis",
        "aux_axis",
        {
            "variant": "deformation_secondary",
            "date_range": (start, end),
            "range": tuple(cfg["defo_range"]),
            "frame": cfg["x_secondary_frame"],
            "axis_label": cfg["defo_label"],
            "y_frame": cfg["defo_y_frame"],
            "time_label": cfg["time_label"],
            "title": cfg["title"],
            "secondary_tick_length": cfg["secondary_tick_length"],
            "secondary_annot_offset": cfg["secondary_annot_offset"],
        },
    )
    add(
        "figure.plot.deformation",
        "aux_series",
        {
            "variant": "point",
            "dates": series["deformation"]["date"],
            "values": series["deformation"]["value"],
            "range": tuple(cfg["defo_range"]),
            "date_range": (start, end),
            "pen": cfg["defo_pen"],
            "style": cfg["defo_symbol"],
            "fill": cfg["defo_color"],
            "label": cfg["defo_legend_label"],
        },
    )
    add(
        "figure.plot.fit",
        "aux_series",
        {
            "variant": "line",
            "dates": series["fit"]["date"],
            "values": series["fit"]["value"],
            "range": tuple(cfg["defo_range"]),
            "date_range": (start, end),
            "pen": cfg["fit_pen"],
            "style": "",
            "fill": "",
            "label": cfg["fit_legend_label"],
        },
    )
    add(
        "figure.legend.auxiliary",
        "aux_legend",
        {
            "enabled": cfg["add_legend"],
            "position": cfg["legend_position"],
            "font": cfg["legend_font"],
            "box": cfg["legend_box"],
        },
    )
    panel = PanelPlan(
        identifier="main",
        region=None,
        projection=projection,
        layers=tuple(layers),
    )
    setup = _layer(
        "figure.setup.auxiliary",
        "aux_setup",
        {"defaults": cfg["defaults"]},
        0,
    )
    save = _layer(
        "figure.savefig",
        "savefig",
        {"fname": cfg["output"], "dpi": cfg["output_dpi"]},
        0,
    )
    return FigurePlan(
        config_path=Path(str(cfg["config_path"])),
        project=MappingProxyType({"output_dir": str(cfg["output_dir"])}),
        figure=MappingProxyType({"layout": "cartesian"}),
        operations=(setup,),
        panels=(panel,),
        figure_layers=(save,),
    )


__all__ = ["compile_aux_timeseries"]
