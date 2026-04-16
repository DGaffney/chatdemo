"""Backend test suite.

Unit tests run under pytest with ``asyncio_mode = auto`` (see
``pyproject.toml``) and each test that touches the database gets its own
temp-file SQLite via an autouse fixture. ``run_evals.py`` is a separate
integration-level eval harness that talks to a live server.
"""
