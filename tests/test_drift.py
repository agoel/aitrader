import json
from pathlib import Path

from aitrader.ml.drift import _drift_score, filter_corpus_by_age, run_drift_detection
from aitrader.workspace import ensure_run_layout


def test_drift_score() -> None:
    assert _drift_score(0.2, 0.1) == 0.5
    assert _drift_score(0.0, 0.0) == 0.0


def test_filter_corpus_by_age() -> None:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=100)).strftime("%Y-%m-%dT12:00:00Z")
    recent = (now - timedelta(days=5)).strftime("%Y-%m-%dT12:00:00Z")
    corpus = [
        {"published_at": old, "title": "old"},
        {"published_at": recent, "title": "new"},
    ]
    recent_only = filter_corpus_by_age(corpus, max_age_days=30)
    assert len(recent_only) == 1


def test_run_drift_detection(tmp_path: Path) -> None:
    root = ensure_run_layout(tmp_path)
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "sectors.yaml").write_text(
        "sectors:\n  - id: technology\n    name: Technology\n    etf_proxy: XLK\n"
    )
    (root / "models").mkdir(exist_ok=True)
    (root / "models" / "keyword_map_technology.json").write_text(
        json.dumps([{"keyword": "fed", "ic": 0.1, "direction": "bullish"}])
    )
    (root / "models" / "keyword_map_anchor.json").write_text("[]")
    (root / "data" / "news").mkdir(parents=True, exist_ok=True)
    (root / "data" / "news" / "corpus.jsonl").write_text("")

    report, refresh = run_drift_detection(
        tmp_path,
        require_consecutive=False,
    )
    assert report.exists()
    assert isinstance(refresh, bool)
    meta = json.loads((root / "meta.json").read_text())
    assert "drift" in meta
