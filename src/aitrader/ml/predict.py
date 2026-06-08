"""Multi-horizon price prediction — Recipe — Multi-horizon price prediction."""

from __future__ import annotations

import json
import math
import pickle
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sklearn.linear_model import Ridge

from aitrader.ml.drift import filter_corpus_by_age, load_keyword_map
from aitrader.nlp.keyword_cache import keywords_for_article, load_keyword_cache
from aitrader.nlp.keywords import (
    HORIZON_TRADING_DAYS,
    _labels_from_corpus,
    _vader_sentiment,
    forward_return_at,
    load_etf_closes,
    load_sector_etfs,
)
from aitrader.nlp.news import load_corpus
from aitrader.ml.predict_config import DEFAULT_CONFIG, PredictTuneConfig, load_predict_config
from aitrader.workspace import ensure_run_layout, update_meta

ANCHOR_TICKERS = ("SPY", "IWM")
DEFAULT_HORIZONS = ("2w", "1m", "3m")
FEATURE_COLS = ("keyword_score", "sentiment", "cluster_prior", "momentum", "beta_spy")
MIN_TRAIN_ROWS = 20
CONFIDENCE_Z = 1.96


@dataclass
class _HorizonModel:
    horizon: str
    horizon_days: int
    ridge: Ridge | None
    residual_std: float
    cap_sigma: float
    cold_start: bool
    train_rows: int


def load_universe(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "data" / "universe.csv"
    if not path.exists():
        return pd.DataFrame(columns=["sector_id", "ticker", "etf_proxy"])
    return pd.read_csv(path)


def load_current_cluster(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "models" / "current_cluster.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _keyword_coef_map(keyword_map: list[dict[str, Any]]) -> dict[str, float]:
    return {str(r["keyword"]).lower(): float(r.get("coef", 0.0)) for r in keyword_map}


def _articles_for_ticker(
    corpus: list[dict[str, Any]],
    *,
    sector_id: str,
    ticker: str,
    window_days: int,
) -> list[dict[str, Any]]:
    recent = filter_corpus_by_age(corpus, max_age_days=window_days)
    ticker_u = ticker.upper()
    out: list[dict[str, Any]] = []
    for row in recent:
        row_sector = row.get("sector_id") or "macro"
        tickers = [t.upper() for t in (row.get("tickers") or []) if t]
        if row_sector == sector_id or row_sector == "macro":
            if tickers and ticker_u not in tickers:
                continue
            out.append(row)
    return out


def _signal_from_articles(
    articles: list[dict[str, Any]],
    coef_map: dict[str, float],
    llm_cache: dict[str, dict[str, Any]] | None,
    *,
    max_articles: int | None = None,
) -> tuple[float, float, list[str]]:
    if max_articles and len(articles) > max_articles:
        articles = sorted(articles, key=lambda a: a.get("published_at", ""))[-max_articles:]
    score = 0.0
    sentiments: list[float] = []
    contrib: list[tuple[str, float]] = []
    for art in articles:
        text = f"{art.get('title', '')} {art.get('body', '')}"
        kws = keywords_for_article(art, llm_cache)
        if not kws:
            continue
        sentiments.append(_vader_sentiment(text))
        for kw in kws:
            coef = coef_map.get(kw.lower())
            if coef is None:
                continue
            score += coef
            contrib.append((kw, coef))
    contrib.sort(key=lambda x: abs(x[1]), reverse=True)
    top = [k for k, _ in contrib[:5]]
    mean_sent = sum(sentiments) / len(sentiments) if sentiments else 0.0
    return score, mean_sent, top


def _cluster_prior(sector_id: str, cluster_doc: dict[str, Any]) -> float:
    profile = cluster_doc.get("sector_return_profile") or {}
    return float(profile.get(sector_id, 0.0))


def _last_trading_day(closes: pd.Series) -> pd.Timestamp | None:
    if closes.empty:
        return None
    return closes.index[-1]


def _momentum_at(closes: pd.Series, day: pd.Timestamp, lookback: int = 21) -> float:
    if closes.empty or day not in closes.index:
        return 0.0
    idx = closes.index.get_loc(day)
    if idx < lookback:
        return 0.0
    return float(closes.iloc[idx] / closes.iloc[idx - lookback] - 1.0)


def _beta_at(
    ticker_closes: pd.Series,
    spy_closes: pd.Series,
    day: pd.Timestamp,
    window: int = 63,
) -> float:
    if ticker_closes.empty or spy_closes.empty or day not in ticker_closes.index:
        return 1.0
    idx = ticker_closes.index.get_loc(day)
    if idx < window:
        return 1.0
    t_slice = ticker_closes.iloc[idx - window : idx + 1]
    s_slice = spy_closes.reindex(t_slice.index).dropna()
    if len(s_slice) < 10:
        return 1.0
    t_ret = t_slice.pct_change().dropna()
    s_ret = s_slice.pct_change().dropna()
    aligned = pd.concat([t_ret, s_ret], axis=1, join="inner").dropna()
    if len(aligned) < 10:
        return 1.0
    cov = float(np.cov(aligned.iloc[:, 0], aligned.iloc[:, 1])[0, 1])
    var = float(np.var(aligned.iloc[:, 1]))
    if var < 1e-12:
        return 1.0
    return cov / var


def _feature_row(
    *,
    keyword_score: float,
    sentiment: float,
    cluster_prior: float,
    momentum: float,
    beta_spy: float,
) -> np.ndarray:
    return np.array([[keyword_score, sentiment, cluster_prior, momentum, beta_spy]])


def _build_training_frame(
    run_dir: Path,
    horizon_days: int,
    *,
    llm_cache: dict[str, dict[str, Any]] | None,
) -> pd.DataFrame:
    corpus = load_corpus(run_dir)
    sector_etfs = load_sector_etfs(run_dir)
    sector_etfs["anchor"] = "SPY"
    spy_closes = load_etf_closes(run_dir, "SPY")
    rows: list[dict[str, Any]] = []

    for sector_id, etf in sector_etfs.items():
        labels = _labels_from_corpus(
            corpus,
            sector_id,
            run_dir,
            etf,
            horizon_days,
            include_macro=True,
            llm_cache=llm_cache,
            use_llm=True,
        )
        coef_map = _keyword_coef_map(load_keyword_map(run_dir, sector_id))
        for label in labels:
            kw_score = sum(coef_map.get(k.lower(), 0.0) for k in label.keywords)
            ticker_closes = load_etf_closes(run_dir, etf)
            mom = _momentum_at(ticker_closes, label.trading_day)
            beta = _beta_at(ticker_closes, spy_closes, label.trading_day)
            rows.append(
                {
                    "sector_id": sector_id,
                    "trading_day": label.trading_day,
                    "keyword_score": kw_score,
                    "sentiment": label.sentiment,
                    "cluster_prior": 0.0,
                    "momentum": mom,
                    "beta_spy": beta,
                    "forward_return": label.forward_return,
                }
            )
    return pd.DataFrame(rows)


def _train_horizon_model(
    frame: pd.DataFrame,
    horizon: str,
    horizon_days: int,
) -> _HorizonModel:
    y = frame["forward_return"].to_numpy()
    cap_sigma = float(np.std(y)) if len(y) > 5 else 0.05
    if len(frame) < MIN_TRAIN_ROWS:
        return _HorizonModel(
            horizon=horizon,
            horizon_days=horizon_days,
            ridge=None,
            residual_std=cap_sigma,
            cap_sigma=cap_sigma,
            cold_start=True,
            train_rows=len(frame),
        )
    X = frame[list(FEATURE_COLS)].to_numpy()
    ridge = Ridge(alpha=1.0)
    ridge.fit(X, y)
    preds = ridge.predict(X)
    resid = y - preds
    residual_std = float(np.std(resid)) if len(resid) > 1 else cap_sigma
    return _HorizonModel(
        horizon=horizon,
        horizon_days=horizon_days,
        ridge=ridge,
        residual_std=max(residual_std, 1e-4),
        cap_sigma=cap_sigma,
        cold_start=False,
        train_rows=len(frame),
    )


def _event_boost_factor(macro_events: str, config: PredictTuneConfig) -> float:
    if config.event_keyword_boost <= 1.0 or not macro_events or macro_events == "none":
        return 1.0
    tags = {t.strip() for t in macro_events.split("|") if t.strip()}
    if tags & {"fed", "inflation", "employment", "tariff"}:
        return config.event_keyword_boost
    return 1.0


def _predict_from_features(
    model: _HorizonModel,
    features: dict[str, float],
    *,
    spy_momentum: float,
    config: PredictTuneConfig | None = None,
    news_articles: int = 0,
    macro_events: str = "none",
) -> tuple[float, float, float, bool, float]:
    cfg = config or DEFAULT_CONFIG
    boost = _event_boost_factor(macro_events, cfg)
    kw = cfg.scaled_keyword(features["keyword_score"]) * boost
    feat = {
        **features,
        "keyword_score": kw,
        "momentum": features["momentum"] * cfg.momentum_dampen,
    }
    row = _feature_row(
        keyword_score=feat["keyword_score"],
        sentiment=feat["sentiment"],
        cluster_prior=feat["cluster_prior"],
        momentum=feat["momentum"],
        beta_spy=feat["beta_spy"],
    )
    cold = model.cold_start
    has_news = news_articles >= cfg.min_news_confident

    if model.ridge is None:
        ridge_pred = (
            feat["keyword_score"] * 8.0
            + feat["cluster_prior"] * 0.6
            + feat["momentum"] * 0.35
            + feat["beta_spy"] * spy_momentum * 0.25
        )
    else:
        ridge_pred = float(model.ridge.predict(row)[0])

    if not has_news:
        # News-driven objective: no forecast without dated macro news in window.
        # Momentum is a training feature only; separate momentum indicator is future work.
        expected = 0.0
        cold = True
    else:
        blend = cfg.cluster_blend
        expected = (1.0 - blend) * ridge_pred + blend * feat["cluster_prior"]

    cap = model.cap_sigma * 3.0
    if model.horizon == "2w" and abs(expected) > 0.5:
        expected = math.copysign(min(abs(expected), cap), expected)
    else:
        expected = max(-cap, min(cap, expected))

    half = model.residual_std * CONFIDENCE_Z
    if not has_news:
        half *= 4.0
    elif boost > 1.0:
        half *= 0.85
    lower = expected - half
    upper = expected + half
    if lower >= expected:
        lower = expected - 1e-4
    if upper <= expected:
        upper = expected + 1e-4
    confidence = min(1.0, (1.0 / (1.0 + half * 10.0)) * (0.15 if not has_news else 1.0))
    return expected, lower, upper, cold, confidence


def _tickers_to_score(run_dir: Path) -> list[tuple[str, str]]:
    universe = load_universe(run_dir)
    seen: set[str] = set()
    pairs: list[tuple[str, str]] = []
    for _, row in universe.iterrows():
        ticker = str(row["ticker"]).upper()
        sector_id = str(row["sector_id"])
        if ticker not in seen:
            pairs.append((ticker, sector_id))
            seen.add(ticker)
    sector_etfs = load_sector_etfs(run_dir)
    for sector_id, etf in sector_etfs.items():
        etf_u = etf.upper()
        if etf_u not in seen:
            pairs.append((etf_u, sector_id))
            seen.add(etf_u)
    return pairs


def train_horizon_models(
    run_dir: str | Path,
    *,
    horizons: tuple[str, ...] = DEFAULT_HORIZONS,
) -> dict[str, _HorizonModel]:
    root = ensure_run_layout(run_dir)
    llm_cache = load_keyword_cache(root)
    models: dict[str, _HorizonModel] = {}
    models_dir = root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    for horizon in horizons:
        days = HORIZON_TRADING_DAYS.get(horizon, 21)
        frame = _build_training_frame(root, days, llm_cache=llm_cache)
        hm = _train_horizon_model(frame, horizon, days)
        models[horizon] = hm
        path = models_dir / f"predictor_{horizon}.pkl"
        with path.open("wb") as fh:
            pickle.dump(hm, fh)
    return models


def load_horizon_models(
    run_dir: Path,
    *,
    horizons: tuple[str, ...] = DEFAULT_HORIZONS,
) -> dict[str, _HorizonModel]:
    models: dict[str, _HorizonModel] = {}
    for horizon in horizons:
        path = run_dir / "models" / f"predictor_{horizon}.pkl"
        if path.exists():
            with path.open("rb") as fh:
                models[horizon] = pickle.load(fh)
    return models


def run_predictions(
    run_dir: str | Path,
    *,
    horizons: tuple[str, ...] = DEFAULT_HORIZONS,
    news_window_days: int = 7,
    retrain: bool = False,
) -> Path:
    root = ensure_run_layout(run_dir)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if retrain or not any((root / "models" / f"predictor_{h}.pkl").exists() for h in horizons):
        models = train_horizon_models(root, horizons=horizons)
    else:
        models = load_horizon_models(root, horizons=horizons)
        missing = [h for h in horizons if h not in models]
        if missing:
            trained = train_horizon_models(root, horizons=tuple(missing))
            models.update(trained)

    corpus = load_corpus(root)
    llm_cache = load_keyword_cache(root)
    cluster_doc = load_current_cluster(root)
    cluster_id = cluster_doc.get("dominant_cluster_id", -1)
    spy_closes = load_etf_closes(root, "SPY")
    as_of = _last_trading_day(spy_closes)
    spy_mom = _momentum_at(spy_closes, as_of) if as_of is not None else 0.0
    tune = load_predict_config(root)

    records: list[dict[str, Any]] = []
    for ticker, sector_id in _tickers_to_score(root):
        ticker_closes = load_etf_closes(root, ticker)
        if ticker_closes.empty or as_of is None:
            continue
        kw_map = load_keyword_map(root, sector_id if sector_id != "anchor" else "anchor")
        coef_map = _keyword_coef_map(kw_map)
        articles = _articles_for_ticker(
            corpus,
            sector_id=sector_id,
            ticker=ticker,
            window_days=news_window_days,
        )
        kw_score, sentiment, top_kw = _signal_from_articles(articles, coef_map, llm_cache)
        prior = _cluster_prior(sector_id, cluster_doc)
        mom = _momentum_at(ticker_closes, as_of)
        beta = _beta_at(ticker_closes, spy_closes, as_of)

        features = {
            "keyword_score": kw_score,
            "sentiment": sentiment,
            "cluster_prior": prior,
            "momentum": mom,
            "beta_spy": beta,
        }
        for horizon in horizons:
            hm = models.get(horizon)
            if hm is None:
                continue
            n_arts = len(articles)
            expected, lower, upper, cold, conf = _predict_from_features(
                hm,
                features,
                spy_momentum=spy_mom,
                config=tune,
                news_articles=n_arts,
                macro_events="none",
            )
            records.append(
                {
                    "ticker": ticker,
                    "sector_id": sector_id,
                    "horizon": horizon,
                    "expected_return": round(expected, 6),
                    "confidence_lower": round(lower, 6),
                    "confidence_upper": round(upper, 6),
                    "confidence_score": round(conf, 4),
                    "cluster_id": cluster_id,
                    "news_articles": n_arts,
                    "top_keywords": "|".join(top_kw),
                    "cold_start": cold,
                    "no_news_signal": n_arts < tune.min_news_confident,
                }
            )

    df = pd.DataFrame(records)
    if df.empty:
        raise RuntimeError("No predictions generated — check OHLCV and universe data.")

    anchor_mask = df["ticker"].isin(ANCHOR_TICKERS)
    anchor_order = {t: i for i, t in enumerate(ANCHOR_TICKERS)}
    anchors = df[anchor_mask].copy()
    anchors["_anchor_ord"] = anchors["ticker"].map(anchor_order)
    anchors = anchors.sort_values(["_anchor_ord", "horizon"]).drop(columns="_anchor_ord")
    rest = df[~anchor_mask].sort_values(["sector_id", "ticker", "horizon"])
    out_df = pd.concat([anchors, rest], ignore_index=True)

    dupes = out_df.duplicated(subset=["ticker", "horizon"], keep=False)
    if dupes.any():
        out_df = out_df.drop_duplicates(subset=["ticker", "horizon"], keep="first")

    report_path = root / "reports" / f"predictions_{today}.csv"
    out_df.to_csv(report_path, index=False)

    update_meta(
        root,
        {
            "layer": "L4",
            "L4": {
                "status": "completed",
                "predictions_date": today,
                "horizons": list(horizons),
                "rows": len(out_df),
                "anchors": {t: int((out_df["ticker"] == t).sum()) for t in ANCHOR_TICKERS},
            },
        },
    )
    return report_path
