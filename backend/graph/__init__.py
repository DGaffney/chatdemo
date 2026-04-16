"""LangGraph orchestration for the parent-chat request lifecycle.

- :mod:`backend.graph.state` defines the ``GraphState`` TypedDict shared
  between nodes.
- :mod:`backend.graph.graph` assembles the top-level graph: pre-guardrail,
  classify, retrieve, answer/escalate, post-guardrail, log.
- :mod:`backend.graph.nodes` contains the individual node implementations.
"""
