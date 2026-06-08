"""Macro news ingest — Recipe — Macro news ingest and clustering (ingest slice for L2)."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from importlib import resources
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import yaml
import yfinance as yf

from aitrader.universe import load_universe_tickers
from aitrader.workspace import ensure_run_layout

NEWS_FIELDS = ("id", "published_at", "title", "body", "source", "tags", "tickers", "sector_id")


@dataclass
class NewsArticle:
    id: str
    published_at: str
    title: str
    body: str
    source: str
    tags: list[str] = field(default_factory=list)
    tickers: list[str] = field(default_factory=list)
    sector_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _article_id(source: str, title: str, published_at: str) -> str:
    raw = f"{source}|{title}|{published_at}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value[:19], fmt[: len(value)])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def load_news_feeds(path: Path | None = None) -> list[dict[str, Any]]:
    if path is not None:
        doc = yaml.safe_load(path.read_text())
    else:
        with resources.files("aitrader.config").joinpath("news_feeds.yaml").open() as fh:
            doc = yaml.safe_load(fh)
    return doc.get("feeds", [])


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_rss_feed(feed: dict[str, Any], *, window_days: int = 7) -> list[NewsArticle]:
    url = feed["url"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    articles: list[NewsArticle] = []
    try:
        import urllib.request

        req = urllib.request.Request(url, headers={"User-Agent": "aitrader/0.1"})
        root = ElementTree.fromstring(urllib.request.urlopen(req, timeout=15).read())
    except Exception:
        return articles

    channel = root.find("channel")
    items = root.findall(".//item") if channel is None else channel.findall("item")
    for item in items:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or feed.get("name", url)).strip()
        body = _strip_html(
            item.findtext("description") or item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""
        )
        pub = _parse_datetime(item.findtext("pubDate") or item.findtext("published"))
        if pub < cutoff or not title:
            continue
        published_at = pub.strftime("%Y-%m-%dT%H:%M:%SZ")
        articles.append(
            NewsArticle(
                id=_article_id(feed["id"], title, published_at),
                published_at=published_at,
                title=title,
                body=body or title,
                source=feed.get("name", feed["id"]),
                tags=list(feed.get("tags", [])),
                tickers=[],
                sector_id="macro",
            )
        )
    return articles


def fetch_yahoo_news(
    ticker: str,
    *,
    ticker_sector: dict[str, str] | None = None,
    sleep_s: float = 0.3,
) -> list[NewsArticle]:
    articles: list[NewsArticle] = []
    try:
        raw_items = yf.Ticker(ticker).news or []
    except Exception:
        return articles
    sector_id = (ticker_sector or {}).get(ticker.upper(), "")
    for item in raw_items:
        content = item.get("content") or {}
        title = (content.get("title") or item.get("title") or "").strip()
        if not title:
            continue
        pub_raw = content.get("pubDate") or content.get("displayTime") or ""
        pub = _parse_datetime(pub_raw if isinstance(pub_raw, str) else None)
        published_at = pub.strftime("%Y-%m-%dT%H:%M:%SZ")
        summary = (content.get("summary") or content.get("description") or title).strip()
        provider = (content.get("provider") or {}).get("displayName") or "yahoo_finance"
        articles.append(
            NewsArticle(
                id=_article_id("yahoo", title, published_at),
                published_at=published_at,
                title=title,
                body=_strip_html(summary),
                source=provider,
                tags=["yahoo_finance"],
                tickers=[ticker.upper()],
                sector_id=sector_id,
            )
        )
    if sleep_s:
        time.sleep(sleep_s)
    return articles


def load_ticker_sector_map(run_dir: Path) -> dict[str, str]:
    import csv

    path = run_dir / "data" / "universe.csv"
    mapping: dict[str, str] = {}
    if not path.exists():
        return mapping
    with path.open() as fh:
        for row in csv.DictReader(fh):
            mapping[row["ticker"].upper()] = row["sector_id"]
    return mapping


def dedupe_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    seen: set[str] = set()
    out: list[NewsArticle] = []
    for art in articles:
        if art.id in seen:
            continue
        seen.add(art.id)
        out.append(art)
    return out


def write_news_jsonl(run_dir: str | Path, articles: list[NewsArticle], *, date: str | None = None) -> Path:
    root = ensure_run_layout(run_dir)
    news_dir = root / "data" / "news"
    news_dir.mkdir(parents=True, exist_ok=True)
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = news_dir / f"{date}.jsonl"
    with out_path.open("w") as fh:
        for art in articles:
            fh.write(json.dumps(art.to_dict()) + "\n")
    return out_path


def append_corpus_jsonl(run_dir: str | Path, articles: list[NewsArticle]) -> Path:
    """Append deduped articles to rolling corpus for keyword discovery."""
    root = ensure_run_layout(run_dir)
    corpus_path = root / "data" / "news" / "corpus.jsonl"
    existing_ids: set[str] = set()
    if corpus_path.exists():
        with corpus_path.open() as fh:
            for line in fh:
                row = json.loads(line)
                existing_ids.add(row["id"])
    with corpus_path.open("a") as fh:
        for art in articles:
            if art.id in existing_ids:
                continue
            fh.write(json.dumps(art.to_dict()) + "\n")
            existing_ids.add(art.id)
    return corpus_path


def load_corpus(run_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(run_dir).expanduser().resolve()
    articles: list[dict[str, Any]] = []
    news_dir = root / "data" / "news"
    if not news_dir.exists():
        return articles
    paths = sorted(news_dir.glob("*.jsonl"))
    seen: set[str] = set()
    for path in paths:
        with path.open() as fh:
            for line in fh:
                row = json.loads(line)
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                articles.append(row)
    return articles


def load_google_news_feeds(path: Path | None = None) -> list[dict[str, Any]]:
    from aitrader.nlp.gdelt import load_historical_news_sources

    cfg = load_historical_news_sources(path)
    gnews = cfg.get("sources", {}).get("google_news_rss", {})
    if not gnews.get("enabled", True):
        return []
    return list(gnews.get("feeds", []))


def fetch_google_news_feeds(
    *,
    window_days: int = 400,
    sources_path: Path | None = None,
) -> list[NewsArticle]:
    articles: list[NewsArticle] = []
    for feed in load_google_news_feeds(sources_path):
        articles.extend(fetch_rss_feed(feed, window_days=window_days))
    return articles


def ingest_historical_news(
    run_dir: str | Path,
    *,
    timespan: str = "90days",
    rss_window_days: int = 365,
    include_gdelt: bool = True,
    include_gkg: bool = True,
    include_gnews: bool = True,
    include_rss: bool = True,
    gkg_lookback_days: int | None = None,
    gkg_sample_days: int | None = None,
) -> tuple[Path, int]:
    """Ingest dated historical macro news (GKG bulk + GDELT DOC + Google News + RSS)."""
    from aitrader.nlp.gdelt import ingest_gdelt_historical
    from aitrader.nlp.gdelt_gkg import ingest_gdelt_gkg

    root = ensure_run_layout(run_dir)
    total = 0
    last_path = root / "data" / "news" / "corpus.jsonl"

    if include_rss:
        path, count = ingest_news(
            run_dir,
            window_days=rss_window_days,
            sources=["rss"],
        )
        last_path = path
        total += count

    if include_gnews:
        gnews_arts = fetch_google_news_feeds(window_days=max(rss_window_days, 400))
        if gnews_arts:
            gnews_arts = dedupe_articles(gnews_arts)
            write_news_jsonl(root, gnews_arts)
            append_corpus_jsonl(root, gnews_arts)
            total += len(gnews_arts)

    if include_gkg:
        kwargs: dict[str, Any] = {}
        if gkg_lookback_days is not None:
            kwargs["lookback_days"] = gkg_lookback_days
        if gkg_sample_days is not None:
            kwargs["sample_days"] = gkg_sample_days
        path, count = ingest_gdelt_gkg(root, **kwargs)
        last_path = path
        total += count

    if include_gdelt:
        path, count = ingest_gdelt_historical(root, timespan=timespan)
        last_path = path
        total += count

    return last_path, total


def ingest_news(
    run_dir: str | Path,
    *,
    window_days: int = 7,
    sources: list[str] | None = None,
    yahoo_tickers: list[str] | None = None,
    yahoo_universe: bool = False,
) -> tuple[Path, int]:
    """Ingest macro news into dated jsonl + rolling corpus."""
    root = ensure_run_layout(run_dir)
    sources = sources or ["rss", "yahoo_finance"]
    articles: list[NewsArticle] = []

    if "rss" in sources:
        for feed in load_news_feeds():
            articles.extend(fetch_rss_feed(feed, window_days=window_days))

    ticker_sector = load_ticker_sector_map(root)
    if "yahoo_finance" in sources:
        if yahoo_universe:
            tickers = load_universe_tickers(root)
        else:
            tickers = yahoo_tickers or ["SPY", "IWM"]
            sectors_path = root / "config" / "sectors.yaml"
            if sectors_path.exists():
                sectors_doc = yaml.safe_load(sectors_path.read_text())
                for sector in sectors_doc.get("sectors", []):
                    tickers.append(sector["etf_proxy"])
            tickers = sorted(set(tickers))
        for ticker in tickers:
            articles.extend(
                fetch_yahoo_news(ticker, ticker_sector=ticker_sector, sleep_s=0.25)
            )

    articles = dedupe_articles(articles)
    jsonl_path = write_news_jsonl(root, articles)
    append_corpus_jsonl(root, articles)
    return jsonl_path, len(articles)
