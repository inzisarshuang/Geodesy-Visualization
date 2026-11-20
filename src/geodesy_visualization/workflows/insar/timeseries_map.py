"""
geodesy_visualization.workflows.insar.timeseries_map
==================================================

功能概述:
    读取上游已导出的 lon/lat/多期形变标准宽表，通过 cfg 生成地理
    坐标系散点时序子图。Defsour、canonical HDF5 与其他处理格式应先在
    envInSAR 中由 Geodesy-DataAdapter 导出为绘图交换产品。

函数说明:
    ``build_parser``: 构建 cfg 命令行入口。
    ``load_config``: 读取并校验空间时序图配置。
    ``load_timeseries_table``: 分块读取坐标和所选时序列。
    ``compile_timeseries_map``: 将所选时期编译为共享 CPT 的 PanelPlan。
    ``main``: 执行配置加载、数据读取和绘图。
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from geodesy_visualization.io import (
    get_optional,
    get_required,
    load_key_value_config,
    parse_bool,
    parse_choice,
    parse_float,
    parse_int,
    parse_csv_strings,
    resolve_output_path,
    resolve_publication_output_dir,
    resolve_project_dir,
    resolve_path,
    validate_config_keys,
    validate_numeric_range,
)
from geodesy_visualization.resources import resource_path
from geodesy_visualization.styles import (
    colorbar_metadata_keys,
    font_style_keys,
    parse_colorbar_metadata,
    parse_font_style,
    resolve_cpt_reference,
)
from geodesy_visualization.figure_ops.executor import FigureExecutor
from geodesy_visualization.workflows.insar.timeseries_map_plan import (
    compile_timeseries_map,
)


DEFAULT_CONFIG = resource_path(
    "config_examples", "timeseries_map", "timeseries_map.cfg"
)


ALLOWED_KEYS = {
    "project_root", "project", "processing_root",
    "data_source", "render_mode", "data_file", "dates_file",
    "output_dir", "output_file", "region_west", "region_east",
    "region_south", "region_north", "projection", "subplot_rows", "subplot_columns",
    "panel_margin_x", "panel_margin_y", "canvas_margin", "start_epoch", "end_epoch",
    "data_scale", "bar_min",
    "bar_max", "bar_step", "cpt", "cpt_reverse", "point_style", "point_pen",
    "basemap_mode", "basemap_tif", "dem_cpt", "dem_bar_min", "dem_bar_max",
    "title_prefix", "title_date_format", "show_panel_title", "show_panel_number",
    "panel_number_style", "coordinate_mode", "longitude_interval", "latitude_interval",
    "coordinate_format", "show_coordinate_grid", "font_reference_panel_width",
    "font_scale", "font_family", "font_bold", "panel_title_font_size", "panel_number_font_size",
    "coordinate_font_size", "colorbar_annotation_font_size", "colorbar_label_font_size",
    "chunk_rows", "nan_tokens", "colorbar_interval",
    "colorbar_width", "colorbar_height", "colorbar_offset", "colorbar_box",
    "output_dpi",
}
ALLOWED_KEYS.update(colorbar_metadata_keys())
ALLOWED_KEYS.update(font_style_keys("default", include_secondary=True))


def build_parser() -> argparse.ArgumentParser:
    """Build the configuration-only command-line interface."""
    parser = argparse.ArgumentParser(description="Plot multi-epoch deformation map panels.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--dry-run", action="store_true")
    return parser


def load_config(config_file: str) -> dict[str, object]:
    """Load and normalize one spatial time-series plotting configuration."""
    path = Path(config_file).expanduser().resolve()
    raw = load_key_value_config(str(path))
    validate_config_keys(raw, ALLOWED_KEYS, str(path))
    base = resolve_project_dir(raw, path)
    output_dir = str(
        resolve_publication_output_dir(raw, path, "timeseries_map")
    )
    region = [
        parse_float(get_required(raw, "region_west"), 0.0),
        parse_float(get_required(raw, "region_east"), 0.0),
        parse_float(get_required(raw, "region_south"), 0.0),
        parse_float(get_required(raw, "region_north"), 0.0),
    ]
    validate_numeric_range(region[0], region[1], "region_west", "region_east")
    validate_numeric_range(region[2], region[3], "region_south", "region_north")
    cpt = resolve_cpt_reference(get_optional(raw, "cpt", "jet"), base)
    data_source = parse_choice(
        get_optional(raw, "data_source", "table"), ("table",), "data_source"
    )
    render_mode = parse_choice(
        get_optional(raw, "render_mode", "scatter"), ("scatter",), "render_mode"
    )
    dates_value = get_optional(raw, "dates_file", "")
    if not dates_value:
        raise ValueError("dates_file is required for the visualization exchange table")
    cfg = {
        "config_path": str(path),
        "output_dir": output_dir,
        "data_source": data_source,
        "render_mode": render_mode,
        "data_file": resolve_path(get_required(raw, "data_file"), base),
        "dates_file": resolve_path(dates_value, base) if dates_value else "",
        "output": resolve_output_path(get_optional(raw, "output_file", "deformation_timeseries_map.png"), output_dir, base),
        "region": region,
        "projection": get_optional(raw, "projection", "M4i"),
        "rows": parse_int(get_optional(raw, "subplot_rows", ""), 3),
        "columns": parse_int(get_optional(raw, "subplot_columns", ""), 4),
        "panel_margin_x": get_optional(raw, "panel_margin_x", "20p"),
        "panel_margin_y": get_optional(raw, "panel_margin_y", "35p"),
        "canvas_margin": get_optional(raw, "canvas_margin", "0.35c"),
        "start_epoch": parse_int(get_optional(raw, "start_epoch", ""), 1),
        "end_epoch": parse_int(get_optional(raw, "end_epoch", ""), 12),
        "scale": parse_float(get_optional(raw, "data_scale", ""), 1.0),
        "bar_min": parse_float(get_optional(raw, "bar_min", ""), -35.0),
        "bar_max": parse_float(get_optional(raw, "bar_max", ""), 35.0),
        "bar_step": parse_float(get_optional(raw, "bar_step", ""), 5.0),
        "cpt": cpt,
        "cpt_reverse": parse_bool(get_optional(raw, "cpt_reverse", ""), True),
        "point_style": get_optional(raw, "point_style", "c2.5p"),
        "point_pen": get_optional(raw, "point_pen", ""),
        "basemap_mode": parse_choice(get_optional(raw, "basemap_mode", "none"), ("none", "dem", "optic"), "basemap_mode"),
        "basemap_tif": resolve_path(get_optional(raw, "basemap_tif", ""), base) if get_optional(raw, "basemap_tif", "") else "",
        "dem_cpt": get_optional(raw, "dem_cpt", "gray"),
        "dem_bar_min": parse_float(get_optional(raw, "dem_bar_min", ""), -250.0),
        "dem_bar_max": parse_float(get_optional(raw, "dem_bar_max", ""), 3500.0),
        "title_prefix": get_optional(raw, "title_prefix", ""),
        "title_date_format": get_optional(raw, "title_date_format", "%Y-%m-%d"),
        "show_panel_title": parse_bool(get_optional(raw, "show_panel_title", ""), True),
        "show_panel_number": parse_bool(get_optional(raw, "show_panel_number", ""), True),
        "panel_number_style": get_optional(raw, "panel_number_style", "(1)"),
        "coordinate_mode": parse_choice(
            get_optional(raw, "coordinate_mode", "outer"),
            ("none", "outer", "all"),
            "coordinate_mode",
        ),
        "longitude_interval": parse_float(
            get_optional(raw, "longitude_interval", ""), 0.03
        ),
        "latitude_interval": parse_float(
            get_optional(raw, "latitude_interval", ""), 0.02
        ),
        "coordinate_format": get_optional(raw, "coordinate_format", "ddd:mm"),
        "show_coordinate_grid": parse_bool(
            get_optional(raw, "show_coordinate_grid", ""), False
        ),
        "font_reference_panel_width": get_optional(
            raw, "font_reference_panel_width", "400p"
        ),
        "font_scale": parse_float(get_optional(raw, "font_scale", ""), 1.0),
        "font_family": get_optional(raw, "font_family", "TeX Gyre Heros"),
        "font_bold": parse_bool(get_optional(raw, "font_bold", ""), False),
        "panel_title_font_size": parse_float(
            get_optional(raw, "panel_title_font_size", ""), 18.0
        ),
        "panel_number_font_size": parse_float(
            get_optional(raw, "panel_number_font_size", ""), 20.0
        ),
        "coordinate_font_size": parse_float(
            get_optional(raw, "coordinate_font_size", ""), 13.0
        ),
        "colorbar_annotation_font_size": parse_float(
            get_optional(raw, "colorbar_annotation_font_size", ""), 14.0
        ),
        "colorbar_label_font_size": parse_float(
            get_optional(raw, "colorbar_label_font_size", ""), 16.0
        ),
        "chunk_rows": parse_int(get_optional(raw, "chunk_rows", ""), 250_000),
        "nan_tokens": parse_csv_strings(get_optional(raw, "nan_tokens", "nan,NaN,-9999")),
        **parse_colorbar_metadata(
            raw,
            "",
            enabled=parse_bool(get_optional(raw, "add_colorbar", ""), True),
            default_label="Deformation",
            default_unit="mm",
        ),
        "colorbar_interval": parse_float(
            get_optional(raw, "colorbar_interval", ""), 10.0
        ),
        "colorbar_width": get_optional(raw, "colorbar_width", "14c"),
        "colorbar_height": get_optional(raw, "colorbar_height", "0.5c"),
        "colorbar_offset": get_optional(raw, "colorbar_offset", "0c/0.9c"),
        "colorbar_box": get_optional(raw, "colorbar_box", "F+gwhite+p1p+c10p/8p"),
        "output_dpi": parse_int(get_optional(raw, "output_dpi", ""), 600),
        "defaults": parse_font_style(
            raw,
            "default",
            "16p,TeX Gyre Heros-Bold",
            "10p,TeX Gyre Heros",
            "12p,TeX Gyre Heros",
            default_secondary="10p,TeX Gyre Heros",
        ),
    }
    if cfg["rows"] < 1 or cfg["columns"] < 1 or cfg["chunk_rows"] < 1:
        raise ValueError("subplot dimensions and chunk_rows must be positive")
    for key in (
        "longitude_interval", "latitude_interval", "colorbar_interval", "font_scale",
        "panel_title_font_size", "panel_number_font_size", "coordinate_font_size",
        "colorbar_annotation_font_size", "colorbar_label_font_size",
    ):
        if cfg[key] <= 0:
            raise ValueError(f"{key} must be positive")
    if cfg["output_dpi"] <= 0:
        raise ValueError("output_dpi must be positive")
    if cfg["start_epoch"] < 1 or cfg["end_epoch"] < cfg["start_epoch"]:
        raise ValueError("epochs use one-based indexing and require end_epoch >= start_epoch")
    if cfg["end_epoch"] - cfg["start_epoch"] + 1 > cfg["rows"] * cfg["columns"]:
        raise ValueError("subplot layout has fewer panels than selected epochs")
    if cfg["basemap_mode"] != "none" and not cfg["basemap_tif"]:
        raise ValueError("basemap_tif is required for DEM or optical basemap mode")
    validate_numeric_range(cfg["bar_min"], cfg["bar_max"], "bar_min", "bar_max")
    return cfg


def load_timeseries_table(
    data_file: str,
    dates_file: str,
    start_epoch: int,
    end_epoch: int,
    scale: float,
    chunk_rows: int,
    nan_tokens: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Load a named wide table and verify every epoch column against its date."""
    date_table = pd.read_csv(dates_file, sep=r"\s+", dtype=str)
    if date_table.columns.tolist() != ["epoch_index", "date_yyyymmdd"]:
        raise ValueError(
            "dates table must contain 'epoch_index date_yyyymmdd' columns: "
            f"{dates_file}"
        )
    epoch_indices = pd.to_numeric(date_table["epoch_index"], errors="raise").tolist()
    expected_indices = list(range(1, len(date_table) + 1))
    if epoch_indices != expected_indices:
        raise ValueError(f"epoch_index must be consecutive and one-based: {dates_file}")
    dates = date_table["date_yyyymmdd"].tolist()
    if not dates or any(
        pd.isna(pd.to_datetime(date, format="%Y%m%d", errors="coerce"))
        for date in dates
    ):
        raise ValueError(f"dates table contains an invalid YYYYMMDD value: {dates_file}")
    expected_columns = [
        "longitude_deg",
        "latitude_deg",
        *(
            f"epoch_{epoch:03d}_deformation_{date}_mm"
            for epoch, date in zip(epoch_indices, dates)
        ),
    ]
    actual_columns = pd.read_csv(data_file, sep=r"\s+", nrows=0).columns.tolist()
    if actual_columns != expected_columns:
        raise ValueError(
            "time-series columns must be longitude_deg, latitude_deg, then one "
            "epoch_NNN_deformation_YYYYMMDD_mm column per dates-table row"
        )
    if end_epoch > len(dates):
        raise ValueError(f"end_epoch={end_epoch} exceeds {len(dates)} dates")
    columns = [
        "longitude_deg",
        "latitude_deg",
        *expected_columns[start_epoch + 1 : end_epoch + 2],
    ]
    chunks = []
    for chunk in pd.read_csv(
        data_file,
        sep=r"\s+",
        usecols=columns,
        chunksize=chunk_rows,
        na_values=nan_tokens,
    ):
        chunk = chunk.loc[:, columns].apply(pd.to_numeric, errors="raise")
        chunks.append(chunk.to_numpy(dtype=float))
    if not chunks:
        raise ValueError("time-series table contains no rows")
    table = np.concatenate(chunks, axis=0)
    values = table[:, 2:] * scale
    valid_coordinates = np.isfinite(table[:, 0]) & np.isfinite(table[:, 1])
    return table[valid_coordinates, 0], table[valid_coordinates, 1], values[valid_coordinates], dates[start_epoch - 1 : end_epoch]


def _length_to_points(value: str) -> float:
    """Convert a positive GMT length in points, centimeters, or inches to points."""
    text = value.strip().lower()
    factors = {"p": 1.0, "c": 72.0 / 2.54, "i": 72.0}
    if len(text) < 2 or text[-1] not in factors:
        raise ValueError(f"GMT length must end in p, c, or i: {value}")
    result = float(text[:-1]) * factors[text[-1]]
    if not np.isfinite(result) or result <= 0:
        raise ValueError(f"GMT length must be positive: {value}")
    return result


def _scaled_font(
    base_size: float,
    cfg: dict[str, object],
    panel_width: str,
    bold: bool = False,
) -> str:
    """Scale one configured base font by panel width and the global font multiplier."""
    width_factor = _length_to_points(panel_width) / _length_to_points(
        str(cfg["font_reference_panel_width"])
    )
    size = base_size * float(cfg["font_scale"]) * width_factor
    family = str(cfg["font_family"])
    if bold:
        family = f"{family}-Bold"
    return f"{size:.4g}p,{family},black"


def _format_panel_title(date: str, cfg: dict[str, object]) -> str:
    """Format one YYYYMMDD epoch using the configured strftime representation."""
    formatted = pd.to_datetime(date, format="%Y%m%d", errors="raise").strftime(
        str(cfg["title_date_format"])
    )
    return f"{cfg['title_prefix']}{formatted}"


def _projected_panel_size(region: list[float], projection: str) -> tuple[str, str]:
    """Ask GMT for the projected map width and height and return centimeter sizes."""
    environment_gmt = Path(sys.prefix) / "bin" / "gmt"
    executable = str(environment_gmt) if environment_gmt.is_file() else "gmt"
    region_argument = "/".join(str(value) for value in region)
    completed = subprocess.run(
        [executable, "mapproject", f"-R{region_argument}", f"-J{projection}", "-W"],
        check=True,
        capture_output=True,
        text=True,
    )
    dimensions = completed.stdout.split()
    if len(dimensions) != 2:
        raise ValueError(
            "GMT mapproject did not return projected width and height for "
            f"region={region}, projection={projection}: {completed.stdout!r}"
        )
    width, height = (float(value) for value in dimensions)
    if not np.isfinite(width) or not np.isfinite(height) or width <= 0 or height <= 0:
        raise ValueError(f"invalid projected panel dimensions: {width}, {height}")
    return f"{width:.8g}c", f"{height:.8g}c"


def main(arguments: Sequence[str] | None = None) -> None:
    """Load selected epochs, compile their panel plan, and execute one figure."""
    args = build_parser().parse_args(arguments)
    cfg = load_config(args.config)
    if args.dry_run:
        date_table = pd.read_csv(str(cfg["dates_file"]), sep=r"\s+", dtype=str)
        selected_dates = date_table["date_yyyymmdd"].tolist()[
            int(cfg["start_epoch"]) - 1 : int(cfg["end_epoch"])
        ]
        empty = np.empty((0,), dtype=float)
        epochs = (
            empty,
            empty,
            np.empty((0, len(selected_dates)), dtype=float),
            selected_dates,
        )
        plan = compile_timeseries_map(cfg, epochs)
        print(f"Panels: {len(plan.panels)}")
        for panel in plan.panels:
            print(f"  Panel {panel.identifier}: {panel.layers[-1].options['date']}")
        print(f"Output: {plan.figure_layers[-1].options['fname']}")
        return
    from geodesy_visualization.figure_ops.timeseries_layers import (
        TIMESERIES_HANDLERS,
    )

    data = load_timeseries_table(
        str(cfg["data_file"]), str(cfg["dates_file"]), int(cfg["start_epoch"]),
        int(cfg["end_epoch"]), float(cfg["scale"]), int(cfg["chunk_rows"]),
        list(cfg["nan_tokens"]),
    )
    plan = compile_timeseries_map(cfg, data)
    FigureExecutor(plan, handlers=TIMESERIES_HANDLERS).execute_plan()
    print(f"Saved: {cfg['output']}")


__all__ = [
    "ALLOWED_KEYS",
    "build_parser",
    "compile_timeseries_map",
    "load_config",
    "load_timeseries_table",
    "main",
]


if __name__ == "__main__":
    main()
