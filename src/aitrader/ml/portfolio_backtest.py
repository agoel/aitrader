"""SPY portfolio backtest — simulate $10K following monthly news-driven predictions."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from aitrader.ml.backtest import _monthly_spy_backtest
from aitrader.ml.predict_config import PredictTuneConfig, load_predict_config
from aitrader.nlp.keyword_cache import load_keyword_cache
from aitrader.nlp.keywords import HORIZON_TRADING_DAYS, load_etf_closes
from aitrader.workspace import ensure_run_layout, update_meta

DEFAULT_CAPITAL_USD = 10_000
DEFAULT_LOOKBACK_YEARS = 5


def _position_from_signal(
    predicted_return: float,
    news_articles: int,
    *,
    min_news_confident: int,
) -> str:
    """Long SPY when news-backed bullish; otherwise cash."""
    if news_articles < min_news_confident:
        return "cash"
    if predicted_return > 0:
        return "long"
    return "cash"


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
        position = _position_from_signal(
            pred, news_n, min_news_confident=cfg.min_news_confident
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
        f"Simulate **${capital_usd:,.0f}** invested in **SPY only**, rebalanced monthly on "
        "news-driven 1-month predictions.",
        "",
        "## Rules",
        "",
        f"- **Long SPY (100%)** when `news_articles >= {cfg.min_news_confident}` and "
        "`predicted_return > 0`",
        "- **Cash (0%)** when no news signal or non-bullish forecast",
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
