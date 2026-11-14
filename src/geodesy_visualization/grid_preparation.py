"""
geodesy_visualization.grid_preparation
======================================

功能概述:
    将上游已准备好的地理 GeoTIFF 和标准经纬度点表准备为 GMT 绘图临时网格。
    本模块只做显示缩放和临时格式准备，不解析 Defsour/canonical HDF5，
    不执行坐标重投影或科学单位转换。

函数说明:
    ``tif2grd``:
        校验已准备 GeoTIFF 的 CRS，按块应用显示缩放后生成 GMT GRD。
    ``txt2grd``:
        分块读取标准经纬度点表，再生成 GMT GRD。
    ``defsour2grd``:
        返回可操作的边界错误，要求先在 envInSAR 中完成数据转换。
    ``prepare_grid``:
        按输入类型调度临时绘图网格准备。
    ``prepare_dataset_grid``:
        按标准化工作流数据集配置准备临时绘图网格。
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import pygmt
import rasterio
from pyproj import CRS

from geodesy_visualization.io import gmt_grdconvert, replace_dataset, temporary_path


def tif2grd(
    tif_path: str,
    grd_path: str,
    scale: float = 1.0,
    nan_to_zero: bool = True,
    target_crs: str | None = "EPSG:4326",
    metadata: object | None = None,
    source_crs_override: str | None = None,
) -> List[float]:
    """Prepare a GMT grid from one already-standardized geographic GeoTIFF."""
    source = Path(tif_path).expanduser().resolve()
    output = Path(grd_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"input GeoTIFF not found: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)

    if metadata is not None or source_crs_override is not None:
        raise ValueError(
            "Visualization no longer accepts Adapter metadata or CRS overrides; "
            "prepare the GeoTIFF in envInSAR with Geodesy-DataAdapter first"
        )

    with temporary_path(output.parent, ".tif") as temporary_tif:
        with rasterio.open(source) as src:
            if src.count != 1:
                raise ValueError(f"plot-ready GeoTIFF must contain one band: {source}")
            if src.crs is None:
                raise ValueError(
                    "plot-ready GeoTIFF must declare a CRS; prepare it in envInSAR "
                    "with Geodesy-DataAdapter first"
                )
            if target_crs and CRS.from_user_input(src.crs) != CRS.from_user_input(target_crs):
                raise ValueError(
                    f"GeoTIFF CRS {src.crs} does not match requested {target_crs}; "
                    "reproject it in envInSAR with Geodesy-DataAdapter first"
                )
            region = [
                float(src.bounds.left),
                float(src.bounds.right),
                float(src.bounds.bottom),
                float(src.bounds.top),
            ]
            profile = src.profile.copy()
            profile.update(
                dtype="float32",
                count=1,
                nodata=0.0 if nan_to_zero else np.nan,
            )
            with rasterio.open(temporary_tif, "w", **profile) as dst:
                for _, window in src.block_windows(1):
                    values = src.read(1, window=window, masked=True).astype(
                        np.float32
                    )
                    scaled = values.filled(np.nan) * np.float32(scale)
                    if nan_to_zero:
                        scaled[~np.isfinite(scaled)] = 0.0
                    dst.write(scaled.astype(np.float32, copy=False), 1, window=window)
        with temporary_path(output.parent, output.suffix or ".grd") as temporary_grd:
            gmt_grdconvert(str(temporary_tif), str(temporary_grd))
            replace_dataset(temporary_grd, output)

    print(f"Converted to GRD: {output}")
    return region


def txt2grd(
    txt_path: str,
    grd_path: str,
    scale: float = 1.0,
    space: float = 0.0005,
    chunk_rows: int = 250_000,
    value_column: str | None = None,
    metadata: object | None = None,
) -> List[float]:
    """Prepare a GMT grid from a standardized headered lon/lat/value table."""
    source = Path(txt_path).expanduser().resolve()
    output = Path(grd_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"input text file not found: {source}")
    if space <= 0:
        raise ValueError(f"space must be positive; got {space}")
    if chunk_rows <= 0:
        raise ValueError(f"chunk_rows must be positive; got {chunk_rows}")
    output.parent.mkdir(parents=True, exist_ok=True)
    if metadata is not None:
        raise ValueError(
            "Visualization no longer accepts Adapter metadata objects; provide an "
            "EPSG:4326 lon/lat/value exchange table prepared in envInSAR"
        )

    columns = pd.read_csv(source, sep=r"\s+", nrows=0).columns.tolist()
    if len(columns) < 3:
        raise ValueError("point table must contain at least three named columns")
    x_column = "lon" if "lon" in columns else "longitude_deg"
    y_column = "lat" if "lat" in columns else "latitude_deg"
    if x_column not in columns or y_column not in columns:
        raise ValueError(
            "point table coordinates must be named lon/lat or "
            "longitude_deg/latitude_deg"
        )
    selected_value = value_column or columns[2]
    if selected_value not in columns or selected_value in {x_column, y_column}:
        raise ValueError(f"invalid point-table value column: {selected_value}")

    bounds = [np.inf, -np.inf, np.inf, -np.inf]
    row_count = 0
    with temporary_path(output.parent, ".xyz") as temporary_xyz:
        for block in pd.read_csv(
            source,
            sep=r"\s+",
            usecols=[x_column, y_column, selected_value],
            chunksize=chunk_rows,
        ):
            selected = pd.DataFrame({
                "lon": pd.to_numeric(block[x_column], errors="raise"),
                "lat": pd.to_numeric(block[y_column], errors="raise"),
                "value": pd.to_numeric(block[selected_value], errors="raise")
                * scale,
            })
            selected = selected[
                np.isfinite(selected["lon"]) & np.isfinite(selected["lat"])
            ]
            if selected.empty:
                continue

            bounds[0] = min(bounds[0], float(selected["lon"].min()))
            bounds[1] = max(bounds[1], float(selected["lon"].max()))
            bounds[2] = min(bounds[2], float(selected["lat"].min()))
            bounds[3] = max(bounds[3], float(selected["lat"].max()))
            selected.to_csv(
                temporary_xyz,
                sep="\t",
                columns=["lon", "lat", "value"],
                header=False,
                index=False,
                mode="a",
            )
            row_count += len(selected)

        if row_count == 0:
            raise ValueError(f"text input contains no valid coordinate rows: {source}")

        data_region = [float(value) for value in bounds]
        x_steps = max(1, int(np.ceil((data_region[1] - data_region[0]) / space)))
        y_steps = max(1, int(np.ceil((data_region[3] - data_region[2]) / space)))
        region = [
            data_region[0],
            data_region[0] + x_steps * space,
            data_region[2],
            data_region[2] + y_steps * space,
        ]
        with temporary_path(output.parent, output.suffix or ".grd") as temporary_grd:
            pygmt.xyz2grd(
                data=str(temporary_xyz),
                region=region,
                spacing=space,
                outgrid=str(temporary_grd),
            )
            replace_dataset(temporary_grd, output)

    print(f"Converted text to GRD: {output}")
    return region


def defsour2grd(
    txt_path: str,
    grd_path: str,
    input_crs: str,
    scale: float = 1.0,
    space: float = 0.0005,
    chunk_rows: int = 250_000,
    deformation_column: int = 3,
    metadata: object | None = None,
) -> List[float]:
    """Reject processing-format input at the visualization boundary."""
    raise ValueError(
        "Defsour is a processing format and is no longer read by Visualization; "
        "export GeoTIFF or an EPSG:4326 lon/lat/value table with "
        "Geodesy-DataAdapter in envInSAR, then use input_type=tif or txt"
    )


def prepare_grid(
    input_type: str,
    input_path: str,
    grd_path: str,
    scale: float = 1.0,
    space: float = 0.0005,
    nan_to_zero: bool = True,
    chunk_rows: int = 250_000,
    input_crs: str | None = None,
    deformation_column: int = 3,
    target_crs: str | None = "EPSG:4326",
    defsour_metadata: object | None = None,
    text_value_column: str | None = None,
    text_metadata: object | None = None,
) -> List[float]:
    """Convert a supported raster or point table into a geographic GMT grid."""
    normalized_type = input_type.strip().lower()
    if normalized_type == "tif":
        return tif2grd(input_path, grd_path, scale, nan_to_zero, target_crs)
    if normalized_type == "txt":
        return txt2grd(
            input_path,
            grd_path,
            scale,
            space,
            chunk_rows,
            text_value_column,
            text_metadata,
        )
    if normalized_type == "defsour":
        return defsour2grd(
            input_path,
            grd_path,
            input_crs or "",
            scale,
            space,
            chunk_rows,
            deformation_column,
            defsour_metadata,
        )
    raise ValueError(f"unsupported input_type: {input_type}; choose from tif, txt, defsour")


def prepare_dataset_grid(dataset: Dict[str, object]) -> List[float]:
    """Prepare a GMT grid from the shared plotting dataset schema."""
    required = ("input_type", "input_path", "grd_path", "scale", "space", "nan_to_zero")
    missing = [key for key in required if key not in dataset]
    if missing:
        raise ValueError(f"dataset configuration is missing: {', '.join(missing)}")
    return prepare_grid(
        input_type=str(dataset["input_type"]),
        input_path=str(dataset["input_path"]),
        grd_path=str(dataset["grd_path"]),
        scale=float(dataset["scale"]),
        space=float(dataset["space"]),
        nan_to_zero=bool(dataset["nan_to_zero"]),
        chunk_rows=int(dataset.get("chunk_rows", 250_000)),
        input_crs=str(dataset.get("input_crs") or "") or None,
        deformation_column=int(dataset.get("deformation_column", 3)),
        target_crs=str(dataset.get("target_crs", "EPSG:4326") or "") or None,
        defsour_metadata=dataset.get("defsour_metadata"),
        text_value_column=str(dataset.get("text_value_column") or "") or None,
        text_metadata=dataset.get("text_metadata"),
    )

__all__ = [
    "defsour2grd",
    "prepare_dataset_grid",
    "prepare_grid",
    "tif2grd",
    "txt2grd",
]

