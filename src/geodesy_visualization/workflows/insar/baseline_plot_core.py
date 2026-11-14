"""
geodesy_visualization.workflows.insar.baseline_plot_core
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
    ``render_baseline_plot``:
        将已验证的时间—垂直基线网络原子发布为 PNG 图件。
"""

from __future__ import annotations

import json
import math
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from geodesy_visualization.io import atomic_output_path

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure


@dataclass(frozen=True)
class BaselineManifest:
    """Store one validated Analysis manifest and its resolved network path."""

    source_path: Path
    project_root: Path
    network_path: Path
    reference_date: str
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


def _calendar_tick_dates(
    lower: datetime, upper: datetime, unit: str, interval: int
) -> tuple[datetime, ...]:
    """Return globally anchored calendar ticks shared with the MATLAB backend."""

    if interval < 1:
        raise ValueError("date tick interval must be positive")
    if unit == "month":
        serial = lower.year * 12 + lower.month - 1
        first_serial = ((serial + interval - 1) // interval) * interval
        year, month_index = divmod(first_serial, 12)
        current = datetime(year, month_index + 1, 1)
        if current < lower:
            first_serial += interval
            year, month_index = divmod(first_serial, 12)
            current = datetime(year, month_index + 1, 1)
        values: list[datetime] = []
        while current <= upper:
            values.append(current)
            first_serial += interval
            year, month_index = divmod(first_serial, 12)
            current = datetime(year, month_index + 1, 1)
        return tuple(values)
    if unit == "year":
        year = ((lower.year + interval - 1) // interval) * interval
        current = datetime(year, 1, 1)
        if current < lower:
            current = datetime(year + interval, 1, 1)
        values = []
        while current <= upper:
            values.append(current)
            current = datetime(current.year + interval, 1, 1)
        return tuple(values)
    if unit == "day":
        anchor = datetime(1970, 1, 1)
        elapsed_days = (lower - anchor).total_seconds() / 86400.0
        step = math.ceil(elapsed_days / interval) * interval
        current = anchor + timedelta(days=step)
        values = []
        while current <= upper:
            values.append(current)
            current += timedelta(days=interval)
        return tuple(values)
    raise ValueError("date tick unit must be day, month, or year")


def _build_baseline_plot(
    network: BaselineNetwork,
    *,
    title: str,
    figsize: tuple[float, float],
    y_top_extra: float,
    y_bottom_extra: float,
    title_label_font_size: float,
    tick_font_size: float,
    legend_font_size: float,
    font_weight: str,
    xlabel: str,
    ylabel: str,
    date_format: str,
    date_tick_unit: str,
    date_tick_interval: int,
    date_tick_rotation: float,
    y_tick_interval: float,
    line_color: str,
    slave_color: str,
    reference_color: str,
    grid_color: str,
    show_grid: bool,
    line_label: str,
    slave_label: str,
    reference_label: str,
    font_dir: Path | None = None,
    font_family: str | None = None,
) -> tuple[Figure, Axes]:
    """Build one validated baseline figure without publishing it."""

    if not isinstance(network, BaselineNetwork):
        raise TypeError("network must be BaselineNetwork")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.ticker import FixedLocator, MultipleLocator

    from geodesy_visualization.backends.matplotlib import configure_plot_font

    selected_font = configure_plot_font(font_family, strict=True, font_dir=font_dir)
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
    figure.patch.set_facecolor("white")
    axis.set_facecolor("white")
    axis.add_collection(
        LineCollection(
            segments,
            colors=line_color,
            linewidths=2.0,
            zorder=1,
            label=line_label,
        )
    )
    reference = network.manifest.reference_date
    normal = [date for date in network.dates if date != reference]
    axis.scatter(
        [date_to_x[date] for date in normal],
        [date_to_y[date] for date in normal],
        s=100,
        facecolor=slave_color,
        edgecolor=slave_color,
        linewidth=1.5,
        zorder=3,
        label=slave_label,
    )
    axis.scatter(
        [date_to_x[reference]],
        [date_to_y[reference]],
        s=100,
        facecolor=reference_color,
        edgecolor=reference_color,
        linewidth=1.5,
        zorder=4,
        label=reference_label,
    )
    axis.set_title(
        title,
        fontsize=title_label_font_size,
        fontweight=font_weight,
        pad=12,
    )
    axis.set_xlabel(
        xlabel, fontsize=title_label_font_size, fontweight=font_weight
    )
    axis.set_ylabel(
        ylabel, fontsize=title_label_font_size, fontweight=font_weight
    )
    axis.set_axisbelow(True)
    axis.grid(
        show_grid,
        which="major",
        color=grid_color,
        linewidth=1.0,
        zorder=0,
    )
    axis.xaxis.set_major_formatter(mdates.DateFormatter(date_format))
    axis.yaxis.set_major_locator(MultipleLocator(y_tick_interval))
    axis.tick_params(
        axis="both",
        which="major",
        labelsize=tick_font_size,
        width=2.0,
        length=6.0,
        top=True,
        right=True,
        direction="in",
    )
    plt.setp(
        axis.get_xticklabels(),
        rotation=date_tick_rotation,
        ha="right" if date_tick_rotation else "center",
        fontweight=font_weight,
    )
    plt.setp(axis.get_yticklabels(), fontweight=font_weight)
    for spine in axis.spines.values():
        spine.set_linewidth(2.0)
    xs = tuple(date_to_x.values())
    ys = tuple(date_to_y.values())
    y_span = max(ys) - min(ys)
    y_pad = max(40.0, y_span * 0.12)
    x_lower = min(xs) - 30.0
    x_upper = max(xs) + 30.0
    axis.set_xlim(x_lower, x_upper)
    tick_dates = _calendar_tick_dates(
        mdates.num2date(x_lower).replace(tzinfo=None),
        mdates.num2date(x_upper).replace(tzinfo=None),
        date_tick_unit,
        date_tick_interval,
    )
    axis.xaxis.set_major_locator(
        FixedLocator([mdates.date2num(value) for value in tick_dates])
    )
    axis.set_ylim(
        min(ys) - y_pad - y_bottom_extra,
        max(ys) + y_pad + y_top_extra,
    )
    legend = axis.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        borderaxespad=0.0,
        frameon=True,
        framealpha=1.0,
        fontsize=legend_font_size,
        prop={
            "family": selected_font,
            "size": legend_font_size,
            "weight": font_weight,
        },
    )
    legend.get_frame().set_edgecolor("black")
    legend.get_frame().set_linewidth(1.5)
    return figure, axis


def render_baseline_plot(
    network: BaselineNetwork,
    output: Path,
    *,
    dpi: int,
    **validated_style: object,
) -> Path:
    """Draw one validated temporal–perpendicular network and publish it atomically."""

    import matplotlib.pyplot as plt

    figure, _ = _build_baseline_plot(network, **validated_style)
    try:
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
    "render_baseline_plot",
    "read_baseline_manifest",
    "read_baseline_network",
]
