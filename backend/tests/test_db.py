"""Unit tests for the database layer.

Uses a temporary in-memory SQLite database for each test to avoid
side effects between tests or on real data.
"""
import pytest

from backend.db import database as db_mod
from backend.db.conversations import insert_conversation, get_conversation, list_conversations
from backend.db.triage import (
    insert_triage_item, get_open_triage, get_triage_item,
    resolve_triage_item, dismiss_triage_item, get_triage_stats,
)
from backend.db.overrides import (
    insert_override, find_override, list_overrides, delete_override,
)
from backend.db.config import get_config, set_config, get_all_config


@pytest.fixture(autouse=True)
async def fresh_db(tmp_path, monkeypatch):
    """Provide a clean temp-file database for every test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("backend.settings.settings.database_path", db_path)
    db_mod._db = None
    await db_mod.init_db()
    yield
    await db_mod.close_db()


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

class TestConversations:

    async def test_insert_and_get(self):
        cid = await insert_conversation(
            question="Are you open today?",
            answer="Yes!",
            intent="lookup",
            topic="hours",
            confidence=0.95,
        )
        assert isinstance(cid, int)
        row = await get_conversation(cid)
        assert row is not None
        assert row["question"] == "Are you open today?"
        assert row["answer"] == "Yes!"
        assert row["intent"] == "lookup"
        assert row["topic"] == "hours"
        assert row["confidence"] == 0.95

    async def test_get_nonexistent(self):
        assert await get_conversation(9999) is None

    async def test_list_all(self):
        await insert_conversation(question="Q1", intent="lookup", topic="hours")
        await insert_conversation(question="Q2", intent="policy", topic="meals")
        rows = await list_conversations()
        assert len(rows) == 2

    async def test_list_filter_by_intent(self):
        await insert_conversation(question="Q1", intent="lookup", topic="hours")
        await insert_conversation(question="Q2", intent="policy", topic="meals")
        rows = await list_conversations(intent="lookup")
        assert len(rows) == 1
        assert rows[0]["intent"] == "lookup"

    async def test_list_filter_by_topic(self):
        await insert_conversation(question="Q1", intent="lookup", topic="hours")
        await insert_conversation(question="Q2", intent="lookup", topic="tuition")
        rows = await list_conversations(topic="tuition")
        assert len(rows) == 1
        assert rows[0]["topic"] == "tuition"

    async def test_list_filter_by_escalated(self):
        await insert_conversation(question="Q1", escalated=False)
        await insert_conversation(question="Q2", escalated=True, escalation_reason="sensitive")
        rows = await list_conversations(escalated=True)
        assert len(rows) == 1
        assert rows[0]["escalated"]

    async def test_list_pagination(self):
        for i in range(5):
            await insert_conversation(question=f"Q{i}")
        page = await list_conversations(limit=2, offset=0)
        assert len(page) == 2
        page2 = await list_conversations(limit=2, offset=2)
        assert len(page2) == 2

    async def test_guardrail_flags_stored_as_json(self):
        cid = await insert_conversation(
            question="test",
            guardrail_flags=["flag_a", "flag_b"],
        )
        row = await get_conversation(cid)
        assert '"flag_a"' in row["guardrail_flags"]
        assert '"flag_b"' in row["guardrail_flags"]


# ---------------------------------------------------------------------------
# Triage
# ---------------------------------------------------------------------------

class TestTriage:

    async def _make_conversation(self, **kwargs):
        defaults = {"question": "test question", "intent": "lookup", "topic": "hours"}
        defaults.update(kwargs)
        return await insert_conversation(**defaults)

    async def test_insert_and_get(self):
        cid = await self._make_conversation()
        tid = await insert_triage_item(conversation_id=cid, priority="high")
        item = await get_triage_item(tid)
        assert item is not None
        assert item["priority"] == "high"
        assert item["status"] == "open"
        assert item["question"] == "test question"

    async def test_get_open_triage(self):
        cid = await self._make_conversation()
        await insert_triage_item(conversation_id=cid, priority="high")
        items = await get_open_triage()
        assert len(items) == 1

    async def test_get_open_triage_filter_priority(self):
        c1 = await self._make_conversation(question="Q1")
        c2 = await self._make_conversation(question="Q2")
        await insert_triage_item(conversation_id=c1, priority="high")
        await insert_triage_item(conversation_id=c2, priority="normal")
        high = await get_open_triage(priority="high")
        assert len(high) == 1
        assert high[0]["priority"] == "high"

    async def test_resolve(self):
        cid = await self._make_conversation()
        tid = await insert_triage_item(conversation_id=cid)
        await resolve_triage_item(tid, resolved_by="maria", resolution_text="Done")
        item = await get_triage_item(tid)
        assert item["status"] == "resolved"
        assert item["resolved_by"] == "maria"
        assert item["resolution_text"] == "Done"
        # resolved items should not appear in open list
        assert len(await get_open_triage()) == 0

    async def test_dismiss(self):
        cid = await self._make_conversation()
        tid = await insert_triage_item(conversation_id=cid)
        await dismiss_triage_item(tid)
        item = await get_triage_item(tid)
        assert item["status"] == "dismissed"
        assert len(await get_open_triage()) == 0

    async def test_get_nonexistent(self):
        assert await get_triage_item(9999) is None

    async def test_high_priority_sorted_first(self):
        c1 = await self._make_conversation(question="Normal Q")
        c2 = await self._make_conversation(question="High Q")
        await insert_triage_item(conversation_id=c1, priority="normal")
        await insert_triage_item(conversation_id=c2, priority="high")
        items = await get_open_triage()
        assert items[0]["priority"] == "high"

    async def test_stats(self):
        c1 = await self._make_conversation(topic="hours")
        c2 = await self._make_conversation(topic="hours")
        c3 = await self._make_conversation(topic="other", topic_guess="nap_mats")
        await insert_triage_item(conversation_id=c1)
        await insert_triage_item(conversation_id=c2)
        await insert_triage_item(conversation_id=c3)
        stats = await get_triage_stats()
        assert stats["open_count"] == 3
        assert any(t["topic"] == "hours" and t["cnt"] == 2 for t in stats["by_topic"])
        assert any(t["topic_guess"] == "nap_mats" for t in stats["novel_topics"])


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------

class TestOverrides:

    async def test_insert_and_list(self):
        oid = await insert_override(
            topic="holidays",
            question_pattern="Are you open Christmas Eve?",
            answer="We close at noon on Christmas Eve.",
        )
        assert isinstance(oid, int)
        overrides = await list_overrides()
        assert len(overrides) == 1
        assert overrides[0]["topic"] == "holidays"

    async def test_find_override_matching(self):
        await insert_override(
            topic="holidays",
            question_pattern="Are you open Christmas Eve?",
            answer="We close at noon.",
        )
        match = await find_override("Are you open on Christmas Eve?", topic="holidays")
        assert match is not None
        assert "noon" in match["answer"]

    async def test_find_override_no_match(self):
        await insert_override(
            topic="holidays",
            question_pattern="Are you open Christmas Eve?",
            answer="We close at noon.",
        )
        match = await find_override("What is the meaning of life?", topic="holidays")
        assert match is None

    async def test_find_override_filters_by_topic(self):
        await insert_override(
            topic="tuition",
            question_pattern="What is infant tuition?",
            answer="$1800",
        )
        match = await find_override("What is infant tuition?", topic="holidays")
        assert match is None
        match = await find_override("What is infant tuition?", topic="tuition")
        assert match is not None

    async def test_delete(self):
        oid = await insert_override(
            topic="hours",
            question_pattern="test",
            answer="test answer",
        )
        await delete_override(oid)
        overrides = await list_overrides()
        assert len(overrides) == 0


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestConfig:

    async def test_set_and_get(self):
        await set_config("center_name", "Test Center")
        assert await get_config("center_name") == "Test Center"

    async def test_get_missing(self):
        assert await get_config("nonexistent_key") is None

    async def test_upsert(self):
        await set_config("key", "value1")
        await set_config("key", "value2")
        assert await get_config("key") == "value2"

    async def test_get_all(self):
        await set_config("a", "1")
        await set_config("b", "2")
        all_config = await get_all_config()
        assert all_config == {"a": "1", "b": "2"}
