"""
geodesy_visualization.grid_preparation
======================================

功能概述:
    将 Adapter 已校验或转换的 GeoTIFF、带表头点表和 Defsour 点表准备为 GMT
    绘图临时网格，并为 cfg 工作流提供来源中立的调度入口。本模块不生成正式
    科学交换产品。

函数说明:
    ``tif2grd``:
        使用 Adapter 转换临时 GeoTIFF，再生成 GMT GRD。
    ``txt2grd``:
        使用 Adapter 分块读取具名点表，再生成 GMT GRD。
    ``defsour2grd``:
        使用 Adapter 分块读取并转换 Defsour 坐标，再生成 GMT GRD。
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
from insar_data_adapter import (
    DefsourMetadata,
    DefsourPointSource,
    GeoTiffValueMetadata,
    HeaderedPointTableSource,
    PointValueMetadata,
    convert_geotiff_raster,
)
from pyproj import CRS

from geodesy_visualization.io import gmt_grdconvert, replace_dataset, temporary_path


def tif2grd(
    tif_path: str,
    grd_path: str,
    scale: float = 1.0,
    nan_to_zero: bool = True,
    target_crs: str | None = "EPSG:4326",
    metadata: GeoTiffValueMetadata | None = None,
    source_crs_override: str | None = None,
) -> List[float]:
    """Prepare a GMT grid from one Adapter-converted temporary GeoTIFF."""
    source = Path(tif_path).expanduser().resolve()
    output = Path(grd_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"input GeoTIFF not found: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)

    if metadata is None:
        metadata = GeoTiffValueMetadata(
            input_unit="unspecified by legacy visualization config",
            output_unit="unspecified by legacy visualization config",
            value_quantity="unspecified by legacy visualization config",
            los_positive="unspecified by legacy visualization config",
            nodata_policy=(
                "source nodata becomes zero" if nan_to_zero else "source nodata becomes NaN"
            ),
            temporal_reference="unspecified by legacy visualization config",
            spatial_reference="unspecified by legacy visualization config",
            source_provenance=str(source),
        )
    elif not isinstance(metadata, GeoTiffValueMetadata):
        raise TypeError("metadata must be a GeoTiffValueMetadata instance")

    with temporary_path(output.parent, ".tif") as temporary_tif:
        result = convert_geotiff_raster(
            source,
            temporary_tif,
            metadata,
            target_crs=target_crs,
            source_crs_override=source_crs_override,
            scale=scale,
            nan_to_zero=nan_to_zero,
            resampling="bilinear",
        )
        with temporary_path(output.parent, output.suffix or ".grd") as temporary_grd:
            gmt_grdconvert(str(temporary_tif), str(temporary_grd))
            replace_dataset(temporary_grd, output)

    print(f"Converted to GRD: {output}")
    return list(result.region)


def txt2grd(
    txt_path: str,
    grd_path: str,
    scale: float = 1.0,
    space: float = 0.0005,
    chunk_rows: int = 250_000,
    value_column: str | None = None,
    metadata: PointValueMetadata | None = None,
) -> List[float]:
    """Prepare a GMT grid from Adapter-validated headered lon/lat point blocks."""
    source = Path(txt_path).expanduser().resolve()
    output = Path(grd_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"input text file not found: {source}")
    if space <= 0:
        raise ValueError(f"space must be positive; got {space}")
    if chunk_rows <= 0:
        raise ValueError(f"chunk_rows must be positive; got {chunk_rows}")
    output.parent.mkdir(parents=True, exist_ok=True)
    if metadata is None:
        metadata = PointValueMetadata(
            source_format="headered_text_points",
            value_unit="unspecified by legacy visualization config",
            value_quantity="unspecified by legacy visualization config",
            los_positive="unspecified by legacy visualization config",
            crs="EPSG:4326",
            nodata_policy="non-finite coordinates are invalid; zero is valid",
            temporal_reference="unspecified by legacy visualization config",
            spatial_reference="unspecified by legacy visualization config",
            source_provenance=str(source),
        )
    elif not isinstance(metadata, PointValueMetadata):
        raise TypeError("metadata must be a PointValueMetadata instance")
    elif CRS.from_user_input(metadata.crs) != CRS.from_epsg(4326):
        raise ValueError("txt2grd requires metadata.crs to be EPSG:4326")

    bounds = [np.inf, -np.inf, np.inf, -np.inf]
    row_count = 0
    with temporary_path(output.parent, ".xyz") as temporary_xyz:
        with HeaderedPointTableSource(
            source,
            metadata,
            chunk_points=chunk_rows,
            value_column=value_column,
        ) as point_source:
            for block in point_source.iter_blocks():
                selected = pd.DataFrame(
                    {
                        "lon": block.x,
                        "lat": block.y,
                        "value": block.value * scale,
                    }
                )
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
    text_value_column: str | None = None,
    text_metadata: PointValueMetadata | None = None,
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

