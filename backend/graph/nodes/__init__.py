"""Individual LangGraph nodes used by :mod:`backend.graph.graph`.

Each module exports one or more async functions that take a ``GraphState``
and return an updated ``GraphState``:

- :mod:`backend.graph.nodes.guardrails` — pre- and post-call guardrails
- :mod:`backend.graph.nodes.classify`   — intent x topic classification
- :mod:`backend.graph.nodes.retrieve`   — handbook + override retrieval
- :mod:`backend.graph.nodes.answer`     — per-intent LLM answer generation
- :mod:`backend.graph.nodes.escalate`   — empathetic escalation handoff
"""
