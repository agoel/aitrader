"""Concept drift detection — Recipe — Concept drift detection."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from aitrader.nlp.keywords import (
    HORIZON_TRADING_DAYS,
    _labels_from_corpus,
    _pearson_ic,
    load_sector_etfs,
)
from aitrader.nlp.news import load_corpus
from aitrader.workspace import ensure_run_layout, update_meta

ANCHOR_TICKERS = ("SPY", "IWM")


def _parse_pub(pub: str) -> datetime:
    return datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone(timezone.utc)


def filter_corpus_by_age(
    corpus: list[dict[str, Any]],
    *,
    max_age_days: int | None = None,
    min_age_days: int | None = None,
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    out: list[dict[str, Any]] = []
    for row in corpus:
        pub = row.get("published_at")
        if not pub:
            continue
        age = (now - _parse_pub(pub)).days
        if max_age_days is not None and age > max_age_days:
            continue
        if min_age_days is not None and age < min_age_days:
            continue
        out.append(row)
    return out


def load_keyword_map(run_dir: Path, sector_id: str) -> list[dict[str, Any]]:
    path = run_dir / "models" / f"keyword_map_{sector_id}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _keyword_ic(keyword: str, labels) -> float | None:
    if len(labels) < 5:
        return None
    xs = [1.0 if keyword in a.keywords else 0.0 for a in labels]
    ys = [a.forward_return for a in labels]
    if len(set(xs)) < 2:
        return None
    return _pearson_ic(xs, ys)


def _hit_rate(keyword: str, labels) -> float | None:
    present = [a for a in labels if keyword in a.keywords]
    if not present:
        return None
    hits = sum(1 for a in present if a.forward_return > 0)
    return hits / len(present)


def _drift_score(ic_baseline: float, ic_recent: float) -> float:
    if abs(ic_baseline) < 1e-6:
        return 0.0 if abs(ic_recent) < 1e-6 else 1.0
    if ic_baseline * ic_recent < 0:
        return 1.0 - (ic_recent / ic_baseline)
    return 1.0 - (abs(ic_recent) / abs(ic_baseline))


def _evaluate_sector(
    run_dir: Path,
    sector_id: str,
    etf: str,
    corpus_recent: list[dict[str, Any]],
    corpus_baseline: list[dict[str, Any]],
    *,
    horizon_days: int,
    keyword_map: list[dict[str, Any]],
) -> dict[str, Any]:
    labels_recent = _labels_from_corpus(
        corpus_recent, sector_id, run_dir, etf, horizon_days, include_macro=True
    )
    labels_baseline = _labels_from_corpus(
        corpus_baseline, sector_id, run_dir, etf, horizon_days, include_macro=True
    )

    stored_ics = [float(k.get("ic", 0)) for k in keyword_map]
    ic_baseline_mean = (
        sum(abs(x) for x in stored_ics) / len(stored_ics) if stored_ics else 0.0
    )

    flipped: list[dict[str, Any]] = []
    recent_ics: list[float] = []
    mae_deltas: list[float] = []

    for entry in keyword_map[:25]:
        kw = entry["keyword"]
        ic_stored = float(entry.get("ic", 0))
        ic_r = _keyword_ic(kw, labels_recent)
        ic_b = _keyword_ic(kw, labels_baseline)
        if ic_r is not None:
            recent_ics.append(abs(ic_r))
        if ic_stored * (ic_r or 0) < 0 and ic_r is not None:
            flipped.append(
                {
                    "keyword": kw,
                    "stored_ic": ic_stored,
                    "recent_ic": round(ic_r, 4),
                    "stored_direction": entry.get("direction"),
                }
            )
        if ic_b is not None and ic_r is not None:
            mae_deltas.append(abs(abs(ic_b) - abs(ic_r)))

    ic_recent_mean = sum(recent_ics) / len(recent_ics) if recent_ics else 0.0
    score = _drift_score(ic_baseline_mean, ic_recent_mean)
    hit_recent = _aggregate_hit_rate(keyword_map[:10], labels_recent)

    return {
        "sector_id": sector_id,
        "etf": etf,
        "ic_baseline": round(ic_baseline_mean, 4),
        "ic_recent": round(ic_recent_mean, 4),
        "drift_score": round(score, 4),
        "hit_rate_recent": round(hit_recent, 4) if hit_recent is not None else None,
        "mae_ic_delta": round(sum(mae_deltas) / len(mae_deltas), 4) if mae_deltas else None,
        "labels_recent": len(labels_recent),
        "labels_baseline": len(labels_baseline),
        "keywords_flipped": flipped,
    }


def _aggregate_hit_rate(keyword_map: list[dict[str, Any]], labels) -> float | None:
    rates = []
    for entry in keyword_map:
        hr = _hit_rate(entry["keyword"], labels)
        if hr is not None:
            rates.append(hr)
    return sum(rates) / len(rates) if rates else None


def run_drift_detection(
    run_dir: str | Path,
    *,
    drift_threshold: float = 0.15,
    eval_window_days: int = 63,
    baseline_window_days: int = 252,
    label_horizon: str = "1m",
    require_consecutive: bool = True,
) -> tuple[Path, bool]:
    root = ensure_run_layout(run_dir)
    corpus = load_corpus(root)
    horizon_days = HORIZON_TRADING_DAYS.get(label_horizon, 21)

    corpus_recent = filter_corpus_by_age(corpus, max_age_days=eval_window_days)
    corpus_baseline = filter_corpus_by_age(
        corpus, max_age_days=baseline_window_days, min_age_days=eval_window_days
    )

    sector_etfs = load_sector_etfs(root)
    sector_etfs["anchor"] = "SPY"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows: list[dict[str, Any]] = []

    for sector_id, etf in sorted(sector_etfs.items()):
        row = _evaluate_sector(
            root,
            sector_id,
            etf,
            corpus_recent,
            corpus_baseline,
            horizon_days=horizon_days,
            keyword_map=load_keyword_map(root, sector_id),
        )
        rows.append(row)

    for ticker in ANCHOR_TICKERS:
        if ticker == "SPY" and any(r["etf"] == "SPY" for r in rows):
            continue
        row = _evaluate_sector(
            root,
            "anchor",
            ticker,
            corpus_recent,
            corpus_baseline,
            horizon_days=horizon_days,
            keyword_map=load_keyword_map(root, "anchor"),
        )
        row["sector_id"] = f"anchor_{ticker.lower()}"
        row["etf"] = ticker
        rows.append(row)

    flagged = [r for r in rows if r["drift_score"] > drift_threshold]
    refresh_recommended = len(flagged) > 0

    meta_path = root / "meta.json"
    meta: dict[str, Any] = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
    prior = meta.get("drift", {})
    streak = int(prior.get("above_threshold_streak", 0))
    if refresh_recommended:
        streak += 1
    else:
        streak = 0
    if require_consecutive and streak < 2:
        refresh_recommended = False

    report_path = root / "reports" / f"drift_{today}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Drift report — {today}",
        "",
        f"- **Eval window:** {eval_window_days} days",
        f"- **Baseline window:** {baseline_window_days} days",
        f"- **Threshold:** {drift_threshold}",
        f"- **Refresh recommended:** {refresh_recommended} (streak {streak})",
        "",
        "| Sector | ETF | IC baseline | IC recent | Drift | Hit rate |",
        "|--------|-----|-------------|-----------|-------|----------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['sector_id']} | {r['etf']} | {r['ic_baseline']} | {r['ic_recent']} | "
            f"{r['drift_score']} | {r.get('hit_rate_recent', '—')} |"
        )
    lines.append("")
    lines.append("## Keyword stability (sign flips)")
    for r in rows:
        if r["keywords_flipped"]:
            lines.append(f"### {r['sector_id']}")
            for flip in r["keywords_flipped"][:5]:
                lines.append(
                    f"- `{flip['keyword']}`: stored {flip['stored_ic']} → recent {flip['recent_ic']}"
                )
    report_path.write_text("\n".join(lines) + "\n")

    update_meta(
        root,
        {
            "drift": {
                "last_run": today,
                "refresh_recommended": refresh_recommended,
                "above_threshold_streak": streak,
                "flagged_sectors": [r["sector_id"] for r in flagged],
            },
        },
    )
    return report_path, refresh_recommended
