"""Parent-facing chat endpoint.

Exposes ``POST /api/ask`` as a Server-Sent Events stream. The request is
handed to the LangGraph orchestrator (:mod:`backend.graph.graph`); once the
graph completes, the generated answer is chunked into pseudo-streamed
``token`` events followed by a final ``done`` event carrying classification
metadata (intent, topic, confidence, escalation flags, guardrail hits).

The chunking is cosmetic — the graph runs to completion before the first
token event is sent — but a small inter-chunk delay gives the frontend a
realistic "typing" UX without requiring token-level streaming from the
upstream model (and without streaming partial text that post-guardrails
might later redact).
"""
import asyncio
import json
import re
import uuid

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.graph.graph import run_parent_turn

router = APIRouter(tags=["parent"])

TYPING_CHUNK_DELAY_S = 0.025
TYPING_TOKEN_PATTERN = re.compile(r"\s+|\S+")


class AskRequest(BaseModel):
    question: str
    session_id: str | None = None
    parent_email: str | None = None


def _typing_chunks(text: str) -> list[str]:
    """Split on whitespace boundaries so markdown tokens stay intact while typing."""
    return TYPING_TOKEN_PATTERN.findall(text)


@router.post("/ask")
async def ask(request: AskRequest):
    session_id = request.session_id or str(uuid.uuid4())

    initial_state = {
        "question": request.question,
        "session_id": session_id,
        "parent_email": request.parent_email or "",
        "guardrail_flags": [],
        "blocked": False,
        "escalated": False,
    }

    async def event_generator():
        yield {"event": "status", "data": json.dumps({"status": "processing"})}

        result = await run_parent_turn(
            initial_state,
            langsmith_extra={
                "metadata": {"session_id": session_id},
                "tags": [f"session:{session_id}"],
            },
        )

        answer = result.get("answer", "")
        for chunk in _typing_chunks(answer):
            yield {
                "event": "token",
                "data": json.dumps({"type": "token", "content": chunk}),
            }
            await asyncio.sleep(TYPING_CHUNK_DELAY_S)

        metadata = {
            "type": "done",
            "session_id": session_id,
            "intent": result.get("intent"),
            "topic": result.get("topic"),
            "topic_guess": result.get("topic_guess"),
            "confidence": result.get("confidence"),
            "escalated": result.get("escalated", False),
            "escalation_reason": result.get("escalation_reason"),
            "policy_cited": result.get("policy_cited"),
            "guardrail_flags": result.get("guardrail_flags", []),
        }
        yield {"event": "done", "data": json.dumps(metadata)}

    return EventSourceResponse(event_generator())
