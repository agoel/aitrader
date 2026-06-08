"""Human-readable progress for long-running pipelines."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class PipelineStatus:
    pipeline: str
    phase: str
    step: int
    steps_total: int
    items_done: int = 0
    items_total: int = 0
    message: str = ""
    status: str = "running"  # running | done | error
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def step_pct(self) -> float:
        if self.steps_total <= 0:
            return 100.0
        return 100.0 * self.step / self.steps_total

    @property
    def items_pct(self) -> float:
        if self.items_total <= 0:
            return 0.0
        return 100.0 * self.items_done / self.items_total

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["step_pct"] = round(self.step_pct, 1)
        d["items_pct"] = round(self.items_pct, 1)
        return d


def status_path(run_dir: Path) -> Path:
    return run_dir / "reports" / "pipeline_status.json"


def write_status(run_dir: Path | str, status: PipelineStatus) -> Path:
    root = Path(run_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "reports").mkdir(parents=True, exist_ok=True)
    status.updated_at = datetime.now(timezone.utc).isoformat()
    path = status_path(root)
    path.write_text(json.dumps(status.to_dict(), indent=2) + "\n")
    return path


def _emit(line: str, *, quiet: bool) -> None:
    if not quiet:
        print(line, flush=True)


class RunProgress:
    """Item-level counter with stdout + optional status file updates."""

    def __init__(
        self,
        label: str,
        total: int,
        *,
        run_dir: Path | str | None = None,
        pipeline: str = "",
        phase: str = "",
        step: int = 1,
        steps_total: int = 1,
        quiet: bool = False,
        every: int = 1,
    ) -> None:
        self.label = label
        self.total = max(0, total)
        self.done = 0
        self.run_dir = Path(run_dir).expanduser().resolve() if run_dir else None
        self.pipeline = pipeline
        self.phase = phase
        self.step = step
        self.steps_total = steps_total
        self.quiet = quiet
        self.every = max(1, every)
        self._last_print = 0

    def start(self, message: str = "") -> None:
        self._tick(0, message=message or f"starting {self.label}", force=True)

    def advance(self, n: int = 1, *, message: str = "") -> None:
        self.done = min(self.total, self.done + n) if self.total else self.done + n
        self._tick(n, message=message)

    def _tick(self, n: int, *, message: str = "", force: bool = False) -> None:
        if self.total:
            pct = 100.0 * self.done / self.total
            left = self.total - self.done
            line = f"[{self.label}] {self.done}/{self.total} ({pct:.0f}%) — {left} left"
        else:
            line = f"[{self.label}] {self.done} done"
        if message:
            line += f" — {message}"
        should_print = force or n >= self.every or self.done >= self.total
        if should_print and (force or self.done - self._last_print >= self.every or self.done >= self.total):
            _emit(line, quiet=self.quiet)
            self._last_print = self.done
        if self.run_dir is not None:
            write_status(
                self.run_dir,
                PipelineStatus(
                    pipeline=self.pipeline,
                    phase=self.phase or self.label,
                    step=self.step,
                    steps_total=self.steps_total,
                    items_done=self.done,
                    items_total=self.total,
                    message=message,
                    status="running",
                ),
            )

    def finish(self, message: str = "complete") -> None:
        if self.total:
            self.done = self.total
        self._tick(0, message=message, force=True)
        if self.run_dir is not None:
            write_status(
                self.run_dir,
                PipelineStatus(
                    pipeline=self.pipeline,
                    phase=self.phase or self.label,
                    step=self.step,
                    steps_total=self.steps_total,
                    items_done=self.done,
                    items_total=self.total,
                    message=message,
                    status="done",
                ),
            )


@contextmanager
def pipeline_phase(
    run_dir: Path | str,
    pipeline: str,
    phase: str,
    step: int,
    steps_total: int,
    *,
    quiet: bool = False,
):
    """Mark a pipeline step start/end in status file and stdout."""
    root = Path(run_dir).expanduser().resolve()
    _emit(f"\n== {pipeline} step {step}/{steps_total}: {phase} ==", quiet=quiet)
    write_status(
        root,
        PipelineStatus(
            pipeline=pipeline,
            phase=phase,
            step=step,
            steps_total=steps_total,
            message="started",
            status="running",
        ),
    )
    try:
        yield
        write_status(
            root,
            PipelineStatus(
                pipeline=pipeline,
                phase=phase,
                step=step,
                steps_total=steps_total,
                message="complete",
                status="done",
            ),
        )
        _emit(f"== {phase} complete ==\n", quiet=quiet)
    except Exception as exc:
        write_status(
            root,
            PipelineStatus(
                pipeline=pipeline,
                phase=phase,
                step=step,
                steps_total=steps_total,
                message=str(exc)[:200],
                status="error",
            ),
        )
        raise


def parallel_map_progress(
    func: Callable[[T], R],
    items: Iterable[T],
    progress: RunProgress,
    *,
    workers: int | None = None,
    use_threads: bool = False,
) -> list[R]:
    """Like parallel_map but advances progress as each item completes."""
    from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

    from aitrader.nlp.parallel import default_workers

    seq = list(items)
    if not seq:
        return []
    w = min(default_workers(workers), len(seq))
    progress.start(f"{len(seq)} items, {w} workers")
    if w <= 1:
        out: list[R] = []
        for x in seq:
            out.append(func(x))
            progress.advance(1)
        progress.finish()
        return out

    executor = ThreadPoolExecutor if use_threads else ProcessPoolExecutor
    results: list[R | None] = [None] * len(seq)
    with executor(max_workers=w) as pool:
        futures = {pool.submit(func, x): i for i, x in enumerate(seq)}
        for fut in as_completed(futures):
            idx = futures[fut]
            results[idx] = fut.result()
            progress.advance(1)
    progress.finish()
    return [r for r in results if r is not None]  # type: ignore[misc]
