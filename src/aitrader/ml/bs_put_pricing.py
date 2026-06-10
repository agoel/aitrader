"""Black-Scholes put spread pricing for CSP portfolio backtests."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from aitrader.ml.csp_spread_pricing import (
    PutLeg,
    PutSpreadQuote,
    assignment_prob_from_delta,
    exit_signal_for_delta,
    realized_vol,
    safe_prob_from_delta,
)

DEFAULT_RISK_FREE = 0.02


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_put_price(
    spot: float,
    strike: float,
    *,
    vol: float,
    dte_days: int,
    risk_free: float = DEFAULT_RISK_FREE,
) -> float:
    if spot <= 0 or strike <= 0 or dte_days <= 0 or vol <= 0:
        return max(0.0, strike - spot)
    t = dte_days / 365.0
    sigma_sqrt_t = vol * math.sqrt(t)
    if sigma_sqrt_t <= 0:
        return max(0.0, strike - spot)
    d1 = (math.log(spot / strike) + (risk_free + 0.5 * vol * vol) * t) / sigma_sqrt_t
    d2 = d1 - sigma_sqrt_t
    return strike * math.exp(-risk_free * t) * norm_cdf(-d2) - spot * norm_cdf(-d1)


def bs_put_delta(
    spot: float,
    strike: float,
    *,
    vol: float,
    dte_days: int,
    risk_free: float = DEFAULT_RISK_FREE,
) -> float:
    if spot <= 0 or strike <= 0 or dte_days <= 0 or vol <= 0:
        return -1.0 if strike >= spot else 0.0
    t = dte_days / 365.0
    sigma_sqrt_t = vol * math.sqrt(t)
    if sigma_sqrt_t <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + (risk_free + 0.5 * vol * vol) * t) / sigma_sqrt_t
    return norm_cdf(d1) - 1.0


def _leg_from_bs(strike: float, *, spot: float, vol: float, dte_days: int) -> PutLeg:
    mark = bs_put_price(spot, strike, vol=vol, dte_days=dte_days)
    delta = bs_put_delta(spot, strike, vol=vol, dte_days=dte_days)
    return PutLeg(
        strike=strike,
        symbol=f"BS_PUT_{strike:.0f}",
        bid=mark,
        ask=mark,
        mark=mark,
        delta=delta,
    )


def bs_spread_mid(
    spot_index: float,
    short_strike: float,
    long_strike: float,
    *,
    vol: float,
    dte_days: int,
) -> float:
    """Bull put spread mark (short mark − long mark) in index points."""
    short = bs_put_price(spot_index, short_strike, vol=vol, dte_days=dte_days)
    long = bs_put_price(spot_index, long_strike, vol=vol, dte_days=dte_days)
    return max(0.0, short - long)


def pick_bs_put_spread(
    spot_index: float,
    *,
    vol: float,
    dte_days: int,
    spread_width: float = 5.0,
    credit_lo: float = 0.20,
    credit_hi: float = 0.30,
    entry_min_safe_prob: float = 0.90,
    max_entry_safe_prob: float = 0.93,
    min_short_delta: float = 0.075,
    strike_step: float = 5.0,
    expiry: str = "",
) -> PutSpreadQuote | None:
    """Furthest OTM 5-pt put spread with BS marks in credit band (Schwab ANALYTICAL analogue)."""
    if spot_index <= 0 or dte_days <= 0:
        return None

    lo_strike = max(strike_step, spot_index * 0.70)
    hi_strike = spot_index * 0.995
    strikes: list[float] = []
    k = math.floor(hi_strike / strike_step) * strike_step
    while k >= lo_strike:
        strikes.append(k)
        k -= strike_step

    best: PutSpreadQuote | None = None
    furthest = float("inf")
    fallback: PutSpreadQuote | None = None
    fallback_strike = float("inf")

    for short_k in strikes:
        long_k = short_k - spread_width
        if long_k <= 0:
            continue
        short = _leg_from_bs(short_k, spot=spot_index, vol=vol, dte_days=dte_days)
        long = _leg_from_bs(long_k, spot=spot_index, vol=vol, dte_days=dte_days)
        credit_mid = short.mark - long.mark
        if credit_mid <= 0:
            continue
        delta_abs = abs(short.delta)
        safe_p = 1.0 - assignment_prob_from_delta(short.delta)
        if delta_abs < min_short_delta or safe_p < entry_min_safe_prob:
            continue
        if safe_p > max_entry_safe_prob:
            continue
        q = PutSpreadQuote(
            expiry=expiry,
            short_leg=short,
            long_leg=long,
            credit_conservative=credit_mid,
            credit_mid=credit_mid,
            width=spread_width,
            short_delta_abs=delta_abs,
            assignment_prob=assignment_prob_from_delta(short.delta),
            safe_prob=safe_p,
            exit_signal=exit_signal_for_delta(short.delta),
            pricing_source="black_scholes",
        )
        in_band = credit_lo <= credit_mid <= credit_hi
        if in_band and short_k < furthest:
            furthest = short_k
            best = q
        elif q is not None and short_k < fallback_strike:
            fallback_strike = short_k
            fallback = q

    return best or fallback


def spread_expiry_payoff_per_contract(
    short_strike_index: float,
    long_strike_index: float,
    spot_index: float,
) -> float:
    """Spread intrinsic at expiry in index points (×100 for USD per contract)."""
    short_intrinsic = max(0.0, short_strike_index - spot_index)
    long_intrinsic = max(0.0, long_strike_index - spot_index)
    return short_intrinsic - long_intrinsic


def _remaining_dte(signal_day: pd.Timestamp, day: pd.Timestamp, expiry_day: pd.Timestamp) -> int:
    if day >= expiry_day:
        return 0
    return max(1, len(pd.bdate_range(day + pd.Timedelta(days=1), expiry_day)))


@dataclass
class SpreadExitResult:
    outcome: Literal["expiry", "early_exit"]
    pnl_usd: float
    assigned: bool
    exit_day: str | None
    exit_safe_prob: float | None
    close_debit_per_share: float | None


def simulate_daily_safe_exit(
    closes: pd.Series,
    *,
    signal_day: pd.Timestamp,
    expiry_day: pd.Timestamp,
    short_strike_index: float,
    long_strike_index: float,
    entry_credit_per_share: float,
    contracts: int,
    index_scale: float = 10.0,
    exit_min_safe_prob: float = 0.70,
) -> SpreadExitResult:
    """Mark spread daily; exit first session where short-leg safe prob &lt; 70%."""
    mult = 100.0 * contracts
    monitor_days = closes.index[(closes.index > signal_day) & (closes.index <= expiry_day)]

    for day in monitor_days:
        if day >= expiry_day:
            break
        spot_idx = float(closes.loc[day]) * index_scale
        dte = _remaining_dte(signal_day, day, expiry_day)
        vol = realized_vol(closes.loc[:day].tail(25).tolist())
        delta = bs_put_delta(spot_idx, short_strike_index, vol=vol, dte_days=dte)
        safe_p = safe_prob_from_delta(delta)
        if safe_p < exit_min_safe_prob:
            close_debit = bs_spread_mid(
                spot_idx,
                short_strike_index,
                long_strike_index,
                vol=vol,
                dte_days=dte,
            )
            pnl = (entry_credit_per_share - close_debit) * mult
            return SpreadExitResult(
                outcome="early_exit",
                pnl_usd=pnl,
                assigned=False,
                exit_day=day.strftime("%Y-%m-%d"),
                exit_safe_prob=round(safe_p, 4),
                close_debit_per_share=round(close_debit, 4),
            )

    if expiry_day in closes.index:
        spot_exp = float(closes.loc[expiry_day])
    else:
        prior = closes.index[closes.index <= expiry_day]
        spot_exp = float(closes.loc[prior[-1]]) if len(prior) else float(closes.iloc[-1])
    spot_idx_exp = spot_exp * index_scale
    intrinsic = spread_expiry_payoff_per_contract(
        short_strike_index, long_strike_index, spot_idx_exp
    )
    pnl = entry_credit_per_share * mult - intrinsic * mult
    return SpreadExitResult(
        outcome="expiry",
        pnl_usd=pnl,
        assigned=intrinsic > 0,
        exit_day=None,
        exit_safe_prob=None,
        close_debit_per_share=None,
    )
