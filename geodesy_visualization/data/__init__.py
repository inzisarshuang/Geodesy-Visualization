"""
geodesy_visualization.data
==========================

功能概述:
    提供可视化工作流消费已校验科学产品时使用的数据选择和受控内存读取接口；
    不解析上游软件私有格式，也不执行科学单位或参考变换。

函数说明:
    ``CanonicalGridSelection``:
        保存标准规则栅格的时期选择、坐标轴和显式科学元数据。
    ``GridEpochBlock``:
        保存一个时期内连续行块的原始形变值与有效掩膜。
    ``load_canonical_grid_selection``:
        通过 Adapter 公共 API 校验标准 HDF5 并建立轻量选择对象。
    ``iter_canonical_grid_blocks``:
        按时期和连续行块读取选择范围，不物化完整数据立方体。
"""

from .canonical_grid import (
    CanonicalGridSelection,
    GridEpochBlock,
    iter_canonical_grid_blocks,
    load_canonical_grid_selection,
)


__all__ = [
    "CanonicalGridSelection",
    "GridEpochBlock",
    "iter_canonical_grid_blocks",
    "load_canonical_grid_selection",
]
