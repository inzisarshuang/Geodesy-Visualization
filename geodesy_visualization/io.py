"""
geodesy_visualization.io
========================

功能概述:
    集中提供 Geodesy-Visualization 所需的严格 cfg 解析、路径解析、参数转换、
    临时文件管理、原子替换和 GDAL 命令调用功能。

函数说明:
    文件与外部命令:
        ``gdal_translate``:
            使用参数列表调用 GDAL，将栅格转换为指定格式。
        ``gmt_grdconvert``:
            使用 GMT 原生命令将可读栅格转换为 NetCDF 浮点网格。
        ``temporary_path``:
            创建唯一临时路径，并在退出上下文时清理文件和 GDAL 边车文件。
        ``replace_dataset``:
            原子替换目标栅格，并同步处理 GDAL 边车文件。
    配置读取与路径:
        ``_expand_cfg_refs``:
            展开 cfg 和环境变量引用，并检测循环引用。
        ``load_key_value_config``:
            严格读取 key=value 或 key:value 配置文件。
        ``validate_config_keys``:
            拒绝未知配置键，并为可能的拼写错误给出建议。
        ``resolve_path`` / ``resolve_output_path``:
            根据 cfg 目录和输出目录解析输入、输出路径。
        ``get_required`` / ``get_optional``:
            读取必需或可选配置值。
    参数解析与校验:
        ``parse_bool`` / ``parse_float`` / ``parse_int``:
            将人类可读配置值转换为基础数据类型。
        ``parse_csv_strings`` / ``parse_coord_pairs``:
            解析逗号分隔字符串和经纬度坐标对。
        ``parse_choice`` / ``parse_style_block``:
            解析限定选项和多组绘图样式。
        ``validate_numeric_range`` / ``validate_closed_range``:
            校验数值上下界和闭区间约束。
        ``validate_same_length``:
            校验多组关联参数具有相同长度。
"""

from __future__ import annotations

from contextlib import contextmanager
import os
import re
import subprocess
import sys
import tempfile
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


def gdal_translate(
    src: str,
    dst: str,
    fmt: str = "GSBG",
    bands: Optional[Sequence[int]] = None,
    creation_options: Optional[Sequence[str]] = None,
) -> None:
    """Run gdal_translate through the GDAL CLI without requiring osgeo bindings."""
    environment_gdal = Path(sys.prefix) / "bin" / "gdal_translate"
    executable = str(environment_gdal) if environment_gdal.is_file() else "gdal_translate"
    cmd = [executable, "-of", fmt]
    for band in bands or []:
        cmd.extend(["-b", str(band)])
    for option in creation_options or []:
        cmd.extend(["-co", option])
    cmd.extend([src, dst])
    subprocess.run(cmd, check=True)


def gmt_grdconvert(src: str, dst: str) -> None:
    """Convert a GDAL/GMT-readable raster to an unambiguous NetCDF float grid."""
    environment_gmt = Path(sys.prefix) / "bin" / "gmt"
    executable = str(environment_gmt) if environment_gmt.is_file() else "gmt"
    subprocess.run([executable, "grdconvert", src, f"{dst}=nf"], check=True)


@contextmanager
def temporary_path(directory: Path, suffix: str) -> Iterator[Path]:
    """Yield a unique temporary path and remove it and its GDAL sidecars afterward."""
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".pygmt_", suffix=suffix, dir=directory)
    os.close(descriptor)
    path = Path(name)
    path.unlink(missing_ok=True)
    try:
        yield path
    finally:
        for related_path in (path, Path(f"{path}.aux.xml"), Path(f"{path}.ovr")):
            related_path.unlink(missing_ok=True)


def replace_dataset(source: Path, destination: Path) -> None:
    """Atomically replace a raster and move its GDAL sidecar metadata when present."""
    os.replace(source, destination)
    for sidecar_suffix in (".aux.xml", ".ovr"):
        source_sidecar = Path(f"{source}{sidecar_suffix}")
        destination_sidecar = Path(f"{destination}{sidecar_suffix}")
        if source_sidecar.exists():
            os.replace(source_sidecar, destination_sidecar)
        else:
            destination_sidecar.unlink(missing_ok=True)


_CFG_REF_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_CFG_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INLINE_COMMENT_RE = re.compile(r"\s+#.*$")


def _expand_cfg_refs(values: Dict[str, str], config_file: Path) -> Dict[str, str]:
    """Expand config and environment references with cycle detection."""
    resolved: Dict[str, str] = {}

    def resolve(key: str, stack: Tuple[str, ...] = ()) -> str:
        """Resolve one key recursively while tracking the active reference chain."""
        if key in resolved:
            return resolved[key]
        if key in stack:
            chain = " -> ".join((*stack, key))
            raise ValueError(f"cyclic configuration reference in {config_file}: {chain}")

        def replace(match: re.Match[str]) -> str:
            """Replace one ${name} token from cfg values or the environment."""
            referenced_key = match.group(1)
            if referenced_key in values:
                return resolve(referenced_key, (*stack, key))
            environment_value = os.environ.get(referenced_key)
            if environment_value is not None:
                return environment_value
            raise ValueError(
                f"unresolved reference '${{{referenced_key}}}' in key '{key}' "
                f"of {config_file}"
            )

        expanded = _CFG_REF_RE.sub(replace, values[key])
        resolved[key] = os.path.expanduser(expanded)
        return resolved[key]

    return {key: resolve(key) for key in values}


def load_key_value_config(config_file: str) -> Dict[str, str]:
    """Read a strict key=value or key:value configuration file."""
    path = Path(config_file).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"configuration file not found: {config_file}")

    values: Dict[str, str] = {}
    with path.open("r", encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" in line:
                key, raw_value = line.split("=", 1)
            elif ":" in line:
                key, raw_value = line.split(":", 1)
            else:
                raise ValueError(
                    f"invalid configuration line {path}:{line_number}; "
                    "expected key=value"
                )

            key = key.strip()
            if not _CFG_KEY_RE.fullmatch(key):
                raise ValueError(f"invalid configuration key '{key}' at {path}:{line_number}")
            if key in values:
                raise ValueError(f"duplicate configuration key '{key}' at {path}:{line_number}")

            # A comment marker starts an inline comment only when preceded by
            # whitespace, so values such as #1f77b4 remain valid colors.
            value = _INLINE_COMMENT_RE.sub("", raw_value.strip()).strip()
            values[key] = value
    return _expand_cfg_refs(values, path)


def validate_config_keys(
    cfg: Dict[str, str],
    allowed_keys: Iterable[str],
    config_file: str,
    allowed_prefixes: Sequence[str] = (),
) -> None:
    """Reject unknown keys and suggest the closest supported spelling."""
    allowed = set(allowed_keys)
    unknown = sorted(
        key
        for key in cfg
        if key not in allowed and not any(key.startswith(prefix) for prefix in allowed_prefixes)
    )
    if not unknown:
        return

    details = []
    for key in unknown:
        matches = get_close_matches(key, allowed, n=1, cutoff=0.65)
        suggestion = f"; did you mean '{matches[0]}'?" if matches else ""
        details.append(f"'{key}'{suggestion}")
    raise ValueError(f"unknown configuration key(s) in {config_file}: {', '.join(details)}")


def resolve_path(value: str, base_dir: Path) -> str:
    """Resolve a path relative to the config directory when needed."""
    expanded = Path(os.path.expandvars(os.path.expanduser(value)))
    if expanded.is_absolute():
        return str(expanded)
    return str((base_dir / expanded).resolve())


def resolve_output_path(value: str, output_dir: str, base_dir: Path) -> str:
    """Resolve output paths, placing bare filenames inside output_dir."""
    expanded = Path(os.path.expandvars(os.path.expanduser(value)))
    if expanded.is_absolute():
        return str(expanded)
    if expanded.parent == Path("."):
        return str((Path(output_dir) / expanded).resolve())
    return str((base_dir / expanded).resolve())


def get_required(cfg: Dict[str, str], key: str) -> str:
    """Return a required config value or raise a helpful error."""
    value = cfg.get(key, "").strip()
    if not value:
        raise ValueError(f"missing required configuration key: {key}")
    return value


def get_optional(cfg: Dict[str, str], key: str, default: str = "") -> str:
    """Return an optional config value."""
    return cfg.get(key, default).strip()


def parse_bool(value: str | bool | None, default: bool = False) -> bool:
    """Parse common boolean strings."""
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"cannot parse boolean value: {value}")


def parse_float(value: str | None, default: float) -> float:
    """Parse a float with fallback."""
    if value is None or str(value).strip() == "":
        return default
    return float(value)


def parse_int(value: str | None, default: int) -> int:
    """Parse an int with fallback."""
    if value is None or str(value).strip() == "":
        return default
    return int(value)


def parse_csv_strings(value: str | None) -> List[str]:
    """Parse a comma-separated string list."""
    if value is None or str(value).strip() == "":
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def parse_coord_pairs(value: str) -> List[Tuple[float, float]]:
    """Parse 'lon,lat; lon,lat; ...' coordinate pairs."""
    pairs: List[Tuple[float, float]] = []
    for index, item in enumerate(value.split(";"), start=1):
        item = item.strip()
        if not item:
            continue
        parts = [part.strip() for part in item.split(",")]
        if len(parts) != 2:
            raise ValueError(f"invalid coordinate pair #{index}: '{item}'; expected lon,lat")
        pairs.append((float(parts[0]), float(parts[1])))
    return pairs


def parse_choice(value: str, choices: Sequence[str], key: str) -> str:
    """Parse a case-insensitive choice and report the supported values."""
    normalized = value.strip().lower()
    allowed = {choice.lower() for choice in choices}
    if normalized not in allowed:
        raise ValueError(f"invalid value for {key}: '{value}'; choose from {', '.join(choices)}")
    return normalized


def validate_numeric_range(
    minimum: float,
    maximum: float,
    minimum_key: str,
    maximum_key: str,
) -> None:
    """Ensure the lower numeric limit is smaller than the upper limit."""
    if minimum >= maximum:
        raise ValueError(f"{minimum_key} must be smaller than {maximum_key}")


def validate_closed_range(value: float, key: str, minimum: float, maximum: float) -> None:
    """Ensure a numeric value falls inside a closed interval."""
    if not minimum <= value <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}; got {value}")


def parse_style_block(
    cfg: Dict[str, str],
    prefix: str,
    default_title: str,
    default_annot: str,
    default_label: str,
) -> Dict[str, str]:
    """Collect font-related style values for a named block."""
    return {
        "FONT_TITLE": get_optional(cfg, f"{prefix}_font_title", default_title),
        "FONT_ANNOT_PRIMARY": get_optional(cfg, f"{prefix}_font_annot_primary", default_annot),
        "FONT_LABEL": get_optional(cfg, f"{prefix}_font_label", default_label),
    }


def validate_same_length(items: Sequence[Sequence[object]], names: Sequence[str]) -> None:
    """Ensure multiple parsed lists have the same length."""
    lengths = [len(item) for item in items]
    if len(set(lengths)) > 1:
        detail = ", ".join(f"{name}={length}" for name, length in zip(names, lengths))
        raise ValueError(f"list lengths do not match: {detail}")


__all__ = [
    "gdal_translate",
    "get_optional",
    "get_required",
    "gmt_grdconvert",
    "load_key_value_config",
    "parse_bool",
    "parse_choice",
    "parse_coord_pairs",
    "parse_csv_strings",
    "parse_float",
    "parse_int",
    "parse_style_block",
    "replace_dataset",
    "resolve_output_path",
    "resolve_path",
    "temporary_path",
    "validate_closed_range",
    "validate_config_keys",
    "validate_numeric_range",
    "validate_same_length",
]
