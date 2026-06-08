import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from aitrader.nlp.cluster import fit_news_clusters
from aitrader.workspace import ensure_run_layout


def test_fit_news_clusters(tmp_path: Path) -> None:
    root = ensure_run_layout(tmp_path)
    (root / "config" / "sectors.yaml").write_text(
        "sectors:\n  - id: technology\n    name: Technology\n    etf_proxy: XLK\n"
    )
    ohlcv = root / "data" / "ohlcv"
    ohlcv.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2024-01-02", periods=60, freq="B")
    prices = [100 + i * 0.05 for i in range(60)]
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
    df.to_parquet(ohlcv / "XLK.parquet", index=False)

    now = datetime.now(timezone.utc)
    lines = []
    for i in range(20):
        pub = (now - timedelta(days=i % 5)).strftime("%Y-%m-%dT10:00:00Z")
        lines.append(
            json.dumps(
                {
                    "id": f"n{i}",
                    "published_at": pub,
                    "title": f"Fed inflation outlook week {i}",
                    "body": "Rates and earnings drive technology stocks higher.",
                    "source": "test",
                    "tags": [],
                    "tickers": ["AAPL"],
                    "sector_id": "technology",
                }
            )
        )
    (root / "data" / "news").mkdir(parents=True, exist_ok=True)
    (root / "data" / "news" / "corpus.jsonl").write_text("\n".join(lines) + "\n")

    model, current, report = fit_news_clusters(tmp_path, cluster_k=3)
    assert model.exists()
    assert current.exists()
    assert report.exists()
    doc = json.loads(current.read_text())
    assert "dominant_cluster_id" in doc
