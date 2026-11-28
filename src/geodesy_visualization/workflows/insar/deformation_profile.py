"""
geodesy_visualization.workflows.insar.deformation_profile
========================================================

功能概述:
    读取严格 cfg 配置，通过过渡期 ``lib.pygmt_geo`` 边界准备两套形变网格，
    绘制各自地图，并沿公共命名轨迹输出折线和散点剖面对比图。本模块负责工作流
    编排，不拥有持久格式转换实现。

函数说明:
    ``build_parser``:
        构建命令行参数解析器。
    ``load_dataset_cfg``:
        读取并归一化一个形变数据集的输入和绘图参数。
    ``load_config``:
        读取、解析并校验地图、轨迹和剖面绘图配置。
    ``build_tracks``:
        根据配置中的起止坐标生成命名剖面轨迹。
    ``extract_profiles``:
        沿每条公共轨迹采样全部形变数据集。
    ``profile_output_path``:
        生成指定轨迹和绘图模式的输出路径。
    ``compile_profile_figures``:
        将地图、轨迹和剖面结果编译为统一图层计划。
    ``main``:
        准备网格、提取剖面并执行全部地图和剖面绘图流程。
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from geodesy_visualization.geo import extract_profile, generate_tracks
from geodesy_visualization.grid_preparation import prepare_dataset_grid
from geodesy_visualization.io import (
    get_optional,
    get_required,
    load_key_value_config,
    parse_bool,
    parse_choice,
    parse_coord_pairs,
    parse_csv_strings,
    parse_float,
    parse_int,
    resolve_output_path,
    resolve_publication_output_dir,
    resolve_project_dir,
    resolve_path,
    validate_closed_range,
    validate_config_keys,
    validate_numeric_range,
    validate_same_length,
)
from geodesy_visualization.styles import (
    DEFORMATION_MAP_STYLE_KEYS,
    colorbar_metadata_keys,
    font_style_keys,
    parse_colorbar_metadata,
    parse_deformation_map_style,
    parse_scoped_font_style,
    resolve_cpt_reference,
)
from geodesy_visualization.figure_ops.executor import FigureExecutor
from geodesy_visualization.resources import resource_path
from geodesy_visualization.workflows.insar.deformation_profile_plan import (
    compile_profile_figures,
)


cpt_path = resource_path("cpt")
DEFAULT_CONFIG = resource_path(
    "config_examples", "deformation_profile", "deformation_profile.cfg"
)


ALLOWED_KEYS = {
    "project_root", "project", "processing_root",
    "output_dir", "projection", "dem_tif", "dem_cpt", "dem_bar_min", "dem_bar_max",
    "defo_cpt", "defo_cpt_reverse", "defo_bar_min", "defo_bar_max", "defo_transparency",
    "add_scale", "map_scale",
    "map_scale_box", "map_scale_height", "map_scale_font_annot", "map_scale_font_label",
    "add_rose", "track_start_coords", "track_end_coords", "track_names", "track_num_points",
    "track_line_pen", "track_label_font", "track_start_justify", "track_end_justify",
    "track_end_suffix", "marker_lon", "marker_lat", "marker_style", "marker_pen", "marker_fill",
    "export_line_profiles", "export_scatter_profiles", "profile_title_prefix",
    "profile_x_label", "profile_y_label", "profile_padding", "profile_projection",
    "profile_x_frame", "profile_y_frame", "profile_frame_pen",
    "profile_add_legend", "profile_legend_position", "profile_legend_box", "profile_legend_font",
}
ALLOWED_KEYS.update(colorbar_metadata_keys("defo") | DEFORMATION_MAP_STYLE_KEYS)
for _style_prefix in ("default", "map", "profile"):
    ALLOWED_KEYS.update(font_style_keys(_style_prefix))
for _prefix in ("dataset1", "dataset2"):
    ALLOWED_KEYS.update(
        {
            f"{_prefix}_label", f"{_prefix}_title", f"{_prefix}_input_type",
            f"{_prefix}_input_path", f"{_prefix}_grd", f"{_prefix}_scale",
            f"{_prefix}_space", f"{_prefix}_nan_to_zero", f"{_prefix}_chunk_rows",
            f"{_prefix}_input_crs", f"{_prefix}_deformation_column", f"{_prefix}_target_crs",
            f"{_prefix}_output_map", f"{_prefix}_line_pen", f"{_prefix}_scatter_style",
            f"{_prefix}_scatter_fill", f"{_prefix}_scatter_pen",
            f"{_prefix}_scatter_transparency",
        }
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for selecting a profile configuration file."""
    parser = argparse.ArgumentParser(
        description="Plot deformation maps and profile figures from a key-value cfg file."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to key=value cfg file. Defaults to the bundled deformation-profile example.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def load_dataset_cfg(
    cfg: dict,
    base_dir: Path,
    output_dir: str,
    prefix: str,
    default_title: str,
    default_output_stub: str,
) -> dict:
    """Normalize one prefixed dataset block, including map and profile styles."""
    grd_default = f"{default_output_stub}.grd"
    return {
        "label": get_optional(cfg, f"{prefix}_label", default_output_stub),
        "title": get_optional(cfg, f"{prefix}_title", default_title),
        "input_type": parse_choice(
            get_optional(cfg, f"{prefix}_input_type", "tif"), ("tif", "txt"), f"{prefix}_input_type"
        ),
        "input_path": resolve_path(get_required(cfg, f"{prefix}_input_path"), base_dir),
        "grd_path": resolve_path(get_optional(cfg, f"{prefix}_grd", grd_default), base_dir),
        "scale": parse_float(get_optional(cfg, f"{prefix}_scale", ""), 1.0),
        "space": parse_float(get_optional(cfg, f"{prefix}_space", ""), 0.003),
        "nan_to_zero": parse_bool(get_optional(cfg, f"{prefix}_nan_to_zero", ""), True),
        "chunk_rows": parse_int(get_optional(cfg, f"{prefix}_chunk_rows", ""), 250_000),
        "input_crs": get_optional(cfg, f"{prefix}_input_crs", ""),
        "deformation_column": parse_int(get_optional(cfg, f"{prefix}_deformation_column", ""), 3),
        "target_crs": get_optional(cfg, f"{prefix}_target_crs", "EPSG:4326"),
        "output_map": resolve_output_path(
            get_optional(cfg, f"{prefix}_output_map", f"{default_output_stub}.png"),
            output_dir,
            base_dir,
        ),
        "line_pen": get_optional(cfg, f"{prefix}_line_pen", "2p,blue"),
        "scatter_style": get_optional(cfg, f"{prefix}_scatter_style", "c0.4c"),
        "scatter_fill": get_optional(cfg, f"{prefix}_scatter_fill", "blue"),
        "scatter_pen": get_optional(cfg, f"{prefix}_scatter_pen", "0.5p,blue"),
        "scatter_transparency": int(
            parse_float(get_optional(cfg, f"{prefix}_scatter_transparency", ""), 60.0)
        ),
    }


def load_config(config_path: str) -> dict:
    """Load and validate map, dataset, track, profile, and style settings from cfg."""
    cfg_path = Path(config_path).expanduser().resolve()
    cfg = load_key_value_config(str(cfg_path))
    validate_config_keys(cfg, ALLOWED_KEYS, str(cfg_path))
    base_dir = resolve_project_dir(cfg, cfg_path)

    output_dir = str(
        resolve_publication_output_dir(cfg, cfg_path, "deformation_profile")
    )
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    first_dataset = load_dataset_cfg(
        cfg, base_dir, output_dir, "dataset1", "Deformation: Dataset1", "dataset1"
    )
    second_dataset = load_dataset_cfg(
        cfg, base_dir, output_dir, "dataset2", "Deformation: Dataset2", "dataset2"
    )

    start_coords = parse_coord_pairs(get_required(cfg, "track_start_coords"))
    end_coords = parse_coord_pairs(get_required(cfg, "track_end_coords"))
    pointnames = parse_csv_strings(get_required(cfg, "track_names"))
    validate_same_length(
        (start_coords, end_coords, pointnames),
        ("track_start_coords", "track_end_coords", "track_names"),
    )

    marker_lon = get_optional(cfg, "marker_lon", "")
    marker_lat = get_optional(cfg, "marker_lat", "")
    if bool(marker_lon) != bool(marker_lat):
        raise ValueError("marker_lon and marker_lat must be provided together.")

    conf = {
        "config_path": str(cfg_path),
        "projection": get_optional(cfg, "projection", "M8i"),
        "dem_tif": resolve_path(get_required(cfg, "dem_tif"), base_dir),
        "dem_cpt": get_optional(cfg, "dem_cpt", "gray"),
        "defo_cpt": resolve_cpt_reference(
            get_optional(cfg, "defo_cpt", str(cpt_path / "seismic.cpt")), base_dir
        ),
        "defo_cpt_reverse": parse_bool(get_optional(cfg, "defo_cpt_reverse", ""), False),
        "dem_bar_min": parse_float(get_optional(cfg, "dem_bar_min", ""), 700.0),
        "dem_bar_max": parse_float(get_optional(cfg, "dem_bar_max", ""), 2300.0),
        "defo_bar_min": parse_float(get_optional(cfg, "defo_bar_min", ""), -0.1),
        "defo_bar_max": parse_float(get_optional(cfg, "defo_bar_max", ""), 0.1),
        "defo_transparency": int(parse_float(get_optional(cfg, "defo_transparency", ""), 25.0)),
        **parse_colorbar_metadata(
            cfg,
            "defo",
            enabled=parse_bool(get_optional(cfg, "add_colorbar", ""), True),
            default_label="Deformation",
            default_unit="m/yr",
        ),
        "num_points": parse_int(get_optional(cfg, "track_num_points", ""), 100),
        "track_start_coords": start_coords,
        "track_end_coords": end_coords,
        "track_names": pointnames,
        "output_dir": output_dir,
        "line_profiles": parse_bool(get_optional(cfg, "export_line_profiles", ""), True),
        "scatter_profiles": parse_bool(get_optional(cfg, "export_scatter_profiles", ""), True),
        "add_scale": parse_bool(get_optional(cfg, "add_scale", ""), True),
        "map_scale": get_optional(cfg, "map_scale", "JTC+o0c/4c+w10k+f+u"),
        "map_scale_box": get_optional(cfg, "map_scale_box", "F+gWHITE+p2p+c20p/20p"),
        "map_scale_height": get_optional(cfg, "map_scale_height", "20p"),
        "map_scale_font_annot": get_optional(cfg, "map_scale_font_annot", "20p"),
        "map_scale_font_label": get_optional(cfg, "map_scale_font_label", "20p,Helvetica-Bold,black"),
        "add_rose": parse_bool(get_optional(cfg, "add_rose", ""), True),
        **parse_deformation_map_style(cfg),
        "map_style": parse_scoped_font_style(
            cfg, "map", ("28p,Helvetica-Bold", "14p,Helvetica-Bold", "28p,Helvetica-Bold")
        ),
        "profile_style": parse_scoped_font_style(
            cfg, "profile", ("20p,Helvetica-Bold", "12p,Helvetica", "16p,Helvetica")
        ),
        "profile_title_prefix": get_optional(cfg, "profile_title_prefix", "Profile"),
        "profile_x_label": get_optional(cfg, "profile_x_label", "Distance (m)"),
        "profile_y_label": get_optional(cfg, "profile_y_label", "Deformation (m)"),
        "profile_padding": parse_float(get_optional(cfg, "profile_padding", ""), 0.1),
        "profile_projection": get_optional(cfg, "profile_projection", "X16c/10c"),
        "profile_x_frame": get_optional(cfg, "profile_x_frame", "af"),
        "profile_y_frame": get_optional(cfg, "profile_y_frame", "af"),
        "profile_frame_pen": get_optional(cfg, "profile_frame_pen"),
        "profile_add_legend": parse_bool(get_optional(cfg, "profile_add_legend"), True),
        "profile_legend_font": get_optional(cfg, "profile_legend_font"),
        "profile_legend_position": get_optional(cfg, "profile_legend_position", "JTR+o0.5c/-1.2c"),
        "profile_legend_box": get_optional(cfg, "profile_legend_box", "+gwhite+p1.5p"),
        "track_line_pen": get_optional(cfg, "track_line_pen", "2p,black"),
        "track_label_font": get_optional(cfg, "track_label_font", "20p,Helvetica-Bold"),
        "track_start_justify": get_optional(cfg, "track_start_justify", "BR"),
        "track_end_justify": get_optional(cfg, "track_end_justify", "BL"),
        "track_end_suffix": get_optional(cfg, "track_end_suffix", "'"),
        "dataset1": first_dataset,
        "dataset2": second_dataset,
        "marker_lon": float(marker_lon) if marker_lon else None,
        "marker_lat": float(marker_lat) if marker_lat else None,
        "marker_style": get_optional(cfg, "marker_style", "a16p"),
        "marker_pen": get_optional(cfg, "marker_pen", "2p,black"),
        "marker_fill": get_optional(cfg, "marker_fill", ""),
    }
    validate_numeric_range(conf["defo_bar_min"], conf["defo_bar_max"], "defo_bar_min", "defo_bar_max")
    validate_numeric_range(conf["dem_bar_min"], conf["dem_bar_max"], "dem_bar_min", "dem_bar_max")
    validate_closed_range(conf["defo_transparency"], "defo_transparency", 0, 100)
    if conf["num_points"] < 2:
        raise ValueError("track_num_points must be at least 2")
    if conf["profile_padding"] < 0:
        raise ValueError("profile_padding cannot be negative")
    for prefix, dataset in (("dataset1", first_dataset), ("dataset2", second_dataset)):
        if dataset["space"] <= 0:
            raise ValueError(f"{prefix}_space must be positive")
        if dataset["chunk_rows"] <= 0:
            raise ValueError(f"{prefix}_chunk_rows must be positive")
        if dataset["deformation_column"] < 0:
            raise ValueError(f"{prefix}_deformation_column must be non-negative")
        validate_closed_range(
            dataset["scatter_transparency"], f"{prefix}_scatter_transparency", 0, 100
        )
    return conf


def build_tracks(cfg: dict) -> dict:
    """Generate named lon/lat sampling tracks from normalized cfg coordinates."""
    return generate_tracks(
        start_coords=cfg["track_start_coords"],
        end_coords=cfg["track_end_coords"],
        num_points=cfg["num_points"],
        pointnames=cfg["track_names"],
    )


def extract_profiles(dataset_cfgs: list[dict], tracks: dict) -> dict:
    """Sample every dataset along every named track and group results by track."""
    profiles: dict = {name: [] for name in tracks}
    for dataset_cfg in dataset_cfgs:
        for track_name in tracks:
            profiles[track_name].append(
                extract_profile(dataset_cfg["grd_path"], tracks[track_name])
            )
    return profiles


def profile_output_path(cfg: dict, track_name: str, mode: str) -> str:
    """Build the output filename for one track and profile rendering mode."""
    filename = f"{cfg['profile_title_prefix']}_{track_name}_{mode}.png"
    return str(Path(cfg["output_dir"]) / filename)


def main(arguments: Sequence[str] | None = None) -> None:
    """Prepare grids, sample profiles, compile plans, and execute all figures."""
    args = build_parser().parse_args(arguments)
    cfg = load_config(args.config)
    tracks = build_tracks(cfg)
    if args.dry_run:
        placeholder = {
            name: ((), ())
            for name in tracks
        }
        for plan in compile_profile_figures(cfg, tracks, placeholder):
            print(f"Figure: {plan.figure['dataset']}")
            for layer in plan.operations:
                print(f"  {layer.order + 1:02d}. {layer.section}")
            print(f"Output: {plan.operations[-1].options['fname']}")
        return

    dataset_cfgs = [cfg["dataset1"], cfg["dataset2"]]
    for dataset_cfg in dataset_cfgs:
        prepare_dataset_grid(dataset_cfg)

    profiles = extract_profiles(dataset_cfgs, tracks)
    from geodesy_visualization.figure_ops.deformation_layers import (
        DEFORMATION_HANDLERS,
    )
    from geodesy_visualization.figure_ops.profile_layers import PROFILE_HANDLERS

    handlers = {**DEFORMATION_HANDLERS, **PROFILE_HANDLERS}
    for plan in compile_profile_figures(cfg, tracks, profiles):
        FigureExecutor(plan, handlers=handlers).execute_plan()


__all__ = [
    "ALLOWED_KEYS",
    "build_parser",
    "build_tracks",
    "compile_profile_figures",
    "extract_profiles",
    "load_config",
    "load_dataset_cfg",
    "main",
    "profile_output_path",
]


if __name__ == "__main__":
    main()
