"""
geodesy_visualization.figure_ops.executor
=========================================

功能概述:
    将已校验 FigurePlan 依次应用到同一个 PyGMT Figure，并通过共享上下文
    传递区域、投影、CPT、图例和输出状态，同时保留链式 ``apply`` 接口。

函数说明:
    ``RenderContext``:
        保存当前 Figure、配置来源、共享绘图资源和运行期消息。
    ``FigureExecutor``:
        延迟创建 Figure，按注册 handler 执行有序操作并返回自身以支持链式调用。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cartography_operations import CARTOGRAPHY_HANDLERS
from .direct_operations import DIRECT_HANDLERS
from .model import FigureOperation, FigurePlan


@dataclass
class RenderContext:
    """Share one Figure and prepared resources across ordered operations."""

    figure: object
    config_path: Path
    project: Mapping[str, str]
    figure_options: Mapping[str, str]
    resources: dict[str, dict[str, object]] = field(default_factory=dict)
    legend_items: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    region: tuple[float, float, float, float] | None = None
    projection: str | None = None
    active_cpt_source: str | None = None


Handler = Callable[[RenderContext, FigureOperation], None]


class FigureExecutor:
    """Execute a FigurePlan through small registered handlers and return self."""

    def __init__(
        self,
        plan: FigurePlan,
        figure_factory: Callable[[], object] | None = None,
        handlers: Mapping[str, Handler] | None = None,
    ):
        """Initialize a lazy executor without importing or creating PyGMT yet."""
        self.plan = plan
        self._figure_factory = figure_factory or self._create_pygmt_figure
        self._handlers: dict[str, Handler] = dict(DIRECT_HANDLERS)
        self._handlers.update(CARTOGRAPHY_HANDLERS)
        if handlers:
            self._handlers.update(handlers)
        self._context: RenderContext | None = None

    @staticmethod
    def _create_pygmt_figure() -> object:
        """Import PyGMT lazily and return a new Figure instance."""
        import pygmt

        return pygmt.Figure()

    def _ensure_context(self) -> RenderContext:
        """Create the Figure and shared context on first rendering use."""
        if self._context is None:
            self._context = RenderContext(
                figure=self._figure_factory(),
                config_path=self.plan.config_path,
                project=self.plan.project,
                figure_options=self.plan.figure,
            )
        return self._context

    @property
    def context(self) -> RenderContext:
        """Return the active context, creating it lazily if requested."""
        return self._ensure_context()

    def apply(self, operation: FigureOperation) -> "FigureExecutor":
        """Apply one operation and return this executor for fluent composition."""
        enabled = operation.options.get("enabled", True)
        if enabled is False:
            return self
        source = operation.options.get("source")
        if source is not None:
            resources = {} if self._context is None else self._context.resources
            if source not in resources:
                raise ValueError(
                    f"[{operation.section}] source {source!r} has not been prepared "
                    "by an earlier operation"
                )
        handler = self._handlers.get(operation.handler)
        if handler is None:
            raise ValueError(
                f"[{operation.section}] has no registered handler {operation.handler!r}"
            )
        handler(self._ensure_context(), operation)
        return self

    def execute(self) -> "FigureExecutor":
        """Validate terminal output placement and execute every operation in order."""
        enabled_indices = [
            index for index, operation in enumerate(self.plan.operations)
            if operation.options.get("enabled", True) is not False
        ]
        save_indices = [
            index for index, operation in enumerate(self.plan.operations)
            if operation.handler == "savefig" and operation.options.get("enabled", True) is not False
        ]
        if save_indices and save_indices[-1] != enabled_indices[-1]:
            section = self.plan.operations[save_indices[-1]].section
            raise ValueError(f"[{section}] must be the last enabled figure operation")
        if len(save_indices) > 1:
            raise ValueError("a figure plan may contain only one enabled figure.savefig operation")
        for operation in self.plan.operations:
            self.apply(operation)
        return self


__all__ = ["FigureExecutor", "RenderContext"]
