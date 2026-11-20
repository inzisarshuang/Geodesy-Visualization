"""
geodesy_visualization.workflows.insar.timeseries_aux
==================================================

功能概述:
    读取日期-数值表，通过共享时间轴叠加形变、拟合曲线、降水和温度序列。

函数说明:
    ``build_parser``: 构建 cfg 命令行入口。
    ``load_config``: 读取并校验组合时序图配置。
    ``read_date_value_table``: 严格读取两列日期-数值文本。
    ``load_series``: 读取配置指定的四套日期序列。
    ``main``: 编译 FigurePlan 并通过共享执行器绘图。
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from geodesy_visualization.io import (
    get_optional,
    get_required,
    load_key_value_config,
    parse_bool,
    parse_float,
    resolve_output_path,
    resolve_publication_output_dir,
    resolve_project_dir,
    resolve_path,
    validate_config_keys,
    validate_numeric_range,
)
from geodesy_visualization.resources import resource_path
from geodesy_visualization.styles import font_style_keys, parse_font_style
from geodesy_visualization.figure_ops.executor import FigureExecutor
from geodesy_visualization.workflows.insar.timeseries_aux_plan import (
    compile_aux_timeseries,
)


DEFAULT_CONFIG = resource_path(
    "config_examples", "timeseries_aux", "timeseries_aux.cfg"
)


ALLOWED_KEYS = {
    "project_root", "project", "processing_root",
    "deformation_file", "fit_file", "precipitation_file", "temperature_file", "output_dir",
    "output_file", "date_start", "date_end", "projection", "defo_min", "defo_max",
    "precip_min", "precip_max", "temperature_min", "temperature_max", "defo_color",
    "precip_color", "temperature_color", "defo_label", "precip_label", "temperature_label",
    "time_label", "defo_symbol", "defo_pen", "fit_pen", "precip_pen", "temperature_pen",
    "x_primary_frame", "x_secondary_frame", "defo_y_frame", "precip_y_frame",
    "temperature_y_frame", "primary_time_font", "secondary_tick_length",
    "secondary_annot_offset",
    "add_legend", "legend_position", "legend_box",
    "defo_legend_label", "fit_legend_label",
    "precip_legend_label", "temperature_legend_label",
}
ALLOWED_KEYS.update(font_style_keys("default"))


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the configuration-only command-line interface."""
    parser = argparse.ArgumentParser(description="Plot deformation with weather auxiliary series.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--dry-run", action="store_true")
    return parser


def load_config(config_file: str) -> dict[str, object]:
    """Load and normalize one Cartesian time-series plotting configuration."""
    path = Path(config_file).expanduser().resolve()
    raw = load_key_value_config(str(path))
    validate_config_keys(raw, ALLOWED_KEYS, str(path))
    base = resolve_project_dir(raw, path)
    output_dir = str(
        resolve_publication_output_dir(raw, path, "timeseries_aux")
    )
    cfg = {
        "config_path": str(path),
        "output_dir": output_dir,
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
        "primary_time_font": get_optional(raw, "primary_time_font", "6p,TeX Gyre Heros"),
        "secondary_tick_length": get_optional(raw, "secondary_tick_length", "0p"),
        "secondary_annot_offset": get_optional(raw, "secondary_annot_offset", "18p"),
        "add_legend": parse_bool(get_optional(raw, "add_legend", "false")),
        "legend_position": get_optional(raw, "legend_position", "JTR+o0.2c/0.2c"),
        "legend_box": get_optional(raw, "legend_box", "+gwhite+p0.8p"),
        "defo_legend_label": get_optional(raw, "defo_legend_label", "Deformation"),
        "fit_legend_label": get_optional(
            raw, "fit_legend_label", "Fitted deformation"
        ),
        "precip_legend_label": get_optional(
            raw, "precip_legend_label", "Precipitation"
        ),
        "temperature_legend_label": get_optional(
            raw, "temperature_legend_label", "Temperature"
        ),
        "defaults": {
            **parse_font_style(
                raw,
                "default",
                "14p,TeX Gyre Heros-Bold",
                "11p,TeX Gyre Heros",
                "11p,TeX Gyre Heros",
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


def load_series(cfg: dict[str, object]) -> dict[str, pd.DataFrame]:
    """Load the four named date/value tables required by one auxiliary plot."""
    return {
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


def main(arguments: Sequence[str] | None = None) -> None:
    """Compile one cfg and execute its ordered auxiliary time-series layers."""
    args = build_parser().parse_args(arguments)
    cfg = load_config(args.config)
    series = load_series(cfg)
    plan = compile_aux_timeseries(cfg, series)
    if args.dry_run:
        sections = [layer.section for layer in plan.panels[0].layers]
        print(f"dry-run: layers={sections} output={cfg['output']}")
        return
    from geodesy_visualization.figure_ops.timeseries_layers import (
        TIMESERIES_HANDLERS,
    )

    FigureExecutor(plan, handlers=TIMESERIES_HANDLERS).execute_plan()
    print(f"Saved: {cfg['output']}")


__all__ = [
    "ALLOWED_KEYS",
    "build_parser",
    "compile_aux_timeseries",
    "load_config",
    "load_series",
    "main",
    "read_date_value_table",
]


if __name__ == "__main__":
    main()
