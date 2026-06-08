import json
from unittest.mock import patch

from aitrader.nlp.gdelt import (
    _gdelt_article_from_row,
    _parse_seendate,
    fetch_gdelt_artlist,
    ingest_gdelt_historical,
)
from aitrader.workspace import ensure_run_layout


def test_parse_seendate() -> None:
    assert _parse_seendate("20240608T153000Z") == "2024-06-08T15:30:00Z"


def test_gdelt_article_from_row() -> None:
    art = _gdelt_article_from_row(
        {
            "title": "Fed holds rates steady",
            "seendate": "20240601T120000Z",
            "domain": "reuters.com",
            "url": "https://example.com/fed",
        },
        query_id="fed_rates",
        tags=["fed"],
    )
    assert art.title == "Fed holds rates steady"
    assert art.published_at == "2024-06-01T12:00:00Z"
    assert "fed" in art.tags
    assert art.sector_id == "macro"


def test_fetch_gdelt_artlist_parses_json() -> None:
    payload = json.dumps(
        {
            "articles": [
                {
                    "title": "Inflation cools",
                    "seendate": "20240501T100000Z",
                    "domain": "cnbc.com",
                    "url": "https://example.com/cpi",
                }
            ]
        }
    ).encode()

    class FakeResp:
        def read(self) -> bytes:
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        rows = fetch_gdelt_artlist("inflation", sleep_s=0)
    assert len(rows) == 1
    assert rows[0]["title"] == "Inflation cools"


def test_ingest_gdelt_historical_appends_corpus(tmp_path) -> None:
    root = ensure_run_layout(tmp_path)
    payload = json.dumps(
        {
            "articles": [
                {
                    "title": "Jobs report beats",
                    "seendate": "20240315T140000Z",
                    "domain": "bls.gov",
                    "url": "https://example.com/jobs",
                }
            ]
        }
    ).encode()

    class FakeResp:
        def read(self) -> bytes:
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        path, count = ingest_gdelt_historical(root, timespan="30days")
    assert count >= 1
    corpus = (root / "data" / "news" / "corpus.jsonl").read_text()
    assert "Jobs report beats" in corpus
    assert path.exists()
