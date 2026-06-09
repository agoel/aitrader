"""Option-expiry range study — model confidence bands vs SPY at monthly expiry."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from aitrader.data.cot import cot_signal_at, ensure_cot_data
from aitrader.ml.backtest import (
    BACKTEST_SIGNAL_MAX_ARTICLES,
    _anchor_cluster_prior,
    _assign_clusters,
    _cluster_context_pit,
    _corpus_before,
    _corpus_timeline,
    _keyword_coef_map,
    _load_cluster_model,
    _macro_events,
    _macro_events_from_text,
    _score_monthly_spy_from_features,
    _train_horizon_model,
    build_backtest_feature_cache,
)
from aitrader.ml.drift import load_keyword_map
from aitrader.ml.predict import _momentum_at, _predict_from_features, _signal_from_articles
from aitrader.ml.predict_config import PredictTuneConfig, load_predict_config
from aitrader.ml.strategy_signals import blend_predicted_return
from aitrader.nlp.keyword_cache import keywords_for_article, load_keyword_cache
from aitrader.nlp.keywords import HORIZON_TRADING_DAYS, load_etf_closes
from aitrader.nlp.news import load_corpus
from aitrader.workspace import ensure_run_layout

SPX_PER_SPY = 10.0
DEFAULT_PUT_BUFFER_PCTS = (0.0, 0.02, 0.05)


def third_friday(year: int, month: int) -> pd.Timestamp:
    """Calendar 3rd Friday (SPY/SPX standard monthly option expiry anchor)."""
    first = pd.Timestamp(year=year, month=month, day=1)
    offset = (4 - first.weekday()) % 7
    return first + pd.Timedelta(days=offset + 14)


def map_to_trading_day(spy_index: pd.DatetimeIndex, day: pd.Timestamp) -> pd.Timestamp | None:
    """Map calendar day to last SPY session on or before that day (AM-settled convention)."""
    ts = pd.Timestamp(day).normalize()
    if ts in spy_index:
        return ts
    prior = spy_index[spy_index <= ts]
    if len(prior) == 0:
        return None
    return prior[-1]


def monthly_option_cycles(
    spy_index: pd.DatetimeIndex,
    *,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> list[tuple[pd.Timestamp, pd.Timestamp, str]]:
    """
    (signal_day, expiry_day, expiry_month_label) tuples.

    Signal = prior month's expiry session (when you'd roll / sell next monthly put).
    Expiry = current month's 3rd-Friday-aligned session.
    """
    if len(spy_index) == 0:
        return []
    idx_start = start or spy_index[0]
    idx_end = end or spy_index[-1]
    periods = pd.period_range(idx_start, idx_end, freq="M")
    expiries: list[tuple[pd.Timestamp, str]] = []
    for p in periods:
        cal = third_friday(p.year, p.month)
        td = map_to_trading_day(spy_index, cal)
        if td is not None and idx_start <= td <= idx_end:
            expiries.append((td, f"{p.year}-{p.month:02d}"))
    cycles: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
    for i in range(1, len(expiries)):
        signal_day, _ = expiries[i - 1]
        expiry_day, label = expiries[i]
        if signal_day < expiry_day:
            cycles.append((signal_day, expiry_day, label))
    return cycles


def _features_at_day(
    run_dir: Path,
    as_of: pd.Timestamp,
    *,
    horizon_days: int,
    news_window_days: int,
    llm_cache: dict[str, Any] | None,
) -> dict[str, Any] | None:
    spy = load_etf_closes(run_dir, "SPY")
    if as_of not in spy.index:
        return None
    corpus = load_corpus(run_dir)
    timeline = _corpus_timeline(corpus)
    cluster_model = _load_cluster_model(run_dir)
    coef_map = _keyword_coef_map(load_keyword_map(run_dir, "anchor"))
    pub_cutoff = as_of.to_pydatetime().replace(tzinfo=timezone.utc)
    window = _corpus_before(
        corpus, pub_cutoff, window_days=news_window_days, timeline=timeline
    )
    kw_score, sentiment, top_kw, _ = _signal_from_articles(
        window,
        coef_map,
        llm_cache,
        max_articles=BACKTEST_SIGNAL_MAX_ARTICLES,
        run_dir=run_dir,
    )
    cids = _assign_clusters(cluster_model, window)
    dom, profile = _cluster_context_pit(
        run_dir, window, cids, horizon_days=horizon_days, cluster_model=cluster_model
    )
    events: list[str] = []
    for art in window:
        text = f"{art.get('title', '')} {art.get('body', '')}"
        events.extend(_macro_events(keywords_for_article(art, llm_cache) or []))
        events.extend(_macro_events_from_text(text))
    cot_sig = 0.0
    try:
        cot_frame = ensure_cot_data(run_dir)
        cot_sig = cot_signal_at(cot_frame, as_of)
    except (OSError, RuntimeError):
        pass

    return {
        "keyword_score": kw_score,
        "sentiment": sentiment,
        "cluster_prior": _anchor_cluster_prior(profile),
        "momentum": _momentum_at(spy, as_of),
        "beta_spy": 1.0,
        "cluster_id": dom,
        "news_articles": len(window),
        "macro_events": "|".join(sorted(set(events))) if events else "none",
        "top_keywords": "|".join(top_kw[:5]),
        "cot_signal": cot_sig,
    }


def run_option_range_study(
    run_dir: str | Path,
    *,
    news_window_days: int = 30,
    min_train_months: int = 12,
    lookback_years: int = 5,
    eval_start: str | None = None,
    eval_end: str | None = None,
    put_buffer_pcts: tuple[float, ...] = DEFAULT_PUT_BUFFER_PCTS,
    config: PredictTuneConfig | None = None,
) -> tuple[pd.DataFrame, dict[str, Any], Path]:
    """Score 1m bands at prior expiry; check SPY at next monthly option expiry."""
    root = ensure_run_layout(run_dir)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cfg = config or load_predict_config(root)
    llm_cache = load_keyword_cache(root)
    horizon_days = HORIZON_TRADING_DAYS.get("1m", 21)
    spy = load_etf_closes(root, "SPY")
    if spy.empty:
        raise RuntimeError("SPY OHLCV missing")

    if eval_start and eval_end:
        eval_start_ts = pd.Timestamp(eval_start)
        eval_end_ts = pd.Timestamp(eval_end)
        train_buffer_months = min_train_months + 6
        cache_from = eval_start_ts - pd.DateOffset(months=train_buffer_months)
        max_months = int((eval_end_ts - cache_from).days / 28) + 24
    else:
        eval_start_ts = None
        eval_end_ts = None
        max_months = lookback_years * 12

    feature_cache = build_backtest_feature_cache(
        root,
        horizon_days,
        llm_cache=llm_cache,
        news_window_days=news_window_days,
        min_train_months=min_train_months,
        max_months=max_months,
        through_date=eval_end_ts,
        quiet=True,
    )
    if feature_cache is None:
        raise RuntimeError("Insufficient history for option range study")

    monthly_preds = _score_monthly_spy_from_features(feature_cache, cfg, quiet=True)
    if monthly_preds.empty and not (eval_start and eval_end):
        raise RuntimeError("No monthly walk-forward predictions")

    if eval_start_ts is None:
        eval_start_ts = pd.Timestamp(monthly_preds["trading_day"].min())
        eval_end_ts = pd.Timestamp(monthly_preds["trading_day"].max())

    if spy.index.min() > eval_start_ts:
        raise RuntimeError(
            f"SPY history starts {spy.index.min().date()} — ingest OHLCV before {eval_start_ts.date()}"
        )

    cycles = monthly_option_cycles(spy.index, start=eval_start_ts, end=eval_end_ts)

    rows: list[dict[str, Any]] = []
    for signal_day, expiry_day, expiry_label in cycles:
        feat = _features_at_day(
            root,
            signal_day,
            horizon_days=horizon_days,
            news_window_days=news_window_days,
            llm_cache=llm_cache,
        )
        if feat is None:
            continue

        # Walk-forward train on month-ends strictly before signal
        train_rows = []
        month_ends = feature_cache.month_ends
        for j, me in enumerate(month_ends):
            if me >= signal_day:
                break
            realized = feature_cache.month_realized[j]
            mf = feature_cache.month_features[j]
            if realized is None or not mf:
                continue
            if cfg.train_news_only and mf.get("news_articles", 0) < cfg.min_news_train:
                continue
            train_rows.append({**mf, "forward_return": realized})
        if len(train_rows) < max(3, min_train_months // 2):
            continue

        train_df = pd.DataFrame(train_rows)
        hm = _train_horizon_model(train_df, "1m", horizon_days)
        mom = feat["momentum"]
        ridge_pred, lo, hi, cold, conf = _predict_from_features(
            hm,
            {
                "keyword_score": feat["keyword_score"],
                "sentiment": feat["sentiment"],
                "cluster_prior": feat["cluster_prior"],
                "momentum": mom,
                "beta_spy": 1.0,
            },
            spy_momentum=mom,
            config=cfg,
            news_articles=int(feat.get("news_articles", 0)),
            macro_events=str(feat.get("macro_events", "none")),
        )
        pred = blend_predicted_return(
            ridge_pred,
            sentiment=float(feat.get("sentiment", 0) or 0),
            momentum=mom,
            cot_signal=float(feat.get("cot_signal", 0) or 0),
            news_articles=int(feat.get("news_articles", 0)),
            config=cfg,
        )

        spot_signal = float(spy.loc[signal_day])
        spot_expiry = float(spy.loc[expiry_day])
        trading_days = int(spy.index.get_loc(expiry_day) - spy.index.get_loc(signal_day))

        # Return bands → price bands (model output is forward return, not log)
        lower_ret = float(lo)
        upper_ret = float(hi)
        lower_price = spot_signal * (1.0 + lower_ret)
        upper_price = spot_signal * (1.0 + upper_ret)
        mid_price = spot_signal * (1.0 + float(pred))

        realized_ret = spot_expiry / spot_signal - 1.0
        inside_band = lower_price <= spot_expiry <= upper_price
        below_lower = spot_expiry < lower_price
        above_upper = spot_expiry > upper_price
        breach_lower_usd = round(lower_price - spot_expiry, 2) if below_lower else 0.0
        breach_upper_usd = round(spot_expiry - upper_price, 2) if above_upper else 0.0

        row: dict[str, Any] = {
            "expiry_month": expiry_label,
            "signal_day": signal_day.strftime("%Y-%m-%d"),
            "expiry_day": expiry_day.strftime("%Y-%m-%d"),
            "trading_days_to_expiry": trading_days,
            "spot_at_signal": round(spot_signal, 2),
            "spot_at_expiry": round(spot_expiry, 2),
            "predicted_return": round(pred, 6),
            "confidence_lower_ret": round(lower_ret, 6),
            "confidence_upper_ret": round(upper_ret, 6),
            "price_lower": round(lower_price, 2),
            "price_upper": round(upper_price, 2),
            "price_mid": round(mid_price, 2),
            "realized_return": round(realized_ret, 6),
            "inside_band": inside_band,
            "breach_lower": below_lower,
            "breach_upper": above_upper,
            "breach_lower_usd": breach_lower_usd,
            "breach_upper_usd": breach_upper_usd,
            "spx_lower": round(lower_price * SPX_PER_SPY, 0),
            "spx_upper": round(upper_price * SPX_PER_SPY, 0),
            "spx_spot_signal": round(spot_signal * SPX_PER_SPY, 0),
            "spx_spot_expiry": round(spot_expiry * SPX_PER_SPY, 0),
            "news_articles": feat.get("news_articles", 0),
            "cold_start": cold,
        }
        for buf in put_buffer_pcts:
            strike = lower_price * (1.0 - buf)
            assigned = spot_expiry < strike
            key = f"put_strike_{int(buf * 100)}pct_om_buffer"
            row[key] = round(strike, 2)
            row[f"{key}_assigned"] = assigned
            row[f"{key}_om"] = round(strike, 2)
            if buf == 0.0:
                row["csp_at_model_lower"] = round(strike, 2)
                row["csp_assigned"] = assigned
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No option expiry cycles in evaluation window")

    summary = _summarize_range_study(df, put_buffer_pcts)
    summary["eval_start"] = eval_start_ts.strftime("%Y-%m-%d")
    summary["eval_end"] = eval_end_ts.strftime("%Y-%m-%d")
    summary["news_coverage"] = round(
        100.0 * float((df["news_articles"] > 0).sum()) / len(df), 1
    ) if len(df) else 0.0

    # Compare to month-end alignment (legacy)
    if "article_id" in monthly_preds.columns:
        month_end_rows = monthly_preds[monthly_preds["article_id"].isna()].copy()
    else:
        month_end_rows = monthly_preds.copy()
    if not month_end_rows.empty and "trading_day" in month_end_rows.columns:
        td = pd.to_datetime(month_end_rows["trading_day"])
        month_end_rows = month_end_rows[(td >= eval_start_ts) & (td <= eval_end_ts)]
    me_compare = _month_end_violation_stats(root, month_end_rows, spy)
    summary["month_end_alignment"] = me_compare

    period_tag = (
        f"{eval_start_ts.strftime('%Y')}-{eval_end_ts.strftime('%Y')}"
        if eval_start and eval_end
        else today
    )
    report_path = root / "reports" / f"option_range_study_{period_tag}.md"
    csv_path = root / "reports" / f"option_range_study_{period_tag}.csv"
    df.to_csv(csv_path, index=False)
    report_path.write_text(_format_report(df, summary, cfg, today, period_tag) + "\n")
    return df, summary, report_path


def _month_end_violation_stats(
    run_dir: Path,
    monthly: pd.DataFrame,
    spy: pd.Series,
) -> dict[str, Any]:
    if monthly.empty:
        return {}
    breaches_lo = breaches_hi = inside = 0
    for _, r in monthly.iterrows():
        td = pd.Timestamp(r["trading_day"])
        if td not in spy.index:
            continue
        spot = float(spy.loc[td])
        fwd_idx = spy.index.get_loc(td) + HORIZON_TRADING_DAYS.get("1m", 21)
        if fwd_idx >= len(spy):
            continue
        spot_fwd = float(spy.iloc[fwd_idx])
        lo_p = spot * (1 + float(r["confidence_lower"]))
        hi_p = spot * (1 + float(r["confidence_upper"]))
        if spot_fwd < lo_p:
            breaches_lo += 1
        elif spot_fwd > hi_p:
            breaches_hi += 1
        else:
            inside += 1
    n = breaches_lo + breaches_hi + inside
    return {
        "n": n,
        "inside_band_pct": round(100 * inside / n, 1) if n else 0,
        "breach_lower_pct": round(100 * breaches_lo / n, 1) if n else 0,
        "breach_upper_pct": round(100 * breaches_hi / n, 1) if n else 0,
        "note": "21 trading-day forward from month-end (not option expiry)",
    }


def _summarize_range_study(
    df: pd.DataFrame,
    put_buffer_pcts: tuple[float, ...],
) -> dict[str, Any]:
    n = len(df)
    inside = int(df["inside_band"].sum())
    breach_lo = int(df["breach_lower"].sum())
    breach_hi = int(df["breach_upper"].sum())
    summary: dict[str, Any] = {
        "n_expiry_cycles": n,
        "inside_band_pct": round(100 * inside / n, 1),
        "breach_lower_pct": round(100 * breach_lo / n, 1),
        "breach_upper_pct": round(100 * breach_hi / n, 1),
        "mean_breach_lower_usd": round(
            float(df.loc[df["breach_lower"], "breach_lower_usd"].mean()) if breach_lo else 0.0,
            2,
        ),
        "max_breach_lower_usd": round(
            float(df["breach_lower_usd"].max()) if breach_lo else 0.0,
            2,
        ),
        "mean_trading_days_to_expiry": round(float(df["trading_days_to_expiry"].mean()), 1),
    }
    for buf in put_buffer_pcts:
        key = f"put_strike_{int(buf * 100)}pct_om_buffer"
        assigned_col = f"{key}_assigned"
        if assigned_col in df.columns:
            assigned = int(df[assigned_col].sum())
            summary[f"csp_assigned_{int(buf*100)}pct_buffer_pct"] = round(
                100 * assigned / n, 1
            )
    if "csp_assigned" in df.columns:
        summary["csp_at_model_lower_assigned_pct"] = round(
            100 * int(df["csp_assigned"].sum()) / n, 1
        )
    return summary


def _format_report(
    df: pd.DataFrame,
    summary: dict[str, Any],
    cfg: PredictTuneConfig,
    today: str,
    period_tag: str,
) -> str:
    lines = [
        f"# Option expiry range study — {period_tag}",
        "",
        f"**Generated:** {today} | **Period:** {summary.get('eval_start')} → {summary.get('eval_end')}",
        f"**Config:** `{cfg.name}` | **Alignment:** signal at **prior monthly option expiry** "
        "(3rd Friday → trading day), settle at **next monthly expiry**",
        "",
        f"**News-backed signals:** {summary.get('news_coverage', 0)}% of cycles "
        "(0% expected before news corpus era)",
        "",
        f"**Cycles:** {summary['n_expiry_cycles']} | "
        f"**Inside band:** {summary['inside_band_pct']}% | "
        f"**Breach lower:** {summary['breach_lower_pct']}% | "
        f"**Breach upper:** {summary['breach_upper_pct']}%",
        "",
        "Prices are **SPY** (÷10 ≈ SPX strike). Example: SPY $550 → SPX ~5500.",
        "",
        "## Cash-secured put (sell strike just below model lower)",
        "",
    ]
    if "csp_at_model_lower_assigned_pct" in summary:
        lines.append(
            f"- **Strike = model lower bound:** assigned (spot < strike at expiry) "
            f"**{summary['csp_at_model_lower_assigned_pct']}%** of months"
        )
    for buf in (2, 5):
        k = f"csp_assigned_{buf}pct_buffer_pct"
        if k in summary:
            lines.append(
                f"- **Strike = lower × {1 - buf/100:.2f} ({buf}% OTM buffer):** "
                f"assigned **{summary[k]}%** of months"
            )
    lines.extend(
        [
            "",
            f"- Mean breach below lower when violated: **${summary['mean_breach_lower_usd']}**",
            f"- Max breach below lower: **${summary['max_breach_lower_usd']}**",
            f"- Avg calendar span signal→expiry: **{summary['mean_trading_days_to_expiry']}** trading days",
            "",
            "## vs month-end alignment (legacy backtest)",
            "",
        ]
    )
    me = summary.get("month_end_alignment", {})
    if me:
        lines.append(
            f"Month-end + 21d forward: inside {me.get('inside_band_pct')}% | "
            f"breach lower {me.get('breach_lower_pct')}% | "
            f"breach upper {me.get('breach_upper_pct')}% ({me.get('note')})"
        )
    lines.extend(
        [
            "",
            "## Monthly detail (last 12 cycles)",
            "",
            "| Expiry | Signal | SPY@signal | Lower | Upper | SPY@expiry | Inside | "
            "Δ below lower | CSP assign |",
            "|--------|--------|------------|-------|-------|------------|--------|"
            "---------------|------------|",
        ]
    )
    for _, r in df.tail(12).iterrows():
        assign = "yes" if r.get("csp_assigned") else "no"
        inside = "yes" if r["inside_band"] else ("low" if r["breach_lower"] else "high")
        lines.append(
            f"| {r['expiry_month']} | {r['signal_day']} | ${r['spot_at_signal']:.0f} | "
            f"${r['price_lower']:.0f} | ${r['price_upper']:.0f} | ${r['spot_at_expiry']:.0f} | "
            f"{inside} | ${r['breach_lower_usd']:.0f} | {assign} |"
        )
    lines.extend(
        [
            "",
            "## Full ledger",
            "",
            f"See `option_range_study_{period_tag}.csv` for all cycles with SPX-scaled columns.",
            "",
        ]
    )
    return "\n".join(lines)
