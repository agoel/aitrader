"""Phase 3 — finance-aware sentiment (FinBERT + VADER shadow)."""

from __future__ import annotations

import json
import os
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from aitrader.workspace import ensure_run_layout, update_meta

SentimentBackend = Literal["vader", "finbert", "blend"]
DEFAULT_BACKEND: SentimentBackend = "finbert"
BLEND_VADER_WEIGHT = 0.35  # FinBERT-primary blend when backend=blend

IndexTag = Literal["SPX", "RUT"]

INDEX_TEXT_TAGS: dict[IndexTag, tuple[str, ...]] = {
    "SPX": ("spy", "spx", "s&p", "s and p", "500", "large cap"),
    "RUT": ("iwm", "rut", "russell", "small cap", "russell 2000"),
}

_pipe: Any = None
_vader_analyzer: Any = None


def finbert_available() -> bool:
    try:
        import transformers  # noqa: F401

        return True
    except ImportError:
        return False


def _load_finbert_pipeline():
    global _pipe
    if _pipe is not None:
        return _pipe
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from transformers import pipeline

    _pipe = pipeline(
        "sentiment-analysis",
        model="ProsusAI/finbert",
        tokenizer="ProsusAI/finbert",
        truncation=True,
        max_length=512,
        device=-1,
    )
    return _pipe


def _vader_analyzer_instance():
    global _vader_analyzer
    if _vader_analyzer is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        _vader_analyzer = SentimentIntensityAnalyzer()
    return _vader_analyzer


def vader_score(text: str) -> float:
    try:
        return float(_vader_analyzer_instance().polarity_scores(text)["compound"])
    except Exception:
        return 0.0


def finbert_score(text: str, *, pipe: Any = None) -> float:
    text = (text or "")[:512]
    if len(text) < 20:
        return 0.0
    p = pipe or _load_finbert_pipeline()
    r = p(text)[0]
    lab = str(r["label"]).lower()
    s = float(r["score"])
    if lab == "positive":
        return s
    if lab == "negative":
        return -s
    return 0.0


def article_text(article: dict[str, Any], *, max_chars: int = 512) -> str:
    title = article.get("title") or ""
    body = (article.get("body") or "")[: max_chars - len(title) - 1]
    return f"{title} {body}".strip()[:max_chars]


def resolve_backend(
    run_dir: str | Path | None = None,
    *,
    override: SentimentBackend | None = None,
) -> SentimentBackend:
    if override:
        return override
    env = os.environ.get("AITRADER_SENTIMENT", "").lower()
    if env in ("vader", "finbert", "blend"):
        return env  # type: ignore[return-value]
    if run_dir is not None:
        meta_path = Path(run_dir).expanduser() / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            b = (meta.get("sentiment") or {}).get("backend", "").lower()
            if b in ("vader", "finbert", "blend"):
                return b  # type: ignore[return-value]
    if finbert_available():
        return DEFAULT_BACKEND
    return "vader"


def _cache_path(run_dir: Path) -> Path:
    return run_dir / "data" / "news" / "finbert_sentiment.jsonl"


def load_finbert_disk_cache(run_dir: str | Path) -> dict[str, float]:
    """Article-id → FinBERT score (for fast training without re-inference)."""
    return _load_disk_cache(Path(run_dir).expanduser())


def _load_disk_cache(run_dir: Path) -> dict[str, float]:
    path = _cache_path(run_dir)
    cache: dict[str, float] = {}
    if not path.exists():
        return cache
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            cache[row["id"]] = float(row["score"])
    return cache


def _append_disk_cache(run_dir: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path = _cache_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _macro_keyword_hit(text: str, llm_cache: dict[str, dict[str, Any]] | None, article: dict[str, Any]) -> bool:
    from aitrader.nlp.keyword_cache import keywords_for_article
    from aitrader.nlp.keywords import MACRO_SEEDS

    kws = keywords_for_article(article, llm_cache)
    if kws:
        blob = " ".join(kws).lower()
        if any(s in blob for s in MACRO_SEEDS) or any(k.lower() in MACRO_SEEDS for k in kws):
            return True
    text_l = text.lower()
    return any(re.search(rf"\b{re.escape(seed)}\b", text_l) for seed in MACRO_SEEDS)


def _index_text_hit(text: str, index: IndexTag) -> bool:
    text_l = text.lower()
    return any(tag in text_l for tag in INDEX_TEXT_TAGS[index])


def filter_macro_articles(
    articles: list[dict[str, Any]],
    llm_cache: dict[str, dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Articles with macro seed keywords (proxy benchmark A1 gate)."""
    out: list[dict[str, Any]] = []
    for art in articles:
        text = article_text(art)
        if (art.get("sector_id") or "macro") == "macro" or _macro_keyword_hit(text, llm_cache, art):
            out.append(art)
    return out


def filter_index_articles(
    articles: list[dict[str, Any]],
    index: IndexTag,
    llm_cache: dict[str, dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Ticker-tagged proxy: SPX/SPY or RUT/IWM mentions in text, tickers, or keywords."""
    from aitrader.nlp.keyword_cache import keywords_for_article

    etf = "SPY" if index == "SPX" else "IWM"
    out: list[dict[str, Any]] = []
    for art in articles:
        text = article_text(art, max_chars=800)
        tickers = [t.upper() for t in (art.get("tickers") or []) if t]
        if etf in tickers or _index_text_hit(text, index):
            out.append(art)
            continue
        kws = keywords_for_article(art, llm_cache) or []
        if any(_index_text_hit(k, index) for k in kws):
            out.append(art)
    return out


@dataclass
class SentimentScorer:
    backend: SentimentBackend
    run_dir: Path | None
    _finbert_pipe: Any = None
    _disk: dict[str, float] | None = None
    _pending_writes: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if self.backend in ("finbert", "blend") and not finbert_available():
            self.backend = "vader"
        if self.run_dir and self.backend in ("finbert", "blend"):
            self._disk = _load_disk_cache(self.run_dir)
            self._pending_writes = []

    def flush_cache(self) -> None:
        if self.run_dir and self._pending_writes:
            _append_disk_cache(self.run_dir, self._pending_writes)
            self._pending_writes.clear()

    def score_article(self, article: dict[str, Any]) -> tuple[float, float]:
        """Return (primary_sentiment, vader_shadow)."""
        text = article_text(article)
        v = vader_score(text)
        art_id = str(article.get("id", ""))

        if self.backend == "vader":
            return v, v

        fb: float | None = None
        if self._disk is not None and art_id and art_id in self._disk:
            fb = self._disk[art_id]
        elif self.backend in ("finbert", "blend"):
            if self._finbert_pipe is None:
                self._finbert_pipe = _load_finbert_pipeline()
            fb = finbert_score(text, pipe=self._finbert_pipe)
            if art_id and self._disk is not None and self._pending_writes is not None:
                self._disk[art_id] = fb
                self._pending_writes.append({"id": art_id, "score": fb})

        if self.backend == "finbert":
            return float(fb or 0.0), v
        # blend
        primary = (1.0 - BLEND_VADER_WEIGHT) * float(fb or 0.0) + BLEND_VADER_WEIGHT * v
        return primary, v

    def mean_for_articles(
        self,
        articles: list[dict[str, Any]],
        llm_cache: dict[str, dict[str, Any]] | None,
        *,
        max_articles: int | None = None,
        require_keywords: bool = True,
    ) -> tuple[float, float]:
        from aitrader.nlp.keyword_cache import keywords_for_article

        if max_articles and len(articles) > max_articles:
            articles = sorted(articles, key=lambda a: a.get("published_at", ""))[-max_articles:]
        primary: list[float] = []
        vader: list[float] = []
        for art in articles:
            if require_keywords and not keywords_for_article(art, llm_cache):
                continue
            p, v = self.score_article(art)
            primary.append(p)
            vader.append(v)
        self.flush_cache()
        if not primary:
            return 0.0, 0.0
        return (
            sum(primary) / len(primary),
            sum(vader) / len(vader),
        )

    def macro_mean(
        self,
        articles: list[dict[str, Any]],
        llm_cache: dict[str, dict[str, Any]] | None,
        *,
        max_articles: int | None = None,
    ) -> tuple[float, float]:
        """FinBERT/VADER mean on macro-filtered articles only."""
        macro = filter_macro_articles(articles, llm_cache)
        return self.mean_for_articles(macro, llm_cache, max_articles=max_articles, require_keywords=False)

    def index_macro_mean(
        self,
        articles: list[dict[str, Any]],
        index: IndexTag,
        llm_cache: dict[str, dict[str, Any]] | None,
    ) -> tuple[float, float]:
        """Macro + index-tagged article sentiment."""
        macro = filter_macro_articles(articles, llm_cache)
        tagged = filter_index_articles(macro, index, llm_cache)
        pool = tagged if tagged else macro
        return self.mean_for_articles(pool, llm_cache, require_keywords=False)


def get_sentiment_scorer(
    run_dir: str | Path | None = None,
    *,
    backend: SentimentBackend | None = None,
) -> SentimentScorer:
    root = ensure_run_layout(run_dir) if run_dir else None
    resolved = resolve_backend(root, override=backend)
    return SentimentScorer(backend=resolved, run_dir=root)


def set_sentiment_backend(run_dir: str | Path, backend: SentimentBackend) -> None:
    root = ensure_run_layout(run_dir)
    update_meta(root, {"sentiment": {"backend": backend}})


def score_text(
    text: str,
    *,
    backend: SentimentBackend | None = None,
    run_dir: str | Path | None = None,
) -> tuple[float, float]:
    """Score raw text; returns (primary, vader)."""
    art = {"id": "", "title": text, "body": ""}
    scorer = get_sentiment_scorer(run_dir, backend=backend)
    return scorer.score_article(art)
