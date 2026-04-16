"""Operator dashboard REST endpoints.

Everything the operator UI needs to triage escalated questions, browse
conversation history, manage knowledge overrides, and view insights:

- ``/api/triage``                      list open triage items (priority-sorted)
- ``/api/triage/{id}``                 full triage detail
- ``/api/triage/{id}/resolve``         resolve + optionally promote the
  resolution to a :mod:`backend.db.overrides` row (the learning loop)
- ``/api/triage/{id}/dismiss``         dismiss without resolution
- ``/api/conversations``               paged conversation history w/ filters
- ``/api/conversations/{id}``          single conversation
- ``/api/stats``                       aggregate counts for dashboards
- ``/api/override`` + ``/api/overrides`` CRUD on operator answer overrides
"""
import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db.triage import (
    get_open_triage,
    get_triage_item,
    resolve_triage_item,
    dismiss_triage_item,
    get_triage_stats,
)
from backend.db.overrides import (
    insert_override,
    list_overrides,
    delete_override,
)
from backend.db.conversations import list_conversations, get_conversation
from backend.knowledge.documents import storage as document_storage
from backend.knowledge.loader import remove_chunks_for_document
from backend.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["operator"])


class ResolveRequest(BaseModel):
    resolution_text: str
    resolved_by: str = "operator"
    promote_to_override: bool = False
    override_topic: str | None = None


class OverrideRequest(BaseModel):
    topic: str
    question_pattern: str
    answer: str
    author: str = "operator"


@router.get("/triage")
async def get_triage(priority: str | None = None):
    items = await get_open_triage(priority=priority)
    return {"items": items, "count": len(items)}


@router.get("/triage/{triage_id}")
async def get_triage_detail(triage_id: int):
    item = await get_triage_item(triage_id)
    if not item:
        raise HTTPException(status_code=404, detail="Triage item not found")
    return item


@router.post("/triage/{triage_id}/resolve")
async def resolve_triage(triage_id: int, request: ResolveRequest):
    item = await get_triage_item(triage_id)
    if not item:
        raise HTTPException(status_code=404, detail="Triage item not found")

    await resolve_triage_item(
        triage_id,
        resolved_by=request.resolved_by,
        resolution_text=request.resolution_text,
    )

    override_id = None
    if request.promote_to_override:
        topic = request.override_topic or item.get("topic", "other")
        override_id = await insert_override(
            topic=topic,
            question_pattern=item["question"],
            answer=request.resolution_text,
            author=request.resolved_by,
            source_conversation_id=item["conversation_id"],
        )

    return {"status": "resolved", "override_id": override_id}


@router.post("/triage/{triage_id}/dismiss")
async def dismiss_triage(triage_id: int):
    item = await get_triage_item(triage_id)
    if not item:
        raise HTTPException(status_code=404, detail="Triage item not found")
    await dismiss_triage_item(triage_id)
    return {"status": "dismissed"}


@router.get("/conversations")
async def get_conversations(
    intent: str | None = None,
    topic: str | None = None,
    escalated: bool | None = None,
    limit: int = 50,
    offset: int = 0,
):
    convos = await list_conversations(
        intent=intent, topic=topic, escalated=escalated, limit=limit, offset=offset
    )
    return {"conversations": convos, "count": len(convos)}


@router.get("/conversations/{conversation_id}")
async def get_conversation_detail(conversation_id: int):
    convo = await get_conversation(conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@router.get("/stats")
async def get_stats():
    triage_stats = await get_triage_stats()

    from backend.db.database import get_db
    db = await get_db()

    cursor = await db.execute(
        "SELECT intent, COUNT(*) as cnt FROM conversations GROUP BY intent"
    )
    intent_dist = {row["intent"]: row["cnt"] for row in await cursor.fetchall()}

    cursor = await db.execute(
        "SELECT topic, COUNT(*) as cnt FROM conversations GROUP BY topic ORDER BY cnt DESC"
    )
    topic_dist = [dict(r) for r in await cursor.fetchall()]

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM conversations")
    total = (await cursor.fetchone())["cnt"]

    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM conversations WHERE escalated = 1"
    )
    escalated = (await cursor.fetchone())["cnt"]

    return {
        "total_conversations": total,
        "escalation_rate": (escalated / total * 100) if total > 0 else 0,
        "intent_distribution": intent_dist,
        "topic_distribution": topic_dist,
        "triage": triage_stats,
    }


@router.post("/override")
async def create_override(request: OverrideRequest):
    override_id = await insert_override(
        topic=request.topic,
        question_pattern=request.question_pattern,
        answer=request.answer,
        author=request.author,
    )
    return {"id": override_id, "status": "created"}


@router.get("/overrides")
async def get_overrides():
    overrides = await list_overrides()
    return {"overrides": overrides, "count": len(overrides)}


@router.delete("/overrides/{override_id}")
async def remove_override(override_id: int):
    await delete_override(override_id)
    return {"status": "deleted"}


def _document_to_dict(
    doc: document_storage.Document, sections: list[dict] | None = None
) -> dict:
    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "uploaded_at": doc.uploaded_at,
        "processed_at": doc.processed_at,
        "error_message": doc.error_message,
        "page_count": doc.page_count,
        "chunk_count": doc.chunk_count,
        "topics": doc.topics,
        "summary": doc.summary,
        "sections": sections or [],
    }


@router.get("/documents")
async def get_documents():
    docs = await document_storage.list_documents()
    sections_by_doc = await document_storage.list_sections_for_documents(
        [d.id for d in docs]
    )
    return {
        "documents": [
            _document_to_dict(d, sections_by_doc.get(d.id, [])) for d in docs
        ],
        "count": len(docs),
    }


@router.delete("/documents/{document_id}")
async def remove_document(document_id: int):
    doc = await document_storage.get_document(document_id, include_chunks=False)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    removed = await document_storage.delete_document(document_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Document not found")

    pruned = remove_chunks_for_document(document_id)

    file_path = os.path.join(settings.documents_path, doc.filename)
    file_deleted = False
    file_error: str | None = None
    if os.path.isfile(file_path):
        try:
            os.remove(file_path)
            file_deleted = True
        except OSError as e:
            file_error = str(e)
            logger.warning("Failed to delete %s: %s", file_path, e)

    return {
        "status": "deleted",
        "chunks_pruned": pruned,
        "file_deleted": file_deleted,
        "file_error": file_error,
    }
