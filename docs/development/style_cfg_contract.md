# Shared Style CFG Contract / 统一样式 CFG 契约

This document defines which visual controls are shared across workflows and
which remain workflow-specific. Read it before adding, renaming, or copying any
font, axis, CPT, colorbar, spacing, or panel-layout key.

本文档规定哪些视觉控制可跨工作流共享，哪些必须保留为工作流专用。在新增、
重命名或复制字体、坐标轴、CPT、色标、间距或面板布局参数前必须阅读。

## 1. Precedence / 优先级

Use explicit workflow scope over the default block:
`profile_*` or `map_*` → `default_*` → workflow-owned fallback. Existing cfg
keys remain valid until a tested compatibility alias and migration note exist.

优先采用明确的工作流作用域：`profile_*` 或 `map_*` → `default_*` → 工作流
默认值。现有 cfg 键只有在具备经过测试的兼容别名和迁移说明后才能移除。

## 2. Canonical Font Blocks / 标准字体块

Every font block uses the same suffixes:

| CFG suffix | GMT setting | Meaning |
|---|---|---|
| `font_title` | `FONT_TITLE` | Figure or panel title font |
| `font_annot_primary` | `FONT_ANNOT_PRIMARY` | Primary coordinate/value annotations |
| `font_annot_secondary` | `FONT_ANNOT_SECONDARY` | Optional secondary time/coordinate annotations |
| `font_label` | `FONT_LABEL` | Axis and colorbar label font |

Prefixes currently used are `default`, `map`, and `profile`. The shared
`parse_font_style` function owns parsing. Font weight belongs in the complete GMT
font specification, for example `14p,Helvetica-Bold`; the responsive panel
workflow may additionally use `font_bold` because it constructs scaled font
specifications dynamically.

当前前缀为 `default`、`map` 和 `profile`，统一由 `parse_font_style` 解析。字体
粗细写在完整 GMT 字体规格中，例如 `14p,Helvetica-Bold`；响应式多面板工作流
因需动态生成缩放字体，可额外使用 `font_bold`。

## 3. Shared Semantics, Scoped Geometry / 共享语义与专用几何

- `add_colorbar`, colorbar label, and unit have shared semantics. Position,
  width, height, interval, and box remain workflow-specific until their
  different map/profile/panel geometries are modeled explicitly.<br>
  色标开关、标签和单位具有共享语义；位置、宽高、间隔和边框在不同几何模型
  明确建模前仍属工作流专用。
  These three metadata values are normalized by `parse_colorbar_metadata`;
  dataset-specific figures use a prefix such as `defo`, while a single-value
  figure uses the unprefixed keys.<br>这三项元数据由 `parse_colorbar_metadata`
  统一归一化；多数据类型图件使用 `defo` 等前缀，单值图件使用无前缀键。
- CPT path/name and reverse flag have shared semantics. Dataset prefixes such as
  `defo_` and `dem_` remain necessary because one figure can use both.<br>
  CPT 路径/名称和反转开关语义相同；同图可同时使用形变与 DEM，因此保留数据集前缀。
  File references ending in `.cpt` or containing a directory component resolve
  relative to the cfg file; plain values such as `vik` remain GMT built-in
  palette names. This distinction is owned by `resolve_cpt_reference`.<br>
  以 `.cpt` 结尾或含目录分量的文件引用相对 cfg 文件解析；`vik` 等纯名称仍表示
  GMT 内置色标。该判定统一由 `resolve_cpt_reference` 负责。
- Coordinate visibility, annotation intervals, and grid visibility are shared
  concepts, but Cartesian time axes and geographic map axes use different GMT
  frame syntax and must not share raw frame strings.<br>
  坐标显示、注记间隔和网格显示属于共享概念，但笛卡尔时间轴与地理坐标轴采用
  不同 GMT frame 语法，不能共用原始 frame 字符串。
- `subplot_rows`, `subplot_columns`, panel margins, responsive font scale, and
  canvas margin apply only to multi-panel workflows.<br>
  子图行列数、面板间距、响应式字体比例和画布留白仅用于多面板工作流。

## 4. PyGMT Figure Operation Naming / PyGMT Figure 操作命名

The study-area workflow uses ordered INI sections with the stable form
`figure.<pygmt_method>.<optional_scientific_semantics>.<optional_instance_id>`.
The method component follows a public PyGMT Figure method whenever the mapping
is direct. Scientific suffixes distinguish repeated uses of a general method,
for example `figure.plot.footprint.reference` and
`figure.plot.footprint.saocom`.

研究区 workflow 使用有序 INI section，统一格式为
`figure.<pygmt方法>.<可选科学语义>.<可选实例名>`。能够直接映射时，方法部分
沿用 PyGMT Figure 公共方法；通用方法的重复科学用途通过后缀区分，例如
`figure.plot.footprint.reference` 与 `figure.plot.footprint.saocom`。

Rules / 规则：

- Use lowercase `snake_case` identifiers.<br>标识符统一使用小写 `snake_case`。
- Use full PyGMT parameter names (`projection`, `transparency`, `pen`), never
  GMT one-letter aliases (`J`, `t`, `W`).<br>使用完整 PyGMT 参数名，不使用 GMT 单字母别名。
- Operation section order is rendering order.<br>操作 section 顺序就是绘图顺序。
- Use `footprint`, not `coverage`, for product spatial extent.<br>产品空间范围统一使用 `footprint`，不使用 `coverage`。
- Keep workflow-only keys limited to `enabled`, `source`, `layout`,
  `processing_root`, `kinematic_field`, `highlight`, and `regions` unless this
  contract is updated with tests.<br>工作流自定义 key 限定为上述集合；新增前必须更新本契约和测试。
- A `source` value is the full identifier of an earlier resource-producing
  operation, such as `figure.grdimage.dem`.<br>`source` 使用资源操作的完整标识符。

PyGMT version adapters may translate these stable names to an older installed
API. Version-specific raw syntax belongs in the adapter, not in the shared CFG
contract.

PyGMT 版本适配器可以将稳定配置名称转换为服务器旧版接口；版本相关原始语法只
属于适配器，不进入共享 CFG 契约。

## 5. Current Inventory / 当前盘点

| Workflow | Shared font blocks | Specialized controls |
|---|---|---|
| Deformation map | `default`, `map` | target regions, map scale, rose, DEM/deformation CPT |
| Deformation profile | `default`, `map`, `profile` | tracks, markers, profile legend and padding |
| Auxiliary time series | `default` | primary/secondary time frames and three Y axes |
| Spatial time-series map | `default` | responsive panel fonts, outer/all/none coordinates, subplot layout, colorbar geometry |
| Study area | Figure-operation sections | footprint/fault styles, sidecar layout, insets, meca, scalebar, directional rose |

## 6. Migration Rule / 迁移规则

Add a shared parser only for equivalent semantics. Keep workflow-specific
defaults at the workflow call site so adopting a shared parser never changes an
existing figure. Each migration must load real cfg files, compare normalized
values, and then use targeted rendering only when drawing behavior changes.

只有语义等价的参数才能加入共享解析器。工作流默认值继续保留在调用位置，确保
采用公共解析器不会改变既有图件。每次迁移必须加载真实 cfg、比较归一化结果；
只有绘制行为发生变化时才执行针对性的图件验收。

## 7. Axis and Layout Decision / 坐标与布局结论

The spatial time-series map keeps `coordinate_mode=none|outer|all` plus
longitude/latitude intervals and a geographic format. The auxiliary time-series
figure keeps its primary/secondary Cartesian GMT frame strings. They share the
concept of visibility but not a parser or raw cfg alias. Subplot rows, columns,
panel margins, canvas margin, and responsive font sizing remain exclusive to
the spatial multi-panel workflow.

时空地图继续使用 `coordinate_mode=none|outer|all`、经纬度间隔和地理格式；辅助
时序图继续使用主/次笛卡尔 GMT frame 字符串。二者只共享“是否显示”的概念，
不共享解析器或底层 cfg 别名。子图行列、面板间距、画布留白和响应式字号继续仅
属于时空多面板工作流。
