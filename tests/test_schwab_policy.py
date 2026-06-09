"""Schwab quotes-only policy enforcement."""

from __future__ import annotations

import pytest

from aitrader.data.schwab import (
    MARKET_DATA_BASE,
    SCHWAB_QUOTES_ONLY_POLICY,
    assert_quotes_only_url,
)


def test_quotes_only_policy_flag() -> None:
    assert SCHWAB_QUOTES_ONLY_POLICY is True


def test_allows_market_data_urls() -> None:
    assert_quotes_only_url(f"{MARKET_DATA_BASE}/quotes?symbols=SPY")
    assert_quotes_only_url(f"{MARKET_DATA_BASE}/chains?symbol=%24SPX")


def test_blocks_trading_urls() -> None:
    with pytest.raises(RuntimeError, match="trading API blocked"):
        assert_quotes_only_url("https://api.schwabapi.com/trader/v1/accounts/123/orders")
    with pytest.raises(RuntimeError, match="trading API blocked"):
        assert_quotes_only_url("https://api.schwabapi.com/trader/v1/accounts/hash/orders")
