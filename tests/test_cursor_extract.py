import json
from pathlib import Path

from aitrader.nlp.cursor_extract import (
    apply_cursor_batch,
    fill_cursor_batches,
    prepare_cursor_batches,
    suggest_macro_keywords,
)
from aitrader.nlp.keyword_cache import load_keyword_cache
from aitrader.workspace import ensure_run_layout


def test_prepare_and_apply_cursor_batch(tmp_path: Path) -> None:
    root = ensure_run_layout(tmp_path)
    (root / "data" / "news").mkdir(parents=True, exist_ok=True)
    articles = [
        {
            "id": "a1",
            "published_at": "2026-06-01T10:00:00Z",
            "title": "Fed signals rate cut",
            "body": "Markets rally on rate cut hopes for technology sector.",
            "source": "test",
            "tags": [],
            "tickers": ["AAPL"],
            "sector_id": "technology",
        }
    ]
    (root / "data" / "news" / "corpus.jsonl").write_text(
        json.dumps(articles[0]) + "\n"
    )
    batches_dir, count = prepare_cursor_batches(tmp_path, batch_size=8)
    assert count == 1
    assert (batches_dir / "batch_001.md").exists()

    out = {
        "batch_index": 1,
        "articles": [
            {
                "id": "a1",
                "keywords": [{"phrase": "rate cut", "type": "macro"}],
            }
        ],
    }
    (batches_dir / "batch_001_out.json").write_text(json.dumps(out))
    n, cache_path = apply_cursor_batch(tmp_path, 1)
    assert n == 1
    cache = load_keyword_cache(tmp_path)
    assert cache["a1"]["keywords"] == ["rate cut"]


def test_suggest_macro_keywords_grounded() -> None:
    art = {
        "id": "x",
        "title": "Fed signals rate cut amid inflation worries",
        "body": "Treasury yields fall as investors price in easing.",
        "tickers": ["SPY"],
        "sector_id": "macro",
    }
    kws = suggest_macro_keywords(art)
    phrases = [k["phrase"] for k in kws]
    assert "rate cut" in phrases or "inflation" in phrases
    assert "nyse" not in phrases
    assert "what the" not in phrases


def test_suggest_macro_keywords_no_title_bigram_fallback() -> None:
    """Phase 1: no arbitrary title bigrams when macro patterns are sparse."""
    art = {
        "id": "y",
        "title": "Company reports quarterly results",
        "body": "Shares moved on guidance.",
        "tickers": [],
        "sector_id": "macro",
    }
    kws = suggest_macro_keywords(art)
    phrases = [k["phrase"] for k in kws]
    assert "company reports" not in phrases
    assert "reports quarterly" not in phrases


def test_fill_cursor_batches(tmp_path: Path) -> None:
    root = ensure_run_layout(tmp_path)
    (root / "data" / "news").mkdir(parents=True, exist_ok=True)
    art = {
        "id": "a1",
        "published_at": "2026-06-01T10:00:00Z",
        "title": "Oil prices rise on supply cuts",
        "body": "Energy sector gains as crude rallies.",
        "source": "test",
        "tags": [],
        "tickers": ["XOM"],
        "sector_id": "energy",
    }
    (root / "data" / "news" / "corpus.jsonl").write_text(json.dumps(art) + "\n")
    prepare_cursor_batches(tmp_path, batch_size=8)
    filled, articles = fill_cursor_batches(tmp_path)
    assert filled == 1
    assert articles == 1
    assert (root / "data" / "news" / "cursor_batches" / "batch_001_out.json").exists()
