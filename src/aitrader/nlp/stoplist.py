"""Phase 1 keyword hygiene — junk phrase filter for extract, discover, and scoring."""

from __future__ import annotations

import re

# Junk from anchor-map audit + proxy benchmark A3 (Phase 0)
KEYWORD_STOPLIST: frozenset[str] = frozenset(
    {
        "what the",
        "are the",
        "llc has",
        "from the",
        "source iedfolrf0000001",
        "llc sells",
        "capital llc",
        "things know",
        "the best",
        "with the",
        "advisors llc",
    }
)

_FILLER_WORDS = frozenset(
    """
    what the are with from for how this that best things know more while when where
    which who whom whose why will would could should has have had been being does did
    """.split()
)

_JUNK_SUFFIXES = (" llc", " has", " sells", " inc", " corp")


def is_stoplisted(phrase: str) -> bool:
    """True if phrase should never enter keyword maps or scores."""
    p = re.sub(r"\s+", " ", phrase.strip().lower())
    if not p or len(p) < 3:
        return True
    if p in KEYWORD_STOPLIST:
        return True
    if any(p.endswith(s) for s in _JUNK_SUFFIXES):
        return True
    words = [w for w in p.split() if w]
    if len(words) == 2 and words[0] in _FILLER_WORDS and words[1] in _FILLER_WORDS:
        return True
    return False


def filter_keywords(phrases: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        p = phrase.strip()
        if not p or p.lower() in seen or is_stoplisted(p):
            continue
        seen.add(p.lower())
        out.append(p)
    return out


def filter_coef_map(coef_map: dict[str, float]) -> dict[str, float]:
    return {k: v for k, v in coef_map.items() if not is_stoplisted(k)}
