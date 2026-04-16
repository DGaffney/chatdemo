"""Conversation log DAL.

One row per parent turn, written by ``log_conversation`` in
:mod:`backend.graph.graph` after every graph execution. Captures the
question, the generated answer (or empty when escalated), the classifier's
intent/topic/confidence, and whether guardrails or escalation fired.

The conversation id is referenced by ``triage_queue`` rows and by
``knowledge_overrides.source_conversation_id`` so the learning loop can
trace a promoted override back to its origin question.
"""
import json
from backend.db.database import get_db


async def insert_conversation(
    *,
    session_id: str | None = None,
    question: str,
    answer: str | None = None,
    intent: str | None = None,
    topic: str | None = None,
    topic_guess: str | None = None,
    confidence: float | None = None,
    escalated: bool = False,
    escalation_reason: str | None = None,
    policy_cited: str | None = None,
    guardrail_flags: list[str] | None = None,
) -> int:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO conversations
           (session_id, question, answer, intent, topic, topic_guess,
            confidence, escalated, escalation_reason, policy_cited, guardrail_flags)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            question,
            answer,
            intent,
            topic,
            topic_guess,
            confidence,
            escalated,
            escalation_reason,
            policy_cited,
            json.dumps(guardrail_flags) if guardrail_flags else None,
        ),
    )
    await db.commit()
    return cursor.lastrowid


async def get_conversation(conversation_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return dict(row)


async def list_recent_turns(
    session_id: str,
    limit: int = 8,
) -> list[dict]:
    """Return the most recent ``limit`` turns for a session, oldest first.

    Memory is a log, not a judgment. We intentionally do NOT filter by
    ``escalated`` — knowing that a prior turn was flagged (and why) is
    useful signal for the model on the next turn (e.g. so it doesn't
    re-escalate the same custody question or re-ask for a parent email
    it already captured). Downstream code decides how to present that
    signal; the DAL just returns the rows. The only rows we skip are
    still-in-flight ones with no answer yet.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT question, answer, intent, topic, escalated, escalation_reason
           FROM conversations
           WHERE session_id = ? AND answer IS NOT NULL
           ORDER BY created_at DESC
           LIMIT ?""",
        (session_id, limit),
    )
    rows = await cursor.fetchall()
    return list(reversed([dict(r) for r in rows]))


async def list_conversations(
    *,
    intent: str | None = None,
    topic: str | None = None,
    escalated: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    db = await get_db()
    clauses: list[str] = []
    params: list = []
    if intent:
        clauses.append("intent = ?")
        params.append(intent)
    if topic:
        clauses.append("topic = ?")
        params.append(topic)
    if escalated is not None:
        clauses.append("escalated = ?")
        params.append(escalated)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    query = f"SELECT * FROM conversations{where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]
