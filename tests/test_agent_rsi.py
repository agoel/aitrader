import json
from pathlib import Path

from aitrader.agent_rsi import log_agent_rsi, probe_backtest_performance, seed_session_improvements
from aitrader.workspace import ensure_run_layout


def test_log_agent_rsi_writes_manifest(tmp_path: Path) -> None:
    path = log_agent_rsi(
        tmp_path,
        "test_topic",
        symptom="slow loop",
        fix="parallelize",
        verify="probe under 60s",
    )
    assert path.exists()
    manifest = json.loads((tmp_path / "agent_rsi" / "manifest.json").read_text())
    assert len(manifest) == 1
    assert manifest[0]["topic"] == "test_topic"


def test_seed_session_improvements_idempotent(tmp_path: Path) -> None:
    ensure_run_layout(tmp_path)
    first = seed_session_improvements(tmp_path)
    second = seed_session_improvements(tmp_path)
    assert len(first) >= 1
    assert second == []


def test_probe_backtest_performance_on_minimal_run(tmp_path: Path) -> None:
    ensure_run_layout(tmp_path)
    report = probe_backtest_performance(tmp_path, quiet=True)
    assert "probe_sec" in report
    assert (tmp_path / "agent_rsi").is_dir()
