"""Operator knowledge-override DAL.

Overrides are the highest-priority layer of the knowledge model — they beat
both the markdown handbook and any ingested PDFs. ``find_override`` matches
by simple keyword overlap against ``question_pattern``; a v2 would use
embeddings. Writes typically happen via the triage resolution flow in
:mod:`backend.api.operator` ("promote this answer to an override").
"""
from backend.db.database import get_db


async def insert_override(
    *,
    topic: str,
    question_pattern: str,
    answer: str,
    author: str = "operator",
    source_conversation_id: int | None = None,
) -> int:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO knowledge_overrides
           (topic, question_pattern, answer, author, source_conversation_id)
           VALUES (?, ?, ?, ?, ?)""",
        (topic, question_pattern, answer, author, source_conversation_id),
    )
    await db.commit()
    return cursor.lastrowid


async def find_override(question: str, topic: str | None = None) -> dict | None:
    """Find the best-matching operator override for a question.

    Uses simple keyword overlap scoring. In production this would use
    embeddings or a more sophisticated matching strategy.
    """
    db = await get_db()
    query = "SELECT * FROM knowledge_overrides"
    params: list = []
    if topic:
        query += " WHERE topic = ?"
        params.append(topic)
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    if not rows:
        return None

    q_words = set(question.lower().split())
    best_match = None
    best_score = 0.0

    for row in rows:
        pattern_words = set(row["question_pattern"].lower().split())
        if not pattern_words:
            continue
        overlap = len(q_words & pattern_words)
        score = overlap / max(len(pattern_words), 1)
        if score > best_score and score >= 0.4:
            best_score = score
            best_match = dict(row)

    return best_match


async def list_overrides() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM knowledge_overrides ORDER BY created_at DESC"
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def delete_override(override_id: int) -> None:
    db = await get_db()
    await db.execute("DELETE FROM knowledge_overrides WHERE id = ?", (override_id,))
    await db.commit()
