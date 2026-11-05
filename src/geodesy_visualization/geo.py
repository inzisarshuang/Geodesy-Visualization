"""
geodesy_visualization.geo
=========================

功能概述:
    提供可视化工作流所需的网格范围读取、剖面轨迹生成和沿轨迹采样功能。
    本模块只生成图件视图数据，不负责来源格式解析、科学单位转换、重投影或
    持久科学产品导出。

函数说明:
    ``region_from_grd``:
        从 GMT 可读网格提取绘图范围。
    ``generate_tracks``:
        在多组起止坐标之间生成命名的等间距剖面轨迹。
    ``extract_profile``:
        沿指定轨迹采样网格，并计算 WGS84 累计距离。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pygmt
from pyproj import Geod


def region_from_grd(grid_path: str) -> List[float]:
    """Return a GMT-readable grid region as ``[xmin, xmax, ymin, ymax]``."""
    info_text = pygmt.grdinfo(grid=grid_path, per_column="n")
    values = np.fromstring(info_text, sep=" ")
    if values.size < 4:
        raise ValueError(f"cannot parse grid region: {grid_path}")
    return values[:4].astype(float).tolist()


def generate_tracks(
    start_coords: List[Tuple[float, float]],
    end_coords: List[Tuple[float, float]],
    num_points: int = 100,
    pointnames: Optional[List[str]] = None,
) -> Dict[str, np.ndarray]:
    """Generate named, evenly spaced profile tracks between coordinate pairs."""
    if len(start_coords) != len(end_coords):
        raise ValueError(
            "start_coords and end_coords must have the same length; "
            f"got {len(start_coords)} and {len(end_coords)}"
        )
    if not start_coords:
        raise ValueError("at least one profile track is required")
    if num_points < 2:
        raise ValueError(f"num_points must be at least 2; got {num_points}")

    if pointnames is None:
        pointnames = [chr(ord("A") + index) for index in range(len(start_coords))]
    if len(pointnames) != len(start_coords):
        raise ValueError(
            "pointnames must match the number of profile tracks; "
            f"got {len(pointnames)} names and {len(start_coords)} tracks"
        )
    if len(set(pointnames)) != len(pointnames):
        raise ValueError("pointnames must be unique")

    tracks: Dict[str, np.ndarray] = {}
    for name, start, end in zip(pointnames, start_coords, end_coords):
        lons = np.linspace(start[0], end[0], num_points)
        lats = np.linspace(start[1], end[1], num_points)
        tracks[name] = np.column_stack((lons, lats))
    return tracks


def extract_profile(
    grd_file: str,
    track: np.ndarray,
    newcolname: str = "z",
) -> pd.DataFrame:
    """Sample a GMT grid along a track and append WGS84 cumulative distance."""
    track_array = np.asarray(track, dtype=float)
    if track_array.ndim != 2 or track_array.shape[1] != 2 or len(track_array) < 2:
        raise ValueError("track must have shape (n, 2) with at least two lon/lat points")

    profile: pd.DataFrame = pygmt.grdtrack(
        points=track_array,
        grid=grd_file,
        newcolname=newcolname,
    )
    if profile.shape[1] < 3:
        raise ValueError(f"grdtrack returned fewer than three columns for {grd_file}")
    profile = profile.iloc[:, :3].copy()
    profile.columns = ["lon", "lat", newcolname]
    if len(profile) == 0:
        profile["distance"] = pd.Series(dtype=float)
        return profile

    geod = Geod(ellps="WGS84")
    lons = profile["lon"].to_numpy(dtype=float)
    lats = profile["lat"].to_numpy(dtype=float)
    _, _, segment_distances = geod.inv(lons[:-1], lats[:-1], lons[1:], lats[1:])
    profile["distance"] = np.concatenate(([0.0], np.cumsum(segment_distances)))
    return profile


__all__ = ["extract_profile", "generate_tracks", "region_from_grd"]
