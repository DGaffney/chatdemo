"""SQLite data-access layer.

All persistence lives here as small async helpers built on ``aiosqlite``:

- :mod:`backend.db.database`      — connection lifecycle + schema bootstrap
- :mod:`backend.db.conversations` — one row per parent turn (question, answer,
  classification, escalation metadata)
- :mod:`backend.db.triage`        — operator triage queue with priority +
  resolution state
- :mod:`backend.db.overrides`     — operator-authored answer overrides
- :mod:`backend.db.config`        — per-center key/value configuration
"""
