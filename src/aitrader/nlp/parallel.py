"""Parallel helpers for embarrassingly parallel NLP workloads."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


def default_workers(requested: int | None = None) -> int:
    if requested is not None and requested > 0:
        return requested
    return min(8, os.cpu_count() or 4)


def parallel_map(
    func: Callable[[T], R],
    items: Iterable[T],
    *,
    workers: int | None = None,
    use_threads: bool = False,
) -> list[R]:
    seq = list(items)
    if not seq:
        return []
    w = min(default_workers(workers), len(seq))
    if w <= 1:
        return [func(x) for x in seq]
    executor = ThreadPoolExecutor if use_threads else ProcessPoolExecutor
    with executor(max_workers=w) as pool:
        return list(pool.map(func, seq, chunksize=max(1, len(seq) // (w * 4))))
