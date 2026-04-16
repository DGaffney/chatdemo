"""Knowledge retrieval node.

Delegates to :func:`backend.knowledge.overrides.retrieve_with_overrides`
which checks operator overrides before the shared chunk pool (markdown
handbook + ingested PDFs). Concatenates the top-k chunks into a single
``retrieved_context`` string for the answer prompt and records the set of
citation sources in ``policy_cited``. An override hit bumps confidence to
0.95 so the post-call guardrail won't auto-escalate a known-good answer.
"""
from langsmith import traceable

from backend.graph.state import GraphState
from backend.knowledge.overrides import retrieve_with_overrides


@traceable(run_type="retriever", name="retrieve_knowledge")
async def retrieve_knowledge(state: GraphState) -> GraphState:
    results, override = await retrieve_with_overrides(
        state["question"], state.get("topic"), top_k=5
    )

    override_used = bool(override)
    confidence = state.get("confidence", 0.5)
    if override_used:
        confidence = max(confidence, 0.95)

    context_parts = []
    sources = []
    for r in results:
        context_parts.append(f"### {r.chunk.heading}\n{r.chunk.content}")
        if r.chunk.source not in sources:
            sources.append(r.chunk.source)

    return {
        **state,
        "retrieved_context": "\n\n---\n\n".join(context_parts),
        "policy_cited": ", ".join(sources),
        "override_used": override_used,
        "confidence": confidence,
    }
