"""Prompts for batch section topic tagging during PDF ingestion.

Unlike the parent-chat classifier which runs per-question, this prompt
batches ~20 heading strings per LLM call and asks for a JSON array
pinning each index to a topic from the shared closed vocabulary plus a
``is_boilerplate`` flag. Used by :mod:`backend.knowledge.documents
.section_classifier` in the ingestion pipeline.
"""

SECTION_CLASSIFIER_SYSTEM_PROMPT = """\
You are a topic tagger for a daycare center's handbook. Given a list of section
headings from a parsed handbook, assign each heading exactly one topic from the
closed vocabulary below.

## Topic vocabulary

hours, tuition, sick_policy, meals, tours, enrollment, custody, billing, staff,
curriculum, safety, holidays, other

Use "other" only when no topic applies. When in doubt between two topics,
prefer the more specific one (e.g., "sick_policy" beats "safety" for a section
titled "Illness").

Also flag each section as boilerplate when it is clearly a signature-capture
form, acknowledgment page, or a duplicate table-of-contents-style summary —
these should be excluded from retrieval.

## Output format

Return valid JSON with exactly this shape:
{
  "sections": [
    {"index": <integer>, "topic": "<topic>", "is_boilerplate": <boolean>},
    ...
  ]
}

The index field MUST match the input index. Return one object per input heading.
"""

SECTION_CLASSIFIER_USER_PROMPT = """\
Classify these handbook section headings:

{headings}
"""
