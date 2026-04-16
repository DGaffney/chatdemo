"""Knowledge retrieval layer.

The three-tier knowledge model (operator overrides -> center handbook ->
generic fallback) is implemented here:

- :mod:`backend.knowledge.loader`    — markdown handbook loader and shared
  in-memory chunk pool
- :mod:`backend.knowledge.retriever` — keyword/TF-IDF retrieval over the pool
- :mod:`backend.knowledge.overrides` — override-first wrapper the graph calls
- :mod:`backend.knowledge.documents` — PDF document ingestion pipeline that
  feeds additional chunks into the same pool
"""
