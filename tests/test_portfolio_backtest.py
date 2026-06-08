import pandas as pd

from aitrader.ml.portfolio_backtest import (
    _position_from_signal,
    simulate_spy_portfolio,
)
from aitrader.ml.predict_config import PredictTuneConfig


def test_position_from_signal() -> None:
    cfg = PredictTuneConfig(min_news_confident=1)
    assert _position_from_signal(0.05, 2, min_news_confident=cfg.min_news_confident) == "long"
    assert _position_from_signal(-0.05, 2, min_news_confident=cfg.min_news_confident) == "cash"
    assert _position_from_signal(0.05, 0, min_news_confident=cfg.min_news_confident) == "cash"


def test_simulate_spy_portfolio() -> None:
    monthly = pd.DataFrame(
        {
            "trading_day": pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-28"]),
            "predicted_return": [0.02, 0.0, -0.01],
            "realized_return": [0.05, 0.03, -0.02],
            "news_articles": [3, 0, 2],
            "cluster_id": [7, -1, 7],
        }
    )
    ledger, summary = simulate_spy_portfolio(monthly, capital_usd=10_000)
    assert summary["final_value_usd"] == round(10_000 * 1.05, 2)
    assert summary["long_months"] == 1
    assert summary["cash_months"] == 2
    assert len(ledger) == 3
