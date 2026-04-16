"""SQLite connection lifecycle + schema bootstrap.

Owns a lazily-created module-level ``aiosqlite`` connection with WAL mode
and foreign keys enabled. ``init_db()`` is idempotent — it ``executescript``s
``backend/db/schema.sql``, which uses ``CREATE TABLE IF NOT EXISTS`` so it is
safe to run on every startup. Tests monkeypatch ``settings.database_path``
and reset the module-level ``_db`` to get an isolated temp database.
"""
import os
import aiosqlite

from backend.settings import settings

_db: aiosqlite.Connection | None = None


def _schema_path() -> str:
    return os.path.join(os.path.dirname(__file__), "schema.sql")


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        os.makedirs(os.path.dirname(settings.database_path) or ".", exist_ok=True)
        _db = await aiosqlite.connect(settings.database_path)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def init_db():
    db = await get_db()
    with open(_schema_path()) as f:
        await db.executescript(f.read())
    await _apply_migrations(db)
    await db.commit()


async def _apply_migrations(db) -> None:
    """Apply lightweight, idempotent ALTERs for columns added after initial release.

    ``CREATE TABLE IF NOT EXISTS`` doesn't add columns to an existing table,
    so any column introduced after a user has already initialized their DB
    must be added explicitly. Each migration is wrapped in try/except so
    repeated runs are no-ops.
    """
    cursor = await db.execute("PRAGMA table_info(documents)")
    cols = {row["name"] for row in await cursor.fetchall()}
    if "summary" not in cols:
        await db.execute("ALTER TABLE documents ADD COLUMN summary TEXT")


async def close_db():
    global _db
    if _db is not None:
        await _db.close()
        _db = None
