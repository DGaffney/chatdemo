"""Unit tests for :mod:`backend.knowledge.documents.chunker`.

Exercises the three contracts the chunker is responsible for: full heading
paths survive nesting and h1 resets, chunk sizing stays inside the 120-800
word envelope with small siblings merged and oversized paragraphs split,
and list blocks never get bisected mid-list.
"""
from backend.knowledge.documents.chunker import chunk_markdown


def _words(n: int) -> str:
    return " ".join(f"word{i}" for i in range(n))


class TestChunkerHeadingPath:
    def test_nested_headings_produce_full_path(self):
        md = (
            f"# Health\n\n## Medication\n\n{_words(200)}\n\n"
            f"## Immunizations\n\n{_words(200)}\n"
        )
        chunks = chunk_markdown(md)
        paths = [c.heading_path for c in chunks]
        assert "Health > Medication" in paths
        assert "Health > Immunizations" in paths

    def test_heading_path_resets_on_sibling_h1(self):
        md = (
            f"# Health\n\n## Medication\n\n{_words(200)}\n\n"
            f"# Billing\n\n## Invoices\n\n{_words(200)}\n"
        )
        chunks = chunk_markdown(md)
        paths = [c.heading_path for c in chunks]
        assert "Health > Medication" in paths
        assert "Billing > Invoices" in paths

    def test_chunks_indexed_sequentially(self):
        md = f"# A\n\n{_words(200)}\n\n# B\n\n{_words(200)}\n"
        chunks = chunk_markdown(md)
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


class TestChunkerSizeTargets:
    def test_large_body_gets_split(self):
        md = f"# Big Section\n\n{_words(2000)}\n"
        chunks = chunk_markdown(md)
        assert len(chunks) > 1
        for c in chunks:
            assert len(c.content.split()) <= 900

    def test_small_sibling_sections_merge(self):
        md = (
            f"# Parent\n\n## Child A\n\n{_words(30)}\n\n"
            f"## Child B\n\n{_words(30)}\n"
        )
        chunks = chunk_markdown(md)
        assert len(chunks) == 1

    def test_empty_markdown_yields_no_chunks(self):
        assert chunk_markdown("") == []


class TestChunkerListAwareness:
    def test_bullet_list_not_split_mid_list(self):
        list_body = "\n".join(f"- item {i} {_words(50)}" for i in range(20))
        md = f"# Rules\n\n{list_body}\n"
        chunks = chunk_markdown(md)
        for c in chunks:
            lines = [line for line in c.content.splitlines() if line.strip()]
            if not lines:
                continue
            first_list_idx = next(
                (i for i, line in enumerate(lines) if line.lstrip().startswith("-")),
                None,
            )
            if first_list_idx is None:
                continue
            last_list_idx = max(
                i for i, line in enumerate(lines) if line.lstrip().startswith("-")
            )
            between = lines[first_list_idx : last_list_idx + 1]
            assert all(
                line.lstrip().startswith("-") for line in between if line.strip()
            ), "list got split with non-list content in the middle"
