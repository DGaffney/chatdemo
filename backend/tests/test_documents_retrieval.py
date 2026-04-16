"""End-to-end test: document chunks flow through the shared retriever.

Seeds a fake document via the storage DAL, hydrates the retrieval pool, then
calls the same `retriever.retrieve()` that the production graph uses and
asserts a document chunk ranks for a matching query.
"""
import pytest

from backend.db import database as db_mod
from backend.knowledge import loader, retriever
from backend.knowledge.documents import storage
from backend.knowledge.documents.bootstrap import hydrate_chunk_pool


@pytest.fixture(autouse=True)
async def fresh_db_and_pool(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("backend.settings.settings.database_path", db_path)
    db_mod._db = None
    loader._chunks = []
    await db_mod.init_db()
    yield
    await db_mod.close_db()
    loader._chunks = []


async def _seed_ready_document(
    checksum: str = "rt1",
    filename: str = "center_handbook.pdf",
    chunks_data: list[tuple[str, str, str]] | None = None,
) -> int:
    """chunks_data items are (heading_path, topic, content)."""
    doc_id = await storage.insert_document_pending(checksum, filename)
    await storage.mark_processing(doc_id)
    chunks = [
        storage.DocumentChunk(
            document_id=doc_id,
            chunk_index=i,
            heading_path=hp,
            topic=topic,
            content=content,
        )
        for i, (hp, topic, content) in enumerate(chunks_data or [])
    ]
    await storage.insert_chunks(doc_id, chunks)
    topics = sorted({t for _, t, _ in chunks_data or []})
    await storage.mark_ready(
        doc_id, page_count=1, chunk_count=len(chunks), topics=topics
    )
    return doc_id


class TestHydrateAndRetrieve:
    async def test_document_chunk_is_retrievable(self):
        await _seed_ready_document(
            chunks_data=[
                (
                    "Health > Medication",
                    "sick_policy",
                    "Children who have a fever above 100.4 must stay home.",
                )
            ]
        )
        added = await hydrate_chunk_pool()
        assert added == 1

        results = retriever.retrieve("fever policy", topic="sick_policy")
        assert len(results) > 0
        top = results[0]
        assert "fever" in top.chunk.content.lower()
        assert top.chunk.source.startswith("doc:center_handbook.pdf")
        assert top.chunk.category == "sick_policy"
        assert top.chunk.metadata["heading_path"] == "Health > Medication"

    async def test_only_ready_document_chunks_are_hydrated(self):
        await _seed_ready_document(
            checksum="ok",
            chunks_data=[("Hours", "hours", "We open at 7 AM every weekday.")],
        )
        pending_id = await storage.insert_document_pending("pending", "pending.pdf")
        await storage.mark_processing(pending_id)
        await storage.insert_chunks(
            pending_id,
            [
                storage.DocumentChunk(
                    document_id=pending_id,
                    chunk_index=0,
                    heading_path="Secret",
                    topic="other",
                    content="This should not be retrievable.",
                )
            ],
        )

        await hydrate_chunk_pool()
        results = retriever.retrieve("secret retrievable")
        for r in results:
            assert "should not be retrievable" not in r.chunk.content

    async def test_document_chunk_metadata_populated(self):
        await _seed_ready_document(
            chunks_data=[
                (
                    "Enrollment > Tours",
                    "tours",
                    "Tours are scheduled Tuesdays and Thursdays.",
                )
            ]
        )
        await hydrate_chunk_pool()
        results = retriever.retrieve("tour scheduled")
        assert results
        top = results[0]
        assert top.chunk.metadata["document_id"] is not None
        assert top.chunk.metadata["chunk_index"] == 0
        assert top.chunk.heading == "Tours"
