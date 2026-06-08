"""Tunable prediction parameters — selected by RSI backtest loop."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class PredictTuneConfig:
    name: str = "default"
    keyword_scale: float = 1.0
    cluster_blend: float = 0.0
    momentum_dampen: float = 1.0
    event_keyword_boost: float = 1.0
    min_news_train: int = 0
    min_news_confident: int = 1
    train_news_only: bool = False
    # Deprecated: momentum-only fallback removed — use no_news_signal_zero behavior in predict.
    no_news_momentum_only: bool = False

    def scaled_keyword(self, score: float) -> float:
        return score * self.keyword_scale

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_CONFIG = PredictTuneConfig(name="default")

RSI_CANDIDATES: tuple[PredictTuneConfig, ...] = (
    PredictTuneConfig(name="v1_baseline"),
    PredictTuneConfig(
        name="v2_news_gated",
        min_news_train=1,
        cluster_blend=0.45,
        keyword_scale=1.25,
    ),
    PredictTuneConfig(
        name="v3_cluster_prior",
        min_news_train=1,
        cluster_blend=0.65,
        keyword_scale=1.5,
        event_keyword_boost=1.75,
    ),
    PredictTuneConfig(
        name="v4_event_boost",
        min_news_train=1,
        cluster_blend=0.55,
        keyword_scale=2.0,
        event_keyword_boost=2.5,
        train_news_only=True,
    ),
    PredictTuneConfig(
        name="v5_momentum_damp",
        min_news_train=1,
        min_news_confident=2,
        cluster_blend=0.7,
        keyword_scale=1.75,
        event_keyword_boost=2.0,
        momentum_dampen=0.35,
        train_news_only=True,
    ),
)

RSI_MIN_NEWS_IC = 0.12
RSI_MIN_HIT_RATE = 0.65
RSI_MIN_NEWS_ROWS = 3
RSI_MIN_COVERAGE = 0.60


def expand_rsi_candidates() -> tuple[PredictTuneConfig, ...]:
    """Baseline candidates plus grid over knobs that affect long/cash and forecast level."""
    by_name: dict[str, PredictTuneConfig] = {c.name: c for c in RSI_CANDIDATES}
    for kw in (1.25, 1.5, 1.75, 2.0, 2.5, 3.0):
        for cb in (0.35, 0.5, 0.65, 0.8, 0.9):
            for boost in (1.0, 1.75, 2.5):
                for damp in (0.5, 1.0):
                    name = f"g_kw{kw}_cb{cb}_eb{boost}_md{damp}"
                    if name in by_name:
                        continue
                    by_name[name] = PredictTuneConfig(
                        name=name,
                        keyword_scale=kw,
                        cluster_blend=cb,
                        event_keyword_boost=boost,
                        momentum_dampen=damp,
                        min_news_train=1,
                        min_news_confident=1,
                    )
    ordered = list(RSI_CANDIDATES)
    ordered.extend(c for n, c in sorted(by_name.items()) if n not in {x.name for x in RSI_CANDIDATES})
    return tuple(ordered)


def save_predict_config(run_dir: Path, config: PredictTuneConfig) -> Path:
    path = run_dir / "models" / "predict_config.json"
    path.write_text(json.dumps(config.to_dict(), indent=2) + "\n")
    return path


def load_predict_config(run_dir: Path) -> PredictTuneConfig:
    path = run_dir / "models" / "predict_config.json"
    if not path.exists():
        return DEFAULT_CONFIG
    data = json.loads(path.read_text())
    return PredictTuneConfig(**data)
