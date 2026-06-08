from datetime import datetime, timezone

import pandas as pd

from aitrader.data.cot import cot_signal_at


def test_cot_signal_at_point_in_time() -> None:
    cot = pd.DataFrame(
        {
            "report_date": pd.to_datetime(["2024-01-02", "2024-01-09", "2024-01-16"]),
            "cot_signal": [0.1, 0.5, -0.2],
        }
    )
    assert cot_signal_at(cot, pd.Timestamp("2024-01-10")) == 0.5
    assert cot_signal_at(cot, pd.Timestamp("2024-01-01")) == 0.0
    assert cot_signal_at(cot, pd.Timestamp("2024-01-20")) == -0.2
