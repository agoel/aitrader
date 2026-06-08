"""Optional OpenAI keyword extraction (comparison track). Primary path: cursor_extract.py."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aitrader.nlp.keyword_cache import (
    append_keyword_cache,
    load_keyword_cache,
    normalize_keywords,
)
from aitrader.nlp.news import load_corpus
from aitrader.workspace import ensure_run_layout

OPENAI_API_BASE = "https://api.openai.com/v1"
OPENAI_CHAT_URL = f"{OPENAI_API_BASE}/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"
PROMPT_VERSION = "macro_keywords_v1"

KEYWORD_SYSTEM = (
    "You extract finance-relevant keyword phrases from news headlines for macro equity trading. "
    "Return JSON only."
)

EXCLUDE_HINT = (
    "nyse, nasdaq, dow, while, more, move, week, story, recent, gets, taking, according, "
    "said, says, stock, stocks, market, investors, trading, price, shares"
)


def resolve_openai_api_key() -> str | None:
    return os.environ.get("OPENAI_API_KEY")


def resolve_openai_model(run_dir: Path | None = None, *, cli_model: str | None = None) -> str:
    if cli_model and cli_model.strip():
        return cli_model.strip()
    if run_dir is not None:
        meta_path = run_dir / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            model = meta.get("openai_model")
            if isinstance(model, str) and model.strip():
                return model.strip()
    env_model = os.environ.get("OPENAI_MODEL")
    if env_model and env_model.strip():
        return env_model.strip()
    return DEFAULT_MODEL


def _openai_chat_json(
    body: dict,
    *,
    api_key: str,
    timeout: int = 120,
) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        OPENAI_CHAT_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {detail}") from exc
    content = payload["choices"][0]["message"]["content"]
    return json.loads(content)


def _supports_temperature(model: str) -> bool:
    return not model.strip().lower().startswith("gpt-5")


def build_batch_prompt(articles: list[dict[str, Any]]) -> str:
    lines = [
        "For each article, extract 3-8 short phrases (1-4 words) that could move the "
        "stated sector or related equities.",
        "Prefer: Fed/rates/inflation, earnings/guidance, tariffs/regulation, sector themes, "
        "named companies/products when central to the story.",
        f"Exclude generic filler and boilerplate, including: {EXCLUDE_HINT}.",
        'Return JSON: {"articles": [{"id": str, "keywords": [{"phrase": str, "type": '
        '"macro|sector|company|policy"}]}]}',
        "",
    ]
    for art in articles:
        sector = art.get("sector_id") or "macro"
        tickers = ", ".join(art.get("tickers") or []) or "n/a"
        lines.append(f"--- id={art['id']} sector={sector} tickers={tickers}")
        lines.append(f"title: {art.get('title', '')}")
        lines.append(f"body: {(art.get('body') or '')[:800]}")
        lines.append("")
    return "\n".join(lines)


load_llm_keyword_cache = load_keyword_cache
append_llm_keyword_cache = append_keyword_cache


def extract_llm_keywords_batch(
    articles: list[dict[str, Any]],
    *,
    model: str,
    api_key: str,
) -> dict[str, list[str]]:
    if not articles:
        return {}
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": KEYWORD_SYSTEM},
            {"role": "user", "content": build_batch_prompt(articles)},
        ],
        "response_format": {"type": "json_object"},
    }
    if _supports_temperature(model):
        body["temperature"] = 0.1
    data = _openai_chat_json(body, api_key=api_key)
    results: dict[str, list[str]] = {}
    for entry in data.get("articles", []):
        art_id = str(entry.get("id", ""))
        src = next((a for a in articles if a["id"] == art_id), None)
        if not src:
            continue
        results[art_id] = normalize_keywords(
            entry.get("keywords", []),
            src.get("title", ""),
            src.get("body", ""),
        )
    return results


def extract_llm_keywords(
    run_dir: str | Path,
    *,
    batch_size: int = 8,
    limit: int | None = None,
    model: str | None = None,
    sleep_s: float = 0.5,
    force: bool = False,
) -> tuple[Path, int]:
    """Extract and cache LLM keywords for news corpus. Requires OPENAI_API_KEY."""
    root = ensure_run_layout(run_dir)
    api_key = resolve_openai_api_key()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Export your key to run LLM keyword extraction."
        )
    model = resolve_openai_model(root, cli_model=model)
    corpus = load_corpus(root)
    cache_path = root / "data" / "news" / "llm_keywords.jsonl"
    if force and cache_path.exists():
        cache_path.unlink()
    cache = {} if force else load_llm_keyword_cache(root)

    pending = [a for a in corpus if a["id"] not in cache]
    if limit is not None:
        pending = pending[:limit]

    written = 0
    today = datetime.now(timezone.utc).isoformat()
    for i in range(0, len(pending), batch_size):
        batch = pending[i : i + batch_size]
        try:
            mapped = extract_llm_keywords_batch(batch, model=model, api_key=api_key)
        except RuntimeError as exc:
            raise RuntimeError(f"LLM batch failed at offset {i}: {exc}") from exc
        rows: list[dict[str, Any]] = []
        for art in batch:
            kws = mapped.get(art["id"], [])
            rows.append(
                {
                    "id": art["id"],
                    "keywords": kws,
                    "model": model,
                    "prompt_version": PROMPT_VERSION,
                    "extracted_at": today,
                }
            )
        append_llm_keyword_cache(root, rows)
        written += len(rows)
        if sleep_s:
            time.sleep(sleep_s)

    return root / "data" / "news" / "llm_keywords.jsonl", written
