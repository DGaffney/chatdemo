"""Startup helpers that tie documents into the main app.

Called from :func:`backend.main.lifespan` after the markdown handbook
loads. Two responsibilities:

- ``scan_and_ingest(path)``: walk ``path`` for ``*.pdf`` files, run each
  one through the ingestion pipeline. Already-``ready`` documents
  short-circuit in the pipeline's dedup node, so this is safe to call on
  every boot.
- ``hydrate_chunk_pool()``: read all active chunks from ``ready``
  documents, convert them to ``loader.Chunk`` objects (source prefixed with
  ``doc:<filename>#<heading_path>``, category = topic), and extend the
  shared in-memory pool via ``loader.extend_chunks()``. After this runs
  the retriever sees PDF-derived chunks alongside markdown ones with no
  special-casing.
"""
import logging
import os

from backend.knowledge.documents import storage
from backend.knowledge.documents.pipeline import ingest
from backend.knowledge.loader import Chunk, extend_chunks

logger = logging.getLogger(__name__)


async def scan_and_ingest(documents_path: str) -> list[int]:
    """Walk documents_path for PDFs and ingest any not yet stored as 'ready'.

    Returns the list of document IDs that are now 'ready' as a result of this
    scan (both freshly-ingested and previously-ready documents whose files are
    still on disk).
    """
    if not os.path.isdir(documents_path):
        logger.info("Documents path %s does not exist; skipping scan", documents_path)
        return []

    ready_ids: list[int] = []
    for fname in sorted(os.listdir(documents_path)):
        if not fname.lower().endswith(".pdf"):
            continue
        full_path = os.path.join(documents_path, fname)
        if not os.path.isfile(full_path):
            continue

        try:
            result = await ingest(full_path, fname)
        except Exception:
            logger.exception("Ingestion raised for %s", fname)
            continue

        doc_id = result.get("document_id")
        if doc_id is None:
            continue

        doc = await storage.get_document(doc_id, include_chunks=False)
        if doc and doc.status == "ready":
            ready_ids.append(doc_id)
        elif doc:
            logger.warning(
                "Document %s finished with status=%s (error=%s)",
                fname,
                doc.status,
                doc.error_message,
            )

    return ready_ids


def _chunk_from_document_chunk(
    doc_chunk: storage.DocumentChunk, filename: str
) -> Chunk:
    heading = doc_chunk.heading_path.split(" > ")[-1] if doc_chunk.heading_path else ""
    source = f"doc:{filename}"
    if doc_chunk.heading_path:
        source = f"{source}#{doc_chunk.heading_path}"
    return Chunk(
        content=doc_chunk.content,
        source=source,
        category=doc_chunk.topic or "other",
        heading=heading,
        metadata={
            "document_id": doc_chunk.document_id,
            "chunk_index": doc_chunk.chunk_index,
            "heading_path": doc_chunk.heading_path,
            "page_start": doc_chunk.page_start,
            "page_end": doc_chunk.page_end,
        },
    )


async def hydrate_chunk_pool() -> int:
    """Load all active chunks from ready documents into the retriever pool.

    Safe to call after scan_and_ingest(). Returns the number of chunks
    appended to the pool.
    """
    doc_chunks = await storage.list_active_chunks()
    if not doc_chunks:
        return 0

    filenames: dict[int, str] = {}
    converted: list[Chunk] = []
    for dc in doc_chunks:
        filename = filenames.get(dc.document_id)
        if filename is None:
            doc = await storage.get_document(dc.document_id, include_chunks=False)
            filename = doc.filename if doc else f"document_{dc.document_id}"
            filenames[dc.document_id] = filename
        converted.append(_chunk_from_document_chunk(dc, filename))

    extend_chunks(converted)
    logger.info("Hydrated retrieval pool with %d document chunk(s)", len(converted))
    return len(converted)
