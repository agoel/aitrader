import json
from pathlib import Path

from aitrader.nlp.cursor_extract import fill_pending_keywords, suggest_macro_keywords
from aitrader.nlp.parallel import default_workers, parallel_map
from aitrader.workspace import ensure_run_layout


def _double(x: int) -> int:
    return x * 2


def test_parallel_map() -> None:
    out = parallel_map(_double, range(20), workers=4)
    assert out == [i * 2 for i in range(20)]


def test_default_workers() -> None:
    assert default_workers(4) == 4
    assert default_workers(None) >= 1


def test_fill_pending_keywords_parallel(tmp_path: Path) -> None:
    root = ensure_run_layout(tmp_path)
    lines = []
    for i in range(40):
        lines.append(
            json.dumps(
                {
                    "id": f"a{i}",
                    "published_at": "2024-06-01T10:00:00Z",
                    "title": "Fed raises rates on inflation fears",
                    "body": "Federal reserve inflation earnings outlook",
                    "source": "test",
                    "tags": [],
                    "tickers": [],
                    "sector_id": "macro",
                }
            )
        )
    (root / "data" / "news").mkdir(parents=True, exist_ok=True)
    (root / "data" / "news" / "corpus.jsonl").write_text("\n".join(lines) + "\n")
    n, path = fill_pending_keywords(root, workers=4)
    assert n == 40
    assert path.exists()
    cached = path.read_text().strip().splitlines()
    assert len(cached) == 40
    row = json.loads(cached[0])
    assert row["keywords"]


def test_suggest_macro_keywords_returns_strings() -> None:
    art = {
        "title": "Fed holds rates steady as inflation cools",
        "body": "Federal reserve inflation earnings",
        "tickers": [],
        "sector_id": "macro",
    }
    kws = suggest_macro_keywords(art)
    assert kws
    assert all(isinstance(k, dict) and "phrase" in k for k in kws)
