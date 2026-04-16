"""Top-level LangGraph for parent chat request processing.

Assembles the node graph, wires conditional routing, and owns the final
``log_conversation`` node that persists the turn and (if escalated) creates
a triage-queue row. Exposes a compiled ``graph`` instance at import time so
the API layer can call ``graph.ainvoke(initial_state)`` directly.

Routing:

- load_history        -> pre_guardrail (seeds state['history'] from the
  conversations table so downstream LLM calls see prior turns for the same
  session_id)
- pre_guardrail       -> classify (or log, if blocked)
- classify            -> retrieve (lookup/policy) or retrieve_for_escalation
- retrieve            -> generate_answer -> post_guardrail -> log
- retrieve_for_escalation -> generate_answer (lead) or escalate (sensitive)
  -> log

Lead turns go through answer generation so the parent still gets a warm
acknowledgement while the escalation is recorded.
"""
import logging

from langgraph.graph import StateGraph, END
from langsmith import traceable

from backend.graph.state import GraphState
from backend.graph.history import load_history
from backend.graph.nodes.guardrails import pre_call_guardrail, post_call_guardrail
from backend.graph.nodes.classify import classify
from backend.graph.nodes.retrieve import retrieve_knowledge
from backend.graph.nodes.answer import generate_answer
from backend.graph.nodes.escalate import escalate
from backend.db.conversations import insert_conversation
from backend.db.triage import insert_triage_item

logger = logging.getLogger(__name__)


@traceable(run_type="tool", name="log_conversation")
async def log_conversation(state: GraphState) -> GraphState:
    conversation_id = await insert_conversation(
        session_id=state.get("session_id"),
        question=state.get("question", ""),
        answer=state.get("answer"),
        intent=state.get("intent"),
        topic=state.get("topic"),
        topic_guess=state.get("topic_guess"),
        confidence=state.get("confidence"),
        escalated=state.get("escalated", False),
        escalation_reason=state.get("escalation_reason"),
        policy_cited=state.get("policy_cited"),
        guardrail_flags=state.get("guardrail_flags"),
    )

    if state.get("escalated"):
        priority = "high" if state.get("intent") in ("lead", "sensitive") else "normal"
        await insert_triage_item(
            conversation_id=conversation_id,
            parent_email=state.get("parent_email"),
            priority=priority,
        )

    return {**state, "conversation_id": conversation_id}


def _route_after_guardrail(state: GraphState) -> str:
    if state.get("blocked"):
        return "log"
    return "classify"


def _route_after_classify(state: GraphState) -> str:
    intent = state.get("intent", "lookup")
    if intent in ("sensitive", "lead"):
        return "retrieve_for_escalation"
    return "retrieve"


def _route_after_answer(state: GraphState) -> str:
    return "post_guardrail"


def _route_after_escalation_retrieve(state: GraphState) -> str:
    intent = state.get("intent")
    if intent == "lead":
        return "generate_answer"
    return "escalate"


def build_graph() -> StateGraph:
    builder = StateGraph(GraphState)

    builder.add_node("load_history", load_history)
    builder.add_node("pre_guardrail", pre_call_guardrail)
    builder.add_node("classify", classify)
    builder.add_node("retrieve", retrieve_knowledge)
    builder.add_node("retrieve_for_escalation", retrieve_knowledge)
    builder.add_node("generate_answer", generate_answer)
    builder.add_node("escalate", escalate)
    builder.add_node("post_guardrail", post_call_guardrail)
    builder.add_node("log", log_conversation)

    builder.set_entry_point("load_history")
    builder.add_edge("load_history", "pre_guardrail")

    builder.add_conditional_edges(
        "pre_guardrail",
        _route_after_guardrail,
        {"log": "log", "classify": "classify"},
    )

    builder.add_conditional_edges(
        "classify",
        _route_after_classify,
        {"retrieve": "retrieve", "retrieve_for_escalation": "retrieve_for_escalation"},
    )

    builder.add_edge("retrieve", "generate_answer")

    builder.add_conditional_edges(
        "retrieve_for_escalation",
        _route_after_escalation_retrieve,
        {"generate_answer": "generate_answer", "escalate": "escalate"},
    )

    builder.add_edge("generate_answer", "post_guardrail")
    builder.add_edge("post_guardrail", "log")
    builder.add_edge("escalate", "log")
    builder.add_edge("log", END)

    return builder.compile()


graph = build_graph()


@traceable(run_type="chain", name="parent_chat_turn")
async def run_parent_turn(initial_state: GraphState) -> GraphState:
    """Root-level entry point for a single parent turn.

    Exists so that every request is a single LangSmith trace with all node
    calls nested underneath it. Call this instead of ``graph.ainvoke`` from
    the API layer.
    """
    return await graph.ainvoke(initial_state)
