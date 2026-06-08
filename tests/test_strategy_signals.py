from aitrader.ml.predict_config import (
    STRATEGY_ALWAYS_LONG,
    STRATEGY_COT_MOMENTUM,
    STRATEGY_TRIPLE_COMBO,
    PredictTuneConfig,
)
from aitrader.ml.portfolio_backtest import _position_from_signal
from aitrader.ml.strategy_signals import blend_predicted_return, position_from_row


def test_always_long_strategy() -> None:
    cfg = PredictTuneConfig(strategy=STRATEGY_ALWAYS_LONG)
    assert position_from_row(
        predicted_return=-0.1,
        news_articles=0,
        config=cfg,
    ) == "long"


def test_triple_combo_vote() -> None:
    cfg = PredictTuneConfig(
        strategy=STRATEGY_TRIPLE_COMBO,
        combo_mode="vote",
        min_votes=2,
        sentiment_threshold=0.0,
        momentum_threshold=0.0,
        cot_threshold=0.0,
    )
    assert (
        position_from_row(
            predicted_return=0.02,
            news_articles=3,
            sentiment=0.1,
            momentum=0.03,
            cot_signal=0.2,
            config=cfg,
        )
        == "long"
    )
    assert (
        position_from_row(
            predicted_return=-0.02,
            news_articles=0,
            sentiment=-0.1,
            momentum=-0.03,
            cot_signal=-0.2,
            config=cfg,
        )
        == "cash"
    )


def test_cot_momentum_and_mode() -> None:
    cfg = PredictTuneConfig(
        strategy=STRATEGY_COT_MOMENTUM,
        momentum_threshold=0.01,
        cot_threshold=0.05,
        combo_mode="and",
    )
    assert (
        position_from_row(
            predicted_return=0.0,
            news_articles=0,
            momentum=0.02,
            cot_signal=0.1,
            config=cfg,
        )
        == "long"
    )
    assert (
        position_from_row(
            predicted_return=0.0,
            news_articles=0,
            momentum=0.02,
            cot_signal=-0.1,
            config=cfg,
        )
        == "cash"
    )


def test_blend_predicted_return_triple() -> None:
    cfg = PredictTuneConfig(
        strategy=STRATEGY_TRIPLE_COMBO,
        sentiment_weight=0.3,
        momentum_weight=0.4,
        cot_weight=0.3,
    )
    blended = blend_predicted_return(
        0.01,
        sentiment=0.2,
        momentum=0.03,
        cot_signal=0.5,
        news_articles=5,
        config=cfg,
    )
    assert blended > 0.01


def test_position_from_signal_backward_compat() -> None:
    assert _position_from_signal(0.05, 2, min_news_confident=1) == "long"
    assert _position_from_signal(-0.05, 2, min_news_confident=1) == "cash"
    assert _position_from_signal(0.05, 0, min_news_confident=1) == "cash"
