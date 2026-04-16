"""Unit tests for :mod:`backend.knowledge.documents.pipeline`.

Runs the LangGraph ingestion subgraph end-to-end with the Docling parser
and the LLM section classifier stubbed out so the tests are fast and
offline. Covers the happy path (chunks persisted, status flipped to
``ready``, topics aggregated), checksum short-circuiting on duplicate
uploads, parse/classify failure recording ``error_message`` with
``status='failed'``, and boilerplate sections being dropped from storage.
"""
import pytest

from backend.db import database as db_mod
from backend.knowledge.documents import pipeline, storage
from backend.knowledge.documents.parser import ParseResult
from backend.knowledge.documents.section_classifier import SectionTag

SAMPLE_MARKDOWN = """\
# Health

## Medication

""" + ("Policy detail. " * 80) + """

## Immunizations

""" + ("Shot records. " * 80) + """

# Hours

""" + ("We open at 7. " * 80) + """
"""


@pytest.fixture(autouse=True)
async def fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("backend.settings.settings.database_path", db_path)
    db_mod._db = None
    pipeline._graph = None
    await db_mod.init_db()
    yield
    await db_mod.close_db()


@pytest.fixture
def sample_pdf(tmp_path):
    f = tmp_path / "handbook.pdf"
    f.write_bytes(b"%PDF-fake-bytes-for-test\n" + b"x" * 1024)
    return str(f)


def _mock_parser(monkeypatch, markdown: str = SAMPLE_MARKDOWN, pages: int = 3):
    """Stub out the Docling parser so tests don't need torch/easyocr."""

    def fake_parse(file_path: str) -> ParseResult:
        return ParseResult(markdown=markdown, page_count=pages)

    import backend.knowledge.documents.parser as parser_mod

    monkeypatch.setattr(parser_mod, "parse_pdf", fake_parse)
    pipeline._graph = None


def _mock_classifier(
    monkeypatch,
    topic_map: dict[str, str] | None = None,
    boilerplate: set[str] | None = None,
):
    """Stub out the LLM section classifier."""
    topic_map = topic_map or {}
    boilerplate = boilerplate or set()

    async def fake_classify(headings: list[str]) -> list[SectionTag]:
        return [
            SectionTag(
                topic=topic_map.get(h, "other"),
                is_boilerplate=h in boilerplate,
            )
            for h in headings
        ]

    monkeypatch.setattr(
        "backend.knowledge.documents.pipeline.classify_headings", fake_classify
    )
    pipeline._graph = None


class TestPipelineHappyPath:
    async def test_success_persists_chunks_and_flips_status(
        self, monkeypatch, sample_pdf
    ):
        _mock_parser(monkeypatch)
        _mock_classifier(
            monkeypatch,
            {
                "Health > Medication": "sick_policy",
                "Health > Immunizations": "sick_policy",
                "Hours": "hours",
            },
        )

        result = await pipeline.ingest(sample_pdf, "handbook.pdf")
        doc_id = result["document_id"]

        doc = await storage.get_document(doc_id, include_chunks=True)
        assert doc is not None
        assert doc.status == "ready"
        assert doc.page_count == 3
        assert doc.chunk_count == len(doc.chunks)
        assert len(doc.chunks) >= 3
        assert set(doc.topics) == {"hours", "sick_policy"}
        assert {c.topic for c in doc.chunks} == {"hours", "sick_policy"}


class TestPipelineDedup:
    async def test_duplicate_checksum_short_circuits(self, monkeypatch, sample_pdf):
        _mock_parser(monkeypatch)
        _mock_classifier(monkeypatch)

        first = await pipeline.ingest(sample_pdf, "handbook.pdf")
        first_id = first["document_id"]

        second = await pipeline.ingest(sample_pdf, "handbook.pdf")
        assert second["document_id"] == first_id
        assert second.get("short_circuited") is True

        all_docs = await storage.list_documents()
        assert len(all_docs) == 1


class TestPipelineFailures:
    async def test_parse_failure_records_error(self, monkeypatch, sample_pdf):
        import backend.knowledge.documents.pipeline as pl

        async def failing_parse(state):
            return {**state, "error": "parse: simulated boom"}

        monkeypatch.setattr(pl, "_node_parse", failing_parse)
        _mock_classifier(monkeypatch)
        pl._graph = None

        result = await pipeline.ingest(sample_pdf, "handbook.pdf")
        doc = await storage.get_document(result["document_id"], include_chunks=True)
        assert doc is not None
        assert doc.status == "failed"
        assert doc.error_message is not None
        assert "parse" in doc.error_message
        assert doc.chunks == []

    async def test_classify_failure_records_error(self, monkeypatch, sample_pdf):
        _mock_parser(monkeypatch)
        import backend.knowledge.documents.pipeline as pl

        async def failing_classify(state):
            return {**state, "error": "classify: simulated"}

        monkeypatch.setattr(pl, "_node_classify", failing_classify)
        pl._graph = None

        result = await pipeline.ingest(sample_pdf, "handbook.pdf")
        doc = await storage.get_document(result["document_id"], include_chunks=True)
        assert doc is not None
        assert doc.status == "failed"
        assert doc.chunks == []


class TestPipelineBoilerplate:
    async def test_boilerplate_sections_are_dropped(self, monkeypatch, sample_pdf):
        _mock_parser(monkeypatch)
        _mock_classifier(
            monkeypatch,
            topic_map={
                "Health > Medication": "sick_policy",
                "Health > Immunizations": "sick_policy",
            },
            boilerplate={"Hours"},
        )

        result = await pipeline.ingest(sample_pdf, "handbook.pdf")
        doc = await storage.get_document(result["document_id"], include_chunks=True)
        assert doc is not None
        assert doc.status == "ready"
        assert all(c.heading_path != "Hours" for c in doc.chunks)
        assert "other" not in doc.topics  # boilerplate section's topic not counted
