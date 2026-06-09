"""Training frame optimizations — cached OHLCV, corpus cap, parallel sectors."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from aitrader.ml.predict import (
    DEFAULT_TRAIN_MAX_ARTICLES,
    _build_training_frame,
    train_horizon_models,
)
from aitrader.nlp.keywords import sample_corpus_for_training
from aitrader.workspace import ensure_run_layout


def _write_ohlcv(path: Path, dates: pd.DatetimeIndex, start: float = 100.0) -> None:
    prices = [start + i * 0.1 for i in range(len(dates))]
    df = pd.DataFrame(
        {
            "date": dates,
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "volume": 1e6,
            "adj_close": prices,
        }
    )
    df.to_parquet(path, index=False)


def _seed_run(tmp_path: Path, n_articles: int) -> Path:
    root = ensure_run_layout(tmp_path)
    (root / "config" / "sectors.yaml").write_text(
        "sectors:\n"
        "  - id: technology\n    name: Technology\n    etf_proxy: XLK\n"
        "  - id: financials\n    name: Financials\n    etf_proxy: XLF\n"
    )
    (root / "data" / "universe.csv").write_text(
        "sector_id,sector_name,ticker,name,etf_proxy,is_anchor,weight_proxy\n"
        "anchor,Anchor,SPY,SPY,SPY,true,1.0\n"
        "technology,Technology,AAPL,AAPL,XLK,false,\n"
        "financials,Financials,JPM,JPM,XLF,false,\n"
    )
    ohlcv = root / "data" / "ohlcv"
    ohlcv.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2024-01-02", periods=120, freq="B")
    for t in ("SPY", "XLK", "XLF", "AAPL", "JPM"):
        _write_ohlcv(ohlcv / f"{t}.parquet", dates)

    now = datetime.now(timezone.utc)
    lines = []
    for i in range(n_articles):
        pub = (now - timedelta(days=i % 40)).strftime("%Y-%m-%dT10:00:00Z")
        lines.append(
            json.dumps(
                {
                    "id": f"n{i}",
                    "published_at": pub,
                    "title": "Fed rate cut lifts earnings outlook",
                    "body": "Inflation cools; stocks rally.",
                    "source": "test",
                    "tags": [],
                    "tickers": ["AAPL"],
                    "sector_id": "macro" if i % 2 == 0 else "technology",
                }
            )
        )
    news_dir = root / "data" / "news"
    news_dir.mkdir(parents=True, exist_ok=True)
    (news_dir / "corpus.jsonl").write_text("\n".join(lines) + "\n")
    kw_lines = [
        json.dumps({"id": f"n{i}", "keywords": ["rate cut", "earnings"]})
        for i in range(min(n_articles, 50))
    ]
    (news_dir / "llm_keywords.jsonl").write_text("\n".join(kw_lines) + "\n")
    for sector in ("technology", "financials", "anchor"):
        (root / "models" / f"keyword_map_{sector}.json").write_text(
            json.dumps([{"keyword": "rate cut", "coef": 0.02, "ic": 0.1, "direction": "bullish"}])
        )
    return root


def test_sample_corpus_for_training_zero_keeps_all() -> None:
    corpus = [{"id": "a", "published_at": "2026-01-01"}] * 10
    assert len(sample_corpus_for_training(corpus, max_articles=0)) == 10


def test_build_training_frame_respects_max_articles(tmp_path: Path) -> None:
    root = _seed_run(tmp_path, n_articles=200)
    from aitrader.nlp.keyword_cache import load_keyword_cache

    full = _build_training_frame(
        root,
        21,
        llm_cache=load_keyword_cache(root),
        quiet=True,
        max_train_articles=0,
        workers=1,
    )
    capped = _build_training_frame(
        root,
        21,
        llm_cache=load_keyword_cache(root),
        quiet=True,
        max_train_articles=50,
        workers=1,
    )
    assert len(capped) < len(full)


def test_train_horizon_models_parallel_workers(tmp_path: Path) -> None:
    root = _seed_run(tmp_path, n_articles=80)
    models = train_horizon_models(
        root,
        horizons=("2w",),
        max_train_articles=DEFAULT_TRAIN_MAX_ARTICLES,
        workers=2,
    )
    assert "2w" in models
    assert models["2w"].train_rows >= 20
