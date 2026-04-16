"""LangGraph subgraph for PDF ingestion.

Orchestrates the document pipeline as a state machine:

    checksum -> dedup -> parse -> chunk -> classify -> summarize -> persist -> finalize

``dedup`` short-circuits to ``finalize`` for a PDF already stored with
``status='ready'``. Any node failure sets ``state['error']`` and routes
straight to ``finalize``, which flips the row to ``status='failed'`` with
the error message preserved so the operator can surface it later.

The graph is built lazily and memoized in ``_graph`` — tests reset it to
pick up monkey-patched nodes. ``ingest(file_path, filename)`` is the public
entry point used by :mod:`backend.knowledge.documents.bootstrap` and the
module-level ``create()``.
"""
import logging
from typing import TypedDict

import litellm
from langgraph.graph import END, StateGraph

from backend.knowledge.documents import storage
from backend.knowledge.documents.checksum import compute_file_checksum
from backend.knowledge.documents.chunker import ChunkDraft, chunk_markdown
from backend.knowledge.documents.section_classifier import (
    SectionTag,
    classify_headings,
)
from backend.prompts.document_summary import (
    DOCUMENT_SUMMARY_SYSTEM_PROMPT,
    DOCUMENT_SUMMARY_USER_PROMPT,
)
from backend.settings import settings

logger = logging.getLogger(__name__)

SUMMARY_EXCERPT_CHAR_LIMIT = 6000


class IngestState(TypedDict, total=False):
    file_path: str
    filename: str
    checksum: str
    document_id: int
    markdown: str
    page_count: int | None
    chunk_drafts: list[ChunkDraft]
    section_tags: dict[str, SectionTag]
    topics: list[str]
    summary: str
    error: str
    short_circuited: bool


async def _node_checksum(state: IngestState) -> IngestState:
    checksum = compute_file_checksum(state["file_path"])
    return {**state, "checksum": checksum}


async def _node_dedup(state: IngestState) -> IngestState:
    existing = await storage.get_document_by_checksum(state["checksum"])
    if existing and existing.status == "ready":
        logger.info(
            "Document %s already ingested (doc_id=%d); short-circuiting",
            state["filename"],
            existing.id,
        )
        return {
            **state,
            "document_id": existing.id,
            "short_circuited": True,
        }

    if existing:
        doc_id = existing.id
        await storage.mark_processing(doc_id)
    else:
        doc_id = await storage.insert_document_pending(
            state["checksum"], state["filename"]
        )
        await storage.mark_processing(doc_id)
    return {**state, "document_id": doc_id, "short_circuited": False}


async def _node_parse(state: IngestState) -> IngestState:
    try:
        from backend.knowledge.documents.parser import parse_pdf

        result = parse_pdf(state["file_path"])
        return {
            **state,
            "markdown": result.markdown,
            "page_count": result.page_count,
        }
    except Exception as e:
        logger.exception("Parse failed for %s", state["filename"])
        return {**state, "error": f"parse: {e}"}


async def _node_chunk(state: IngestState) -> IngestState:
    if state.get("error"):
        return state
    try:
        drafts = chunk_markdown(state["markdown"])
        return {**state, "chunk_drafts": drafts}
    except Exception as e:
        logger.exception("Chunking failed for %s", state["filename"])
        return {**state, "error": f"chunk: {e}"}


async def _node_classify(state: IngestState) -> IngestState:
    if state.get("error"):
        return state
    drafts = state.get("chunk_drafts", [])
    headings = [d.heading_path for d in drafts]
    try:
        tags = await classify_headings(headings)
    except Exception as e:
        logger.exception("Classification failed for %s", state["filename"])
        return {**state, "error": f"classify: {e}"}

    by_heading: dict[str, SectionTag] = {}
    topic_set: set[str] = set()
    for heading, tag in zip(headings, tags):
        by_heading[heading] = tag
        if not tag.is_boilerplate:
            topic_set.add(tag.topic)

    return {
        **state,
        "section_tags": by_heading,
        "topics": sorted(topic_set),
    }


async def _node_summarize(state: IngestState) -> IngestState:
    """Generate a 2-3 sentence operator-facing description of the document.

    Best-effort: a failure here is logged and does not block ingestion —
    the document still gets persisted, just without a summary.
    """
    if state.get("error"):
        return state

    drafts = state.get("chunk_drafts", [])
    tags = state.get("section_tags", {})
    kept_headings = [
        d.heading_path
        for d in drafts
        if not tags.get(d.heading_path, SectionTag("other", False)).is_boilerplate
    ]

    heading_lines = "\n".join(f"- {h}" for h in kept_headings[:30]) or "(none)"
    excerpt = (state.get("markdown") or "")[:SUMMARY_EXCERPT_CHAR_LIMIT]
    if not excerpt.strip():
        return state

    try:
        response = await litellm.acompletion(
            model=settings.classifier_model,
            messages=[
                {"role": "system", "content": DOCUMENT_SUMMARY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": DOCUMENT_SUMMARY_USER_PROMPT.format(
                        filename=state["filename"],
                        headings=heading_lines,
                        excerpt=excerpt,
                    ),
                },
            ],
            temperature=0.2,
        )
        summary = (response.choices[0].message.content or "").strip()
        return {**state, "summary": summary}
    except Exception:
        logger.exception("Summary generation failed for %s", state["filename"])
        return state


async def _node_persist(state: IngestState) -> IngestState:
    if state.get("error"):
        return state
    drafts = state.get("chunk_drafts", [])
    tags = state.get("section_tags", {})

    chunks: list[storage.DocumentChunk] = []
    for d in drafts:
        tag = tags.get(d.heading_path, SectionTag("other", False))
        if tag.is_boilerplate:
            continue
        chunks.append(
            storage.DocumentChunk(
                document_id=state["document_id"],
                chunk_index=d.chunk_index,
                heading_path=d.heading_path,
                topic=tag.topic,
                page_start=None,
                page_end=None,
                content=d.content,
            )
        )

    try:
        await storage.insert_chunks(state["document_id"], chunks)
        await storage.mark_ready(
            state["document_id"],
            page_count=state.get("page_count"),
            chunk_count=len(chunks),
            topics=state.get("topics", []),
            summary=state.get("summary"),
        )
    except Exception as e:
        logger.exception("Persist failed for %s", state["filename"])
        return {**state, "error": f"persist: {e}"}

    return state


async def _node_finalize(state: IngestState) -> IngestState:
    if state.get("error"):
        doc_id = state.get("document_id")
        if doc_id is not None:
            await storage.mark_failed(doc_id, state["error"])
    return state


def _route_after_dedup(state: IngestState) -> str:
    return "finalize" if state.get("short_circuited") else "parse"


def _route_after_parse(state: IngestState) -> str:
    return "finalize" if state.get("error") else "chunk"


def _route_after_chunk(state: IngestState) -> str:
    return "finalize" if state.get("error") else "classify"


def _route_after_classify(state: IngestState) -> str:
    return "finalize" if state.get("error") else "summarize"


def _route_after_summarize(state: IngestState) -> str:
    return "finalize" if state.get("error") else "persist"


def build_ingest_graph():
    builder = StateGraph(IngestState)
    builder.add_node("checksum", _node_checksum)
    builder.add_node("dedup", _node_dedup)
    builder.add_node("parse", _node_parse)
    builder.add_node("chunk", _node_chunk)
    builder.add_node("classify", _node_classify)
    builder.add_node("summarize", _node_summarize)
    builder.add_node("persist", _node_persist)
    builder.add_node("finalize", _node_finalize)

    builder.set_entry_point("checksum")
    builder.add_edge("checksum", "dedup")
    builder.add_conditional_edges(
        "dedup", _route_after_dedup, {"finalize": "finalize", "parse": "parse"}
    )
    builder.add_conditional_edges(
        "parse", _route_after_parse, {"finalize": "finalize", "chunk": "chunk"}
    )
    builder.add_conditional_edges(
        "chunk", _route_after_chunk, {"finalize": "finalize", "classify": "classify"}
    )
    builder.add_conditional_edges(
        "classify",
        _route_after_classify,
        {"finalize": "finalize", "summarize": "summarize"},
    )
    builder.add_conditional_edges(
        "summarize",
        _route_after_summarize,
        {"finalize": "finalize", "persist": "persist"},
    )
    builder.add_edge("persist", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_ingest_graph()
    return _graph


async def ingest(file_path: str, filename: str) -> IngestState:
    graph = get_graph()
    initial: IngestState = {"file_path": file_path, "filename": filename}
    return await graph.ainvoke(initial)
