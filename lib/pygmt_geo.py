"""
pygmt_geo
=========

功能概述:
    集中提供低内存地理栅格运算、GeoTIFF/TXT 到 GMT GRD 转换、
    网格范围读取、剖面轨迹生成和空间采样功能。

函数说明:
    ``_validate_matching_grids``:
        校验两幅栅格的尺寸、仿射变换和坐标参考系是否一致。
    ``add_tifs``:
        按窗口相加两幅共网格单波段 GeoTIFF，并按配置传播空值。
    ``region_from_grd``:
        兼容重导出正式包中的网格绘图范围读取函数。
    ``tif2grd``:
        按窗口读取、缩放 GeoTIFF，并转换为 GMT GRD。
    ``txt2grd``:
        分块读取经纬度点表，缩放数值并转换为 GMT GRD。
    ``defsour2grd``:
        读取无表头 X/Y/高程/形变 Defsour 表并重投影到经纬度网格。
    ``prepare_grid``:
        根据输入类型统一调度 TIF 或 TXT 网格转换。
    ``prepare_dataset_grid``:
        根据公共数据集配置结构准备 GMT GRD。
    ``generate_tracks`` / ``extract_profile``:
        兼容重导出正式包中的剖面轨迹生成和沿轨迹采样函数。
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import sys

import numpy as np
import pandas as pd
import pygmt
import rasterio
from insar_data_adapter import DefsourMetadata, DefsourPointSource
from pyproj import CRS
from rasterio.enums import Resampling
from rasterio.transform import array_bounds
from rasterio.warp import calculate_default_transform, reproject

from geodesy_visualization.io import gmt_grdconvert, replace_dataset, temporary_path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from geodesy_visualization.geo import extract_profile, generate_tracks, region_from_grd


def _validate_matching_grids(src1: rasterio.io.DatasetReader, src2: rasterio.io.DatasetReader) -> None:
    """Ensure two rasters share the same pixel grid before arithmetic."""
    mismatches = []
    if (src1.width, src1.height) != (src2.width, src2.height):
        mismatches.append("dimensions")
    if src1.transform != src2.transform:
        mismatches.append("transform")
    if src1.crs != src2.crs:
        mismatches.append("CRS")
    if mismatches:
        raise ValueError(f"input rasters do not share the same grid: {', '.join(mismatches)}")


def add_tifs(
    tif1_path: str,
    tif2_path: str,
    out_tif: str,
    mask_any: bool = True,
) -> None:
    """Add two single-band GeoTIFFs using bounded-memory window reads.

    将两幅共网格单波段 GeoTIFF 按像元相加，并使用分块读取限制内存占用。

    Parameters
    ----------
    tif1_path, tif2_path : str
        Input GeoTIFF paths. Their dimensions, transform, and CRS must match.
        输入文件路径；两者的尺寸、仿射变换和坐标系必须一致。
    out_tif : str
        Output GeoTIFF path. The file is replaced only after a complete write.
        输出路径；仅在完整写入成功后替换目标文件。
    mask_any : bool, default=True
        If True, output nodata when either input is nodata. If False, treat one
        missing operand as zero and output nodata only when both are nodata.
        为 True 时任一输入为空即输出空值；为 False 时单侧空值按零处理，
        仅两侧均为空时输出空值。
    """
    source1 = Path(tif1_path).expanduser().resolve()
    source2 = Path(tif2_path).expanduser().resolve()
    output = Path(out_tif).expanduser().resolve()
    for source in (source1, source2):
        if not source.is_file():
            raise FileNotFoundError(f"input GeoTIFF not found: {source}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with temporary_path(output.parent, output.suffix or ".tif") as temporary_output:
        with rasterio.open(source1) as src1, rasterio.open(source2) as src2:
            if src1.count < 1 or src2.count < 1:
                raise ValueError("both input rasters must contain at least one band")
            _validate_matching_grids(src1, src2)

            profile = src1.profile.copy()
            profile.update(count=1, dtype="float32", nodata=np.nan)
            with rasterio.open(temporary_output, "w", **profile) as dst:
                for _, window in src1.block_windows(1):
                    arr1 = src1.read(1, window=window, masked=True).filled(np.nan).astype("float32")
                    arr2 = src2.read(1, window=window, masked=True).filled(np.nan).astype("float32")
                    nan1 = np.isnan(arr1)
                    nan2 = np.isnan(arr2)

                    if mask_any:
                        result = arr1 + arr2
                        result[nan1 | nan2] = np.nan
                    else:
                        result = np.nan_to_num(arr1, nan=0.0) + np.nan_to_num(arr2, nan=0.0)
                        result[nan1 & nan2] = np.nan
                    dst.write(result.astype("float32", copy=False), 1, window=window)

        replace_dataset(temporary_output, output)

    print(f"Output saved to: {output}")


def tif2grd(
    tif_path: str,
    grd_path: str,
    scale: float = 1.0,
    nan_to_zero: bool = True,
    target_crs: str | None = "EPSG:4326",
) -> List[float]:
    """Convert one GeoTIFF band to a scaled GMT grid, optionally reprojecting it."""
    source = Path(tif_path).expanduser().resolve()
    output = Path(grd_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"input GeoTIFF not found: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(source) as src:
        if src.count < 1:
            raise ValueError(f"input GeoTIFF has no raster bands: {source}")
        destination_crs = CRS.from_user_input(target_crs) if target_crs else src.crs
        if destination_crs is None:
            raise ValueError(f"input GeoTIFF has no CRS and target_crs was not provided: {source}")
        if src.crs is not None and CRS.from_user_input(src.crs) != destination_crs:
            transform, width, height = calculate_default_transform(
                src.crs, destination_crs, src.width, src.height, *src.bounds
            )
        else:
            transform, width, height = src.transform, src.width, src.height
        left, bottom, right, top = array_bounds(height, width, transform)
        region = [left, right, bottom, top]
        profile = src.profile.copy()
        profile.update(
            count=1,
            width=width,
            height=height,
            transform=transform,
            crs=destination_crs,
            dtype=rasterio.float32,
            nodata=0 if nan_to_zero else np.nan,
        )

        with temporary_path(output.parent, ".tif") as temporary_tif:
            with rasterio.open(temporary_tif, "w", **profile) as dst:
                reproject(
                    source=rasterio.band(src, 1),
                    destination=rasterio.band(dst, 1),
                    src_transform=src.transform,
                    src_crs=src.crs or destination_crs,
                    src_nodata=src.nodata,
                    dst_transform=transform,
                    dst_crs=destination_crs,
                    dst_nodata=profile["nodata"],
                    resampling=Resampling.bilinear,
                )
            with rasterio.open(temporary_tif, "r+") as dst:
                for _, window in dst.block_windows(1):
                    data = dst.read(1, window=window, masked=True).astype("float32")
                    scaled = data.filled(np.nan) * np.float32(scale)
                    if nan_to_zero:
                        scaled = np.nan_to_num(scaled, nan=0.0)
                    dst.write(scaled.astype("float32", copy=False), 1, window=window)

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
) -> List[float]:
    """Convert a lon/lat/value text table to a GMT grid using chunked reads."""
    source = Path(txt_path).expanduser().resolve()
    output = Path(grd_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"input text file not found: {source}")
    if space <= 0:
        raise ValueError(f"space must be positive; got {space}")
    if chunk_rows <= 0:
        raise ValueError(f"chunk_rows must be positive; got {chunk_rows}")
    output.parent.mkdir(parents=True, exist_ok=True)

    bounds = [np.inf, -np.inf, np.inf, -np.inf]
    row_count = 0
    with temporary_path(output.parent, ".xyz") as temporary_xyz:
        for chunk in pd.read_csv(source, sep=r"\s+", chunksize=chunk_rows):
            if len(chunk.columns) < 3 or "lon" not in chunk or "lat" not in chunk:
                raise ValueError(
                    f"text input must contain lon/lat headers and at least three columns: {source}"
                )
            value_column = chunk.columns[2]
            selected = chunk.loc[:, ["lon", "lat", value_column]].copy()
            selected["lon"] = pd.to_numeric(selected["lon"], errors="raise")
            selected["lat"] = pd.to_numeric(selected["lat"], errors="raise")
            selected[value_column] = pd.to_numeric(selected[value_column], errors="raise") * scale
            selected = selected[np.isfinite(selected["lon"]) & np.isfinite(selected["lat"])]
            if selected.empty:
                continue

            bounds[0] = min(bounds[0], float(selected["lon"].min()))
            bounds[1] = max(bounds[1], float(selected["lon"].max()))
            bounds[2] = min(bounds[2], float(selected["lat"].min()))
            bounds[3] = max(bounds[3], float(selected["lat"].max()))
            selected.to_csv(
                temporary_xyz,
                sep="\t",
                columns=["lon", "lat", value_column],
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
    metadata: DefsourMetadata | None = None,
) -> List[float]:
    """Prepare a WGS84 GMT grid from Adapter-validated Defsour point blocks.

    ``metadata`` is optional only for compatibility with existing visualization
    cfg files. The compatibility record explicitly marks unavailable scientific
    semantics as unspecified; it does not infer units, LOS sign, or references.
    """
    source = Path(txt_path).expanduser().resolve()
    output = Path(grd_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Defsour text file not found: {source}")
    if not input_crs:
        raise ValueError("input_crs is required for Defsour coordinates")
    if deformation_column < 0:
        raise ValueError("deformation_column must be a zero-based non-negative index")
    if space <= 0 or chunk_rows <= 0:
        raise ValueError("space and chunk_rows must be positive")
    output.parent.mkdir(parents=True, exist_ok=True)
    if metadata is None:
        metadata = DefsourMetadata(
            input_crs=input_crs,
            deformation_unit="unspecified by legacy visualization config",
            deformation_quantity="unspecified snapshot deformation",
            height_unit="unspecified by legacy visualization config",
            los_positive="unspecified by legacy visualization config",
            nodata_policy="non-finite deformation is excluded; zero is valid",
            temporal_reference="unspecified by legacy visualization config",
            spatial_reference="unspecified by legacy visualization config",
            source_provenance=str(source),
        )
    elif not isinstance(metadata, DefsourMetadata):
        raise TypeError("metadata must be a DefsourMetadata instance")
    elif CRS.from_user_input(metadata.input_crs) != CRS.from_user_input(input_crs):
        raise ValueError("metadata.input_crs must match input_crs")
    bounds = [np.inf, -np.inf, np.inf, -np.inf]
    row_count = 0
    with temporary_path(output.parent, ".xyz") as temporary_xyz:
        with DefsourPointSource(
            source,
            metadata,
            chunk_points=chunk_rows,
            deformation_column=deformation_column,
        ) as point_source:
            for block in point_source.iter_blocks(target_crs="EPSG:4326"):
                selected = pd.DataFrame(
                    {
                        "lon": block.x,
                        "lat": block.y,
                        "value": block.deformation * scale,
                    }
                )
                selected = selected[np.isfinite(selected).all(axis=1)]
                if selected.empty:
                    continue
                bounds[0] = min(bounds[0], float(selected["lon"].min()))
                bounds[1] = max(bounds[1], float(selected["lon"].max()))
                bounds[2] = min(bounds[2], float(selected["lat"].min()))
                bounds[3] = max(bounds[3], float(selected["lat"].max()))
                selected.to_csv(
                    temporary_xyz, sep="\t", header=False, index=False, mode="a"
                )
                row_count += len(selected)
        if row_count == 0:
            raise ValueError(f"Defsour input contains no valid coordinate rows: {source}")
        x_steps = max(1, int(np.ceil((bounds[1] - bounds[0]) / space)))
        y_steps = max(1, int(np.ceil((bounds[3] - bounds[2]) / space)))
        region = [
            float(bounds[0]),
            float(bounds[0] + x_steps * space),
            float(bounds[2]),
            float(bounds[2] + y_steps * space),
        ]
        with temporary_path(output.parent, output.suffix or ".grd") as temporary_grd:
            pygmt.xyz2grd(data=str(temporary_xyz), region=region, spacing=space, outgrid=str(temporary_grd))
            replace_dataset(temporary_grd, output)
    print(f"Converted Defsour table to GRD: {output}")
    return region


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
    defsour_metadata: DefsourMetadata | None = None,
) -> List[float]:
    """Convert a supported raster or point table into a geographic GMT grid."""
    normalized_type = input_type.strip().lower()
    if normalized_type == "tif":
        return tif2grd(input_path, grd_path, scale, nan_to_zero, target_crs)
    if normalized_type == "txt":
        return txt2grd(input_path, grd_path, scale, space, chunk_rows)
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
    )


__all__ = [
    "add_tifs",
    "defsour2grd",
    "extract_profile",
    "generate_tracks",
    "prepare_dataset_grid",
    "prepare_grid",
    "region_from_grd",
    "tif2grd",
    "txt2grd",
]
