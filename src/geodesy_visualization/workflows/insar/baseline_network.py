"""
geodesy_visualization.workflows.insar.baseline_network
=====================================================

功能概述:
    读取 Analysis 发布的标准基线清单及网络表，校验完整性并构建
    与处理引擎无关的时间—垂直基线可视化数据。本模块不调用 GAMMA，
    也不修改 Analysis 产品。

函数说明:
    ``BaselineManifest``:
        表示已验证的 Analysis 基线清单身份与网络文件位置。
    ``BaselinePair``:
        表示一条保持原始顺序的干涉对基线记录。
    ``BaselineNetwork``:
        表示可绘制的日期、干涉对和相对垂直基线。
    ``read_baseline_manifest``:
        读取并校验 Analysis schema-1/schema-2 基线清单。
    ``read_baseline_network``:
        读取四列基线网络并求解各日期相对垂直基线。
    ``plot_baseline_network``:
        将已验证的时间—垂直基线网络原子发布为 PNG 图件。
"""

from __future__ import annotations

import json
import math
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType

from geodesy_visualization.io import atomic_output_path


@dataclass(frozen=True)
class BaselineManifest:
    """Store one validated Analysis manifest and its resolved network path."""

    source_path: Path
    project_root: Path
    network_path: Path
    reference_date: str
    pair_count: int
    network_type: str


@dataclass(frozen=True)
class BaselinePair:
    """Store one ordered pair and its perpendicular/time baseline values."""

    master: str
    slave: str
    perpendicular_baseline_m: float
    temporal_baseline_days: float


@dataclass(frozen=True)
class BaselineNetwork:
    """Store the immutable display data derived from one baseline product."""

    manifest: BaselineManifest
    pairs: tuple[BaselinePair, ...]
    dates: tuple[str, ...]
    perpendicular_baselines_m: Mapping[str, float]


def _inside(path: Path, root: Path, label: str) -> Path:
    """Resolve one path and reject values outside the declared project."""

    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{label} must stay inside project root: {root}") from error
    return resolved


def _date(value: object, label: str) -> str:
    """Normalize a strict YYYYMMDD string without accepting implicit formats."""

    if not isinstance(value, str):
        raise ValueError(f"{label} must be YYYYMMDD")
    try:
        parsed = datetime.strptime(value, "%Y%m%d")
    except ValueError as error:
        raise ValueError(f"{label} must be a valid YYYYMMDD date: {value!r}") from error
    if parsed.strftime("%Y%m%d") != value:
        raise ValueError(f"{label} must be a valid YYYYMMDD date: {value!r}")
    return value


def read_baseline_manifest(
    path: Path, *, project_root: Path
) -> BaselineManifest:
    """Read one complete Analysis baseline manifest safely."""

    root = Path(project_root).expanduser().resolve(strict=True)
    source = _inside(Path(path), root, "baseline manifest")
    if not source.is_file():
        raise FileNotFoundError(f"baseline manifest not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid baseline manifest JSON {source}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("baseline manifest root must be a JSON object")
    if payload.get("schema_version") not in {1, 2}:
        raise ValueError("baseline manifest schema_version must be 1 or 2")
    if payload.get("status") != "complete":
        raise ValueError("baseline manifest status must be complete")
    reference_date = _date(
        payload.get("reference_date"), "baseline manifest reference_date"
    )
    pair_count = payload.get("pair_count")
    if (
        not isinstance(pair_count, int)
        or isinstance(pair_count, bool)
        or pair_count < 1
    ):
        raise ValueError("baseline manifest pair_count must be a positive integer")
    raw_network = payload.get("network_path")
    if not isinstance(raw_network, str) or not raw_network.strip():
        raise ValueError("baseline manifest network_path is required")
    relative_network = Path(raw_network.strip())
    if relative_network.is_absolute():
        raise ValueError("baseline manifest network_path must be relative")
    if ".." in relative_network.parts:
        raise ValueError("baseline manifest network_path cannot traverse with '..'")
    network_path = _inside(
        source.parent / relative_network, root, "baseline network"
    )
    try:
        network_path.relative_to(source.parent)
    except ValueError as error:
        raise ValueError("baseline network must stay beside its manifest") from error
    network_type = payload.get("network_type", "")
    if not isinstance(network_type, str):
        raise ValueError("baseline manifest network_type must be text")
    return BaselineManifest(
        source_path=source,
        project_root=root,
        network_path=network_path,
        reference_date=reference_date,
        pair_count=pair_count,
        network_type=network_type.strip().upper(),
    )


def _solve_perpendicular_baselines(
    pairs: tuple[BaselinePair, ...], dates: tuple[str, ...], reference_date: str
) -> Mapping[str, float]:
    """Accumulate signed pair baselines from the declared reference date."""

    graph: dict[str, list[tuple[str, float]]] = {date: [] for date in dates}
    for pair in pairs:
        graph[pair.master].append((pair.slave, pair.perpendicular_baseline_m))
        graph[pair.slave].append((pair.master, -pair.perpendicular_baseline_m))
    solved: dict[str, float] = {reference_date: 0.0}
    queue: deque[str] = deque([reference_date])
    while queue:
        current = queue.popleft()
        for neighbor, delta in graph[current]:
            if neighbor in solved:
                continue
            solved[neighbor] = solved[current] + delta
            queue.append(neighbor)
    missing = [date for date in dates if date not in solved]
    if missing:
        raise ValueError(
            "baseline network is disconnected from reference date "
            f"{reference_date}: {', '.join(missing)}"
        )
    return MappingProxyType(solved)


def read_baseline_network(manifest: BaselineManifest) -> BaselineNetwork:
    """Read and validate the manifest's ordered four-column network table."""

    if not isinstance(manifest, BaselineManifest):
        raise TypeError("manifest must be BaselineManifest")
    path = manifest.network_path
    if not path.is_file():
        raise FileNotFoundError(f"baseline network not found: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"baseline network is empty: {path}")
    pairs: list[BaselinePair] = []
    directed: set[tuple[str, str]] = set()
    undirected: set[frozenset[str]] = set()
    dates: set[str] = set()
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 4:
            raise ValueError(
                f"baseline network line {line_number} must contain four columns"
            )
        master = _date(fields[0], f"network line {line_number} master date")
        slave = _date(fields[1], f"network line {line_number} slave date")
        if master == slave:
            raise ValueError(f"baseline network contains self pair: {master}-{slave}")
        directed_key = (master, slave)
        if directed_key in directed:
            raise ValueError(
                f"baseline network contains duplicate pair: {master}-{slave}"
            )
        undirected_key = frozenset(directed_key)
        if undirected_key in undirected:
            raise ValueError(
                f"baseline network contains reversed pair: {master}-{slave}"
            )
        try:
            perpendicular = float(fields[2])
            temporal = float(fields[3])
        except ValueError as error:
            raise ValueError(
                f"baseline network line {line_number} has non-numeric baselines"
            ) from error
        if not math.isfinite(perpendicular) or not math.isfinite(temporal):
            raise ValueError(
                f"baseline network line {line_number} baselines must be finite"
            )
        directed.add(directed_key)
        undirected.add(undirected_key)
        dates.update(directed_key)
        pairs.append(
            BaselinePair(
                master=master,
                slave=slave,
                perpendicular_baseline_m=perpendicular,
                temporal_baseline_days=temporal,
            )
        )
    if not pairs:
        raise ValueError(f"baseline network is empty: {path}")
    if len(pairs) != manifest.pair_count:
        raise ValueError(
            "baseline manifest pair_count does not match network: "
            f"{manifest.pair_count} != {len(pairs)}"
        )
    ordered_dates = tuple(sorted(dates))
    if manifest.reference_date not in dates:
        raise ValueError(
            "baseline reference date is absent from network: "
            f"{manifest.reference_date}"
        )
    return BaselineNetwork(
        manifest=manifest,
        pairs=tuple(pairs),
        dates=ordered_dates,
        perpendicular_baselines_m=_solve_perpendicular_baselines(
            tuple(pairs), ordered_dates, manifest.reference_date
        ),
    )


def plot_baseline_network(
    network: BaselineNetwork,
    output: Path,
    *,
    title: str,
    dpi: int,
    figsize: tuple[float, float],
    y_top_extra: float,
    y_bottom_extra: float,
    font_family: str,
) -> Path:
    """Draw one validated temporal–perpendicular network and publish it atomically."""

    if not isinstance(network, BaselineNetwork):
        raise TypeError("network must be BaselineNetwork")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    from geodesy_visualization.backends.matplotlib import configure_plot_font

    configure_plot_font(font_family)
    date_to_x = {
        date: mdates.date2num(datetime.strptime(date, "%Y%m%d"))
        for date in network.dates
    }
    date_to_y = dict(network.perpendicular_baselines_m)
    segments = [
        [
            (date_to_x[pair.master], date_to_y[pair.master]),
            (date_to_x[pair.slave], date_to_y[pair.slave]),
        ]
        for pair in network.pairs
    ]
    figure, axis = plt.subplots(figsize=figsize, constrained_layout=True)
    try:
        figure.patch.set_facecolor("white")
        axis.set_facecolor("#f7f8fa")
        axis.add_collection(
            LineCollection(
                segments,
                colors="#4b5563",
                linewidths=1.75,
                alpha=0.78,
                zorder=1,
            )
        )
        reference = network.manifest.reference_date
        normal = [date for date in network.dates if date != reference]
        axis.scatter(
            [date_to_x[date] for date in normal],
            [date_to_y[date] for date in normal],
            s=62,
            facecolor="#2f80ed",
            edgecolor="#1f2937",
            linewidth=0.8,
            zorder=3,
            label="SLC images",
        )
        axis.scatter(
            [date_to_x[reference]],
            [date_to_y[reference]],
            s=86,
            facecolor="#ef4444",
            edgecolor="#111827",
            linewidth=1.1,
            zorder=4,
            label=f"master SLC ({reference})",
        )
        axis.set_title(title, fontsize=15, fontweight="bold", pad=12)
        axis.set_xlabel("SLC Acquisition Date", fontsize=12, fontweight="bold")
        axis.set_ylabel("Perpendicular Baseline (m)", fontsize=12, fontweight="bold")
        axis.set_axisbelow(True)
        axis.grid(True, which="major", color="white", linewidth=1.2, zorder=0)
        axis.grid(
            True, which="minor", color="white", linewidth=0.5, alpha=0.65, zorder=0
        )
        axis.tick_params(axis="both", labelsize=10)
        axis.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=8))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        plt.setp(axis.get_xticklabels(), rotation=25, ha="right")
        xs = tuple(date_to_x.values())
        ys = tuple(date_to_y.values())
        y_span = max(ys) - min(ys)
        y_pad = max(40.0, y_span * 0.12)
        axis.set_xlim(min(xs) - 30.0, max(xs) + 30.0)
        axis.set_ylim(
            min(ys) - y_pad - y_bottom_extra,
            max(ys) + y_pad + y_top_extra,
        )
        legend = axis.legend(loc="upper left", frameon=True, framealpha=0.96)
        legend.get_frame().set_edgecolor("#d1d5db")
        destination = Path(output).expanduser().resolve()
        with atomic_output_path(destination) as temporary:
            figure.savefig(temporary, dpi=dpi, facecolor="white")
        return destination
    finally:
        plt.close(figure)


__all__ = [
    "BaselineManifest",
    "BaselineNetwork",
    "BaselinePair",
    "plot_baseline_network",
    "read_baseline_manifest",
    "read_baseline_network",
]
