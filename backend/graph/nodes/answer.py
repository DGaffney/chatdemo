"""Answer generation node.

Dispatches on ``state['intent']`` to one of three per-intent prompt pairs:

- ``lookup`` — factual, citation-required, temperature 0.1
- ``policy`` — conservative, always ends with a "flagged for staff" note,
  temperature 0.2
- ``lead``   — warm lead capture, sets ``escalated=True`` so the operator
  follows up, temperature 0.3

Sensitive turns never reach this node (they go to :mod:`backend.graph.nodes
.escalate`). The model used is ``settings.default_model`` (Sonnet by
default) via LiteLLM.
"""
import litellm
from langsmith import traceable

from backend.graph.history import history_messages
from backend.graph.state import GraphState
from backend.settings import settings
from backend.prompts.lookup_answer import LOOKUP_SYSTEM_PROMPT, LOOKUP_USER_PROMPT
from backend.prompts.policy_answer import POLICY_SYSTEM_PROMPT, POLICY_USER_PROMPT
from backend.prompts.lead_capture import LEAD_SYSTEM_PROMPT, LEAD_USER_PROMPT


def _operator_name() -> str:
    return settings.operator_email.split("@")[0].replace(".", " ").title()


@traceable(run_type="chain", name="generate_answer")
async def generate_answer(state: GraphState) -> GraphState:
    intent = state.get("intent", "lookup")
    if intent == "lookup":
        return await _generate_lookup(state)
    elif intent == "policy":
        return await _generate_policy(state)
    elif intent == "lead":
        return await _generate_lead(state)
    return state


@traceable(run_type="llm", name="generate_lookup")
async def _generate_lookup(state: GraphState) -> GraphState:
    response = await litellm.acompletion(
        model=settings.default_model,
        messages=[
            {
                "role": "system",
                "content": LOOKUP_SYSTEM_PROMPT.format(
                    center_name=settings.center_name,
                    operator_name=_operator_name(),
                    context=state.get("retrieved_context", ""),
                ),
            },
            *history_messages(state.get("history")),
            {
                "role": "user",
                "content": LOOKUP_USER_PROMPT.format(question=state["question"]),
            },
        ],
        temperature=0.1,
    )
    return {**state, "answer": response.choices[0].message.content}


@traceable(run_type="llm", name="generate_policy")
async def _generate_policy(state: GraphState) -> GraphState:
    response = await litellm.acompletion(
        model=settings.default_model,
        messages=[
            {
                "role": "system",
                "content": POLICY_SYSTEM_PROMPT.format(
                    center_name=settings.center_name,
                    operator_name=_operator_name(),
                    context=state.get("retrieved_context", ""),
                ),
            },
            *history_messages(state.get("history")),
            {
                "role": "user",
                "content": POLICY_USER_PROMPT.format(question=state["question"]),
            },
        ],
        temperature=0.2,
    )
    return {**state, "answer": response.choices[0].message.content}


@traceable(run_type="llm", name="generate_lead")
async def _generate_lead(state: GraphState) -> GraphState:
    response = await litellm.acompletion(
        model=settings.default_model,
        messages=[
            {
                "role": "system",
                "content": LEAD_SYSTEM_PROMPT.format(
                    center_name=settings.center_name,
                    operator_name=_operator_name(),
                    context=state.get("retrieved_context", ""),
                ),
            },
            *history_messages(state.get("history")),
            {
                "role": "user",
                "content": LEAD_USER_PROMPT.format(question=state["question"]),
            },
        ],
        temperature=0.3,
    )
    return {
        **state,
        "answer": response.choices[0].message.content,
        "escalated": True,
        "escalation_reason": "lead",
    }
