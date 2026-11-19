"""
geodesy_visualization.workflows.insar.timeseries_map_plan
========================================================

功能概述:
    将空间时序宽表和紧凑 cfg 编译为一张带多个 PanelPlan 的 FigurePlan，
    共享 CPT、subplot 几何和最终色标。

函数说明:
    ``compile_timeseries_map``:
        按选定时期顺序生成 subplot、panel layers、共享色标和输出图层。
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

from geodesy_visualization.figure_ops.model import (
    FigurePlan,
    LayerOperation,
    PanelPlan,
)


def _projected_panel_size(region: list[float], projection: str) -> tuple[str, str]:
    """Reuse the workflow's GMT projection-size calculation at compile time."""
    from geodesy_visualization.workflows.insar.timeseries_map import (
        _projected_panel_size as calculate,
    )

    return calculate(region, projection)


def _layer(
    section: str,
    handler: str,
    options: dict[str, object],
    order: int,
) -> LayerOperation:
    """Create one immutable time-series layer."""
    tokens = section.split(".")
    return LayerOperation(
        section=section,
        method=tokens[1],
        semantics=tuple(tokens[2:]),
        options=MappingProxyType(options),
        order=order,
        handler=handler,
    )


def _fonts(cfg: dict[str, object], panel_width: str) -> dict[str, str]:
    """Calculate every responsive font once for the whole subplot figure."""
    from geodesy_visualization.workflows.insar.timeseries_map import _scaled_font

    bold = bool(cfg["font_bold"])
    return {
        "title": _scaled_font(
            float(cfg["panel_title_font_size"]), cfg, panel_width, bold=bold
        ),
        "tag": _scaled_font(
            float(cfg["panel_number_font_size"]), cfg, panel_width, bold=bold
        ),
        "coordinate": _scaled_font(
            float(cfg["coordinate_font_size"]), cfg, panel_width, bold=bold
        ),
        "colorbar_annotation": _scaled_font(
            float(cfg["colorbar_annotation_font_size"]),
            cfg,
            panel_width,
            bold=bold,
        ),
        "colorbar_label": _scaled_font(
            float(cfg["colorbar_label_font_size"]), cfg, panel_width, bold=bold
        ),
    }


def compile_timeseries_map(
    cfg: dict[str, object],
    epochs: tuple[object, object, object, list[str]],
) -> FigurePlan:
    """Compile selected epoch arrays into one shared-CPT subplot figure plan."""
    import numpy as np

    longitude, latitude, values, dates = epochs
    values_array = np.asarray(values)
    if values_array.ndim != 2 or values_array.shape[1] != len(dates):
        raise ValueError("time-series epoch values must match the selected dates")
    panel_width, panel_height = _projected_panel_size(
        list(cfg["region"]), str(cfg["projection"])
    )
    fonts = _fonts(cfg, panel_width)
    subplot: dict[str, object] = {
        "nrows": int(cfg["rows"]),
        "ncols": int(cfg["columns"]),
        "subsize": (panel_width, panel_height),
        "region": cfg["region"],
        "projection": str(cfg["projection"]),
        "margins": [str(cfg["panel_margin_x"]), str(cfg["panel_margin_y"])],
    }
    if cfg["show_panel_number"]:
        subplot["autolabel"] = f"{cfg['panel_number_style']}+jTL+o8p/8p+gwhite@70"

    setup = _layer(
        "figure.setup.timeseries",
        "timeseries_setup",
        {
            "defaults": cfg["defaults"],
            "tag_font": fonts["tag"],
            "cpt": cfg["cpt"],
            "series": (cfg["bar_min"], cfg["bar_max"], cfg["bar_step"]),
            "reverse": cfg["cpt_reverse"],
            "continuous": True,
            "title_font": fonts["title"],
        },
        0,
    )

    from geodesy_visualization.workflows.insar.timeseries_map import _format_panel_title

    panels: list[PanelPlan] = []
    for index, date in enumerate(dates):
        row, column = divmod(index, int(cfg["columns"]))
        mode = str(cfg["coordinate_mode"])
        show_x = mode == "all" or (
            mode == "outer" and row == int(cfg["rows"]) - 1
        )
        show_y = mode == "all" or (mode == "outer" and column == 0)
        layers = (
            _layer(
                f"figure.basemap.epoch_{index + int(cfg['start_epoch']):03d}",
                "timeseries_frame",
                {
                    "region": tuple(cfg["region"]),
                    "projection": cfg["projection"],
                    "title": _format_panel_title(date, cfg),
                    "show_title": cfg["show_panel_title"],
                    "show_x": show_x,
                    "show_y": show_y,
                    "longitude_interval": cfg["longitude_interval"],
                    "latitude_interval": cfg["latitude_interval"],
                    "show_grid": cfg["show_coordinate_grid"],
                    "coordinate_format": cfg["coordinate_format"],
                    "title_font": fonts["title"],
                    "coordinate_font": fonts["coordinate"],
                },
                0,
            ),
            _layer(
                f"figure.grdimage.background.epoch_{index + int(cfg['start_epoch']):03d}",
                "timeseries_background",
                {
                    "mode": cfg["basemap_mode"],
                    "tif": cfg["basemap_tif"],
                    "dem_cpt": cfg["dem_cpt"],
                    "dem_min": cfg["dem_bar_min"],
                    "dem_max": cfg["dem_bar_max"],
                },
                1,
            ),
            _layer(
                f"figure.plot.epoch_{index + int(cfg['start_epoch']):03d}",
                "timeseries_epoch",
                {
                    "longitude": longitude,
                    "latitude": latitude,
                    "values": values_array[:, index],
                    "style": cfg["point_style"],
                    "pen": cfg["point_pen"],
                    "date": date,
                },
                2,
            ),
        )
        panels.append(
            PanelPlan(
                identifier=index,
                region=tuple(cfg["region"]),
                projection=str(cfg["projection"]),
                layers=layers,
            )
        )

    colorbar = _layer(
        "figure.colorbar.timeseries",
        "timeseries_colorbar",
        {
            "enabled": cfg["add_colorbar"],
            "label": cfg["colorbar_label"],
            "unit": cfg["colorbar_unit"],
            "interval": cfg["colorbar_interval"],
            "width": cfg["colorbar_width"],
            "height": cfg["colorbar_height"],
            "offset": cfg["colorbar_offset"],
            "box": cfg["colorbar_box"],
            "annotation_font": fonts["colorbar_annotation"],
            "label_font": fonts["colorbar_label"],
        },
        0,
    )
    save = _layer(
        "figure.savefig",
        "savefig",
        {
            "fname": cfg["output"],
            "dpi": cfg["output_dpi"],
            "canvas_margin": cfg["canvas_margin"],
        },
        1,
    )
    return FigurePlan(
        config_path=Path(str(cfg["config_path"])),
        project=MappingProxyType({"output_dir": str(cfg["output_dir"])}),
        figure=MappingProxyType(
            {
                "layout": "subplot",
                "subplot": MappingProxyType(subplot),
                "epoch_range": (cfg["start_epoch"], cfg["end_epoch"]),
            }
        ),
        operations=(setup,),
        panels=tuple(panels),
        figure_layers=(colorbar, save),
    )


__all__ = ["compile_timeseries_map"]
