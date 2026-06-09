from aitrader.nlp.sentiment import (
    SentimentScorer,
    article_text,
    resolve_backend,
    vader_score,
)


def test_vader_score_sign() -> None:
    pos = vader_score("Markets rally on strong earnings and rate cut hopes")
    neg = vader_score("Recession fears spike as unemployment surges")
    assert pos > neg


def test_article_text_truncates() -> None:
    art = {"title": "Fed holds", "body": "x" * 1000}
    assert len(article_text(art, max_chars=100)) <= 100


def test_scorer_vader_backend() -> None:
    scorer = SentimentScorer(backend="vader", run_dir=None)
    art = {"id": "t1", "title": "Stocks rise", "body": "Bullish macro backdrop"}
    primary, shadow = scorer.score_article(art)
    assert primary == shadow


def test_resolve_backend_env(monkeypatch) -> None:
    monkeypatch.setenv("AITRADER_SENTIMENT", "blend")
    assert resolve_backend() == "blend"
