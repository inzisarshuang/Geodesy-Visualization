"""
geodesy_visualization.workflows.insar.deformation_profile_plan
==============================================================

功能概述:
    将形变剖面工作流配置、公共轨迹和采样结果编译为地图与 Cartesian
    FigurePlan，使用户配置保持简洁而绘图顺序完整可检查。

函数说明:
    ``compile_profile_figures``:
        编译两张数据地图以及每条轨迹启用的折线/散点剖面图。
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
    """Create one immutable internal profile layer."""
    tokens = section.split(".")
    return LayerOperation(
        section=section,
        method=tokens[1],
        semantics=tuple(tokens[2:]),
        options=MappingProxyType(options),
        order=order,
        handler=handler,
    )


def _map_plan(cfg: dict, name: str, dataset: dict, tracks: dict) -> FigurePlan:
    """Compile one deformation dataset map with common tracks and marker."""
    map_style = {**cfg["default_style"], **cfg["map_style"]}
    layers = (
        _layer(
            f"figure.basemap.{name}",
            "deformation_basemap",
            {
                "region": None,
                "region_grid": dataset["grd_path"],
                "projection": cfg["projection"],
                "title": dataset["title"],
                "style": map_style,
            },
            0,
        ),
        _layer(
            f"figure.grdimage.background.{name}",
            "deformation_background",
            {
                "mode": "dem",
                "dem_tif": cfg["dem_tif"],
                "dem_cpt": cfg["dem_cpt"],
                "dem_min": cfg["dem_bar_min"],
                "dem_max": cfg["dem_bar_max"],
            },
            1,
        ),
        _layer(
            f"figure.plot.deformation.{name}",
            "deformation_data",
            {
                "mode": "grd",
                "grid": dataset["grd_path"],
                "cpt": cfg["defo_cpt"],
                "cpt_reverse": cfg["defo_cpt_reverse"],
                "minimum": cfg["defo_bar_min"],
                "maximum": cfg["defo_bar_max"],
                "transparency": cfg["defo_transparency"],
                "scatter_style": "",
                "scatter_pen": "",
                "clip_kml": "",
            },
            2,
        ),
        _layer(
            f"figure.plot.profile_tracks.{name}",
            "profile_tracks",
            {
                "tracks": MappingProxyType(dict(tracks)),
                "line_pen": cfg["track_line_pen"],
                "label_font": cfg["track_label_font"],
                "start_justify": cfg["track_start_justify"],
                "end_justify": cfg["track_end_justify"],
                "end_suffix": cfg["track_end_suffix"],
            },
            3,
        ),
        _layer(
            f"figure.plot.marker.{name}",
            "profile_marker",
            {
                "enabled": cfg["marker_lon"] is not None,
                "longitude": cfg["marker_lon"],
                "latitude": cfg["marker_lat"],
                "style": cfg["marker_style"],
                "pen": cfg["marker_pen"],
                "fill": cfg["marker_fill"] or None,
            },
            4,
        ),
        _layer(
            f"figure.colorbar.deformation.{name}",
            "deformation_colorbar",
            {
                "enabled": cfg["add_colorbar"],
                "label": cfg["defo_colorbar_label"],
                "unit": cfg["defo_colorbar_unit"],
                "tick_interval": None,
            },
            5,
        ),
        _layer(
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
            6,
        ),
        _layer(
            f"figure.directional_rose.{name}",
            "deformation_rose",
            {"enabled": cfg["add_rose"]},
            7,
        ),
        _layer(
            "figure.savefig",
            "savefig",
            {"fname": dataset["output_map"], "dpi": 300},
            8,
        ),
    )
    return FigurePlan(
        config_path=Path(cfg["config_path"]),
        project=MappingProxyType({"output_dir": cfg["output_dir"]}),
        figure=MappingProxyType({"layout": "single_panel", "dataset": name}),
        operations=layers,
    )


def _profile_plan(
    cfg: dict,
    track_name: str,
    mode: str,
    dataset_cfgs: tuple[dict, dict],
    track_profiles: tuple[object, ...],
) -> FigurePlan:
    """Compile one line or scatter comparison into Cartesian layers."""
    style = {**cfg["default_style"], **cfg["profile_style"]}
    layers: list[LayerOperation] = [
        _layer(
            f"figure.basemap.profile.{track_name}.{mode}",
            "profile_basemap",
            {
                "profiles": track_profiles,
                "title": f"{cfg['profile_title_prefix']} {track_name}",
                "x_label": cfg["profile_x_label"],
                "y_label": cfg["profile_y_label"],
                "padding": cfg["profile_padding"],
                "projection": cfg["profile_projection"],
                "style": style,
            },
            0,
        )
    ]
    for index, (dataset, profile) in enumerate(zip(dataset_cfgs, track_profiles), start=1):
        options: dict[str, object] = {
            "mode": mode,
            "profile": profile,
            "label": dataset["label"],
            "pen": dataset["line_pen"] if mode == "line" else dataset["scatter_pen"],
            "style": dataset["scatter_style"],
            "fill": dataset["scatter_fill"],
            "transparency": dataset["scatter_transparency"],
        }
        layers.append(
            _layer(
                f"figure.plot.profile.{track_name}.{mode}.dataset{index}",
                "profile_series",
                options,
                len(layers),
            )
        )
    layers.append(
        _layer(
            f"figure.legend.profile.{track_name}.{mode}",
            "profile_legend",
            {
                "position": cfg["profile_legend_position"],
                "box": cfg["profile_legend_box"],
            },
            len(layers),
        )
    )
    output = str(
        Path(cfg["output_dir"])
        / f"{cfg['profile_title_prefix']}_{track_name}_{mode}.png"
    )
    layers.append(
        _layer(
            "figure.savefig",
            "savefig",
            {"fname": output, "dpi": 300},
            len(layers),
        )
    )
    return FigurePlan(
        config_path=Path(cfg["config_path"]),
        project=MappingProxyType({"output_dir": cfg["output_dir"]}),
        figure=MappingProxyType(
            {"layout": "cartesian", "dataset": f"profile:{track_name}:{mode}"}
        ),
        operations=tuple(layers),
    )


def compile_profile_figures(
    cfg: dict,
    tracks: dict,
    profiles: dict,
) -> tuple[FigurePlan, ...]:
    """Compile dataset maps and every enabled profile comparison figure."""
    datasets = (cfg["dataset1"], cfg["dataset2"])
    plans: list[FigurePlan] = [
        _map_plan(cfg, "dataset1", datasets[0], tracks),
        _map_plan(cfg, "dataset2", datasets[1], tracks),
    ]
    for track_name in tracks:
        track_profiles = tuple(profiles[track_name])
        if cfg["line_profiles"]:
            plans.append(
                _profile_plan(cfg, track_name, "line", datasets, track_profiles)
            )
        if cfg["scatter_profiles"]:
            plans.append(
                _profile_plan(cfg, track_name, "scatter", datasets, track_profiles)
            )
    return tuple(plans)


__all__ = ["compile_profile_figures"]
