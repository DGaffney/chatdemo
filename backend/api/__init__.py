"""HTTP route handlers for the FastAPI app.

Each submodule exposes a ``router`` that ``backend.main`` mounts under
``/api``:

- :mod:`backend.api.parent`     — parent-facing chat endpoint (SSE)
- :mod:`backend.api.operator`   — operator dashboard endpoints (triage,
  conversations, knowledge overrides, insights)
- :mod:`backend.api.onboarding` — center setup wizard
"""
