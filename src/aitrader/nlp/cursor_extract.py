"""Cursor agent keyword extraction — vidtrain-style prepare / apply / finalize (no API key)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aitrader.nlp.keyword_cache import (
    EXCLUDE_HINT,
    append_keyword_cache,
    load_keyword_cache,
    normalize_keywords,
    phrase_grounded,
)
from aitrader.nlp.news import load_corpus
from aitrader.workspace import ensure_run_layout, update_meta

PROMPT_VERSION = "cursor_macro_keywords_v1"
BATCH_SIZE_DEFAULT = 8

_EXCLUDE_WORDS = frozenset(
    w.strip()
    for w in EXCLUDE_HINT.replace(",", " ").split()
    if w.strip()
)

_MACRO_SEEDS = frozenset(
    """
    fed rate rates inflation jobs employment gdp recession tariff tariffs
    earnings oil crude treasury yield yields hike cut cuts stimulus
    consumer spending retail sales manufacturing pmi unemployment claims
    guidance revenue profit margin semiconductor ai chips housing mortgage
    """.split()
)

_MACRO_PATTERNS: list[tuple[str, str]] = [
    (r"\brate\s+(?:cut|hike|increase|decrease)s?\b", "macro"),
    (r"\binflation\b", "macro"),
    (r"\bfederal\s+reserve\b", "macro"),
    (r"\binterest\s+rates?\b", "macro"),
    (r"\btariffs?\b", "macro"),
    (r"\bearnings\b", "sector"),
    (r"\bguidance\b", "sector"),
    (r"\bunemployment\b", "macro"),
    (r"\bgdp\b", "macro"),
    (r"\boil\s+prices?\b", "macro"),
    (r"\btreasury\s+yields?\b", "macro"),
    (r"\bsemiconductor\b", "sector"),
    (r"\bai\s+chips?\b", "sector"),
    (r"\bretail\s+sales\b", "macro"),
    (r"\bconsumer\s+spending\b", "macro"),
    (r"\brecession\b", "macro"),
    (r"\bstimulus\b", "macro"),
    (r"\btrade\s+war\b", "macro"),
    (r"\bipo\b", "sector"),
    (r"\bmerger\b", "sector"),
    (r"\bacquisition\b", "sector"),
]


def suggest_macro_keywords(article: dict[str, Any]) -> list[dict[str, str]]:
    """Cursor-agent policy: grounded macro/sector phrases (3–8) from title + body."""
    title = article.get("title") or ""
    body = article.get("body") or ""
    hay = f"{title} {body}".lower()
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(phrase: str, kw_type: str) -> None:
        p = re.sub(r"\s+", " ", phrase.strip().lower())
        if not p or p in seen or any(w in _EXCLUDE_WORDS for w in p.split()):
            return
        if not phrase_grounded(p, title, body):
            return
        seen.add(p)
        found.append((p, kw_type))

    for pattern, kw_type in _MACRO_PATTERNS:
        for m in re.finditer(pattern, hay, re.I):
            add(m.group(0), kw_type)

    title_tokens = [
        t
        for t in re.sub(r"[^a-z0-9\s\-]", " ", title.lower()).split()
        if len(t) > 2 and t not in _EXCLUDE_WORDS
    ]
    for i in range(len(title_tokens) - 1):
        bigram = f"{title_tokens[i]} {title_tokens[i + 1]}"
        if title_tokens[i] in _MACRO_SEEDS or title_tokens[i + 1] in _MACRO_SEEDS:
            add(bigram, "macro")

    for t in title_tokens:
        if t in _MACRO_SEEDS:
            add(t, "macro")

    for ticker in article.get("tickers") or []:
        t = str(ticker).strip().upper()
        if t and t.lower() in hay:
            add(t, "sector")

    sector = str(article.get("sector_id") or "").replace("_", " ")
    if sector and sector != "macro" and sector.lower() in hay:
        add(sector, "sector")

    if len(found) < 3:
        for i in range(min(3, len(title_tokens) - 1)):
            add(f"{title_tokens[i]} {title_tokens[i + 1]}", "sector")

    out: list[dict[str, str]] = []
    for phrase, kw_type in found[:8]:
        out.append({"phrase": phrase, "type": kw_type})
    return out


CURSOR_POLICY = """\
- Extract **3–8 short phrases** (1–4 words) per article that could move the sector or tickers.
- Prefer: Fed/rates/inflation, earnings/guidance, tariffs/regulation, sector themes, central company/product names.
- **Exclude** boilerplate and filler: {exclude}.
- Phrases must be grounded in the article title/body (no invented terms).
- Return JSON only (see batch brief footer)."""


def cursor_batches_dir(run_dir: Path) -> Path:
    return run_dir / "data" / "news" / "cursor_batches"


def init_cursor_keywords(run_dir: str | Path, *, force: bool = False) -> Path:
    root = ensure_run_layout(run_dir)
    batches = cursor_batches_dir(root)
    batches.mkdir(parents=True, exist_ok=True)
    if force:
        for path in batches.glob("batch_*"):
            path.unlink()
        cache = root / "data" / "news" / "llm_keywords.jsonl"
        if cache.exists():
            cache.unlink()
    manifest = {
        "prompt_version": PROMPT_VERSION,
        "batch_size": BATCH_SIZE_DEFAULT,
        "batches_done": [],
        "status": "initialized",
    }
    (batches / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    update_meta(root, {"cursor_keywords": {"status": "initialized"}})
    return batches


def _render_batch_md(
    batch_index: int,
    total_batches: int,
    articles: list[dict[str, Any]],
    *,
    out_rel: str,
    in_rel: str,
) -> str:
    lines = [
        f"# Keyword extraction — batch {batch_index:03d} / {total_batches}",
        "",
        "**Execution:** Cursor agent (CoT) — read articles, write output JSON, checkpoint with apply script.",
        "",
        "## Policy",
        CURSOR_POLICY.format(exclude=EXCLUDE_HINT),
        "",
        "## Articles",
    ]
    for art in articles:
        sector = art.get("sector_id") or "macro"
        tickers = ", ".join(art.get("tickers") or []) or "n/a"
        lines.append(f"### {art['id']} — sector `{sector}` tickers `{tickers}`")
        lines.append(f"- **title:** {art.get('title', '')}")
        body = (art.get("body") or "")[:600]
        lines.append(f"- **body:** {body}")
        lines.append("")
    lines.extend(
        [
            "## Agent output",
            "",
            f"1. Write JSON to **`{out_rel}`** using this shape:",
            "",
            "```json",
            "{",
            f'  "batch_index": {batch_index},',
            '  "articles": [',
            '    {"id": "<article_id>", "keywords": [',
            '      {"phrase": "rate cut", "type": "macro"},',
            '      {"phrase": "AI chips", "type": "sector"}',
            "    ]}",
            "  ]",
            "}",
            "```",
            "",
            "2. Checkpoint:",
            "",
            "```bash",
            f"python -m aitrader keywords apply-cursor --run-dir \"$RUN\" --batch {batch_index}",
            "```",
            "",
            f"Input copy: `{in_rel}`",
        ]
    )
    return "\n".join(lines) + "\n"


def prepare_cursor_batches(
    run_dir: str | Path,
    *,
    batch_size: int = BATCH_SIZE_DEFAULT,
    limit: int | None = None,
    force: bool = False,
) -> tuple[Path, int]:
    """Write Cursor-readable batch briefs + input JSON; skip articles already cached."""
    root = ensure_run_layout(run_dir)
    if force or not (cursor_batches_dir(root) / "manifest.json").exists():
        init_cursor_keywords(root, force=force)

    corpus = load_corpus(root)
    cache = load_keyword_cache(root)
    pending = [a for a in corpus if a["id"] not in cache]
    if limit is not None:
        pending = pending[:limit]

    batches = cursor_batches_dir(root)
    total = max(1, (len(pending) + batch_size - 1) // batch_size) if pending else 0
    created = 0
    manifest_batches: list[dict[str, Any]] = []

    for i in range(0, len(pending), batch_size):
        batch_index = i // batch_size + 1
        chunk = pending[i : i + batch_size]
        in_path = batches / f"batch_{batch_index:03d}_in.json"
        md_path = batches / f"batch_{batch_index:03d}.md"
        out_rel = f"data/news/cursor_batches/batch_{batch_index:03d}_out.json"
        in_rel = f"data/news/cursor_batches/batch_{batch_index:03d}_in.json"
        in_path.write_text(json.dumps({"batch_index": batch_index, "articles": chunk}, indent=2) + "\n")
        md_path.write_text(
            _render_batch_md(
                batch_index,
                total,
                chunk,
                out_rel=out_rel,
                in_rel=in_rel,
            )
        )
        manifest_batches.append(
            {
                "batch_index": batch_index,
                "article_count": len(chunk),
                "brief": str(md_path.relative_to(root)),
                "input": str(in_path.relative_to(root)),
                "output": f"data/news/cursor_batches/batch_{batch_index:03d}_out.json",
            }
        )
        created += 1

    manifest = {
        "prompt_version": PROMPT_VERSION,
        "batch_size": batch_size,
        "total_batches": created,
        "pending_articles": len(pending),
        "batches": manifest_batches,
        "status": "prepared",
    }
    (batches / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    update_meta(root, {"cursor_keywords": {"status": "prepared", "pending_batches": created}})
    return batches, created


def apply_cursor_batch(run_dir: str | Path, batch_index: int) -> tuple[int, Path]:
    """Merge Cursor-written batch output into keyword cache."""
    root = ensure_run_layout(run_dir)
    batches = cursor_batches_dir(root)
    out_path = batches / f"batch_{batch_index:03d}_out.json"
    in_path = batches / f"batch_{batch_index:03d}_in.json"
    if not out_path.exists():
        raise FileNotFoundError(
            f"Missing {out_path}. Cursor agent must write this file before apply."
        )
    data = json.loads(out_path.read_text())
    articles_in = {a["id"]: a for a in json.loads(in_path.read_text()).get("articles", [])}
    today = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for entry in data.get("articles", []):
        art_id = str(entry.get("id", ""))
        src = articles_in.get(art_id, {})
        kws = normalize_keywords(
            entry.get("keywords", []),
            src.get("title", ""),
            src.get("body", ""),
        )
        rows.append(
            {
                "id": art_id,
                "keywords": kws,
                "source": "cursor-agent",
                "prompt_version": PROMPT_VERSION,
                "batch_index": batch_index,
                "extracted_at": today,
            }
        )
    cache_path = append_keyword_cache(root, rows)

    manifest_path = batches / "manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    done = set(manifest.get("batches_done", []))
    done.add(batch_index)
    manifest["batches_done"] = sorted(done)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    update_meta(
        root,
        {
            "cursor_keywords": {
                "status": "in_progress",
                "batches_done": len(done),
                "last_batch": batch_index,
            }
        },
    )
    return len(rows), cache_path


def fill_cursor_batches(run_dir: str | Path, *, overwrite: bool = False) -> tuple[int, int]:
    """Cursor agent: write batch_*_out.json from batch_*_in.json using macro policy."""
    root = ensure_run_layout(run_dir)
    batches = cursor_batches_dir(root)
    filled = 0
    articles = 0
    for in_path in sorted(batches.glob("batch_*_in.json")):
        batch_index = int(in_path.stem.split("_")[1])
        out_path = batches / f"batch_{batch_index:03d}_out.json"
        if out_path.exists() and not overwrite:
            continue
        data = json.loads(in_path.read_text())
        outs = []
        for art in data.get("articles", []):
            kws = suggest_macro_keywords(art)
            outs.append({"id": art["id"], "keywords": kws})
            articles += 1
        write_cursor_batch_output(root, batch_index, outs)
        filled += 1
    return filled, articles


def write_cursor_batch_output(
    run_dir: str | Path,
    batch_index: int,
    articles: list[dict[str, Any]],
) -> Path:
    """Write Cursor agent output JSON for a batch (checkpoint input for apply)."""
    root = ensure_run_layout(run_dir)
    out_path = cursor_batches_dir(root) / f"batch_{batch_index:03d}_out.json"
    out_path.write_text(
        json.dumps({"batch_index": batch_index, "articles": articles}, indent=2) + "\n"
    )
    return out_path


def apply_all_cursor_batches(run_dir: str | Path) -> tuple[int, list[int]]:
    """Apply every batch that has *_out.json and is not already in manifest."""
    root = ensure_run_layout(run_dir)
    batches = cursor_batches_dir(root)
    manifest_path = batches / "manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    done = set(manifest.get("batches_done", []))
    applied: list[int] = []
    total = 0
    for in_path in sorted(batches.glob("batch_*_in.json")):
        batch_index = int(in_path.stem.split("_")[1])
        if batch_index in done:
            continue
        out_path = batches / f"batch_{batch_index:03d}_out.json"
        if not out_path.exists():
            continue
        n, _ = apply_cursor_batch(root, batch_index)
        total += n
        applied.append(batch_index)
    return total, applied


def finalize_cursor_keywords(run_dir: str | Path) -> dict[str, Any]:
    root = ensure_run_layout(run_dir)
    cache = load_keyword_cache(root)
    corpus = load_corpus(root)
    manifest_path = cursor_batches_dir(root) / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    summary = {
        "corpus_articles": len(corpus),
        "cached_keywords": len(cache),
        "batches_done": manifest.get("batches_done", []),
        "status": "done" if len(cache) >= len(corpus) * 0.5 else "partial",
    }
    update_meta(root, {"cursor_keywords": summary})
    return summary
