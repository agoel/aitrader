from datetime import datetime
from unittest.mock import patch

import pandas as pd

from aitrader.data.yahoo import _normalize_frame, fetch_ohlcv, ingest_ticker


def test_normalize_frame() -> None:
    raw = pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [1_000_000, 1_100_000],
            "Adj Close": [100.5, 101.5],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )
    out = _normalize_frame(raw)
    assert list(out.columns) == [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "adj_close",
    ]
    assert len(out) == 2


@patch("aitrader.data.yahoo.yf.download")
def test_fetch_ohlcv(mock_download) -> None:
    mock_download.return_value = pd.DataFrame(
        {
            "Open": [400.0],
            "High": [401.0],
            "Low": [399.0],
            "Close": [400.5],
            "Volume": [50_000_000],
            "Adj Close": [400.5],
        },
        index=pd.to_datetime([datetime(2024, 6, 1)]),
    )
    df = fetch_ohlcv("SPY", years=1)
    assert len(df) == 1
    assert df.loc[0, "close"] == 400.5


@patch("aitrader.data.yahoo.fetch_ohlcv")
def test_ingest_ticker(mock_fetch, tmp_path) -> None:
    mock_fetch.return_value = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "open": [1.0, 2.0],
            "high": [1.0, 2.0],
            "low": [1.0, 2.0],
            "close": [1.0, 2.0],
            "volume": [100, 100],
            "adj_close": [1.0, 2.0],
        }
    )
    result = ingest_ticker("SPY", tmp_path, sleep_s=0)
    assert result["status"] == "ok"
    assert result["rows"] == 2
    assert (tmp_path / "SPY.parquet").exists()
