"""
geodesy_visualization.batch
===========================

功能概述:
    提供与绘图后端无关的 CFG 列表解析和失败隔离批处理结果模型。

函数说明:
    ``BatchResult``:
        保存一个 CFG 任务的路径、返回状态和可选错误信息。
    ``BatchSummary``:
        汇总全部批处理任务及成功、失败数量。
    ``load_job_list``:
        从简单文本列表读取 CFG 路径并相对列表文件解析。
    ``run_job_batch``:
        顺序运行每个 CFG，记录失败并继续执行后续独立任务。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BatchResult:
    """Record one attempted configuration job and its visible outcome."""

    path: Path
    status: int
    error: str | None = None


@dataclass(frozen=True)
class BatchSummary:
    """Summarize all attempted jobs without hiding individual failures."""

    results: tuple[BatchResult, ...]

    @property
    def total(self) -> int:
        """Return the total number of requested jobs."""
        return len(self.results)

    @property
    def succeeded(self) -> int:
        """Return the number of jobs that returned zero status."""
        return sum(result.status == 0 for result in self.results)

    @property
    def failed(self) -> int:
        """Return the number of jobs that raised or returned non-zero status."""
        return self.total - self.succeeded

    @property
    def ok(self) -> bool:
        """Return whether every requested job succeeded."""
        return self.failed == 0


def load_job_list(path: str | Path) -> tuple[Path, ...]:
    """Load one CFG path per non-empty, non-comment line relative to the list."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"visualization job list not found: {source}")
    jobs: list[Path] = []
    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        candidate = Path(line).expanduser()
        if not candidate.is_absolute():
            candidate = source.parent / candidate
        jobs.append(candidate.resolve())
    if not jobs:
        raise ValueError(f"visualization job list contains no CFG paths: {source}")
    return tuple(jobs)


def run_job_batch(
    paths: Iterable[Path],
    runner: Callable[[Path], int | None],
) -> BatchSummary:
    """Run every path in order, isolate failures, and return a complete summary."""
    results: list[BatchResult] = []
    for path in paths:
        resolved = Path(path).expanduser().resolve()
        try:
            returned = runner(resolved)
            status = 0 if returned is None else int(returned)
            error = None if status == 0 else f"workflow returned status {status}"
        except Exception as exc:  # noqa: BLE001 - batch boundary must isolate jobs.
            status = 1
            error = f"{type(exc).__name__}: {exc}"
        results.append(BatchResult(path=resolved, status=status, error=error))
    return BatchSummary(results=tuple(results))


__all__ = ["BatchResult", "BatchSummary", "load_job_list", "run_job_batch"]
