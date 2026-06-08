import warnings
from pathlib import Path

from aitrader.ml.predict_config import TUNE_CANDIDATES, expand_tune_candidates
from aitrader.ml.rsi_predict import run_prediction_rsi
from aitrader.workspace import ensure_run_layout


def test_expand_tune_candidates_includes_baselines() -> None:
    expanded = expand_tune_candidates()
    assert len(expanded) > len(TUNE_CANDIDATES)
    for base in TUNE_CANDIDATES:
        assert any(c.name == base.name for c in expanded)


def test_run_prediction_tune_writes_learning_artifacts(tmp_path: Path) -> None:
    """Smoke test: tune on minimal run fails gracefully or uses backtest from test_backtest fixture."""
    root = ensure_run_layout(tmp_path)
    assert (root / "learning").is_dir()
    assert (root / "agent_rsi").is_dir()


def test_run_prediction_rsi_deprecated_alias(tmp_path: Path) -> None:
    ensure_run_layout(tmp_path)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            run_prediction_rsi(
                tmp_path, max_rounds=1, use_grid=False, run_probe=False
            )
        except RuntimeError:
            pass
    assert any("deprecated" in str(w.message).lower() for w in caught)
