"""CSP put-spread advisor — delta OTM, safety gate, macro filter."""

from __future__ import annotations

import numpy as np
import pandas as pd

from aitrader.ml.csp_spread_advisor import (
    CSPSpreadParams,
    csp_action_gate,
    csp_safety_score,
    effective_breach_buffer,
    empirical_otm_pct,
    scale_return_for_dte,
)
from aitrader.nlp.sentiment import filter_macro_articles, filter_index_articles


def test_empirical_otm_pct_in_range() -> None:
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    closes = pd.Series(100 + np.cumsum(np.random.default_rng(1).normal(0, 0.2, len(idx))), index=idx)
    otm = empirical_otm_pct(closes, target_delta=0.085)
    assert 0.075 <= otm <= 0.14


def test_scale_return_for_dte() -> None:
    assert scale_return_for_dte(0.04, 21) == 0.04
    assert scale_return_for_dte(0.04, 29) > 0.04


def test_csp_safety_score_high_when_floor_above_strike() -> None:
    score, _ = csp_safety_score(
        spot=100.0,
        short_strike=91.0,
        model_floor=93.0,
        otm_pct=0.09,
        lower_return=-0.07,
        macro_sentiment=0.1,
        index_sentiment=0.05,
        momentum=0.02,
        cot_signal=0.5,
        event_penalty=0.0,
        predicted_return=0.01,
    )
    assert score > 25.0


def test_effective_breach_buffer_boosts_positive_forecast() -> None:
    base = effective_breach_buffer(-0.07, 0.09, 0.0)
    boosted = effective_breach_buffer(-0.07, 0.09, 0.02)
    assert boosted > base


def test_csp_action_gate_sell_when_eff_clear() -> None:
    p = CSPSpreadParams()
    assert (
        csp_action_gate(
            eff_buffer=0.025,
            predicted_return=0.01,
            safety_score=30.0,
            crash_veto=False,
            params=p,
        )
        == "SELL"
    )


def test_csp_action_gate_sell_otm_when_credit_band_met() -> None:
    p = CSPSpreadParams()
    assert (
        csp_action_gate(
            eff_buffer=-0.02,
            predicted_return=0.01,
            safety_score=5.0,
            crash_veto=False,
            params=p,
            schwab_safe_prob=0.915,
            schwab_credit_mid=0.27,
        )
        == "SELL_OTM"
    )
    assert (
        csp_action_gate(
            eff_buffer=-0.02,
            predicted_return=0.01,
            safety_score=5.0,
            crash_veto=False,
            params=p,
            schwab_safe_prob=0.915,
            schwab_credit_mid=0.60,
        )
        == "SKIP"
    )


def test_filter_macro_articles() -> None:
    arts = [
        {"id": "1", "title": "Fed raises rates", "body": "inflation", "sector_id": "macro"},
        {"id": "2", "title": "Random sports", "body": "game", "sector_id": "technology"},
    ]
    macro = filter_macro_articles(arts, None)
    assert len(macro) == 1


def test_filter_index_articles_spx() -> None:
    arts = [
        {"id": "1", "title": "SPY rallies on jobs report", "body": "", "sector_id": "macro"},
        {"id": "2", "title": "Oil prices", "body": "", "sector_id": "macro"},
    ]
    tagged = filter_index_articles(arts, "SPX", None)
    assert len(tagged) == 1
