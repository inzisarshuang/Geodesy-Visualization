"""
geodesy_visualization.figure_ops.cartography_inputs
==================================================

功能概述:
    为研究区制图准备 KML footprint 与断层线数据，不依赖可选的 Python
    GDAL/GeoPandas 绑定，并统一运动学分类优先级。

函数说明:
    ``FaultFeature``:
        保存一条可绘制断层线及其原始运动学描述。
    ``parse_kml_footprints``:
        读取 KML Polygon/MultiGeometry 中的全部外边界并显式闭合。
    ``read_fault_features``:
        通过 ogr2ogr 导出 GeoJSON，读取并展开 LineString/MultiLineString。
    ``classify_fault_kinematics``:
        按走滑、逆冲、正断和其他的固定优先级分类断层。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

import numpy as np


@dataclass(frozen=True)
class FaultFeature:
    """Contain one fault line and its source kinematic description."""

    coordinates: np.ndarray
    kinematics: str


def _coordinate_array(
    coordinates: Sequence[Sequence[float]],
    path: Path,
) -> np.ndarray:
    """Normalize one GeoJSON line to a finite two-column coordinate array."""
    try:
        array = np.asarray([[point[0], point[1]] for point in coordinates], dtype=float)
    except (IndexError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid line coordinates in fault dataset: {path}") from exc
    if array.ndim != 2 or array.shape[1] != 2 or len(array) < 2:
        raise ValueError(f"fault line must contain at least two lon/lat points: {path}")
    if not np.isfinite(array).all():
        raise ValueError(f"fault line contains non-finite coordinates: {path}")
    return array


def parse_kml_footprints(path: str | Path) -> tuple[np.ndarray, ...]:
    """Return every explicitly closed KML Polygon outer boundary as lon/lat arrays."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"footprint KML not found: {source}")
    try:
        root = ET.parse(source).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"invalid KML XML in {source}: {exc}") from exc

    coordinate_elements = root.findall(".//{*}Polygon//{*}coordinates")
    polygons: list[np.ndarray] = []
    saw_non_empty = False
    for element in coordinate_elements:
        text = (element.text or "").strip()
        if not text:
            continue
        saw_non_empty = True
        points: list[tuple[float, float]] = []
        for token in text.split():
            fields = token.split(",")
            if len(fields) < 2:
                raise ValueError(f"malformed coordinate {token!r} in footprint KML: {source}")
            try:
                longitude, latitude = float(fields[0]), float(fields[1])
            except ValueError as exc:
                raise ValueError(
                    f"malformed coordinate {token!r} in footprint KML: {source}"
                ) from exc
            if not np.isfinite([longitude, latitude]).all():
                raise ValueError(f"non-finite coordinate {token!r} in footprint KML: {source}")
            points.append((longitude, latitude))
        if len(points) < 3:
            raise ValueError(f"footprint polygon requires at least three points: {source}")
        if points[0] != points[-1]:
            points.append(points[0])
        polygons.append(np.asarray(points, dtype=float))

    if not saw_non_empty or not polygons:
        raise ValueError(f"KML contains no non-empty Polygon coordinates: {source}")
    return tuple(polygons)


def read_fault_features(
    path: str | Path,
    kinematic_field: str,
) -> tuple[FaultFeature, ...]:
    """Read fault line features through ogr2ogr GeoJSON standard output."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"fault dataset not found: {source}")
    executable = shutil.which("ogr2ogr")
    if executable is None:
        raise RuntimeError("ogr2ogr is required to read configured fault datasets")
    completed = subprocess.run(
        [executable, "-f", "GeoJSON", "/vsistdout/", str(source), "-t_srs", "EPSG:4326"],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        collection = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"ogr2ogr returned invalid GeoJSON for fault dataset: {source}") from exc

    results: list[FaultFeature] = []
    for index, feature in enumerate(collection.get("features", [])):
        properties = feature.get("properties") or {}
        if kinematic_field not in properties:
            raise ValueError(
                f"{kinematic_field!r}: configured kinematic field is missing from "
                f"feature {index} in {source}"
            )
        kinematics = "" if properties[kinematic_field] is None else str(properties[kinematic_field])
        geometry = feature.get("geometry") or {}
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")
        if geometry_type == "LineString":
            lines = [coordinates]
        elif geometry_type == "MultiLineString":
            lines = coordinates
        else:
            raise ValueError(
                f"fault feature {index} in {source} must be LineString or MultiLineString; "
                f"got {geometry_type!r}"
            )
        if not isinstance(lines, list) or not lines:
            raise ValueError(f"fault feature {index} contains no line coordinates: {source}")
        for line in lines:
            results.append(FaultFeature(_coordinate_array(line, source), kinematics))
    if not results:
        raise ValueError(f"fault dataset contains no drawable line features: {source}")
    return tuple(results)


def classify_fault_kinematics(
    value: str,
) -> Literal["strike_slip", "reverse", "normal", "other"]:
    """Classify a fault description with strike-slip taking precedence."""
    normalized = value.casefold()
    if any(
        token in normalized
        for token in ("left lateral", "right lateral", "strike-slip", "strike slip")
    ):
        return "strike_slip"
    if "reverse" in normalized or "thrust" in normalized:
        return "reverse"
    if "normal" in normalized:
        return "normal"
    return "other"


__all__ = [
    "FaultFeature",
    "classify_fault_kinematics",
    "parse_kml_footprints",
    "read_fault_features",
]
