"""Shared keyword cache and validation for Cursor and optional API tracks."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

EXCLUDE_HINT = (
    "nyse, nasdaq, dow, while, more, move, week, story, recent, gets, taking, according, "
    "said, says, stock, stocks, market, investors, trading, price, shares"
)


def phrase_grounded(phrase: str, title: str, body: str) -> bool:
    hay = f"{title} {body}".lower()
    p = phrase.lower().strip()
    if not p or len(p) < 3:
        return False
    if p in hay:
        return True
    words = [w for w in re.split(r"\s+", p) if len(w) > 2]
    return len(words) >= 2 and all(w in hay for w in words)


def normalize_keywords(
    raw: list[Any],
    title: str,
    body: str,
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            phrase = item.strip()
        elif isinstance(item, dict):
            phrase = str(item.get("phrase", "")).strip()
        else:
            continue
        if not phrase or phrase.lower() in seen:
            continue
        if not phrase_grounded(phrase, title, body):
            continue
        seen.add(phrase.lower())
        out.append(phrase)
    return out


def load_keyword_cache(run_dir: Path) -> dict[str, dict[str, Any]]:
    path = run_dir / "data" / "news" / "llm_keywords.jsonl"
    cache: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return cache
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            cache[row["id"]] = row
    return cache


def append_keyword_cache(run_dir: Path, rows: list[dict[str, Any]]) -> Path:
    path = run_dir / "data" / "news" / "llm_keywords.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def keywords_for_article(
    article: dict[str, Any],
    cache: dict[str, dict[str, Any]] | None,
) -> list[str]:
    title = article.get("title", "")
    body = article.get("body", "")
    if cache and article["id"] in cache:
        raw = cache[article["id"]].get("keywords") or []
        return normalize_keywords(raw, title, body)
    if article.get("llm_keywords"):
        return normalize_keywords(list(article["llm_keywords"]), title, body)
    return []
