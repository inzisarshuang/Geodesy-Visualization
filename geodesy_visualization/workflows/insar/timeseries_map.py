"""
geodesy_visualization.workflows.insar.timeseries_map
==================================================

功能概述:
    读取 lon/lat/多期形变宽表和日期列表，通过 cfg 生成地理坐标系时序子图。

函数说明:
    ``build_parser``: 构建 cfg 命令行入口。
    ``load_config``: 读取并校验空间时序图配置。
    ``load_timeseries_table``: 分块读取坐标和所选时序列。
    ``draw_panel_basemap``: 绘制空白、DEM 或光学底图。
    ``render``: 组合时序子图并安全保存。
    ``main``: 执行配置加载、数据读取和绘图。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pygmt

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
    resolve_path,
    validate_config_keys,
    validate_numeric_range,
)
from geodesy_visualization.backends.pygmt import PyGMTPlotter


DEFAULT_CONFIG = (
    Path(__file__).resolve().parents[3]
    / "plot_defo_timeseries_map"
    / "plot_defo_timeseries_map.cfg"
)


ALLOWED_KEYS = {
    "data_file", "dates_file", "output_dir", "output_file", "region_west", "region_east",
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
    "chunk_rows", "nan_tokens", "add_colorbar", "colorbar_label", "colorbar_unit",
    "colorbar_interval",
    "colorbar_width", "colorbar_height", "colorbar_offset", "colorbar_box",
    "output_dpi", "default_font_title", "default_font_annot_primary",
    "default_font_annot_secondary", "default_font_label",
}


def build_parser() -> argparse.ArgumentParser:
    """Build the configuration-only command-line interface."""
    parser = argparse.ArgumentParser(description="Plot multi-epoch deformation map panels.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    return parser


def load_config(config_file: str) -> dict[str, object]:
    """Load and normalize one spatial time-series plotting configuration."""
    path = Path(config_file).expanduser().resolve()
    raw = load_key_value_config(str(path))
    validate_config_keys(raw, ALLOWED_KEYS, str(path))
    base = path.parent
    output_dir = resolve_path(get_optional(raw, "output_dir", "result"), base)
    region = [
        parse_float(get_required(raw, "region_west"), 0.0),
        parse_float(get_required(raw, "region_east"), 0.0),
        parse_float(get_required(raw, "region_south"), 0.0),
        parse_float(get_required(raw, "region_north"), 0.0),
    ]
    validate_numeric_range(region[0], region[1], "region_west", "region_east")
    validate_numeric_range(region[2], region[3], "region_south", "region_north")
    cpt_value = get_optional(raw, "cpt", "jet")
    # Treat values containing a path component as files relative to the cfg.
    # Plain GMT palette names such as ``jet`` and ``vik`` remain unchanged.
    cpt_path = Path(cpt_value)
    cpt = (
        resolve_path(cpt_value, base)
        if cpt_path.suffix.lower() == ".cpt" or cpt_path.parent != Path(".")
        else cpt_value
    )
    cfg = {
        "data_file": resolve_path(get_required(raw, "data_file"), base),
        "dates_file": resolve_path(get_required(raw, "dates_file"), base),
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
        "font_family": get_optional(raw, "font_family", "Helvetica"),
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
        "add_colorbar": parse_bool(get_optional(raw, "add_colorbar", ""), True),
        "colorbar_label": get_optional(raw, "colorbar_label", "Deformation"),
        "colorbar_unit": get_optional(raw, "colorbar_unit", "mm"),
        "colorbar_interval": parse_float(
            get_optional(raw, "colorbar_interval", ""), 10.0
        ),
        "colorbar_width": get_optional(raw, "colorbar_width", "14c"),
        "colorbar_height": get_optional(raw, "colorbar_height", "0.5c"),
        "colorbar_offset": get_optional(raw, "colorbar_offset", "0c/0.9c"),
        "colorbar_box": get_optional(raw, "colorbar_box", "F+gwhite+p1p+c10p/8p"),
        "output_dpi": parse_int(get_optional(raw, "output_dpi", ""), 600),
        "defaults": {
            "FONT_TITLE": get_optional(raw, "default_font_title", "16p,Helvetica-Bold"),
            "FONT_ANNOT_PRIMARY": get_optional(raw, "default_font_annot_primary", "10p,Helvetica"),
            "FONT_ANNOT_SECONDARY": get_optional(
                raw, "default_font_annot_secondary", "10p,Helvetica"
            ),
            "FONT_LABEL": get_optional(raw, "default_font_label", "12p,Helvetica"),
        },
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


def draw_panel_basemap(plotter: PyGMTPlotter, cfg: dict[str, object]) -> None:
    """Draw the configured blank, optical or DEM background on the active panel."""
    if cfg["basemap_mode"] == "optic":
        plotter.draw_optic(str(cfg["basemap_tif"]), cfg["region"], str(cfg["projection"]))
    elif cfg["basemap_mode"] == "dem":
        plotter.draw_dem(
            str(cfg["basemap_tif"]), str(cfg["dem_cpt"]), cfg["region"], str(cfg["projection"]),
            float(cfg["dem_bar_min"]), float(cfg["dem_bar_max"]),
        )


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


def _draw_panel_frame(
    plotter: PyGMTPlotter,
    cfg: dict[str, object],
    title: str,
    index: int,
    title_font: str,
    coordinate_font: str,
) -> None:
    """Draw a panel border plus optional shared-edge coordinates and title."""
    figure = plotter._require_figure()
    figure.basemap(
        region=cfg["region"],
        projection=str(cfg["projection"]),
        frame="0",
    )

    row, column = divmod(index, int(cfg["columns"]))
    mode = str(cfg["coordinate_mode"])
    show_x = mode == "all" or (mode == "outer" and row == int(cfg["rows"]) - 1)
    show_y = mode == "all" or (mode == "outer" and column == 0)
    if show_x or show_y:
        axes = ("W" if show_y else "") + ("S" if show_x else "")
        frame = [axes]
        if show_x:
            interval = float(cfg["longitude_interval"])
            grid = f"g{interval:g}" if cfg["show_coordinate_grid"] else ""
            frame.append(f"xaf{interval:g}{grid}")
        if show_y:
            interval = float(cfg["latitude_interval"])
            grid = f"g{interval:g}" if cfg["show_coordinate_grid"] else ""
            frame.append(f"yaf{interval:g}{grid}")
        with pygmt.config(
            FONT_ANNOT_PRIMARY=coordinate_font,
            FORMAT_GEO_MAP=str(cfg["coordinate_format"]),
            MAP_FRAME_TYPE="plain",
            MAP_FRAME_PEN="0.7p,black",
        ):
            figure.basemap(
                region=cfg["region"],
                projection=str(cfg["projection"]),
                frame=frame,
            )

    west, east, south, north = cfg["region"]
    figure.plot(
        x=[west, east, east, west, west],
        y=[south, south, north, north, south],
        pen="0.7p,black",
    )
    if cfg["show_panel_title"]:
        figure.text(
            x=(west + east) / 2,
            y=north,
            text=title,
            justify="BC",
            offset="0p/6p",
            no_clip=True,
            font=title_font,
        )


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


def render(
    cfg: dict[str, object],
    longitude: np.ndarray,
    latitude: np.ndarray,
    values: np.ndarray,
    dates: list[str],
) -> Path:
    """Render selected epochs as geographic scatter-map panels and save atomically."""
    plotter = PyGMTPlotter(defaults=cfg["defaults"])
    plotter.new()
    figure = plotter._require_figure()
    # GMT projections preserve geographic geometry. Deriving both subplot
    # dimensions from the same -R/-J pair prevents a square subplot slot from
    # being combined with a shorter Mercator map.
    panel_width, panel_height = _projected_panel_size(
        list(cfg["region"]), str(cfg["projection"])
    )
    bold = bool(cfg["font_bold"])
    title_font = _scaled_font(
        float(cfg["panel_title_font_size"]), cfg, panel_width, bold=bold
    )
    tag_font = _scaled_font(
        float(cfg["panel_number_font_size"]), cfg, panel_width, bold=bold
    )
    coordinate_font = _scaled_font(
        float(cfg["coordinate_font_size"]), cfg, panel_width, bold=bold
    )
    colorbar_annotation_font = _scaled_font(
        float(cfg["colorbar_annotation_font_size"]), cfg, panel_width, bold=bold
    )
    colorbar_label_font = _scaled_font(
        float(cfg["colorbar_label_font_size"]), cfg, panel_width, bold=bold
    )
    pygmt.makecpt(
        cmap=str(cfg["cpt"]),
        series=[float(cfg["bar_min"]), float(cfg["bar_max"]), float(cfg["bar_step"])],
        reverse=bool(cfg["cpt_reverse"]),
        continuous=True,
    )
    subplot_options = {
        "nrows": int(cfg["rows"]),
        "ncols": int(cfg["columns"]),
        "subsize": (panel_width, panel_height),
        "region": cfg["region"],
        "projection": str(cfg["projection"]),
        "margins": [str(cfg["panel_margin_x"]), str(cfg["panel_margin_y"])],
    }
    if cfg["show_panel_number"]:
        subplot_options["autolabel"] = (
            f"{cfg['panel_number_style']}+jTL+o8p/8p+gwhite@70"
        )
    with pygmt.config(FONT_TAG=tag_font), figure.subplot(
        **subplot_options,
    ):
        for index, date in enumerate(dates):
            with figure.set_panel(panel=index):
                _draw_panel_frame(
                    plotter,
                    cfg,
                    _format_panel_title(date, cfg),
                    index,
                    title_font,
                    coordinate_font,
                )
                draw_panel_basemap(plotter, cfg)
                kwargs = {
                    "x": longitude,
                    "y": latitude,
                    "fill": values[:, index],
                    "cmap": True,
                    "style": str(cfg["point_style"]),
                }
                if cfg["point_pen"]:
                    kwargs["pen"] = str(cfg["point_pen"])
                figure.plot(**kwargs)
    if cfg["add_colorbar"]:
        with pygmt.config(
            FONT_ANNOT_PRIMARY=colorbar_annotation_font,
            # GMT draws a horizontal colorbar's end unit (for example ``mm``)
            # with the secondary annotation font, not the axis-label font.
            FONT_ANNOT_SECONDARY=colorbar_annotation_font,
            FONT_LABEL=colorbar_label_font,
        ):
            figure.colorbar(
                cmap=True,
                position=(
                    f"JBC+o{cfg['colorbar_offset']}+w{cfg['colorbar_width']}"
                    f"/{cfg['colorbar_height']}+h"
                ),
                frame=[
                    f"xa{float(cfg['colorbar_interval']):g}+l{cfg['colorbar_label']}",
                    f"y+l{cfg['colorbar_unit']}",
                ],
                box=str(cfg["colorbar_box"]),
            )
    destination = Path(str(cfg["output"]))
    plotter.save(
        str(destination),
        dpi=int(cfg["output_dpi"]),
        canvas_margin=str(cfg["canvas_margin"]),
    )
    return destination


def main() -> None:
    """Load one cfg, read the selected epochs and render the time-series map."""
    cfg = load_config(build_parser().parse_args().config)
    data = load_timeseries_table(
        str(cfg["data_file"]), str(cfg["dates_file"]), int(cfg["start_epoch"]),
        int(cfg["end_epoch"]), float(cfg["scale"]), int(cfg["chunk_rows"]),
        list(cfg["nan_tokens"]),
    )
    print(f"Saved: {render(cfg, *data)}")


__all__ = [
    "ALLOWED_KEYS",
    "build_parser",
    "draw_panel_basemap",
    "load_config",
    "load_timeseries_table",
    "main",
    "render",
]


if __name__ == "__main__":
    main()
