"""Agent-brain RSI — performance probes and improvement logs (not domain self-learning)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aitrader.ml.backtest import (
    _build_macro_event_features,
    _build_monthly_spy_features,
)
from aitrader.nlp.keyword_cache import load_keyword_cache
from aitrader.nlp.keywords import HORIZON_TRADING_DAYS
from aitrader.workspace import ensure_run_layout, update_meta

DEFAULT_SLICE_MONTHS = 3
DEFAULT_SLICE_MACRO_DAYS = 10
DEFAULT_SLICE_BUDGET_SEC = 60.0
DEFAULT_FULL_MONTHS = 48
DEFAULT_FULL_MACRO_DAYS = 374


def agent_rsi_dir(run_dir: str | Path) -> Path:
    root = ensure_run_layout(run_dir)
    path = root / "agent_rsi"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_agent_rsi(
    run_dir: str | Path,
    topic: str,
    *,
    symptom: str,
    fix: str,
    verify: str = "",
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Append an agent-brain improvement entry under agent_rsi/."""
    root = ensure_run_layout(run_dir)
    out_dir = agent_rsi_dir(root)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = topic.replace(" ", "_").lower()[:40]
    path = out_dir / f"{today}_{slug}.md"
    body = [
        f"# Agent RSI — {topic}",
        "",
        f"**Date:** {today}",
        "",
        "## Symptom",
        symptom,
        "",
        "## Fix (agent brain)",
        fix,
        "",
    ]
    if verify:
        body.extend(["## Verify", verify, ""])
    if metadata:
        body.extend(["## Metadata", "```json", json.dumps(metadata, indent=2), "```", ""])
    path.write_text("\n".join(body) + "\n")

    manifest_path = out_dir / "manifest.json"
    manifest: list[dict[str, Any]] = []
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    manifest.append(
        {
            "date": today,
            "topic": topic,
            "path": str(path.relative_to(root)),
            "symptom": symptom[:200],
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    update_meta(root, {"agent_rsi": {"last_entry": str(path.relative_to(root)), "entries": len(manifest)}})
    return path


def probe_backtest_performance(
    run_dir: str | Path,
    *,
    slice_months: int = DEFAULT_SLICE_MONTHS,
    slice_macro_days: int = DEFAULT_SLICE_MACRO_DAYS,
    budget_sec: float = DEFAULT_SLICE_BUDGET_SEC,
    news_window_days: int = 30,
    full_months: int = DEFAULT_FULL_MONTHS,
    full_macro_days: int = DEFAULT_FULL_MACRO_DAYS,
    quiet: bool = False,
) -> dict[str, Any]:
    """
    Slice-first gate for backtest/tune — profile small slice, extrapolate, log to agent_rsi/.
    """
    root = ensure_run_layout(run_dir)
    llm = load_keyword_cache(root)
    horizon_days = HORIZON_TRADING_DAYS.get("1m", 21)

    t0 = time.perf_counter()
    monthly = _build_monthly_spy_features(
        root,
        horizon_days,
        llm_cache=llm,
        news_window_days=news_window_days,
        max_months=slice_months,
        pipeline="agent_rsi.probe",
        quiet=quiet,
    )
    monthly_sec = time.perf_counter() - t0

    t1 = time.perf_counter()
    macro_rows = _build_macro_event_features(
        root,
        horizon_days,
        llm_cache=llm,
        pipeline="agent_rsi.probe",
        quiet=quiet,
        max_trading_days=slice_macro_days,
    )
    macro_sec = time.perf_counter() - t1
    probe_total = monthly_sec + macro_sec

    month_scale = full_months / max(slice_months, 1)
    macro_scale = full_macro_days / max(slice_macro_days, 1)
    est_monthly = monthly_sec * month_scale
    est_macro = macro_sec * macro_scale
    est_total = est_monthly + est_macro

    ok = probe_total <= budget_sec and est_total <= budget_sec * 8

    report = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "probe_sec": round(probe_total, 2),
        "monthly_features_sec": round(monthly_sec, 2),
        "macro_features_sec": round(macro_sec, 2),
        "slice_months": slice_months,
        "slice_macro_days": slice_macro_days,
        "budget_sec": budget_sec,
        "extrapolated_full_sec": round(est_total, 1),
        "extrapolated_monthly_sec": round(est_monthly, 1),
        "extrapolated_macro_sec": round(est_macro, 1),
        "passes_gate": ok,
        "monthly_rows": len(monthly[1]) if monthly else 0,
        "macro_rows": len(macro_rows),
    }

    lines = [
        f"# Backtest perf probe — {report['date']}",
        "",
        f"- **Probe time:** {report['probe_sec']}s (budget {budget_sec}s)",
        f"- **Monthly features ({slice_months} mo):** {report['monthly_features_sec']}s",
        f"- **Macro features ({slice_macro_days} days):** {report['macro_features_sec']}s",
        f"- **Extrapolated full run:** ~{report['extrapolated_full_sec']}s "
        f"({full_months} mo + ~{full_macro_days} macro days)",
        f"- **Gate:** {'PASS' if ok else 'FAIL — fix hot path before full batch'}",
        "",
        "```json",
        json.dumps(report, indent=2),
        "```",
        "",
    ]
    out = agent_rsi_dir(root) / f"{report['date']}_backtest_probe.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    (agent_rsi_dir(root) / f"{report['date']}_backtest_probe.md").write_text("\n".join(lines) + "\n")

    if not quiet:
        status = "PASS" if ok else "FAIL"
        print(
            f"[agent-rsi probe] {status} probe={report['probe_sec']}s "
            f"extrapolated≈{report['extrapolated_full_sec']}s",
            flush=True,
        )
    return report


def seed_session_improvements(run_dir: str | Path) -> list[Path]:
    """Document shipped agent-brain fixes from the performance pass (idempotent topics)."""
    entries = [
        (
            "parallel_keywords",
            "Keyword fill single-threaded; 22k articles stalled",
            "Parallel workers in fill_pending_keywords (--workers 8); RunProgress on batches",
            "keywords discover completes with visible progress",
        ),
        (
            "backtest_cluster_cache",
            "Per-month _sector_return_profiles ~17s×48mo",
            "Reuse news_clusters.pkl sector_profiles in _cluster_context_pit",
            "48-month feature build <20s on active run",
        ),
        (
            "macro_per_day",
            "Macro event study looped 21k articles ~2h",
            "One row per trading day; merge event tags per day",
            "374 macro days in ~2min",
        ),
        (
            "backtest_feature_cache",
            "RSI/tune re-built features every config round",
            "BacktestFeatureCache: build once, score many configs",
            "185-config tune ~2min",
        ),
        (
            "slice_first_gate",
            "Full batch launched before profiling",
            "Recipe — Slice-first performance gate + agent_rsi probe CLI",
            "probe_backtest_performance under 60s on slice",
        ),
    ]
    written: list[Path] = []
    out_dir = agent_rsi_dir(run_dir)
    for topic, symptom, fix, verify in entries:
        marker = out_dir / f"seed_{topic}.marker"
        if marker.exists():
            continue
        path = log_agent_rsi(run_dir, topic, symptom=symptom, fix=fix, verify=verify)
        marker.write_text(path.name + "\n")
        written.append(path)
    return written
