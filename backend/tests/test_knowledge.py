"""Unit tests for the knowledge loader and retriever.

These test handbook loading, chunk splitting, and keyword retrieval
without any LLM calls.
"""
import pytest

from backend.knowledge.loader import load_handbook, get_chunks, Chunk, _split_by_heading
from backend.knowledge.retriever import retrieve, RetrievalResult, _tokenize


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class TestSplitByHeading:

    def test_splits_on_h1(self):
        md = "# Title\nSome content.\n# Second\nMore content."
        sections = _split_by_heading(md)
        assert len(sections) == 2
        assert sections[0][0] == "Title"
        assert sections[1][0] == "Second"

    def test_splits_on_h2(self):
        md = "## First\nA\n## Second\nB"
        sections = _split_by_heading(md)
        assert len(sections) == 2

    def test_preserves_content_before_first_heading(self):
        md = "Intro text\n# Heading\nBody"
        sections = _split_by_heading(md)
        assert len(sections) == 2
        assert "Intro text" in sections[0][1]

    def test_empty_string(self):
        sections = _split_by_heading("")
        assert len(sections) == 1
        assert sections[0][1] == ""


class TestLoadHandbook:

    def test_loads_chunks_from_handbook(self):
        chunks = load_handbook()
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunks_have_required_fields(self):
        chunks = load_handbook()
        for chunk in chunks:
            assert chunk.content
            assert chunk.source
            assert chunk.category

    def test_loads_center_specific_and_generic(self):
        chunks = load_handbook()
        sources = {c.source for c in chunks}
        assert any(not s.startswith("_generic/") for s in sources), "Missing center-specific content"
        assert any(s.startswith("_generic/") for s in sources), "Missing generic content"

    def test_expected_categories_present(self):
        chunks = load_handbook()
        categories = {c.category for c in chunks}
        for expected in ["hours", "tuition", "holidays", "sick_policy", "meals", "tours"]:
            assert expected in categories, f"Missing category: {expected}"

    def test_get_chunks_returns_loaded_chunks(self):
        loaded = load_handbook()
        got = get_chunks()
        assert got == loaded
        assert len(got) > 0


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

class TestTokenize:

    def test_basic_tokenization(self):
        tokens = _tokenize("Hello, World! 123")
        assert tokens == ["hello", "world", "123"]

    def test_empty_string(self):
        assert _tokenize("") == []


class TestRetrieve:

    @pytest.fixture(autouse=True)
    def _load(self):
        load_handbook()

    def test_returns_results_for_known_topic(self):
        results = retrieve("Are you open on Veterans Day?", topic="holidays")
        assert len(results) > 0
        assert all(isinstance(r, RetrievalResult) for r in results)

    def test_top_result_is_holidays_for_veterans_day(self):
        results = retrieve("Are you open on Veterans Day?", topic="holidays")
        assert results[0].chunk.source == "holidays.md"

    def test_top_result_is_tuition_for_tuition_question(self):
        results = retrieve("How much is tuition for infants?", topic="tuition")
        assert results[0].chunk.source == "tuition.md"

    def test_top_result_is_sick_policy_for_fever_question(self):
        results = retrieve("My daughter has a 100.4 fever", topic="sick_policy")
        assert results[0].chunk.source == "sick_policy.md"

    def test_top_result_is_hours_for_hours_question(self):
        results = retrieve("What are your operating hours?", topic="hours")
        assert results[0].chunk.source == "hours.md"

    def test_top_result_is_meals_for_lunch_question(self):
        results = retrieve("Do you provide lunch?", topic="meals")
        top_source = results[0].chunk.source
        assert top_source == "meals.md" or top_source == "_generic/meals.md"

    def test_top_result_is_tours_for_tour_question(self):
        results = retrieve("How do I schedule a tour?", topic="tours")
        assert results[0].chunk.source == "tours.md"

    def test_respects_top_k(self):
        results = retrieve("daycare information", top_k=2)
        assert len(results) <= 2

    def test_center_specific_preferred_over_generic(self):
        results = retrieve("sick child fever policy", topic="sick_policy")
        center_idx = None
        generic_idx = None
        for i, r in enumerate(results):
            if r.chunk.source == "sick_policy.md" and center_idx is None:
                center_idx = i
            if r.chunk.source == "_generic/sick_policy.md" and generic_idx is None:
                generic_idx = i
        if center_idx is not None and generic_idx is not None:
            assert center_idx < generic_idx

    def test_empty_query_returns_results(self):
        results = retrieve("")
        assert isinstance(results, list)

    def test_no_results_for_gibberish(self):
        results = retrieve("xyzzyplugh42 zork999")
        assert len(results) == 0
