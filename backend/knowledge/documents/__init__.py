"""Document pipeline module.

Public CRUD surface for PDF handbook ingestion. Callers should use these
functions rather than reaching into storage/pipeline directly.

    create(file_path)  -> ingest a PDF, return doc_id
    read(doc_id)       -> fetch a Document (with chunks) by id
    update(doc_id, fp) -> re-ingest and supersede (v1 stub)
    delete(doc_id)     -> tombstone chunks (v1 stub)
    search(query)      -> scoped retrieval over document chunks
"""

from __future__ import annotations

import os

from backend.knowledge.documents import storage
from backend.knowledge.documents.pipeline import ingest
from backend.knowledge.documents.storage import Document, DocumentChunk
from backend.knowledge.retriever import RetrievalResult, retrieve

__all__ = [
    "Document",
    "DocumentChunk",
    "create",
    "read",
    "update",
    "delete",
    "search",
]


async def create(file_path: str) -> int:
    """Ingest a PDF and return its document id.

    Re-uploading a file with a checksum already stored as 'ready' is a no-op
    that returns the existing id.
    """
    filename = os.path.basename(file_path)
    result = await ingest(file_path, filename)
    doc_id = result.get("document_id")
    if doc_id is None:
        raise RuntimeError(f"Ingestion did not produce a document id for {filename}")
    return doc_id


async def read(doc_id: int) -> Document | None:
    """Fetch a Document (with its active chunks) by id, or None if missing."""
    return await storage.get_document(doc_id, include_chunks=True)


async def update(doc_id: int, file_path: str) -> int:
    """Re-ingest a document, superseding the prior version.

    v1 stub — the operator-facing upload flow that would call this is
    deferred. The ingestion pipeline already supports re-processing stale
    rows; wiring supersede semantics belongs with the upload API work.
    """
    raise NotImplementedError(
        "update() is deferred until the operator upload endpoint lands"
    )


async def delete(doc_id: int) -> None:
    """Soft-delete a document by tombstoning its chunks.

    v1 stub — we haven't wired re-hydration of the in-memory retrieval pool
    on delete. Ship this together with the operator 'remove document' UI.
    """
    raise NotImplementedError(
        "delete() is deferred until the operator document management UI lands"
    )


async def search(
    query: str,
    topic: str | None = None,
    doc_id: int | None = None,
    top_k: int = 5,
) -> list[RetrievalResult]:
    """Retrieve the most relevant chunks for a query.

    Delegates to the shared `knowledge.retriever` so documents and markdown
    compete in a single scoring pass. If `doc_id` is supplied, results are
    filtered to chunks belonging to that document.
    """
    results = retrieve(query, topic=topic, top_k=top_k * 4 if doc_id else top_k)

    if doc_id is not None:
        results = [
            r
            for r in results
            if r.chunk.metadata.get("document_id") == doc_id
        ][:top_k]

    return results
