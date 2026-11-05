"""
geodesy_visualization.backends.matplotlib
==========================================

功能概述:
    提供与科学分析实现解耦的 Matplotlib 字体、数组面板和时序图件组合。
    本模块不读取 InSAR 来源产品，不执行投影、参考或单位转换。

函数说明:
    ``configure_plot_font``:
        注册 Visualization 自带字体并配置 Matplotlib 默认科研绘图字体。
    ``plot_array_cube``:
        将二维数组或三维数组的全部图层绘制为规则子图网格。
    ``getfig``:
        保留 MATLAB ``getfig.m`` 参数名称的兼容包装。
    ``plot_target_timeseries``:
        绘制一个轨道中多个目标区域的 LOS 时序子图。
    ``plot_multitrack_timeseries``:
        在相同目标子图中对比多个轨道的 LOS 时序。
    ``plot_insar_gnss_comparison``:
        绘制已投影、已校正时间参考的 InSAR 和 GNSS LOS 时序。
    ``TargetSeriesLike``:
        描述目标时序绘图所需的最小只读数据接口。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from math import ceil
from pathlib import Path
from typing import Optional, Protocol

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.colorbar import Colorbar
from matplotlib.figure import Figure

from geodesy_visualization.io import atomic_output_path
from geodesy_visualization.resources import resource_path


_BUNDLED_FONT_DIR = resource_path("fonts")
_BUNDLED_FONTS_REGISTERED = False
DEFAULT_PLOT_FONT = "TeX Gyre Heros"


class TargetSeriesLike(Protocol):
    """Describe the analysis-neutral values required by target-series plots."""

    dates: Sequence[str]
    values: Mapping[str, Sequence[float]]
    unit: str


def _register_bundled_fonts() -> None:
    """向当前 Matplotlib 进程注册 Visualization 字体，不修改系统字体库。"""
    global _BUNDLED_FONTS_REGISTERED
    if _BUNDLED_FONTS_REGISTERED:
        return
    if _BUNDLED_FONT_DIR.is_dir():
        for pattern in ("*.ttf", "*.otf"):
            for font_file in sorted(_BUNDLED_FONT_DIR.rglob(pattern)):
                font_manager.fontManager.addfont(font_file)
    _BUNDLED_FONTS_REGISTERED = True


def _as_cube(data: np.ndarray) -> np.ndarray:
    """将二维输入扩展为单层三维数组，并校验图层维数。"""
    cube = np.asarray(data)
    if cube.ndim == 2:
        cube = cube[:, :, np.newaxis]
    if cube.ndim != 3:
        raise ValueError(f"data must be 2-D or 3-D, got shape {cube.shape}")
    if cube.shape[2] == 0:
        raise ValueError("data cube contains no layers")
    return cube


def _auto_limit(layer: np.ndarray) -> tuple[float, float]:
    """根据单层有限值计算显示范围，并处理空数组和常量数组。"""
    finite = np.asarray(layer, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return -1.0, 1.0
    lower = float(np.min(finite))
    upper = float(np.max(finite))
    if lower == upper:
        return lower - 0.5, upper + 0.5
    return lower, upper


def _normalize_limits(
    cube: np.ndarray,
    limits: Optional[Sequence[float] | np.ndarray],
) -> np.ndarray:
    """将共享或逐层显示范围标准化为 ``(图层数, 2)`` 数组。"""
    layer_count = cube.shape[2]
    if limits is None or np.asarray(limits).size == 1:
        return np.asarray([_auto_limit(cube[:, :, i]) for i in range(layer_count)])

    normalized = np.asarray(limits, dtype=float)
    if normalized.shape == (2,):
        normalized = np.repeat(normalized[np.newaxis, :], layer_count, axis=0)
    if normalized.shape != (layer_count, 2):
        raise ValueError(
            f"limits must have shape (2,) or ({layer_count}, 2), got {normalized.shape}"
        )

    normalized = normalized.copy()
    for index in range(layer_count):
        lower, upper = normalized[index]
        if not np.isfinite(lower) or not np.isfinite(upper) or lower == upper == 0:
            normalized[index] = _auto_limit(cube[:, :, index])
        elif lower == upper:
            normalized[index] = (lower - 0.5, upper + 0.5)
        elif lower > upper:
            normalized[index] = (upper, lower)
    return normalized


def plot_array_cube(
    data: np.ndarray,
    limits: Optional[Sequence[float] | np.ndarray] = None,
    colorbars: bool = False,
    tick_labels: bool = False,
    layout: Optional[Sequence[int]] = None,
    panel_positions: Optional[Sequence[int]] = None,
    titles: Optional[Sequence[str]] = None,
    *,
    cmap: str = "jet",
    interpolation: str = "nearest",
    figure: Optional[Figure] = None,
    dpi: int = 120,
    font_family: Optional[str] = None,
) -> tuple[Figure, list[Axes], list[Colorbar]]:
    """
    将二维数组或三维数组的全部图层绘制为紧凑子图网格。

    参数:
        data:
            ``(行, 列)`` 或 ``(行, 列, 图层)`` 数组。
        limits:
            共享 ``(最小值, 最大值)``，或每层一个范围。``None`` 和
            ``(0, 0)`` 表示按有限值自动计算。
        colorbars:
            是否为每个子图添加独立色标。
        tick_labels:
            是否显示影像行列刻度。
        layout:
            可选 ``(子图行数, 子图列数)``。
        panel_positions:
            每层使用的一基子图位置，对应 MATLAB ``newind``。
        titles:
            每层标题。
        cmap:
            Matplotlib 色表名称。
        interpolation:
            ``imshow`` 插值方式。
        figure:
            可选已有 Figure；未提供时自动创建。
        dpi:
            新建 Figure 的分辨率。
        font_family:
            Visualization 内置字体名称，默认使用 ``TeX Gyre Heros``。

    返回:
        figure:
            Matplotlib Figure。
        axes:
            按图层顺序排列的 Axes 列表。
        colorbar_objects:
            已创建的 Colorbar 列表。

    说明:
        NaN/Inf 使用透明色。函数只负责绘图，不自动保存或关闭 Figure。
    """
    configure_plot_font(font_family)
    cube = _as_cube(data)
    layer_count = cube.shape[2]
    layer_limits = _normalize_limits(cube, limits)

    if layout is None:
        panel_rows = max(1, int(np.floor(np.sqrt(layer_count))))
        panel_cols = int(np.ceil(layer_count / panel_rows))
    else:
        if len(layout) != 2:
            raise ValueError("layout must contain subplot rows and columns")
        panel_rows, panel_cols = int(layout[0]), int(layout[1])
        if panel_rows < 1 or panel_cols < 1:
            raise ValueError("subplot rows and columns must be positive")

    panel_count = panel_rows * panel_cols
    positions = (
        list(range(1, layer_count + 1))
        if panel_positions is None
        else [int(value) for value in panel_positions]
    )
    if len(positions) != layer_count:
        raise ValueError("panel_positions length must match the data layers")
    if len(set(positions)) != len(positions):
        raise ValueError("panel_positions must be unique")
    if min(positions) < 1 or max(positions) > panel_count:
        raise ValueError(f"panel positions must lie between 1 and {panel_count}")
    if titles is not None and len(titles) != layer_count:
        raise ValueError("titles length must match the data layers")

    data_aspect = cube.shape[0] / max(cube.shape[1], 1)
    panel_width = 3.5 + (0.45 if colorbars else 0.0)
    panel_height = float(np.clip(panel_width * data_aspect, 2.2, 4.2))
    if figure is None:
        figure = plt.figure(
            figsize=(panel_cols * panel_width, panel_rows * panel_height),
            dpi=dpi,
            constrained_layout=True,
        )
    grid = figure.add_gridspec(panel_rows, panel_cols)

    color_map = plt.get_cmap(cmap).copy()
    color_map.set_bad((1.0, 1.0, 1.0, 0.0))
    axes: list[Axes] = []
    colorbar_objects: list[Colorbar] = []
    for layer_index, position in enumerate(positions):
        row, col = divmod(position - 1, panel_cols)
        axis = figure.add_subplot(grid[row, col])
        image = axis.imshow(
            np.ma.masked_invalid(cube[:, :, layer_index]),
            cmap=color_map,
            vmin=float(layer_limits[layer_index, 0]),
            vmax=float(layer_limits[layer_index, 1]),
            interpolation=interpolation,
            origin="upper",
            aspect="equal",
        )
        if titles is not None:
            axis.set_title(str(titles[layer_index]), fontsize=10)
        if not tick_labels:
            axis.set_xticks([])
            axis.set_yticks([])
        if colorbars:
            colorbar_objects.append(
                figure.colorbar(image, ax=axis, pad=0.025, fraction=0.048)
            )
        axes.append(axis)
    return figure, axes, colorbar_objects


def getfig(
    data: np.ndarray,
    dls: Optional[Sequence[float] | np.ndarray] = None,
    flag_clb: bool = False,
    flag_tklb: bool = False,
    siz: Optional[Sequence[int]] = None,
    newind: Optional[Sequence[int]] = None,
    lgdstr: Optional[Sequence[str]] = None,
    **kwargs,
) -> tuple[Figure, list[Axes], list[Colorbar]]:
    """
    使用 MATLAB ``getfig`` 参数名称调用 ``plot_array_cube``。

    参数:
        data:
            二维数组或三维数组。
        dls:
            对应 ``limits``。
        flag_clb:
            对应 ``colorbars``。
        flag_tklb:
            对应 ``tick_labels``。
        siz:
            对应 ``layout``。
        newind:
            对应一基 ``panel_positions``。
        lgdstr:
            对应 ``titles``。
        **kwargs:
            继续传递 ``cmap``、``interpolation``、``figure`` 和 ``dpi``。

    返回:
        result:
            ``(figure, axes, colorbars)``。
    """
    return plot_array_cube(
        data,
        limits=dls,
        colorbars=flag_clb,
        tick_labels=flag_tklb,
        layout=siz,
        panel_positions=newind,
        titles=lgdstr,
        **kwargs,
    )


def _plot_dates(dates: Sequence[str]) -> list[datetime]:
    """将 ``YYYYMMDD`` 或含连字符日期转换为 Matplotlib datetime 列表。"""
    return [datetime.strptime(str(date).replace("-", ""), "%Y%m%d") for date in dates]


def _format_time_axis(axis: Axes, show_zero_line: bool = False) -> None:
    """统一设置时序坐标轴的网格、可选零线、日期刻度和标签旋转。"""
    axis.grid(True, color="0.88", linewidth=0.6)
    if show_zero_line:
        axis.axhline(0.0, color="0.45", linewidth=0.7)
    axis.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=7))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    axis.tick_params(axis="x", rotation=35)


def _publication_font(preferred: Optional[str] = None) -> str:
    """优先选择 Visualization 自带的论文绘图字体，避免依赖系统字体库。"""
    _register_bundled_fonts()
    candidates = (
        preferred,
        DEFAULT_PLOT_FONT,
        "Liberation Sans",
        "Liberation Serif",
        "DejaVu Sans",
    )
    for family in candidates:
        if not family:
            continue
        try:
            font_manager.findfont(
                font_manager.FontProperties(family=family),
                fallback_to_default=False,
            )
        except ValueError:
            continue
        return family
    return "DejaVu Sans"


def configure_plot_font(preferred: Optional[str] = None) -> str:
    """注册 Visualization 字体并设置当前 Matplotlib 进程的默认绘图字体。"""
    selected = _publication_font(preferred)
    plt.rcParams["font.family"] = selected
    return selected


def _set_series_y_padding(
    axis: Axes,
    *values: Sequence[float],
    fraction: float = 1.0 / 3.0,
) -> None:
    """按数据跨度扩展 Y 轴上下界，为图例和站点信息预留空白。"""
    if fraction < 0:
        raise ValueError("y padding fraction must be non-negative")
    finite_parts = [np.asarray(value, dtype=float).ravel() for value in values]
    finite = np.concatenate(finite_parts) if finite_parts else np.empty(0)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return
    lower = float(np.min(finite))
    upper = float(np.max(finite))
    span = upper - lower
    if span == 0:
        span = max(abs(lower), 1.0)
    padding = span * fraction
    axis.set_ylim(lower - padding, upper + padding)


def plot_target_timeseries(
    series: TargetSeriesLike,
    output_file: Optional[str | Path] = None,
    title: Optional[str] = None,
    columns: int = 4,
    filter_edge_days: int = 0,
    dpi: int = 300,
    color: str = "#2166ac",
    marker: str = "o",
    marker_size: float = 2.5,
    line_style: str = "-",
    line_width: float = 1.6,
    y_padding_fraction: float = 0.08,
    show_zero_line: bool = False,
    font_family: Optional[str] = None,
) -> tuple[Figure, list[Axes]]:
    """
    绘制一个轨道中多个目标区域的 LOS 时序。

    参数:
        series:
            目标区域时序对象。
        output_file:
            可选输出图片路径；未提供时仅返回绘图对象。
        title:
            总标题。
        columns:
            子图列数。
        filter_edge_days:
            在序列首尾以灰色标记的时间滤波边缘天数，0 表示不标记。
        dpi:
            保存图片分辨率。
        color, marker, marker_size:
            时序颜色、Matplotlib marker 符号及 marker 大小。
        line_style, line_width:
            连线样式和宽度；``none`` 表示只绘制离散点。
        y_padding_fraction:
            Y 轴上下各增加的数据跨度比例。
        show_zero_line:
            是否额外绘制 ``y=0`` 水平参考线，默认不绘制。
        font_family:
            Visualization 内置字体名称，默认使用 ``TeX Gyre Heros``。

    返回:
        figure:
            Matplotlib Figure。
        axes:
            与目标区域一一对应的可见 Axes 列表。

    说明:
        所有目标共享 x、y 轴范围，便于直接比较不同区域的幅度。
    """
    configure_plot_font(font_family)
    labels = list(series.values)
    if not labels:
        raise ValueError("target time series contains no columns")
    columns = max(1, min(int(columns), len(labels)))
    rows = ceil(len(labels) / columns)
    dates = _plot_dates(series.dates)
    figure, axes_array = plt.subplots(
        rows,
        columns,
        figsize=(3.8 * columns, 3.0 * rows),
        sharex=True,
        sharey=True,
        squeeze=False,
    )
    axes = list(axes_array.flat)
    for axis, label in zip(axes, labels):
        axis.plot(
            dates,
            series.values[label],
            color=color,
            linewidth=line_width,
            linestyle=line_style,
            marker=marker,
            markersize=marker_size,
        )
        axis.set_title(label, fontsize=11, fontweight="bold")
        _format_time_axis(axis, show_zero_line=show_zero_line)
        if filter_edge_days > 0:
            edge = timedelta(days=int(filter_edge_days))
            axis.axvspan(dates[0], dates[0] + edge, color="0.7", alpha=0.2, linewidth=0)
            axis.axvspan(dates[-1] - edge, dates[-1], color="0.7", alpha=0.2, linewidth=0)
    for axis in axes[len(labels) :]:
        axis.set_visible(False)
    for axis in axes_array[:, 0]:
        axis.set_ylabel(f"LOS displacement ({series.unit})")
    _set_series_y_padding(
        axes[0],
        *series.values.values(),
        fraction=y_padding_fraction,
    )
    figure.suptitle(title or "Target LOS time series", fontsize=15, fontweight="bold")
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    if output_file is not None:
        output = Path(output_file).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with atomic_output_path(output) as temporary:
            figure.savefig(temporary, dpi=dpi, bbox_inches="tight", facecolor="white")
    return figure, axes[: len(labels)]


def plot_multitrack_timeseries(
    tracks: Mapping[str, TargetSeriesLike],
    output_file: Optional[str | Path] = None,
    title: Optional[str] = None,
    colors: Optional[Mapping[str, str]] = None,
    markers: Optional[Mapping[str, str]] = None,
    marker_sizes: Optional[Mapping[str, float]] = None,
    line_styles: Optional[Mapping[str, str]] = None,
    line_widths: Optional[Mapping[str, float]] = None,
    columns: int = 4,
    filter_edge_days: int = 0,
    dpi: int = 300,
    y_padding_fraction: float = 0.08,
    show_zero_line: bool = False,
    font_family: Optional[str] = None,
) -> tuple[Figure, list[Axes]]:
    """
    在相同目标子图中对比多个轨道的 LOS 时序。

    参数:
        tracks:
            ``轨道名称 -> TargetSeriesLike`` 映射。所有轨道必须具有相同的
            目标列顺序和单位，日期数量可以不同。
        output_file:
            可选输出图片路径。
        title:
            总标题。
        colors:
            可选 ``轨道名称 -> Matplotlib 颜色`` 映射。
        markers, marker_sizes:
            可选逐轨 marker 符号和大小映射。
        line_styles, line_widths:
            可选逐轨连线样式和宽度映射；样式 ``none`` 表示只绘制点。
        columns:
            子图列数。
        filter_edge_days:
            各轨道首尾滤波边缘的灰色标记天数。
        dpi:
            保存图片分辨率。
        y_padding_fraction:
            Y 轴上下各增加的数据跨度比例。
        show_zero_line:
            是否绘制 ``y=0`` 水平参考线，默认不绘制。
        font_family:
            Visualization 内置字体名称，默认使用 ``TeX Gyre Heros``。

    返回:
        figure:
            Matplotlib Figure。
        axes:
            与目标区域对应的可见 Axes 列表。

    说明:
        函数不会改变 LOS 符号或时间参考；跨轨比较前应明确各轨道的观测
        方向和参考期。
    """
    configure_plot_font(font_family)
    if not tracks:
        raise ValueError("tracks cannot be empty")
    first = next(iter(tracks.values()))
    labels = list(first.values)
    for track, series in tracks.items():
        if list(series.values) != labels:
            raise ValueError(f"target columns for track {track} do not match")
        if series.unit != first.unit:
            raise ValueError("all tracks must use the same displacement unit")

    columns = max(1, min(int(columns), len(labels)))
    rows = ceil(len(labels) / columns)
    figure, axes_array = plt.subplots(
        rows,
        columns,
        figsize=(3.8 * columns, 3.0 * rows),
        sharey=True,
        squeeze=False,
    )
    axes = list(axes_array.flat)
    for axis, label in zip(axes, labels):
        for track, series in tracks.items():
            dates = _plot_dates(series.dates)
            axis.plot(
                dates,
                series.values[label],
                label=track,
                color=None if colors is None else colors.get(track),
                linewidth=1.5 if line_widths is None else line_widths.get(track, 1.5),
                linestyle="-" if line_styles is None else line_styles.get(track, "-"),
                marker="o" if markers is None else markers.get(track, "o"),
                markersize=2.2 if marker_sizes is None else marker_sizes.get(track, 2.2),
            )
            if filter_edge_days > 0:
                edge = timedelta(days=int(filter_edge_days))
                axis.axvspan(
                    dates[0], dates[0] + edge, color="0.7", alpha=0.12, linewidth=0
                )
                axis.axvspan(
                    dates[-1] - edge,
                    dates[-1],
                    color="0.7",
                    alpha=0.12,
                    linewidth=0,
                )
        axis.set_title(label, fontsize=11, fontweight="bold")
        _format_time_axis(axis, show_zero_line=show_zero_line)
    for axis in axes[len(labels) :]:
        axis.set_visible(False)
    for axis in axes_array[:, 0]:
        axis.set_ylabel(f"LOS displacement ({first.unit})")
    _set_series_y_padding(
        axes[0],
        *(values for series in tracks.values() for values in series.values.values()),
        fraction=y_padding_fraction,
    )
    axes[0].legend(frameon=False)
    figure.suptitle(title or "Multi-track LOS time series", fontsize=15, fontweight="bold")
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    if output_file is not None:
        output = Path(output_file).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with atomic_output_path(output) as temporary:
            figure.savefig(temporary, dpi=dpi, bbox_inches="tight", facecolor="white")
    return figure, axes[: len(labels)]


def plot_insar_gnss_comparison(
    insar_dates: Sequence[str],
    insar_values: Sequence[float],
    gnss_dates: Sequence[str],
    gnss_values: Sequence[float],
    unit: str = "mm",
    output_file: Optional[str | Path] = None,
    title: str = "InSAR and GNSS LOS comparison",
    dpi: int = 300,
    font_family: Optional[str] = None,
    y_padding_fraction: float = 1.0 / 3.0,
    insar_color: str = "#1f77b4",
    gnss_color: str = "#33147d",
    insar_marker: str = "^",
    gnss_marker: str = "o",
    insar_marker_size: float = 5.0,
    gnss_marker_size: float = 2.5,
    show_zero_line: bool = False,
) -> tuple[Figure, Axes]:
    """
    绘制 InSAR 与 GNSS 的 LOS 时序对比图。

    参数:
        insar_dates, insar_values:
            InSAR 日期和 LOS 形变。
        gnss_dates, gnss_values:
            已投影到 LOS 且已完成时间对齐的 GNSS 日期和形变。
        unit:
            两条曲线共同使用的形变单位。
        output_file:
            可选输出图片路径。
        title:
            图标题。
        dpi:
            保存图片分辨率。
        font_family:
            绘图字体。默认使用 Visualization ``fonts`` 目录内的
            ``TeX Gyre Heros``；也可选择 ``TeX Gyre Termes``、
            ``Liberation Sans`` 等字体，不依赖本机字体库。
        y_padding_fraction:
            Y 轴上下各增加的数据跨度比例，默认三分之一，用于放置图例和注记。
        insar_color, gnss_color:
            两套数据使用的 Matplotlib 颜色。
        insar_marker, gnss_marker:
            两套数据的 marker 符号。
        insar_marker_size, gnss_marker_size:
            两套数据的 marker 大小。
        show_zero_line:
            是否绘制 ``y=0`` 水平参考线，默认不绘制。

    返回:
        figure:
            Matplotlib Figure。
        axis:
            时序坐标轴。

    说明:
        本函数不执行 ENU 投影、粗差剔除或时间偏移估计，这些数值处理由
        上游 Analysis 接口完成。
    """
    selected_font = _publication_font(font_family)
    with plt.rc_context({"font.family": selected_font}):
        figure, axis = plt.subplots(figsize=(11.5, 4.5))
        axis.plot(
            _plot_dates(insar_dates),
            insar_values,
            linestyle="None",
            marker=insar_marker,
            markersize=insar_marker_size,
            color=insar_color,
            label="InSAR",
        )
        axis.plot(
            _plot_dates(gnss_dates),
            gnss_values,
            linestyle="None",
            marker=gnss_marker,
            markersize=gnss_marker_size,
            color=gnss_color,
            label="GNSS",
        )
        axis.set_xlabel("Date", fontsize=12, fontweight="bold")
        axis.set_ylabel(f"LOS displacement ({unit})", fontsize=12, fontweight="bold")
        axis.set_title(title, fontsize=14, fontweight="bold")
        _set_series_y_padding(
            axis,
            insar_values,
            gnss_values,
            fraction=y_padding_fraction,
        )
        legend = axis.legend(loc="upper right", frameon=True, fontsize=10)
        legend.get_frame().set_edgecolor("black")
        legend.get_frame().set_linewidth(0.8)
        _format_time_axis(axis, show_zero_line=show_zero_line)
        figure.tight_layout()
        if output_file is not None:
            output = Path(output_file).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            with atomic_output_path(output) as temporary:
                figure.savefig(temporary, dpi=dpi, bbox_inches="tight", facecolor="white")
    return figure, axis
