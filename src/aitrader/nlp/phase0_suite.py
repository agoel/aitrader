"""Phase 0 closure — frozen baselines, audit, sentiment benchmark, guardrail backtest."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from aitrader.ml.backtest import run_prediction_backtest
from aitrader.ml.drift import load_keyword_map
from aitrader.ml.sentiment_proxy_benchmark import run_proxy_benchmark, write_proxy_report
from aitrader.nlp.keywords import MACRO_SEEDS, _pearson_ic
from aitrader.nlp.stoplist import is_stoplisted
from aitrader.workspace import ensure_run_layout

# Frozen Phase 0 measurements (2026-06-08, pre-hygiene)
PHASE0_FROZEN: dict[str, Any] = {
    "junk_in_anchor_top50": 11,
    "keyword_score_ic": -0.062,
    "vader_mean_ic": -0.040,
    "macro_vader_ic": 0.082,
    "walkforward_ic": 0.1043,
    "walkforward_hit_rate": 0.5564,
}

# Post-Phase-1 guardrails (must not regress)
def _fmt_ic(v: float | None) -> str:
    return f"{v:+.4f}" if v is not None else "n/a"


def _fmt_pct(v: float | None) -> str:
    return f"{v:.1%}" if v is not None else "n/a"


PHASE1_GUARDRAILS: dict[str, Any] = {
    "junk_in_anchor_top50_max": 0,
    "keyword_score_ic_min": 0.0,
    "walkforward_ic_min": 0.094,  # allow 0.01 slip from 0.1043
    "walkforward_hit_rate_min": 0.546,
}


def _map_for_audit(run_dir: Path) -> list[dict[str, Any]]:
    for sid in ("market", "anchor"):
        rows = load_keyword_map(run_dir, sid)
        if rows:
            return rows
    return []


def run_keyword_audit(run_dir: str | Path) -> dict[str, Any]:
    """Junk count, top phrases, macro-tagged share in anchor/market map."""
    root = ensure_run_layout(run_dir)
    rows = _map_for_audit(root)
    sorted_rows = sorted(rows, key=lambda r: abs(float(r.get("ic", 0))), reverse=True)
    top50 = sorted_rows[:50]
    junk = [r for r in top50 if is_stoplisted(str(r.get("keyword", "")))]
    macro_hits = 0
    for r in top50:
        kw = str(r.get("keyword", "")).lower()
        if any(s in kw.split() for s in MACRO_SEEDS) or kw in MACRO_SEEDS:
            macro_hits += 1
    return {
        "map_rows": len(rows),
        "top50_junk_count": len(junk),
        "top50_junk_phrases": [r["keyword"] for r in junk],
        "top50_macro_tagged_pct": round(macro_hits / max(len(top50), 1), 4),
        "top20": [
            {
                "keyword": r["keyword"],
                "ic": r.get("ic"),
                "support": r.get("support"),
            }
            for r in sorted_rows[:20]
        ],
    }


def run_benchmark_sentiment(
    run_dir: str | Path,
    *,
    max_months: int = 46,
    skip_finbert: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any], Path]:
    root = ensure_run_layout(run_dir)
    df, summary = run_proxy_benchmark(
        root, max_months=max_months, use_finbert=not skip_finbert
    )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    csv_path = root / "reports" / f"sentiment_benchmark_{today}.csv"
    df.to_csv(csv_path, index=False)
    summary["benchmark_csv"] = str(csv_path)
    write_proxy_report(root, df, summary)
    return df, summary, csv_path


def _metric_from_backtest_summary(run_dir: Path) -> dict[str, float | None]:
    reports = sorted((run_dir / "reports").glob("backtest_summary_*.csv"))
    if not reports:
        return {"walkforward_ic": None, "walkforward_hit_rate": None}
    df = pd.read_csv(reports[-1])
    label_col = "slice" if "slice" in df.columns else "label"
    overall = df[df[label_col] == "overall_1m"]
    if overall.empty:
        return {"walkforward_ic": None, "walkforward_hit_rate": None}
    row = overall.iloc[0]
    return {
        "walkforward_ic": float(row["ic"]),
        "walkforward_hit_rate": float(row["hit_rate"]),
    }


def run_phase0_close(
    run_dir: str | Path,
    *,
    max_months: int = 46,
    news_window_days: int = 30,
    skip_backtest: bool = False,
    skip_finbert: bool = True,
    quiet: bool = False,
) -> Path:
    """Audit + sentiment benchmark + walk-forward guardrail → closure report."""
    root = ensure_run_layout(run_dir)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    audit = run_keyword_audit(root)
    _, bench_summary, bench_csv = run_benchmark_sentiment(
        root, max_months=max_months, skip_finbert=skip_finbert
    )

    backtest_paths: dict[str, str] = {}
    if not skip_backtest:
        csv_p, report_p = run_prediction_backtest(
            root,
            news_window_days=news_window_days,
            quiet=quiet,
            run_probe=True,
        )
        backtest_paths = {"csv": str(csv_p), "report": str(report_p)}

    wf = _metric_from_backtest_summary(root)

    def _bench_ic(label: str) -> float | None:
        for r in bench_summary.get("results", []):
            if r.get("signal") == label:
                return r.get("ic")
        return None

    current = {
        "junk_in_anchor_top50": audit["top50_junk_count"],
        "keyword_score_ic": _bench_ic("Baseline keyword_score"),
        "vader_mean_ic": _bench_ic("Baseline VADER mean"),
        "macro_vader_ic": _bench_ic("A1 macro-filter VADER"),
        "walkforward_ic": wf.get("walkforward_ic"),
        "walkforward_hit_rate": wf.get("walkforward_hit_rate"),
    }

    checks = {
        "junk_ok": audit["top50_junk_count"] <= PHASE1_GUARDRAILS["junk_in_anchor_top50_max"],
        "keyword_ic_ok": (
            current["keyword_score_ic"] is not None
            and current["keyword_score_ic"] >= PHASE1_GUARDRAILS["keyword_score_ic_min"]
        ),
        "walkforward_ic_ok": (
            current["walkforward_ic"] is not None
            and current["walkforward_ic"] >= PHASE1_GUARDRAILS["walkforward_ic_min"]
        ),
        "walkforward_hit_ok": (
            current["walkforward_hit_rate"] is not None
            and current["walkforward_hit_rate"] >= PHASE1_GUARDRAILS["walkforward_hit_rate_min"]
        ),
    }
    # Hit rate is advisory — IC is the primary Phase 0→1 guardrail
    checks["phase0_suite_closed"] = (
        checks["junk_ok"] and checks["keyword_ic_ok"] and checks["walkforward_ic_ok"]
    )

    payload = {
        "date": today,
        "phase0_frozen": PHASE0_FROZEN,
        "phase1_guardrails": PHASE1_GUARDRAILS,
        "current": current,
        "audit": audit,
        "benchmark_summary": bench_summary,
        "backtest": backtest_paths,
        "checks": checks,
    }

    json_path = root / "reports" / f"phase0_closure_{today}.json"
    json_path.write_text(json.dumps(payload, indent=2) + "\n")

    lines = [
        f"# Phase 0 closure — {today}",
        "",
        f"**Suite closed:** {checks['phase0_suite_closed']}",
        "",
        f"*Hit rate guardrail (advisory):* {checks['walkforward_hit_ok']}",
        "",
        "## Frozen Phase 0 vs current",
        "",
        "| Metric | Phase 0 frozen | Current | Guardrail | Pass |",
        "|--------|----------------|---------|-----------|------|",
        f"| Junk in top-50 | {PHASE0_FROZEN['junk_in_anchor_top50']} | {current['junk_in_anchor_top50']} | ≤ {PHASE1_GUARDRAILS['junk_in_anchor_top50_max']} | {checks['junk_ok']} |",
        f"| keyword_score IC | {PHASE0_FROZEN['keyword_score_ic']:+.3f} | {_fmt_ic(current['keyword_score_ic'])} | ≥ {PHASE1_GUARDRAILS['keyword_score_ic_min']} | {checks['keyword_ic_ok']} |",
        f"| Walk-forward IC | {PHASE0_FROZEN['walkforward_ic']:+.4f} | {_fmt_ic(current['walkforward_ic'])} | ≥ {PHASE1_GUARDRAILS['walkforward_ic_min']} | {checks['walkforward_ic_ok']} |",
        f"| Walk-forward hit | {PHASE0_FROZEN['walkforward_hit_rate']:.1%} | {_fmt_pct(current['walkforward_hit_rate'])} | ≥ {PHASE1_GUARDRAILS['walkforward_hit_rate_min']:.1%} | {checks['walkforward_hit_ok']} |",
        "",
        "## Artifacts",
        "",
        f"- `{bench_csv.name}` — monthly sentiment IC harness",
        f"- `{json_path.name}` — full closure JSON",
    ]
    if backtest_paths:
        lines.append(f"- Backtest: `{Path(backtest_paths['report']).name}`")

    md_path = root / "reports" / f"phase0_closure_{today}.md"
    md_path.write_text("\n".join(lines) + "\n")
    return md_path
