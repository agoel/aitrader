import pandas as pd

from aitrader.ml.option_range_study import (
    map_to_trading_day,
    monthly_option_cycles,
    third_friday,
)


def test_third_friday_jan_2024() -> None:
    assert third_friday(2024, 1) == pd.Timestamp("2024-01-19")


def test_monthly_option_cycles() -> None:
    idx = pd.bdate_range("2023-01-01", periods=400)
    cycles = monthly_option_cycles(idx, start=idx[20], end=idx[-20])
    assert len(cycles) >= 10
    signal, expiry, label = cycles[0]
    assert signal < expiry
    assert "-" in label


def test_map_to_trading_day() -> None:
    idx = pd.bdate_range("2024-01-01", periods=30)
    # Saturday maps to prior Friday
    sat = pd.Timestamp("2024-01-06")
    assert map_to_trading_day(idx, sat) == pd.Timestamp("2024-01-05")
