"""Triage queue DAL.

The operator's inbox of escalated conversations. Every escalated turn (from
sensitive handling, low confidence, or lead capture) produces a triage row.
Lead and sensitive escalations are marked ``priority='high'`` so they sort
above the rest. ``resolve_triage_item`` is the entry point for the learning
loop — operator.py calls it and can promote the resolution to a knowledge
override in the same request.

``get_triage_stats`` also surfaces novel topics (``topic_guess`` values from
classifier "other" responses) so the operator can spot handbook gaps.
"""
from backend.db.database import get_db


async def insert_triage_item(
    *,
    conversation_id: int,
    parent_email: str | None = None,
    priority: str = "normal",
) -> int:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO triage_queue (conversation_id, parent_email, priority)
           VALUES (?, ?, ?)""",
        (conversation_id, parent_email, priority),
    )
    await db.commit()
    return cursor.lastrowid


async def get_open_triage(
    *, priority: str | None = None, limit: int = 100
) -> list[dict]:
    db = await get_db()
    params: list = []
    clauses = ["t.status = 'open'"]
    if priority:
        clauses.append("t.priority = ?")
        params.append(priority)
    where = " WHERE " + " AND ".join(clauses)
    query = f"""
        SELECT t.*, c.question, c.answer, c.intent, c.topic, c.topic_guess,
               c.confidence, c.escalation_reason
        FROM triage_queue t
        JOIN conversations c ON t.conversation_id = c.id
        {where}
        ORDER BY
            CASE t.priority WHEN 'high' THEN 0 ELSE 1 END,
            t.created_at DESC
        LIMIT ?
    """
    params.append(limit)
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_triage_item(triage_id: int) -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        """SELECT t.*, c.question, c.answer, c.intent, c.topic, c.topic_guess,
                  c.confidence, c.escalation_reason, c.session_id
           FROM triage_queue t
           JOIN conversations c ON t.conversation_id = c.id
           WHERE t.id = ?""",
        (triage_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def resolve_triage_item(
    triage_id: int, *, resolved_by: str, resolution_text: str
) -> None:
    db = await get_db()
    await db.execute(
        """UPDATE triage_queue
           SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP,
               resolved_by = ?, resolution_text = ?
           WHERE id = ?""",
        (resolved_by, resolution_text, triage_id),
    )
    await db.commit()


async def dismiss_triage_item(triage_id: int) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE triage_queue SET status = 'dismissed' WHERE id = ?",
        (triage_id,),
    )
    await db.commit()


async def get_triage_stats() -> dict:
    db = await get_db()

    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM triage_queue WHERE status = 'open'"
    )
    row = await cursor.fetchone()
    open_count = row["cnt"]

    cursor = await db.execute(
        """SELECT c.topic, COUNT(*) as cnt
           FROM triage_queue t JOIN conversations c ON t.conversation_id = c.id
           WHERE t.status = 'open'
           GROUP BY c.topic ORDER BY cnt DESC"""
    )
    by_topic = [dict(r) for r in await cursor.fetchall()]

    cursor = await db.execute(
        """SELECT c.topic_guess, COUNT(*) as cnt
           FROM triage_queue t JOIN conversations c ON t.conversation_id = c.id
           WHERE t.status = 'open' AND c.topic = 'other' AND c.topic_guess IS NOT NULL
           GROUP BY c.topic_guess ORDER BY cnt DESC"""
    )
    novel_topics = [dict(r) for r in await cursor.fetchall()]

    return {
        "open_count": open_count,
        "by_topic": by_topic,
        "novel_topics": novel_topics,
    }
