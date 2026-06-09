from aitrader.nlp.stoplist import filter_coef_map, filter_keywords, is_stoplisted


def test_stoplist_rejects_anchor_junk() -> None:
    for junk in ("what the", "advisors llc", "capital llc", "the best"):
        assert is_stoplisted(junk)


def test_stoplist_allows_macro_phrases() -> None:
    assert not is_stoplisted("rate cut")
    assert not is_stoplisted("federal reserve")


def test_filter_keywords_drops_junk() -> None:
    out = filter_keywords(["rate cut", "what the", "inflation", "advisors llc"])
    assert out == ["rate cut", "inflation"]


def test_filter_coef_map() -> None:
    raw = {"rate cut": 0.01, "what the": -0.01, "inflation": 0.02}
    assert filter_coef_map(raw) == {"rate cut": 0.01, "inflation": 0.02}
