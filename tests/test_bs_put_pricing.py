"""Black-Scholes put spread pricing."""

from __future__ import annotations

import math

import pandas as pd

from aitrader.ml.bs_put_pricing import (
    bs_put_delta,
    bs_put_price,
    pick_bs_put_spread,
    simulate_daily_safe_exit,
    spread_expiry_payoff_per_contract,
)
from aitrader.ml.csp_portfolio_backtest import contracts_for_equity
from aitrader.ml.csp_spread_advisor import tier_a_action, tier_b_action


def test_bs_put_price_atm_positive() -> None:
    px = bs_put_price(100.0, 100.0, vol=0.20, dte_days=30)
    assert px > 0.5


def test_bs_put_delta_negative_otm() -> None:
    d = bs_put_delta(5500.0, 5300.0, vol=0.18, dte_days=25)
    assert -0.25 < d < -0.03


def test_pick_bs_put_spread_credit_band() -> None:
    q = pick_bs_put_spread(5500.0, vol=0.18, dte_days=25, spread_width=5.0)
    assert q is not None
    assert 0.05 <= q.credit_mid <= 1.0
    assert q.short_leg.strike > q.long_leg.strike
    assert q.safe_prob >= 0.85


def test_spread_expiry_payoff_max_loss() -> None:
    intrinsic = spread_expiry_payoff_per_contract(5000.0, 4995.0, 4980.0)
    assert math.isclose(intrinsic, 5.0)


def test_spread_expiry_payoff_otm_zero() -> None:
    intrinsic = spread_expiry_payoff_per_contract(5000.0, 4995.0, 5100.0)
    assert intrinsic == 0.0


def test_contracts_for_equity_compounds() -> None:
    assert contracts_for_equity(10_000) == 20
    assert contracts_for_equity(12_000) == 24
    assert contracts_for_equity(4_000) == 8
    assert contracts_for_equity(499) == 0


def test_simulate_daily_safe_exit_triggers_on_drop() -> None:
    idx = pd.bdate_range("2024-01-02", periods=30, freq="B")
    # SPY ~550 → SPX ~5500; drop mid-cycle to push delta up
    prices = [550.0] * 10 + [520.0] * 5 + [500.0] * 15
    closes = pd.Series(prices, index=idx)
    signal = idx[0]
    expiry = idx[22]
    result = simulate_daily_safe_exit(
        closes,
        signal_day=signal,
        expiry_day=expiry,
        short_strike_index=5300.0,
        long_strike_index=5295.0,
        entry_credit_per_share=0.25,
        contracts=10,
        exit_min_safe_prob=0.70,
    )
    assert result.outcome == "early_exit"
    assert result.exit_day is not None
    assert result.exit_safe_prob is not None
    assert result.exit_safe_prob < 0.70


def test_tier_a_skips_marginal() -> None:
    action, traded = tier_a_action("SKIP", crash_veto=False)
    assert action == "SKIP"
    assert traded is False
    action, traded = tier_a_action("SELL", crash_veto=False)
    assert action == "SELL"
    assert traded is True


def test_tier_b_trades_unless_veto() -> None:
    action, traded = tier_b_action("SKIP", crash_veto=False)
    assert action == "WIDEN"
    assert traded is True
    action, traded = tier_b_action("SELL", crash_veto=False)
    assert action == "SELL"
    assert traded is True
    action, traded = tier_b_action("WIDEN", crash_veto=True)
    assert action == "SKIP"
    assert traded is False
