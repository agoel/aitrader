"""GDELT GKG 2.0 bulk ingest — multi-year dated macro news from masterfilelist."""

from __future__ import annotations

import io
import re
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from aitrader.nlp.gdelt import GDELT_USER_AGENT, load_historical_news_sources
from aitrader.nlp.news import NewsArticle, _article_id, append_corpus_jsonl, write_news_jsonl

MASTER_URL = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"
GKG_SUFFIX = ".gkg.csv.zip"

# GKG V2.1 tab columns (0-based).
_COL_DATE = 1
_COL_DOMAIN = 3
_COL_URL = 4
_COL_THEMES = 7
_COL_ORGS = 13
_COL_PERSONS = 11
_COL_TONE = 15
_COL_V2EXTRAS = 22

MACRO_THEME_MARKERS: tuple[str, ...] = (
    "ECON_STOCKMARKET",
    "ECON_INFLATION",
    "ECON_INTERESTRATE",
    "ECON_UNEMPLOYMENT",
    "ECON_TRADE",
    "ECON_CENTRALBANK",
    "ECON_",
    "EPU_CATS_",
    "EPU_POLICY",
    "STOCKMARKET",
    "INFLATION",
    "FEDERALRESERVE",
    "CENTRAL_BANK",
)

PREFERRED_DOMAINS: frozenset[str] = frozenset(
    {
        "reuters.com",
        "bloomberg.com",
        "cnbc.com",
        "marketwatch.com",
        "wsj.com",
        "ft.com",
        "federalreserve.gov",
        "bls.gov",
        "bea.gov",
        "treasury.gov",
        "sec.gov",
        "economist.com",
        "barrons.com",
        "finance.yahoo.com",
    }
)

_THEME_TAG_MAP: list[tuple[str, str]] = [
    ("ECON_INFLATION", "inflation"),
    ("ECON_INTERESTRATE", "fed"),
    ("ECON_UNEMPLOYMENT", "employment"),
    ("ECON_TRADE", "tariff"),
    ("ECON_STOCKMARKET", "earnings"),
    ("FEDERALRESERVE", "fed"),
    ("CENTRAL_BANK", "fed"),
    ("INFLATION", "inflation"),
    ("TARIFF", "tariff"),
]


def _cache_dir(run_dir: Path) -> Path:
    d = run_dir / "data" / "news" / "gkg_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fetch_masterfilelist(*, cache_dir: Path | None = None, max_age_hours: int = 24) -> list[str]:
    """Return GKG zip URLs from GDELT masterfilelist (cached)."""
    cache_path = (cache_dir or Path(".")) / "masterfilelist.txt"
    if cache_path.exists():
        age_h = (time.time() - cache_path.stat().st_mtime) / 3600.0
        if age_h < max_age_hours:
            lines = cache_path.read_text().splitlines()
            return [ln.split()[-1] for ln in lines if GKG_SUFFIX in ln]

    req = urllib.request.Request(MASTER_URL, headers={"User-Agent": GDELT_USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    if cache_dir is not None:
        cache_path.write_text(raw)
    return [ln.split()[-1] for ln in raw.splitlines() if GKG_SUFFIX in ln]


def _parse_gkg_timestamp(url: str) -> str:
    name = url.rsplit("/", 1)[-1]
    return name.replace(GKG_SUFFIX, "")


def select_gkg_urls(
    gkg_urls: list[str],
    *,
    start: date,
    end: date,
    sample_days: int = 7,
    hour_utc: int = 12,
) -> list[str]:
    """Pick one GKG file per sample day closest to hour_utc."""
    by_day: dict[str, list[tuple[int, str]]] = {}
    start_s = start.strftime("%Y%m%d")
    end_s = end.strftime("%Y%m%d")
    target_min = int(hour_utc) * 10000

    for url in gkg_urls:
        ts = _parse_gkg_timestamp(url)
        if len(ts) < 14:
            continue
        day = ts[:8]
        if day < start_s or day > end_s:
            continue
        hhmmss = int(ts[8:14])
        by_day.setdefault(day, []).append((hhmmss, url))

    selected: list[str] = []
    cur = start
    while cur <= end:
        day = cur.strftime("%Y%m%d")
        candidates = by_day.get(day)
        if candidates:
            _, best = min(candidates, key=lambda t: abs(t[0] - target_min))
            selected.append(best)
        cur += timedelta(days=max(1, sample_days))
    return selected


def _themes_match(themes: str) -> bool:
    upper = themes.upper()
    return any(m in upper for m in MACRO_THEME_MARKERS)


def _tags_from_themes(themes: str) -> list[str]:
    upper = themes.upper()
    tags = ["macro"]
    for marker, tag in _THEME_TAG_MAP:
        if marker in upper and tag not in tags:
            tags.append(tag)
    return tags


def _title_from_gkg(parts: list[str]) -> str:
    if len(parts) > _COL_V2EXTRAS and parts[_COL_V2EXTRAS]:
        for chunk in reversed(parts[_COL_V2EXTRAS].split("|")):
            text = chunk.strip()
            if text and not text.isdigit() and len(text) > 8:
                return text[:240]
    url = parts[_COL_URL] if len(parts) > _COL_URL else ""
    if url:
        slug = url.rstrip("/").split("/")[-1]
        slug = re.sub(r"\.[a-z]+$", "", slug, flags=re.I)
        slug = slug.replace("-", " ").replace("_", " ")
        if len(slug) > 12:
            return slug[:240]
    if len(parts) > _COL_ORGS and parts[_COL_ORGS]:
        return parts[_COL_ORGS].split(";")[0][:240]
    return "Macro economic news"


def _body_from_gkg(parts: list[str]) -> str:
    themes = parts[_COL_THEMES] if len(parts) > _COL_THEMES else ""
    orgs = parts[_COL_ORGS] if len(parts) > _COL_ORGS else ""
    persons = parts[_COL_PERSONS] if len(parts) > _COL_PERSONS else ""
    tone = parts[_COL_TONE] if len(parts) > _COL_TONE else ""
    url = parts[_COL_URL] if len(parts) > _COL_URL else ""
    bits = [_title_from_gkg(parts)]
    if orgs:
        bits.append(f"Organizations: {orgs[:500]}")
    if persons:
        bits.append(f"Persons: {persons[:300]}")
    if themes:
        bits.append(f"Themes: {themes[:400]}")
    if tone:
        bits.append(f"Tone: {tone[:80]}")
    if url:
        bits.append(url)
    return ". ".join(bits)


def _published_from_gkg(date_field: str) -> str:
    try:
        dt = datetime.strptime(date_field[:14], "%Y%m%d%H%M%S")
        return dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_score(parts: list[str]) -> int:
    domain = (parts[_COL_DOMAIN] if len(parts) > _COL_DOMAIN else "").lower()
    score = 0
    if any(d in domain for d in PREFERRED_DOMAINS):
        score += 10
    if "ECON_" in (parts[_COL_THEMES] if len(parts) > _COL_THEMES else "").upper():
        score += 5
    return score


def parse_gkg_zip_bytes(
    data: bytes,
    *,
    max_articles: int = 80,
    prefer_domains: bool = True,
) -> list[NewsArticle]:
    """Parse a GKG zip and return macro-themed articles."""
    articles: list[NewsArticle] = []
    candidates: list[tuple[int, NewsArticle]] = []

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not names:
            return articles
        with zf.open(names[0]) as fh:
            for raw_line in fh:
                try:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
                except Exception:
                    continue
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 8:
                    continue
                themes = parts[_COL_THEMES]
                if not _themes_match(themes):
                    continue
                url = parts[_COL_URL] if len(parts) > _COL_URL else ""
                if not url.startswith("http"):
                    continue
                published_at = _published_from_gkg(parts[_COL_DATE])
                title = _title_from_gkg(parts)
                body = _body_from_gkg(parts)
                domain = parts[_COL_DOMAIN] if len(parts) > _COL_DOMAIN else "gdelt"
                tags = _tags_from_themes(themes)
                source = f"gdelt_gkg:{domain}"
                art = NewsArticle(
                    id=_article_id(source, title, published_at),
                    published_at=published_at,
                    title=title,
                    body=body,
                    source=source,
                    tags=tags,
                    tickers=[],
                    sector_id="macro",
                )
                score = _row_score(parts)
                if prefer_domains and score == 0 and len(candidates) > max_articles * 3:
                    continue
                candidates.append((score, art))

    candidates.sort(key=lambda t: t[0], reverse=True)
    seen: set[str] = set()
    for _, art in candidates:
        if art.id in seen:
            continue
        seen.add(art.id)
        articles.append(art)
        if len(articles) >= max_articles:
            break
    return articles


def download_gkg_zip(url: str, *, sleep_s: float = 0.2) -> bytes | None:
    if sleep_s > 0:
        time.sleep(sleep_s)
    req = urllib.request.Request(url, headers={"User-Agent": GDELT_USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()
    except (urllib.error.URLError, TimeoutError):
        return None


def ingest_gdelt_gkg(
    run_dir: str | Path,
    *,
    lookback_days: int = 1825,
    sample_days: int = 7,
    max_per_file: int = 80,
    sources_path: Path | None = None,
) -> tuple[Path, int]:
    """Backfill dated macro news from GDELT GKG 2.0 masterfilelist."""
    root = Path(run_dir).expanduser().resolve()
    cfg = load_historical_news_sources(sources_path)
    gkg_cfg = cfg.get("sources", {}).get("gdelt_gkg", {})
    if not gkg_cfg.get("enabled", True):
        return root / "data" / "news" / "corpus.jsonl", 0

    lookback_days = int(gkg_cfg.get("lookback_days", lookback_days))
    sample_days = int(gkg_cfg.get("sample_days", sample_days))
    max_per_file = int(gkg_cfg.get("max_per_file", max_per_file))
    hour_utc = int(gkg_cfg.get("sample_hour_utc", 12))
    rate_limit = float(gkg_cfg.get("rate_limit_s", 0.25))

    end = date.today()
    start = end - timedelta(days=lookback_days)
    cache = _cache_dir(root)
    gkg_urls = fetch_masterfilelist(cache_dir=cache)
    urls = select_gkg_urls(
        gkg_urls,
        start=start,
        end=end,
        sample_days=sample_days,
        hour_utc=hour_utc,
    )

    articles: list[NewsArticle] = []
    for i, url in enumerate(urls):
        data = download_gkg_zip(url, sleep_s=rate_limit if i else 0.0)
        if not data:
            continue
        articles.extend(parse_gkg_zip_bytes(data, max_articles=max_per_file))

    jsonl_path = write_news_jsonl(root, articles)
    append_corpus_jsonl(root, articles)
    return jsonl_path, len(articles)
