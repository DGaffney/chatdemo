"""Markdown handbook loader and shared in-memory chunk pool.

Reads ``settings.handbook_path`` (generic fallback first, then
center-specific files), parses YAML frontmatter via ``python-frontmatter``,
and splits each file on h1/h2/h3 headings into ``Chunk`` objects. The
module-level ``_chunks`` list is the single source of truth for the
retriever — ``extend_chunks()`` lets other sources (the document pipeline)
contribute chunks to the same pool so downstream code sees a uniform shape.

Loaded once at startup by :func:`backend.main.lifespan`; also re-run by the
onboarding endpoint after generating a new handbook.
"""
import os
import re
from dataclasses import dataclass, field

import frontmatter

from backend.settings import settings

_chunks: list["Chunk"] = []


@dataclass
class Chunk:
    content: str
    source: str
    category: str
    heading: str = ""
    metadata: dict = field(default_factory=dict)


def _split_by_heading(text: str) -> list[tuple[str, str]]:
    """Split markdown text into (heading, body) pairs."""
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in text.split("\n"):
        if re.match(r"^#{1,3}\s+", line):
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = line.strip("# ").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, "\n".join(current_lines).strip()))

    return sections


def _load_file(filepath: str, is_generic: bool = False) -> list[Chunk]:
    with open(filepath, "r") as f:
        post = frontmatter.load(f)

    category = post.metadata.get("category", "other")
    source_name = os.path.basename(filepath)
    if is_generic:
        source_name = f"_generic/{source_name}"

    sections = _split_by_heading(post.content)

    chunks = []
    for heading, body in sections:
        if not body.strip():
            continue
        chunks.append(
            Chunk(
                content=body,
                source=source_name,
                category=category,
                heading=heading,
                metadata=dict(post.metadata),
            )
        )
    return chunks


def load_handbook() -> list[Chunk]:
    global _chunks
    _chunks = []
    handbook_path = settings.handbook_path

    generic_dir = os.path.join(handbook_path, "_generic")
    if os.path.isdir(generic_dir):
        for fname in sorted(os.listdir(generic_dir)):
            if fname.endswith(".md"):
                _chunks.extend(_load_file(os.path.join(generic_dir, fname), is_generic=True))

    for fname in sorted(os.listdir(handbook_path)):
        full = os.path.join(handbook_path, fname)
        if fname.endswith(".md") and os.path.isfile(full):
            _chunks.extend(_load_file(full))

    return _chunks


def get_chunks() -> list[Chunk]:
    return _chunks


def extend_chunks(chunks: list[Chunk]) -> None:
    """Append additional chunks (e.g. from ingested documents) to the retrieval pool.

    Intended for callers that produce Chunks from sources other than the
    markdown handbook — the documents pipeline uses this at startup after
    hydrating from the SQLite `document_chunks` table.
    """
    _chunks.extend(chunks)


def remove_chunks_for_document(document_id: int) -> int:
    """Drop any chunks tagged with ``metadata['document_id'] == document_id``.

    Used when a PDF is deleted through the operator UI so the retriever
    stops seeing its content without requiring a restart. Returns the
    number of chunks removed.
    """
    global _chunks
    before = len(_chunks)
    _chunks = [c for c in _chunks if c.metadata.get("document_id") != document_id]
    return before - len(_chunks)
