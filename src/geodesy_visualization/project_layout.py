"""
geodesy_visualization.project_layout
====================================

功能概述:
    为 Visualization 工作流生成受约束的方法根论文图目录。

函数说明:
    ``VisualizationProjectLayout``:
        绑定项目、case 与处理方法根，并生成 FIGURES/PUBLICATION 路径。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_CASE = re.compile(r"[A-Z0-9_]+")
_METHOD = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
_WORKFLOW = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


@dataclass(frozen=True)
class VisualizationProjectLayout:
    project_root: Path
    case_root: Path
    processing_root: Path

    @classmethod
    def bind(
        cls,
        project_root: str | Path,
        project: str,
        processing_root: str,
    ) -> "VisualizationProjectLayout":
        """Bind one SENSOR/CASE/METHOD root inside an existing project."""
        root = Path(project_root).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"project_root must be an existing directory: {root}")
        case_parts = project.split("/")
        method_parts = processing_root.split("/")
        if len(case_parts) != 2 or any(
            not part or _CASE.fullmatch(part) is None for part in case_parts
        ):
            raise ValueError("project must be SENSOR/CASE with uppercase components")
        if (
            len(method_parts) != 3
            or method_parts[:2] != case_parts
            or _METHOD.fullmatch(method_parts[2]) is None
        ):
            raise ValueError(
                "processing_root must be SENSOR/CASE/METHOD below the declared project"
            )
        return cls(
            root,
            root.joinpath(*case_parts).resolve(),
            root.joinpath(*method_parts).resolve(),
        )

    def publication(self, workflow: str) -> Path:
        """Return the centralized publication directory for one workflow."""
        if _WORKFLOW.fullmatch(workflow) is None:
            raise ValueError(f"unsafe publication workflow: {workflow!r}")
        return self.processing_root / "FIGURES" / "PUBLICATION" / workflow.upper()


__all__ = ["VisualizationProjectLayout"]
