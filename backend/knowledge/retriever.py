"""Keyword retriever over the shared chunk pool.

v1 scoring: keyword-overlap ratio + topic-match boost + source boost
(center-specific preferred over ``_generic/``, a chunk with zero keyword
overlap never scores above zero regardless of boosts). Operates on
``loader.get_chunks()`` so both markdown handbook entries and
ingested-PDF chunks participate in a single ranking.

A v2 could swap this for TF-IDF/embeddings without changing the call-sites
— the public contract is just ``retrieve(query, topic, top_k)``.
"""
import re
from dataclasses import dataclass

from backend.knowledge.loader import Chunk, get_chunks


@dataclass
class RetrievalResult:
    chunk: Chunk
    score: float


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _compute_score(query_tokens: set[str], chunk: Chunk, topic: str | None) -> float:
    """Score a chunk against a query using keyword overlap + topic boost."""
    chunk_text = f"{chunk.heading} {chunk.content}"
    chunk_tokens = set(_tokenize(chunk_text))

    if not chunk_tokens or not query_tokens:
        return 0.0

    overlap = len(query_tokens & chunk_tokens)
    keyword_score = overlap / len(query_tokens)

    topic_boost = 0.0
    if topic and chunk.category == topic:
        topic_boost = 0.3

    if keyword_score == 0:
        return 0.0

    source_boost = -0.2 if chunk.source.startswith("_generic/") else 0.1

    return keyword_score + topic_boost + source_boost


def retrieve(
    query: str, topic: str | None = None, top_k: int = 5
) -> list[RetrievalResult]:
    """Retrieve the most relevant handbook chunks for a query.

    Returns chunks sorted by relevance score. Center-specific content
    is preferred over generic content via a scoring penalty.
    """
    chunks = get_chunks()
    if not chunks:
        return []

    query_tokens = set(_tokenize(query))
    scored = []

    for chunk in chunks:
        score = _compute_score(query_tokens, chunk, topic)
        if score > 0:
            scored.append(RetrievalResult(chunk=chunk, score=score))

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_k]
