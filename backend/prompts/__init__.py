"""LLM prompt templates used by the graph nodes.

Templates are plain Python strings with ``{placeholder}`` markers and are
kept separate from node logic so they can be iterated on without touching
orchestration code:

- :mod:`backend.prompts.classifier`         — intent x topic classifier
- :mod:`backend.prompts.lookup_answer`      — factual-question answers
- :mod:`backend.prompts.policy_answer`      — conservative policy answers
- :mod:`backend.prompts.lead_capture`       — tour / enrollment leads
- :mod:`backend.prompts.escalate`           — sensitive-topic handoff
- :mod:`backend.prompts.section_classifier` — PDF section topic tagging
"""
