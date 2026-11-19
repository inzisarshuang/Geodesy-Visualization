"""
geodesy_visualization.figure_ops.executor
=========================================

功能概述:
    将已校验 FigurePlan 的整图与 Panel 图层应用到同一个 PyGMT Figure，
    通过受控上下文传递区域、投影、CPT、图例和输出状态。

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
from .model import FigureOperation, FigurePlan, LayerOperation, PanelPlan


@dataclass
class RenderContext:
    """Share one Figure and prepared resources across ordered operations."""

    figure: object
    config_path: Path
    project: Mapping[str, str]
    figure_options: Mapping[str, object]
    resources: dict[str, dict[str, object]] = field(default_factory=dict)
    figure_resources: dict[str, dict[str, object]] = field(default_factory=dict)
    legend_items: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    region: tuple[float, float, float, float] | None = None
    projection: str | None = None
    active_cpt_source: str | None = None
    panel_identifier: int | str | None = None


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

    @staticmethod
    def _enabled_layers(layers: tuple[LayerOperation, ...]) -> tuple[LayerOperation, ...]:
        """Return enabled layers while preserving their configured order."""
        return tuple(
            layer
            for layer in layers
            if layer.options.get("enabled", True) is not False
        )

    def _all_layers(self) -> tuple[LayerOperation, ...]:
        """Flatten the plan in execution order for terminal-layer validation."""
        panel_layers = tuple(
            layer for panel in self.plan.panels for layer in panel.layers
        )
        return self.plan.operations + panel_layers + self.plan.figure_layers

    def _execute_panel(self, panel: PanelPlan) -> None:
        """Execute one panel with isolated resources and panel-local map state."""
        context = self._ensure_context()
        previous_region = context.region
        previous_projection = context.projection
        previous_resources = context.resources
        previous_cpt = context.active_cpt_source
        previous_identifier = context.panel_identifier
        context.region = panel.region
        context.projection = panel.projection
        context.resources = dict(context.figure_resources)
        context.active_cpt_source = None
        context.panel_identifier = panel.identifier
        try:
            if self.plan.figure.get("layout") == "cartesian":
                for layer in panel.layers:
                    self.apply(layer)
            else:
                set_panel = getattr(context.figure, "set_panel", None)
                if set_panel is None:
                    raise TypeError(
                        "configured PanelPlan requires Figure.set_panel support"
                    )
                with set_panel(panel=panel.identifier):
                    for layer in panel.layers:
                        self.apply(layer)
        finally:
            context.region = previous_region
            context.projection = previous_projection
            context.resources = previous_resources
            context.active_cpt_source = previous_cpt
            context.panel_identifier = previous_identifier

    def _execute_panels(self) -> None:
        """Execute all panels inside one optional owning subplot scope."""
        if not self.plan.panels:
            return
        subplot_options = self.plan.figure.get("subplot")
        if subplot_options is None:
            for panel in self.plan.panels:
                self._execute_panel(panel)
            return
        context = self._ensure_context()
        subplot = getattr(context.figure, "subplot", None)
        if subplot is None:
            raise TypeError("subplot FigurePlan requires Figure.subplot support")
        with subplot(**dict(subplot_options)):
            for panel in self.plan.panels:
                self._execute_panel(panel)

    def execute_plan(self, plan: FigurePlan | None = None) -> "FigureExecutor":
        """Execute one complete figure plan and return this fluent executor."""
        if plan is not None and plan is not self.plan:
            self.plan = plan
            self._context = None

        all_layers = self._all_layers()
        enabled_layers = self._enabled_layers(all_layers)
        save_layers = tuple(
            layer for layer in enabled_layers if layer.handler == "savefig"
        )
        if save_layers and save_layers[-1] is not enabled_layers[-1]:
            raise ValueError(
                f"[{save_layers[-1].section}] must be the last enabled figure operation"
            )
        if len(save_layers) > 1:
            raise ValueError("a figure plan may contain only one enabled figure.savefig operation")

        for layer in self.plan.operations:
            self.apply(layer)
        if self._context is not None:
            self._context.figure_resources = dict(self._context.resources)
        self._execute_panels()
        for layer in self.plan.figure_layers:
            self.apply(layer)
        return self

    def execute(self) -> "FigureExecutor":
        """Execute the configured plan through the compatibility entry point."""
        return self.execute_plan()


__all__ = ["FigureExecutor", "RenderContext"]
