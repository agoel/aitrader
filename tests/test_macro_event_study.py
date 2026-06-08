import json
from datetime import datetime, timedelta, timezone

import pandas as pd

from aitrader.ml.backtest import _macro_articles_by_trading_day, _macro_event_study
from aitrader.workspace import ensure_run_layout


def test_macro_articles_grouped_by_trading_day() -> None:
    spy_idx = pd.date_range("2023-01-03", periods=30, freq="B")
    arts = []
    for i in range(3):
        pub = (spy_idx[5 + i]).strftime("%Y-%m-%dT%H:%M:%SZ")
        arts.append({"id": f"a{i}", "published_at": pub, "sector_id": "macro"})
    by_day = _macro_articles_by_trading_day(arts, spy_idx, horizon_days=5)
    assert len(by_day) >= 1
    total = sum(len(v) for v in by_day.values())
    assert total == 3


def test_macro_event_study_one_row_per_day(tmp_path) -> None:
    root = ensure_run_layout(tmp_path)
    dates = pd.date_range("2023-01-03", periods=80, freq="B")
    prices = [100.0 + i * 0.1 for i in range(len(dates))]
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
    (root / "data" / "ohlcv").mkdir(parents=True, exist_ok=True)
    df.to_parquet(root / "data" / "ohlcv" / "SPY.parquet", index=False)
    (root / "models" / "keyword_map_anchor.json").write_text(
        json.dumps([{"keyword": "fed", "coef": 0.01, "ic": 0.1}])
    )
    lines = []
    for i in range(10):
        pub = dates[10 + i].strftime("%Y-%m-%dT10:00:00Z")
        lines.append(
            json.dumps(
                {
                    "id": f"m{i}",
                    "published_at": pub,
                    "title": "Fed holds rates steady",
                    "body": "Inflation cools.",
                    "source": "test",
                    "sector_id": "macro",
                }
            )
        )
    news = root / "data" / "news"
    news.mkdir(parents=True, exist_ok=True)
    (news / "corpus.jsonl").write_text("\n".join(lines) + "\n")
    from aitrader.nlp.cluster import fit_news_clusters

    fit_news_clusters(tmp_path, cluster_k=2)
    out = _macro_event_study(tmp_path, 5, llm_cache={}, quiet=True)
    assert not out.empty
    assert len(out) <= 10
    assert "macro_articles" in out.columns
