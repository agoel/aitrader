"""Portfolio strategy overlays — sentiment, momentum, COT combinations."""

from __future__ import annotations

from typing import Any

from aitrader.ml.predict_config import PredictTuneConfig


def blend_predicted_return(
    ridge_pred: float,
    *,
    sentiment: float,
    momentum: float,
    cot_signal: float,
    news_articles: int,
    config: PredictTuneConfig,
) -> float:
    """Adjust ridge forecast with optional sentiment/momentum/COT overlays."""
    if config.strategy == "always_long":
        return max(ridge_pred, 0.01)
    if config.strategy == "news_ridge":
        return ridge_pred

    news_ok = news_articles >= config.min_news_confident
    base = ridge_pred if news_ok else 0.0
    overlay = (
        config.sentiment_weight * sentiment * 0.04
        + config.momentum_weight * momentum
        + config.cot_weight * cot_signal * 0.03
    )
    if config.strategy == "momentum_only":
        return config.momentum_weight * momentum
    if config.strategy == "cot_momentum":
        return config.momentum_weight * momentum + config.cot_weight * cot_signal * 0.03
    if config.strategy == "sentiment_momentum":
        if news_ok:
            return base + overlay
        if config.allow_momentum_without_news:
            return config.momentum_weight * momentum
        return 0.0
    # triple_combo and default: weighted blend of ridge + overlays
    ridge_w = max(0.0, 1.0 - config.sentiment_weight - config.momentum_weight - config.cot_weight)
    return ridge_w * base + overlay


def position_from_row(
    *,
    predicted_return: float,
    news_articles: int,
    sentiment: float = 0.0,
    momentum: float = 0.0,
    cot_signal: float = 0.0,
    config: PredictTuneConfig,
) -> str:
    """Long SPY vs cash under strategy-specific rules."""
    cfg = config
    news_ok = news_articles >= cfg.min_news_confident

    if cfg.strategy == "always_long":
        return "long"

    if cfg.strategy == "momentum_only":
        return "long" if momentum >= cfg.momentum_threshold else "cash"

    if cfg.strategy == "cot_momentum":
        mom_bull = momentum >= cfg.momentum_threshold
        cot_bull = cot_signal >= cfg.cot_threshold
        if cfg.combo_mode == "vote":
            votes = int(mom_bull) + int(cot_bull)
            return "long" if votes >= cfg.min_votes else "cash"
        return "long" if mom_bull and cot_bull else "cash"

    if cfg.strategy == "sentiment_momentum":
        sent_bull = sentiment >= cfg.sentiment_threshold
        mom_bull = momentum >= cfg.momentum_threshold
        ridge_bull = predicted_return > 0
        if cfg.combo_mode == "vote":
            votes = 0
            if news_ok and (ridge_bull or sent_bull):
                votes += 1
            if mom_bull:
                votes += 1
            if cfg.allow_momentum_without_news and mom_bull:
                return "long"
            return "long" if votes >= cfg.min_votes else "cash"
        if news_ok and ridge_bull:
            return "long"
        if cfg.allow_momentum_without_news and mom_bull:
            return "long"
        if news_ok and sent_bull and mom_bull:
            return "long"
        return "cash"

    if cfg.strategy == "triple_combo":
        sent_bull = sentiment >= cfg.sentiment_threshold
        mom_bull = momentum >= cfg.momentum_threshold
        cot_bull = cot_signal >= cfg.cot_threshold
        ridge_bull = predicted_return > 0
        if cfg.combo_mode == "vote":
            votes = int(mom_bull) + int(cot_bull)
            if news_ok and (ridge_bull or sent_bull):
                votes += 1
            return "long" if votes >= cfg.min_votes else "cash"
        score = 0.0
        if news_ok and ridge_bull:
            score += 0.35
        if sent_bull:
            score += cfg.sentiment_weight
        if mom_bull:
            score += cfg.momentum_weight
        if cot_bull:
            score += cfg.cot_weight
        return "long" if score >= cfg.score_threshold else "cash"

    # news_ridge (default)
    if not news_ok:
        if cfg.allow_momentum_without_news and momentum >= cfg.momentum_threshold:
            return "long"
        return "cash"
    if predicted_return > 0:
        return "long"
    return "cash"


def position_from_signal(
    predicted_return: float,
    news_articles: int,
    *,
    min_news_confident: int,
    sentiment: float = 0.0,
    momentum: float = 0.0,
    cot_signal: float = 0.0,
    config: PredictTuneConfig | None = None,
) -> str:
    cfg = config if config is not None else PredictTuneConfig(min_news_confident=min_news_confident)
    return position_from_row(
        predicted_return=predicted_return,
        news_articles=news_articles,
        sentiment=sentiment,
        momentum=momentum,
        cot_signal=cot_signal,
        config=cfg,
    )


def row_signals(row: dict[str, Any] | Any) -> dict[str, float]:
    """Extract signal fields from a monthly backtest / ledger row."""
    get = row.get if hasattr(row, "get") else lambda k, d=None: getattr(row, k, d)
    return {
        "sentiment": float(get("sentiment", 0) or 0),
        "momentum": float(get("momentum", 0) or 0),
        "cot_signal": float(get("cot_signal", 0) or 0),
    }
