"""Tunable prediction parameters — selected by self-learning (predict tune) loop."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

STRATEGY_NEWS_RIDGE = "news_ridge"
STRATEGY_SENTIMENT_MOMENTUM = "sentiment_momentum"
STRATEGY_COT_MOMENTUM = "cot_momentum"
STRATEGY_TRIPLE_COMBO = "triple_combo"
STRATEGY_MOMENTUM_ONLY = "momentum_only"
STRATEGY_ALWAYS_LONG = "always_long"


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
    # Multi-signal portfolio strategies
    strategy: str = STRATEGY_NEWS_RIDGE
    sentiment_weight: float = 0.0
    momentum_weight: float = 0.0
    cot_weight: float = 0.0
    sentiment_threshold: float = 0.0
    momentum_threshold: float = 0.0
    cot_threshold: float = 0.0
    allow_momentum_without_news: bool = False
    combo_mode: str = "and"  # and | vote
    min_votes: int = 2
    score_threshold: float = 0.45
    # Half-width of return band = residual_std * confidence_z (1.96 ≈ 95% naive normal)
    confidence_z: float = 1.96

    def scaled_keyword(self, score: float) -> float:
        return score * self.keyword_scale

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_CONFIG = PredictTuneConfig(name="default")

TUNE_CANDIDATES: tuple[PredictTuneConfig, ...] = (
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
    # --- Multi-signal strategies (sentiment + momentum + COT) ---
    PredictTuneConfig(
        name="s_always_long",
        strategy=STRATEGY_ALWAYS_LONG,
    ),
    PredictTuneConfig(
        name="s_momentum_trend",
        strategy=STRATEGY_MOMENTUM_ONLY,
        momentum_weight=1.0,
        momentum_threshold=0.0,
    ),
    PredictTuneConfig(
        name="s_momentum_strict",
        strategy=STRATEGY_MOMENTUM_ONLY,
        momentum_weight=1.0,
        momentum_threshold=0.02,
    ),
    PredictTuneConfig(
        name="s_cot_momentum_and",
        strategy=STRATEGY_COT_MOMENTUM,
        momentum_weight=0.55,
        cot_weight=0.45,
        momentum_threshold=0.0,
        cot_threshold=0.0,
        combo_mode="and",
    ),
    PredictTuneConfig(
        name="s_cot_momentum_vote",
        strategy=STRATEGY_COT_MOMENTUM,
        momentum_weight=0.5,
        cot_weight=0.5,
        momentum_threshold=-0.01,
        cot_threshold=-0.1,
        combo_mode="vote",
        min_votes=1,
    ),
    PredictTuneConfig(
        name="s_sentiment_momentum_loose",
        strategy=STRATEGY_SENTIMENT_MOMENTUM,
        sentiment_weight=0.4,
        momentum_weight=0.6,
        sentiment_threshold=-0.05,
        momentum_threshold=-0.01,
        allow_momentum_without_news=True,
        combo_mode="vote",
        min_votes=1,
    ),
    PredictTuneConfig(
        name="s_sentiment_momentum_strict",
        strategy=STRATEGY_SENTIMENT_MOMENTUM,
        sentiment_weight=0.5,
        momentum_weight=0.5,
        sentiment_threshold=0.05,
        momentum_threshold=0.02,
        combo_mode="vote",
        min_votes=2,
    ),
    PredictTuneConfig(
        name="s_triple_vote2",
        strategy=STRATEGY_TRIPLE_COMBO,
        sentiment_weight=0.3,
        momentum_weight=0.35,
        cot_weight=0.35,
        sentiment_threshold=0.0,
        momentum_threshold=0.0,
        cot_threshold=0.0,
        combo_mode="vote",
        min_votes=2,
    ),
    PredictTuneConfig(
        name="s_triple_vote1",
        strategy=STRATEGY_TRIPLE_COMBO,
        sentiment_weight=0.35,
        momentum_weight=0.35,
        cot_weight=0.3,
        sentiment_threshold=-0.05,
        momentum_threshold=-0.02,
        cot_threshold=-0.15,
        combo_mode="vote",
        min_votes=1,
    ),
    PredictTuneConfig(
        name="s_triple_score_balanced",
        strategy=STRATEGY_TRIPLE_COMBO,
        sentiment_weight=0.3,
        momentum_weight=0.35,
        cot_weight=0.35,
        sentiment_threshold=0.0,
        momentum_threshold=0.01,
        cot_threshold=0.05,
        combo_mode="and",
        score_threshold=0.4,
    ),
    PredictTuneConfig(
        name="s_news_mom_fill",
        strategy=STRATEGY_NEWS_RIDGE,
        allow_momentum_without_news=True,
        momentum_threshold=0.01,
    ),
    PredictTuneConfig(
        name="s_triple_news_heavy",
        strategy=STRATEGY_TRIPLE_COMBO,
        sentiment_weight=0.45,
        momentum_weight=0.3,
        cot_weight=0.25,
        sentiment_threshold=0.0,
        momentum_threshold=0.0,
        cot_threshold=-0.1,
        combo_mode="vote",
        min_votes=2,
    ),
)

TUNE_MIN_NEWS_IC = 0.12
TUNE_MIN_HIT_RATE = 0.65
TUNE_MIN_NEWS_ROWS = 3
TUNE_MIN_COVERAGE = 0.60
TUNE_MIN_PORTFOLIO_EXCESS = 0.0
TUNE_MAX_ROUNDS = 5
TUNE_DEFAULT_CAPITAL_USD = 10_000

# Deprecated aliases (Phase 2 — remove after one release)
RSI_CANDIDATES = TUNE_CANDIDATES
RSI_MIN_NEWS_IC = TUNE_MIN_NEWS_IC
RSI_MIN_HIT_RATE = TUNE_MIN_HIT_RATE
RSI_MIN_NEWS_ROWS = TUNE_MIN_NEWS_ROWS
RSI_MIN_COVERAGE = TUNE_MIN_COVERAGE


def _combo_grid_candidates() -> list[PredictTuneConfig]:
    """Weight/threshold grid for triple_combo and sentiment_momentum variants."""
    out: list[PredictTuneConfig] = []
    triple_weights = (
        (0.25, 0.4, 0.35),
        (0.35, 0.35, 0.3),
        (0.4, 0.3, 0.3),
        (0.3, 0.45, 0.25),
        (0.2, 0.4, 0.4),
    )
    for sw, mw, cw in triple_weights:
        for mom_th in (-0.01, 0.01):
            for mode, mv in (("vote", 2), ("vote", 1)):
                name = f"g_triple_sw{sw}_mw{mw}_cw{cw}_m{mom_th}_{mode}{mv}"
                out.append(
                    PredictTuneConfig(
                        name=name,
                        strategy=STRATEGY_TRIPLE_COMBO,
                        sentiment_weight=sw,
                        momentum_weight=mw,
                        cot_weight=cw,
                        momentum_threshold=mom_th,
                        cot_threshold=-0.1,
                        combo_mode=mode,
                        min_votes=mv,
                    )
                )
    for allow_fill in (True, False):
        for mom_th in (-0.01, 0.02):
            name = f"g_sm_fill{int(allow_fill)}_m{mom_th}"
            out.append(
                PredictTuneConfig(
                    name=name,
                    strategy=STRATEGY_SENTIMENT_MOMENTUM,
                    sentiment_weight=0.45,
                    momentum_weight=0.55,
                    sentiment_threshold=0.0,
                    momentum_threshold=mom_th,
                    allow_momentum_without_news=allow_fill,
                    combo_mode="vote",
                    min_votes=1 if allow_fill else 2,
                )
            )
    for mom_th in (-0.02, 0.0, 0.02):
        for cot_th in (-0.2, 0.0):
            name = f"g_cm_m{mom_th}_c{cot_th}"
            out.append(
                PredictTuneConfig(
                    name=name,
                    strategy=STRATEGY_COT_MOMENTUM,
                    momentum_weight=0.5,
                    cot_weight=0.5,
                    momentum_threshold=mom_th,
                    cot_threshold=cot_th,
                    combo_mode="vote",
                    min_votes=1,
                )
            )
    return out


def expand_tune_candidates() -> tuple[PredictTuneConfig, ...]:
    """Baseline + multi-signal strategies + knob grid over news_ridge params."""
    by_name: dict[str, PredictTuneConfig] = {c.name: c for c in TUNE_CANDIDATES}
    for c in _combo_grid_candidates():
        by_name.setdefault(c.name, c)
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
    ordered = list(TUNE_CANDIDATES)
    ordered.extend(
        c for n, c in sorted(by_name.items()) if n not in {x.name for x in TUNE_CANDIDATES}
    )
    return tuple(ordered)


def expand_rsi_candidates() -> tuple[PredictTuneConfig, ...]:
    return expand_tune_candidates()


def save_predict_config(run_dir: Path, config: PredictTuneConfig) -> Path:
    path = run_dir / "models" / "predict_config.json"
    path.write_text(json.dumps(config.to_dict(), indent=2) + "\n")
    return path


def load_predict_config(run_dir: Path) -> PredictTuneConfig:
    path = run_dir / "models" / "predict_config.json"
    if not path.exists():
        return DEFAULT_CONFIG
    data = json.loads(path.read_text())
    # Backward compat: ignore unknown keys from older configs
    fields = {f.name for f in PredictTuneConfig.__dataclass_fields__.values()}
    filtered = {k: v for k, v in data.items() if k in fields}
    return PredictTuneConfig(**filtered)
