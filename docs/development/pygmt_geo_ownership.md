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
| `add_tifs` | none | `analysis-candidate` | Keep in place. Move to Geodesy-Analysis only if a real workflow adopts it; otherwise deprecate after a separate usage review. |
| `region_from_grd` | `geodesy_visualization.workflows.insar.deformation_map`, `geodesy_visualization.workflows.insar.deformation_profile` | `visualization-view` | Canonical implementation is in `geodesy_visualization.geo`; the legacy module re-exports the same function object. |
| `tif2grd` | internal only | `adapter-gated` | Split persistent reprojection/scaling from temporary GMT conversion; compare CRS, registration, transform, values, bounds, and nodata. |
| `txt2grd` | internal only | `visualization-view` | Adapter 0.10 owns named headers, column roles, bounded parsing, metadata, point order, and optional CRS conversion. This compatibility function retains display scaling and temporary GMT gridding; legacy cfg metadata is explicitly unspecified rather than inferred. |
| `defsour2grd` | internal only | `visualization-view` | Adapter 0.9 owns bounded Defsour parsing, explicit column roles, point order, metadata, and CRS conversion. This compatibility function retains only display scaling and temporary GMT gridding. Existing cfg files receive an honest `unspecified by legacy visualization config` metadata record instead of inferred science; callers may already pass complete `DefsourMetadata` before the shared cfg contract is migrated. Formal persistent GRD export remains a separate Adapter phase. |
| `prepare_grid` | internal only | `visualization-view` | Later become a source-neutral view-preparation dispatcher; retain existing cfg aliases during transition. |
| `prepare_dataset_grid` | `geodesy_visualization.workflows.insar.deformation_map`, `geodesy_visualization.workflows.insar.deformation_profile` | `visualization-view` | Preserve as the workflow compatibility boundary while the three conversion branches are separated; package workflows use the qualified `lib.pygmt_geo` import. |
| `generate_tracks` | `geodesy_visualization.workflows.insar.deformation_profile` | `visualization-view` | Canonical implementation is in `geodesy_visualization.geo`; keep it figure-oriented unless tracks become persisted scientific products. |
| `extract_profile` | `geodesy_visualization.workflows.insar.deformation_profile` | `visualization-view` | Canonical implementation is in `geodesy_visualization.geo`; keep it figure-oriented unless sampled values become a reusable/exported analysis result. |

The private `_validate_matching_grids` helper belongs with `add_tifs` and is not
part of the public compatibility surface.

私有函数 `_validate_matching_grids` 随 `add_tifs` 归属，不属于公共兼容接口。

## Safe Migration Order / 安全迁移顺序

1. Move the remaining `prepare_grid` and `prepare_dataset_grid` view dispatchers
   behind a package API only after their adapter-gated branches are separated.
2. Leave `adapter-gated` functions active until Data-Adapter owns equivalent
   source and persistent-output contracts.
3. Split persistent conversion from temporary plotting grids and run shadow
   numerical comparisons before redirecting callers.
4. Decide `add_tifs` from an Analysis use case; do not include it in either move
   by convenience.

1. 只有在受 Adapter 前置条件约束的分支完成拆分后，才把剩余的
   `prepare_grid` 和 `prepare_dataset_grid` 视图调度器迁入包 API。
2. 在 Data-Adapter 具备等价来源与持久输出契约前，保持 `adapter-gated`
   函数原位生效。
3. 分开持久格式转换与绘图临时制网，完成影子数值对比后才切换调用者。
4. 根据真实 Analysis 用例决定 `add_tifs` 去留，不为迁移方便而随意归类。
