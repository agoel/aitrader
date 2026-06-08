"""Deprecated alias — use learn_predict.run_prediction_tune (self-learning, not agent RSI)."""

from __future__ import annotations

import warnings

from aitrader.ml.learn_predict import (
    TUNE_DEFAULT_CAPITAL_USD,
    TUNE_MAX_ROUNDS,
    backtest_with_config,
    evaluate_news_backed_metrics,
    evaluate_portfolio_metrics,
    run_prediction_tune,
)

RSI_MAX_ROUNDS = TUNE_MAX_ROUNDS
RSI_DEFAULT_CAPITAL_USD = TUNE_DEFAULT_CAPITAL_USD


def run_prediction_rsi(*args, **kwargs):
    warnings.warn(
        "run_prediction_rsi is deprecated; use run_prediction_tune from learn_predict",
        DeprecationWarning,
        stacklevel=2,
    )
    return run_prediction_tune(*args, **kwargs)


__all__ = [
    "RSI_DEFAULT_CAPITAL_USD",
    "RSI_MAX_ROUNDS",
    "backtest_with_config",
    "evaluate_news_backed_metrics",
    "evaluate_portfolio_metrics",
    "run_prediction_rsi",
    "run_prediction_tune",
]
