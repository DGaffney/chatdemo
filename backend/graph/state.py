"""Graph state schema shared by all nodes in :mod:`backend.graph.graph`.

``GraphState`` is a ``TypedDict`` with ``total=False`` so nodes can populate
fields incrementally without LangGraph complaining about missing keys.
Field semantics are in-line below; the most important ones:

- ``intent``: routes the graph (lookup/policy -> retrieve+answer,
  lead/sensitive -> escalate)
- ``confidence``: thresholded by the post-call guardrail to decide whether
  to escalate despite a successful answer
- ``blocked``: set by the pre-call guardrail to short-circuit injection or
  off-topic requests with a canned reply
"""
from typing import TypedDict


class GraphState(TypedDict, total=False):
    question: str
    session_id: str
    parent_email: str

    history: list[dict]  # prior {question, answer, intent, topic} turns, oldest first

    intent: str  # lookup | policy | lead | sensitive
    topic: str
    topic_guess: str | None
    confidence: float

    retrieved_context: str
    policy_cited: str
    override_used: bool

    answer: str
    escalated: bool
    escalation_reason: str

    guardrail_flags: list[str]
    blocked: bool
    block_reason: str
