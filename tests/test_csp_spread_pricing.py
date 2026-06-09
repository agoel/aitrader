"""CSP spread pricing from Schwab-style option chains."""

from __future__ import annotations

from aitrader.ml.csp_spread_pricing import (
    assignment_prob_from_delta,
    exit_signal_for_delta,
    pick_furthest_credit_band_spread,
    quote_spx_spread_at_strikes,
    safe_prob_from_delta,
)


def _sample_chain() -> dict:
    return {
        "underlying": {"mark": 5500.0, "last": 5500.0},
        "putExpDateMap": {
            "2026-07-17:38": {
                "5050.0": [
                    {
                        "putCall": "PUT",
                        "symbol": "SPX_PUT_5050",
                        "strikePrice": 5050.0,
                        "bid": 0.32,
                        "ask": 0.34,
                        "mark": 0.33,
                        "delta": -0.085,
                    }
                ],
                "5045.0": [
                    {
                        "putCall": "PUT",
                        "symbol": "SPX_PUT_5045",
                        "strikePrice": 5045.0,
                        "bid": 0.07,
                        "ask": 0.09,
                        "mark": 0.08,
                        "delta": -0.04,
                    }
                ],
                "5040.0": [
                    {
                        "putCall": "PUT",
                        "symbol": "SPX_PUT_5040",
                        "strikePrice": 5040.0,
                        "bid": 0.22,
                        "ask": 0.24,
                        "mark": 0.23,
                        "delta": -0.082,
                    }
                ],
                "5035.0": [
                    {
                        "putCall": "PUT",
                        "symbol": "SPX_PUT_5035",
                        "strikePrice": 5035.0,
                        "bid": 0.06,
                        "ask": 0.08,
                        "mark": 0.07,
                        "delta": -0.038,
                    }
                ],
            }
        },
    }


def test_quote_spx_spread_at_strikes() -> None:
    q = quote_spx_spread_at_strikes(
        _sample_chain(), short_strike=5050.0, long_strike=5045.0, expiry="2026-07-17"
    )
    assert q is not None
    assert q.credit_mid == 0.25
    assert q.safe_prob > 0.90


def test_pick_furthest_credit_band_spread() -> None:
    q = pick_furthest_credit_band_spread(
        _sample_chain(),
        spread_width=5.0,
        credit_lo=0.25,
        credit_hi=0.30,
        expiry="2026-07-17",
    )
    assert q is not None
    assert q.short_leg.strike == 5050.0
    assert q.long_leg.strike == 5045.0
    assert 0.25 <= q.credit_mid <= 0.30


def test_assignment_and_exit_rules() -> None:
    assert assignment_prob_from_delta(-0.085) == 0.085
    assert safe_prob_from_delta(-0.085) == 0.915
    assert exit_signal_for_delta(-0.085) == "HOLD"
    assert exit_signal_for_delta(-0.35) == "EXIT"
