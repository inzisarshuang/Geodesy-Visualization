# PyGMT-Plotter

PyGMT-Plotter is a configuration-driven toolkit for deformation maps, DEM or optical basemaps, and deformation profiles. It combines strict cfg interfaces, bounded-memory geospatial processing, and reusable PyGMT drawing primitives.

PyGMT-Plotter 是一个配置驱动的科研绘图库，用于绘制形变地图、DEM 或光学底图以及形变剖面。仓库整合了严格的 cfg 接口、低内存地理数据处理和可复用的 PyGMT 绘图功能。

The repository is being reorganized toward the engine-neutral name
`Geodesy-Visualization`. The first compatibility phase introduces the
`geodesy_visualization` Python package without changing repository, workflow,
or cfg paths.

仓库正在向不绑定绘图引擎的 `Geodesy-Visualization` 重组。首个兼容阶段引入
`geodesy_visualization` Python 包，但不改变仓库路径、工作流入口或 cfg 路径。

## 1. Project Structure / 项目结构

```text
PyGMT-Plotter/
├── AGENTS.md                         # coding baseline / 代码基线
├── CONTRIBUTING.md                   # contribution workflow / 开发流程
├── cpt/                              # shared color palettes / 公共色带
├── docs/development/                 # engineering rules / 工程规则
├── geodesy_visualization/            # new public Python package / 新公共 Python 包
│   ├── io.py                         # canonical config and file I/O / 正式配置与文件 I/O
│   ├── geo.py                        # view geometry and sampling / 视图几何与采样
│   ├── workflows/insar/
│   │   └── timeseries_aux.py         # canonical auxiliary-series workflow / 正式辅助时序流程
│   └── backends/
│       └── pygmt.py                  # canonical PyGMT backend / 正式 PyGMT 后端
├── lib/
│   ├── pygmt_io.py                   # compatibility import / 兼容导入
│   ├── pygmt_geo.py                  # spatial processing / 空间处理
│   └── pygmt_visual.py               # compatibility import / 兼容导入
├── plot_defo_dem_optic/              # deformation map workflow / 形变地图流程
├── plot_defo_profile/                # map and profile workflow / 地图与剖面流程
├── plot_defo_timeseries_map/          # spatial time-series panels / 空间时序子图
├── plot_defo_timeseries_aux/          # deformation and auxiliary series / 形变与辅助时序
├── tests/                            # regression tests / 回归测试
└── requirements.txt                  # Python dependencies / Python 依赖
```

The tracked example datasets allow both workflows to run after cloning. Generated GRD files and figures are ignored by Git.

仓库已跟踪两套示例数据，克隆后即可运行两个流程；生成的 GRD 和图片由 Git 忽略。

### 1.1 Documentation / 文档入口

- Project usage: this `README.md`.<br>项目使用说明：当前 `README.md`。
- Development entry points: [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md).<br>开发入口：上述两个文件。
- Engineering baseline: [docs/development/README.md](docs/development/README.md).<br>工程规范入口：上述链接。
- Scientific conventions: [docs/development/scientific_conventions.md](docs/development/scientific_conventions.md).<br>科学数据约定：上述链接。
- Workflow parameters: [plot_defo_dem_optic.cfg](plot_defo_dem_optic/plot_defo_dem_optic.cfg) and [plot_defo_dem_profile.cfg](plot_defo_profile/plot_defo_dem_profile.cfg).<br>流程参数说明：上述两个示例 cfg。

## 2. Workflow Overview / 流程总览

### 2.1 Deformation Map / 形变地图

`plot_defo_dem_optic` converts TIF, lon/lat TXT, or Defsour deformation data to GMT GRD and draws it over a DEM, optical image, or blank basemap.

`plot_defo_dem_optic` 将 TIF、经纬度 TXT 或 Defsour 形变数据转换为 GMT GRD，并叠加到 DEM、光学影像或空白底图。

1. Read and validate the cfg file, including paths, units, color limits, transparency, and styles.<br>读取并校验 cfg 中的路径、单位、色标范围、透明度和样式。
2. Convert the enabled SBAS and PSI datasets to GMT GRD using windowed raster or chunked table reads.<br>通过栅格窗口或文本分块读取，将启用的 SBAS 和 PSI 数据转换为 GMT GRD。
3. Draw the selected basemap, deformation grid or scatter points, target regions, colorbar, scale, and north arrow.<br>绘制选定底图、形变网格或散点、目标区域、色标、比例尺和指北针。
4. Save each completed figure through a temporary sibling file and atomic replacement.<br>通过同目录临时文件和原子替换安全保存每张完整图片。

### 2.2 Deformation Profiles / 形变剖面

`plot_defo_profile` compares two deformation datasets on separate maps and along common named profile tracks.

`plot_defo_profile` 在独立地图和公共命名剖线上对比两套形变数据。

1. Normalize both dataset configurations and prepare their GMT grids.<br>归一化两套数据配置并准备 GMT 网格。
2. Generate evenly spaced named tracks from configured start and end coordinates.<br>根据配置的起止坐标生成等间距命名轨迹。
3. Sample both grids along every track and calculate cumulative WGS84 distance.<br>沿每条轨迹采样两套网格并计算 WGS84 累计距离。
4. Export one map per dataset and optional line or scatter comparison figures per track.<br>为每套数据输出地图，并按剖线选择输出折线或散点对比图。

### 2.3 Library Responsibilities / 函数库职责

`plot_defo_timeseries_map` provides cfg-driven multi-epoch geographic panels. `plot_defo_timeseries_aux` provides a shared-date-axis deformation, fit, precipitation, and temperature figure. Each workflow keeps its example input under its own `data/` directory and writes figures under `result/`.

`plot_defo_timeseries_map` 提供 cfg 驱动的多期地理子图；`plot_defo_timeseries_aux` 提供共享日期轴的形变、拟合、降水和温度组合图。每个流程的示例输入位于自身 `data/` 目录，结果写入 `result/`。

- `geodesy_visualization/io.py`: canonical strict cfg parsing, path resolution, parameter validation, temporary files, atomic replacement, and GDAL command wrappers.<br>正式负责严格 cfg 解析、路径处理、参数校验、临时文件、原子替换和 GDAL 命令封装。
- `geodesy_visualization/geo.py`: canonical figure-oriented grid-region inspection, profile-track geometry, and profile sampling.<br>正式负责面向图件的网格范围读取、剖面轨迹几何和剖面采样。
- `lib/pygmt_io.py`: compatibility re-export for existing imports; it contains no separate implementation.<br>为现有导入路径提供兼容重导出，不包含独立实现。
- `lib/pygmt_geo.py`: transitional raster conversion and view-preparation module; its function-level migration boundary is recorded in `docs/development/pygmt_geo_ownership.md`.<br>过渡期的栅格转换与视图准备模块；函数级迁移边界记录在 `docs/development/pygmt_geo_ownership.md`。
- `geodesy_visualization/backends/pygmt.py`: canonical PyGMT figure state, map layers, profile plots, annotations, legends, and final figure output.<br>正式负责 PyGMT 图形状态、地图图层、剖面图、注记、图例和最终图片输出。
- `geodesy_visualization/workflows/insar/timeseries_aux.py`: canonical cfg-driven deformation and auxiliary-series workflow.<br>正式的 cfg 驱动形变与辅助时序工作流。
- `lib/pygmt_visual.py`: compatibility re-export for existing imports; it contains no separate implementation.<br>为现有绘图器导入路径提供兼容重导出，不包含独立实现。
- `plot_*/*.py`: workflow implementations not yet migrated, or compatibility CLIs for migrated workflows.<br>尚未迁移的工作流实现，或已迁移工作流的兼容命令行入口。

## 3. Dependencies / 依赖环境

### 3.1 Core Requirements / 核心依赖

- Python 3.10 or newer; the recommended Conda environment name is `envPlot`.<br>Python 3.10 或更高版本，推荐 Conda 环境名为 `envPlot`。
- GMT and PyGMT for map and grid operations.<br>GMT 与 PyGMT，用于地图和网格操作。
- GDAL with `gdal_translate` available on `PATH`.<br>GDAL，并确保 `gdal_translate` 位于 `PATH`。
- Rasterio, PyProj, NumPy, and Pandas for geospatial and tabular processing.<br>Rasterio、PyProj、NumPy 和 Pandas，用于地理空间及表格处理。

### 3.2 Installation / 安装方法

```bash
# Create and activate the plotting environment.
# 创建并激活绘图环境。
conda create -n envPlot -c conda-forge \
  python=3.10 pygmt=0.10 gmt gdal rasterio pyproj numpy pandas -y
conda activate envPlot
```

PyGMT `0.10.0` is the verified server version. Later compatible versions may be used after running the repository tests and both example workflows.

服务器已验证 PyGMT `0.10.0`；使用后续兼容版本时，应重新运行仓库测试和两个示例流程。

### 3.3 Environment Check / 环境自检

```bash
python -c "import pygmt, rasterio, pyproj, numpy, pandas; print('envPlot OK')"
gmt --version
gdal_translate --version
```

## 4. Quick Start / 快速开始

Paths inside a cfg file are resolved relative to that cfg file rather than the shell's current directory. Bare output filenames are placed under the configured `output_dir`.

cfg 中的相对路径以 cfg 文件目录为基准，而不是终端当前目录；仅包含文件名的输出会写入配置的 `output_dir`。

### 4.1 Deformation Map / 形变地图

```bash
conda run -n envPlot python plot_defo_dem_optic/plot_defo_dem_optic.py \
  --config plot_defo_dem_optic/plot_defo_dem_optic.cfg
```

### 4.2 Deformation Profiles / 形变剖面

```bash
conda run -n envPlot python plot_defo_profile/plot_defo_dem_profile.py \
  --config plot_defo_profile/plot_defo_dem_profile.cfg
```

### 4.3 Spatial Time-Series Panels / 空间时序子图

```bash
conda run -n envPlot python plot_defo_timeseries_map/plot_defo_timeseries_map.py \
  --config plot_defo_timeseries_map/plot_defo_timeseries_map.cfg
```

### 4.4 Deformation And Auxiliary Series / 形变与辅助时序

```bash
conda run -n envPlot python plot_defo_timeseries_aux/plot_defo_timeseries_aux.py \
  --config plot_defo_timeseries_aux/plot_defo_timeseries_aux.cfg
```

Each example cfg documents every supported key, unit, valid choice, and output option. Unknown, duplicate, malformed, or inconsistent settings fail before plotting. Hex colors such as `#1f77b4` are accepted directly.

每个示例 cfg 均说明支持的配置键、单位、可选值和输出选项。未知、重复、格式错误或相互矛盾的参数会在绘图前报错；可直接使用 `#1f77b4` 等十六进制颜色。

## 5. Data And Output Behavior / 数据与输出行为

- Example text inputs use explicit, unit-bearing headers. Geographic point
  tables start with `lon lat`; auxiliary tables start with `date_yyyymmdd`;
  spatial time-series columns use
  `epoch_NNN_deformation_YYYYMMDD_mm` and are checked against
  `epoch_index date_yyyymmdd` in the dates table.<br>示例文本输入均使用包含单位的明确表头。地理点表以 `lon lat` 开头，辅助时序表以 `date_yyyymmdd` 开头；空间时序列使用 `epoch_NNN_deformation_YYYYMMDD_mm`，并与日期表中的 `epoch_index date_yyyymmdd` 逐列核对。
- The repository versions a spatially representative time-series example;
  full-resolution local tables remain ignored because GitHub rejects files
  larger than 100 MB.<br>仓库保存具有空间代表性的时序示例；完整分辨率本地表保持忽略，因为 GitHub 拒绝超过 100 MB 的单个文件。
- TIF conversion reads raster blocks instead of loading a complete scene into memory.<br>TIF 转换按栅格块读取，不将整景数据一次性载入内存。
- TXT point tables are scaled and passed to GMT in configurable chunks through `*_chunk_rows`.<br>TXT 点表按 `*_chunk_rows` 配置分块缩放并交给 GMT。
- Headerless Defsour tables use zero-based columns `X=0`, `Y=1`, `elevation=2`, and `deformation=3`; configure `*_input_crs` and use `*_input_type=defsour`. Coordinates are transformed to WGS84 before gridding.<br>无表头 Defsour 表使用零基列号 `X=0`、`Y=1`、`高程=2`、`形变=3`；设置 `*_input_crs` 并选择 `*_input_type=defsour`，制网前自动转换到 WGS84。
- Projected GeoTIFF inputs are reprojected to WGS84 by default; set `*_target_crs` explicitly only when a non-geographic plotting workflow requires it.<br>投影 GeoTIFF 默认重投影到 WGS84；只有非地理绘图流程才应显式修改 `*_target_crs`。
- Pixel-wise raster arithmetic requires matching dimensions, transforms, and coordinate reference systems.<br>逐像元栅格运算要求尺寸、仿射变换和坐标参考系一致。
- Zero and nodata remain distinct; conversion occurs only through explicit cfg options such as `*_nan_to_zero`.<br>零值与 nodata 始终区分，仅通过 `*_nan_to_zero` 等显式配置执行转换。
- Grid scatter plots use temporary XYZ files instead of materializing a full Pandas DataFrame.<br>网格散点通过临时 XYZ 文件交给 GMT，不构造完整 Pandas DataFrame。
- Temporary products use unique names, and final grids or figures replace destinations only after success.<br>临时产品使用唯一名称，最终网格或图片仅在成功后替换目标文件。
- Display limits such as `defo_bar_min` and `defo_bar_max` control color mapping without altering source values.<br>`defo_bar_min` 和 `defo_bar_max` 等显示范围只控制颜色映射，不修改源数据。

## 6. Verification And Development / 验证与开发

### 6.1 Automated Checks / 自动检查

```bash
python -m compileall -q geodesy_visualization lib plot_defo_*
python -m unittest discover -s tests -v
git diff --check
```

Changes to shared plotting, geospatial, or I/O behavior must also run both example workflows and inspect at least one generated map and profile figure.

修改公共绘图、地理处理或 I/O 行为后，还必须运行两个示例流程，并检查至少一张地图和一张剖面图。

### 6.2 Development Rules / 开发规则

- Read [AGENTS.md](AGENTS.md) before adding or changing code.<br>新增或修改代码前阅读上述编码基线。
- Follow [engineering_rules.md](docs/development/engineering_rules.md) for module ownership, memory, output, and cache behavior.<br>模块职责、内存、输出和缓存行为遵循上述工程规则。
- Follow [python_rules.md](docs/development/python_rules.md) for module documentation and Python interfaces.<br>模块说明和 Python 接口遵循上述 Python 规则。
- Do not add region-specific benchmark files; measure performance with representative task data when needed.<br>不新增与特定研究区绑定的 benchmark；需要时使用当前任务代表性数据测量性能。

## 7. Author / 作者

- Yilun Tan · SIGM@3D Laboratory, School of Geosciences and Info-Physics, Central South University.<br>谭逸伦 · 中南大学地球科学与信息物理学院 SIGM@3D 实验室。
- Email: `csuyiluntan@gmail.com`, `yiluntancsu@qq.com`.<br>邮箱：同上。

## 8. Security / 安全说明

Do not commit credentials, private absolute paths, or confidential project data in cfg files, documentation, or examples. Rotate credentials and clean repository history immediately if a secret is exposed.

不得在 cfg、文档或示例中提交凭据、私有绝对路径或保密工程数据；若发生泄露，应立即更换凭据并清理仓库历史。

## 9. License Notice / 许可说明

No repository-wide license file is currently provided. Third-party dependencies and example datasets remain subject to their respective terms; obtain permission before redistributing repository code or data.

当前仓库尚未提供统一许可证文件。第三方依赖和示例数据遵循各自条款；重新分发仓库代码或数据前应取得许可。
