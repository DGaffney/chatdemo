"""Override-first retrieval wrapper.

Enforces the knowledge precedence rule: if an operator override matches the
question (via :func:`backend.db.overrides.find_override`), its answer is
returned as a synthetic top-ranked ``Chunk`` with score 2.0, above anything
the handbook retriever could produce. Handbook results still come through
as the tail so the LLM has fallback context, but in practice the graph's
retrieve node will pick the override first.
"""
from backend.db.overrides import find_override as db_find_override
from backend.knowledge.retriever import retrieve, RetrievalResult
from backend.knowledge.loader import Chunk


async def retrieve_with_overrides(
    query: str, topic: str | None = None, top_k: int = 5
) -> tuple[list[RetrievalResult], dict | None]:
    """Check operator overrides first, then fall back to handbook retrieval.

    Returns (retrieval_results, override_or_none).
    If an override is found, it's returned as the second element and also
    prepended to the retrieval results as a synthetic chunk.
    """
    override = await db_find_override(query, topic)

    results = retrieve(query, topic, top_k)

    if override:
        override_chunk = Chunk(
            content=override["answer"],
            source="operator_override",
            category=override.get("topic", "other"),
            heading=f"Operator Answer: {override['question_pattern']}",
        )
        override_result = RetrievalResult(chunk=override_chunk, score=2.0)
        results = [override_result] + results

    return results, override
