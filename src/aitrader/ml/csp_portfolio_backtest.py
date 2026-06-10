"""Compounding CSP put-spread portfolio backtest with Tier A/B and entry pricing modes."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from aitrader.ml.backtest import build_backtest_feature_cache
from aitrader.ml.bs_put_pricing import pick_bs_put_spread, simulate_daily_safe_exit
from aitrader.ml.csp_spread_advisor import (
    CSPSpreadParams,
    INDEX_ETF,
    INDEX_SCALE,
    UtilizationTier,
    WIDEN_OTM_MULT,
    _cycle_forecast,
    apply_utilization_tier,
    empirical_otm_pct,
)
from aitrader.ml.csp_spread_pricing import PutSpreadQuote, realized_vol
from aitrader.ml.option_range_study import monthly_option_cycles
from aitrader.ml.predict_config import load_predict_config
from aitrader.nlp.keyword_cache import load_keyword_cache
from aitrader.nlp.keywords import HORIZON_TRADING_DAYS, load_etf_closes
from aitrader.nlp.sentiment import IndexTag
from aitrader.workspace import ensure_run_layout

HORIZON_DAYS_1M = HORIZON_TRADING_DAYS.get("1m", 21)
MARGIN_PER_SPREAD_USD = 500.0  # 5 index pts × $100 multiplier
DEFAULT_START_EQUITY = 10_000.0
EntryPricing = Literal["black_scholes", "schwab_analytical"]
DEFAULT_SCHWAB_RATE_LIMIT_SEC = 0.35


def contracts_for_equity(equity: float, *, margin_per_spread: float = MARGIN_PER_SPREAD_USD) -> int:
    if equity < margin_per_spread:
        return 0
    return int(equity // margin_per_spread)


def _index_strikes_from_otm(
    spot_etf: float,
    otm_pct: float,
    *,
    spread_width_index: float,
) -> tuple[float, float, float, float]:
    """Return (short_etf, long_etf, short_index, long_index)."""
    short_etf = spot_etf * (1.0 - otm_pct)
    width_etf = spread_width_index / INDEX_SCALE
    long_etf = short_etf - width_etf
    short_index = short_etf * INDEX_SCALE
    long_index = long_etf * INDEX_SCALE
    return short_etf, long_etf, short_index, long_index


def _otm_for_action(
    closes: pd.Series,
    action: str,
    *,
    params: CSPSpreadParams,
) -> float:
    otm = empirical_otm_pct(closes, target_delta=params.target_delta)
    if action == "WIDEN":
        otm = min(otm * WIDEN_OTM_MULT, 0.14)
    return otm


def _price_spread_bs(
    spot_etf: float,
    closes: pd.Series,
    *,
    signal_day: pd.Timestamp,
    expiry_day: pd.Timestamp,
    dte: int,
    action: str,
    params: CSPSpreadParams,
) -> tuple[PutSpreadQuote | None, float, float, float, float]:
    hist = closes.loc[:signal_day].tail(25)
    vol = realized_vol(hist.tolist())
    spot_index = spot_etf * INDEX_SCALE
    otm = _otm_for_action(closes, action, params=params)
    short_etf, long_etf, short_idx, long_idx = _index_strikes_from_otm(
        spot_etf,
        otm,
        spread_width_index=params.spread_width_points,
    )
    quote = pick_bs_put_spread(
        spot_index,
        vol=vol,
        dte_days=max(1, dte),
        spread_width=params.spread_width_points,
        credit_lo=params.target_credit_band[0],
        credit_hi=params.target_credit_band[1],
        entry_min_safe_prob=params.entry_min_safe_prob,
        max_entry_safe_prob=params.max_entry_safe_prob,
        min_short_delta=params.min_short_delta,
        expiry=expiry_day.strftime("%Y-%m-%d"),
    )
    if quote is not None:
        short_idx = quote.short_leg.strike
        long_idx = quote.long_leg.strike
        short_etf = short_idx / INDEX_SCALE
        long_etf = long_idx / INDEX_SCALE
    return quote, vol, short_etf, long_etf, short_idx


def _price_spread_schwab(
    client: Any,
    index: IndexTag,
    spot_etf: float,
    closes: pd.Series,
    *,
    signal_day: pd.Timestamp,
    expiry_day: pd.Timestamp,
    dte: int,
    params: CSPSpreadParams,
    rate_limit_sec: float = DEFAULT_SCHWAB_RATE_LIMIT_SEC,
) -> tuple[PutSpreadQuote | None, float, str | None]:
    from aitrader.ml.csp_spread_pricing import fetch_index_put_spread

    hist = closes.loc[:signal_day].tail(25)
    vol = realized_vol(hist.tolist())
    spot_index = spot_etf * INDEX_SCALE
    try:
        quote = fetch_index_put_spread(
            client,
            index,
            expiry=expiry_day.date(),
            target_credit_lo=params.target_credit_band[0],
            target_credit_hi=params.target_credit_band[1],
            spread_width=params.spread_width_points,
            entry_min_safe_prob=params.entry_min_safe_prob,
            max_entry_safe_prob=params.max_entry_safe_prob,
            min_short_delta=params.min_short_delta,
            analytical=True,
            underlying_price=spot_index,
            volatility=vol,
            days_to_expiration=max(1, dte),
        )
    except Exception as exc:
        time.sleep(rate_limit_sec)
        return None, vol, str(exc)
    time.sleep(rate_limit_sec)
    return quote, vol, None


def _price_spread_entry(
    index: IndexTag,
    spot_etf: float,
    closes: pd.Series,
    *,
    signal_day: pd.Timestamp,
    expiry_day: pd.Timestamp,
    dte: int,
    action: str,
    params: CSPSpreadParams,
    entry_pricing: EntryPricing,
    schwab_client: Any | None = None,
    rate_limit_sec: float = DEFAULT_SCHWAB_RATE_LIMIT_SEC,
) -> tuple[PutSpreadQuote | None, float, str, str | None]:
    """Return (quote, vol, pricing_source, error)."""
    if entry_pricing == "schwab_analytical":
        if schwab_client is None:
            return None, 0.0, "schwab_analytical", "Schwab client not configured"
        quote, vol, err = _price_spread_schwab(
            schwab_client,
            index,
            spot_etf,
            closes,
            signal_day=signal_day,
            expiry_day=expiry_day,
            dte=dte,
            params=params,
            rate_limit_sec=rate_limit_sec,
        )
        if quote is not None:
            return quote, vol, "schwab_analytical", None
        # Schwab ANALYTICAL has no historical calendar — often misses the credit band.
        quote, vol, _s, _l, _k = _price_spread_bs(
            spot_etf,
            closes,
            signal_day=signal_day,
            expiry_day=expiry_day,
            dte=dte,
            action=action,
            params=params,
        )
        if quote is not None:
            return quote, vol, "black_scholes_fallback", err or "no schwab spread in credit band"
        return None, vol, "schwab_analytical", err or "no spread in credit band"

    quote, vol, _s, _l, _k = _price_spread_bs(
        spot_etf,
        closes,
        signal_day=signal_day,
        expiry_day=expiry_day,
        dte=dte,
        action=action,
        params=params,
    )
    return quote, vol, "black_scholes", None


def _write_svg_chart(
    path: Path,
    series: dict[str, pd.Series],
    *,
    title: str,
    width: int = 900,
    height: int = 420,
) -> None:
    """Minimal SVG cumulative-return chart (no matplotlib dependency)."""
    if not series:
        path.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>\n")
        return

    aligned = pd.DataFrame(series).dropna(how="all")
    if aligned.empty:
        path.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>\n")
        return

    xmin, xmax = 0, len(aligned) - 1
    ymin = float(aligned.min().min())
    ymax = float(aligned.max().max())
    pad = max(2.0, (ymax - ymin) * 0.08)
    ymin -= pad
    ymax += pad
    if ymax <= ymin:
        ymax = ymin + 1.0

    colors = {
        "SPX book": "#2563eb",
        "RUT book": "#dc2626",
        "Combined": "#059669",
        "SPY buy & hold": "#6b7280",
    }

    def xpx(i: int) -> float:
        return 70 + (width - 100) * (i - xmin) / max(1, xmax - xmin)

    def ypx(v: float) -> float:
        return height - 50 - (height - 90) * (v - ymin) / (ymax - ymin)

    lines: list[str] = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}'>",
        f"<rect width='{width}' height='{height}' fill='#fafafa'/>",
        f"<text x='{width//2}' y='24' text-anchor='middle' font-size='16' font-family='sans-serif'>{title}</text>",
        f"<line x1='70' y1='{height-50}' x2='{width-30}' y2='{height-50}' stroke='#ccc'/>",
        f"<line x1='70' y1='40' x2='70' y2='{height-50}' stroke='#ccc'/>",
        f"<text x='12' y='{height//2}' font-size='11' font-family='sans-serif' transform='rotate(-90 12,{height//2})'>Return %</text>",
    ]

    for col in aligned.columns:
        pts = []
        for i, val in enumerate(aligned[col].tolist()):
            if pd.isna(val):
                continue
            pts.append(f"{xpx(i):.1f},{ypx(float(val)):.1f}")
        if len(pts) < 2:
            continue
        color = colors.get(col, "#111827")
        lines.append(
            f"<polyline fill='none' stroke='{color}' stroke-width='2' points='{' '.join(pts)}'/>"
        )
        lines.append(
            f"<text x='{width-28}' y='{ypx(float(aligned[col].dropna().iloc[-1])):.0f}' "
            f"font-size='11' font-family='sans-serif' fill='{color}' text-anchor='end'>{col}</text>"
        )

    lines.append("</svg>\n")
    path.write_text("\n".join(lines))


def schwab_analytical_spot_check(
    run_dir: Path,
    samples: list[dict[str, Any]],
    *,
    token_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Compare BS credits to Schwab ANALYTICAL for a handful of backtest months."""
    try:
        from aitrader.data.schwab import SchwabClient
        from aitrader.ml.csp_spread_pricing import fetch_spx_put_spread
    except Exception:
        return [{"error": "Schwab client unavailable"}]

    try:
        client = SchwabClient.from_token_path(token_path)
    except Exception as exc:
        return [{"error": f"Schwab auth: {exc}"}]

    rows: list[dict[str, Any]] = []
    for row in samples[:5]:
        if row.get("index") != "SPX":
            continue
        try:
            expiry = pd.Timestamp(row["expiry_day"]).date()
            spot_idx = float(row["spot_index"])
            vol = float(row["vol"])
            dte = int(row["trading_days_to_expiry"])
            schwab_q = fetch_spx_put_spread(
                client,
                expiry=expiry,
                analytical=True,
                underlying_price=spot_idx,
                volatility=vol,
                days_to_expiration=dte,
            )
            rows.append(
                {
                    "expiry_month": row["expiry_month"],
                    "bs_credit": row.get("credit_per_share"),
                    "schwab_credit": schwab_q.credit_mid if schwab_q else None,
                    "bs_short": row.get("short_strike_index"),
                    "schwab_short": schwab_q.short_leg.strike if schwab_q else None,
                    "vol": vol,
                    "spot_index": spot_idx,
                }
            )
        except Exception as exc:
            rows.append({"expiry_month": row.get("expiry_month"), "error": str(exc)})
    return rows


def run_csp_portfolio_backtest(
    run_dir: str | Path,
    *,
    lookback_years: int = 10,
    indices: tuple[IndexTag, ...] = ("SPX", "RUT"),
    params: CSPSpreadParams | None = None,
    news_window_days: int = 30,
    start_equity: float = DEFAULT_START_EQUITY,
    schwab_spot_check: bool = True,
    token_path: Path | str | None = None,
    utilization_tier: UtilizationTier = "B",
    entry_pricing: EntryPricing = "black_scholes",
    schwab_rate_limit_sec: float = DEFAULT_SCHWAB_RATE_LIMIT_SEC,
) -> tuple[pd.DataFrame, dict[str, Any], Path, Path, Path]:
    root = ensure_run_layout(run_dir)
    p = params or CSPSpreadParams()
    cfg = load_predict_config(root)
    llm_cache = load_keyword_cache(root)
    spy = load_etf_closes(root, "SPY")

    schwab_client = None
    if entry_pricing == "schwab_analytical":
        try:
            from aitrader.data.schwab import SchwabClient

            schwab_client = SchwabClient.from_token_path(token_path)
        except Exception as exc:
            raise RuntimeError(f"Schwab ANALYTICAL entry requires valid token: {exc}") from exc
    if spy.empty:
        raise RuntimeError("SPY OHLCV missing — run `aitrader data yahoo --years 11`")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    feature_cache = build_backtest_feature_cache(
        root,
        HORIZON_DAYS_1M,
        llm_cache=llm_cache,
        news_window_days=news_window_days,
        min_train_months=12,
        max_months=lookback_years * 12 + 12,
        quiet=True,
    )
    if feature_cache is None:
        raise RuntimeError("Insufficient history for portfolio backtest")

    eval_end = spy.index[-1]
    eval_start = eval_end - pd.DateOffset(years=lookback_years)
    cycles = monthly_option_cycles(spy.index, start=eval_start, end=eval_end)

    equity: dict[IndexTag, float] = {idx: start_equity for idx in indices}
    ledger: list[dict[str, Any]] = []

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

            base_action = row["action"]
            action, traded = apply_utilization_tier(
                base_action,
                crash_veto=bool(row.get("crash_veto")),
                tier=utilization_tier,
            )
            equity_start = equity[index]
            contracts = 0
            credit_usd = 0.0
            credit_pc = 0.0
            pnl = 0.0
            vol = 0.0
            short_idx = long_idx = 0.0
            assigned = False
            exit_outcome = ""
            exit_day = None
            exit_safe_prob = None
            entry_pricing_source = ""
            entry_pricing_error = None

            if traded and equity_start < MARGIN_PER_SPREAD_USD:
                traded = False
                action = "SKIP"

            if traded:
                etf = INDEX_ETF[index]
                closes = load_etf_closes(root, etf)
                spot_etf = float(closes.loc[signal_day])
                dte = int(row["trading_days_to_expiry"])
                quote, vol, entry_pricing_source, entry_pricing_error = _price_spread_entry(
                    index,
                    spot_etf,
                    closes,
                    signal_day=signal_day,
                    expiry_day=expiry_day,
                    dte=dte,
                    action=action,
                    params=p,
                    entry_pricing=entry_pricing,
                    schwab_client=schwab_client,
                    rate_limit_sec=schwab_rate_limit_sec,
                )
                if quote is None:
                    traded = False
                    action = "SKIP"
                else:
                    credit_pc = quote.credit_mid
                    contracts = contracts_for_equity(equity_start)
                    if contracts <= 0:
                        traded = False
                        action = "SKIP"
                    else:
                        credit_usd = credit_pc * 100.0 * contracts
                        short_idx = quote.short_leg.strike
                        long_idx = quote.long_leg.strike
                        exit_result = simulate_daily_safe_exit(
                            closes,
                            signal_day=signal_day,
                            expiry_day=expiry_day,
                            short_strike_index=short_idx,
                            long_strike_index=long_idx,
                            entry_credit_per_share=credit_pc,
                            contracts=contracts,
                            index_scale=INDEX_SCALE,
                            exit_min_safe_prob=p.min_safe_prob,
                        )
                        assigned = exit_result.assigned
                        pnl = exit_result.pnl_usd
                        exit_outcome = exit_result.outcome
                        exit_day = exit_result.exit_day
                        exit_safe_prob = exit_result.exit_safe_prob
                        equity[index] = max(0.0, equity_start + pnl)

            ledger.append(
                {
                    "expiry_month": label,
                    "index": index,
                    "signal_day": row["signal_day"],
                    "expiry_day": row["expiry_day"],
                    "base_action": base_action,
                    "action": action,
                    "traded": traded,
                    "crash_veto": bool(row.get("crash_veto")),
                    "equity_start": round(equity_start, 2),
                    "contracts": contracts,
                    "credit_per_share": round(credit_pc, 4) if traded else 0.0,
                    "credit_usd": round(credit_usd, 2),
                    "vol": round(vol, 4) if traded else 0.0,
                    "short_strike_index": round(short_idx, 1) if traded else 0.0,
                    "long_strike_index": round(long_idx, 1) if traded else 0.0,
                    "spot_index": row["index_spot"],
                    "spot_at_expiry_index": round(float(row["spot_at_expiry"]) * INDEX_SCALE, 1)
                    if row.get("spot_at_expiry") is not None
                    else None,
                    "assigned": assigned,
                    "exit_outcome": exit_outcome,
                    "exit_day": exit_day,
                    "exit_safe_prob": exit_safe_prob,
                    "pnl_usd": round(pnl, 2),
                    "equity_end": round(equity[index], 2),
                    "safety_score": row["safety_score"],
                    "expected_return": row["expected_return"],
                    "trading_days_to_expiry": row["trading_days_to_expiry"],
                    "entry_pricing": entry_pricing_source,
                    "entry_pricing_error": entry_pricing_error,
                    "exit_pricing": "black_scholes",
                }
            )

    df = pd.DataFrame(ledger)
    if df.empty:
        raise RuntimeError("No portfolio backtest cycles")

    # Cumulative return series by book (at each expiry month, last row per month per index)
    cum_rows: list[dict[str, Any]] = []
    for label in sorted(df["expiry_month"].unique()):
        sub = df[df["expiry_month"] == label]
        point: dict[str, Any] = {"expiry_month": label}
        combined_eq = 0.0
        for index in indices:
            idx_sub = sub[sub["index"] == index]
            eq = float(idx_sub["equity_end"].iloc[-1]) if len(idx_sub) else equity.get(index, start_equity)
            point[f"{index}_equity"] = eq
            point[f"{index}_return_pct"] = round(100 * (eq / start_equity - 1), 2)
            combined_eq += eq
        point["combined_equity"] = round(combined_eq, 2)
        point["combined_return_pct"] = round(100 * (combined_eq / (start_equity * len(indices)) - 1), 2)
        cum_rows.append(point)
    cum_df = pd.DataFrame(cum_rows)

    # SPY buy-and-hold on combined notional
    spy_start = float(spy.loc[pd.Timestamp(cycles[0][0])]) if cycles else float(spy.iloc[0])
    spy_bh: list[float] = []
    for label in cum_df["expiry_month"]:
        exp_rows = df[(df["expiry_month"] == label)]
        if exp_rows.empty:
            spy_bh.append(float("nan"))
            continue
        exp_day = pd.Timestamp(exp_rows["expiry_day"].iloc[0])
        if exp_day in spy.index:
            spy_px = float(spy.loc[exp_day])
        else:
            prior = spy.index[spy.index <= exp_day]
            spy_px = float(spy.loc[prior[-1]]) if len(prior) else spy_start
        ret = 100 * (spy_px / spy_start - 1)
        spy_bh.append(round(ret, 2))
    cum_df["spy_buyhold_return_pct"] = spy_bh

    traded_df = df[df["traded"]]
    schwab_entries = int((traded_df["entry_pricing"] == "schwab_analytical").sum()) if len(traded_df) else 0
    bs_fallback_entries = int((traded_df["entry_pricing"] == "black_scholes_fallback").sum()) if len(traded_df) else 0
    months_per_index = len(df) // len(indices)
    utilization = 100 * len(traded_df) / max(len(df), 1)
    final_eq = {idx: equity[idx] for idx in indices}
    combined_final = sum(final_eq.values())
    years = lookback_years
    initial_combined = start_equity * len(indices)
    if years > 0 and combined_final > 0 and initial_combined > 0:
        combined_cagr = 100 * ((combined_final / initial_combined) ** (1 / years) - 1)
    elif combined_final <= 0:
        combined_cagr = -100.0
    else:
        combined_cagr = 0.0

    spot_check: list[dict[str, Any]] = []
    if schwab_spot_check and entry_pricing == "black_scholes":
        spx_traded = traded_df[traded_df["index"] == "SPX"].sort_values("expiry_day")
        samples = spx_traded.tail(5).to_dict("records")
        spot_check = schwab_analytical_spot_check(root, samples, token_path=token_path)

    peak_combined = float(cum_df["combined_equity"].max()) if len(cum_df) else combined_final
    peak_row = cum_df.loc[cum_df["combined_equity"].idxmax()] if len(cum_df) else None
    summary: dict[str, Any] = {
        "lookback_years": lookback_years,
        "tier": utilization_tier,
        "entry_pricing": entry_pricing,
        "exit_pricing": "black_scholes",
        "schwab_entry_trades": schwab_entries,
        "bs_fallback_entry_trades": bs_fallback_entries,
        "start_equity_per_book": start_equity,
        "margin_per_spread": MARGIN_PER_SPREAD_USD,
        "confidence_z": cfg.confidence_z,
        "cycles_per_index": months_per_index,
        "months_traded": len(traded_df),
        "utilization_pct": round(utilization, 1),
        "assignment_rate_pct": round(
            100 * traded_df["assigned"].mean() if len(traded_df) else 0.0, 1
        ),
        "early_exit_rate_pct": round(
            100 * (traded_df["exit_outcome"] == "early_exit").mean() if len(traded_df) else 0.0,
            1,
        ),
        "exit_min_safe_prob": p.min_safe_prob,
        "credit_band": list(p.target_credit_band),
        "peak_combined_equity": round(peak_combined, 2),
        "peak_month": str(peak_row["expiry_month"]) if peak_row is not None else "",
        "final_equity": {k: round(v, 2) for k, v in final_eq.items()},
        "combined_final_equity": round(combined_final, 2),
        "combined_cagr_pct": round(combined_cagr, 2),
        "schwab_spot_check": spot_check,
    }

    tier_tag = utilization_tier.lower()
    pricing_tag = "schwab" if entry_pricing == "schwab_analytical" else "bs"
    slug = f"{tier_tag}_{pricing_tag}"
    report = root / "reports" / f"csp_portfolio_backtest_{slug}_{today}.md"
    csv_path = root / "reports" / f"csp_portfolio_backtest_{slug}_{today}.csv"
    cum_csv = root / "reports" / f"csp_portfolio_backtest_cumulative_{slug}_{today}.csv"
    chart_path = root / "reports" / f"csp_portfolio_backtest_{slug}_{today}.svg"

    df.to_csv(csv_path, index=False)
    cum_df.to_csv(cum_csv, index=False)

    chart_series = {
        "SPX book": cum_df.set_index("expiry_month")["SPX_return_pct"],
        "RUT book": cum_df.set_index("expiry_month")["RUT_return_pct"],
        "Combined": cum_df.set_index("expiry_month")["combined_return_pct"],
        "SPY buy & hold": cum_df.set_index("expiry_month")["spy_buyhold_return_pct"],
    }
    _write_svg_chart(
        chart_path,
        chart_series,
        title=(
            f"CSP put-spread portfolio — {lookback_years}y Tier {utilization_tier} "
            f"({'Schwab entry' if entry_pricing == 'schwab_analytical' else 'BS entry'})"
        ),
    )

    lines = [
        f"# CSP portfolio backtest — {today}",
        "",
        f"**Period:** {lookback_years} years ending {eval_end.strftime('%Y-%m-%d')}",
        f"**Tier {utilization_tier}:** "
        + (
            "SELL/WIDEN/SELL_OTM only when gates pass"
            if utilization_tier == "A"
            else "trade WIDEN unless crash_veto"
        )
        + (
            " | **Entry:** Schwab ANALYTICAL"
            if entry_pricing == "schwab_analytical"
            else " | **Entry:** Black-Scholes"
        ),
        f"**Exit:** daily BS mark — close first day safe prob &lt; {p.min_safe_prob*100:.0f}% | "
        f"**Entry credit:** {p.target_credit_band[0]:.2f}–{p.target_credit_band[1]:.2f} idx pts, furthest OTM",
        f"**Books:** ${start_equity:,.0f} SPX + ${start_equity:,.0f} RUT | "
        f"**Contracts:** `floor(equity / {MARGIN_PER_SPREAD_USD:.0f})` | "
        f"**confidence_z:** {cfg.confidence_z}",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Utilization (traded / all cycles) | {summary['utilization_pct']}% ({summary['months_traded']} trades) |",
    ]
    if entry_pricing == "schwab_analytical":
        lines.append(
            f"| Entry priced via Schwab / BS fallback | {summary['schwab_entry_trades']} / "
            f"{summary['bs_fallback_entry_trades']} |"
        )
    lines.extend(
        [
        f"| Assignment rate (traded, held to expiry) | {summary['assignment_rate_pct']}% |",
        f"| Early exit rate (safe &lt; {p.min_safe_prob*100:.0f}%) | {summary['early_exit_rate_pct']}% |",
        ]
    )
    lines.extend(
        [
        f"| Final SPX book | ${final_eq.get('SPX', 0):,.2f} |",
        f"| Final RUT book | ${final_eq.get('RUT', 0):,.2f} |",
        f"| Peak combined | ${summary['peak_combined_equity']:,.2f} ({summary['peak_month']}) |",
        f"| Combined final | ${combined_final:,.2f} |",
        f"| Combined CAGR | {summary['combined_cagr_pct']}% |",
        "",
        "## Cumulative returns (last 12 months)",
        "",
        "| Expiry | SPX % | RUT % | Combined % | SPY B&H % |",
        "|--------|-------|-------|------------|----------|",
        ]
    )
    for _, r in cum_df.tail(12).iterrows():
        lines.append(
            f"| {r['expiry_month']} | {r['SPX_return_pct']} | {r['RUT_return_pct']} | "
            f"{r['combined_return_pct']} | {r['spy_buyhold_return_pct']} |"
        )

    if spot_check:
        lines.extend(["", "## Schwab ANALYTICAL spot-check (recent SPX months)", ""])
        for sc in spot_check:
            if "error" in sc and len(sc) == 1:
                lines.append(f"- {sc['error']}")
            elif "error" in sc:
                lines.append(f"- {sc.get('expiry_month')}: {sc['error']}")
            else:
                lines.append(
                    f"- {sc['expiry_month']}: BS {sc['bs_credit']} vs Schwab {sc['schwab_credit']} "
                    f"(short {sc['bs_short']} vs {sc['schwab_short']})"
                )

    lines.extend(
        [
            "",
            "## Artifacts",
            f"- `{csv_path.name}` — monthly ledger",
            f"- `{cum_csv.name}` — cumulative return table",
            f"- `{chart_path.name}` — cumulative return chart",
        ]
    )
    report.write_text("\n".join(lines) + "\n")
    return df, summary, report, chart_path, cum_csv
