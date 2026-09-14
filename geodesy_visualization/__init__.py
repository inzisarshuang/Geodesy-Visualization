"""
geodesy_visualization
=====================

功能概述:
    提供与具体工作流解耦的大地测量可视化公共接口；当前阶段公开配置、路径、
    临时文件、原子输出、Matplotlib/PyGMT 后端和 Adapter 驱动的临时网格准备，
    不负责科学反演或持久来源数据转换。

函数说明:
    当前包级接口由 ``geodesy_visualization.io`` 模块提供，不在包根重复定义函数。
"""

__version__ = "0.4.0"
