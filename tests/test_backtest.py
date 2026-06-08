import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from aitrader.ml.backtest import run_prediction_backtest
from aitrader.workspace import ensure_run_layout


def _write_ohlcv(path: Path, dates: pd.DatetimeIndex, start: float = 100.0) -> None:
    prices = [start + i * 0.08 for i in range(len(dates))]
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


def test_prediction_backtest(tmp_path: Path) -> None:
    root = ensure_run_layout(tmp_path)
    (root / "config" / "sectors.yaml").write_text(
        "sectors:\n  - id: technology\n    name: Technology\n    etf_proxy: XLK\n"
    )
    (root / "data" / "universe.csv").write_text(
        "sector_id,sector_name,ticker,name,etf_proxy,is_anchor\n"
        "anchor,Anchor,SPY,SPY,SPY,true\n"
        "technology,Technology,AAPL,AAPL,XLK,false\n"
    )
    ohlcv = root / "data" / "ohlcv"
    dates = pd.date_range("2023-01-03", periods=500, freq="B")
    for t in ("SPY", "XLK", "AAPL"):
        _write_ohlcv(ohlcv / f"{t}.parquet", dates)

    now = datetime.now(timezone.utc)
    lines = []
    for i in range(40):
        pub = (now - timedelta(days=i * 3)).strftime("%Y-%m-%dT10:00:00Z")
        lines.append(
            json.dumps(
                {
                    "id": f"n{i}",
                    "published_at": pub,
                    "title": "Fed signals rate cut amid inflation data",
                    "body": "Earnings outlook improves for technology sector.",
                    "source": "test",
                    "tags": [],
                    "tickers": ["AAPL"],
                    "sector_id": "technology",
                }
            )
        )
    news_dir = root / "data" / "news"
    news_dir.mkdir(parents=True, exist_ok=True)
    (news_dir / "corpus.jsonl").write_text("\n".join(lines) + "\n")
    (root / "data" / "news" / "llm_keywords.jsonl").write_text(
        "\n".join(
            json.dumps({"id": f"n{i}", "keywords": ["rate cut", "earnings", "inflation"]})
            for i in range(40)
        )
        + "\n"
    )
    (root / "models" / "keyword_map_technology.json").write_text(
        json.dumps(
            [
                {"keyword": "rate cut", "coef": 0.02, "ic": 0.1},
                {"keyword": "earnings", "coef": 0.01, "ic": 0.08},
                {"keyword": "inflation", "coef": -0.01, "ic": -0.05},
            ]
        )
    )
    (root / "models" / "keyword_map_anchor.json").write_text(
        json.dumps([{"keyword": "rate cut", "coef": 0.015, "ic": 0.09}])
    )

    from aitrader.nlp.cluster import fit_news_clusters

    fit_news_clusters(tmp_path, cluster_k=3)

    csv_path, report = run_prediction_backtest(
        tmp_path,
        horizons=("1m",),
        min_train_days=2,
        include_monthly_spy=True,
    )
    assert csv_path.exists()
    assert report.exists()
    summary = report.read_text()
    assert "Prediction backtest" in summary
    bt = pd.read_csv(csv_path)
    assert len(bt) >= 1
    assert "predicted_return" in bt.columns
    assert "realized_return" in bt.columns
