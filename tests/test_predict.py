import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from aitrader.ml.predict import run_predictions, train_horizon_models
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


def test_run_predictions(tmp_path: Path) -> None:
    root = ensure_run_layout(tmp_path)
    (root / "config" / "sectors.yaml").write_text(
        "sectors:\n  - id: technology\n    name: Technology\n    etf_proxy: XLK\n"
    )
    (root / "data" / "universe.csv").write_text(
        "sector_id,sector_name,ticker,name,etf_proxy,is_anchor,weight_proxy\n"
        "anchor,Anchor,SPY,SPY,SPY,true,1.0\n"
        "anchor,Anchor,IWM,IWM,IWM,true,1.0\n"
        "technology,Technology,AAPL,AAPL,XLK,false,\n"
    )
    ohlcv = root / "data" / "ohlcv"
    ohlcv.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2024-01-02", periods=120, freq="B")
    for t in ("SPY", "IWM", "XLK", "AAPL"):
        _write_ohlcv(ohlcv / f"{t}.parquet", dates)

    now = datetime.now(timezone.utc)
    lines = []
    for i in range(30):
        pub = (now - timedelta(days=i % 6)).strftime("%Y-%m-%dT10:00:00Z")
        lines.append(
            json.dumps(
                {
                    "id": f"n{i}",
                    "published_at": pub,
                    "title": "Fed rate cut lifts earnings outlook",
                    "body": "Inflation cools; technology stocks rally on guidance.",
                    "source": "test",
                    "tags": [],
                    "tickers": ["AAPL"],
                    "sector_id": "technology",
                }
            )
        )
    (root / "data" / "news").mkdir(parents=True, exist_ok=True)
    (root / "data" / "news" / "corpus.jsonl").write_text("\n".join(lines) + "\n")
    (root / "data" / "news" / "llm_keywords.jsonl").write_text(
        json.dumps({"id": "n0", "keywords": ["rate cut", "earnings"]}) + "\n"
    )
    (root / "models" / "keyword_map_technology.json").write_text(
        json.dumps(
            [
                {"keyword": "rate cut", "coef": 0.02, "ic": 0.1, "direction": "bullish"},
                {"keyword": "earnings", "coef": 0.01, "ic": 0.08, "direction": "bullish"},
            ]
        )
    )
    (root / "models" / "keyword_map_anchor.json").write_text(
        json.dumps([{"keyword": "rate cut", "coef": 0.015, "ic": 0.09, "direction": "bullish"}])
    )
    (root / "models" / "current_cluster.json").write_text(
        json.dumps(
            {
                "dominant_cluster_id": 1,
                "sector_return_profile": {"technology": 0.02, "anchor": 0.01},
            }
        )
    )

    train_horizon_models(tmp_path, horizons=("2w", "1m"))
    path = run_predictions(tmp_path, horizons=("2w", "1m"), retrain=False)
    assert path.exists()
    df = pd.read_csv(path)
    assert not df.duplicated(subset=["ticker", "horizon"]).any()
    for ticker in ("SPY", "IWM"):
        sub = df[df["ticker"] == ticker]
        assert len(sub) == 2
        for _, row in sub.iterrows():
            assert row["confidence_lower"] < row["expected_return"] < row["confidence_upper"]
            assert "confidence_score" in row.index or "confidence_score" in df.columns
