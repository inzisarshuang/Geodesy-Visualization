"""
geodesy_visualization.backends.pygmt
=====================================

功能概述:
    集中提供 PyGMT 图形状态管理、地图底图、形变网格、剖面轨迹、
    二维剖面、色标、比例尺、指北针和图例绘制功能。

函数说明:
    ``PyGMTPlotter``:
        封装可链式调用的 PyGMT 绘图流程，并管理图形状态和缓存目录。
    图形状态:
        ``PyGMTPlotter.new``:
            创建新 Figure 并应用当前 GMT 默认样式。
        ``PyGMTPlotter.set_defaults`` / ``PyGMTPlotter.reset_defaults``:
            更新或恢复当前绘图器的默认样式。
        ``PyGMTPlotter.save``:
            通过同目录临时文件安全保存最终图像。
    地图绘制:
        ``PyGMTPlotter.draw_geo_basemap``:
            绘制地理坐标边框、刻度和标题。
        ``PyGMTPlotter.draw_dem`` / ``PyGMTPlotter.draw_optic``:
            绘制 DEM 阴影或光学影像底图。
        ``PyGMTPlotter.draw_defo_grd`` / ``PyGMTPlotter.draw_defo_scatter``:
            以网格或散点方式绘制形变数据。
        ``PyGMTPlotter.add_colorbar`` / ``PyGMTPlotter.add_scale``:
            添加颜色条和地图比例尺。
        ``PyGMTPlotter.add_rose`` / ``PyGMTPlotter.add_marker``:
            添加指北针和单点标记。
        ``PyGMTPlotter.draw_profile_tracks``:
            绘制命名剖面轨迹及其起止点标签。
    剖面绘制:
        ``PyGMTPlotter.draw_math_basemap``:
            根据一个或多个剖面自动建立二维坐标框架。
        ``PyGMTPlotter.draw_line_2d`` / ``PyGMTPlotter.draw_scatter_2d``:
            绘制折线或散点剖面数据。
        ``PyGMTPlotter.add_legend``:
            添加剖面图例。

作者:
    谭逸伦，SIGM@3D Laboratory，中南大学地球科学与信息物理学院。
"""

from hashlib import sha256
from pathlib import Path
from typing import Dict, List, Optional, Sequence
import os
import tempfile
import pygmt
import numpy as np
import pandas as pd

from ..io import gdal_translate, replace_dataset, temporary_path

# 默认基础绘图参数
DEFAULTS = dict(
    FONT_TITLE="20p,TeX Gyre Heros-Bold",
    FONT_ANNOT_PRIMARY="12p,TeX Gyre Heros-Bold",
    FONT_ANNOT_SECONDARY="12p,TeX Gyre Heros-Bold",
    FONT_LABEL="20p,TeX Gyre Heros-Bold",
)


class PyGMTPlotter:
    """
    基于 pygmt 的绘图器，初始化设置为 Figure 对象与默认绘图参数 config 。

    参数 (Parameters)
    ----------
    defaults : dict, optional
        初始化时用于覆盖默认绘图参数的字典（键为 GMT 配置项，如 FONT_TITLE 等）。
        若为 None，则使用原有的默认 DEFAULTS 的备份 。

    属性 (Attributes)
    ----------
    fig : pygmt.Figure or None
        当前绘图对象。调用 new() 前为 None，new() 后为有效对象。
    _base_defaults : dict
        默认样式的副本，用于 reset_defaults() 恢复到初始参数设置。
    defaults : dict
        当前实例的可修改默认样式；new() 时会一次性应用到 GMT 会话。
    """

    def __init__(self, defaults: dict | None = None, cache_dir: str | None = None):
        """Initialize figure state, GMT defaults, and the derived-grid cache directory."""
        self.fig = None
        self._base_defaults = (defaults or DEFAULTS).copy()
        self.defaults = self._base_defaults.copy()
        self.cache_dir = (
            Path(cache_dir).expanduser().resolve()
            if cache_dir
            else Path(tempfile.gettempdir()) / "pygmt-plotter-cache"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _require_figure(self) -> pygmt.Figure:
        """Return the active figure or fail with an actionable message."""
        if self.fig is None:
            raise RuntimeError("请先调用 new() 创建绘图对象 / call new() before drawing")
        return self.fig

    # ------------------------- 默认绘图参数更新方法 -------------------------

    def new(self) -> "PyGMTPlotter":
        """
        开始一张“全新”的图：新建 Figure 并应用当前默认样式到 GMT 会话。
        Start a new figure and apply current defaults to the GMT session.

        步骤 (What it does)
        -------------------
        1) self.fig = pygmt.Figure()
        2) pygmt.config(**self.defaults) 一次性写入当前默认样式（字体等）

        注意 (Notes)
        ------------
        - 想让 set_defaults() 的修改生效，需在下一次绘图前调用 new()。
        - 建议每张图都先调用一次 new() 以确保样式可控、可复现。

        返回 (Returns)
        -------
        self : PyGMTPlotter
            支持链式调用。
        """
        self.fig = pygmt.Figure()
        pygmt.config(**self.defaults)
        return self

    def set_defaults(self, **kwargs) -> "PyGMTPlotter":
        """
        更新当前实例的默认样式（不会立刻影响已开启的图，会在下一次 new() 生效）。
        Update defaults for this instance; will take effect on next `new()`.

        参数 (Parameters)
        ----------
        **kwargs :
            形如 FONT_TITLE="24p,TeX Gyre Heros-Bold" 等 GMT 配置项键值。

        返回 (Returns)
        -------
        self : PyGMTPlotter
            支持链式调用。
        """
        self.defaults.update(kwargs)
        return self

    def reset_defaults(self) -> "PyGMTPlotter":
        """
        将当前实例的绘图默认参数恢复为原始设置。
        Reset this instance's defaults back to baseline.

        返回 (Returns)
        -------
        self : PyGMTPlotter
            支持链式调用。
        """
        self.defaults = self._base_defaults.copy()
        return self

    def save(
        self,
        output_file: str,
        dpi: int = 300,
        canvas_margin: str | None = None,
    ) -> "PyGMTPlotter":
        """
        保存当前图像到文件。
        Save current figure to file.

        参数 (Parameters)
        ----------
        output_file : str
            输出文件路径（例如 "SBAS_AllRegion.png"）。
            Output file path (e.g., "SBAS_AllRegion.png").
        dpi : int, optional
            Raster output resolution. Vector formats retain vector geometry.
            栅格图输出分辨率；矢量格式仍保留矢量几何。
        canvas_margin : str or None, optional
            Extra margin around GMT's tight bounding box, such as ``"0.35c"``.
            GMT 紧致裁剪边界外的附加留白，例如 ``"0.35c"``。

        返回 (Returns)
        -------
        self : PyGMTPlotter
            支持链式调用。
        """
        figure = self._require_figure()
        output = Path(output_file).expanduser().resolve()
        if not output.suffix:
            raise ValueError(f"output file must include an extension: {output_file}")
        if dpi <= 0:
            raise ValueError(f"dpi must be positive; got {dpi}")
        output.parent.mkdir(parents=True, exist_ok=True)
        with temporary_path(output.parent, output.suffix) as temporary_output:
            save_options = {"dpi": dpi}
            if canvas_margin:
                save_options["resize"] = f"+m{canvas_margin}"
            figure.savefig(str(temporary_output), **save_options)
            os.replace(temporary_output, output)
        print(f"图像已保存：{output_file}")
        return self

    # ------------------------- 绘图步骤方法（无返回值） -------------------------

    def draw_geo_basemap(
        self,
        region: List[float],
        projection: str,
        title: str,
    ) -> "PyGMTPlotter":
        """
        绘制底图框（花式边框 + 三等分轴注 + 标题）。
        Draw map frame with fancy border, 3-part ticks, and title.

        参数 (Parameters)
        ----------
        region : List[float]
            地图区域范围 [xmin, xmax, ymin, ymax]。
        projection : str
            投影字符串，例如 "M8i"（墨卡托，宽 8 英寸）。
        title : str
            图幅标题，将显示在图上方。

        返回 (Returns)
        -------
        None
        """
        factor = 3
        figure = self._require_figure()
        x_stride = round((region[1] - region[0]) / factor, 4)
        y_stride = round((region[3] - region[2]) / factor, 4)
        x_anno = f"a{x_stride}fg"
        y_anno = f"a{y_stride}fg"
        with pygmt.config(
            MAP_FRAME_TYPE="fancy",
            MAP_FRAME_WIDTH="6p",
            FONT_ANNOT="18p,TeX Gyre Heros-Bold",
            MAP_FRAME_PEN="3p",
            MAP_TICK_PEN="3p",
            FORMAT_GEO_MAP="ddd:mm:ss",
        ):
            figure.basemap(
                region=region,
                projection=projection,
                frame=[f"x{x_anno}", f"y{y_anno}", f"+t{title}"],
            )

        return self

    def draw_dem(
        self,
        dem_tif: str,
        region: List[float],
        projection: str,
        cpt: str = "gray",
        bar_min: float = 700,
        bar_max: float = 2500,
        dem_grd: Optional[str] = None,
        demgradient_grd: Optional[str] = None,
    ) -> "PyGMTPlotter":
        """
        绘制 DEM 灰度底图并叠加阴影（hillshade）。
        Render DEM in grayscale with hillshade.

        参数 (Parameters)
        ----------
        dem_tif : str
            DEM 的 GeoTIFF 文件路径。
        region : List[float]
            地图区域范围 [xmin, xmax, ymin, ymax]。
        projection : str
            投影字符串，例如 "M8i"。
        dem_grd : str, optional
            中间产物：DEM 的 GSBG（GMT grid）路径，不存在时自动生成。
        demgradient_grd : str, optional
            中间产物：DEM 阴影（梯度）GSBG 路径，不存在时自动生成。

        返回 (Returns)
        -------
        None
        """
        figure = self._require_figure()
        source = Path(dem_tif).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"DEM GeoTIFF not found: {source}")

        signature = f"{source}:{source.stat().st_size}:{source.stat().st_mtime_ns}"
        cache_key = sha256(signature.encode("utf-8")).hexdigest()[:16]
        dem_grid = (
            Path(dem_grd).expanduser().resolve()
            if dem_grd
            else self.cache_dir / f"{cache_key}_dem.grd"
        )
        gradient_grid = (
            Path(demgradient_grd).expanduser().resolve()
            if demgradient_grd
            else self.cache_dir / f"{cache_key}_dem_gradient.grd"
        )
        dem_grid.parent.mkdir(parents=True, exist_ok=True)
        gradient_grid.parent.mkdir(parents=True, exist_ok=True)

        if not dem_grid.exists():
            with temporary_path(dem_grid.parent, dem_grid.suffix or ".grd") as temporary_grd:
                gdal_translate(str(source), str(temporary_grd), fmt="GSBG")
                replace_dataset(temporary_grd, dem_grid)
        if not gradient_grid.exists():
            with temporary_path(gradient_grid.parent, gradient_grid.suffix or ".grd") as temporary_gradient:
                pygmt.grdgradient(grid=str(dem_grid), outgrid=str(temporary_gradient), azimuth=0)
                replace_dataset(temporary_gradient, gradient_grid)

        pygmt.makecpt(
            cmap=cpt,
            series=[bar_min, bar_max],
            background=True,
            reverse=True,
        )
        figure.grdimage(
            grid=str(dem_grid),
            region=region,
            projection=projection,
            cmap=True,
            shading=str(gradient_grid),
        )

        return self

    def draw_optic(
        self,
        optic_tif: str,
        region: List[float],
        projection: str,
    ) -> "PyGMTPlotter":
        """
        绘制光学（影像）底图（直接使用 GeoTIFF / RGB 文件，无需转换为 GRD）。
        Render an optical/raster basemap directly from a GeoTIFF/RGB file (no GRD conversion).

        参数 (Parameters)
        ----------
        optic_tif : str
            光学影像文件路径（GeoTIFF 或其他 GDAL 可识别的影像，支持多波段 RGB）。
            Path to the optical image (GeoTIFF or any GDAL-readable raster, including RGB).
        region : List[float]
            地图区域范围 [xmin, xmax, ymin, ymax]。
        projection : str
            投影字符串，例如 "M8i"。
        transparency : int, optional
            图层整体透明度（0=不透明，100=完全透明），默认 0。
            Layer transparency (0..100).

        返回 (Returns)
        -------
        self : PyGMTPlotter
            支持链式调用。
        """

        figure = self._require_figure()
        source = Path(optic_tif).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"optical GeoTIFF not found: {source}")

        try:
            with temporary_path(self.cache_dir, ".tif") as rgb_tif:
                gdal_translate(
                    str(source),
                    str(rgb_tif),
                    fmt="GTiff",
                    bands=[1, 2, 3],
                    creation_options=[
                        "COMPRESS=LZW",
                        "INTERLEAVE=PIXEL",
                        "TILED=YES",
                        "PHOTOMETRIC=RGB",
                    ],
                )
                figure.grdimage(
                    grid=str(rgb_tif),
                    region=region,
                    projection=projection,
                )

        except Exception as e:
            raise RuntimeError(f"使用 pygmt 绘制光学影像时出错: {e}") from e

        return self


    def draw_defo_grd(
        self,
        data_grd: str,
        cpt: str,
        region: List[float],
        projection: str,
        bar_min: float = -0.06,
        bar_max: float = 0.06,
        transparency: int = 25,
        cpt_reverse: bool = False,
    ) -> "PyGMTPlotter":
        """
        绘制形变量网格（外部 CPT + 指定数值范围 + NaN 透明 + 整层透明度）。
        Render deformation grid using external CPT; map to [bar_min, bar_max]; NaN transparent.

        参数 (Parameters)
        ----------
        data_grd : str
            形变量网格（GRD/GSBG/GeoTIFF 等 GMT 可识别）路径。
        cpt : str
            外部 CPT 文件路径（保留原配色，只做数值映射）。
        region : List[float]
            地图区域范围 [xmin, xmax, ymin, ymax]。
        projection : str
            投影字符串，例如 "M8i"。
        bar_min : float, optional
            颜色映射下界。
        bar_max : float, optional
            颜色映射上界。
        alpha : int, optional
            网格整层透明度（0=不透明，100=完全透明）。

        返回 (Returns)
        -------
        None
        """
        figure = self._require_figure()
        pygmt.makecpt(
            cmap=cpt,
            series=[bar_min, bar_max],
            background=True,
            reverse=cpt_reverse,
        )
        figure.grdimage(
            grid=data_grd,
            region=region,
            projection=projection,
            cmap=True,
            nan_transparent=True,
            transparency=transparency,
        )

        return self

    def draw_defo_scatter(
        self,
        data_grd: str,
        cpt: str,
        region: List[float],
        projection: str,
        bar_min: float = -0.06,
        bar_max: float = 0.06,
        style: str = "c0.08c",
        pen: str = "0.01p,white",
        transparency: int = 0,
        cpt_reverse: bool = False,
    ) -> "PyGMTPlotter":
        """
        基于栅格直接绘制散点形变图（输入为 GRD/GeoTIFF 等 GMT 可读栅格）。
        Render deformation as colored scatter points directly from a grid (GRD/GeoTIFF).

        参数 (Parameters)
        ----------
        data_grd : str
            单波段形变栅格（GRD/GeoTIFF/NetCDF 等 GMT 可读）。
        cpt : str
            外部 CPT 文件路径（用作颜色映射）。
        region : List[float]
            地图范围 [xmin, xmax, ymin, ymax]。
        projection : str
            投影字符串，例如 "M8i"。
        bar_min, bar_max : float
            颜色映射范围，与 draw_deformation 一致。
        style : str
            点样式（默认 "c0.08c"）。
        pen : str
            点边框画笔（默认 "0.25p,black"）。
        transparency : int
            图层透明度（0=不透明，100=完全透明）。

        返回 (Returns)
        -------
        self : PyGMTPlotter
            支持链式调用。
        """
        figure = self._require_figure()

        # 2) 颜色表（与 draw_deformation 保持一致）
        pygmt.makecpt(
            cmap=cpt,
            series=[bar_min, bar_max],
            background=True,
            reverse=cpt_reverse,
        )

        with temporary_path(self.cache_dir, ".xyz") as xyz_file:
            pygmt.grd2xyz(
                grid=data_grd,
                region=region,
                output_type="file",
                outfile=str(xyz_file),
                skiprows="2",
            )
            figure.plot(
                data=str(xyz_file),
                region=region,
                projection=projection,
                style=style,
                pen=pen,
                cmap=True,
                transparency=transparency,
            )

        return self


    def add_colorbar(
        self,
        label: str = "Deformation",
        unit: str = "m/yr",
        tick_interval: float | None = None,
    ) -> "PyGMTPlotter":
        """
        添加颜色条（底部居中 + 下移；白底 + 边框 + 内边距）。
        Add colorbar at bottom center with outward offset, white background & padding.

        参数 (Parameters)
        ----------
        None

        返回 (Returns)
        -------
        None
        """
        figure = self._require_figure()
        with pygmt.config(
            FONT_ANNOT_PRIMARY="20p",
            FONT_ANNOT_SECONDARY="24p, TeX Gyre Heros-Bold",
        ):
            frame = [f"xa{tick_interval:g}" if tick_interval else "xa", f"y+l{unit}"]
            figure.colorbar(
                cmap=True,
                position="JBC+o0c/4c+w12c/0.6c+h",
                frame=[frame[0] + f"+l{label}", frame[1]],
                box="F+gWHITE+p2p+c20p/20p",
            )

        return self

    def add_scale(
        self,
        region: List[float],
        projection: str,
        map_scale: str = "JTC+o0c/4c+w10k+f+u",
        box: str = "F+gWHITE+p2p+c20p/20p",
        scale_height: str = "20p",
        font_annot: str = "20p",
        font_label: str = "20p,TeX Gyre Heros-Bold,black",
    ) -> "PyGMTPlotter":
        """
        添加比例尺（上方居中 + 上移；白底 + 边框 + 内边距）。
        Add map scale at top center with outward offset.

        参数 (Parameters)
        ----------
        region : List[float]
            地图区域范围 [xmin, xmax, ymin, ymax]。
        projection : str
            投影字符串，例如 "M8i"。

        返回 (Returns)
        -------
        None
        """
        figure = self._require_figure()
        with pygmt.config(
            MAP_SCALE_HEIGHT=scale_height,
            FONT_ANNOT_PRIMARY=font_annot,
            FONT_LABEL=font_label,
        ):
            figure.basemap(
                region=region,
                projection=projection,
                map_scale=map_scale,
                box=box,
            )

        return self

    def add_rose(
        self,
        region: List[float],
        projection: str,
    ) -> "PyGMTPlotter":
        """
        添加玫瑰图/指北针（右侧居中 + 右移；白底 + 边框 + 内边距）。
        Add compass rose at right middle with outward offset.

        参数 (Parameters)
        ----------
        region : List[float]
            地图区域范围 [xmin, xmax, ymin, ymax]。
        projection : str
            投影字符串，例如 "M8i"。

        返回 (Returns)
        -------
        None
        """
        figure = self._require_figure()
        figure.basemap(
            region=region,
            projection=projection,
            rose="JMR+jCM+o10c/0c+w5c+l+f1",
            box="F+gwhite+p2p+c1.5c",
        )

        return self

    def draw_profile_tracks(
        self,
        tracks: Dict[str, Sequence[Sequence[float]]],
        line_pen: str = "2p,black",
        start_label_font: str = "20p,TeX Gyre Heros-Bold",
        end_label_font: str | None = None,
        start_justify: str = "BR",
        end_justify: str = "BL",
        end_suffix: str = "'",
    ) -> "PyGMTPlotter":
        """
        绘制多条剖面轨迹，并在每条轨迹的起点/终点加注记。
        Plot multiple profile tracks and label start/end points.

        参数 (Parameters)
        ----------
        tracks : Dict[str, Sequence[Sequence[float]]]
            键为注记名（如 "A"），值为二维序列/数组（每行 [lon, lat]，顺序：起点→终点）。
        line_pen : str, optional
            轨迹线型（GMT pen 字符串），默认 "2p,black"。
        start_label_font : str, optional
            起点注记字体（默认 "20p,TeX Gyre Heros-Bold"）。
        end_label_font : str or None, optional
            终点注记字体；为 None 时与起点相同。
        start_justify : str, optional
            起点注记对齐方式（默认 "BR"）。
        end_justify : str, optional
            终点注记对齐方式（默认 "BL"）。
        end_suffix : str, optional
            终点注记后缀（默认在字母后加撇号 "'").

        返回 (Returns)
        -------
        self : PyGMTPlotter
            支持链式调用。
        """
        if end_label_font is None:
            end_label_font = start_label_font
        figure = self._require_figure()

        for name, track in tracks.items():
            arr = np.asarray(track, dtype=float)
            # 轨迹线
            figure.plot(x=arr[:, 0], y=arr[:, 1], pen=line_pen)
            # 起点注记
            figure.text(
                x=[arr[0, 0]], y=[arr[0, 1]],
                text=name, font=start_label_font, justify=start_justify
            )
            # 终点注记
            figure.text(
                x=[arr[-1, 0]], y=[arr[-1, 1]],
                text=name + end_suffix, font=end_label_font, justify=end_justify
            )
        return self

    def add_marker(
        self,
        lon: float,
        lat: float,
        style: str = "a16p",
        pen: str = "2p,black",
        fill: str | None = None,
    ) -> "PyGMTPlotter":
        """
        绘制单个标记点（可多次调用叠加多个点）。
        Plot a single marker. Call repeatedly to add multiple points.

        参数 (Parameters)
        ----------
        lon : float
            经度（x）。
        lat : float
            纬度（y）。
        style : str, optional
            GMT 点样式（默认 "a16p" 星形，大小 16p）。
        pen : str, optional
            标记边框画笔（默认 "2p,black"）。
        fill : str or None, optional
            填充色（如 "red"）。None 表示不显式指定填充。

        返回 (Returns)
        -------
        self : PyGMTPlotter
            支持链式调用。
        """
        figure = self._require_figure()
        kwargs = dict(x=[float(lon)], y=[float(lat)], style=style, pen=pen)
        if fill is not None:
            kwargs["fill"] = fill
        figure.plot(**kwargs)
        return self

    def draw_math_basemap(
        self,
        profiles: 'pd.DataFrame | Sequence[pd.DataFrame]',
        title: str = "Profile_Curve",
        x_label: str = "Distance (m)",
        y_label: str = "Deformation (m)",
        padding: float = 0.1,
        projection: str = "X16c/10c",
    )-> "PyGMTPlotter":
        """
        初始化剖面坐标轴：根据单个或多个剖面数据自动计算绘图范围，并绘制坐标框架。
        - 横坐标为累计距离（列名 "distance"）
        - 纵坐标为剖面数值（列名 "z"）

        参数:
        profiles_or_single: 单个 DataFrame（含 "distance"/"z"）或 DataFrame 列表/元组
        title: 图形标题
        x_label: 横轴标题（默认 "Distance (m)"）
        y_label: 纵轴标题（默认 "Deformation (m)"）
        padding: 纵轴上下边距比例（默认 0.1）

        返回:
        self（支持链式调用）
        """
        profile_list = list(profiles) if isinstance(profiles, (list, tuple)) else [profiles]
        if not profile_list:
            raise ValueError("at least one profile is required")
        for profile in profile_list:
            missing = {"distance", "z"} - set(profile.columns)
            if missing:
                raise ValueError(f"profile is missing required columns: {', '.join(sorted(missing))}")

        x_values = np.concatenate([profile["distance"].to_numpy(dtype=float) for profile in profile_list])
        y_values = np.concatenate([profile["z"].to_numpy(dtype=float) for profile in profile_list])
        x_values = x_values[np.isfinite(x_values)]
        y_values = y_values[np.isfinite(y_values)]
        if x_values.size == 0 or y_values.size == 0:
            raise ValueError("profiles contain no finite distance/deformation values")

        x_min, x_max = float(x_values.min()), float(x_values.max())
        y_min, y_max = float(y_values.min()), float(y_values.max())

        if x_max == x_min:
            x_min -= 1.0; x_max += 1.0
        if y_max == y_min:
            y_min -= 1.0; y_max += 1.0

        y_gap = (y_max - y_min) * float(padding)
        y_min -= y_gap; y_max += y_gap

        figure = self._require_figure()
        figure.basemap(
            region=[x_min, x_max, y_min, y_max],
            projection=projection,
            frame=[f"xaf+l{x_label}", f"yaf+l{y_label}", f"+t{title}"]
        )
        return self


    def draw_line_2d(
        self,
        profile: 'pd.DataFrame',
        label: str,
        pen: str = "2p,blue",
    ) -> "PyGMTPlotter":

        """
        在当前剖面坐标轴上添加一条折线剖面。

        参数:
        profile: DataFrame，包含 "distance" 和 "z" 两列
        label: 图例标签
        pen: 线型（默认 "2p,blue"）

        返回:
        self（支持链式调用）
        """
        figure = self._require_figure()
        figure.plot(x=profile["distance"], y=profile["z"], pen=pen, label=label)
        return self


    def draw_scatter_2d(
        self,
        profile: 'pd.DataFrame',
        label: str,
        style: str = "c0.4c",
        fill: Optional[str] = None,
        pen: str = "0p",
        transparency: int = 60,
        alpha: Optional[int] = None,
    ) -> "PyGMTPlotter":
        """
        在当前剖面坐标轴上添加一条散点剖面。

        参数:
        profile: DataFrame，包含 "distance" 和 "z" 两列
        label: 图例标签
        style: 点样式（默认 "c0.4c" 圆点 0.4cm）
        fill: 填充色（如 "blue"）；None 表示不显式指定
        pen: 点边框画笔（默认 "0p"）
        transparency: 透明度 0~100（默认 60）
        alpha: 透明度别名；若给定，则覆盖 transparency

        返回:
        self（支持链式调用）
        """
        if alpha is not None:
            transparency = alpha
        kw = dict(x=profile["distance"], y=profile["z"],
                style=style, pen=pen, transparency=transparency, label=label)
        if fill is not None:
            kw["fill"] = fill
        self._require_figure().plot(**kw)
        return self

    def add_legend(
    self,
    position: str = "JTR+o0.5c/-1.2c",
    box: str = "+gwhite+p1.5p",
    ) -> "PyGMTPlotter":
        """
        添加剖面图例。

        参数:
        position: 图例位置与偏移，默认 "JTR+o0.2c/-1.2c"
        box: 图例面板样式（白底+边框），默认 "+gwhite+p1.2p"

        返回:
        self（支持链式调用）
        """
        self._require_figure().legend(position=position, box=box)
        return self


__all__ = ["DEFAULTS", "PyGMTPlotter"]
