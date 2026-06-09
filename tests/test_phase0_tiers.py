import json
from pathlib import Path

from aitrader.nlp.keyword_tiers import (
    TIER_MARKET,
    infer_tier,
    tier_overlap_stats,
    tiered_phrases_for_article,
)
from aitrader.nlp.phase0_suite import PHASE0_FROZEN, run_keyword_audit
from aitrader.nlp.stoplist import is_stoplisted
from aitrader.workspace import ensure_run_layout


def test_infer_tier_macro() -> None:
    art = {"title": "Fed cuts rates", "body": "", "tickers": ["SPY"], "sector_id": "macro"}
    assert infer_tier("rate cut", art) == TIER_MARKET


def test_infer_tier_ticker_symbol() -> None:
    art = {"title": "Apple earnings", "body": "", "tickers": ["AAPL"], "sector_id": "technology"}
    assert infer_tier("AAPL", art) == "ticker"


def test_tiered_phrases_from_dict_cache() -> None:
    art = {
        "id": "a1",
        "title": "Fed holds rates steady",
        "body": "Inflation cools.",
        "tickers": ["SPY"],
        "sector_id": "macro",
    }
    cache = {
        "a1": {
            "keywords": [
                {"phrase": "rate cut", "type": "macro"},
                {"phrase": "earnings", "type": "sector"},
            ]
        }
    }
    pairs = tiered_phrases_for_article(art, cache)
    tiers = {p: t for p, t in pairs}
    assert tiers["rate cut"] == TIER_MARKET
    assert tiers["earnings"] == "sector"


def test_run_keyword_audit_no_junk(tmp_path: Path) -> None:
    root = ensure_run_layout(tmp_path)
    (root / "models").mkdir(exist_ok=True)
    rows = [
        {"keyword": "the fed", "ic": 0.8, "support": 5},
        {"keyword": "inflation", "ic": 0.5, "support": 6},
    ]
    (root / "models" / "keyword_map_market.json").write_text(json.dumps(rows))
    audit = run_keyword_audit(tmp_path)
    assert audit["top50_junk_count"] == 0
    assert not any(is_stoplisted(k) for k in [r["keyword"] for r in audit["top20"]])


def test_phase0_frozen_baseline_exists() -> None:
    assert PHASE0_FROZEN["keyword_score_ic"] == -0.062
    assert PHASE0_FROZEN["walkforward_ic"] > 0.1


def test_tier_overlap_stats_empty(tmp_path: Path) -> None:
    root = ensure_run_layout(tmp_path)
    stats = tier_overlap_stats(root)
    assert stats["market_keywords"] == 0
