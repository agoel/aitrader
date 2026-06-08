"""SPY portfolio backtest — simulate $10K following monthly news-driven predictions."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from aitrader.data.cot import cot_signal_at, ensure_cot_data
from aitrader.ml.backtest import _monthly_spy_backtest
from aitrader.ml.predict import _momentum_at
from aitrader.ml.predict_config import PredictTuneConfig, load_predict_config
from aitrader.ml.strategy_signals import position_from_row, row_signals
from aitrader.nlp.keyword_cache import load_keyword_cache
from aitrader.nlp.keywords import HORIZON_TRADING_DAYS, load_etf_closes
from aitrader.workspace import ensure_run_layout, update_meta

DEFAULT_CAPITAL_USD = 10_000
DEFAULT_LOOKBACK_YEARS = 5
DEFAULT_TRANCHE_PCT = 0.25
DEFAULT_LADDER_WEEK_DAYS = 7


def _strategy_rules_lines(cfg: PredictTuneConfig) -> list[str]:
    if cfg.strategy == "always_long":
        return ["- **Long SPY (100%)** every month (benchmark)"]
    if cfg.strategy == "cot_momentum":
        return [
            f"- **Strategy:** COT + momentum (`{cfg.combo_mode}`, min_votes={cfg.min_votes})",
            f"- **Long SPY** when momentum ≥ {cfg.momentum_threshold} and/or "
            f"COT signal ≥ {cfg.cot_threshold} (vote threshold applies)",
            "- **Cash** when signals fail the vote/and gate",
        ]
    if cfg.strategy == "sentiment_momentum":
        return [
            f"- **Strategy:** sentiment + momentum (`{cfg.combo_mode}`, min_votes={cfg.min_votes})",
            f"- **Long SPY** on news-backed ridge + sentiment ≥ {cfg.sentiment_threshold} "
            f"and/or momentum ≥ {cfg.momentum_threshold}",
            f"- **Momentum without news:** {cfg.allow_momentum_without_news}",
        ]
    if cfg.strategy == "triple_combo":
        return [
            f"- **Strategy:** sentiment + momentum + COT (`{cfg.combo_mode}`, min_votes={cfg.min_votes})",
            f"- Weights: sentiment={cfg.sentiment_weight}, momentum={cfg.momentum_weight}, "
            f"cot={cfg.cot_weight}",
            f"- Thresholds: sentiment≥{cfg.sentiment_threshold}, momentum≥{cfg.momentum_threshold}, "
            f"cot≥{cfg.cot_threshold}",
        ]
    if cfg.strategy == "momentum_only":
        return [
            f"- **Strategy:** momentum trend (threshold ≥ {cfg.momentum_threshold})",
        ]
    lines = [
        f"- **Long SPY (100%)** when `news_articles >= {cfg.min_news_confident}` and "
        "`predicted_return > 0`",
    ]
    if cfg.allow_momentum_without_news:
        lines.append(
            f"- **Or long** on momentum ≥ {cfg.momentum_threshold} when news is thin"
        )
    lines.append("- **Cash (0%)** otherwise")
    return lines


def _position_from_signal(
    predicted_return: float,
    news_articles: int,
    *,
    min_news_confident: int,
    sentiment: float = 0.0,
    momentum: float = 0.0,
    cot_signal: float = 0.0,
    config: PredictTuneConfig | None = None,
) -> str:
    """Long SPY vs cash — news ridge or multi-signal strategy."""
    cfg = config if config is not None else PredictTuneConfig(min_news_confident=min_news_confident)
    return position_from_row(
        predicted_return=predicted_return,
        news_articles=news_articles,
        sentiment=sentiment,
        momentum=momentum,
        cot_signal=cot_signal,
        config=cfg,
    )


def simulate_spy_portfolio(
    monthly: pd.DataFrame,
    *,
    capital_usd: float = DEFAULT_CAPITAL_USD,
    config: PredictTuneConfig | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Walk monthly predictions: invest full capital in SPY on bullish news months, else cash."""
    cfg = config or PredictTuneConfig()
    if monthly.empty:
        raise ValueError("No monthly backtest rows — run news ingest and predict backtest first.")

    df = monthly.sort_values("trading_day").copy()
    df["trading_day"] = pd.to_datetime(df["trading_day"])
    value = float(capital_usd)
    ledger: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        pred = float(row["predicted_return"])
        realized = float(row["realized_return"])
        news_n = int(row.get("news_articles", 0) or 0)
        sig = row_signals(row)
        position = _position_from_signal(
            pred,
            news_n,
            min_news_confident=cfg.min_news_confident,
            sentiment=sig["sentiment"],
            momentum=sig["momentum"],
            cot_signal=sig["cot_signal"],
            config=cfg,
        )
        period_return = realized if position == "long" else 0.0
        value_before = value
        value *= 1.0 + period_return
        ledger.append(
            {
                "trading_day": row["trading_day"].strftime("%Y-%m-%d"),
                "position": position,
                "predicted_return": round(pred, 6),
                "realized_return": round(realized, 6),
                "period_return": round(period_return, 6),
                "portfolio_value": round(value, 2),
                "news_articles": news_n,
                "cluster_id": row.get("cluster_id"),
                "macro_events": row.get("macro_events", ""),
                "cold_start": bool(row.get("cold_start", False)),
            }
        )

    ledger_df = pd.DataFrame(ledger)
    start = ledger_df["trading_day"].iloc[0]
    end = ledger_df["trading_day"].iloc[-1]
    months = len(ledger_df)
    years = max(months / 12.0, 1 / 12.0)
    total_return = value / capital_usd - 1.0
    cagr = (value / capital_usd) ** (1.0 / years) - 1.0 if value > 0 else -1.0

    long_months = int((ledger_df["position"] == "long").sum())
    cash_months = int((ledger_df["position"] == "cash").sum())
    strategy_compound = float(np.prod(1.0 + ledger_df["period_return"].to_numpy()) - 1.0)

    summary = {
        "capital_usd": capital_usd,
        "start_date": start,
        "end_date": end,
        "months": months,
        "final_value_usd": round(value, 2),
        "total_return_pct": round(total_return * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "strategy_compound_return_pct": round(strategy_compound * 100, 2),
        "long_months": long_months,
        "cash_months": cash_months,
        "pct_months_invested": round(100.0 * long_months / months, 1) if months else 0.0,
        "config_name": cfg.name,
        "min_news_confident": cfg.min_news_confident,
    }
    return ledger_df, summary


def _weekly_entry_days(
    spy: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    week_calendar_days: int = DEFAULT_LADDER_WEEK_DAYS,
) -> list[pd.Timestamp]:
    """Calendar-week entry anchors mapped to first SPY session on or after each date."""
    entries: list[pd.Timestamp] = []
    cursor = pd.Timestamp(start).normalize()
    end_ts = pd.Timestamp(end).normalize()
    idx = spy.index
    while cursor <= end_ts:
        on_or_after = idx[idx >= cursor]
        if len(on_or_after) == 0:
            break
        day = on_or_after[0]
        if not entries or day > entries[-1]:
            entries.append(day)
        cursor = cursor + pd.Timedelta(days=week_calendar_days)
    return entries


def simulate_weekly_ladder(
    run_dir: Path,
    *,
    capital_usd: float = DEFAULT_CAPITAL_USD,
    tranche_pct: float = DEFAULT_TRANCHE_PCT,
    horizon_days: int | None = None,
    start: str | None = None,
    end: str | None = None,
    always_invest: bool = True,
    config: PredictTuneConfig | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Weekly ladder: each week deploy ``tranche_pct`` of initial capital into a ~1-month SPY tranche.

    Example: $10K, 25% → $2,500 per week into a position held ~21 trading days; up to four
    overlapping tranches fully deploy capital at steady state.
    """
    horizon = horizon_days or HORIZON_TRADING_DAYS.get("1m", 21)
    spy = load_etf_closes(run_dir, "SPY")
    if spy.empty:
        raise ValueError("SPY OHLCV missing")

    cfg = config or PredictTuneConfig()
    cot_frame = None
    if not always_invest:
        try:
            cot_frame = ensure_cot_data(run_dir)
        except (OSError, RuntimeError):
            cot_frame = None

    tranche_principal = capital_usd * tranche_pct
    idx = spy.index
    eval_start = pd.Timestamp(start) if start else idx[horizon + 5]
    eval_end = pd.Timestamp(end) if end else idx[-1 - horizon]
    entry_days = _weekly_entry_days(spy, eval_start, eval_end)

    cash = float(capital_usd)
    active: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    opened = skipped = matured = 0

    for entry_day in entry_days:
        entry_loc = idx.get_loc(entry_day)
        # Mature tranches whose exit date has arrived
        still_active: list[dict[str, Any]] = []
        for t in active:
            if t["exit_loc"] <= entry_loc:
                exit_px = float(spy.iloc[t["exit_loc"]])
                cash += t["principal"] * (exit_px / t["entry_price"])
                matured += 1
            else:
                still_active.append(t)
        active = still_active

        go_long = True
        if not always_invest:
            mom = _momentum_at(spy, entry_day)
            cot_sig = cot_signal_at(cot_frame, entry_day) if cot_frame is not None else 0.0
            go_long = (
                position_from_row(
                    predicted_return=0.0,
                    news_articles=0,
                    momentum=mom,
                    cot_signal=cot_sig,
                    config=cfg,
                )
                == "long"
            )

        if not go_long:
            skipped += 1
            ledger.append(
                {
                    "entry_day": entry_day.strftime("%Y-%m-%d"),
                    "action": "skip",
                    "tranche_usd": 0.0,
                    "active_tranches": len(active),
                    "cash_usd": round(cash, 2),
                    "nav_usd": round(_ladder_nav(cash, active, spy, entry_loc), 2),
                }
            )
            continue

        if cash < tranche_principal:
            ledger.append(
                {
                    "entry_day": entry_day.strftime("%Y-%m-%d"),
                    "action": "no_cash",
                    "tranche_usd": 0.0,
                    "active_tranches": len(active),
                    "cash_usd": round(cash, 2),
                    "nav_usd": round(_ladder_nav(cash, active, spy, entry_loc), 2),
                }
            )
            continue

        exit_loc = entry_loc + horizon
        if exit_loc >= len(idx):
            continue

        entry_price = float(spy.iloc[entry_loc])
        cash -= tranche_principal
        active.append(
            {
                "entry_day": entry_day,
                "entry_loc": entry_loc,
                "exit_loc": exit_loc,
                "exit_day": idx[exit_loc],
                "entry_price": entry_price,
                "principal": tranche_principal,
            }
        )
        opened += 1
        ledger.append(
            {
                "entry_day": entry_day.strftime("%Y-%m-%d"),
                "action": "open",
                "tranche_usd": tranche_principal,
                "exit_day": idx[exit_loc].strftime("%Y-%m-%d"),
                "active_tranches": len(active),
                "cash_usd": round(cash, 2),
                "nav_usd": round(_ladder_nav(cash, active, spy, entry_loc), 2),
            }
        )

    end_loc = idx.get_loc(idx[idx <= eval_end][-1])
    for t in active:
        exit_px = float(spy.iloc[min(t["exit_loc"], end_loc)])
        cash += t["principal"] * (exit_px / t["entry_price"])
    final_nav = cash
    start_s = entry_days[0].strftime("%Y-%m-%d") if entry_days else str(eval_start.date())
    end_s = idx[end_loc].strftime("%Y-%m-%d")
    years = max((pd.Timestamp(end_s) - pd.Timestamp(start_s)).days / 365.25, 1 / 365.25)
    total_return = final_nav / capital_usd - 1.0
    cagr = (final_nav / capital_usd) ** (1.0 / years) - 1.0 if final_nav > 0 else -1.0

    summary = {
        "schedule": "weekly_ladder",
        "capital_usd": capital_usd,
        "tranche_pct": tranche_pct,
        "tranche_usd": tranche_principal,
        "horizon_trading_days": horizon,
        "always_invest": always_invest,
        "config_name": cfg.name if not always_invest else "always_long",
        "start_date": start_s,
        "end_date": end_s,
        "weeks": len(entry_days),
        "tranches_opened": opened,
        "tranches_skipped": skipped,
        "tranches_matured": matured,
        "final_value_usd": round(final_nav, 2),
        "total_return_pct": round(total_return * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
    }
    return pd.DataFrame(ledger), summary


def _ladder_nav(
    cash: float,
    active: list[dict[str, Any]],
    spy: pd.Series,
    loc: int,
) -> float:
    nav = cash
    px = float(spy.iloc[loc])
    for t in active:
        nav += t["principal"] * (px / t["entry_price"])
    return nav


def compare_portfolio_schedules(
    run_dir: str | Path,
    *,
    capital_usd: float = DEFAULT_CAPITAL_USD,
    lookback_years: int = DEFAULT_LOOKBACK_YEARS,
    news_window_days: int = 30,
    min_train_months: int = 12,
) -> tuple[Path, dict[str, Any]]:
    """Compare monthly signal strategy, weekly ladder (always), weekly ladder (signals), buy & hold."""
    root = ensure_run_layout(run_dir)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cfg = load_predict_config(root)
    llm_cache = load_keyword_cache(root)
    horizon_days = HORIZON_TRADING_DAYS.get("1m", 21)
    max_months = lookback_years * 12

    monthly = _monthly_spy_backtest(
        root,
        horizon_days,
        llm_cache=llm_cache,
        news_window_days=news_window_days,
        min_train_months=min_train_months,
        max_months=max_months,
        config=cfg,
    )
    if monthly.empty:
        raise RuntimeError("No monthly backtest rows for schedule comparison.")

    _, monthly_summary = simulate_spy_portfolio(
        monthly, capital_usd=capital_usd, config=cfg
    )
    start = monthly_summary["start_date"]
    end = monthly_summary["end_date"]

    ladder_always_ledger, ladder_always = simulate_weekly_ladder(
        root,
        capital_usd=capital_usd,
        start=start,
        end=end,
        always_invest=True,
    )
    ladder_signal_ledger, ladder_signal = simulate_weekly_ladder(
        root,
        capital_usd=capital_usd,
        start=start,
        end=end,
        always_invest=False,
        config=cfg,
    )
    bh = _buy_hold_spy(root, start, end, capital_usd=capital_usd)

    for row in (monthly_summary, ladder_always, ladder_signal):
        row["excess_return_pct"] = round(
            row["total_return_pct"] - bh["total_return_pct"], 2
        )

    comparison = {
        "period": f"{start} → {end}",
        "capital_usd": capital_usd,
        "buy_hold": bh,
        "monthly_signal": monthly_summary,
        "weekly_ladder_always": ladder_always,
        "weekly_ladder_signal": ladder_signal,
    }

    report_path = root / "reports" / f"portfolio_schedule_compare_{today}.md"
    lines = [
        f"# SPY schedule comparison — {today}",
        "",
        f"**Capital:** ${capital_usd:,.0f} | **Period:** {start} → {end}",
        "",
        "## Strategies",
        "",
        "1. **Buy & hold** — fully invested from day one",
        f"2. **Monthly signal** — `{cfg.name}`; full capital in/out each month",
        "3. **Weekly ladder (always)** — every 7 calendar days deploy **25%** "
        f"(${capital_usd * DEFAULT_TRANCHE_PCT:,.0f}) into a **{horizon_days}-trading-day** "
        "SPY tranche (up to 4 overlapping)",
        f"4. **Weekly ladder (signal)** — same ladder, but skip tranche when "
        f"`{cfg.name}` COT+momentum gate is cash",
        "",
        "## Results",
        "",
        "| Strategy | Final value | Total return | CAGR | Excess vs B&H |",
        "|----------|-------------|--------------|------|---------------|",
        f"| Buy & hold | ${bh['final_value_usd']:,.2f} | {bh['total_return_pct']:+.2f}% | "
        f"{bh['cagr_pct']:.2f}% | — |",
        f"| Monthly signal (`{cfg.name}`) | ${monthly_summary['final_value_usd']:,.2f} | "
        f"{monthly_summary['total_return_pct']:+.2f}% | {monthly_summary['cagr_pct']:.2f}% | "
        f"{monthly_summary['excess_return_pct']:+.2f} pp |",
        f"| Weekly ladder (always SPY) | ${ladder_always['final_value_usd']:,.2f} | "
        f"{ladder_always['total_return_pct']:+.2f}% | {ladder_always['cagr_pct']:.2f}% | "
        f"{ladder_always['excess_return_pct']:+.2f} pp |",
        f"| Weekly ladder (signal gated) | ${ladder_signal['final_value_usd']:,.2f} | "
        f"{ladder_signal['total_return_pct']:+.2f}% | {ladder_signal['cagr_pct']:.2f}% | "
        f"{ladder_signal['excess_return_pct']:+.2f} pp |",
        "",
        "### Weekly ladder detail (always SPY)",
        "",
        f"- Entry weeks: {ladder_always['weeks']}",
        f"- Tranches opened: {ladder_always['tranches_opened']}",
        f"- Tranche size: ${ladder_always['tranche_usd']:,.0f} ({ladder_always['tranche_pct']*100:.0f}% of initial capital)",
        "",
        "### Weekly ladder detail (signal gated)",
        "",
        f"- Tranches opened: {ladder_signal['tranches_opened']}",
        f"- Tranches skipped (cash): {ladder_signal['tranches_skipped']}",
        "",
        "## Takeaway",
        "",
    ]
    best = max(
        [
            ("Monthly signal", monthly_summary["final_value_usd"]),
            ("Weekly ladder (always)", ladder_always["final_value_usd"]),
            ("Weekly ladder (signal)", ladder_signal["final_value_usd"]),
            ("Buy & hold", bh["final_value_usd"]),
        ],
        key=lambda x: x[1],
    )
    lines.append(
        f"**Best on this window:** {best[0]} at **${best[1]:,.2f}**."
    )
    lines.append("")
    report_path.write_text("\n".join(lines) + "\n")

    ladder_always_ledger.to_csv(
        root / "reports" / f"weekly_ladder_always_{today}.csv", index=False
    )
    ladder_signal_ledger.to_csv(
        root / "reports" / f"weekly_ladder_signal_{today}.csv", index=False
    )
    return report_path, comparison


def _buy_hold_spy(
    run_dir: Path,
    start: str,
    end: str,
    *,
    capital_usd: float,
) -> dict[str, Any]:
    spy = load_etf_closes(run_dir, "SPY")
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    idx = spy.index
    start_px = spy.loc[idx[idx >= start_ts][0]] if len(idx[idx >= start_ts]) else spy.iloc[0]
    end_px = spy.loc[idx[idx <= end_ts][-1]] if len(idx[idx <= end_ts]) else spy.iloc[-1]
    bh_return = float(end_px / start_px - 1.0)
    final = capital_usd * (1.0 + bh_return)
    months = max(
        (end_ts.year - start_ts.year) * 12 + (end_ts.month - start_ts.month) + 1,
        1,
    )
    years = months / 12.0
    cagr = (final / capital_usd) ** (1.0 / years) - 1.0
    return {
        "final_value_usd": round(final, 2),
        "total_return_pct": round(bh_return * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
    }


def run_spy_portfolio_backtest(
    run_dir: str | Path,
    *,
    capital_usd: float = DEFAULT_CAPITAL_USD,
    lookback_years: int = DEFAULT_LOOKBACK_YEARS,
    news_window_days: int = 30,
    min_train_months: int = 12,
) -> tuple[Path, Path, dict[str, Any]]:
    """5-year SPY-only portfolio simulation vs buy-and-hold."""
    root = ensure_run_layout(run_dir)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cfg = load_predict_config(root)
    llm_cache = load_keyword_cache(root)
    horizon_days = HORIZON_TRADING_DAYS.get("1m", 21)
    max_months = lookback_years * 12

    monthly = _monthly_spy_backtest(
        root,
        horizon_days,
        llm_cache=llm_cache,
        news_window_days=news_window_days,
        min_train_months=min_train_months,
        max_months=max_months,
        config=cfg,
    )
    if monthly.empty:
        raise RuntimeError(
            "Portfolio backtest produced no monthly rows — check SPY OHLCV and news corpus."
        )

    ledger_df, summary = simulate_spy_portfolio(
        monthly, capital_usd=capital_usd, config=cfg
    )
    bh = _buy_hold_spy(
        root,
        summary["start_date"],
        summary["end_date"],
        capital_usd=capital_usd,
    )
    summary["buy_hold_final_usd"] = bh["final_value_usd"]
    summary["buy_hold_return_pct"] = bh["total_return_pct"]
    summary["buy_hold_cagr_pct"] = bh["cagr_pct"]
    summary["excess_return_pct"] = round(
        summary["total_return_pct"] - summary["buy_hold_return_pct"], 2
    )

    ledger_path = root / "reports" / f"portfolio_backtest_spy_{today}.csv"
    ledger_df.to_csv(ledger_path, index=False)

    lines = [
        f"# SPY portfolio backtest — {today}",
        "",
        f"Simulate **${capital_usd:,.0f}** invested in **SPY only**, rebalanced monthly.",
        "",
        "## Rules",
        "",
        *_strategy_rules_lines(cfg),
        f"- Walk-forward train window: {min_train_months} months before first trade",
        f"- Evaluation window: {lookback_years} years of month-ends (`max_months={max_months}`)",
        f"- Tuned config: `{cfg.name}`",
        "",
        "## Results",
        "",
        "| Metric | Strategy | Buy & hold SPY |",
        "|--------|----------|----------------|",
        f"| Final value | ${summary['final_value_usd']:,.2f} | ${summary['buy_hold_final_usd']:,.2f} |",
        f"| Total return | {summary['total_return_pct']:.2f}% | {summary['buy_hold_return_pct']:.2f}% |",
        f"| CAGR | {summary['cagr_pct']:.2f}% | {summary['buy_hold_cagr_pct']:.2f}% |",
        "",
        f"- **Period:** {summary['start_date']} → {summary['end_date']} ({summary['months']} months)",
        f"- **Months in SPY:** {summary['long_months']} ({summary['pct_months_invested']:.1f}%)",
        f"- **Months in cash:** {summary['cash_months']}",
        f"- **Excess return vs B&H:** {summary['excess_return_pct']:+.2f} pp",
        "",
        "## Artifacts",
        "",
        f"- `{ledger_path.name}` — monthly ledger (position, returns, portfolio value)",
        "",
    ]
    report_path = root / "reports" / f"portfolio_backtest_spy_{today}.md"
    report_path.write_text("\n".join(lines) + "\n")

    update_meta(
        root,
        {
            "L4": {
                "portfolio_backtest_spy": {
                    "date": today,
                    "capital_usd": capital_usd,
                    "final_value_usd": summary["final_value_usd"],
                    "total_return_pct": summary["total_return_pct"],
                    "buy_hold_return_pct": summary["buy_hold_return_pct"],
                    "report": str(report_path.relative_to(root)),
                }
            }
        },
    )
    return ledger_path, report_path, summary
