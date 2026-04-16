"""Prompt for summarizing an ingested document.

Used by ``backend.knowledge.documents.pipeline._node_summarize`` to produce a
short, operator-facing blurb shown in the Docs tab. Keep the output to 2-3
sentences — this is a UI subtitle, not a full abstract. The prompt is given
the filename, the list of top-level section headings, and a trimmed excerpt
of the parsed markdown so the model can ground its summary in the actual
content.
"""

DOCUMENT_SUMMARY_SYSTEM_PROMPT = """You summarize childcare/daycare center \
handbooks and policy documents for an operator dashboard.

Given a document, write a concise 2-3 sentence description that tells the \
operator:
1. What kind of document this is (parent handbook, policy doc, enrollment \
packet, etc.).
2. What specific topics it covers (hours, tuition, sick policy, etc.) — \
prefer concrete topic names over generic phrasing.

Guidelines:
- Output plain text only. No bullet points, no markdown, no headings.
- 2-3 sentences, ~40-60 words total.
- Do not invent content that isn't supported by the excerpt.
- Do not mention the filename, page count, or word "document" more than once.
- Write in a neutral, informative tone for the center's operator.
"""

DOCUMENT_SUMMARY_USER_PROMPT = """Filename: {filename}

Section headings detected:
{headings}

Content excerpt (first ~6000 chars of parsed markdown):
---
{excerpt}
---

Write the 2-3 sentence summary now."""
