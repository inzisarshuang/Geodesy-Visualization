"""
pygmt_geo
=========

功能概述:
    保留旧地理辅助 API。栅格相加仍为待分类 Analysis 候选；临时网格准备、
    网格范围、剖面轨迹和采样均从正式 geodesy_visualization 模块重导出。

函数说明:
    ``_validate_matching_grids``:
        校验两幅栅格的尺寸、仿射变换和坐标参考系是否一致。
    ``add_tifs``:
        按窗口相加两幅共网格单波段 GeoTIFF，并按配置传播空值。
    ``region_from_grd``:
        兼容重导出正式包中的网格绘图范围读取函数。
    ``tif2grd``:
        兼容重导出正式包中的 GeoTIFF 临时制网函数。
    ``txt2grd``:
        兼容重导出正式包中的具名点表临时制网函数。
    ``defsour2grd``:
        兼容重导出正式包中的 Defsour 临时制网函数。
    ``prepare_grid``:
        兼容重导出正式包中的绘图网格准备调度器。
    ``prepare_dataset_grid``:
        根据公共数据集配置结构准备 GMT GRD。
    ``generate_tracks`` / ``extract_profile``:
        兼容重导出正式包中的剖面轨迹生成和沿轨迹采样函数。
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import rasterio

from geodesy_visualization.io import replace_dataset, temporary_path

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


from geodesy_visualization.grid_preparation import (
    defsour2grd,
    prepare_dataset_grid,
    prepare_grid,
    tif2grd,
    txt2grd,
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
