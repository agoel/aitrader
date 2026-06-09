"""Proxy tests A3 / B2 / D — decide if graph/adversarial complexity is worth building."""

from __future__ import annotations

import json
import re
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from aitrader.ml.backtest import (
    BACKTEST_SIGNAL_MAX_ARTICLES,
    _corpus_before,
    _corpus_timeline,
    _keyword_coef_map,
    _macro_events,
    _macro_events_from_text,
    _signal_from_articles,
)
from aitrader.ml.drift import load_keyword_map
from aitrader.nlp.keyword_cache import keywords_for_article, load_keyword_cache
from aitrader.nlp.keywords import (
    HORIZON_TRADING_DAYS,
    MACRO_SEEDS,
    _pearson_ic,
    _vader_sentiment,
    forward_return_at,
    load_etf_closes,
)
from aitrader.nlp.stoplist import KEYWORD_STOPLIST, filter_coef_map

EVENT_TAGS = ("fed", "inflation", "employment", "earnings", "tariff")


def _hit_rate(pred: list[float], real: list[float]) -> float:
    if not pred:
        return 0.0
    return float(sum((p > 0) == (r > 0) for p, r in zip(pred, real)) / len(pred))


def _ic_row(name: str, x: list[float], y: list[float]) -> dict[str, Any]:
    if len(x) < 5:
        return {"signal": name, "ic": None, "hit_rate": None, "n": len(x)}
    return {
        "signal": name,
        "ic": round(_pearson_ic(x, y), 4),
        "hit_rate": round(_hit_rate(x, y), 4),
        "n": len(x),
        "mean": round(float(np.mean(x)), 4),
    }


def _keyword_score_filtered(
    articles: list[dict[str, Any]],
    coef_map: dict[str, float],
    llm_cache: dict[str, Any] | None,
    *,
    stoplist: frozenset[str] | None = None,
) -> float:
    if stoplist:
        filtered_coef = filter_coef_map(
            {k: v for k, v in coef_map.items() if k.lower() not in stoplist}
        )
    else:
        filtered_coef = coef_map
    score, _, _, _ = _signal_from_articles(
        articles,
        filtered_coef,
        llm_cache,
        max_articles=BACKTEST_SIGNAL_MAX_ARTICLES,
        run_dir=None,
    )
    return score


def _article_events(art: dict[str, Any], llm_cache: dict[str, Any] | None) -> set[str]:
    text = f"{art.get('title', '')} {art.get('body', '')}"
    tags = set(_macro_events(keywords_for_article(art, llm_cache) or []))
    tags.update(_macro_events_from_text(text))
    return tags


def _event_bucket_sentiment(
    articles: list[dict[str, Any]],
    llm_cache: dict[str, Any] | None,
    *,
    score_fn,
) -> float:
    """B2: median sentiment per event tag, equal-weight across active tags."""
    by_event: dict[str, list[float]] = defaultdict(list)
    for art in articles:
        if not keywords_for_article(art, llm_cache):
            continue
        text = f"{art.get('title', '')} {art.get('body', '')}"
        s = score_fn(text)
        for tag in _article_events(art, llm_cache):
            if tag in EVENT_TAGS:
                by_event[tag].append(s)
    if not by_event:
        return 0.0
    medians = [float(np.median(v)) for v in by_event.values()]
    return float(np.mean(medians))


def _trimmed_mean(values: list[float], trim: float = 0.1) -> float:
    if not values:
        return 0.0
    arr = sorted(values)
    k = int(len(arr) * trim)
    if k > 0 and len(arr) > 2 * k:
        arr = arr[k:-k]
    return float(np.mean(arr))


def _load_finbert():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from transformers import pipeline

    return pipeline(
        "sentiment-analysis",
        model="ProsusAI/finbert",
        tokenizer="ProsusAI/finbert",
        truncation=True,
        max_length=512,
        device=-1,
    )


def _finbert_score(pipe, text: str) -> float:
    text = text[:512]
    if len(text) < 20:
        return 0.0
    r = pipe(text)[0]
    lab = r["label"].lower()
    s = float(r["score"])
    if lab == "positive":
        return s
    if lab == "negative":
        return -s
    return 0.0


def run_proxy_benchmark(
    run_dir: str | Path,
    *,
    max_months: int = 46,
    news_window_days: int = 30,
    use_finbert: bool = True,
    finbert_article_cap: int = 80,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    root = Path(run_dir).expanduser()
    corpus = __import__("aitrader.nlp.news", fromlist=["load_corpus"]).load_corpus(root)
    llm = load_keyword_cache(root)
    spy = load_etf_closes(root, "SPY")
    coef = _keyword_coef_map(load_keyword_map(root, "anchor"))
    horizon = HORIZON_TRADING_DAYS["1m"]
    timeline = _corpus_timeline(corpus)

    month_ends = (
        spy.index.to_series().groupby(spy.index.to_period("M")).max().sort_values().tail(max_months)
    )

    finbert_pipe = _load_finbert() if use_finbert else None
    finbert_cache: dict[str, float] = {}

    def finbert_fn(text: str, art_id: str | None = None) -> float:
        if art_id and art_id in finbert_cache:
            return finbert_cache[art_id]
        s = _finbert_score(finbert_pipe, text)
        if art_id:
            finbert_cache[art_id] = s
        return s

    rows: list[dict[str, Any]] = []
    for as_of in month_ends:
        if as_of not in spy.index:
            continue
        idx = spy.index.get_loc(as_of)
        if idx + horizon >= len(spy):
            continue
        realized, _ = forward_return_at(spy, as_of, horizon)
        if realized is None:
            continue

        pub_cutoff = as_of.to_pydatetime().replace(tzinfo=timezone.utc)
        window = _corpus_before(
            corpus, pub_cutoff, window_days=news_window_days, timeline=timeline
        )
        arts_scored = sorted(window, key=lambda a: a.get("published_at", ""))[
            -BACKTEST_SIGNAL_MAX_ARTICLES:
        ]

        vader_scores = []
        macro_vader = []
        for art in arts_scored:
            kws = keywords_for_article(art, llm)
            if not kws:
                continue
            text = f"{art.get('title', '')} {art.get('body', '')}"
            v = _vader_sentiment(text)
            vader_scores.append(v)
            if any(s in " ".join(kws).lower() for s in MACRO_SEEDS):
                macro_vader.append(v)

        kw_base, sent_feat, _, vader_mean_feat = _signal_from_articles(
            window,
            coef,
            llm,
            max_articles=BACKTEST_SIGNAL_MAX_ARTICLES,
            run_dir=root,
        )
        kw_a3 = _keyword_score_filtered(
            window, coef, llm, stoplist=KEYWORD_STOPLIST
        )
        b2_vader = _event_bucket_sentiment(window, llm, score_fn=_vader_sentiment)

        finbert_month = np.nan
        b2_finbert = np.nan
        if finbert_pipe:
            fb_scores = []
            n_fb = 0
            for art in arts_scored:
                if n_fb >= finbert_article_cap:
                    break
                kws = keywords_for_article(art, llm)
                if not kws:
                    continue
                text = f"{art.get('title', '')} {art.get('body', '')}"
                fb_scores.append(finbert_fn(text, art.get("id")))
                n_fb += 1
            if fb_scores:
                finbert_month = float(np.mean(fb_scores))
            b2_finbert = _event_bucket_sentiment(
                window,
                llm,
                score_fn=lambda t: finbert_fn(t),  # no art id in lambda path for events
            )

        rows.append(
            {
                "trading_day": as_of,
                "realized": realized,
                "baseline_keyword_score": kw_base,
                "a3_keyword_stoplist": kw_a3,
                "baseline_vader_mean": float(np.mean(vader_scores)) if vader_scores else 0.0,
                "a1_macro_vader": float(np.mean(macro_vader)) if macro_vader else np.nan,
                "a2_trimmed_vader": _trimmed_mean(vader_scores),
                "b2_event_bucket_vader": b2_vader,
                "d_finbert_mean": finbert_month,
                "b2_event_bucket_finbert": b2_finbert,
                "news_n": len(window),
            }
        )

    df = pd.DataFrame(rows)
    y = df["realized"].tolist()
    summary = {
        "run_dir": str(root),
        "months": len(df),
        "finbert_articles_scored": len(finbert_cache),
        "phase0_baseline": {
            "keyword_score_ic": -0.062,
            "vader_mean_ic": -0.040,
            "macro_vader_ic": 0.082,
            "walkforward_ic": 0.1043,
        },
        "results": [],
        "decision": {},
    }

    signals = [
        ("baseline_keyword_score", "Baseline keyword_score"),
        ("a3_keyword_stoplist", "A3 keyword + stoplist"),
        ("baseline_vader_mean", "Baseline VADER mean"),
        ("a1_macro_vader", "A1 macro-filter VADER"),
        ("a2_trimmed_vader", "A2 trimmed VADER"),
        ("b2_event_bucket_vader", "B2 event-bucket VADER"),
        ("d_finbert_mean", "D FinBERT mean"),
        ("b2_event_bucket_finbert", "B2 event-bucket FinBERT"),
    ]
    for col, label in signals:
        sub = df.dropna(subset=[col])
        if len(sub) < 5:
            continue
        row = _ic_row(label, sub[col].tolist(), sub["realized"].tolist())
        row["column"] = col
        summary["results"].append(row)

    def _get_ic(label: str) -> float | None:
        for r in summary["results"]:
            if r["signal"] == label:
                return r.get("ic")
        return None

    a3_ic = _get_ic("A3 keyword + stoplist")
    base_kw_ic = _get_ic("Baseline keyword_score")
    b2_ic = _get_ic("B2 event-bucket VADER")
    base_v_ic = _get_ic("Baseline VADER mean")
    d_ic = _get_ic("D FinBERT mean")
    a1_ic = _get_ic("A1 macro-filter VADER")

    summary["decision"] = {
        "phase1_worth_it": a3_ic is not None
        and base_kw_ic is not None
        and a3_ic > base_kw_ic + 0.005,
        "graph_proxy_worth_it": b2_ic is not None
        and base_v_ic is not None
        and b2_ic > base_v_ic + 0.02,
        "finbert_worth_it": d_ic is not None
        and base_v_ic is not None
        and d_ic > base_v_ic + 0.03,
        "simple_macro_filter_enough": a1_ic is not None and a1_ic >= 0.08,
        "recommendation": "",
    }
    rec = []
    if summary["decision"]["phase1_worth_it"]:
        rec.append("Ship Phase 1 (stoplist + discover gates)")
    if summary["decision"]["simple_macro_filter_enough"]:
        rec.append("Try macro-only aggregation before graph")
    if summary["decision"]["finbert_worth_it"]:
        rec.append("Ship Phase 3 FinBERT")
    elif d_ic is not None and base_v_ic is not None and d_ic > base_v_ic:
        rec.append("FinBERT marginal — consider after Phase 1")
    if summary["decision"]["graph_proxy_worth_it"]:
        rec.append("Build Phase 2b graph coarsen-refine")
    else:
        rec.append("Skip graph for now — bucket proxy did not beat +0.02 IC")
    if not summary["decision"]["phase1_worth_it"] and not summary["decision"]["graph_proxy_worth_it"]:
        rec.append("Skip adversarial until aggregation/phrase IC moves")
    summary["decision"]["recommendation"] = "; ".join(rec)

    return df, summary


def write_proxy_report(run_dir: str | Path, df: pd.DataFrame, summary: dict[str, Any]) -> Path:
    root = Path(run_dir).expanduser()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    csv_path = root / "reports" / f"sentiment_proxy_benchmark_{today}.csv"
    json_path = root / "reports" / f"sentiment_proxy_benchmark_{today}.json"
    md_path = root / "reports" / f"sentiment_proxy_benchmark_{today}.md"
    df.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(summary, indent=2) + "\n")

    lines = [
        f"# Sentiment proxy benchmark — {today}",
        "",
        f"**Months:** {summary['months']} | **FinBERT articles cached:** {summary.get('finbert_articles_scored', 0)}",
        "",
        "## IC vs SPY 1m realized (Phase 0 baselines in parentheses)",
        "",
        "| Signal | IC | Hit rate | n | vs baseline |",
        "|--------|-----|----------|---|-------------|",
    ]
    p0 = summary["phase0_baseline"]
    for r in summary["results"]:
        note = ""
        if "keyword" in r["signal"] and "Baseline" in r["signal"]:
            note = f" (was {p0['keyword_score_ic']:+.3f})"
        elif r["signal"] == "Baseline VADER mean":
            note = f" (was {p0['vader_mean_ic']:+.3f})"
        elif r["signal"] == "A1 macro-filter VADER":
            note = f" (was {p0['macro_vader_ic']:+.3f})"
        lines.append(
            f"| {r['signal']} | {r['ic']:+.4f} | {r['hit_rate']:.3f} | {r['n']} | {note} |"
        )
    lines.extend(
        [
            "",
            "## Decision gates",
            "",
            f"- **Phase 1 (A3 stoplist):** {summary['decision']['phase1_worth_it']}",
            f"- **Graph proxy (B2 buckets):** {summary['decision']['graph_proxy_worth_it']}",
            f"- **FinBERT (D):** {summary['decision']['finbert_worth_it']}",
            f"- **Macro filter enough:** {summary['decision']['simple_macro_filter_enough']}",
            "",
            f"**Recommendation:** {summary['decision']['recommendation']}",
            "",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n")
    return md_path
