# Shipped Documents

Drop PDF handbooks into this folder. On application startup, any PDF here that
is not already in the `documents` SQLite table (identified by SHA-256 checksum)
will be parsed, chunked, and indexed automatically.

## How it works

1. `backend/main.py` lifespan calls `scan_and_ingest(settings.documents_path)`
   after `load_handbook()`. The path defaults to `docs/` (repo root).
2. Each `*.pdf` is checksummed and compared to the `documents.checksum` column.
3. New files are run through the ingestion pipeline
   (see `backend/knowledge/documents/pipeline.py`): parse with Docling, classify
   sections against the closed topic vocabulary, chunk heading-aware, and persist.
4. Resulting chunks are merged into the in-memory retrieval pool alongside the
   markdown handbook so `retriever.retrieve()` sees them transparently.

## Managing documents

- **Add a PDF:** drop it in `docs/` and restart the app (or, inside Docker,
  the compose bind-mount makes it visible without a rebuild).
- **Delete a document:** use the **Docs** tab in the operator dashboard (`/operator`).
  Deleting from the UI removes the database rows *and* the file on disk.
- **Duplicate uploads** (same file bytes) are no-ops by checksum.
- **Failed ingestion** records an `error_message` on the `documents` row and
  leaves `status='failed'`; the file can be re-dropped after fixing.

Operator-authored overrides in `knowledge_overrides` always win over document
chunks (the existing three-layer precedence is unchanged).
