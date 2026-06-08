import json
from pathlib import Path

from aitrader.progress import RunProgress, pipeline_phase, status_path
from aitrader.workspace import ensure_run_layout


def test_run_progress_writes_status(tmp_path: Path) -> None:
    root = ensure_run_layout(tmp_path)
    prog = RunProgress(
        "test-phase",
        10,
        run_dir=root,
        pipeline="test.pipeline",
        phase="unit",
        quiet=True,
    )
    prog.start()
    prog.advance(5)
    prog.finish()
    data = json.loads(status_path(root).read_text())
    assert data["pipeline"] == "test.pipeline"
    assert data["items_done"] == 10
    assert data["status"] == "done"


def test_pipeline_phase_context(tmp_path: Path) -> None:
    root = ensure_run_layout(tmp_path)
    with pipeline_phase(root, "test", "step_a", 1, 2, quiet=True):
        pass
    data = json.loads(status_path(root).read_text())
    assert data["phase"] == "step_a"
    assert data["status"] == "done"
