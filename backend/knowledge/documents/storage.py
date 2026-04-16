"""Async DAL for the ``documents`` and ``document_chunks`` tables.

Owns the state machine for ingested PDFs:

    pending  ->  processing  ->  ready
                            \\->  failed  (error_message set)

- ``insert_document_pending`` / ``mark_processing`` / ``mark_ready`` /
  ``mark_failed`` drive the lifecycle from :mod:`backend.knowledge
  .documents.pipeline`.
- ``list_active_chunks`` returns only chunks belonging to ``ready``
  documents — the hydration step at startup consumes these.
- ``tombstone_chunks`` soft-deletes a document's chunks (``is_active=0``)
  without losing history; partial indexes on ``is_active=1`` keep the hot
  path fast.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.db.database import get_db


@dataclass
class DocumentChunk:
    document_id: int
    chunk_index: int
    content: str
    heading_path: str = ""
    topic: str = "other"
    page_start: int | None = None
    page_end: int | None = None
    id: int | None = None
    is_active: bool = True


@dataclass
class Document:
    id: int
    checksum: str
    filename: str
    status: str
    uploaded_at: str | None = None
    processed_at: str | None = None
    error_message: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    topics: list[str] = field(default_factory=list)
    summary: str | None = None
    superseded_by: int | None = None
    chunks: list[DocumentChunk] = field(default_factory=list)


def _row_to_document(row, chunks: list[DocumentChunk] | None = None) -> Document:
    topics_raw = row["topics"]
    topics = json.loads(topics_raw) if topics_raw else []
    keys = row.keys() if hasattr(row, "keys") else []
    summary = row["summary"] if "summary" in keys else None
    return Document(
        id=row["id"],
        checksum=row["checksum"],
        filename=row["filename"],
        status=row["status"],
        uploaded_at=row["uploaded_at"],
        processed_at=row["processed_at"],
        error_message=row["error_message"],
        page_count=row["page_count"],
        chunk_count=row["chunk_count"],
        topics=topics,
        summary=summary,
        superseded_by=row["superseded_by"],
        chunks=chunks or [],
    )


def _row_to_chunk(row) -> DocumentChunk:
    return DocumentChunk(
        id=row["id"],
        document_id=row["document_id"],
        chunk_index=row["chunk_index"],
        heading_path=row["heading_path"] or "",
        topic=row["topic"] or "other",
        page_start=row["page_start"],
        page_end=row["page_end"],
        content=row["content"],
        is_active=bool(row["is_active"]),
    )


async def get_document_by_checksum(checksum: str) -> Document | None:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM documents WHERE checksum = ?", (checksum,)
    )
    row = await cursor.fetchone()
    return _row_to_document(row) if row else None


async def get_document(doc_id: int, include_chunks: bool = True) -> Document | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    row = await cursor.fetchone()
    if not row:
        return None
    chunks: list[DocumentChunk] = []
    if include_chunks:
        cursor = await db.execute(
            "SELECT * FROM document_chunks WHERE document_id = ? AND is_active = 1 "
            "ORDER BY chunk_index",
            (doc_id,),
        )
        chunks = [_row_to_chunk(r) for r in await cursor.fetchall()]
    return _row_to_document(row, chunks)


async def list_documents(status: str | None = None) -> list[Document]:
    db = await get_db()
    if status:
        cursor = await db.execute(
            "SELECT * FROM documents WHERE status = ? ORDER BY uploaded_at DESC",
            (status,),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM documents ORDER BY uploaded_at DESC"
        )
    rows = await cursor.fetchall()
    return [_row_to_document(r) for r in rows]


async def list_active_chunks() -> list[DocumentChunk]:
    """All active chunks across all ready documents, for hydrating the retriever."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT c.* FROM document_chunks c
           JOIN documents d ON d.id = c.document_id
           WHERE c.is_active = 1 AND d.status = 'ready'
           ORDER BY c.document_id, c.chunk_index"""
    )
    return [_row_to_chunk(r) for r in await cursor.fetchall()]


async def list_sections_for_documents(
    doc_ids: list[int],
) -> dict[int, list[dict]]:
    """Return a compact section outline per document (no chunk content).

    Used by the operator API to render what was ingested from each PDF without
    shipping the full chunk text. Each entry contains the chunk index, the
    heading path, the topic classification, and the page range.
    """
    if not doc_ids:
        return {}
    db = await get_db()
    placeholders = ",".join("?" for _ in doc_ids)
    cursor = await db.execute(
        f"""SELECT document_id, chunk_index, heading_path, topic,
                   page_start, page_end
            FROM document_chunks
            WHERE document_id IN ({placeholders}) AND is_active = 1
            ORDER BY document_id, chunk_index""",
        tuple(doc_ids),
    )
    rows = await cursor.fetchall()
    by_doc: dict[int, list[dict]] = {doc_id: [] for doc_id in doc_ids}
    for r in rows:
        by_doc[r["document_id"]].append(
            {
                "chunk_index": r["chunk_index"],
                "heading_path": r["heading_path"] or "",
                "topic": r["topic"] or "other",
                "page_start": r["page_start"],
                "page_end": r["page_end"],
            }
        )
    return by_doc


async def insert_document_pending(checksum: str, filename: str) -> int:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO documents (checksum, filename, status)
           VALUES (?, ?, 'pending')""",
        (checksum, filename),
    )
    await db.commit()
    return cursor.lastrowid


async def mark_processing(doc_id: int) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE documents SET status = 'processing' WHERE id = ?", (doc_id,)
    )
    await db.commit()


async def mark_failed(doc_id: int, error_message: str) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE documents SET status = 'failed', error_message = ? WHERE id = ?",
        (error_message, doc_id),
    )
    await db.commit()


async def mark_ready(
    doc_id: int,
    *,
    page_count: int | None,
    chunk_count: int,
    topics: list[str],
    summary: str | None = None,
) -> None:
    db = await get_db()
    processed_at = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """UPDATE documents
           SET status = 'ready',
               processed_at = ?,
               page_count = ?,
               chunk_count = ?,
               topics = ?,
               summary = ?,
               error_message = NULL
           WHERE id = ?""",
        (processed_at, page_count, chunk_count, json.dumps(topics), summary, doc_id),
    )
    await db.commit()


async def insert_chunks(doc_id: int, chunks: list[DocumentChunk]) -> None:
    """Insert a batch of chunks. Caller is responsible for status transitions."""
    if not chunks:
        return
    db = await get_db()
    await db.executemany(
        """INSERT INTO document_chunks
           (document_id, chunk_index, heading_path, topic,
            page_start, page_end, content, is_active)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
        [
            (
                doc_id,
                c.chunk_index,
                c.heading_path,
                c.topic,
                c.page_start,
                c.page_end,
                c.content,
            )
            for c in chunks
        ],
    )
    await db.commit()


async def tombstone_chunks(doc_id: int) -> None:
    """Soft-delete all chunks belonging to a document."""
    db = await get_db()
    await db.execute(
        "UPDATE document_chunks SET is_active = 0 WHERE document_id = ?", (doc_id,)
    )
    await db.commit()


async def delete_document(doc_id: int) -> bool:
    """Hard-delete a document and all of its chunks.

    Returns True if a row was removed, False if the id was unknown. Any
    ``superseded_by`` references from other documents are cleared first so
    the FK constraint doesn't prevent deletion.
    """
    db = await get_db()
    cursor = await db.execute("SELECT id FROM documents WHERE id = ?", (doc_id,))
    if not await cursor.fetchone():
        return False

    await db.execute(
        "UPDATE documents SET superseded_by = NULL WHERE superseded_by = ?",
        (doc_id,),
    )
    await db.execute(
        "DELETE FROM document_chunks WHERE document_id = ?", (doc_id,)
    )
    await db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    await db.commit()
    return True


async def set_superseded_by(old_doc_id: int, new_doc_id: int) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE documents SET superseded_by = ? WHERE id = ?",
        (new_doc_id, old_doc_id),
    )
    await db.commit()
