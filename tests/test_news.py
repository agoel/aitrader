import json
from unittest.mock import patch

from aitrader.nlp.news import NewsArticle, dedupe_articles, write_news_jsonl


def test_dedupe_articles() -> None:
    a = NewsArticle(
        id="abc",
        published_at="2026-06-01T12:00:00Z",
        title="Fed holds rates",
        body="The Federal Reserve kept rates unchanged.",
        source="fed",
        tags=["macro"],
    )
    dup = NewsArticle(
        id="abc",
        published_at="2026-06-01T12:00:00Z",
        title="Fed holds rates",
        body="duplicate",
        source="fed",
    )
    out = dedupe_articles([a, dup])
    assert len(out) == 1


def test_write_news_jsonl(tmp_path) -> None:
    art = NewsArticle(
        id="x1",
        published_at="2026-06-01T12:00:00Z",
        title="Inflation cools",
        body="CPI rose less than expected.",
        source="bls",
        tags=["inflation"],
        sector_id="macro",
    )
    path = write_news_jsonl(tmp_path, [art], date="2026-06-01")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[0]["title"] == "Inflation cools"
    assert set(rows[0].keys()) >= {"id", "published_at", "title", "body", "source", "tags"}


@patch("aitrader.nlp.news.fetch_rss_feed")
@patch("aitrader.nlp.news.fetch_yahoo_news")
def test_ingest_news(mock_yahoo, mock_rss, tmp_path) -> None:
    from aitrader.nlp.news import ingest_news

    mock_rss.return_value = [
        NewsArticle(
            id="r1",
            published_at="2026-06-05T10:00:00Z",
            title="Treasury yields fall",
            body="Bond market rally on rate cut hopes.",
            source="fed",
            sector_id="macro",
        )
    ]
    mock_yahoo.return_value = []
    path, count = ingest_news(tmp_path, sources=["rss"], yahoo_tickers=[])
    assert count == 1
    assert path.exists()
