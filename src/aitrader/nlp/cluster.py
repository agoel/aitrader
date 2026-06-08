"""News clustering — Recipe — Macro news ingest and clustering (cluster slice)."""

from __future__ import annotations

import json
import pickle
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from aitrader.nlp.keywords import (
    HORIZON_TRADING_DAYS,
    _labels_from_corpus,
    load_sector_etfs,
)
from aitrader.nlp.news import load_corpus
from aitrader.workspace import ensure_run_layout

EMBED_MODEL_LOCAL = "tfidf-local"


def _article_text(row: dict[str, Any]) -> str:
    return f"{row.get('title', '')} {row.get('body', '')}".strip()


def _filter_window(corpus: list[dict[str, Any]], window_days: int) -> list[dict[str, Any]]:
    from aitrader.ml.drift import filter_corpus_by_age

    return filter_corpus_by_age(corpus, max_age_days=window_days)


def _top_terms_per_cluster(
    vectorizer: TfidfVectorizer,
    km: KMeans,
    X,
    top_n: int = 8,
) -> dict[int, list[str]]:
    terms = np.array(vectorizer.get_feature_names_out())
    tops: dict[int, list[str]] = {}
    for cid in range(km.n_clusters):
        idx = np.where(km.labels_ == cid)[0]
        if len(idx) == 0:
            tops[cid] = []
            continue
        centroid = X[idx].mean(axis=0).A1
        top_idx = centroid.argsort()[-top_n:][::-1]
        tops[cid] = [str(terms[i]) for i in top_idx if centroid[i] > 0]
    return tops


def _sector_return_profiles(
    run_dir: Path,
    corpus: list[dict[str, Any]],
    cluster_ids: list[int],
    *,
    horizon_days: int,
) -> dict[int, dict[str, float]]:
    sector_etfs = load_sector_etfs(run_dir)
    profiles: dict[int, dict[str, float]] = defaultdict(dict)
    by_cluster: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row, cid in zip(corpus, cluster_ids):
        by_cluster[cid].append(row)

    for cid, articles in by_cluster.items():
        for sector_id, etf in sector_etfs.items():
            labels = _labels_from_corpus(
                articles, sector_id, run_dir, etf, horizon_days, include_macro=True
            )
            if labels:
                profiles[cid][sector_id] = round(
                    sum(a.forward_return for a in labels) / len(labels), 4
                )
    return dict(profiles)


def fit_news_clusters(
    run_dir: str | Path,
    *,
    news_window_days: int = 7,
    cluster_k: int = 12,
    label_horizon: str = "1m",
) -> tuple[Path, Path, Path]:
    root = ensure_run_layout(run_dir)
    corpus = load_corpus(root)
    horizon_days = HORIZON_TRADING_DAYS.get(label_horizon, 21)

    fit_corpus = corpus if len(corpus) >= 30 else corpus
    window_corpus = _filter_window(fit_corpus, news_window_days)
    if len(window_corpus) < 10:
        window_corpus = fit_corpus[: max(10, len(fit_corpus))]

    texts = [_article_text(r) for r in fit_corpus]
    vectorizer = TfidfVectorizer(
        max_features=4000,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,
    )
    X = vectorizer.fit_transform(texts)
    k = min(cluster_k, max(2, X.shape[0] // 5))
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    km.fit(X)

    cluster_terms = _top_terms_per_cluster(vectorizer, km, X)
    profiles = _sector_return_profiles(
        root, fit_corpus, list(km.labels_), horizon_days=horizon_days
    )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    model_payload = {
        "embed_model": EMBED_MODEL_LOCAL,
        "vectorizer": vectorizer,
        "kmeans": km,
        "cluster_terms": cluster_terms,
        "sector_profiles": profiles,
        "fit_corpus_size": len(fit_corpus),
        "fit_date": today,
    }
    model_path = root / "models" / "news_clusters.pkl"
    with model_path.open("wb") as fh:
        pickle.dump(model_payload, fh)

    recent_texts = [_article_text(r) for r in window_corpus]
    recent_X = vectorizer.transform(recent_texts)
    recent_ids = km.predict(recent_X)
    counts = Counter(int(c) for c in recent_ids)
    dominant = counts.most_common(1)[0][0] if counts else 0

    current = {
        "date": today,
        "window_days": news_window_days,
        "articles_in_window": len(window_corpus),
        "dominant_cluster_id": int(dominant),
        "cluster_counts": {str(k): v for k, v in counts.items()},
        "top_terms": cluster_terms.get(dominant, []),
        "sector_return_profile": profiles.get(dominant, {}),
    }
    current_path = root / "models" / "current_cluster.json"
    current_path.write_text(json.dumps(current, indent=2) + "\n")

    report_path = root / "reports" / f"news_cluster_{today}.md"
    lines = [
        f"# News cluster report — {today}",
        "",
        f"- **Articles in window:** {len(window_corpus)}",
        f"- **Clusters fit:** {k}",
        f"- **Dominant cluster:** {dominant}",
        "",
        "## Cluster terms",
    ]
    for cid in sorted(cluster_terms.keys()):
        lines.append(f"### Cluster {cid}")
        lines.append("- " + ", ".join(cluster_terms[cid][:8]) if cluster_terms[cid] else "- *(empty)*")
        prof = profiles.get(cid, {})
        if prof:
            top_sectors = sorted(prof.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
            lines.append(
                "- Sector returns: "
                + ", ".join(f"{s} {r:+.2%}" if abs(r) < 1 else f"{s} {r:+.4f}" for s, r in top_sectors)
            )
        lines.append("")

    report_path.write_text("\n".join(lines) + "\n")
    return model_path, current_path, report_path
