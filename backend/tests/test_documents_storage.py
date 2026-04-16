"""Unit tests for :mod:`backend.knowledge.documents.storage`.

Runs each test against an isolated temp-file SQLite to exercise the
documents state machine (pending -> processing -> ready/failed), the
unique-checksum constraint, chunk insert/read, tombstoning, ``ready``-only
filtering in ``list_active_chunks``, and the supersede-link helper.
"""
import pytest

from backend.db import database as db_mod
from backend.knowledge.documents import storage


@pytest.fixture(autouse=True)
async def fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("backend.settings.settings.database_path", db_path)
    db_mod._db = None
    await db_mod.init_db()
    yield
    await db_mod.close_db()


class TestDocumentLifecycle:
    async def test_insert_pending_and_fetch_by_checksum(self):
        doc_id = await storage.insert_document_pending("abc123", "handbook.pdf")
        doc = await storage.get_document_by_checksum("abc123")
        assert doc is not None
        assert doc.id == doc_id
        assert doc.status == "pending"
        assert doc.filename == "handbook.pdf"

    async def test_unique_checksum_constraint(self):
        await storage.insert_document_pending("dup", "a.pdf")
        with pytest.raises(Exception):
            await storage.insert_document_pending("dup", "b.pdf")

    async def test_mark_ready_updates_metadata(self):
        doc_id = await storage.insert_document_pending("c1", "f.pdf")
        await storage.mark_processing(doc_id)
        await storage.mark_ready(
            doc_id, page_count=12, chunk_count=4, topics=["hours", "meals"]
        )
        doc = await storage.get_document(doc_id, include_chunks=False)
        assert doc is not None
        assert doc.status == "ready"
        assert doc.page_count == 12
        assert doc.chunk_count == 4
        assert set(doc.topics) == {"hours", "meals"}

    async def test_mark_failed_records_error(self):
        doc_id = await storage.insert_document_pending("c2", "f.pdf")
        await storage.mark_failed(doc_id, "boom")
        doc = await storage.get_document(doc_id, include_chunks=False)
        assert doc is not None
        assert doc.status == "failed"
        assert doc.error_message == "boom"


class TestChunks:
    async def _seed_ready_doc(self, checksum: str = "ready1") -> int:
        doc_id = await storage.insert_document_pending(checksum, "f.pdf")
        await storage.mark_processing(doc_id)
        chunks = [
            storage.DocumentChunk(
                document_id=doc_id,
                chunk_index=i,
                heading_path=f"Section {i}",
                topic="hours" if i % 2 == 0 else "meals",
                content=f"Body {i}",
            )
            for i in range(3)
        ]
        await storage.insert_chunks(doc_id, chunks)
        await storage.mark_ready(
            doc_id, page_count=1, chunk_count=len(chunks), topics=["hours", "meals"]
        )
        return doc_id

    async def test_insert_and_read_chunks(self):
        doc_id = await self._seed_ready_doc()
        doc = await storage.get_document(doc_id, include_chunks=True)
        assert doc is not None
        assert len(doc.chunks) == 3
        assert [c.chunk_index for c in doc.chunks] == [0, 1, 2]

    async def test_list_active_chunks_only_ready_documents(self):
        ready_id = await self._seed_ready_doc("ready_a")
        pending_id = await storage.insert_document_pending("pending_b", "f2.pdf")
        await storage.mark_processing(pending_id)
        await storage.insert_chunks(
            pending_id,
            [
                storage.DocumentChunk(
                    document_id=pending_id,
                    chunk_index=0,
                    heading_path="Pending",
                    topic="other",
                    content="should not appear",
                )
            ],
        )
        active = await storage.list_active_chunks()
        doc_ids = {c.document_id for c in active}
        assert ready_id in doc_ids
        assert pending_id not in doc_ids

    async def test_tombstone_excludes_from_active(self):
        doc_id = await self._seed_ready_doc("ts")
        before = await storage.list_active_chunks()
        assert any(c.document_id == doc_id for c in before)
        await storage.tombstone_chunks(doc_id)
        after = await storage.list_active_chunks()
        assert not any(c.document_id == doc_id for c in after)


class TestSupersede:
    async def test_set_superseded_by(self):
        old = await storage.insert_document_pending("old", "v1.pdf")
        new = await storage.insert_document_pending("new", "v2.pdf")
        await storage.set_superseded_by(old, new)
        doc = await storage.get_document(old, include_chunks=False)
        assert doc is not None
        assert doc.superseded_by == new
