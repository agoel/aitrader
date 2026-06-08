"""Run workspace layout for Macro AI Trader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RUN_SUBDIRS = (
    "config",
    "data",
    "data/ohlcv",
    "models",
    "reports",
    "agent_rsi",
    "learning",
    "rsi",  # legacy — domain tune artifacts moved to learning/
)


def expand_run_dir(run_dir: str | Path) -> Path:
    return Path(run_dir).expanduser().resolve()


def ensure_run_layout(run_dir: str | Path) -> Path:
    """Create standard run directory tree per aitrader_subagent.md."""
    root = expand_run_dir(run_dir)
    for sub in RUN_SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def update_meta(run_dir: str | Path, updates: dict[str, Any]) -> Path:
    """Merge keys into run meta.json."""
    root = ensure_run_layout(run_dir)
    meta_path = root / "meta.json"
    meta: dict[str, Any] = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
    meta.update(updates)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return meta_path
