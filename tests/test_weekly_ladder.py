import pandas as pd

from aitrader.ml.portfolio_backtest import simulate_weekly_ladder
from aitrader.workspace import ensure_run_layout


def _write_spy_parquet(root, prices: list[float], start: str = "2020-01-02") -> None:
    dates = pd.bdate_range(start, periods=len(prices))
    df = pd.DataFrame({"date": dates, "close": prices})
    path = root / "data" / "ohlcv"
    path.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path / "SPY.parquet", index=False)


def test_weekly_ladder_always_invests(tmp_path) -> None:
    root = ensure_run_layout(tmp_path)
    # Steady 1% monthly-ish drift over enough days for several tranches
    prices = [100.0 * (1.001 ** i) for i in range(200)]
    _write_spy_parquet(root, prices)
    ledger, summary = simulate_weekly_ladder(
        root,
        capital_usd=10_000,
        tranche_pct=0.25,
        start="2020-03-01",
        end="2020-09-01",
        always_invest=True,
        horizon_days=21,
    )
    assert summary["tranches_opened"] >= 3
    assert summary["final_value_usd"] > 10_000
    assert not ledger.empty
