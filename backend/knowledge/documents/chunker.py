"""Heading-aware markdown splitter for PDF-derived content.

Produces retrieval-sized chunks (target ~500 words, cap ~800) while
preserving structural context:

- Each chunk carries the full ``heading_path`` (e.g. "Health > Medication")
  so downstream citations can show provenance.
- Small sibling sections under a shared parent are merged to avoid
  sub-minimum chunks.
- Oversized sections are split on paragraph boundaries; a single runaway
  paragraph with no blanks falls back to TARGET_WORDS word-windowing.
- List blocks (``-``, ``*``, ``1.``) never get split mid-list.

Mirrors the ``_split_by_heading`` convention used by the markdown
handbook loader so both sources produce compatible chunk shapes.
"""
import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")

# Target token window. Tokens approximated as whitespace-separated words (~0.75
# real tokens per word on average); the 500-800 token target maps to roughly
# 400-650 words here, which is close enough for a handbook-sized corpus.
MIN_WORDS = 120
TARGET_WORDS = 500
MAX_WORDS = 800


@dataclass
class Section:
    heading_path: list[str]
    body: str
    order: int


@dataclass
class ChunkDraft:
    chunk_index: int
    heading_path: str
    content: str


def _split_sections(markdown: str) -> list[Section]:
    """Walk markdown, emitting one Section per leaf heading with its ancestors."""
    lines = markdown.splitlines()
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []  # (level, heading_text)
    current_heading_path: list[str] = []
    current_body: list[str] = []
    order = 0

    def flush():
        nonlocal order, current_body
        body = "\n".join(current_body).strip()
        if body:
            sections.append(
                Section(heading_path=list(current_heading_path), body=body, order=order)
            )
            order += 1
        current_body = []

    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            text = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, text))
            current_heading_path = [h for _, h in stack]
        else:
            current_body.append(line)

    flush()
    return sections


def _word_count(text: str) -> int:
    return len(text.split())


def _is_list_line(line: str) -> bool:
    return bool(LIST_RE.match(line))


def _split_long_body(body: str) -> list[str]:
    """Split a body exceeding MAX_WORDS on paragraph boundaries.

    Never splits inside a contiguous list block — list items stay together
    until the next blank line. Falls back to word-window slicing if a single
    paragraph exceeds MAX_WORDS.
    """
    if _word_count(body) <= MAX_WORDS:
        return [body]

    lines = body.splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []
    in_list = False

    for line in lines:
        is_list = _is_list_line(line)
        blank = not line.strip()

        if blank and not in_list:
            if current:
                blocks.append(current)
                current = []
            continue

        if is_list:
            in_list = True
        elif blank and in_list:
            in_list = False
            if current:
                blocks.append(current)
                current = []
            continue

        current.append(line)

    if current:
        blocks.append(current)

    pieces: list[str] = []
    buf: list[str] = []
    buf_words = 0
    for block in blocks:
        block_text = "\n".join(block)
        block_words = _word_count(block_text)

        if block_words > MAX_WORDS and not any(
            _is_list_line(line) for line in block
        ):
            if buf:
                pieces.append("\n\n".join(buf))
                buf = []
                buf_words = 0
            pieces.extend(_window_words(block_text))
            continue

        if buf and buf_words + block_words > MAX_WORDS:
            pieces.append("\n\n".join(buf))
            buf = [block_text]
            buf_words = block_words
        else:
            buf.append(block_text)
            buf_words += block_words

    if buf:
        pieces.append("\n\n".join(buf))

    return pieces


def _window_words(text: str) -> list[str]:
    """Slice a long run-on paragraph into TARGET_WORDS-sized windows."""
    words = text.split()
    if not words:
        return []
    out: list[str] = []
    for start in range(0, len(words), TARGET_WORDS):
        out.append(" ".join(words[start : start + TARGET_WORDS]))
    return out


def chunk_markdown(markdown: str) -> list[ChunkDraft]:
    """Split markdown into heading-aware retrieval chunks.

    Each emitted chunk corresponds to a leaf heading's body, optionally split
    further if it exceeds MAX_WORDS. Very small sibling sections get merged
    under their shared parent heading to meet MIN_WORDS.
    """
    sections = _split_sections(markdown)
    if not sections:
        return []

    merged: list[Section] = []
    i = 0
    while i < len(sections):
        sec = sections[i]
        words = _word_count(sec.body)

        if words >= MIN_WORDS or not merged or not sec.heading_path:
            merged.append(sec)
            i += 1
            continue

        prev = merged[-1]
        prev_parent = prev.heading_path[:-1] if prev.heading_path else []
        curr_parent = sec.heading_path[:-1] if sec.heading_path else []
        if prev_parent == curr_parent and _word_count(prev.body) + words <= TARGET_WORDS:
            prev.body = f"{prev.body}\n\n{sec.body}"
        else:
            merged.append(sec)
        i += 1

    drafts: list[ChunkDraft] = []
    idx = 0
    for sec in merged:
        heading_path = " > ".join(sec.heading_path) if sec.heading_path else ""
        for piece in _split_long_body(sec.body):
            drafts.append(
                ChunkDraft(
                    chunk_index=idx,
                    heading_path=heading_path,
                    content=piece,
                )
            )
            idx += 1
    return drafts
