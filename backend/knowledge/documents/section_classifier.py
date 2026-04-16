"""LLM topic tagger for PDF sections.

Walks the heading paths produced by :mod:`backend.knowledge.documents
.chunker` and asks ``settings.classifier_model`` to assign each one a topic
from the same closed vocabulary used by the parent-chat classifier (see
:mod:`backend.prompts.classifier`), plus a boilerplate flag so signature
pages and TOC-style summaries can be dropped from retrieval.

Headings are batched ``BATCH_SIZE`` at a time to keep LLM cost low; any
batch failure (invalid JSON, API error) degrades to ``topic='other',
is_boilerplate=False`` for that batch so ingestion never blocks on the
classifier.
"""
import json
import logging
from dataclasses import dataclass

import litellm

from backend.prompts.section_classifier import (
    SECTION_CLASSIFIER_SYSTEM_PROMPT,
    SECTION_CLASSIFIER_USER_PROMPT,
)
from backend.settings import settings

logger = logging.getLogger(__name__)

VALID_TOPICS = {
    "hours", "tuition", "sick_policy", "meals", "tours", "enrollment",
    "custody", "billing", "staff", "curriculum", "safety", "holidays", "other",
}

BATCH_SIZE = 20


@dataclass
class SectionTag:
    topic: str
    is_boilerplate: bool


async def classify_headings(headings: list[str]) -> list[SectionTag]:
    """Assign a topic + boilerplate flag to each heading.

    Headings are batched into groups of BATCH_SIZE LLM calls. On any failure
    (invalid JSON, missing indices), falls back to topic="other" /
    is_boilerplate=False for the affected headings.
    """
    if not headings:
        return []

    tags: list[SectionTag | None] = [None] * len(headings)

    for batch_start in range(0, len(headings), BATCH_SIZE):
        batch = headings[batch_start : batch_start + BATCH_SIZE]
        batch_tags = await _classify_batch(batch)
        for offset, tag in enumerate(batch_tags):
            tags[batch_start + offset] = tag

    return [t if t is not None else SectionTag("other", False) for t in tags]


async def _classify_batch(batch: list[str]) -> list[SectionTag]:
    numbered = "\n".join(f"{i}. {h}" for i, h in enumerate(batch))

    try:
        response = await litellm.acompletion(
            model=settings.classifier_model,
            messages=[
                {"role": "system", "content": SECTION_CLASSIFIER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": SECTION_CLASSIFIER_USER_PROMPT.format(headings=numbered),
                },
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
    except Exception as e:
        logger.warning("Section classifier call failed: %s", e)
        return [SectionTag("other", False) for _ in batch]

    sections = data.get("sections", [])
    by_index: dict[int, SectionTag] = {}
    for item in sections:
        idx = item.get("index")
        if not isinstance(idx, int) or not (0 <= idx < len(batch)):
            continue
        topic = item.get("topic", "other")
        if topic not in VALID_TOPICS:
            topic = "other"
        is_boilerplate = bool(item.get("is_boilerplate", False))
        by_index[idx] = SectionTag(topic=topic, is_boilerplate=is_boilerplate)

    return [by_index.get(i, SectionTag("other", False)) for i in range(len(batch))]
