import json
from unittest.mock import patch

from aitrader.nlp.keyword_cache import keywords_for_article, normalize_keywords, phrase_grounded
from aitrader.nlp.llm_extract import build_batch_prompt, extract_llm_keywords_batch


def test_phrase_grounded() -> None:
    assert phrase_grounded("rate cut", "Fed signals rate cut", "")
    assert not phrase_grounded("quantum foam", "Apple launches new iPhone", "")


def test_normalize_llm_keywords() -> None:
    raw = [
        {"phrase": "rate cut", "type": "macro"},
        {"phrase": "quantum foam", "type": "sector"},
        "earnings guidance",
    ]
    out = normalize_keywords(raw, "Fed rate cut and earnings guidance", "")
    assert "rate cut" in out
    assert "earnings guidance" in out
    assert "quantum foam" not in out


def test_build_batch_prompt_includes_sector() -> None:
    prompt = build_batch_prompt(
        [{"id": "a1", "title": "Test", "body": "Body", "sector_id": "technology", "tickers": ["AAPL"]}]
    )
    assert "technology" in prompt
    assert "a1" in prompt


@patch("aitrader.nlp.llm_extract._openai_chat_json")
def test_extract_llm_keywords_batch(mock_chat) -> None:
    mock_chat.return_value = {
        "articles": [
            {
                "id": "n1",
                "keywords": [{"phrase": "AI chips", "type": "sector"}],
            }
        ]
    }
    articles = [
        {
            "id": "n1",
            "title": "NVIDIA unveils AI chips",
            "body": "New AI chips for datacenters.",
            "sector_id": "technology",
            "tickers": ["NVDA"],
        }
    ]
    out = extract_llm_keywords_batch(articles, model="gpt-4o-mini", api_key="test-key")
    assert out["n1"] == ["AI chips"]


def test_keywords_for_article_cache() -> None:
    art = {"id": "x", "title": "t", "body": "b"}
    cache = {"x": {"id": "x", "keywords": ["fed rates"]}}
    assert keywords_for_article(art, cache) == ["fed rates"]
