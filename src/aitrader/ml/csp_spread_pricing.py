"""Schwab-backed bull put spread pricing and assignment probability."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from aitrader.data.schwab import SchwabClient

# SPX quotes are in index points ($100 per point per contract).
SPX_DEFAULT_SPREAD_WIDTH = 5.0
SPX_CHAIN_STRIKE_COUNT = 500


@dataclass
class PutLeg:
    strike: float
    symbol: str
    bid: float
    ask: float
    mark: float
    delta: float


@dataclass
class PutSpreadQuote:
    expiry: str
    short_leg: PutLeg
    long_leg: PutLeg
    credit_conservative: float  # short bid - long ask (natural fill — often worse than mark)
    credit_mid: float  # short mark - long mark (≈ TOS Mark column)
    width: float
    short_delta_abs: float
    assignment_prob: float
    safe_prob: float
    exit_signal: Literal["HOLD", "EXIT"]
    pricing_source: str


def _iter_puts(chain: dict[str, Any]) -> list[tuple[str, PutLeg]]:
    puts: list[tuple[str, PutLeg]] = []
    put_map = chain.get("putExpDateMap") or {}
    for exp_key, strikes in put_map.items():
        expiry = exp_key.split(":")[0]
        for strike_key, contracts in strikes.items():
            if not contracts:
                continue
            c = contracts[0]
            puts.append(
                (
                    expiry,
                    PutLeg(
                        strike=float(c.get("strikePrice", strike_key)),
                        symbol=str(c.get("symbol", "")),
                        bid=float(c.get("bid", 0) or 0),
                        ask=float(c.get("ask", 0) or 0),
                        mark=float(c.get("mark", 0) or 0),
                        delta=float(c.get("delta", 0) or 0),
                    ),
                )
            )
    return puts


def _leg_by_strike(legs: list[PutLeg], strike: float, *, tol: float = 0.01) -> PutLeg | None:
    for leg in legs:
        if abs(leg.strike - strike) <= tol:
            return leg
    return None


def _spread_from_legs(short: PutLeg, long: PutLeg, *, expiry: str, min_safe_prob: float) -> PutSpreadQuote | None:
    credit_mid = short.mark - long.mark
    if credit_mid <= 0:
        return None
    delta_abs = abs(short.delta)
    assign_p = assignment_prob_from_delta(short.delta)
    safe_p = 1.0 - assign_p
    if safe_p < min_safe_prob:
        return None
    return PutSpreadQuote(
        expiry=expiry,
        short_leg=short,
        long_leg=long,
        credit_conservative=short.bid - long.ask,
        credit_mid=credit_mid,
        width=short.strike - long.strike,
        short_delta_abs=delta_abs,
        assignment_prob=assign_p,
        safe_prob=safe_p,
        exit_signal=exit_signal_for_delta(short.delta, min_safe_prob=0.70),  # sell when OTM prob < 70%
        pricing_source="schwab_chain",
    )


def assignment_prob_from_delta(delta: float) -> float:
    """Short OTM put: |delta| ≈ risk-neutral touch probability at expiry."""
    return float(min(1.0, max(0.0, abs(delta))))


def safe_prob_from_delta(delta: float) -> float:
    return 1.0 - assignment_prob_from_delta(delta)


def exit_signal_for_delta(delta: float, *, min_safe_prob: float = 0.70) -> Literal["HOLD", "EXIT"]:
    """Exit when assignment risk rises — safe probability falls below threshold."""
    return "EXIT" if safe_prob_from_delta(delta) < min_safe_prob else "HOLD"


def quote_spx_spread_at_strikes(
    chain: dict[str, Any],
    *,
    short_strike: float,
    long_strike: float,
    expiry: str | None = None,
    min_safe_prob: float = 0.90,
) -> PutSpreadQuote | None:
    """Quote a fixed short/long put pair from a Schwab chain."""
    by_exp: dict[str, list[PutLeg]] = {}
    for exp, leg in _iter_puts(chain):
        if expiry and exp != expiry:
            continue
        by_exp.setdefault(exp, []).append(leg)
    for exp, legs in by_exp.items():
        short = _leg_by_strike(legs, short_strike)
        long = _leg_by_strike(legs, long_strike)
        if short and long and long.strike < short.strike:
            return _spread_from_legs(short, long, expiry=exp, min_safe_prob=min_safe_prob)
    return None


def pick_furthest_credit_band_spread(
    chain: dict[str, Any],
    *,
    spread_width: float = SPX_DEFAULT_SPREAD_WIDTH,
    credit_lo: float = 0.25,
    credit_hi: float = 0.30,
    entry_min_safe_prob: float = 0.90,
    max_entry_safe_prob: float = 0.93,
    min_short_delta: float = 0.075,
    expiry: str | None = None,
) -> PutSpreadQuote | None:
    """Furthest OTM (lowest short strike) 5-pt spread with realistic mid credit in [lo, hi].

    Excludes phantom far-OTM marks (e.g. 6190 at 97% OTM showing 0.25 credit while TOS shows ~0.05).
    Requires short |delta| in [min_short_delta, 1-entry_min_safe_prob] — typically ~7.5–10% (~90–92.5% OTM).
    """
    puts = _iter_puts(chain)
    if not puts:
        return None

    by_exp: dict[str, list[PutLeg]] = {}
    for exp, leg in puts:
        if expiry and exp != expiry:
            continue
        by_exp.setdefault(exp, []).append(leg)

    best: PutSpreadQuote | None = None
    furthest_short = float("inf")

    for exp, legs in sorted(by_exp.items()):
        for short in legs:
            long_leg = _leg_by_strike(legs, short.strike - spread_width)
            if long_leg is None:
                continue
            q = _spread_from_legs(short, long_leg, expiry=exp, min_safe_prob=entry_min_safe_prob)
            if q is None:
                continue
            if not (credit_lo <= q.credit_mid <= credit_hi):
                continue
            delta_abs = q.short_delta_abs
            if delta_abs < min_short_delta or delta_abs > (1.0 - entry_min_safe_prob):
                continue
            if q.safe_prob > max_entry_safe_prob:
                continue
            if short.strike < furthest_short:
                furthest_short = short.strike
                best = q
    return best


def fetch_index_chain(
    client: SchwabClient,
    index: str,
    expiry: date | None = None,
    *,
    analytical: bool = False,
    underlying_price: float | None = None,
    volatility: float | None = None,
    days_to_expiration: int | None = None,
) -> dict[str, Any]:
    """Fetch option chain. ANALYTICAL mode uses DTE/spot/vol only (no calendar dates)."""
    strategy = "ANALYTICAL" if analytical else None
    strike_count = 50 if analytical else SPX_CHAIN_STRIKE_COUNT
    from_date = None if analytical else expiry
    to_date = None if analytical else expiry
    return client.option_chain(
        index,
        contract_type="PUT",
        from_date=from_date,
        to_date=to_date,
        strike_count=strike_count,
        strategy=strategy,
        underlying_price=underlying_price,
        volatility=volatility,
        days_to_expiration=days_to_expiration,
        include_quotes=not analytical,
    )


def fetch_spx_chain(
    client: SchwabClient,
    expiry: date,
    *,
    analytical: bool = False,
    underlying_price: float | None = None,
    volatility: float | None = None,
    days_to_expiration: int | None = None,
) -> dict[str, Any]:
    return fetch_index_chain(
        client,
        "SPX",
        expiry,
        analytical=analytical,
        underlying_price=underlying_price,
        volatility=volatility,
        days_to_expiration=days_to_expiration,
    )


def fetch_index_put_spread(
    client: SchwabClient,
    index: str,
    *,
    expiry: date,
    target_credit_lo: float = 0.20,
    target_credit_hi: float = 0.30,
    spread_width: float = SPX_DEFAULT_SPREAD_WIDTH,
    entry_min_safe_prob: float = 0.90,
    max_entry_safe_prob: float = 0.93,
    min_short_delta: float = 0.075,
    analytical: bool = False,
    underlying_price: float | None = None,
    volatility: float | None = None,
    days_to_expiration: int | None = None,
    short_strike: float | None = None,
    long_strike: float | None = None,
) -> PutSpreadQuote | None:
    """Live or analytical Schwab chain for index bull put spread (SPX or RUT)."""
    chain = fetch_index_chain(
        client,
        index,
        expiry,
        analytical=analytical,
        underlying_price=underlying_price,
        volatility=volatility,
        days_to_expiration=days_to_expiration,
    )
    exp_str = expiry.isoformat()
    if short_strike is not None and long_strike is not None:
        q = quote_spx_spread_at_strikes(
            chain,
            short_strike=short_strike,
            long_strike=long_strike,
            expiry=exp_str if not analytical else None,
            min_safe_prob=entry_min_safe_prob,
        )
        if q and not (target_credit_lo <= q.credit_mid <= target_credit_hi):
            return None
        if q:
            q.pricing_source = "schwab_analytical" if analytical else "schwab_chain"
        return q
    q = pick_furthest_credit_band_spread(
        chain,
        spread_width=spread_width,
        credit_lo=target_credit_lo,
        credit_hi=target_credit_hi,
        entry_min_safe_prob=entry_min_safe_prob,
        max_entry_safe_prob=max_entry_safe_prob,
        min_short_delta=min_short_delta,
        expiry=None if analytical else exp_str,
    )
    if q and analytical:
        q.pricing_source = "schwab_analytical"
    return q


def fetch_spx_put_spread(
    client: SchwabClient,
    *,
    expiry: date,
    target_credit_lo: float = 0.25,
    target_credit_hi: float = 0.30,
    spread_width: float = SPX_DEFAULT_SPREAD_WIDTH,
    entry_min_safe_prob: float = 0.90,
    max_entry_safe_prob: float = 0.93,
    min_short_delta: float = 0.075,
    exit_min_safe_prob: float = 0.70,
    analytical: bool = False,
    underlying_price: float | None = None,
    volatility: float | None = None,
    days_to_expiration: int | None = None,
    short_strike: float | None = None,
    long_strike: float | None = None,
) -> PutSpreadQuote | None:
    """Live or analytical Schwab chain for SPX bull put spread."""
    return fetch_index_put_spread(
        client,
        "SPX",
        expiry=expiry,
        target_credit_lo=target_credit_lo,
        target_credit_hi=target_credit_hi,
        spread_width=spread_width,
        entry_min_safe_prob=entry_min_safe_prob,
        max_entry_safe_prob=max_entry_safe_prob,
        min_short_delta=min_short_delta,
        analytical=analytical,
        underlying_price=underlying_price,
        volatility=volatility,
        days_to_expiration=days_to_expiration,
        short_strike=short_strike,
        long_strike=long_strike,
    )


def realized_vol(closes: list[float], *, window: int = 20) -> float:
    if len(closes) < window + 1:
        return 0.18
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0]
    if len(rets) < window:
        return 0.18
    chunk = rets[-window:]
    var = sum(r * r for r in chunk) / len(chunk)
    return float(max(0.08, min(0.60, math.sqrt(var * 252))))
