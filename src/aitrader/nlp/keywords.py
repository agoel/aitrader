"""Sentiment keyword discovery — Recipe — Sentiment keyword discovery."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from aitrader.data.yahoo import ingest_ticker
from aitrader.nlp.keyword_cache import keywords_for_article, load_keyword_cache as load_llm_keyword_cache
from aitrader.nlp.news import ingest_news, load_corpus
from aitrader.nlp.parallel import default_workers, parallel_map
from aitrader.progress import RunProgress, parallel_map_progress
from aitrader.workspace import ensure_run_layout

HORIZON_TRADING_DAYS = {"2w": 10, "1m": 21, "3m": 63}

STOPWORDS = frozenset(
    """
    a an the and or but in on at to for of is are was were be been being
    it its this that with from as by about into over after before not no
    yes will would could should has have had do does did say says said
    """.split()
)

MACRO_SEEDS = frozenset(
    """
    fed rate rates inflation jobs employment gdp recession tariff tariffs
    earnings oil crude treasury yield yields hike cut cuts stimulus gdp
    consumer spending retail sales manufacturing pmi unemployment claims
    """.split()
)


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    return [t for t in text.split() if len(t) > 2 and t not in STOPWORDS]


def extract_keywords(title: str, body: str) -> list[str]:
    tokens = _tokenize(f"{title} {body}")
    keywords: set[str] = set()
    for t in tokens:
        if t in MACRO_SEEDS or len(t) >= 4:
            keywords.add(t)
    for i in range(len(tokens) - 1):
        bigram = f"{tokens[i]} {tokens[i+1]}"
        if tokens[i] in MACRO_SEEDS or tokens[i + 1] in MACRO_SEEDS:
            keywords.add(bigram)
    return sorted(keywords)


def _vader_sentiment(text: str) -> float:
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        return SentimentIntensityAnalyzer().polarity_scores(text)["compound"]
    except Exception:
        return 0.0


def _pearson_ic(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 5:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den_x = math.sqrt(sum((a - mx) ** 2 for a in x))
    den_y = math.sqrt(sum((b - my) ** 2 for b in y))
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def load_sector_etfs(run_dir: Path) -> dict[str, str]:
    path = run_dir / "config" / "sectors.yaml"
    if not path.exists():
        return {}
    doc = yaml.safe_load(path.read_text())
    return {s["id"]: s["etf_proxy"] for s in doc.get("sectors", [])}


def ensure_sector_etf_ohlcv(run_dir: Path, *, refresh: bool = True) -> list[str]:
    """Pull or refresh sector ETF bars needed for keyword labels."""
    etfs = set(load_sector_etfs(run_dir).values()) | {"SPY", "IWM"}
    fetched: list[str] = []
    ohlcv_dir = run_dir / "data" / "ohlcv"
    for etf in sorted(etfs):
        path = ohlcv_dir / f"{etf}.parquet"
        if not path.exists() or refresh:
            ingest_ticker(etf, ohlcv_dir, years=5, sleep_s=0.3)
            fetched.append(etf)
    return fetched


def load_etf_closes(run_dir: Path, etf_ticker: str) -> pd.Series:
    parquet = run_dir / "data" / "ohlcv" / f"{etf_ticker}.parquet"
    if not parquet.exists():
        return pd.Series(dtype=float)
    df = pd.read_parquet(parquet)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.sort_values("date").set_index("date")
    return df["close"]


def forward_return_at(
    closes: pd.Series,
    trading_day: pd.Timestamp,
    horizon_days: int,
    *,
    fallback_days: tuple[int, ...] = (5, 1),
) -> tuple[float | None, int]:
    """Return (forward_return, horizon_used) with shorter fallback near series end."""
    if trading_day not in closes.index:
        return None, horizon_days
    idx = closes.index.get_loc(trading_day)
    for h in (horizon_days, *fallback_days):
        if idx + h < len(closes):
            ret = float(closes.iloc[idx + h] / closes.iloc[idx] - 1.0)
            return ret, h
    if idx > 0:
        ret = float(closes.iloc[idx] / closes.iloc[idx - 1] - 1.0)
        return ret, 0
    return None, horizon_days


def _map_to_trading_day(pub: str, trading_index: pd.DatetimeIndex) -> pd.Timestamp | None:
    d = pd.Timestamp(pub[:10])
    valid_future = trading_index[trading_index >= d]
    if len(valid_future) > 0:
        return valid_future[0]
    valid_past = trading_index[trading_index <= d]
    if len(valid_past) > 0:
        return valid_past[-1]
    return None


@dataclass
class _ArticleLabel:
    sector_id: str
    trading_day: pd.Timestamp
    forward_return: float
    label_horizon_days: int
    sentiment: float
    keywords: list[str]


def _article_keywords(
    row: dict[str, Any],
    llm_cache: dict[str, dict[str, Any]] | None,
    *,
    use_llm: bool,
) -> list[str]:
    if use_llm:
        llm_kws = keywords_for_article(row, llm_cache)
        if llm_kws:
            return llm_kws
    return extract_keywords(row.get("title", ""), row.get("body", ""))


def _labels_from_corpus(
    corpus: list[dict[str, Any]],
    sector_id: str,
    run_dir: Path,
    sector_etf: str,
    horizon_days: int,
    *,
    include_macro: bool = True,
    llm_cache: dict[str, dict[str, Any]] | None = None,
    use_llm: bool = True,
) -> list[_ArticleLabel]:
    """Label articles with per-ticker returns when available (cross-sectional variance)."""
    labels: list[_ArticleLabel] = []
    sector_closes = load_etf_closes(run_dir, sector_etf)
    if sector_closes.empty:
        return labels
    ticker_cache: dict[str, pd.Series] = {}

    def _closes_for(ticker: str) -> pd.Series:
        t = ticker.upper()
        if t not in ticker_cache:
            c = load_etf_closes(run_dir, t)
            ticker_cache[t] = c if not c.empty else sector_closes
        return ticker_cache[t]

    for row in corpus:
        row_sector = row.get("sector_id") or "macro"
        if row_sector == sector_id:
            pass
        elif row_sector == "macro" and include_macro:
            pass
        else:
            continue
        pub = row.get("published_at", "")
        if not pub:
            continue
        tickers = [t.upper() for t in (row.get("tickers") or []) if t]
        price_tickers = tickers if tickers else [sector_etf]
        kws = _article_keywords(row, llm_cache, use_llm=use_llm)
        if not kws:
            continue
        sentiment = _vader_sentiment(f"{row.get('title','')} {row.get('body','')}")
        for ticker in price_tickers:
            closes = _closes_for(ticker)
            trading_day = _map_to_trading_day(pub, closes.index)
            if trading_day is None or trading_day not in closes.index:
                continue
            fwd_ret, used_h = forward_return_at(closes, trading_day, horizon_days)
            if fwd_ret is None:
                continue
            labels.append(
                _ArticleLabel(
                    sector_id=sector_id,
                    trading_day=trading_day,
                    forward_return=fwd_ret,
                    label_horizon_days=used_h,
                    sentiment=sentiment,
                    keywords=kws,
                )
            )
            break
    return labels


def _sample_corpus_for_discover(
    corpus: list[dict[str, Any]],
    *,
    lookback_years: int = 5,
    max_articles: int = 8000,
) -> list[dict[str, Any]]:
    """Limit discover to recent history so IC fit stays fast on large corpora."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_years * 365)).strftime("%Y-%m-%d")
    filtered = [a for a in corpus if (a.get("published_at") or "")[:10] >= cutoff]
    if len(filtered) <= max_articles:
        return filtered
    step = len(filtered) / max_articles
    return [filtered[int(i * step)] for i in range(max_articles)]


def _cap_labels(labels: list[_ArticleLabel], max_labels: int) -> list[_ArticleLabel]:
    if len(labels) <= max_labels:
        return labels
    step = len(labels) / max_labels
    return [labels[int(i * step)] for i in range(max_labels)]


def _score_keywords_from_labels(
    labels: list[_ArticleLabel],
    *,
    min_support: int,
    min_keyword_ic: float,
    max_keywords: int,
    today: str,
    max_keywords_to_score: int = 3000,
) -> list[dict[str, Any]]:
    if len(labels) < min_support:
        return []

    all_returns = [a.forward_return for a in labels]
    baseline = sum(all_returns) / len(all_returns)
    keyword_stats: list[dict[str, Any]] = []
    kw_to_present: dict[str, list[float]] = {}
    for a in labels:
        for kw in a.keywords:
            kw_to_present.setdefault(kw, []).append(a.forward_return)

    candidates = [
        (kw, rets)
        for kw, rets in kw_to_present.items()
        if len(rets) >= min_support
    ]
    candidates.sort(key=lambda x: len(x[1]), reverse=True)
    candidates = candidates[:max_keywords_to_score]

    for kw, present in candidates:
        support = len(present)
        absent = [a.forward_return for a in labels if kw not in a.keywords]
        xs = [1.0 if kw in a.keywords else 0.0 for a in labels]
        ys = [a.forward_return for a in labels]
        ic = _pearson_ic(xs, ys)
        if abs(ic) < min_keyword_ic:
            mean_present = sum(present) / len(present)
            ic = (mean_present - baseline) / (pd.Series(all_returns).std() + 1e-9)
            if abs(ic) < min_keyword_ic * 0.5:
                continue
        sents = [a.sentiment for a in labels if kw in a.keywords]
        keyword_stats.append(
            {
                "keyword": kw,
                "coef": round(ic * 0.01, 4),
                "ic": round(float(ic), 4),
                "direction": "bullish" if ic > 0 else "bearish",
                "support": support,
                "avg_sentiment": round(sum(sents) / len(sents), 4) if sents else 0.0,
                "mean_return_present": round(sum(present) / len(present), 4),
                "mean_return_absent": round(sum(absent) / len(absent), 4) if absent else None,
                "last_fit": today,
            }
        )

    keyword_stats.sort(key=lambda x: abs(x["ic"]), reverse=True)
    return keyword_stats[:max_keywords]


def _discover_sector_job(
    args: tuple[Any, ...],
) -> tuple[str, str, list[dict[str, Any]]]:
    (
        sector_id,
        etf,
        corpus,
        root,
        horizon_days,
        llm_cache,
        use_llm,
        min_support,
        min_keyword_ic,
        max_keywords_per_sector,
        max_labels_per_sector,
        today,
    ) = args
    return _discover_one_sector(
        sector_id,
        etf,
        corpus,
        root,
        horizon_days,
        llm_cache=llm_cache,
        use_llm=use_llm,
        min_support=min_support,
        min_keyword_ic=min_keyword_ic,
        max_keywords_per_sector=max_keywords_per_sector,
        max_labels_per_sector=max_labels_per_sector,
        today=today,
    )


def _discover_one_sector(
    sector_id: str,
    etf: str,
    corpus: list[dict[str, Any]],
    root: Path,
    horizon_days: int,
    *,
    llm_cache: dict[str, dict[str, Any]] | None,
    use_llm: bool,
    min_support: int,
    min_keyword_ic: float,
    max_keywords_per_sector: int,
    max_labels_per_sector: int,
    today: str,
) -> tuple[str, str, list[dict[str, Any]]]:
    labels = _labels_from_corpus(
        corpus,
        sector_id,
        root,
        etf,
        horizon_days,
        include_macro=True,
        llm_cache=llm_cache,
        use_llm=use_llm,
    )
    labels = _cap_labels(labels, max_labels_per_sector)
    keyword_stats = _score_keywords_from_labels(
        labels,
        min_support=min_support,
        min_keyword_ic=min_keyword_ic,
        max_keywords=max_keywords_per_sector,
        today=today,
    )
    if len(keyword_stats) < 5 and min_keyword_ic >= 0.03:
        keyword_stats = _score_keywords_from_labels(
            labels,
            min_support=max(2, min_support - 1),
            min_keyword_ic=min_keyword_ic * 0.5,
            max_keywords=max_keywords_per_sector,
            today=today,
        )
        for row in keyword_stats:
            row["low_confidence"] = True
    return sector_id, etf, keyword_stats


def discover_sector_keywords(
    run_dir: str | Path,
    *,
    label_horizon: str = "1m",
    min_keyword_ic: float = 0.03,
    max_keywords_per_sector: int = 50,
    min_support: int = 3,
    enrich_yahoo: bool = True,
    use_llm: bool = True,
    max_labels_per_sector: int = 4000,
    workers: int | None = None,
    quiet: bool = False,
) -> tuple[list[Path], Path]:
    root = ensure_run_layout(run_dir)
    horizon_days = HORIZON_TRADING_DAYS.get(label_horizon, 21)
    ensure_sector_etf_ohlcv(root)

    corpus = load_corpus(root)
    llm_cache = load_llm_keyword_cache(root) if use_llm else None
    if use_llm and llm_cache:
        corpus = [a for a in corpus if a.get("id") in llm_cache and llm_cache[a["id"]].get("keywords")]
    corpus = _sample_corpus_for_discover(corpus)
    if enrich_yahoo and len(corpus) < 200:
        ingest_news(
            root,
            window_days=30,
            sources=["yahoo_finance"],
            yahoo_universe=True,
        )
        corpus = load_corpus(root)

    sector_etfs = load_sector_etfs(root)
    sector_etfs["anchor"] = "SPY"
    keyword_source = "cursor+ic" if (use_llm and llm_cache) else "tokens+ic"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_lines = [
        f"# Keyword report — {today}",
        "",
        f"*Keyword source: {keyword_source}*",
        f"*Labels use `{label_horizon}` forward return with 5d/1d/reaction fallbacks near series end.*",
        "",
    ]
    out_paths: list[Path] = []
    sector_jobs = [
        (sid, etf)
        for sid, etf in sorted(sector_etfs.items())
        if etf
    ]

    discover_args = [
        (
            sid,
            etf,
            corpus,
            root,
            horizon_days,
            llm_cache,
            use_llm,
            min_support,
            min_keyword_ic,
            max_keywords_per_sector,
            max_labels_per_sector,
            today,
        )
        for sid, etf in sector_jobs
    ]
    prog = RunProgress(
        "keyword-discover",
        len(discover_args),
        run_dir=root,
        pipeline="keywords.discover",
        phase="sector_ic_fit",
        quiet=quiet,
        every=1,
    )
    if default_workers(workers) <= 1 or len(discover_args) <= 1:
        prog.start()
        results = []
        for args in discover_args:
            sid = args[0]
            results.append(_discover_sector_job(args))
            prog.advance(1, message=f"sector {sid}")
        prog.finish()
    else:
        results = parallel_map_progress(
            _discover_sector_job,
            discover_args,
            prog,
            workers=workers,
            use_threads=True,
        )

    models_dir = root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    for sector_id, etf, keyword_stats in results:
        out_path = models_dir / f"keyword_map_{sector_id}.json"
        out_path.write_text(json.dumps(keyword_stats, indent=2) + "\n")
        out_paths.append(out_path)

        report_lines.append(f"## {sector_id} ({etf})")
        if keyword_stats:
            for row in keyword_stats[:10]:
                report_lines.append(
                    f"- **{row['keyword']}** — IC {row['ic']}, {row['direction']}, support {row['support']}"
                )
        else:
            report_lines.append("- *(sparse — fewer than 5 keywords passed IC filter)*")
        report_lines.append("")

    report_path = root / "reports" / f"keyword_report_{today}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines) + "\n")
    return out_paths, report_path
