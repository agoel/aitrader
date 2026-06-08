"""GDELT DOC 2.0 historical news ingest — dated macro articles for backtest corpus."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from aitrader.nlp.news import NewsArticle, _article_id, append_corpus_jsonl, write_news_jsonl

GDELT_USER_AGENT = "aitrader/0.1 (macro-news-ingest)"


def load_historical_news_sources(path: Path | None = None) -> dict[str, Any]:
    if path is not None:
        return yaml.safe_load(path.read_text())
    with resources.files("aitrader.config").joinpath("historical_news_sources.yaml").open() as fh:
        return yaml.safe_load(fh)


def _parse_seendate(value: str) -> str:
    """GDELT seendate YYYYMMDDTHHMMSSZ → ISO UTC."""
    value = (value or "").strip()
    if not value:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        dt = datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
        return dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gdelt_article_from_row(row: dict[str, Any], *, query_id: str, tags: list[str]) -> NewsArticle:
    title = (row.get("title") or "").strip() or row.get("url", "")
    published_at = _parse_seendate(str(row.get("seendate", "")))
    domain = (row.get("domain") or "gdelt").strip()
    url = (row.get("url") or "").strip()
    body = f"{title}. Source: {domain}. {url}".strip()
    source = f"gdelt:{query_id}"
    return NewsArticle(
        id=_article_id(source, title, published_at),
        published_at=published_at,
        title=title,
        body=body,
        source=source,
        tags=list(tags),
        tickers=[],
        sector_id="macro",
    )


def fetch_gdelt_artlist(
    query: str,
    *,
    timespan: str = "90days",
    maxrecords: int = 250,
    sort: str = "DateDesc",
    api_base: str = "https://api.gdeltproject.org/api/v2/doc/doc",
    rate_limit_s: float = 6.0,
    sleep_s: float | None = None,
) -> list[dict[str, Any]]:
    """Fetch article list from GDELT DOC 2.0 API (JSON)."""
    params = {
        "query": query,
        "mode": "ArtList",
        "maxrecords": str(maxrecords),
        "format": "json",
        "timespan": timespan,
        "sort": sort,
    }
    url = f"{api_base}?{urllib.parse.urlencode(params)}"
    if sleep_s is not None and sleep_s > 0:
        time.sleep(sleep_s)
    req = urllib.request.Request(url, headers={"User-Agent": GDELT_USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError:
        return []
    if raw.strip().startswith("Please limit requests"):
        return []
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        return []
    articles = doc.get("articles")
    return articles if isinstance(articles, list) else []


def ingest_gdelt_historical(
    run_dir: str | Path,
    *,
    timespan: str = "90days",
    maxrecords_per_query: int | None = None,
    sources_path: Path | None = None,
) -> tuple[Path, int]:
    """Ingest GDELT macro queries into dated jsonl + rolling corpus."""
    root = Path(run_dir).expanduser().resolve()
    cfg = load_historical_news_sources(sources_path)
    gdelt = cfg.get("sources", {}).get("gdelt_doc", {})
    if not gdelt.get("enabled", True):
        return root / "data" / "news" / "corpus.jsonl", 0

    api_base = gdelt.get("api_base", "https://api.gdeltproject.org/api/v2/doc/doc")
    rate_limit = float(gdelt.get("rate_limit_s", 6.0))
    maxrec = maxrecords_per_query or int(gdelt.get("maxrecords_per_query", 250))
    sort = gdelt.get("sort", "DateDesc")
    queries = gdelt.get("queries", [])

    articles: list[NewsArticle] = []
    for i, q in enumerate(queries):
        query_id = q.get("id", f"q{i}")
        query_text = q.get("query", "")
        tags = list(q.get("tags", ["macro"]))
        if not query_text:
            continue
        sleep_s = rate_limit if i > 0 else 0.0
        rows = fetch_gdelt_artlist(
            query_text,
            timespan=timespan,
            maxrecords=maxrec,
            sort=sort,
            api_base=api_base,
            sleep_s=sleep_s,
        )
        for row in rows:
            if not isinstance(row, dict):
                continue
            articles.append(_gdelt_article_from_row(row, query_id=query_id, tags=tags))

    jsonl_path = write_news_jsonl(root, articles)
    append_corpus_jsonl(root, articles)
    return jsonl_path, len(articles)
