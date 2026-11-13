"""
geodesy_visualization.figure_ops.config
=======================================

功能概述:
    将严格、有序的 INI CFG 编译为类型化 Figure 操作计划，并统一处理
    section 命名、相对路径、参数类型与跨操作资源引用。

函数说明:
    ``load_figure_plan``:
        读取并校验一个完整配置文件，返回不可变的有序 FigurePlan。
"""

from __future__ import annotations

import configparser
import re
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .model import FigureOperation, FigurePlan
from .registry import DEFAULT_REGISTRY, OperationRegistry, OperationSpec


_SECTION_RE = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*")
_PROJECT_KEYS = frozenset({"processing_root"})
_FIGURE_KEYS = frozenset({"layout"})
_SUPPORTED_LAYOUTS = frozenset({"publication_sidecar"})
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def _validate_keys(section: str, values: Mapping[str, str], allowed: frozenset[str]) -> None:
    """Reject unsupported keys while identifying their containing section."""
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise ValueError(
            f"unknown key(s) in [{section}]: {', '.join(unknown)}"
        )


def _parse_bool(value: str, section: str, key: str) -> bool:
    """Parse one strict human-readable boolean with section-qualified errors."""
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"[{section}] {key} must be yes/no or true/false; got {value!r}")


def _resolve_path(value: str, base_dir: Path) -> str:
    """Resolve a local path from the CFG directory while preserving GMT remotes."""
    if value.startswith("@"):
        return value
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return str(path.resolve())


def _parse_region(value: str, section: str) -> tuple[float, float, float, float]:
    """Parse west/east/south/north and enforce increasing bounds."""
    fields = [field.strip() for field in value.split(",")]
    if len(fields) != 4:
        raise ValueError(f"[{section}] region must contain west,east,south,north")
    try:
        west, east, south, north = (float(field) for field in fields)
    except ValueError as exc:
        raise ValueError(f"[{section}] region contains a non-numeric value") from exc
    if west >= east or south >= north:
        raise ValueError(f"[{section}] region bounds must be strictly increasing")
    return west, east, south, north


def _normalize_options(
    section: str,
    raw: Mapping[str, str],
    spec: OperationSpec,
    base_dir: Path,
) -> Mapping[str, object]:
    """Validate and normalize the options declared by one operation spec."""
    _validate_keys(section, raw, spec.allowed_keys)
    missing = sorted(key for key in spec.required_keys if not raw.get(key, "").strip())
    if missing:
        raise ValueError(f"missing required key(s) in [{section}]: {', '.join(missing)}")

    normalized: dict[str, object] = {}
    for key, value in raw.items():
        stripped = value.strip()
        try:
            if key in spec.bool_keys:
                normalized[key] = _parse_bool(stripped, section, key)
            elif key in spec.int_keys:
                normalized[key] = int(stripped)
            elif key in spec.float_keys:
                normalized[key] = float(stripped)
            elif key in spec.path_keys:
                normalized[key] = _resolve_path(stripped, base_dir)
            elif key == "region":
                normalized[key] = _parse_region(stripped, section)
            else:
                normalized[key] = stripped
        except ValueError as exc:
            if str(exc).startswith(f"[{section}]"):
                raise
            raise ValueError(f"invalid value for [{section}] {key}: {value!r}") from exc
    return MappingProxyType(normalized)


def load_figure_plan(
    config_file: str | Path,
    registry: OperationRegistry = DEFAULT_REGISTRY,
) -> FigurePlan:
    """Load one strict ordered CFG into an immutable Figure operation plan."""
    path = Path(config_file).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"figure configuration not found: {path}")

    parser = configparser.ConfigParser(
        interpolation=None,
        strict=True,
        empty_lines_in_values=False,
    )
    parser.optionxform = str
    with path.open("r", encoding="utf-8") as stream:
        parser.read_file(stream)

    project_raw = dict(parser.items("project")) if parser.has_section("project") else {}
    figure_raw = dict(parser.items("figure")) if parser.has_section("figure") else {}
    _validate_keys("project", project_raw, _PROJECT_KEYS)
    _validate_keys("figure", figure_raw, _FIGURE_KEYS)
    if "layout" not in figure_raw or not figure_raw["layout"].strip():
        raise ValueError("missing required key in [figure]: layout")
    layout = figure_raw["layout"].strip()
    if layout not in _SUPPORTED_LAYOUTS:
        raise ValueError(
            f"unsupported [figure] layout {layout!r}; choose publication_sidecar"
        )

    base_dir = path.parent
    project = dict(project_raw)
    if project.get("processing_root"):
        project["processing_root"] = _resolve_path(project["processing_root"], base_dir)

    operations: list[FigureOperation] = []
    for section in parser.sections():
        if section in {"project", "figure"}:
            continue
        if _SECTION_RE.fullmatch(section) is None:
            raise ValueError(
                f"invalid section name '{section}'; use lowercase snake_case dotted identifiers"
            )
        spec = registry.resolve(section)
        tokens = section.split(".")
        options = _normalize_options(section, dict(parser.items(section)), spec, base_dir)
        for key in spec.path_keys - {"fname"}:
            value = str(options[key])
            if not value.startswith("@") and not Path(value).is_file():
                raise FileNotFoundError(f"[{section}] {key} input not found: {value}")
        operations.append(
            FigureOperation(
                section=section,
                method=tokens[1],
                semantics=tuple(tokens[2:]),
                options=options,
                order=len(operations),
                handler=spec.handler,
            )
        )

    known_sections = {operation.section for operation in operations}
    for operation in operations:
        source = operation.options.get("source")
        if source is not None and source not in known_sections:
            raise ValueError(
                f"[{operation.section}] source references unknown operation {source!r}"
            )
        if source is not None and not str(source).startswith("figure.grdimage."):
            raise ValueError(
                f"[{operation.section}] source must reference a figure.grdimage operation"
            )

    save_operations = [
        operation for operation in operations if operation.handler == "savefig"
    ]
    if len(save_operations) != 1:
        raise ValueError("figure plan requires exactly one [figure.savefig] operation")
    processing_root = project.get("processing_root")
    if processing_root:
        output = Path(str(save_operations[0].options["fname"]))
        if not output.is_relative_to(Path(processing_root)):
            raise ValueError(
                "[figure.savefig] fname must remain inside [project] processing_root"
            )

    return FigurePlan(
        config_path=path,
        project=MappingProxyType(project),
        figure=MappingProxyType({"layout": layout}),
        operations=tuple(operations),
    )


__all__ = ["load_figure_plan"]
