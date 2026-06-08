"""Self-learning loop for L4 prediction — tune config until objective gates pass."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

TuneObjective = Literal["profit", "composite", "ic"]

import pandas as pd

from aitrader.ml.backtest import (
    build_backtest_feature_cache,
    score_backtest_from_cache,
    _score_monthly_spy_from_features,
    _summarize_slice,
)
from aitrader.ml.portfolio_backtest import (
    DEFAULT_CAPITAL_USD,
    DEFAULT_LOOKBACK_YEARS,
    _buy_hold_spy,
    simulate_spy_portfolio,
)
from aitrader.agent_rsi import probe_backtest_performance
from aitrader.ml.predict_config import (
    TUNE_CANDIDATES,
    TUNE_DEFAULT_CAPITAL_USD,
    TUNE_MAX_ROUNDS,
    TUNE_MIN_COVERAGE,
    TUNE_MIN_HIT_RATE,
    TUNE_MIN_NEWS_IC,
    TUNE_MIN_NEWS_ROWS,
    TUNE_MIN_PORTFOLIO_EXCESS,
    PredictTuneConfig,
    expand_tune_candidates,
    save_predict_config,
)
from aitrader.nlp.keyword_cache import load_keyword_cache
from aitrader.nlp.keywords import HORIZON_TRADING_DAYS, _pearson_ic
from aitrader.progress import RunProgress
from aitrader.workspace import ensure_run_layout, update_meta

LEARN_PIPELINE = "predict.tune"


def _monthly_rows(bt: pd.DataFrame) -> pd.DataFrame:
    if bt.empty:
        return bt
    if "article_id" in bt.columns:
        return bt[bt["article_id"].isna()].copy()
    return bt.copy()


def evaluate_portfolio_metrics(
    run_dir: Path,
    monthly: pd.DataFrame,
    config: PredictTuneConfig,
    *,
    capital_usd: float = TUNE_DEFAULT_CAPITAL_USD,
) -> dict[str, Any]:
    if monthly.empty:
        return {
            "final_value_usd": capital_usd,
            "total_return_pct": 0.0,
            "cagr_pct": 0.0,
            "excess_return_pct": -100.0,
            "long_months": 0,
            "pct_months_invested": 0.0,
        }
    _, summary = simulate_spy_portfolio(monthly, capital_usd=capital_usd, config=config)
    bh = _buy_hold_spy(
        run_dir,
        summary["start_date"],
        summary["end_date"],
        capital_usd=capital_usd,
    )
    summary["buy_hold_return_pct"] = bh["total_return_pct"]
    summary["excess_return_pct"] = round(
        summary["total_return_pct"] - bh["total_return_pct"], 2
    )
    return summary


def _composite_tune_score(
    metrics: dict[str, Any],
    portfolio: dict[str, Any],
    overall: dict[str, Any],
) -> float:
    """Rank configs: portfolio P&L first, then forecast quality."""
    score = 0.0
    excess = float(portfolio.get("excess_return_pct") or 0)
    total = float(portfolio.get("total_return_pct") or 0)
    invested = float(portfolio.get("pct_months_invested") or 0)
    score += excess * 0.3
    score += total * 0.12
    if excess > 0:
        score += 8.0
    if invested >= 40:
        score += 2.0
    elif invested < 15:
        score -= 5.0
    ic = metrics.get("ic")
    if ic is not None:
        score += abs(float(ic)) * 4.0
    overall_ic = overall.get("ic")
    if overall_ic is not None:
        score += abs(float(overall_ic)) * 2.0
    hit_rate = metrics.get("hit_rate")
    if hit_rate is not None:
        score += float(hit_rate) * 2.5
    coverage = metrics.get("coverage")
    if coverage is not None:
        score += float(coverage) * 0.5
    if metrics.get("certainty") == "high":
        score += 3.0
    elif metrics.get("certainty") == "medium":
        score += 1.5
    return score


def _round_leader_doc(round_doc: dict[str, Any]) -> dict[str, Any]:
    cfg = round_doc.get("config", {})
    m = round_doc.get("metrics", {})
    p = round_doc.get("portfolio", {})
    return {
        "round": round_doc.get("round"),
        "config": cfg.get("name"),
        "ic": m.get("ic"),
        "hit_rate": m.get("hit_rate"),
        "final_value_usd": p.get("final_value_usd"),
        "excess_return_pct": p.get("excess_return_pct"),
        "composite_score": round_doc.get("composite_score"),
    }


def evaluate_tune_passes(
    metrics: dict[str, Any],
    portfolio: dict[str, Any],
) -> dict[str, Any]:
    """Forecast gates + optional portfolio excess gate (self-learning stop condition)."""
    base = dict(metrics)
    forecast_pass = bool(metrics.get("passes"))
    excess = float(portfolio.get("excess_return_pct") or -999)
    portfolio_ok = excess >= TUNE_MIN_PORTFOLIO_EXCESS
    base["portfolio_excess_pct"] = excess
    base["passes_forecast"] = forecast_pass
    base["passes_portfolio"] = portfolio_ok
    base["passes_full"] = forecast_pass and portfolio_ok
    if base["passes_full"]:
        base["certainty"] = "high"
    elif forecast_pass or portfolio_ok:
        base["certainty"] = metrics.get("certainty", "medium")
    else:
        base["certainty"] = metrics.get("certainty", "low")
    base["passes"] = base["passes_full"]
    return base


def _coverage(df: pd.DataFrame) -> float:
    if df.empty or "confidence_lower" not in df.columns:
        return 0.0
    ok = 0
    for _, row in df.iterrows():
        lo = row.get("confidence_lower")
        hi = row.get("confidence_upper")
        real = row.get("realized_return")
        if lo is None or hi is None or pd.isna(lo) or pd.isna(hi):
            continue
        if lo <= real <= hi:
            ok += 1
    return ok / len(df) if len(df) else 0.0


def evaluate_news_backed_metrics(
    df: pd.DataFrame,
    *,
    overall: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Metrics on rows with news signal (news_articles >= 1)."""
    if df.empty:
        return {
            "n": 0,
            "ic": None,
            "hit_rate": None,
            "coverage": None,
            "passes": False,
            "certainty": "low",
        }
    news = df
    if "news_articles" in df.columns:
        news = df[df["news_articles"].fillna(0) >= 1]
    if len(news) < 2:
        return {
            "n": len(news),
            "ic": None,
            "hit_rate": None,
            "coverage": None,
            "passes": False,
            "certainty": "low",
        }
    pred = news["predicted_return"].to_numpy()
    real = news["realized_return"].to_numpy()
    ic = _pearson_ic(pred.tolist(), real.tolist())
    hits = sum((p > 0) == (r > 0) for p, r in zip(pred, real) if abs(p) > 1e-8)
    hit_rate = hits / max(1, sum(1 for p in pred if abs(p) > 1e-8))
    cov = _coverage(news)
    overall_ic = (overall or {}).get("ic")
    strict = (
        len(news) >= TUNE_MIN_NEWS_ROWS
        and abs(ic) >= TUNE_MIN_NEWS_IC
        and hit_rate >= TUNE_MIN_HIT_RATE
        and cov >= TUNE_MIN_COVERAGE
    )
    pragmatic = (
        len(news) >= TUNE_MIN_NEWS_ROWS
        and hit_rate >= TUNE_MIN_HIT_RATE
        and cov >= TUNE_MIN_COVERAGE
        and (
            abs(ic) >= 0.05
            or (overall_ic is not None and abs(float(overall_ic)) >= 0.10)
        )
    )
    passes = bool(strict or pragmatic)
    if strict:
        certainty = "high"
    elif pragmatic:
        certainty = "medium"
    else:
        certainty = "low"
    return {
        "n": int(len(news)),
        "ic": round(float(ic), 4),
        "hit_rate": round(float(hit_rate), 4),
        "coverage": round(float(cov), 4),
        "overall_ic": float(overall_ic) if overall_ic is not None else None,
        "passes": passes,
        "certainty": certainty,
    }


def backtest_with_config(
    run_dir: Path,
    config: PredictTuneConfig,
    *,
    news_window_days: int = 30,
    feature_cache=None,
    monthly_only: bool = False,
) -> pd.DataFrame:
    if feature_cache is None:
        llm_cache = load_keyword_cache(run_dir)
        feature_cache = build_backtest_feature_cache(
            run_dir,
            HORIZON_TRADING_DAYS["1m"],
            llm_cache=llm_cache,
            news_window_days=news_window_days,
            pipeline=LEARN_PIPELINE,
        )
    if feature_cache is None:
        return pd.DataFrame()
    if monthly_only:
        return _score_monthly_spy_from_features(
            feature_cache, config, pipeline=LEARN_PIPELINE, quiet=True
        )
    return score_backtest_from_cache(
        feature_cache, config, pipeline=LEARN_PIPELINE, quiet=True
    )


def run_prediction_tune(
    run_dir: str | Path,
    *,
    max_rounds: int = TUNE_MAX_ROUNDS,
    news_window_days: int = 30,
    capital_usd: float = TUNE_DEFAULT_CAPITAL_USD,
    use_grid: bool = True,
    run_probe: bool = True,
    objective: TuneObjective = "composite",
) -> dict[str, Any]:
    root = ensure_run_layout(run_dir)
    learn_dir = root / "learning"
    learn_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rounds: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    best_score = -1.0
    best_ic: dict[str, Any] | None = None
    best_ic_val = -1.0
    best_portfolio: dict[str, Any] | None = None
    best_portfolio_usd = -1.0

    if run_probe:
        probe = probe_backtest_performance(root, news_window_days=news_window_days, quiet=True)
        if not probe.get("passes_gate"):
            raise RuntimeError(
                "Tune blocked: backtest perf probe failed — fix hot path (agent_rsi/) before full tune"
            )

    llm_cache = load_keyword_cache(root)
    eval_months = DEFAULT_LOOKBACK_YEARS * 12
    feature_cache = build_backtest_feature_cache(
        root,
        HORIZON_TRADING_DAYS["1m"],
        llm_cache=llm_cache,
        news_window_days=news_window_days,
        min_train_months=12,
        max_months=eval_months,
        pipeline=LEARN_PIPELINE,
    )
    if feature_cache is None:
        raise RuntimeError("Tune backtest: insufficient SPY history for feature build")

    candidates = expand_tune_candidates() if use_grid else TUNE_CANDIDATES
    trial_configs = list(candidates[:max_rounds] if max_rounds > 0 else candidates)

    tune_prog = RunProgress(
        "predict-tune",
        len(trial_configs),
        run_dir=root,
        pipeline=LEARN_PIPELINE,
        phase="score_configs",
        every=max(1, len(trial_configs) // 10),
    )
    tune_prog.start()

    for i, config in enumerate(trial_configs, start=1):
        bt = backtest_with_config(
            root,
            config,
            news_window_days=news_window_days,
            feature_cache=feature_cache,
            monthly_only=True,
        )
        portfolio = evaluate_portfolio_metrics(
            root, bt, config, capital_usd=capital_usd
        )
        overall = _summarize_slice(bt, "overall") if not bt.empty else {}
        metrics = evaluate_tune_passes(
            evaluate_news_backed_metrics(bt, overall=overall),
            portfolio,
        )
        composite = _composite_tune_score(metrics, portfolio, overall)
        round_doc = {
            "round": i,
            "config": config.to_dict(),
            "metrics": metrics,
            "portfolio": portfolio,
            "overall": overall,
            "composite_score": round(composite, 4),
        }
        rounds.append(round_doc)
        (learn_dir / f"tune_round_{i:03d}.json").write_text(
            json.dumps(round_doc, indent=2) + "\n"
        )

        final_usd = float(portfolio.get("final_value_usd") or 0)
        if best is None or composite > best_score:
            best_score = composite
            best = round_doc
        elif composite == best_score and final_usd > float(
            best.get("portfolio", {}).get("final_value_usd") or 0
        ):
            best = round_doc

        ic_val = abs(float(metrics.get("ic") or 0))
        if ic_val > best_ic_val:
            best_ic_val = ic_val
            best_ic = round_doc
        if final_usd > best_portfolio_usd:
            best_portfolio_usd = final_usd
            best_portfolio = round_doc

        tune_prog.advance(
            1,
            message=f"{config.name} ${portfolio.get('final_value_usd', 0):,.0f}",
        )

    if objective == "profit" and best_portfolio:
        selected = best_portfolio
    elif objective == "ic" and best_ic:
        selected = best_ic
    elif best:
        selected = best
    elif best_portfolio:
        selected = best_portfolio
    else:
        selected = rounds[-1] if rounds else {}

    tune_prog.finish(
        f"selected {selected.get('config', {}).get('name', 'n/a')} ({objective})"
    )

    chosen = PredictTuneConfig(
        **selected.get("config", PredictTuneConfig(name="v1_baseline").to_dict())
    )
    save_predict_config(root, chosen)

    objective_label = {
        "profit": "max $10K final value (SPY monthly sim)",
        "composite": "max composite score (portfolio P&L + IC/hit rate)",
        "ic": "max |IC| on monthly walk-forward",
    }[objective]

    lines = [
        f"# L4 prediction tune (self-learning) — {today}",
        "",
        f"**Stop gates (forecast):** IC ≥ {TUNE_MIN_NEWS_IC}, hit rate ≥ {TUNE_MIN_HIT_RATE}, "
        f"coverage ≥ {TUNE_MIN_COVERAGE}, N ≥ {TUNE_MIN_NEWS_ROWS}",
        f"**Stop gates (portfolio):** excess vs B&H ≥ {TUNE_MIN_PORTFOLIO_EXCESS} pp",
        "",
        f"**Selection (saved config):** {objective_label}",
        f"**Objective:** `{objective}`",
        f"**Capital simulated:** ${capital_usd:,.0f} SPY monthly rebalance",
        "",
        f"**Selected config:** `{chosen.name}`",
        "",
        "| Round | Config | $10K final | Excess vs B&H | IC | Hit rate | Pass |",
        "|-------|--------|------------|---------------|-----|----------|------|",
    ]
    for r in rounds:
        m = r["metrics"]
        p = r.get("portfolio", {})
        lines.append(
            f"| {r['round']} | {r['config']['name']} | "
            f"${p.get('final_value_usd', 0):,.0f} | "
            f"{p.get('excess_return_pct', 'n/a')} pp | "
            f"{m.get('ic', 'n/a')} | {m.get('hit_rate', 'n/a')} | "
            f"{m.get('passes', False)} |"
        )
    lines.extend(
        [
            "",
            "## Leaders",
            "",
            "| Leader | Config | IC | $10K final | Excess vs B&H |",
            "|--------|--------|-----|------------|---------------|",
        ]
    )
    if best_ic:
        li = _round_leader_doc(best_ic)
        lines.append(
            f"| Best IC | {li['config']} | {li['ic']} | ${li['final_value_usd']:,.0f} | "
            f"{li['excess_return_pct']} pp |"
        )
    if best_portfolio:
        lp = _round_leader_doc(best_portfolio)
        lines.append(
            f"| Best $10K | {lp['config']} | {lp['ic']} | ${lp['final_value_usd']:,.0f} | "
            f"{lp['excess_return_pct']} pp |"
        )
    if best and objective == "composite":
        lc = _round_leader_doc(best)
        lines.append(
            f"| Best composite | {lc['config']} | {lc['ic']} | "
            f"${lc['final_value_usd']:,.0f} | {lc['excess_return_pct']} pp |"
        )
    sel_p = selected.get("portfolio", {}) if selected else {}
    sel_m = selected.get("metrics", {}) if selected else {}
    lines.extend(
        [
            "",
            f"**Saved config:** `{chosen.name}` (objective={objective})",
            f"**Selected portfolio:** ${sel_p.get('final_value_usd', 0):,.2f} "
            f"({sel_p.get('total_return_pct', 0):+.2f}% vs B&H {sel_p.get('buy_hold_return_pct', 0):+.2f}%)",
            f"**Passes forecast gate:** {sel_m.get('passes_forecast', False)}",
            f"**Passes portfolio gate:** {sel_m.get('passes_portfolio', False)}",
            f"**Passes full gate:** {sel_m.get('passes_full', False)}",
            f"**Certainty tier:** {sel_m.get('certainty', 'low')}",
            f"**Composite score:** {selected.get('composite_score', 'n/a')}",
            "",
        ]
    )
    tune_md = learn_dir / "predict_tune.md"
    tune_md.write_text("\n".join(lines) + "\n")

    summary = {
        "date": today,
        "rounds": len(rounds),
        "objective": objective,
        "selected_config": chosen.to_dict(),
        "metrics": sel_m,
        "portfolio": sel_p,
        "composite_score": selected.get("composite_score"),
        "leaders": {
            "best_ic": _round_leader_doc(best_ic) if best_ic else None,
            "best_portfolio": _round_leader_doc(best_portfolio) if best_portfolio else None,
            "best_composite": _round_leader_doc(best) if best else None,
            "selected": _round_leader_doc(selected) if selected else None,
        },
        "passes": sel_m.get("passes_full", False),
        "passes_portfolio": sel_m.get("passes_portfolio", False),
        "certainty": sel_m.get("certainty", "low"),
        "tune_report": str(tune_md.relative_to(root)),
    }
    (learn_dir / "predict_tune_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    update_meta(root, {"L4": {"learning": summary}})
    return summary
