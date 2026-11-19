"""
geodesy_visualization.workflows.insar.deformation_map_plan
==========================================================

功能概述:
    将 deformation-map 的紧凑领域配置编译为与 footprint 工作流一致的
    有序 FigurePlan/LayerOperation，不执行数据转换或导入绘图后端。

函数说明:
    ``compile_deformation_maps``:
        为 coverage 或每个启用的形变数据集生成一张可执行 FigurePlan。
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

from geodesy_visualization.figure_ops.model import FigurePlan, LayerOperation


def _layer(
    section: str,
    handler: str,
    options: dict[str, object],
    order: int,
) -> LayerOperation:
    """Create one immutable internal layer operation."""
    tokens = section.split(".")
    return LayerOperation(
        section=section,
        method=tokens[1],
        semantics=tuple(tokens[2:]),
        options=MappingProxyType(options),
        order=order,
        handler=handler,
    )


def _deformation_plan(cfg: dict, name: str, dataset: dict) -> FigurePlan:
    """Compile one normalized deformation dataset into visible ordered layers."""
    region = tuple(cfg["region"]) if cfg["region"] is not None else None
    style = {**cfg["default_style"], **cfg["map_style"]}
    layers: list[LayerOperation] = []

    def add(section: str, handler: str, options: dict[str, object]) -> None:
        """Append one layer using the next deterministic operation order."""
        layers.append(_layer(section, handler, options, len(layers)))

    add(
        f"figure.basemap.{name}",
        "deformation_basemap",
        {
            "region": region,
            "region_grid": dataset["grd_path"],
            "projection": cfg["projection"],
            "title": dataset["title"],
            "style": style,
        },
    )
    add(
        f"figure.grdimage.background.{name}",
        "deformation_background",
        {
            "mode": dataset["basemap_mode"],
            "dem_tif": cfg["dem_tif"],
            "optic_tif": cfg["optic_tif"],
            "dem_cpt": cfg["dem_cpt"],
            "dem_min": cfg["dem_bar_min"],
            "dem_max": cfg["dem_bar_max"],
        },
    )
    add(
        f"figure.plot.deformation.{name}",
        "deformation_data",
        {
            "mode": dataset["defo_mode"],
            "grid": dataset["grd_path"],
            "cpt": cfg["defo_cpt"],
            "cpt_reverse": cfg["defo_cpt_reverse"],
            "minimum": cfg["defo_bar_min"],
            "maximum": cfg["defo_bar_max"],
            "transparency": cfg["defo_transparency"],
            "scatter_style": cfg["scatter_style"],
            "scatter_pen": cfg["scatter_pen"],
            "clip_kml": cfg["clip_kml"],
        },
    )
    add(
        f"figure.plot.targets.{name}",
        "deformation_targets",
        {
            "targets": tuple(cfg["target_regions"]),
            "pen": cfg["target_region_pen"],
            "label_font": cfg["target_region_label_font"],
            "label_offset": cfg["target_region_label_offset"],
            "center_style": cfg["target_region_center_style"],
        },
    )
    add(
        f"figure.colorbar.deformation.{name}",
        "deformation_colorbar",
        {
            "enabled": cfg["add_colorbar"],
            "label": cfg["defo_colorbar_label"],
            "unit": cfg["defo_colorbar_unit"],
            "tick_interval": cfg["defo_colorbar_tick_interval"] or None,
        },
    )
    add(
        f"figure.scalebar.{name}",
        "deformation_scale",
        {
            "enabled": cfg["add_scale"],
            "map_scale": cfg["map_scale"],
            "box": cfg["map_scale_box"],
            "height": cfg["map_scale_height"],
            "font_annot": cfg["map_scale_font_annot"],
            "font_label": cfg["map_scale_font_label"],
        },
    )
    add(
        f"figure.directional_rose.{name}",
        "deformation_rose",
        {"enabled": cfg["add_rose"]},
    )
    add(
        "figure.savefig",
        "savefig",
        {"fname": dataset["output"], "dpi": 300},
    )
    return FigurePlan(
        config_path=Path(cfg["config_path"]),
        project=MappingProxyType({"output_dir": cfg["output_dir"]}),
        figure=MappingProxyType({"layout": "single_panel", "dataset": name}),
        operations=tuple(layers),
    )


def _coverage_plan(cfg: dict) -> FigurePlan:
    """Compile the compatibility coverage mode into the same layer model."""
    style = {**cfg["default_style"], **cfg["map_style"]}
    layers = (
        _layer(
            "figure.basemap.coverage",
            "deformation_basemap",
            {
                "region": tuple(cfg["region"]) if cfg["region"] else None,
                "region_grid": "",
                "projection": cfg["projection"],
                "title": cfg["coverage_title"],
                "style": style,
            },
            0,
        ),
        _layer(
            "figure.grdimage.background.coverage",
            "deformation_background",
            {"mode": "optic", "optic_tif": cfg["optic_tif"]},
            1,
        ),
        _layer(
            "figure.plot.coverage",
            "deformation_coverage",
            {
                "coverage_kml": tuple(cfg["coverage_kml"]),
                "coverage_pen": tuple(cfg["coverage_pen"]),
                "gnss_kml": cfg["gnss_kml"],
                "gnss_style": cfg["gnss_style"],
                "gnss_pen": cfg["gnss_pen"],
                "gnss_labels": cfg["gnss_labels"],
                "gnss_label_font": cfg["gnss_label_font"],
                "gnss_label_offset": cfg["gnss_label_offset"],
            },
            2,
        ),
        _layer(
            "figure.scalebar.coverage",
            "deformation_scale",
            {
                "enabled": cfg["add_scale"],
                "map_scale": cfg["map_scale"],
                "box": cfg["map_scale_box"],
                "height": cfg["map_scale_height"],
                "font_annot": cfg["map_scale_font_annot"],
                "font_label": cfg["map_scale_font_label"],
            },
            3,
        ),
        _layer(
            "figure.directional_rose.coverage",
            "deformation_rose",
            {"enabled": cfg["add_rose"]},
            4,
        ),
        _layer(
            "figure.savefig",
            "savefig",
            {"fname": cfg["coverage_output"], "dpi": 300},
            5,
        ),
    )
    return FigurePlan(
        config_path=Path(cfg["config_path"]),
        project=MappingProxyType({"output_dir": cfg["output_dir"]}),
        figure=MappingProxyType({"layout": "single_panel", "dataset": "coverage"}),
        operations=layers,
    )


def compile_deformation_maps(cfg: dict) -> tuple[FigurePlan, ...]:
    """Compile all enabled map products without drawing or preparing data."""
    if cfg["map_mode"] == "coverage":
        return (_coverage_plan(cfg),)
    plans = [_deformation_plan(cfg, "sbas", cfg["sbas"])]
    if cfg["psi"] is not None:
        plans.append(_deformation_plan(cfg, "psi", cfg["psi"]))
    return tuple(plans)


__all__ = ["compile_deformation_maps"]
