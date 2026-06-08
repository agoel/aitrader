from pathlib import Path

from aitrader.workspace import ensure_run_layout, update_meta


def test_ensure_run_layout(tmp_path: Path) -> None:
    root = ensure_run_layout(tmp_path)
    for sub in (
        "config",
        "data",
        "data/ohlcv",
        "models",
        "reports",
        "agent_rsi",
        "learning",
        "rsi",
    ):
        assert (root / sub).is_dir()


def test_update_meta(tmp_path: Path) -> None:
    update_meta(tmp_path, {"capital_usd": 10000})
    meta = (tmp_path / "meta.json").read_text()
    assert "10000" in meta
