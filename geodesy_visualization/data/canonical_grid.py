"""
geodesy_visualization.data.canonical_grid
==========================================

功能概述:
    通过 ``insar-data-adapter`` 公共 API 读取标准规则栅格 HDF5，为可视化工作流
    提供显式时期选择、坐标轴、单位、CRS、注册方式及受控内存行块。本模块不访问
    Adapter 私有 handle，不缩放形变，不改变 nodata、掩膜或时空参考。

函数说明:
    ``CanonicalGridSelection``:
        保存一基闭区间选择转换后的零基时期索引、日期、坐标和科学元数据。
    ``GridEpochBlock``:
        表示单个时期内一个左闭右开连续行块。
    ``load_canonical_grid_selection``:
        校验标准 HDF5、可选预期单位/CRS及时期范围，返回轻量选择对象。
    ``iter_canonical_grid_blocks``:
        重新验证选择对应产品，并按受控行块产生原始形变和静态有效掩膜。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

from insar_data_adapter import CanonicalGridReader, GridMetadata


_TARGET_BLOCK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class CanonicalGridSelection:
    """Describe selected canonical-grid epochs without materializing their values."""

    path: Path
    epoch_indices: tuple[int, ...]
    dates: tuple[str, ...]
    x: np.ndarray
    y: np.ndarray
    epoch_count: int
    rows: int
    columns: int
    metadata: GridMetadata


@dataclass(frozen=True)
class GridEpochBlock:
    """Carry one epoch's raw values and valid mask for a contiguous row range."""

    epoch_index: int
    date: str
    row_start: int
    row_stop: int
    y: np.ndarray
    values: np.ndarray
    valid_mask: np.ndarray


def _readonly_axis(values: np.ndarray) -> np.ndarray:
    """Return one float64 axis copy that callers cannot mutate accidentally."""
    axis = np.array(values, dtype=np.float64, copy=True)
    axis.setflags(write=False)
    return axis


def load_canonical_grid_selection(
    input_file: str | Path,
    start_epoch: int = 1,
    end_epoch: int | None = None,
    *,
    expected_unit: str | None = None,
    expected_crs: str | None = None,
) -> CanonicalGridSelection:
    """Validate a canonical grid and select a one-based inclusive epoch range."""
    path = Path(input_file).expanduser().resolve()
    with CanonicalGridReader(path) as reader:
        summary = reader.summary
        metadata = reader.metadata
        if summary is None:
            raise RuntimeError("canonical grid summary is unavailable")
        if len(summary.deformation_shape) != 3:
            raise ValueError(
                f"canonical grid displacement must have three dimensions: {path}"
            )
        epoch_count, rows, columns = summary.deformation_shape
        stop_epoch = epoch_count if end_epoch is None else int(end_epoch)
        first_epoch = int(start_epoch)
        if first_epoch < 1 or stop_epoch < first_epoch or stop_epoch > epoch_count:
            raise ValueError(
                "epoch selection must be a one-based inclusive range within "
                f"1..{epoch_count}; got {first_epoch}..{stop_epoch}"
            )
        if expected_unit is not None and metadata.deformation_unit != expected_unit:
            raise ValueError(
                f"deformation unit mismatch: expected {expected_unit}, "
                f"got {metadata.deformation_unit}"
            )
        if expected_crs is not None and metadata.crs != expected_crs:
            raise ValueError(f"CRS mismatch: expected {expected_crs}, got {metadata.crs}")
        x = _readonly_axis(reader.read_axis("x"))
        y = _readonly_axis(reader.read_axis("y"))
        if x.shape != (columns,) or y.shape != (rows,):
            raise ValueError("canonical coordinate axes do not match displacement dimensions")
        indices = tuple(range(first_epoch - 1, stop_epoch))
        dates = tuple(summary.dates[index] for index in indices)

    return CanonicalGridSelection(
        path=path,
        epoch_indices=indices,
        dates=dates,
        x=x,
        y=y,
        epoch_count=epoch_count,
        rows=rows,
        columns=columns,
        metadata=metadata,
    )


def _effective_chunk_rows(selection: CanonicalGridSelection, chunk_rows: int) -> int:
    """Limit one values-plus-mask row block to approximately one MiB."""
    requested = int(chunk_rows)
    if requested < 1:
        raise ValueError("chunk_rows must be positive")
    bytes_per_row = selection.columns * (
        np.dtype("float32").itemsize + np.dtype("uint8").itemsize
    )
    memory_limited = max(1, _TARGET_BLOCK_BYTES // max(1, bytes_per_row))
    return min(requested, selection.rows, memory_limited)


def iter_canonical_grid_blocks(
    selection: CanonicalGridSelection,
    *,
    chunk_rows: int = 256,
) -> Iterator[GridEpochBlock]:
    """Yield selected canonical deformation and masks by epoch-major row blocks."""
    block_rows = _effective_chunk_rows(selection, chunk_rows)
    with CanonicalGridReader(selection.path) as reader:
        summary = reader.summary
        if summary is None:
            raise RuntimeError("canonical grid summary is unavailable")
        if (
            summary.deformation_shape != (
                selection.epoch_count,
                selection.rows,
                selection.columns,
            )
            or tuple(summary.dates[index] for index in selection.epoch_indices)
            != selection.dates
            or reader.metadata != selection.metadata
            or not np.array_equal(reader.read_axis("x"), selection.x)
            or not np.array_equal(reader.read_axis("y"), selection.y)
        ):
            raise RuntimeError("canonical grid changed after the selection was created")

        for epoch_index, date in zip(selection.epoch_indices, selection.dates):
            for row_start in range(0, selection.rows, block_rows):
                row_stop = min(row_start + block_rows, selection.rows)
                yield GridEpochBlock(
                    epoch_index=epoch_index,
                    date=date,
                    row_start=row_start,
                    row_stop=row_stop,
                    y=selection.y[row_start:row_stop],
                    values=reader.read_epoch(epoch_index, row_start, row_stop),
                    valid_mask=reader.read_geometry_rows(
                        "valid_mask", row_start, row_stop
                    ).astype(bool, copy=False),
                )


__all__ = [
    "CanonicalGridSelection",
    "GridEpochBlock",
    "iter_canonical_grid_blocks",
    "load_canonical_grid_selection",
]
