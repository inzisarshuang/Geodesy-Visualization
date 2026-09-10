"""
plot_defo_dem_optic
===================

功能概述:
    读取严格 cfg 配置，将 TIF 或 TXT 形变数据转换为 GMT GRD，
    并在 DEM 或光学影像底图上绘制网格或散点形变结果。

函数说明:
    ``validate_raw_config``:
        在参数归一化前检查未知配置键。
    ``optional_path``:
        按主键、兼容键和默认值顺序解析可选路径。
    ``parse_manual_region``:
        解析可选的手动经纬度绘图范围。
    ``parse_target_regions``:
        解析目标区域边界、标签和中心点样式。
    ``build_parser``:
        构建命令行参数解析器。
    ``load_config``:
        读取、解析并校验地图绘制所需的全部配置。
    ``draw_basemap``:
        根据数据集配置绘制 DEM、光学影像或空白底图。
    ``draw_deformation``:
        根据配置以网格或散点模式叠加形变数据。
    ``draw_target_regions``:
        绘制目标区域边框、中心标记和标签。
    ``render_map``:
        组合并保存一个数据集的完整形变地图。
    ``main``:
        准备启用的数据网格并依次执行地图绘制流程。
"""

import argparse
import re
import sys
from pathlib import Path
import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
lib_path = REPOSITORY_ROOT / "lib"
sys.path.insert(0, str(REPOSITORY_ROOT))
sys.path.insert(0, str(lib_path))

from pygmt_geo import prepare_dataset_grid, region_from_grd
from geodesy_visualization.io import (
    get_optional,
    get_required,
    load_key_value_config,
    parse_bool,
    parse_choice,
    parse_csv_strings,
    parse_float,
    parse_int,
    parse_style_block,
    resolve_output_path,
    resolve_path,
    validate_closed_range,
    validate_config_keys,
    validate_numeric_range,
)
from pygmt_visual import PyGMTPlotter


ALLOWED_KEYS = {
    "input_dir", "output_dir", "projection", "region_west", "region_east", "region_south", "region_north",
    "dem_tif", "optic_tif", "dem_cpt", "dem_bar_min", "dem_bar_max", "defo_cpt",
    "defo_cpt_reverse", "defo_bar_min", "defo_bar_max", "defo_transparency",
    "defo_colorbar_label", "defo_colorbar_unit", "defo_unit", "scatter_style", "scatter_pen",
    "add_colorbar", "add_scale", "map_scale", "map_scale_box", "map_scale_height",
    "map_scale_font_annot", "map_scale_font_label", "add_rose", "target_regions",
    "target_region_pen", "target_region_label_font", "target_region_label_offset",
    "target_region_center_style", "default_font_title", "default_font_annot_primary",
    "default_font_label", "map_font_title", "map_font_annot_primary", "map_font_label",
    "output_defo", "defo_basemap_mode",
}
for _prefix in ("sbas", "psi"):
    ALLOWED_KEYS.update(
        {
            f"{_prefix}_input_path", f"{_prefix}_input_type", f"{_prefix}_grd",
            f"{_prefix}_scale", f"{_prefix}_space", f"{_prefix}_nan_to_zero",
            f"{_prefix}_chunk_rows", f"{_prefix}_title", f"{_prefix}_basemap_mode",
            f"{_prefix}_defo_mode", f"output_{_prefix}", f"{_prefix}_input_crs",
            f"{_prefix}_deformation_column", f"{_prefix}_target_crs",
        }
    )


def validate_raw_config(cfg: dict, config_path: Path) -> None:
    """Validate supported keys, including configured target-region blocks."""
    allowed = set(ALLOWED_KEYS)
    for label in parse_csv_strings(get_optional(cfg, "target_regions", "")):
        if not re.fullmatch(r"[A-Za-z0-9_]+", label):
            raise ValueError(
                f"target region label '{label}' may contain only letters, numbers, and underscores"
            )
        prefix = f"target_{label}"
        allowed.update(
            {
                f"{prefix}_west", f"{prefix}_east", f"{prefix}_south", f"{prefix}_north",
                f"{prefix}_label_position",
            }
        )
    validate_config_keys(cfg, allowed, str(config_path))


def optional_path(cfg: dict, primary: str, fallback: str, default: str = "") -> str:
    """Return a preferred path key while retaining one legacy fallback key."""
    value = get_optional(cfg, primary, "")
    if value:
        return value
    return get_optional(cfg, fallback, default)


def parse_manual_region(cfg: dict) -> list[float] | None:
    """Parse an optional west/east/south/north map region as one validated block."""
    west = get_optional(cfg, "region_west", "")
    east = get_optional(cfg, "region_east", "")
    south = get_optional(cfg, "region_south", "")
    north = get_optional(cfg, "region_north", "")
    values = [west, east, south, north]
    if not any(values):
        return None
    if not all(values):
        raise ValueError("region_west/east/south/north must be set together.")
    region = [float(west), float(east), float(south), float(north)]
    validate_numeric_range(region[0], region[1], "region_west", "region_east")
    validate_numeric_range(region[2], region[3], "region_south", "region_north")
    return region


def parse_target_regions(cfg: dict) -> list[dict]:
    """Parse named ellipse bounds and label positions for target-region annotations."""
    raw_items = parse_csv_strings(get_optional(cfg, "target_regions", ""))
    targets = []
    for label in raw_items:
        prefix = f"target_{label}"
        west = get_optional(cfg, f"{prefix}_west", "")
        east = get_optional(cfg, f"{prefix}_east", "")
        south = get_optional(cfg, f"{prefix}_south", "")
        north = get_optional(cfg, f"{prefix}_north", "")
        if not all([west, east, south, north]):
            raise ValueError(f"{prefix}_west/east/south/north must be set together.")
        targets.append(
            {
                "label": label,
                "west": float(west),
                "east": float(east),
                "south": float(south),
                "north": float(north),
                "label_position": parse_choice(
                    get_optional(cfg, f"{prefix}_label_position", "top"),
                    ("top", "bottom", "left", "right", "northeast", "ne"),
                    f"{prefix}_label_position",
                ),
            }
        )
        validate_numeric_range(targets[-1]["west"], targets[-1]["east"], f"{prefix}_west", f"{prefix}_east")
        validate_numeric_range(
            targets[-1]["south"], targets[-1]["north"], f"{prefix}_south", f"{prefix}_north"
        )
    return targets


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for selecting a map configuration file."""
    parser = argparse.ArgumentParser(
        description="Plot deformation maps with DEM or optical basemap from a key-value cfg file."
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).with_suffix(".cfg")),
        help="Path to key=value cfg file. Defaults to plot_defo_dem_optic.cfg beside this script.",
    )
    return parser


def load_config(config_path: str) -> dict:
    """Load, validate, and normalize one deformation-map cfg into runtime settings."""
    cfg_path = Path(config_path).expanduser().resolve()
    cfg = load_key_value_config(str(cfg_path))
    validate_raw_config(cfg, cfg_path)
    base_dir = cfg_path.parent
    cpt_dir = Path(__file__).resolve().parents[1] / "cpt"

    output_dir = resolve_path(get_optional(cfg, "output_dir", "result"), base_dir)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    sbas_grd = resolve_path(get_optional(cfg, "sbas_grd", "SBAS.grd"), base_dir)
    psi_grd = resolve_path(get_optional(cfg, "psi_grd", "PSI.grd"), base_dir)

    sbas_cfg = {
        "input_type": parse_choice(
            get_optional(cfg, "sbas_input_type", "tif"), ("tif", "txt", "defsour"), "sbas_input_type"
        ),
        "input_path": resolve_path(get_required(cfg, "sbas_input_path"), base_dir),
        "grd_path": sbas_grd,
        "scale": parse_float(get_optional(cfg, "sbas_scale", ""), 1.0),
        "space": parse_float(get_optional(cfg, "sbas_space", ""), 0.0005),
        "nan_to_zero": parse_bool(get_optional(cfg, "sbas_nan_to_zero", ""), True),
        "chunk_rows": parse_int(get_optional(cfg, "sbas_chunk_rows", ""), 250_000),
        "input_crs": get_optional(cfg, "sbas_input_crs", ""),
        "deformation_column": parse_int(get_optional(cfg, "sbas_deformation_column", ""), 3),
        "target_crs": get_optional(cfg, "sbas_target_crs", "EPSG:4326"),
        "title": get_optional(cfg, "sbas_title", "Deformation: SBAS"),
        "defo_mode": parse_choice(
            get_optional(cfg, "sbas_defo_mode", "grd"), ("grd", "scatter"), "sbas_defo_mode"
        ),
        "output": resolve_output_path(
            optional_path(cfg, "output_sbas", "output_defo", f"{Path(output_dir) / 'SBAS.png'}"),
            output_dir,
            base_dir,
        ),
        "basemap_mode": parse_choice(
            get_optional(cfg, "sbas_basemap_mode", get_optional(cfg, "defo_basemap_mode", "optic")),
            ("dem", "optic"),
            "sbas_basemap_mode",
        ),
    }
    psi_cfg = None
    if get_optional(cfg, "psi_input_path", ""):
        psi_cfg = {
            "input_type": parse_choice(
                get_optional(cfg, "psi_input_type", "txt"), ("tif", "txt", "defsour"), "psi_input_type"
            ),
            "input_path": resolve_path(get_required(cfg, "psi_input_path"), base_dir),
            "grd_path": psi_grd,
            "scale": parse_float(get_optional(cfg, "psi_scale", ""), 1.0),
            "space": parse_float(get_optional(cfg, "psi_space", ""), 0.0005),
            "nan_to_zero": parse_bool(get_optional(cfg, "psi_nan_to_zero", ""), True),
            "chunk_rows": parse_int(get_optional(cfg, "psi_chunk_rows", ""), 250_000),
            "input_crs": get_optional(cfg, "psi_input_crs", ""),
            "deformation_column": parse_int(get_optional(cfg, "psi_deformation_column", ""), 3),
            "target_crs": get_optional(cfg, "psi_target_crs", "EPSG:4326"),
            "title": get_optional(cfg, "psi_title", "Deformation: PSI"),
            "defo_mode": parse_choice(
                get_optional(cfg, "psi_defo_mode", "scatter"),
                ("grd", "scatter"),
                "psi_defo_mode",
            ),
            "output": resolve_output_path(
                get_optional(cfg, "output_psi", f"{Path(output_dir) / 'PSI.png'}"),
                output_dir,
                base_dir,
            ),
            "basemap_mode": parse_choice(
                get_optional(cfg, "psi_basemap_mode", "dem"),
                ("dem", "optic"),
                "psi_basemap_mode",
            ),
        }

    dem_file = get_optional(cfg, "dem_tif", "")
    optic_file = get_optional(cfg, "optic_tif", "")

    basemap_modes = {sbas_cfg["basemap_mode"]}
    if psi_cfg is not None:
        basemap_modes.add(psi_cfg["basemap_mode"])

    if "dem" in basemap_modes and not dem_file:
        raise ValueError("dem_tif is required when any basemap mode is 'dem'.")
    if "optic" in basemap_modes and not optic_file:
        raise ValueError("optic_tif is required when any basemap mode is 'optic'.")

    conf = {
        "projection": get_optional(cfg, "projection", "M8i"),
        "region": parse_manual_region(cfg),
        "dem_tif": resolve_path(dem_file, base_dir) if dem_file else "",
        "optic_tif": resolve_path(optic_file, base_dir) if optic_file else "",
        "defo_cpt": resolve_path(get_optional(cfg, "defo_cpt", str(cpt_dir / "saga-01.cpt")), base_dir),
        "defo_cpt_reverse": parse_bool(get_optional(cfg, "defo_cpt_reverse", ""), False),
        "dem_cpt": get_optional(cfg, "dem_cpt", "gray"),
        "defo_bar_min": parse_float(get_optional(cfg, "defo_bar_min", ""), -0.06),
        "defo_bar_max": parse_float(get_optional(cfg, "defo_bar_max", ""), 0.06),
        "dem_bar_min": parse_float(get_optional(cfg, "dem_bar_min", ""), 700.0),
        "dem_bar_max": parse_float(get_optional(cfg, "dem_bar_max", ""), 2300.0),
        "defo_transparency": int(parse_float(get_optional(cfg, "defo_transparency", ""), 25.0)),
        "defo_colorbar_label": get_optional(cfg, "defo_colorbar_label", "Deformation"),
        "defo_colorbar_unit": get_optional(cfg, "defo_colorbar_unit", get_optional(cfg, "defo_unit", "m/yr")),
        "target_regions": parse_target_regions(cfg),
        "target_region_pen": get_optional(cfg, "target_region_pen", "1.5p,black"),
        "target_region_label_font": get_optional(cfg, "target_region_label_font", "12p,Helvetica-Bold,black"),
        "target_region_label_offset": parse_float(get_optional(cfg, "target_region_label_offset", ""), 0.008),
        "target_region_center_style": get_optional(cfg, "target_region_center_style", "c0.08c"),
        "scatter_style": get_optional(cfg, "scatter_style", "c0.08c"),
        "scatter_pen": get_optional(cfg, "scatter_pen", "0.01p,white"),
        "add_colorbar": parse_bool(get_optional(cfg, "add_colorbar", ""), True),
        "add_scale": parse_bool(get_optional(cfg, "add_scale", ""), True),
        "map_scale": get_optional(cfg, "map_scale", "JTC+o0c/4c+w10k+f+u"),
        "map_scale_box": get_optional(cfg, "map_scale_box", "F+gWHITE+p2p+c20p/20p"),
        "map_scale_height": get_optional(cfg, "map_scale_height", "20p"),
        "map_scale_font_annot": get_optional(cfg, "map_scale_font_annot", "20p"),
        "map_scale_font_label": get_optional(cfg, "map_scale_font_label", "20p,Helvetica-Bold,black"),
        "add_rose": parse_bool(get_optional(cfg, "add_rose", ""), True),
        "default_style": parse_style_block(
            cfg,
            "default",
            "24p,Helvetica-Bold",
            "12p,Helvetica-Bold",
            "20p,Helvetica-Bold",
        ),
        "map_style": parse_style_block(
            cfg,
            "map",
            "28p,Helvetica-Bold",
            "14p,Helvetica-Bold",
            "28p,Helvetica-Bold",
        ),
        "sbas": sbas_cfg,
        "psi": psi_cfg,
    }
    validate_numeric_range(conf["defo_bar_min"], conf["defo_bar_max"], "defo_bar_min", "defo_bar_max")
    validate_numeric_range(conf["dem_bar_min"], conf["dem_bar_max"], "dem_bar_min", "dem_bar_max")
    validate_closed_range(conf["defo_transparency"], "defo_transparency", 0, 100)
    for name, dataset in (("sbas", sbas_cfg), ("psi", psi_cfg)):
        if dataset is None:
            continue
        if dataset["space"] <= 0:
            raise ValueError(f"{name}_space must be positive")
        if dataset["chunk_rows"] <= 0:
            raise ValueError(f"{name}_chunk_rows must be positive")
        if dataset["input_type"] == "defsour" and not dataset["input_crs"]:
            raise ValueError(f"{name}_input_crs is required for Defsour input")
        if dataset["deformation_column"] < 0:
            raise ValueError(f"{name}_deformation_column must be non-negative")
    return conf


def draw_basemap(
    plotter: PyGMTPlotter,
    cfg: dict,
    region: list[float],
    projection: str,
    basemap_mode: str,
) -> None:
    """Draw the DEM or optical basemap selected for one deformation dataset."""
    if basemap_mode == "optic":
        plotter.draw_optic(
            optic_tif=cfg["optic_tif"],
            region=region,
            projection=projection,
        )
        return
    if basemap_mode == "dem":
        plotter.draw_dem(
            dem_tif=cfg["dem_tif"],
            cpt=cfg["dem_cpt"],
            region=region,
            projection=projection,
            bar_min=cfg["dem_bar_min"],
            bar_max=cfg["dem_bar_max"],
        )
        return
    raise ValueError(f"unsupported basemap_mode: {basemap_mode}")


def draw_deformation(plotter: PyGMTPlotter, cfg: dict, dataset_cfg: dict, region: list[float]) -> None:
    """Draw one deformation dataset as a continuous grid or colored scatter layer."""
    if dataset_cfg["defo_mode"] == "grd":
        plotter.draw_defo_grd(
            data_grd=dataset_cfg["grd_path"],
            cpt=cfg["defo_cpt"],
            region=region,
            projection=cfg["projection"],
            bar_min=cfg["defo_bar_min"],
            bar_max=cfg["defo_bar_max"],
            transparency=cfg["defo_transparency"],
            cpt_reverse=cfg["defo_cpt_reverse"],
        )
        return
    if dataset_cfg["defo_mode"] == "scatter":
        plotter.draw_defo_scatter(
            data_grd=dataset_cfg["grd_path"],
            cpt=cfg["defo_cpt"],
            region=region,
            projection=cfg["projection"],
            bar_min=cfg["defo_bar_min"],
            bar_max=cfg["defo_bar_max"],
            style=cfg["scatter_style"],
            pen=cfg["scatter_pen"],
            transparency=cfg["defo_transparency"],
            cpt_reverse=cfg["defo_cpt_reverse"],
        )
        return
    raise ValueError(f"unsupported defo_mode: {dataset_cfg['defo_mode']}")


def draw_target_regions(plotter: PyGMTPlotter, cfg: dict) -> None:
    """Overlay configured target ellipses, center markers, and labels on the active map."""
    if not cfg["target_regions"]:
        return
    figure = plotter._require_figure()
    theta = np.linspace(0, 2 * np.pi, 181)
    for target in cfg["target_regions"]:
        west, east = target["west"], target["east"]
        south, north = target["south"], target["north"]
        cx = (west + east) / 2.0
        cy = (south + north) / 2.0
        rx = (east - west) / 2.0
        ry = (north - south) / 2.0
        x = cx + rx * np.cos(theta)
        y = cy + ry * np.sin(theta)
        figure.plot(x=x, y=y, pen=cfg["target_region_pen"])
        figure.plot(
            x=[cx],
            y=[cy],
            style=cfg["target_region_center_style"],
            fill="black",
            pen="0.5p,white",
        )
        offset = cfg["target_region_label_offset"]
        label_position = target["label_position"]
        if label_position == "bottom":
            label_x, label_y, justify = cx, south - offset, "TC"
        elif label_position == "right":
            label_x, label_y, justify = east + offset, cy, "ML"
        elif label_position == "left":
            label_x, label_y, justify = west - offset, cy, "MR"
        elif label_position in {"northeast", "ne"}:
            label_x, label_y, justify = east + offset, north + offset, "BL"
        else:
            label_x, label_y, justify = cx, north + offset, "BC"
        figure.text(
            x=label_x,
            y=label_y,
            text=target["label"],
            font=cfg["target_region_label_font"],
            justify=justify,
        )


def render_map(plotter: PyGMTPlotter, cfg: dict, dataset_cfg: dict) -> None:
    """Compose and save one complete deformation map for a normalized dataset config."""
    region = cfg["region"] or region_from_grd(dataset_cfg["grd_path"])
    plotter.new()
    plotter.draw_geo_basemap(region=region, projection=cfg["projection"], title=dataset_cfg["title"])
    draw_basemap(plotter, cfg, region, cfg["projection"], dataset_cfg["basemap_mode"])
    draw_deformation(plotter, cfg, dataset_cfg, region)
    draw_target_regions(plotter, cfg)
    if cfg["add_colorbar"]:
        plotter.add_colorbar(label=cfg["defo_colorbar_label"], unit=cfg["defo_colorbar_unit"])
    if cfg["add_scale"]:
        plotter.add_scale(
            region=region,
            projection=cfg["projection"],
            map_scale=cfg["map_scale"],
            box=cfg["map_scale_box"],
            scale_height=cfg["map_scale_height"],
            font_annot=cfg["map_scale_font_annot"],
            font_label=cfg["map_scale_font_label"],
        )
    if cfg["add_rose"]:
        plotter.add_rose(region=region, projection=cfg["projection"])
    plotter.save(dataset_cfg["output"])


def main() -> None:
    """Run grid preparation and render all datasets enabled by the selected cfg file."""
    args = build_parser().parse_args()
    cfg = load_config(args.config)

    prepare_dataset_grid(cfg["sbas"])
    if cfg["psi"] is not None:
        prepare_dataset_grid(cfg["psi"])

    map_style = {**cfg["default_style"], **cfg["map_style"]}
    plotter = PyGMTPlotter(defaults=map_style)
    render_map(plotter, cfg, cfg["sbas"])
    if cfg["psi"] is not None:
        render_map(plotter, cfg, cfg["psi"])


if __name__ == "__main__":
    main()
