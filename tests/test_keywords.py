from aitrader.nlp.keywords import _pearson_ic, extract_keywords


def test_extract_keywords_macro_terms() -> None:
    kws = extract_keywords(
        "Fed signals rate cut amid cooling inflation",
        "Markets rallied on jobs data and treasury yields fell.",
    )
    assert "fed" in kws or "rate cut" in kws or "inflation" in kws


def test_pearson_ic_positive() -> None:
    x = [0.0, 0.0, 1.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0]
    y = [0.01, -0.01, 0.05, 0.04, 0.06, -0.02, 0.0, 0.03, 0.05, -0.01]
    ic = _pearson_ic(x, y)
    assert ic > 0.3


def test_discover_keywords_with_corpus(tmp_path) -> None:
    import json
    from pathlib import Path

    import pandas as pd

    from aitrader.nlp.keywords import discover_sector_keywords
    from aitrader.workspace import ensure_run_layout

    root = ensure_run_layout(tmp_path)
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "sectors.yaml").write_text(
        "sectors:\n  - id: technology\n    name: Technology\n    etf_proxy: XLK\n"
    )
    ohlcv = root / "data" / "ohlcv"
    ohlcv.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2024-01-02", periods=80, freq="B")

    def _write_bars(ticker: str, base: float) -> None:
        prices = [base + i * 0.1 for i in range(80)]
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
        df.to_parquet(ohlcv / f"{ticker}.parquet", index=False)

    _write_bars("XLK", 100)
    _write_bars("AAPL", 200)

    news_dir = root / "data" / "news"
    news_dir.mkdir(parents=True, exist_ok=True)
    articles = []
    for i, d in enumerate(dates[::7][:8]):
        articles.append(
            {
                "id": f"n{i}",
                "published_at": d.strftime("%Y-%m-%dT15:00:00Z"),
                "title": "Fed rate outlook shifts tech demand",
                "body": "Inflation and earnings drive semiconductor stocks.",
                "source": "test",
                "tags": ["macro"],
                "tickers": ["AAPL"],
                "sector_id": "technology",
            }
        )
    (news_dir / "corpus.jsonl").write_text("\n".join(json.dumps(a) for a in articles) + "\n")

    paths, report = discover_sector_keywords(tmp_path, min_keyword_ic=0.01, enrich_yahoo=False)
    assert len(paths) >= 1
    assert report.exists()
