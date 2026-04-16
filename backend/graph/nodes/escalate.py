"""Sensitive-topic escalation node.

Produces a warm, non-committal acknowledgment that explicitly does NOT
answer the question (custody disputes, legal, medical emergencies, abuse
concerns, etc.). The reply reassures the parent that the operator will
reach out by email, without revealing why the question was flagged. Sets
``escalated=True`` and an ``escalation_reason`` so the triage row is
created with ``priority='high'``.
"""
import litellm
from langsmith import traceable

from backend.graph.history import history_messages
from backend.graph.state import GraphState
from backend.settings import settings
from backend.prompts.escalate import ESCALATION_SYSTEM_PROMPT, ESCALATION_USER_PROMPT


@traceable(run_type="llm", name="escalate")
async def escalate(state: GraphState) -> GraphState:
    operator_name = settings.operator_email.split("@")[0].replace(".", " ").title()

    response = await litellm.acompletion(
        model=settings.default_model,
        messages=[
            {
                "role": "system",
                "content": ESCALATION_SYSTEM_PROMPT.format(
                    center_name=settings.center_name,
                    operator_name=operator_name,
                ),
            },
            *history_messages(state.get("history")),
            {
                "role": "user",
                "content": ESCALATION_USER_PROMPT.format(question=state["question"]),
            },
        ],
        temperature=0.3,
    )
    return {
        **state,
        "answer": response.choices[0].message.content,
        "escalated": True,
        "escalation_reason": state.get("escalation_reason") or "sensitive",
    }
