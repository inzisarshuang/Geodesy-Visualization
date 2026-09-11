# Python Rules

## Module Responsibilities / 模块职责

- Put configuration syntax, path handling, temporary files, external commands, and generic validation in `geodesy_visualization/io.py`; `lib/pygmt_io.py` is compatibility-only.<br>配置语法、路径处理、临时文件、外部命令和通用校验放在 `geodesy_visualization/io.py`；`lib/pygmt_io.py` 只用于兼容。
- Put figure-oriented grid inspection, track generation, and profile sampling in `geodesy_visualization/geo.py`. Keep only the explicitly mapped transitional conversions and raster arithmetic in `lib/pygmt_geo.py`; package workflows import that boundary as `lib.pygmt_geo` without modifying `sys.path`.<br>面向图件的网格检查、轨迹生成和剖面采样放在 `geodesy_visualization/geo.py`；`lib/pygmt_geo.py` 仅保留职责表明确列出的过渡转换与栅格运算，正式工作流通过 `lib.pygmt_geo` 导入且不得修改 `sys.path`。
- Put selection and bounded iteration over canonical products in `geodesy_visualization/data/`, using the installed Adapter public API without changing units, references, masks, or nodata.<br>标准产品的选择与受控内存迭代放在 `geodesy_visualization/data/`，仅使用已安装 Adapter 的公共 API，不改变单位、参考、掩膜或 nodata。
- Put PyGMT figure state and reusable drawing primitives in `geodesy_visualization/backends/pygmt.py`; `lib/pygmt_visual.py` is compatibility-only.<br>PyGMT 绘图状态和公共绘图原语放在 `geodesy_visualization/backends/pygmt.py`；`lib/pygmt_visual.py` 只用于兼容。
- Put canonical cfg normalization and orchestration in `geodesy_visualization/workflows/`. During migration, keep `plot_*` entry scripts as thin compatibility wrappers and retain their cfg/data paths.<br>正式的 cfg 参数归一化和流程编排放在 `geodesy_visualization/workflows/`；迁移期间保留 `plot_*` 薄兼容入口及其 cfg/data 路径。
- Add domain, mask, and export modules only when they own independent reusable behavior.<br>只有存在独立且可复用的职责时，才新增领域计算、掩膜或产品导出模块。

## Interfaces

- Every new production Python file must begin with the following structure. Update `函数说明` whenever a public top-level function or class is added, removed, or renamed.<br>每个新增生产 Python 文件必须以以下结构开头；新增、删除或重命名公共顶层函数和类时，必须同步更新 `函数说明`。

```python
"""
module_name
===========

功能概述:
    用一到数行说明本模块负责的数据、处理范围和职责边界。

函数说明:
    ``public_function``:
        说明该函数的主要输入、处理行为和输出目的。
    ``PublicClass``:
        说明该类管理的状态或提供的公共能力。
"""
```

- `功能概述` must define what the module owns and what remains outside its boundary. `函数说明` must list every public top-level function and class, grouped by responsibility when useful.<br>`功能概述` 必须说明模块负责和不负责的边界；`函数说明` 必须列出所有公共顶层函数和类，可按职责分组。
- Private helpers may be omitted from the module list when self-explanatory, but still require function-level docstrings.<br>私有辅助函数可按复杂度决定是否列入模块清单，但仍必须具有函数级 docstring。
- 每个生产函数和方法（包括私有辅助函数与入口编排函数）都在函数开头用简洁 docstring 说明作用；公共科学接口按需要补充中英文参数、返回值和单位。
- 运行时输入错误使用 `ValueError`、`FileNotFoundError` 或 `RuntimeError`，不用 `assert`。
- 外部命令必须使用参数列表和 `subprocess.run(..., check=True)`，不拼接 shell 字符串。
- 路径使用 `pathlib.Path`；公开接口可接收字符串以方便 cfg 调用。

## Resource Control

- GeoTIFF 使用 `block_windows` 读取；文本点云使用 `chunksize`。
- GMT 能读取文件时，不先转换为完整 Pandas DataFrame。
- 所有数据集句柄使用上下文管理器关闭。
- 临时文件使用唯一名称并保证异常时清理；最终输出成功后再原子替换。

## Checks

```bash
python -m compileall -q geodesy_visualization lib plot_defo_*
python -m unittest discover -s tests -v
```
