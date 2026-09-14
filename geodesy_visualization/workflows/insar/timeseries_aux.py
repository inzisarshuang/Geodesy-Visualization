"""
geodesy_visualization.workflows.insar.timeseries_aux
==================================================

功能概述:
    读取日期-数值表，通过共享时间轴叠加形变、拟合曲线、降水和温度序列。

函数说明:
    ``build_parser``: 构建 cfg 命令行入口。
    ``load_config``: 读取并校验组合时序图配置。
    ``read_date_value_table``: 严格读取两列日期-数值文本。
    ``render``: 绘制多纵轴时序图并安全保存。
    ``main``: 执行配置加载、数据读取和绘图。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import pygmt

from geodesy_visualization.io import (
    get_optional,
    get_required,
    load_key_value_config,
    parse_float,
    resolve_output_path,
    resolve_path,
    validate_config_keys,
    validate_numeric_range,
)
from geodesy_visualization.styles import parse_font_style
from geodesy_visualization.backends.pygmt import PyGMTPlotter


DEFAULT_CONFIG = (
    Path(__file__).resolve().parents[3]
    / "plot_defo_timeseries_aux"
    / "plot_defo_timeseries_aux.cfg"
)


ALLOWED_KEYS = {
    "deformation_file", "fit_file", "precipitation_file", "temperature_file", "output_dir",
    "output_file", "date_start", "date_end", "projection", "defo_min", "defo_max",
    "precip_min", "precip_max", "temperature_min", "temperature_max", "defo_color",
    "precip_color", "temperature_color", "defo_label", "precip_label", "temperature_label",
    "time_label", "defo_symbol", "defo_pen", "fit_pen", "precip_pen", "temperature_pen",
    "x_primary_frame", "x_secondary_frame", "defo_y_frame", "precip_y_frame",
    "temperature_y_frame", "default_font_title", "default_font_annot_primary",
    "default_font_label", "primary_time_font", "secondary_tick_length",
    "secondary_annot_offset",
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the configuration-only command-line interface."""
    parser = argparse.ArgumentParser(description="Plot deformation with weather auxiliary series.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    return parser


def load_config(config_file: str) -> dict[str, object]:
    """Load and normalize one Cartesian time-series plotting configuration."""
    path = Path(config_file).expanduser().resolve()
    raw = load_key_value_config(str(path))
    validate_config_keys(raw, ALLOWED_KEYS, str(path))
    base = path.parent
    output_dir = resolve_path(get_optional(raw, "output_dir", "result"), base)
    cfg = {
        "deformation_file": resolve_path(get_required(raw, "deformation_file"), base),
        "fit_file": resolve_path(get_required(raw, "fit_file"), base),
        "precipitation_file": resolve_path(get_required(raw, "precipitation_file"), base),
        "temperature_file": resolve_path(get_required(raw, "temperature_file"), base),
        "output": resolve_output_path(
            get_optional(raw, "output_file", "deformation_aux_timeseries.png"),
            output_dir,
            base,
        ),
        "date_start": get_required(raw, "date_start"),
        "date_end": get_required(raw, "date_end"),
        "projection": get_optional(raw, "projection", "X16c/5c"),
        "defo_range": [
            parse_float(get_optional(raw, "defo_min", ""), -15),
            parse_float(get_optional(raw, "defo_max", ""), 15),
        ],
        "precip_range": [
            parse_float(get_optional(raw, "precip_min", ""), 0),
            parse_float(get_optional(raw, "precip_max", ""), 120),
        ],
        "temperature_range": [
            parse_float(get_optional(raw, "temperature_min", ""), 0),
            parse_float(get_optional(raw, "temperature_max", ""), 40),
        ],
        "defo_color": get_optional(raw, "defo_color", "gray20"),
        "precip_color": get_optional(raw, "precip_color", "skyblue2"),
        "temperature_color": get_optional(raw, "temperature_color", "coral1"),
        "defo_label": get_optional(raw, "defo_label", "Deformation (mm)"),
        "precip_label": get_optional(raw, "precip_label", "Daily precipitation (mm)"),
        "temperature_label": get_optional(raw, "temperature_label", "Temperature (°C)"),
        "time_label": get_optional(raw, "time_label", "Time (yr)"),
        "defo_symbol": get_optional(raw, "defo_symbol", "t0.13c"),
        "defo_pen": get_optional(raw, "defo_pen", "0.5p,gray20"),
        "fit_pen": get_optional(raw, "fit_pen", "1p,gray20"),
        "precip_pen": get_optional(raw, "precip_pen", "0.04c,skyblue2"),
        "temperature_pen": get_optional(raw, "temperature_pen", "1p,coral1,-"),
        "x_primary_frame": get_optional(raw, "x_primary_frame", "pxa6Of3o"),
        "x_secondary_frame": get_optional(raw, "x_secondary_frame", "sxa1Y"),
        "defo_y_frame": get_optional(raw, "defo_y_frame", "ya10f5g10"),
        "precip_y_frame": get_optional(raw, "precip_y_frame", "ya30"),
        "temperature_y_frame": get_optional(raw, "temperature_y_frame", "ya10"),
        "primary_time_font": get_optional(raw, "primary_time_font", "6p,Helvetica"),
        "secondary_tick_length": get_optional(raw, "secondary_tick_length", "0p"),
        "secondary_annot_offset": get_optional(raw, "secondary_annot_offset", "18p"),
        "defaults": {
            **parse_font_style(
                raw,
                "default",
                "14p,Helvetica-Bold",
                "11p,Helvetica",
                "11p,Helvetica",
            ),
            "MAP_FRAME_TYPE": "plain",
            "MAP_FRAME_PEN": "0.8p,black",
        },
    }
    for label, value in (
        ("defo", cfg["defo_range"]),
        ("precip", cfg["precip_range"]),
        ("temperature", cfg["temperature_range"]),
    ):
        validate_numeric_range(value[0], value[1], f"{label}_min", f"{label}_max")
    if pd.to_datetime(cfg["date_start"], format="%Y%m%d") >= pd.to_datetime(
        cfg["date_end"], format="%Y%m%d"
    ):
        raise ValueError("date_start must be earlier than date_end")
    return cfg


# ---------------------------------------------------------------------------
# Input tables
# ---------------------------------------------------------------------------

def read_date_value_table(path: str, value_column: str) -> pd.DataFrame:
    """Read and validate one named YYYYMMDD/value table."""
    expected = ["date_yyyymmdd", value_column]
    table = pd.read_csv(path, sep=r"\s+", dtype=str)
    if table.columns.tolist() != expected:
        raise ValueError(
            f"date-value table must have columns {expected}, got "
            f"{table.columns.tolist()}: {path}"
        )
    table.columns = ["date", "value"]
    table["date"] = pd.to_datetime(table["date"].astype(str), format="%Y%m%d", errors="raise")
    table["value"] = pd.to_numeric(table["value"], errors="raise")
    if table.empty:
        raise ValueError(f"date-value table is empty: {path}")
    if table["date"].duplicated().any():
        raise ValueError(f"date-value table contains duplicate dates: {path}")
    return table.sort_values("date")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render(cfg: dict[str, object], series: dict[str, pd.DataFrame]) -> Path:
    """Render deformation, precipitation and temperature against a shared date axis."""
    plotter = PyGMTPlotter(defaults=cfg["defaults"])
    plotter.new()
    figure = plotter._require_figure()
    start = pd.to_datetime(cfg["date_start"], format="%Y%m%d")
    end = pd.to_datetime(cfg["date_end"], format="%Y%m%d")
    projection = str(cfg["projection"])

    # All layers use the same physical plot rectangle. Each layer temporarily
    # supplies its own Y range, so PyGMT can overlay three independent axes.
    # Temperature owns the inner east axis.
    temperature_region = [start, end, *cfg["temperature_range"]]
    with pygmt.config(
        FONT_LABEL=str(cfg["temperature_color"]),
        FONT_ANNOT_PRIMARY=str(cfg["temperature_color"]),
    ):
        figure.basemap(
            region=temperature_region,
            projection=projection,
            frame=["E", f"{cfg['temperature_y_frame']}+l{cfg['temperature_label']}"],
        )
    figure.plot(
        x=series["temperature"]["date"],
        y=series["temperature"]["value"],
        region=temperature_region,
        projection=projection,
        pen=str(cfg["temperature_pen"]),
    )

    # Precipitation uses a second east axis. The annotation offset moves this
    # scale outside the temperature scale instead of printing both in place.
    precipitation_region = [start, end, *cfg["precip_range"]]
    with pygmt.config(
        FONT_LABEL=str(cfg["precip_color"]),
        FONT_ANNOT_PRIMARY=str(cfg["precip_color"]),
        MAP_ANNOT_OFFSET_PRIMARY="1.4c",
    ):
        figure.basemap(
            region=precipitation_region,
            projection=projection,
            frame=["E", f"{cfg['precip_y_frame']}+l{cfg['precip_label']}"],
        )
    figure.plot(
        x=series["precipitation"]["date"],
        y=series["precipitation"]["value"],
        region=precipitation_region,
        projection=projection,
        pen=str(cfg["precip_pen"]),
    )

    # Deformation supplies the visible west axis and the two-level time axis.
    # The primary axis shows half-year dates. The secondary axis shows years;
    # its default GMT 15p tick is disabled to avoid the long vertical marks.
    deformation_region = [start, end, *cfg["defo_range"]]
    with pygmt.config(FONT_ANNOT_PRIMARY=str(cfg["primary_time_font"])):
        figure.basemap(
            region=deformation_region,
            projection=projection,
            frame=["WSrt", str(cfg["x_primary_frame"])],
        )
    with pygmt.config(
        MAP_TICK_LENGTH_SECONDARY=str(cfg["secondary_tick_length"]),
        MAP_ANNOT_OFFSET_SECONDARY=str(cfg["secondary_annot_offset"]),
    ):
        figure.basemap(
            region=deformation_region,
            projection=projection,
            frame=[
                "WSrt",
                f"{cfg['x_secondary_frame']}+l{cfg['time_label']}",
                f"{cfg['defo_y_frame']}+l{cfg['defo_label']}",
            ],
        )
    figure.plot(
        x=series["deformation"]["date"],
        y=series["deformation"]["value"],
        region=deformation_region,
        projection=projection,
        style=str(cfg["defo_symbol"]),
        fill=str(cfg["defo_color"]),
        pen=str(cfg["defo_pen"]),
    )
    figure.plot(
        x=series["fit"]["date"],
        y=series["fit"]["value"],
        region=deformation_region,
        projection=projection,
        pen=str(cfg["fit_pen"]),
    )

    destination = Path(str(cfg["output"]))
    plotter.save(str(destination))
    return destination


def main() -> None:
    """Load one cfg and render the four configured date-value series."""
    cfg = load_config(build_parser().parse_args().config)
    series = {
        "deformation": read_date_value_table(
            str(cfg["deformation_file"]), "deformation_mm"
        ),
        "fit": read_date_value_table(
            str(cfg["fit_file"]), "fitted_deformation_mm"
        ),
        "precipitation": read_date_value_table(
            str(cfg["precipitation_file"]), "precipitation_mm_per_day"
        ),
        "temperature": read_date_value_table(
            str(cfg["temperature_file"]), "temperature_celsius"
        ),
    }
    print(f"Saved: {render(cfg, series)}")


__all__ = [
    "ALLOWED_KEYS",
    "build_parser",
    "load_config",
    "main",
    "read_date_value_table",
    "render",
]


if __name__ == "__main__":
    main()
