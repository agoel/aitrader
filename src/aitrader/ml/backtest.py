"""Walk-forward backtest — keyword/cluster sentiment vs realized returns."""

from __future__ import annotations

import bisect
import json
import math
import pickle
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from aitrader.ml.drift import load_keyword_map
from aitrader.ml.predict import (
    ANCHOR_TICKERS,
    DEFAULT_HORIZONS,
    _beta_at,
    _keyword_coef_map,
    _momentum_at,
    _predict_from_features,
    _signal_from_articles,
    _train_horizon_model,
)
from aitrader.ml.predict_config import DEFAULT_CONFIG, PredictTuneConfig
from aitrader.nlp.cluster import _article_text, _sector_return_profiles
from aitrader.nlp.keyword_cache import keywords_for_article, load_keyword_cache
from aitrader.nlp.keywords import (
    HORIZON_TRADING_DAYS,
    _labels_from_corpus,
    _map_to_trading_day,
    _pearson_ic,
    load_etf_closes,
    load_sector_etfs,
)
from aitrader.nlp.news import load_corpus
from aitrader.progress import RunProgress, pipeline_phase, write_status
from aitrader.progress import PipelineStatus
from aitrader.workspace import ensure_run_layout, update_meta

BACKTEST_SIGNAL_MAX_ARTICLES = 100


@dataclass
class BacktestFeatureCache:
    """Expensive PIT features built once; RSI scores many configs from this cache."""

    run_dir: Path
    horizon_days: int
    month_ends: pd.Series
    month_features: list[dict[str, Any]]
    month_realized: list[float | None]
    macro_event_features: list[dict[str, Any]]
    cold_model: Any
    min_train_months: int = 12


MACRO_EVENT_TAGS = {
    "fed": ("fed", "federal reserve", "rate cut", "rate hike", "fomc"),
    "inflation": ("inflation", "cpi", "ppi", "prices"),
    "earnings": ("earnings", "guidance", "revenue", "profit"),
    "tariff": ("tariff", "tariffs", "trade war"),
    "employment": ("jobs", "employment", "unemployment", "payroll"),
}


def _parse_pub(pub: str) -> datetime:
    return datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone(timezone.utc)


def _corpus_timeline(
    corpus: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[datetime]]:
    pairs: list[tuple[datetime, dict[str, Any]]] = []
    for row in corpus:
        pub = row.get("published_at")
        if not pub:
            continue
        pairs.append((_parse_pub(pub), row))
    pairs.sort(key=lambda x: x[0])
    if not pairs:
        return [], []
    return [p[1] for p in pairs], [p[0] for p in pairs]


def _corpus_before(
    corpus: list[dict[str, Any]],
    as_of: datetime,
    *,
    window_days: int,
    timeline: tuple[list[dict[str, Any]], list[datetime]] | None = None,
) -> list[dict[str, Any]]:
    start = as_of - timedelta(days=window_days)
    if timeline is not None:
        articles, dates = timeline
        if not dates:
            return []
        i0 = bisect.bisect_left(dates, start)
        i1 = bisect.bisect_right(dates, as_of)
        return articles[i0:i1]
    out = []
    for row in corpus:
        pub = row.get("published_at")
        if not pub:
            continue
        dt = _parse_pub(pub)
        if start <= dt <= as_of:
            out.append(row)
    return out


def _load_cluster_model(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "models" / "news_clusters.pkl"
    if not path.exists():
        return None
    with path.open("rb") as fh:
        return pickle.load(fh)


def _assign_clusters(
    model: dict[str, Any] | None,
    articles: list[dict[str, Any]],
) -> list[int]:
    if not model or not articles:
        return [-1] * len(articles)
    vectorizer = model["vectorizer"]
    km = model["kmeans"]
    texts = [_article_text(a) for a in articles]
    X = vectorizer.transform(texts)
    return [int(c) for c in km.predict(X)]


def _anchor_cluster_prior(profile: dict[str, float]) -> float:
    if not profile:
        return 0.0
    if "anchor" in profile:
        return float(profile["anchor"])
    vals = [float(v) for v in profile.values()]
    return sum(vals) / len(vals) if vals else 0.0


def _cluster_context_pit(
    run_dir: Path,
    articles: list[dict[str, Any]],
    cluster_ids: list[int],
    *,
    horizon_days: int,
    cluster_model: dict[str, Any] | None = None,
) -> tuple[int, dict[str, float]]:
    if not articles or not cluster_ids:
        return -1, {}
    counts = Counter(cluster_ids)
    dominant = counts.most_common(1)[0][0]
    cached = (cluster_model or {}).get("sector_profiles")
    if isinstance(cached, dict) and cached:
        profile = cached.get(dominant) or cached.get(int(dominant)) or {}
        return dominant, dict(profile)
    profiles = _sector_return_profiles(
        run_dir,
        articles,
        cluster_ids,
        horizon_days=horizon_days,
    )
    return dominant, profiles.get(dominant, {})


def _macro_events(keywords: list[str]) -> list[str]:
    hay = " ".join(k.lower() for k in keywords)
    hits = []
    for tag, needles in MACRO_EVENT_TAGS.items():
        if any(n in hay for n in needles):
            hits.append(tag)
    return hits


def _macro_events_from_text(text: str) -> list[str]:
    hay = text.lower()
    return [tag for tag, needles in MACRO_EVENT_TAGS.items() if any(n in hay for n in needles)]


def _hit_rate(pred: np.ndarray, realized: np.ndarray) -> float:
    if len(pred) < 1:
        return 0.0
    signs = [(p > 0) == (r > 0) for p, r in zip(pred, realized) if abs(p) > 1e-8]
    return sum(signs) / len(signs) if signs else 0.0


def _rmse(pred: np.ndarray, realized: np.ndarray) -> float:
    if len(pred) < 1:
        return 0.0
    return float(np.sqrt(np.mean((pred - realized) ** 2)))


def _articles_on_trading_day(
    corpus: list[dict[str, Any]],
    trading_day: pd.Timestamp,
    trading_index: pd.DatetimeIndex,
    *,
    sector_id: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in corpus:
        pub = row.get("published_at", "")
        if not pub:
            continue
        td = _map_to_trading_day(pub, trading_index)
        if td != trading_day:
            continue
        row_sector = row.get("sector_id") or "macro"
        if row_sector in (sector_id, "macro"):
            out.append(row)
    return out


def _build_label_observations(
    run_dir: Path,
    horizon_days: int,
    *,
    llm_cache: dict[str, dict[str, Any]] | None,
) -> pd.DataFrame:
    """Article-level observations with features and realized forward returns."""
    corpus = load_corpus(run_dir)
    sector_etfs = load_sector_etfs(run_dir)
    sector_etfs["anchor"] = "SPY"
    spy_closes = load_etf_closes(run_dir, "SPY")
    cluster_model = _load_cluster_model(run_dir)
    rows: list[dict[str, Any]] = []

    priority = ("anchor", "technology", "financials", "energy", "health_care")
    sector_items = sorted(
        sector_etfs.items(),
        key=lambda x: (priority.index(x[0]) if x[0] in priority else 99, x[0]),
    )
    for sector_id, etf in sector_items:
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
        ticker_closes = load_etf_closes(run_dir, etf)

        for label in labels:
            day_arts = _articles_on_trading_day(
                corpus, label.trading_day, spy_closes.index, sector_id=sector_id
            )
            cids = _assign_clusters(cluster_model, day_arts)
            dom, profile = _cluster_context_pit(
                run_dir,
                day_arts,
                cids,
                horizon_days=horizon_days,
                cluster_model=cluster_model,
            )
            cluster_id = dom if dom >= 0 else (-1 if not cids else cids[0])
            cluster_prior = float(profile.get(sector_id, 0.0))
            kw_score = sum(coef_map.get(k.lower(), 0.0) for k in label.keywords)
            events = _macro_events(label.keywords)
            mom = _momentum_at(ticker_closes, label.trading_day)
            beta = _beta_at(ticker_closes, spy_closes, label.trading_day)
            ticker = etf if sector_id != "anchor" else "SPY"

            rows.append(
                {
                    "trading_day": label.trading_day,
                    "sector_id": sector_id,
                    "ticker": ticker,
                    "keyword_score": kw_score,
                    "sentiment": label.sentiment,
                    "cluster_prior": cluster_prior,
                    "momentum": mom,
                    "beta_spy": beta,
                    "cluster_id": cluster_id,
                    "macro_events": "|".join(events) if events else "none",
                    "top_keywords": "|".join(label.keywords[:5]),
                    "realized_return": label.forward_return,
                }
            )

    return pd.DataFrame(rows)


def _walk_forward_predictions(
    frame: pd.DataFrame,
    horizon: str,
    horizon_days: int,
    *,
    min_train_days: int = 3,
    config: PredictTuneConfig | None = None,
) -> pd.DataFrame:
    if frame.empty:
        return frame
    days = sorted(frame["trading_day"].unique())
    preds: list[dict[str, Any]] = []

    for i, test_day in enumerate(days):
        train_days = days[:i]
        if len(train_days) < min_train_days:
            continue
        train = frame[frame["trading_day"].isin(train_days)]
        test = frame[frame["trading_day"] == test_day]
        if train.empty or test.empty:
            continue
        train_fit = train.rename(columns={"realized_return": "forward_return"})
        hm = _train_horizon_model(train_fit, horizon, horizon_days)
        spy_mom = float(train["momentum"].mean())
        for _, row in test.iterrows():
            features = {
                "keyword_score": row["keyword_score"],
                "sentiment": row["sentiment"],
                "cluster_prior": row["cluster_prior"],
                "momentum": row["momentum"],
                "beta_spy": row["beta_spy"],
            }
            expected, lower, upper, cold, conf = _predict_from_features(
                hm,
                features,
                spy_momentum=spy_mom,
                config=config or DEFAULT_CONFIG,
                news_articles=int(row.get("news_articles", 1)),
                macro_events=str(row.get("macro_events", "none")),
            )
            preds.append(
                {
                    **row.to_dict(),
                    "horizon": horizon,
                    "predicted_return": expected,
                    "confidence_lower": lower,
                    "confidence_upper": upper,
                    "confidence_score": conf,
                    "cold_start": cold,
                }
            )
    return pd.DataFrame(preds)


def _build_monthly_spy_features(
    run_dir: Path,
    horizon_days: int,
    *,
    llm_cache: dict[str, dict[str, Any]] | None,
    news_window_days: int = 30,
    min_train_months: int = 12,
    max_months: int = 48,
    pipeline: str = "predict.backtest",
    quiet: bool = False,
) -> tuple[pd.Series, list[dict[str, Any]], list[float | None]] | None:
    spy = load_etf_closes(run_dir, "SPY")
    if len(spy) < horizon_days + min_train_months * 21:
        return None
    corpus = load_corpus(run_dir)
    timeline = _corpus_timeline(corpus)
    cluster_model = _load_cluster_model(run_dir)
    coef_map = _keyword_coef_map(load_keyword_map(run_dir, "anchor"))
    month_ends = (
        spy.index.to_series().groupby(spy.index.to_period("M")).max().sort_values().tail(max_months)
    )
    month_features: list[dict[str, Any]] = []
    month_realized: list[float | None] = []
    feat_prog = RunProgress(
        "backtest-month-features",
        len(month_ends),
        run_dir=run_dir,
        pipeline=pipeline,
        phase="build_month_features",
        quiet=quiet,
        every=max(1, len(month_ends) // 15),
    )
    feat_prog.start()

    for as_of in month_ends:
        if as_of not in spy.index:
            month_features.append({})
            month_realized.append(None)
            feat_prog.advance(1)
            continue
        idx = spy.index.get_loc(as_of)
        if idx + horizon_days >= len(spy):
            month_features.append({})
            month_realized.append(None)
            feat_prog.advance(1)
            continue
        realized = float(spy.iloc[idx + horizon_days] / spy.iloc[idx] - 1.0)
        month_realized.append(realized)
        pub_cutoff = as_of.to_pydatetime().replace(tzinfo=timezone.utc)
        window = _corpus_before(
            corpus, pub_cutoff, window_days=news_window_days, timeline=timeline
        )
        kw_score, sentiment, top_kw = _signal_from_articles(
            window, coef_map, llm_cache, max_articles=BACKTEST_SIGNAL_MAX_ARTICLES
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
        month_features.append(
            {
                "keyword_score": kw_score,
                "sentiment": sentiment,
                "cluster_prior": _anchor_cluster_prior(profile),
                "momentum": _momentum_at(spy, as_of),
                "beta_spy": 1.0,
                "cluster_id": dom,
                "news_articles": len(window),
                "macro_events": "|".join(sorted(set(events))) if events else "none",
                "top_keywords": "|".join(top_kw[:5]),
            }
        )
        feat_prog.advance(1)

    feat_prog.finish()
    return month_ends, month_features, month_realized


def _score_monthly_spy_from_features(
    cache: BacktestFeatureCache,
    config: PredictTuneConfig,
    *,
    pipeline: str = "predict.backtest",
    quiet: bool = False,
) -> pd.DataFrame:
    cfg = config
    month_ends = cache.month_ends
    month_features = cache.month_features
    month_realized = cache.month_realized
    min_train_months = cache.min_train_months
    horizon_days = cache.horizon_days
    rows: list[dict[str, Any]] = []
    wf_total = max(0, len(month_ends) - min_train_months)
    wf_prog = RunProgress(
        "backtest-walkforward",
        wf_total,
        run_dir=cache.run_dir,
        pipeline=pipeline,
        phase="walkforward_spy",
        quiet=quiet,
        every=max(1, wf_total // 10),
    )
    wf_prog.start()
    for i in range(min_train_months, len(month_ends)):
        if month_realized[i] is None or not month_features[i]:
            wf_prog.advance(1, message="skip")
            continue
        train_rows = []
        for j in range(i):
            if month_realized[j] is None or not month_features[j]:
                continue
            feat = month_features[j]
            if cfg.train_news_only and feat.get("news_articles", 0) < cfg.min_news_train:
                continue
            if feat.get("news_articles", 0) < cfg.min_news_train and cfg.min_news_train > 0:
                continue
            train_rows.append({**feat, "forward_return": month_realized[j]})
        train_df = pd.DataFrame(train_rows)
        if len(train_df) < max(3, min_train_months // 2):
            train_rows = []
            for j in range(i):
                if month_realized[j] is None or not month_features[j]:
                    continue
                train_rows.append({**month_features[j], "forward_return": month_realized[j]})
            train_df = pd.DataFrame(train_rows)
        if len(train_df) < 3:
            wf_prog.advance(1, message="skip")
            continue
        hm = _train_horizon_model(train_df, "1m", horizon_days)
        feat = month_features[i]
        mom = feat["momentum"]
        pred, lo, hi, cold, conf = _predict_from_features(
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
        rows.append(
            {
                "trading_day": month_ends.iloc[i],
                "ticker": "SPY",
                "sector_id": "anchor",
                "horizon": "1m",
                "predicted_return": pred,
                "realized_return": month_realized[i],
                "confidence_lower": lo,
                "confidence_upper": hi,
                "confidence_score": conf,
                "cluster_id": feat["cluster_id"],
                "keyword_score": feat["keyword_score"],
                "sentiment": feat["sentiment"],
                "news_articles": feat["news_articles"],
                "macro_events": feat["macro_events"],
                "top_keywords": feat["top_keywords"],
                "cold_start": cold,
            }
        )
        wf_prog.advance(1, message=str(month_ends.iloc[i])[:10])
    wf_prog.finish(f"{len(rows)} SPY monthly predictions")
    return pd.DataFrame(rows)


def _build_macro_event_features(
    run_dir: Path,
    horizon_days: int,
    *,
    llm_cache: dict[str, dict[str, Any]] | None,
    pipeline: str = "predict.backtest",
    quiet: bool = False,
) -> list[dict[str, Any]]:
    corpus = load_corpus(run_dir)
    macro_arts = [a for a in corpus if (a.get("sector_id") or "") == "macro"]
    if not macro_arts:
        return []
    spy = load_etf_closes(run_dir, "SPY")
    by_day = _macro_articles_by_trading_day(macro_arts, spy.index, horizon_days)
    if not by_day:
        return []

    coef_map = _keyword_coef_map(load_keyword_map(run_dir, "anchor"))
    cluster_model = _load_cluster_model(run_dir)
    timeline = _corpus_timeline(corpus)
    feature_rows: list[dict[str, Any]] = []
    trading_days = sorted(by_day.keys())
    prog = RunProgress(
        "backtest-macro-events",
        len(trading_days),
        run_dir=run_dir,
        pipeline=pipeline,
        phase="macro_event_study",
        quiet=quiet,
        every=max(1, len(trading_days) // 10),
    )
    prog.start()

    for td in trading_days:
        arts = by_day[td]
        pub_dts = [_parse_pub(a["published_at"]) for a in arts if a.get("published_at")]
        if not pub_dts:
            prog.advance(1, message="skip")
            continue
        pub_cutoff = max(pub_dts)
        idx = spy.index.get_loc(td)
        realized = float(spy.iloc[idx + horizon_days] / spy.iloc[idx] - 1.0)
        window = _corpus_before(corpus, pub_cutoff, window_days=7, timeline=timeline)
        kw_score, sentiment, top_kw = _signal_from_articles(
            window, coef_map, llm_cache, max_articles=BACKTEST_SIGNAL_MAX_ARTICLES
        )
        cids = _assign_clusters(cluster_model, window)
        dom, profile = _cluster_context_pit(
            run_dir, window, cids, horizon_days=horizon_days, cluster_model=cluster_model
        )
        events: set[str] = set()
        for art in arts:
            text = f"{art.get('title', '')} {art.get('body', '')}"
            events.update(_macro_events_from_text(text))
            events.update(_macro_events(keywords_for_article(art, llm_cache) or []))
        event_str = "|".join(sorted(events)) if events else "none"
        lead = max(arts, key=lambda a: a.get("published_at", ""))
        feature_rows.append(
            {
                "trading_day": td,
                "realized_return": realized,
                "feat": {
                    "keyword_score": kw_score,
                    "sentiment": sentiment,
                    "cluster_prior": _anchor_cluster_prior(profile),
                    "momentum": _momentum_at(spy, td),
                    "beta_spy": 1.0,
                },
                "news_articles": len(window),
                "macro_events": event_str,
                "cluster_id": dom,
                "keyword_score": kw_score,
                "sentiment": sentiment,
                "cluster_prior": _anchor_cluster_prior(profile),
                "top_keywords": "|".join(top_kw[:5]),
                "article_id": lead.get("id"),
                "source": lead.get("source"),
                "title": (lead.get("title") or "")[:120],
                "macro_articles": len(arts),
            }
        )
        prog.advance(1, message=str(td)[:10])
    prog.finish(f"{len(feature_rows)} macro event days")
    return feature_rows


def _score_macro_event_features(
    feature_rows: list[dict[str, Any]],
    *,
    cold_model: Any,
    config: PredictTuneConfig,
) -> pd.DataFrame:
    cfg = config
    rows: list[dict[str, Any]] = []
    for item in feature_rows:
        feat = item["feat"]
        pred, lo, hi, cold, conf = _predict_from_features(
            cold_model,
            feat,
            spy_momentum=feat["momentum"],
            config=cfg,
            news_articles=int(item["news_articles"]),
            macro_events=str(item["macro_events"]),
        )
        rows.append(
            {
                "trading_day": item["trading_day"],
                "article_id": item["article_id"],
                "source": item["source"],
                "title": item["title"],
                "horizon": "1m",
                "ticker": "SPY",
                "sector_id": "anchor",
                "macro_events": item["macro_events"],
                "cluster_id": item["cluster_id"],
                "keyword_score": item["keyword_score"],
                "sentiment": item["sentiment"],
                "cluster_prior": item["cluster_prior"],
                "predicted_return": pred,
                "realized_return": item["realized_return"],
                "confidence_lower": lo,
                "confidence_upper": hi,
                "confidence_score": conf,
                "news_articles": item["news_articles"],
                "macro_articles": item["macro_articles"],
                "top_keywords": item["top_keywords"],
                "cold_start": cold,
            }
        )
    return pd.DataFrame(rows)


def build_backtest_feature_cache(
    run_dir: Path,
    horizon_days: int,
    *,
    llm_cache: dict[str, dict[str, Any]] | None,
    news_window_days: int = 30,
    min_train_months: int = 12,
    max_months: int = 48,
    pipeline: str = "predict.backtest",
    quiet: bool = False,
) -> BacktestFeatureCache | None:
    monthly = _build_monthly_spy_features(
        run_dir,
        horizon_days,
        llm_cache=llm_cache,
        news_window_days=news_window_days,
        min_train_months=min_train_months,
        max_months=max_months,
        pipeline=pipeline,
        quiet=quiet,
    )
    if monthly is None:
        return None
    month_ends, month_features, month_realized = monthly
    macro_event_features = _build_macro_event_features(
        run_dir,
        horizon_days,
        llm_cache=llm_cache,
        pipeline=pipeline,
        quiet=quiet,
    )
    cold_model = _train_horizon_model(
        pd.DataFrame(
            columns=[
                "keyword_score",
                "sentiment",
                "cluster_prior",
                "momentum",
                "beta_spy",
                "forward_return",
            ]
        ),
        "1m",
        horizon_days,
    )
    return BacktestFeatureCache(
        run_dir=run_dir,
        horizon_days=horizon_days,
        month_ends=month_ends,
        month_features=month_features,
        month_realized=month_realized,
        macro_event_features=macro_event_features,
        cold_model=cold_model,
        min_train_months=min_train_months,
    )


def score_backtest_from_cache(
    cache: BacktestFeatureCache,
    config: PredictTuneConfig,
    *,
    pipeline: str = "predict.backtest",
    quiet: bool = False,
) -> pd.DataFrame:
    monthly = _score_monthly_spy_from_features(
        cache, config, pipeline=pipeline, quiet=quiet
    )
    events = _score_macro_event_features(
        cache.macro_event_features,
        cold_model=cache.cold_model,
        config=config,
    )
    parts = [df for df in (monthly, events) if not df.empty]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _monthly_spy_backtest(
    run_dir: Path,
    horizon_days: int,
    *,
    llm_cache: dict[str, dict[str, Any]] | None,
    news_window_days: int = 30,
    min_train_months: int = 12,
    max_months: int = 48,
    config: PredictTuneConfig | None = None,
    quiet: bool = False,
) -> pd.DataFrame:
    """Monthly walk-forward on SPY using point-in-time news + cluster features."""
    cfg = config or DEFAULT_CONFIG
    monthly = _build_monthly_spy_features(
        run_dir,
        horizon_days,
        llm_cache=llm_cache,
        news_window_days=news_window_days,
        min_train_months=min_train_months,
        max_months=max_months,
        quiet=quiet,
    )
    if monthly is None:
        return pd.DataFrame()
    month_ends, month_features, month_realized = monthly
    cache = BacktestFeatureCache(
        run_dir=run_dir,
        horizon_days=horizon_days,
        month_ends=month_ends,
        month_features=month_features,
        month_realized=month_realized,
        macro_event_features=[],
        cold_model=None,
        min_train_months=min_train_months,
    )
    return _score_monthly_spy_from_features(cache, cfg, quiet=quiet)


def _summarize_slice(df: pd.DataFrame, label: str) -> dict[str, Any]:
    if df.empty or len(df) < 3:
        return {"label": label, "n": len(df), "ic": None, "hit_rate": None, "rmse": None}
    pred = df["predicted_return"].to_numpy()
    real = df["realized_return"].to_numpy()
    return {
        "label": label,
        "n": len(df),
        "ic": round(_pearson_ic(pred.tolist(), real.tolist()), 4),
        "hit_rate": round(_hit_rate(pred, real), 4),
        "rmse": round(_rmse(pred, real), 6),
        "mean_realized": round(float(np.mean(real)), 6),
        "mean_predicted": round(float(np.mean(pred)), 6),
    }


def _macro_articles_by_trading_day(
    macro_arts: list[dict[str, Any]],
    spy_index: pd.DatetimeIndex,
    horizon_days: int,
) -> dict[Any, list[dict[str, Any]]]:
    """Group macro articles by SPY trading day (one backtest row per day, not per article)."""
    by_day: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for art in macro_arts:
        pub = art.get("published_at", "")
        if not pub:
            continue
        td = _map_to_trading_day(pub, spy_index)
        if td is None or td not in spy_index:
            continue
        idx = spy_index.get_loc(td)
        if idx + horizon_days >= len(spy_index):
            continue
        by_day[td].append(art)
    return dict(by_day)


def _macro_event_study(
    run_dir: Path,
    horizon_days: int,
    *,
    llm_cache: dict[str, dict[str, Any]] | None,
    config: PredictTuneConfig | None = None,
    quiet: bool = False,
) -> pd.DataFrame:
    """Per trading day with macro news: event tags, cluster, keyword score vs SPY return."""
    cfg = config or DEFAULT_CONFIG
    feature_rows = _build_macro_event_features(
        run_dir, horizon_days, llm_cache=llm_cache, quiet=quiet
    )
    if not feature_rows:
        return pd.DataFrame()
    cold_model = _train_horizon_model(
        pd.DataFrame(
            columns=[
                "keyword_score",
                "sentiment",
                "cluster_prior",
                "momentum",
                "beta_spy",
                "forward_return",
            ]
        ),
        "1m",
        horizon_days,
    )
    return _score_macro_event_features(feature_rows, cold_model=cold_model, config=cfg)


def run_prediction_backtest(
    run_dir: str | Path,
    *,
    horizons: tuple[str, ...] = DEFAULT_HORIZONS,
    news_window_days: int = 7,
    min_train_days: int = 3,
    include_monthly_spy: bool = True,
    include_walk_forward: bool = False,
    max_corpus_for_walk_forward: int = 250,
    quiet: bool = False,
) -> tuple[Path, Path]:
    root = ensure_run_layout(run_dir)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not quiet:
        write_status(
            root,
            PipelineStatus(
                pipeline="predict.backtest",
                phase="starting",
                step=1,
                steps_total=3,
                message="loading corpus and models",
            ),
        )
    llm_cache = load_keyword_cache(root)
    all_preds: list[pd.DataFrame] = []

    corpus = load_corpus(root)
    unique_pub_days = len({a.get("published_at", "")[:10] for a in corpus if a.get("published_at")})

    if include_walk_forward and len(corpus) <= max_corpus_for_walk_forward:
        for horizon in horizons:
            days = HORIZON_TRADING_DAYS.get(horizon, 21)
            if unique_pub_days >= min_train_days + 1:
                obs = _build_label_observations(root, days, llm_cache=llm_cache)
                if not obs.empty and obs["trading_day"].nunique() >= min_train_days + 1:
                    wf = _walk_forward_predictions(
                        obs, horizon, days, min_train_days=min_train_days
                    )
                    if not wf.empty:
                        all_preds.append(wf)

    monthly_spy = pd.DataFrame()
    if include_monthly_spy:
        monthly_spy = _monthly_spy_backtest(
            root,
            HORIZON_TRADING_DAYS.get("1m", 21),
            llm_cache=llm_cache,
            news_window_days=max(news_window_days, 30),
            quiet=quiet,
        )
        if not monthly_spy.empty:
            all_preds.append(monthly_spy)

    event_study = _macro_event_study(
        root,
        HORIZON_TRADING_DAYS.get("1m", 21),
        llm_cache=llm_cache,
        quiet=quiet,
    )
    if not event_study.empty:
        all_preds.append(event_study)

    if not all_preds:
        raise RuntimeError(
            "Backtest produced no rows — ingest dated macro news (RSS) and re-run."
        )

    bt_df = pd.concat(all_preds, ignore_index=True)
    csv_path = root / "reports" / f"backtest_predictions_{today}.csv"
    bt_df.to_csv(csv_path, index=False)

    summaries: list[dict[str, Any]] = []
    for horizon in sorted(bt_df.get("horizon", pd.Series(dtype=str)).dropna().unique()):
        sub = bt_df[bt_df["horizon"] == horizon]
        summaries.append(_summarize_slice(sub, f"overall_{horizon}"))

    for cid in sorted(bt_df.get("cluster_id", pd.Series(dtype=float)).dropna().unique()):
        sub = bt_df[bt_df["cluster_id"] == cid]
        h = sub["horizon"].mode().iloc[0] if "horizon" in sub.columns and not sub.empty else "all"
        summaries.append(_summarize_slice(sub, f"cluster_{int(cid)}_{h}"))

    if "macro_events" in bt_df.columns:
        for tag in list(MACRO_EVENT_TAGS.keys()) + ["none"]:
            sub = bt_df[
                bt_df["macro_events"].astype(str).str.contains(tag, regex=False, na=False)
            ]
            if not sub.empty:
                summaries.append(_summarize_slice(sub, f"event_{tag}"))

    for sector in sorted(bt_df.get("sector_id", pd.Series(dtype=str)).dropna().unique()):
        sub = bt_df[bt_df["sector_id"] == sector]
        summaries.append(_summarize_slice(sub, f"sector_{sector}"))

    sum_df = pd.DataFrame(summaries)
    sum_csv = root / "reports" / f"backtest_summary_{today}.csv"
    sum_df.to_csv(sum_csv, index=False)

    unique_days = bt_df["trading_day"].nunique() if "trading_day" in bt_df.columns else 0
    lines = [
        f"# Prediction backtest — {today}",
        "",
        "Walk-forward evaluation: keyword + sentiment + cluster prior vs realized forward returns.",
        "",
        f"- **Backtest rows:** {len(bt_df)}",
        f"- **Unique trading days:** {unique_days}",
        f"- **News window (monthly SPY):** {max(news_window_days, 30)} days",
        "",
        "## Overall metrics",
        "",
        "| Slice | N | IC | Hit rate | RMSE | Mean pred | Mean realized |",
        "|-------|---|-----|----------|------|-----------|---------------|",
    ]
    for row in summaries:
        ic = row["ic"] if row["ic"] is not None else "n/a"
        hr = row["hit_rate"] if row["hit_rate"] is not None else "n/a"
        rmse = row["rmse"] if row["rmse"] is not None else "n/a"
        mp = row.get("mean_predicted", "n/a")
        mr = row.get("mean_realized", "n/a")
        lines.append(
            f"| {row['label']} | {row['n']} | {ic} | {hr} | {rmse} | {mp} | {mr} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- **IC** = correlation(predicted, realized); positive means directional skill.",
            "- **Cluster slices** show whether news-regime clustering adds predictive power.",
            "- **Event slices** tag articles with macro keywords (fed, inflation, earnings, tariff, employment).",
            "",
            "## Artifacts",
            "",
            f"- `{csv_path.name}` — per-observation predictions vs realized",
            f"- `{sum_csv.name}` — aggregated metrics",
            "",
        ]
    )

    if not event_study.empty:
        lines.extend(["", "## Macro event study (RSS / Fed)", ""])
        for tag in sorted(MACRO_EVENT_TAGS.keys()):
            sub = event_study[
                event_study["macro_events"].astype(str).str.contains(tag, regex=False, na=False)
            ]
            if len(sub) >= 2:
                s = _summarize_slice(
                    sub.rename(columns={"predicted_return": "predicted_return"}),
                    f"macro_event_{tag}",
                )
                lines.append(
                    f"- **{tag}** ({s['n']} articles): IC {s['ic']}, hit rate {s['hit_rate']}, "
                    f"mean realized {s.get('mean_realized', 'n/a')}"
                )
        lines.append("")

    if unique_days < 20:
        lines.extend(
            [
                "## Data caveat",
                "",
                "Yahoo news is recent-only; monthly SPY replay uses point-in-time windows.",
                "Fed/BLS RSS dates deepen macro event study — re-run `news ingest` with `sources=[rss]`.",
                "Use `--walk-forward` for article-level replay on smaller corpora (<250 articles).",
                "",
            ]
        )

    report_path = root / "reports" / f"backtest_report_{today}.md"
    report_path.write_text("\n".join(lines) + "\n")

    update_meta(
        root,
        {
            "L4": {
                "backtest_date": today,
                "backtest_rows": len(bt_df),
                "backtest_trading_days": int(unique_days),
                "backtest_report": str(report_path.relative_to(root)),
            }
        },
    )
    return csv_path, report_path
