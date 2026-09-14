# `pygmt_geo` Ownership Map / `pygmt_geo` 职责划分

This document is the migration contract for the mixed legacy module
`lib/pygmt_geo.py`. It records current callers and target ownership before any
function is moved. A regression test keeps the public-function inventory and
production imports synchronized with this table.

本文档是旧混合模块 `lib/pygmt_geo.py` 的迁移契约。在移动函数前，先记录当前
调用者和目标职责；回归测试会保证公共函数清单、生产代码导入与本表同步。

## Classification Rules / 分类规则

- `visualization-view`: temporary grid inspection, plot preparation, or sampling
  used only to compose a figure. These functions may move into
  `geodesy_visualization` without becoming scientific exporters.
- `adapter-gated`: combines source parsing, CRS/unit/nodata conversion, and a
  persistent GRD result. Keep it compatible in place until an equivalent
  Data-Adapter contract and numerical comparison exist.
- `analysis-candidate`: changes scientific raster values rather than adapting a
  format or drawing a figure. It must not move into Visualization or Adapter
  merely because the current file contains geospatial helpers.

- `visualization-view`：只为图件提供临时网格检查、绘图准备或采样，可迁入
  `geodesy_visualization`，但不能作为科学产品 exporter 对外承诺。
- `adapter-gated`：同时包含来源解析、坐标/单位/nodata 处理和持久 GRD 输出；
  Data-Adapter 具备等价契约并通过数值对照前，继续原位兼容。
- `analysis-candidate`：会改变科学栅格数值，不属于格式转接或绘图；不能因为
  当前位于地理辅助模块中就迁入 Visualization 或 Adapter。

## Function Inventory / 函数清单

The caller column lists direct production imports. `internal only` means that
the function is called only by another function in this module; `none` excludes
tests and documentation.

| Function | Current production caller | Classification | Next action and gate |
|---|---|---|---|
| `add_tifs` | none (repository-wide review 2026-09-14) | `analysis-candidate`, deprecated compatibility API | Keep the tested implementation temporarily in place with a `DeprecationWarning`. Do not create an unused Analysis package; remove only in a separately announced major compatibility phase. |
| `region_from_grd` | `geodesy_visualization.workflows.insar.deformation_map`, `geodesy_visualization.workflows.insar.deformation_profile` | `visualization-view` | Canonical implementation is in `geodesy_visualization.geo`; the legacy module re-exports the same function object. |
| `tif2grd` | internal only | `visualization-view` | Canonical implementation moved to `geodesy_visualization.grid_preparation`; Adapter 0.11 owns GeoTIFF adaptation, while Visualization owns only temporary GMT conversion. Legacy module re-exports the same function object. |
| `txt2grd` | internal only | `visualization-view` | Canonical implementation moved to `geodesy_visualization.grid_preparation`; Adapter 0.10 owns named point ingestion, while Visualization owns display scaling and temporary GMT gridding. |
| `defsour2grd` | internal only | `visualization-view` | Canonical implementation moved to `geodesy_visualization.grid_preparation`; Adapter 0.9 owns Defsour ingestion/CRS conversion, while Visualization owns display scaling and temporary GMT gridding. |
| `prepare_grid` | internal only | `visualization-view` | Canonical source-neutral dispatcher moved to `geodesy_visualization.grid_preparation`; legacy module re-exports it. |
| `prepare_dataset_grid` | `geodesy_visualization.workflows.insar.deformation_map`, `geodesy_visualization.workflows.insar.deformation_profile` | `visualization-view` | Canonical dataset dispatcher moved to `geodesy_visualization.grid_preparation`; both workflows import the package path and the legacy module re-exports it. |
| `generate_tracks` | `geodesy_visualization.workflows.insar.deformation_profile` | `visualization-view` | Canonical implementation is in `geodesy_visualization.geo`; keep it figure-oriented unless tracks become persisted scientific products. |
| `extract_profile` | `geodesy_visualization.workflows.insar.deformation_profile` | `visualization-view` | Canonical implementation is in `geodesy_visualization.geo`; keep it figure-oriented unless sampled values become a reusable/exported analysis result. |

The private `_validate_matching_grids` helper belongs with `add_tifs` and is not
part of the public compatibility surface.

私有函数 `_validate_matching_grids` 随 `add_tifs` 归属，不属于公共兼容接口。

## Completed Usage Decision / 已完成的调用决策

All source adaptation and renderer-specific grid preparation functions have
passed their Adapter gates and moved behind formal package APIs. A repository-
wide review found no production caller for the only remaining local
implementation, `add_tifs`, so it is now a deprecated compatibility API. It is
not copied into Visualization, Adapter, or a speculative Analysis package.

所有来源适配和渲染专用网格准备函数均已通过 Adapter 门槛并迁至正式 package
API。全仓盘点确认唯一剩余本地实现 `add_tifs` 没有生产调用方，因此现作为已弃用
兼容 API 暂时保留；不复制到 Visualization、Adapter 或没有真实调用方的 Analysis
空包中。
