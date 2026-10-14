"""
geodesy_visualization.workflows.insar.baseline_config
====================================================

功能概述:
    严格读取 InSAR 基线图多 case 配置，以项目根目录解析输入输出
    路径，并在导入 Matplotlib 前完成参数与路径边界校验。

函数说明:
    ``BaselinePlotCase``:
        表示一个已完全解析的基线图绘制请求。
    ``load_baseline_plot_config``:
        读取并校验 ``[project]``、``[defaults]`` 和 ``[case:name]``。
    ``select_baseline_plot_case``:
        从有序 case 中选择唯一待执行请求。
"""

from __future__ import annotations

import configparser
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


_CASE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_KEYS = {
    "baseline_manifest",
    "output",
    "title",
    "dpi",
    "figsize",
    "y_top_extra",
    "y_bottom_extra",
    "font_family",
}
_DEFAULTS = {
    "title": "Perpendicular Baselines History",
    "dpi": "300",
    "figsize": "10.5, 6.2",
    "y_top_extra": "50",
    "y_bottom_extra": "0",
    "font_family": "TeX Gyre Heros",
}


@dataclass(frozen=True)
class BaselinePlotCase:
    """Store one project-confined baseline visualization request."""

    name: str
    project_root: Path
    baseline_manifest: Path
    output: Path
    title: str
    dpi: int
    figsize: tuple[float, float]
    y_top_extra: float
    y_bottom_extra: float
    font_family: str


def _within(path: Path, root: Path, label: str) -> Path:
    """Resolve a path and reject values outside the configured project."""

    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{label} must stay inside project root: {root}") from error
    return resolved


def _unknown(section: configparser.SectionProxy, source: Path) -> None:
    """Reject unsupported keys in one defaults or case section."""

    unknown = sorted(set(section) - _KEYS)
    if unknown:
        raise ValueError(f"{source}: unknown key in [{section.name}]: {unknown[0]}")


def _positive_integer(value: str, key: str, source: Path) -> int:
    """Parse a positive integer configuration value."""

    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{source}: {key} must be a positive integer") from error
    if parsed < 1:
        raise ValueError(f"{source}: {key} must be a positive integer")
    return parsed


def _nonnegative_float(value: str, key: str, source: Path) -> float:
    """Parse a finite, non-negative floating-point configuration value."""

    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{source}: {key} must be a non-negative number") from error
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{source}: {key} must be a non-negative number")
    return parsed


def _figsize(value: str, source: Path) -> tuple[float, float]:
    """Parse a positive width/height pair in inches."""

    fields = value.replace(",", " ").split()
    if len(fields) != 2:
        raise ValueError(f"{source}: figsize must contain two positive numbers")
    try:
        parsed = tuple(float(field) for field in fields)
    except ValueError as error:
        raise ValueError(
            f"{source}: figsize must contain two positive numbers"
        ) from error
    if any(not math.isfinite(number) or number <= 0 for number in parsed):
        raise ValueError(f"{source}: figsize must contain two positive numbers")
    return parsed  # type: ignore[return-value]


def load_baseline_plot_config(path: Path) -> tuple[BaselinePlotCase, ...]:
    """Load ordered, fully resolved baseline plot cases from one cfg file."""

    source = Path(path).expanduser().resolve(strict=True)
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        with source.open("r", encoding="utf-8") as stream:
            parser.read_file(stream)
    except configparser.Error as error:
        raise ValueError(f"invalid baseline plot configuration {source}: {error}") from error
    if not parser.has_section("project"):
        raise ValueError(f"{source}: missing [project] section")
    project = parser["project"]
    unknown_project = sorted(set(project) - {"root"})
    if unknown_project:
        raise ValueError(f"{source}: unknown key in [project]: {unknown_project[0]}")
    root_value = project.get("root", "").strip()
    if not root_value:
        raise ValueError(f"{source}: [project] root is required")
    root_candidate = Path(root_value).expanduser()
    root = (
        root_candidate
        if root_candidate.is_absolute()
        else source.parent / root_candidate
    ).resolve(strict=True)
    defaults = dict(_DEFAULTS)
    if parser.has_section("defaults"):
        _unknown(parser["defaults"], source)
        defaults.update(
            (key, value.strip()) for key, value in parser["defaults"].items()
        )
    cases: list[BaselinePlotCase] = []
    for section_name in parser.sections():
        if section_name in {"project", "defaults"}:
            continue
        if not section_name.startswith("case:"):
            raise ValueError(f"{source}: unsupported section [{section_name}]")
        name = section_name.removeprefix("case:").strip()
        if not _CASE_NAME.fullmatch(name):
            raise ValueError(f"{source}: unsafe or empty case name: {name!r}")
        section = parser[section_name]
        _unknown(section, source)
        values = dict(defaults)
        values.update((key, value.strip()) for key, value in section.items())
        missing = [
            key for key in ("baseline_manifest", "output") if not values.get(key)
        ]
        if missing:
            raise ValueError(
                f"{source}: [{section_name}] missing keys: {', '.join(missing)}"
            )
        manifest_value = Path(values["baseline_manifest"]).expanduser()
        manifest = _within(
            manifest_value if manifest_value.is_absolute() else root / manifest_value,
            root,
            "baseline manifest",
        )
        if not manifest.is_file() or manifest.stat().st_size == 0:
            raise FileNotFoundError(f"baseline manifest not found or empty: {manifest}")
        output_value = Path(values["output"]).expanduser()
        output = _within(
            output_value if output_value.is_absolute() else root / output_value,
            root,
            "plot output",
        )
        cases.append(
            BaselinePlotCase(
                name=name,
                project_root=root,
                baseline_manifest=manifest,
                output=output,
                title=values["title"] or _DEFAULTS["title"],
                dpi=_positive_integer(values["dpi"], "dpi", source),
                figsize=_figsize(values["figsize"], source),
                y_top_extra=_nonnegative_float(
                    values["y_top_extra"], "y_top_extra", source
                ),
                y_bottom_extra=_nonnegative_float(
                    values["y_bottom_extra"], "y_bottom_extra", source
                ),
                font_family=values["font_family"] or _DEFAULTS["font_family"],
            )
        )
    if not cases:
        raise ValueError(f"{source}: at least one [case:name] section is required")
    return tuple(cases)


def select_baseline_plot_case(
    cases: Sequence[BaselinePlotCase], name: str | None
) -> BaselinePlotCase:
    """Select a named case, requiring a name only when multiple cases exist."""

    if name is None:
        if len(cases) != 1:
            raise ValueError("--case is required when configuration has multiple cases")
        return cases[0]
    for case in cases:
        if case.name == name:
            return case
    raise ValueError(f"unknown case: {name}")


__all__ = [
    "BaselinePlotCase",
    "load_baseline_plot_config",
    "select_baseline_plot_case",
]
