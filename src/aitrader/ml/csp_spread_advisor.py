"""Cash-secured put spread advisor — 8–9Δ monthly cycles with safety gate."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from aitrader.data.cot import cot_signal_at, ensure_cot_data
from aitrader.ml.backtest import (
    _corpus_before,
    _corpus_timeline,
    _predict_from_features,
    _train_horizon_model,
    build_backtest_feature_cache,
)
from aitrader.ml.option_range_study import (
    _features_at_day,
    map_to_trading_day,
    monthly_option_cycles,
    third_friday,
)
from aitrader.ml.predict import _momentum_at
from aitrader.ml.predict_config import PredictTuneConfig, load_predict_config
from aitrader.ml.strategy_signals import blend_predicted_return
from aitrader.nlp.keyword_cache import keywords_for_article, load_keyword_cache
from aitrader.nlp.keywords import HORIZON_TRADING_DAYS, load_etf_closes
from aitrader.nlp.news import load_corpus
from aitrader.nlp.sentiment import IndexTag, get_sentiment_scorer
from aitrader.workspace import ensure_run_layout

INDEX_ETF: dict[IndexTag, str] = {"SPX": "SPY", "RUT": "IWM"}
INDEX_SCALE = 10.0
HORIZON_DAYS_1M = HORIZON_TRADING_DAYS.get("1m", 21)

# User target: ~8–9Δ short put, ~$200 credit on $10k, 20 spreads
DEFAULT_TARGET_DELTA = 0.085
DEFAULT_SPREADS = 20
DEFAULT_CAPITAL_USD = 10_000.0
DEFAULT_TARGET_CREDIT_USD = 200.0
DEFAULT_SPREAD_WIDTH_PCT = 0.03  # ETF/RUT fallback width
SPX_SPREAD_WIDTH_POINTS = 5.0  # user: 6680/6675 style 5-pt SPX spread
WIDEN_OTM_MULT = 1.35  # ~6Δ when standard ~8.5Δ is marginal


@dataclass
class CSPSpreadParams:
    target_delta: float = DEFAULT_TARGET_DELTA
    spreads: int = DEFAULT_SPREADS
    capital_usd: float = DEFAULT_CAPITAL_USD
    target_credit_usd: float = DEFAULT_TARGET_CREDIT_USD
    spread_width_pct: float = DEFAULT_SPREAD_WIDTH_PCT
    spread_width_points: float = SPX_SPREAD_WIDTH_POINTS
    safety_floor: float = 12.0
    caution_floor: float = 8.0
    sell_eff_floor: float = 0.005
    widen_eff_floor: float = 0.0
    min_pred_sell: float = -0.02
    min_pred_widen: float = -0.015
    max_drawdown_20d: float = -0.07
    min_safe_prob: float = 0.70  # exit when safe prob drops below (assign prob > 30%)
    entry_min_safe_prob: float = 0.90  # require ≥90% OTM at entry (|delta| ≤ 10%)
    max_entry_safe_prob: float = 0.93  # ignore phantom far-OTM marks (>93% safe, ~0.05 credit in TOS)
    min_short_delta: float = 0.075  # ~7.5Δ floor — 0.25 credit not available below ~92.5% OTM
    target_credit_band: tuple[float, float] = (0.20, 0.30)
    spx_short_strike: float | None = None
    spx_long_strike: float | None = None


@dataclass
class CSPAdvice:
    index: IndexTag
    signal_day: str
    expiry_day: str
    trading_days_to_expiry: int
    spot: float
    index_spot: float
    short_strike_etf: float
    short_strike_index: float
    long_strike_etf: float
    model_floor_etf: float
    model_floor_index: float
    expected_return: float
    safety_score: float
    action: Literal["SELL", "WIDEN", "SKIP", "SELL_OTM"]
    credit_usd_est: float
    macro_sentiment: float
    index_sentiment: float
    event_risk: str
    rationale: str
    effective_breach_buffer: float = 0.0
    drawdown_20d: float = 0.0
    target_otm_pct: float = 0.0
    assignment_prob: float = 0.0
    safe_prob: float = 0.0
    exit_signal: str = "HOLD"
    schwab_credit_mid: float | None = None
    schwab_short_strike: float | None = None
    schwab_long_strike: float | None = None


def _monthly_returns(closes: pd.Series) -> np.ndarray:
    rets: list[float] = []
    for i in range(21, len(closes)):
        rets.append(float(closes.iloc[i] / closes.iloc[i - 21] - 1.0))
    return np.array(rets) if rets else np.array([0.0])


def recent_drawdown(closes: pd.Series, as_of: pd.Timestamp, *, days: int = 20) -> float:
    """Trailing return over `days` trading sessions ending at `as_of`."""
    if as_of not in closes.index:
        return 0.0
    pos = closes.index.get_loc(as_of)
    if pos < days:
        return 0.0
    start = closes.iloc[pos - days]
    if start <= 0:
        return 0.0
    return float(closes.iloc[pos] / start - 1.0)


def effective_breach_buffer(lower_return: float, otm_pct: float, predicted_return: float) -> float:
    """Return-space cushion: model floor vs short strike, boosted by positive forecast."""
    return lower_return + otm_pct + max(0.0, predicted_return) * 0.5


def empirical_otm_pct(
    closes: pd.Series,
    *,
    target_delta: float = DEFAULT_TARGET_DELTA,
    floor_pct: float = 0.075,
    cap_pct: float = 0.14,
) -> float:
    """OTM % for short put ≈ target delta from monthly return quantile."""
    rets = _monthly_returns(closes)
    if len(rets) < 12:
        vol = float(np.std(rets)) if len(rets) > 1 else 0.05
        # rough normal: 8.5Δ ≈ 1.35σ monthly
        return float(np.clip(1.35 * vol, floor_pct, cap_pct))
    otm = -float(np.quantile(rets, target_delta))
    return float(np.clip(otm, floor_pct, cap_pct))


def scale_return_for_dte(ret: float, trading_days: int, base_days: int = HORIZON_DAYS_1M) -> float:
    """Expiry-aligned horizon: scale 1m return by √(DTE/base)."""
    if trading_days <= 0:
        return ret
    scale = math.sqrt(trading_days / base_days)
    return ret * scale


def _event_risk_tags(events: str) -> tuple[str, float]:
    """Return dominant stress tag and risk penalty 0..1."""
    if not events or events == "none":
        return "none", 0.0
    tags = set(events.split("|"))
    if "tariff" in tags:
        return "tariff", 0.25
    if "fed" in tags and "inflation" in tags:
        return "fed+inflation", 0.18
    if "fed" in tags:
        return "fed", 0.10
    if "inflation" in tags:
        return "inflation", 0.12
    if "employment" in tags:
        return "employment", 0.08
    return "mixed", 0.05


def _crash_veto(
    *,
    predicted_return: float,
    drawdown_20d: float,
    event_penalty: float,
    macro_sentiment: float,
    index_sentiment: float,
    params: CSPSpreadParams,
) -> tuple[bool, str]:
    if predicted_return < -0.02:
        return True, "forecast drawdown"
    if drawdown_20d <= params.max_drawdown_20d:
        return True, f"20d selloff {drawdown_20d*100:.1f}%"
    if event_penalty >= 0.15 and macro_sentiment < -0.025 and index_sentiment < -0.12:
        return True, "stress macro + index sentiment"
    return False, ""


def csp_action_gate(
    *,
    eff_buffer: float,
    predicted_return: float,
    safety_score: float,
    crash_veto: bool,
    params: CSPSpreadParams,
    schwab_safe_prob: float | None = None,
    schwab_credit_mid: float | None = None,
) -> Literal["SELL", "WIDEN", "SKIP", "SELL_OTM"]:
    hard_veto = crash_veto and predicted_return < -0.025
    if hard_veto:
        return "SKIP"
    lo, hi = params.target_credit_band
    credit_ok = schwab_credit_mid is not None and lo <= schwab_credit_mid <= hi
    if credit_ok and schwab_safe_prob is not None and schwab_safe_prob >= params.entry_min_safe_prob:
        if predicted_return >= params.min_pred_sell:
            return "SELL_OTM"
    if eff_buffer >= params.sell_eff_floor and predicted_return >= params.min_pred_sell:
        if safety_score >= params.safety_floor:
            return "SELL"
    if eff_buffer >= params.widen_eff_floor and predicted_return >= params.min_pred_widen:
        if safety_score >= params.caution_floor:
            return "WIDEN"
    return "SKIP"


def tier_a_action(
    base_action: Literal["SELL", "WIDEN", "SKIP", "SELL_OTM"],
    *,
    crash_veto: bool,
) -> tuple[Literal["SELL", "WIDEN", "SKIP", "SELL_OTM"], bool]:
    """Utilization tier A: trade only when model gates pass (SELL / WIDEN / SELL_OTM)."""
    if crash_veto or base_action == "SKIP":
        return "SKIP", False
    return base_action, True


def tier_b_action(
    base_action: Literal["SELL", "WIDEN", "SKIP", "SELL_OTM"],
    *,
    crash_veto: bool,
) -> tuple[Literal["SELL", "WIDEN", "SKIP", "SELL_OTM"], bool]:
    """Utilization tier B: trade unless crash_veto; default marginal months to WIDEN."""
    if crash_veto:
        return "SKIP", False
    if base_action == "SKIP":
        return "WIDEN", True
    return base_action, True


UtilizationTier = Literal["A", "B"]


def apply_utilization_tier(
    base_action: Literal["SELL", "WIDEN", "SKIP", "SELL_OTM"],
    *,
    crash_veto: bool,
    tier: UtilizationTier = "B",
) -> tuple[Literal["SELL", "WIDEN", "SKIP", "SELL_OTM"], bool]:
    if tier == "A":
        return tier_a_action(base_action, crash_veto=crash_veto)
    return tier_b_action(base_action, crash_veto=crash_veto)


def csp_safety_score(
    *,
    spot: float,
    short_strike: float,
    model_floor: float,
    otm_pct: float,
    lower_return: float,
    macro_sentiment: float,
    index_sentiment: float,
    momentum: float,
    cot_signal: float,
    event_penalty: float,
    predicted_return: float,
) -> tuple[float, str]:
    """0–100 score; higher = safer to sell OTM put spread."""
    margin_pct = 100.0 * (model_floor - short_strike) / spot if spot > 0 else 0.0
    breach_buffer_ret = lower_return + otm_pct
    eff = effective_breach_buffer(lower_return, otm_pct, predicted_return)
    score = 18.0 + eff * 220.0 + margin_pct * 1.2
    score += macro_sentiment * 22.0
    score += index_sentiment * 14.0
    score += momentum * 45.0
    score += cot_signal * 5.0
    score -= event_penalty * 35.0
    score = float(np.clip(score, 0.0, 100.0))
    parts = [
        f"eff buffer {eff*100:+.1f}pp",
        f"raw breach {breach_buffer_ret*100:+.1f}pp",
        f"macro_sent {macro_sentiment:+.3f}",
    ]
    if event_penalty > 0.15:
        parts.append("elevated event risk")
    return score, "; ".join(parts)


def _enhanced_features(
    run_dir: Path,
    as_of: pd.Timestamp,
    index: IndexTag,
    *,
    news_window_days: int,
    llm_cache: dict[str, Any] | None,
) -> dict[str, Any] | None:
    base = _features_at_day(
        run_dir,
        as_of,
        horizon_days=HORIZON_DAYS_1M,
        news_window_days=news_window_days,
        llm_cache=llm_cache,
    )
    if base is None:
        return None
    corpus = load_corpus(run_dir)
    timeline = _corpus_timeline(corpus)
    pub_cutoff = as_of.to_pydatetime().replace(tzinfo=timezone.utc)
    window = _corpus_before(corpus, pub_cutoff, window_days=news_window_days, timeline=timeline)
    scorer = get_sentiment_scorer(run_dir)
    macro_sent, _ = scorer.macro_mean(window, llm_cache)
    index_sent, _ = scorer.index_macro_mean(window, index, llm_cache)
    base["macro_sentiment"] = macro_sent
    base["index_sentiment"] = index_sent
    # Blend headline sentiment with macro-filtered (kickass stack)
    base["sentiment"] = 0.55 * macro_sent + 0.25 * index_sent + 0.20 * float(base.get("sentiment", 0))
    return base


def _cycle_forecast(
    run_dir: Path,
    signal_day: pd.Timestamp,
    expiry_day: pd.Timestamp,
    index: IndexTag,
    *,
    params: CSPSpreadParams,
    cfg: PredictTuneConfig,
    feature_cache: Any,
    llm_cache: dict[str, Any] | None,
    news_window_days: int = 30,
) -> dict[str, Any] | None:
    etf = INDEX_ETF[index]
    closes = load_etf_closes(run_dir, etf)
    spy = load_etf_closes(run_dir, "SPY")
    if signal_day not in closes.index:
        return None
    if expiry_day not in closes.index:
        # forward expiry: still score using signal_day only
        spot_expiry = None
    else:
        spot_expiry = float(closes.loc[expiry_day])

    feat = _enhanced_features(run_dir, signal_day, index, news_window_days=news_window_days, llm_cache=llm_cache)
    if feat is None:
        return None

    train_rows = []
    month_ends = feature_cache.month_ends
    for j, me in enumerate(month_ends):
        if me >= signal_day:
            break
        realized = feature_cache.month_realized[j]
        mf = feature_cache.month_features[j]
        if realized is None or not mf:
            continue
        train_rows.append({**mf, "forward_return": realized})
    if len(train_rows) < 6:
        return None

    train_df = pd.DataFrame(train_rows)
    hm = _train_horizon_model(train_df, "1m", HORIZON_DAYS_1M)
    mom = float(feat["momentum"])
    ridge_pred, lo, hi, cold, _conf = _predict_from_features(
        hm,
        {
            "keyword_score": feat["keyword_score"],
            "sentiment": feat["sentiment"],
            "cluster_prior": feat["cluster_prior"],
            "momentum": mom,
            "beta_spy": 1.0,
        },
        spy_momentum=_momentum_at(spy, signal_day),
        config=cfg,
        news_articles=int(feat.get("news_articles", 0)),
        macro_events=str(feat.get("macro_events", "none")),
    )
    pred = blend_predicted_return(
        ridge_pred,
        sentiment=float(feat.get("sentiment", 0)),
        momentum=mom,
        cot_signal=float(feat.get("cot_signal", 0)),
        news_articles=int(feat.get("news_articles", 0)),
        config=cfg,
    )

    tdays = len(pd.bdate_range(signal_day + pd.Timedelta(days=1), expiry_day))
    pred_s = scale_return_for_dte(pred, tdays)
    lo_s = scale_return_for_dte(float(lo), tdays)
    hi_s = scale_return_for_dte(float(hi), tdays)

    spot = float(closes.loc[signal_day])
    otm_pct = empirical_otm_pct(closes, target_delta=params.target_delta)
    drawdown_20d = recent_drawdown(closes, signal_day)
    model_floor = spot * (1.0 + lo_s)
    eff_buffer = effective_breach_buffer(lo_s, otm_pct, pred_s)

    event_tag, event_pen = _event_risk_tags(str(feat.get("macro_events", "none")))
    macro_sent = float(feat.get("macro_sentiment", 0))
    index_sent = float(feat.get("index_sentiment", 0))
    veto, veto_reason = _crash_veto(
        predicted_return=pred_s,
        drawdown_20d=drawdown_20d,
        event_penalty=event_pen,
        macro_sentiment=macro_sent,
        index_sentiment=index_sent,
        params=params,
    )

    short_strike = spot * (1.0 - otm_pct)
    safety, rationale = csp_safety_score(
        spot=spot,
        short_strike=short_strike,
        model_floor=model_floor,
        otm_pct=otm_pct,
        lower_return=lo_s,
        macro_sentiment=macro_sent,
        index_sentiment=index_sent,
        momentum=mom,
        cot_signal=float(feat.get("cot_signal", 0)),
        event_penalty=event_pen,
        predicted_return=pred_s,
    )
    action = csp_action_gate(
        eff_buffer=eff_buffer,
        predicted_return=pred_s,
        safety_score=safety,
        crash_veto=veto,
        params=params,
    )
    if veto and veto_reason:
        rationale = f"{rationale}; veto: {veto_reason}"

    strike_otm = otm_pct
    if action == "WIDEN":
        strike_otm = min(otm_pct * WIDEN_OTM_MULT, 0.14)
    short_strike = spot * (1.0 - strike_otm)
    long_strike = short_strike * (1.0 - params.spread_width_pct)

    credit = params.target_credit_usd
    assigned = False
    loss_usd = 0.0
    if spot_expiry is not None:
        assigned = spot_expiry < short_strike
        if assigned:
            width = short_strike - long_strike
            loss_usd = (width * INDEX_SCALE * params.spreads) - credit

    return {
        "index": index,
        "signal_day": signal_day.strftime("%Y-%m-%d"),
        "expiry_day": expiry_day.strftime("%Y-%m-%d"),
        "trading_days_to_expiry": tdays,
        "spot": round(spot, 2),
        "index_spot": round(spot * INDEX_SCALE, 0),
        "otm_pct": round(100 * strike_otm, 2),
        "target_otm_pct": round(100 * otm_pct, 2),
        "effective_breach_buffer": round(eff_buffer, 6),
        "drawdown_20d": round(drawdown_20d, 6),
        "short_strike_etf": round(short_strike, 2),
        "short_strike_index": round(short_strike * INDEX_SCALE, 0),
        "long_strike_etf": round(long_strike, 2),
        "model_floor_etf": round(model_floor, 2),
        "model_floor_index": round(model_floor * INDEX_SCALE, 0),
        "expected_return": round(pred_s, 6),
        "confidence_lower_ret": round(lo_s, 6),
        "confidence_upper_ret": round(hi_s, 6),
        "safety_score": round(safety, 1),
        "action": action,
        "credit_usd_est": credit,
        "macro_sentiment": round(float(feat.get("macro_sentiment", 0)), 4),
        "index_sentiment": round(float(feat.get("index_sentiment", 0)), 4),
        "event_risk": event_tag,
        "rationale": rationale,
        "spot_at_expiry": spot_expiry,
        "assigned": assigned,
        "loss_usd": round(loss_usd, 2),
        "cold_start": cold,
        "crash_veto": veto,
    }


def backtest_csp_spreads(
    run_dir: str | Path,
    *,
    indices: tuple[IndexTag, ...] = ("SPX", "RUT"),
    params: CSPSpreadParams | None = None,
    news_window_days: int = 30,
    lookback_years: int = 5,
    only_when_sell: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any], Path]:
    """Simulate monthly 8–9Δ put spreads with safety gate."""
    root = ensure_run_layout(run_dir)
    p = params or CSPSpreadParams()
    cfg = load_predict_config(root)
    llm_cache = load_keyword_cache(root)
    spy = load_etf_closes(root, "SPY")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    feature_cache = build_backtest_feature_cache(
        root,
        HORIZON_DAYS_1M,
        llm_cache=llm_cache,
        news_window_days=news_window_days,
        min_train_months=12,
        max_months=lookback_years * 12,
        quiet=True,
    )
    if feature_cache is None:
        raise RuntimeError("Insufficient history for CSP backtest")

    eval_end = spy.index[-1]
    eval_start = eval_end - pd.DateOffset(years=lookback_years)
    cycles = monthly_option_cycles(spy.index, start=eval_start, end=eval_end)

    rows: list[dict[str, Any]] = []
    for signal_day, expiry_day, label in cycles:
        for index in indices:
            row = _cycle_forecast(
                root,
                signal_day,
                expiry_day,
                index,
                params=p,
                cfg=cfg,
                feature_cache=feature_cache,
                llm_cache=llm_cache,
                news_window_days=news_window_days,
            )
            if row is None:
                continue
            row["expiry_month"] = label
            traded = row["action"] in ("SELL", "WIDEN", "SELL_OTM")
            if only_when_sell:
                traded = row["action"] in ("SELL", "SELL_OTM")
            row["traded"] = traded
            if traded and row.get("spot_at_expiry") is not None:
                row["pnl_usd"] = p.target_credit_usd if not row["assigned"] else -row["loss_usd"]
            else:
                row["pnl_usd"] = 0.0
            rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No CSP spread cycles scored")

    traded_df = df[df["traded"]]
    sell_df = df[df["action"] == "SELL"]
    assigned = int(traded_df["assigned"].sum()) if len(traded_df) else 0
    total_pnl = float(traded_df["pnl_usd"].sum()) if len(traded_df) else 0.0
    months_traded = len(traded_df)
    summary = {
        "capital_usd": p.capital_usd,
        "target_delta": p.target_delta,
        "target_credit_usd": p.target_credit_usd,
        "spreads_per_month": p.spreads,
        "cycles": len(df) // len(indices),
        "months_traded": months_traded,
        "months_sell_only": len(sell_df),
        "months_widen": int((df["action"] == "WIDEN").sum()),
        "months_skipped": int((df["action"] == "SKIP").sum()),
        "assignment_rate_pct": round(100 * assigned / months_traded, 1) if months_traded else 0.0,
        "total_pnl_usd": round(total_pnl, 2),
        "avg_pnl_per_traded_month": round(total_pnl / months_traded, 2) if months_traded else 0.0,
        "cagr_pct": round(
            100 * ((1 + total_pnl / p.capital_usd) ** (12 / max(months_traded, 1)) - 1),
            1,
        ) if months_traded else 0.0,
    }

    report = root / "reports" / f"csp_spread_backtest_{today}.md"
    csv_path = root / "reports" / f"csp_spread_backtest_{today}.csv"
    df.to_csv(csv_path, index=False)
    lines = [
        f"# CSP put-spread backtest — {today}",
        "",
        f"**Strategy:** ~{p.target_delta*100:.1f}Δ short put spread | "
        f"${p.target_credit_usd:.0f} credit | {p.spreads} spreads | "
        f"eff≥{p.sell_eff_floor*100:.1f}pp & safety≥{p.safety_floor:.0f} → SELL | "
        f"eff≥{p.widen_eff_floor*100:.1f}pp → WIDEN",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Months traded (SELL+WIDEN) | {summary['months_traded']} |",
        f"| SELL @ ~{p.target_delta*100:.1f}Δ | {summary['months_sell_only']} |",
        f"| WIDEN (~6Δ) | {summary['months_widen']} |",
        f"| Months skipped (gate) | {summary['months_skipped']} |",
        f"| Assignment rate | {summary['assignment_rate_pct']}% |",
        f"| Total P&L | ${summary['total_pnl_usd']:,.0f} |",
        f"| Avg P&L / traded month | ${summary['avg_pnl_per_traded_month']:,.0f} |",
        f"| Implied CAGR (traded months) | {summary['cagr_pct']}% |",
        "",
        f"Artifacts: `{csv_path.name}`",
    ]
    report.write_text("\n".join(lines) + "\n")
    return df, summary, report


def backtest_csp_spreads_spx_schwab(
    run_dir: str | Path,
    *,
    params: CSPSpreadParams | None = None,
    news_window_days: int = 30,
    lookback_years: int = 5,
    token_path: str | Path | None = None,
    rate_limit_sec: float = 0.35,
) -> tuple[pd.DataFrame, dict[str, Any], Path]:
    """SPX monthly put spreads with Schwab ANALYTICAL option credits (historical spot/vol)."""
    import time as _time

    from aitrader.data.schwab import SchwabClient
    from aitrader.ml.csp_spread_pricing import fetch_spx_put_spread, realized_vol

    root = ensure_run_layout(run_dir)
    p = params or CSPSpreadParams()
    client = SchwabClient.from_token_path(token_path)
    spy = load_etf_closes(root, "SPY")

    df_model, _, _ = backtest_csp_spreads(
        root,
        indices=("SPX",),
        params=p,
        news_window_days=news_window_days,
        lookback_years=lookback_years,
        only_when_sell=False,
    )

    rows: list[dict[str, Any]] = []
    for _, row in df_model.iterrows():
        out = dict(row)
        if row["action"] == "SKIP":
            out["schwab_priced"] = False
            out["pnl_usd"] = 0.0
            rows.append(out)
            continue

        signal_day = pd.Timestamp(row["signal_day"])
        expiry_day = pd.Timestamp(row["expiry_day"])
        hist = spy.loc[:signal_day].tail(25)
        spot = float(hist.iloc[-1]) * INDEX_SCALE
        vol = realized_vol(hist.tolist())
        dte = int(row["trading_days_to_expiry"])

        try:
            quote = fetch_spx_put_spread(
                client,
                expiry=expiry_day.date(),
                target_credit_lo=p.target_credit_band[0],
                target_credit_hi=p.target_credit_band[1],
                spread_width=p.spread_width_points,
                entry_min_safe_prob=p.entry_min_safe_prob,
                analytical=True,
                underlying_price=spot,
                volatility=vol,
                days_to_expiration=dte,
            )
        except Exception as exc:
            out["schwab_priced"] = False
            out["schwab_error"] = str(exc)
            out["pnl_usd"] = 0.0
            rows.append(out)
            _time.sleep(rate_limit_sec)
            continue

        _time.sleep(rate_limit_sec)
        if quote is None:
            out["schwab_priced"] = False
            out["pnl_usd"] = 0.0
            rows.append(out)
            continue

        credit_pc = quote.credit_mid
        credit_total = credit_pc * 100.0 * p.spreads
        spot_exp = row.get("spot_at_expiry")
        assigned = False
        loss_usd = 0.0
        if spot_exp is not None:
            spot_idx = float(spot_exp) * INDEX_SCALE
            assigned = spot_idx < quote.short_leg.strike
            if assigned:
                loss_usd = quote.width * 100.0 * p.spreads - credit_total

        out.update(
            {
                "schwab_priced": True,
                "schwab_credit_per_contract": round(credit_pc, 4),
                "schwab_credit_total": round(credit_total, 2),
                "schwab_short_strike": quote.short_leg.strike,
                "schwab_long_strike": quote.long_leg.strike,
                "schwab_short_delta": round(quote.short_delta_abs, 4),
                "assignment_prob": round(quote.assignment_prob, 4),
                "safe_prob": round(quote.safe_prob, 4),
                "exit_signal": quote.exit_signal,
                "assigned": assigned,
                "loss_usd": round(loss_usd, 2),
                "pnl_usd": credit_total if not assigned else -loss_usd,
                "traded": True,
            }
        )
        rows.append(out)

    out_df = pd.DataFrame(rows)
    traded_df = out_df[(out_df["traded"]) & (out_df.get("schwab_priced", False))]
    assigned = int(traded_df["assigned"].sum()) if len(traded_df) else 0
    total_pnl = float(traded_df["pnl_usd"].sum()) if len(traded_df) else 0.0
    months_traded = len(traded_df)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    summary = {
        "index": "SPX",
        "pricing": "schwab_analytical",
        "months_traded": months_traded,
        "months_skipped": int((out_df["action"] == "SKIP").sum()),
        "assignment_rate_pct": round(100 * assigned / months_traded, 1) if months_traded else 0.0,
        "total_pnl_usd": round(total_pnl, 2),
        "avg_pnl_per_traded_month": round(total_pnl / months_traded, 2) if months_traded else 0.0,
        "cagr_pct": round(
            100 * ((1 + total_pnl / p.capital_usd) ** (12 / max(months_traded, 1)) - 1),
            1,
        )
        if months_traded
        else 0.0,
        "min_safe_prob": p.min_safe_prob,
        "target_credit_band": p.target_credit_band,
    }

    report = root / "reports" / f"csp_spread_spx_schwab_backtest_{today}.md"
    csv_path = root / "reports" / f"csp_spread_spx_schwab_backtest_{today}.csv"
    out_df.to_csv(csv_path, index=False)
    lines = [
        f"# SPX CSP backtest — Schwab analytical prices ({today})",
        "",
        "Uses Schwab `/chains?strategy=ANALYTICAL` at each signal with historical SPX spot, "
        "20d realized vol, and DTE. Credits are model marks (not historical prints).",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Months traded (model gate + Schwab price) | {summary['months_traded']} |",
        f"| Assignment rate | {summary['assignment_rate_pct']}% |",
        f"| Total P&L | ${summary['total_pnl_usd']:,.0f} |",
        f"| Target credit / contract | ${p.target_credit_band[0]:.2f}–${p.target_credit_band[1]:.2f} |",
        f"| Exit rule | HOLD while safe prob ≥ {p.min_safe_prob*100:.0f}% |",
        "",
        f"Artifacts: `{csv_path.name}`",
    ]
    report.write_text("\n".join(lines) + "\n")
    return out_df, summary, report


def advise_next_cycle(
    run_dir: str | Path,
    *,
    expiry_year: int,
    expiry_month: int,
    indices: tuple[IndexTag, ...] = ("SPX", "RUT"),
    params: CSPSpreadParams | None = None,
    news_window_days: int = 30,
    schwab_client: Any | None = None,
) -> tuple[list[CSPAdvice], Path]:
    """Forward advice for a target monthly expiry (3rd Friday)."""
    root = ensure_run_layout(run_dir)
    p = params or CSPSpreadParams()
    cfg = load_predict_config(root)
    llm_cache = load_keyword_cache(root)
    spy = load_etf_closes(root, "SPY")
    signal_day = spy.index[-1]
    cal_exp = third_friday(expiry_year, expiry_month)
    expiry_for_dte = pd.Timestamp(cal_exp.date())
    if expiry_for_dte <= signal_day:
        raise ValueError(f"Expiry {cal_exp.date()} must be after signal {signal_day.date()}")
    expiry_day = map_to_trading_day(spy.index, cal_exp)
    if expiry_day is None or expiry_day <= signal_day:
        expiry_day = expiry_for_dte

    feature_cache = build_backtest_feature_cache(
        root,
        HORIZON_DAYS_1M,
        llm_cache=llm_cache,
        news_window_days=news_window_days,
        min_train_months=12,
        max_months=60,
        quiet=True,
    )
    if feature_cache is None:
        raise RuntimeError("Insufficient history for CSP advice")

    advices: list[CSPAdvice] = []
    for index in indices:
        row = _cycle_forecast(
            root,
            signal_day,
            expiry_day,
            index,
            params=p,
            cfg=cfg,
            feature_cache=feature_cache,
            llm_cache=llm_cache,
            news_window_days=news_window_days,
        )
        if row is None:
            continue

        schwab_credit = None
        schwab_short = None
        schwab_long = None
        assign_p = 0.0
        safe_p = 0.0
        exit_sig = "HOLD"
        action = row["action"]
        if schwab_client is not None and index == "SPX":
            from aitrader.ml.csp_spread_pricing import fetch_spx_put_spread

            try:
                q = fetch_spx_put_spread(
                    schwab_client,
                    expiry=expiry_day.date(),
                    target_credit_lo=p.target_credit_band[0],
                    target_credit_hi=p.target_credit_band[1],
                    spread_width=p.spread_width_points,
                    entry_min_safe_prob=p.entry_min_safe_prob,
                    max_entry_safe_prob=p.max_entry_safe_prob,
                    min_short_delta=p.min_short_delta,
                    exit_min_safe_prob=p.min_safe_prob,
                    short_strike=p.spx_short_strike,
                    long_strike=p.spx_long_strike,
                )
                if q:
                    schwab_credit = q.credit_mid
                    schwab_short = q.short_leg.strike
                    schwab_long = q.long_leg.strike
                    assign_p = q.assignment_prob
                    safe_p = q.safe_prob
                    exit_sig = q.exit_signal
                    action = csp_action_gate(
                        eff_buffer=float(row.get("effective_breach_buffer", 0)),
                        predicted_return=float(row["expected_return"]),
                        safety_score=float(row["safety_score"]),
                        crash_veto=bool(row.get("crash_veto", False)),
                        params=p,
                        schwab_safe_prob=q.safe_prob,
                        schwab_credit_mid=q.credit_mid,
                    )
                    if action == "SELL_OTM":
                        row["rationale"] = (
                            f"{row['rationale']}; disciplined: furthest OTM in "
                            f"{p.target_credit_band[0]:.2f}–{p.target_credit_band[1]:.2f}pt band "
                            f"({q.short_leg.strike:.0f}/{q.long_leg.strike:.0f}, "
                            f"{q.credit_mid:.2f}pts, safe {q.safe_prob*100:.1f}%, exit&lt;70%)"
                        )
                else:
                    row["rationale"] = (
                        f"{row['rationale']}; no Schwab spread in "
                        f"{p.target_credit_band[0]:.2f}–{p.target_credit_band[1]:.2f}pt credit band"
                    )
            except Exception as exc:
                row["schwab_error"] = str(exc)

        advices.append(
            CSPAdvice(
                index=index,
                signal_day=row["signal_day"],
                expiry_day=row["expiry_day"],
                trading_days_to_expiry=int(row["trading_days_to_expiry"]),
                spot=float(row["spot"]),
                index_spot=float(row["index_spot"]),
                short_strike_etf=float(row["short_strike_etf"]),
                short_strike_index=float(row["short_strike_index"]),
                long_strike_etf=float(row["long_strike_etf"]),
                model_floor_etf=float(row["model_floor_etf"]),
                model_floor_index=float(row["model_floor_index"]),
                expected_return=float(row["expected_return"]),
                safety_score=float(row["safety_score"]),
                action=action,
                credit_usd_est=float(row["credit_usd_est"]),
                macro_sentiment=float(row["macro_sentiment"]),
                index_sentiment=float(row["index_sentiment"]),
                event_risk=row["event_risk"],
                rationale=row["rationale"],
                effective_breach_buffer=float(row.get("effective_breach_buffer", 0)),
                drawdown_20d=float(row.get("drawdown_20d", 0)),
                target_otm_pct=float(row.get("target_otm_pct", row.get("otm_pct", 0))),
                assignment_prob=assign_p,
                safe_prob=safe_p,
                exit_signal=exit_sig,
                schwab_credit_mid=schwab_credit,
                schwab_short_strike=schwab_short,
                schwab_long_strike=schwab_long,
            )
        )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = root / "reports" / f"csp_spread_advice_{expiry_year}-{expiry_month:02d}_{today}.md"
    lines = [
        f"# CSP put-spread advice — expiry {cal_exp.strftime('%Y-%m-%d')} ({today})",
        "",
        f"Signal: **{signal_day.strftime('%Y-%m-%d')}** | "
        f"**{p.spreads}** contracts | **{p.spread_width_points:.0f}pt** SPX spread | "
        f"credit **{p.target_credit_band[0]:.2f}–{p.target_credit_band[1]:.2f}** idx pts | "
        f"exit when OTM safe &lt; **{p.min_safe_prob*100:.0f}%**",
        "",
        "_Advisory only — not a trade instruction. Schwab API is quotes-only; execute manually in your broker._",
        "",
    ]
    for a in advices:
        lines += [
            f"## {a.index} ({INDEX_ETF[a.index]})",
            "",
            f"| Field | ETF | Index |",
            f"|-------|-----|-------|",
            f"| Spot | ${a.spot:.2f} | {a.index_spot:.0f} |",
            f"| Short strike (~{p.target_delta*100:.1f}Δ) | ${a.short_strike_etf:.2f} | **{a.short_strike_index:.0f}** |",
            f"| Long strike ({p.spread_width_points:.0f}pt below short) | ${a.long_strike_etf:.2f} | {a.long_strike_etf*INDEX_SCALE:.0f} |",
            f"| Model floor | ${a.model_floor_etf:.2f} | {a.model_floor_index:.0f} |",
            f"| Expected return (DTE-scaled) | {100*a.expected_return:+.2f}% | — |",
            f"| **Safety score** | **{a.safety_score:.0f}/100** | **{a.action}** |",
            "",
            f"- Eff breach buffer: {100*a.effective_breach_buffer:+.1f}pp | 20d return: {100*a.drawdown_20d:+.1f}%",
            f"- Macro FinBERT: {a.macro_sentiment:+.3f} | Index-tagged: {a.index_sentiment:+.3f}",
            f"- Event risk: {a.event_risk} | {a.rationale}",
        ]
        if a.schwab_credit_mid is not None:
            lines += [
                f"- **Schwab spread:** short **{a.schwab_short_strike:.0f}** / long **{a.schwab_long_strike:.0f}** | "
                f"**mark** credit **{a.schwab_credit_mid:.2f} idx pts** (~${a.schwab_credit_mid * 100:.0f}/contract, "
                f"~${a.schwab_credit_mid * p.spreads * 100:.0f} on {p.spreads} spreads) — "
                f"same basis as TOS Mark; use limit at mark",
                f"- Assignment prob **{100*a.assignment_prob:.1f}%** | safe **{100*a.safe_prob:.1f}%** | **{a.exit_signal}** "
                f"(exit if safe &lt; {100*p.min_safe_prob:.0f}%)",
                "",
            ]
        else:
            lines.append("")
    out.write_text("\n".join(lines) + "\n")
    meta_path = root / "models" / "csp_spread_config.json"
    meta_path.write_text(
        json.dumps(
            {
                "params": p.__dict__,
                "advice": [a.__dict__ for a in advices],
                "expiry_calendar": cal_exp.strftime("%Y-%m-%d"),
            },
            indent=2,
        )
    )
    return advices, out
