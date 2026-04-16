"""Short-term conversation memory helpers shared by graph nodes.

``load_history`` is a graph node that pulls the most recent turns for the
current ``session_id`` from the ``conversations`` table and stashes them on
state so downstream nodes can include them in their LLM calls.

``history_messages`` turns that list of turns into an OpenAI-style
``[{"role": "user"/"assistant", "content": ...}]`` slice suitable for
splicing between the system prompt and the current-turn user message.

Nothing here accumulates state across invocations — each request re-reads
the log. The ``conversations`` table is already the authoritative record
(written by ``log_conversation`` after every turn), so we just read it.
"""
from langsmith import traceable

from backend.db.conversations import list_recent_turns
from backend.graph.state import GraphState

HISTORY_TURN_LIMIT = 8
MAX_ANSWER_CHARS = 1500


@traceable(run_type="tool", name="load_history")
async def load_history(state: GraphState) -> GraphState:
    session_id = state.get("session_id")
    if not session_id:
        return {**state, "history": []}
    turns = await list_recent_turns(session_id, limit=HISTORY_TURN_LIMIT)
    return {**state, "history": turns}


def _annotate_assistant(turn: dict, answer: str) -> str:
    """Prefix the assistant message with a compact status tag.

    We surface ``intent``/``topic`` and whether the turn was escalated so
    downstream LLM calls can reason about the arc of the conversation
    (e.g. "I already flagged this for Maria", "we already talked about
    tuition"). The tag is terse on purpose: the conversation content is
    still the primary signal, this is just a breadcrumb.
    """
    tags: list[str] = []
    intent = (turn.get("intent") or "").strip()
    topic = (turn.get("topic") or "").strip()
    if intent:
        tags.append(f"intent={intent}")
    if topic:
        tags.append(f"topic={topic}")
    if turn.get("escalated"):
        reason = (turn.get("escalation_reason") or "escalated").strip()
        tags.append(f"escalated={reason}")
    if not tags:
        return answer
    return f"[prior turn: {', '.join(tags)}]\n{answer}"


def history_messages(history: list[dict] | None) -> list[dict]:
    """Format prior turns as alternating user/assistant messages for LiteLLM.

    Each assistant message is prefixed with a short status tag so the model
    can see the intent/topic/escalation status of the earlier turn without
    having to infer it from content alone. Long answers are truncated so
    history doesn't balloon context for multi-turn sessions.
    """
    if not history:
        return []
    messages: list[dict] = []
    for turn in history:
        question = (turn.get("question") or "").strip()
        answer = (turn.get("answer") or "").strip()
        if not question:
            continue
        messages.append({"role": "user", "content": question})
        if answer:
            if len(answer) > MAX_ANSWER_CHARS:
                answer = answer[:MAX_ANSWER_CHARS].rstrip() + " […]"
            messages.append(
                {"role": "assistant", "content": _annotate_assistant(turn, answer)}
            )
    return messages
