"""Per-center key/value configuration DAL.

Thin wrapper over the ``center_config`` table. Populated by the onboarding
wizard (see :mod:`backend.api.onboarding`) with fields like ``center_name``,
``operator_email``, and raw policy text that feeds the generated handbook.
``INSERT OR REPLACE`` semantics make ``set_config`` idempotent.
"""
from backend.db.database import get_db


async def get_config(key: str) -> str | None:
    db = await get_db()
    cursor = await db.execute("SELECT value FROM center_config WHERE key = ?", (key,))
    row = await cursor.fetchone()
    return row["value"] if row else None


async def set_config(key: str, value: str) -> None:
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO center_config (key, value) VALUES (?, ?)",
        (key, value),
    )
    await db.commit()


async def get_all_config() -> dict[str, str]:
    db = await get_db()
    cursor = await db.execute("SELECT key, value FROM center_config")
    rows = await cursor.fetchall()
    return {row["key"]: row["value"] for row in rows}
