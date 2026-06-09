"""Phase 2 — market / sector / ticker keyword tiers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from aitrader.ml.drift import load_keyword_map
from aitrader.nlp.stoplist import filter_coef_map
from aitrader.nlp.keyword_cache import keywords_for_article, load_keyword_cache
from aitrader.nlp.keywords import (
    DEFAULT_MIN_KEYWORD_IC,
    DEFAULT_MIN_SUPPORT,
    HORIZON_TRADING_DAYS,
    MACRO_SEEDS,
    _cap_labels,
    _labels_from_corpus,
    _score_keywords_from_labels,
    _sample_corpus_for_discover,
    ensure_sector_etf_ohlcv,
    load_sector_etfs,
)
from aitrader.nlp.news import load_corpus
from aitrader.nlp.stoplist import is_stoplisted
from aitrader.workspace import ensure_run_layout

KeywordTier = Literal["market", "sector", "ticker"]

TIER_MARKET: KeywordTier = "market"
TIER_SECTOR: KeywordTier = "sector"
TIER_TICKER: KeywordTier = "ticker"


@dataclass
class TierScores:
    market: float = 0.0
    sector: float = 0.0
    ticker: float = 0.0
    market_top: tuple[str, ...] = ()
    sector_top: tuple[str, ...] = ()
    ticker_top: tuple[str, ...] = ()


def infer_tier(phrase: str, article: dict[str, Any]) -> KeywordTier:
    p = phrase.strip().lower()
    tickers = {str(t).upper() for t in (article.get("tickers") or []) if t}
    if phrase.strip().upper() in tickers:
        return TIER_TICKER
    words = p.split()
    if any(w in MACRO_SEEDS for w in words) or p in MACRO_SEEDS:
        return TIER_MARKET
    if (article.get("sector_id") or "macro") == "macro":
        return TIER_MARKET
    return TIER_SECTOR


def tiered_phrases_for_article(
    article: dict[str, Any],
    cache: dict[str, dict[str, Any]] | None,
) -> list[tuple[str, KeywordTier]]:
    title = article.get("title", "")
    body = article.get("body", "")
    out: list[tuple[str, KeywordTier]] = []
    seen: set[str] = set()

    raw: list[Any] = []
    if cache and article.get("id") in cache:
        raw = cache[article["id"]].get("keywords") or []
    elif article.get("llm_keywords"):
        raw = list(article["llm_keywords"])

    if raw and isinstance(raw[0], dict):
        for item in raw:
            phrase = str(item.get("phrase", "")).strip()
            if not phrase or phrase.lower() in seen or is_stoplisted(phrase):
                continue
            seen.add(phrase.lower())
            kw_type = str(item.get("type", "")).lower()
            if kw_type == "macro":
                tier: KeywordTier = TIER_MARKET
            elif phrase.upper() in {str(t).upper() for t in (article.get("tickers") or [])}:
                tier = TIER_TICKER
            else:
                tier = TIER_SECTOR
            out.append((phrase, tier))
    else:
        for kw in keywords_for_article(article, cache):
            if kw.lower() in seen:
                continue
            seen.add(kw.lower())
            out.append((kw, infer_tier(kw, article)))
    return out


def _coef_map_from_rows(rows: list[dict[str, Any]]) -> dict[str, float]:
    raw = {str(r["keyword"]).lower(): float(r.get("coef", 0.0)) for r in rows}
    return filter_coef_map(raw)


def load_ticker_keyword_map(run_dir: Path) -> dict[str, dict[str, float]]:
    path = run_dir / "models" / "keyword_map_tickers.json"
    if not path.exists():
        return {}
    rows = json.loads(path.read_text())
    by_ticker: dict[str, dict[str, float]] = {}
    for r in rows:
        t = str(r.get("ticker", "")).upper()
        kw = str(r.get("keyword", "")).lower()
        if not t or not kw:
            continue
        by_ticker.setdefault(t, {})[kw] = float(r.get("coef", 0.0))
    return by_ticker


def load_tier_coef_maps(run_dir: Path) -> dict[str, Any]:
    market = _coef_map_from_rows(load_keyword_map(run_dir, "market"))
    sectors: dict[str, dict[str, float]] = {}
    models = run_dir / "models"
    if models.exists():
        for path in models.glob("keyword_map_*.json"):
            sid = path.stem.replace("keyword_map_", "")
            if sid in ("market", "anchor", "tickers"):
                continue
            sectors[sid] = _coef_map_from_rows(json.loads(path.read_text()))
    return {
        "market": market,
        "sectors": sectors,
        "tickers": load_ticker_keyword_map(run_dir),
    }


def _contrib(
    phrases: list[tuple[str, KeywordTier]],
    coef_map: dict[str, float],
    tier: KeywordTier,
) -> tuple[float, list[tuple[str, float]]]:
    score = 0.0
    contrib: list[tuple[str, float]] = []
    for phrase, t in phrases:
        if t != tier:
            continue
        coef = coef_map.get(phrase.lower())
        if coef is None:
            continue
        score += coef
        contrib.append((phrase, coef))
    contrib.sort(key=lambda x: abs(x[1]), reverse=True)
    return score, contrib


def score_article_tiers(
    article: dict[str, Any],
    maps: dict[str, Any],
    llm_cache: dict[str, dict[str, Any]] | None,
    *,
    sector_id: str | None = None,
) -> TierScores:
    phrases = tiered_phrases_for_article(article, llm_cache)
    m_score, m_c = _contrib(phrases, maps["market"], TIER_MARKET)
    sec_map = maps["sectors"].get(sector_id or "", {})
    s_score, s_c = _contrib(phrases, sec_map, TIER_SECTOR)
    t_score = 0.0
    t_c: list[tuple[str, float]] = []
    tickers = {str(t).upper() for t in (article.get("tickers") or []) if t}
    for ticker in tickers:
        tmap = maps["tickers"].get(ticker, {})
        ts, tc = _contrib(phrases, tmap, TIER_TICKER)
        t_score += ts
        t_c.extend(tc)
    t_c.sort(key=lambda x: abs(x[1]), reverse=True)
    return TierScores(
        market=m_score,
        sector=s_score,
        ticker=t_score,
        market_top=tuple(k for k, _ in m_c[:5]),
        sector_top=tuple(k for k, _ in s_c[:5]),
        ticker_top=tuple(k for k, _ in t_c[:5]),
    )


def signal_tiered_from_articles(
    articles: list[dict[str, Any]],
    maps: dict[str, Any],
    llm_cache: dict[str, dict[str, Any]] | None,
    *,
    sector_id: str = "anchor",
    max_articles: int | None = None,
    run_dir: str | Path | None = None,
) -> tuple[TierScores, float, list[str], float]:
    """Aggregate tier scores + sentiment mean. SPY ridge uses `.market` only."""
    from aitrader.nlp.sentiment import get_sentiment_scorer

    if max_articles and len(articles) > max_articles:
        articles = sorted(articles, key=lambda a: a.get("published_at", ""))[-max_articles:]
    totals = TierScores()
    m_contrib: list[tuple[str, float]] = []
    scored_arts: list[dict[str, Any]] = []
    for art in articles:
        phrases = tiered_phrases_for_article(art, llm_cache)
        if not phrases:
            continue
        ts = score_article_tiers(art, maps, llm_cache, sector_id=sector_id)
        totals.market += ts.market
        totals.sector += ts.sector
        totals.ticker += ts.ticker
        scored_arts.append(art)
        for kw in ts.market_top:
            m_contrib.append((kw, ts.market))
    m_contrib.sort(key=lambda x: abs(x[1]), reverse=True)
    top = [k for k, _ in m_contrib[:5]]
    scorer = get_sentiment_scorer(run_dir)
    mean_sent, vader_mean = scorer.mean_for_articles(
        scored_arts, llm_cache, require_keywords=False
    )
    return totals, mean_sent, top, vader_mean


def _filter_keywords_in_labels(
    labels,
    *,
    tier: KeywordTier | None = None,
    exclude: set[str] | None = None,
) -> list:
    from aitrader.nlp.keywords import _ArticleLabel

    out: list[_ArticleLabel] = []
    for a in labels:
        kws = [k for k in a.keywords if not is_stoplisted(k)]
        if exclude:
            kws = [k for k in kws if k.lower() not in exclude]
        if tier == TIER_MARKET:
            kws = [k for k in kws if any(s in k.lower() for s in MACRO_SEEDS) or k.lower() in MACRO_SEEDS]
        if not kws:
            continue
        out.append(
            _ArticleLabel(
                sector_id=a.sector_id,
                trading_day=a.trading_day,
                forward_return=a.forward_return,
                label_horizon_days=a.label_horizon_days,
                sentiment=a.sentiment,
                keywords=kws,
            )
        )
    return out


def discover_market_keywords(
    run_dir: str | Path,
    *,
    label_horizon: str = "1m",
    min_keyword_ic: float = DEFAULT_MIN_KEYWORD_IC,
    min_support: int = DEFAULT_MIN_SUPPORT,
    max_keywords: int = 50,
    use_llm: bool = True,
) -> Path:
    root = ensure_run_layout(run_dir)
    horizon_days = HORIZON_TRADING_DAYS.get(label_horizon, 21)
    ensure_sector_etf_ohlcv(root)
    corpus = _sample_corpus_for_discover(load_corpus(root))
    macro_corpus = [
        a
        for a in corpus
        if (a.get("sector_id") or "macro") == "macro"
        or "macro" in (a.get("tags") or [])
    ]
    llm_cache = load_keyword_cache(root) if use_llm else None
    labels = _labels_from_corpus(
        macro_corpus or corpus,
        "anchor",
        root,
        "SPY",
        horizon_days,
        include_macro=True,
        llm_cache=llm_cache,
        use_llm=use_llm,
    )
    labels = _filter_keywords_in_labels(_cap_labels(labels, 4000), tier=TIER_MARKET)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stats = _score_keywords_from_labels(
        labels,
        min_support=min_support,
        min_keyword_ic=min_keyword_ic,
        max_keywords=max_keywords,
        today=today,
    )
    out = root / "models" / "keyword_map_market.json"
    out.write_text(json.dumps(stats, indent=2) + "\n")
    # Backward-compat alias for anchor consumers
    anchor = root / "models" / "keyword_map_anchor.json"
    anchor.write_text(out.read_text())
    return out


def discover_ticker_keywords(
    run_dir: str | Path,
    *,
    label_horizon: str = "1m",
    min_keyword_ic: float = 0.025,
    min_support: int = 3,
    max_keywords_per_ticker: int = 15,
    min_articles_per_ticker: int = 5,
    max_tickers: int = 60,
    use_llm: bool = True,
) -> Path:
    root = ensure_run_layout(run_dir)
    horizon_days = HORIZON_TRADING_DAYS.get(label_horizon, 21)
    ensure_sector_etf_ohlcv(root)
    corpus = [a for a in load_corpus(root) if a.get("tickers")]
    llm_cache = load_keyword_cache(root) if use_llm else None

    ticker_counts: dict[str, int] = {}
    for a in corpus:
        for t in a.get("tickers") or []:
            ticker_counts[str(t).upper()] = ticker_counts.get(str(t).upper(), 0) + 1
    ranked = sorted(ticker_counts.items(), key=lambda x: x[1], reverse=True)[:max_tickers]

    universe = root / "data" / "universe.csv"
    sector_by_ticker: dict[str, str] = {}
    if universe.exists():
        udf = pd.read_csv(universe)
        for _, row in udf.iterrows():
            sector_by_ticker[str(row["ticker"]).upper()] = str(row["sector_id"])

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    all_rows: list[dict[str, Any]] = []
    for ticker, count in ranked:
        if count < min_articles_per_ticker:
            continue
        sector_id = sector_by_ticker.get(ticker, "technology")
        etf = load_sector_etfs(root).get(sector_id, "SPY")
        ticker_corpus = [a for a in corpus if ticker in {str(x).upper() for x in (a.get("tickers") or [])}]
        # Label with sector ETF return — sparse Yahoo headlines rarely vary by date.
        labels = _labels_from_corpus(
            ticker_corpus,
            sector_id,
            root,
            etf,
            horizon_days,
            include_macro=False,
            llm_cache=llm_cache,
            use_llm=use_llm,
        )
        labels = _cap_labels(labels, 1500)
        stats = _score_keywords_from_labels(
            labels,
            min_support=min_support,
            min_keyword_ic=min_keyword_ic,
            max_keywords=max_keywords_per_ticker,
            today=today,
        )
        if not stats and len(labels) >= 6:
            stats = _score_keywords_from_labels(
                labels,
                min_support=2,
                min_keyword_ic=min_keyword_ic * 0.75,
                max_keywords=max_keywords_per_ticker,
                today=today,
            )
            for row in stats:
                row["low_confidence"] = True
        for row in stats:
            row["ticker"] = ticker
            row["tier"] = TIER_TICKER
            all_rows.append(row)

    out = root / "models" / "keyword_map_tickers.json"
    out.write_text(json.dumps(all_rows, indent=2) + "\n")
    return out


def discover_tiered_keywords(
    run_dir: str | Path,
    *,
    label_horizon: str = "1m",
    min_keyword_ic: float = DEFAULT_MIN_KEYWORD_IC,
    min_support: int = DEFAULT_MIN_SUPPORT,
    use_llm: bool = True,
    workers: int | None = None,
    quiet: bool = False,
) -> tuple[list[Path], Path]:
    """L0 market → L1 sectors (exclude L0) → L2 tickers."""
    from aitrader.nlp.keywords import discover_sector_keywords

    root = ensure_run_layout(run_dir)
    paths: list[Path] = []

    market_path = discover_market_keywords(
        root,
        label_horizon=label_horizon,
        min_keyword_ic=min_keyword_ic,
        min_support=min_support,
        use_llm=use_llm,
    )
    paths.append(market_path)

    market_phrases = {
        str(r["keyword"]).lower()
        for r in json.loads(market_path.read_text())
    }

    sector_paths, _sector_report = discover_sector_keywords(
        root,
        label_horizon=label_horizon,
        min_keyword_ic=min_keyword_ic,
        min_support=min_support,
        use_llm=use_llm,
        workers=workers,
        quiet=quiet,
    )
    # Sector discover also writes anchor — restore L0 market map as anchor alias
    (root / "models" / "keyword_map_anchor.json").write_text(market_path.read_text())
    for sp in sector_paths:
        if sp.stem == "keyword_map_anchor":
            continue
        rows = json.loads(sp.read_text())
        filtered = [r for r in rows if str(r["keyword"]).lower() not in market_phrases]
        for r in filtered:
            r["tier"] = TIER_SECTOR
        sp.write_text(json.dumps(filtered, indent=2) + "\n")
        paths.append(sp)

    ticker_path = discover_ticker_keywords(
        root,
        label_horizon=label_horizon,
        min_keyword_ic=min_keyword_ic,
        use_llm=use_llm,
    )
    paths.append(ticker_path)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    overlap = 0
    sector_kws: set[str] = set()
    for sp in sector_paths:
        if "anchor" in sp.name:
            continue
        for r in json.loads(sp.read_text()):
            sector_kws.add(str(r["keyword"]).lower())
    overlap = len(sector_kws & market_phrases)

    report_lines = [
        f"# Tiered keyword report — {today}",
        "",
        f"*Market map:* `{market_path.name}` ({len(json.loads(market_path.read_text()))} keywords)",
        f"*Ticker map:* `{ticker_path.name}` ({len(json.loads(ticker_path.read_text()))} rows)",
        f"*L0/L1 phrase overlap:* {overlap} ({overlap / max(len(sector_kws), 1):.1%} of sector keywords)",
        "",
        "Sector maps written with L0 phrases removed.",
        "",
    ]
    report_path = root / "reports" / f"keyword_tier_report_{today}.md"
    report_path.write_text("\n".join(report_lines) + "\n")
    return paths, report_path


def tier_overlap_stats(run_dir: Path) -> dict[str, Any]:
    market = {str(r["keyword"]).lower() for r in load_keyword_map(run_dir, "market")}
    sector_kws: set[str] = set()
    models = run_dir / "models"
    for path in models.glob("keyword_map_*.json"):
        sid = path.stem.replace("keyword_map_", "")
        if sid in ("market", "anchor", "tickers"):
            continue
        for r in json.loads(path.read_text()):
            sector_kws.add(str(r["keyword"]).lower())
    overlap = market & sector_kws
    tickers = load_ticker_keyword_map(run_dir)
    return {
        "market_keywords": len(market),
        "sector_keywords": len(sector_kws),
        "overlap_count": len(overlap),
        "overlap_pct_of_sector": round(len(overlap) / max(len(sector_kws), 1), 4),
        "tickers_with_maps": len(tickers),
        "ticker_keyword_rows": sum(len(v) for v in tickers.values()),
    }
