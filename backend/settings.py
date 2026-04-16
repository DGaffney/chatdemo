"""Application settings loaded from environment variables and ``.env``.

Uses ``pydantic-settings`` to map env vars (case-insensitive) onto a typed
``Settings`` model. A single module-level ``settings`` instance is imported
throughout the codebase — do not instantiate ``Settings()`` elsewhere.

See the README for the full list of variables and defaults.
"""
import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    default_model: str = "anthropic/claude-sonnet-4-5"
    classifier_model: str = "anthropic/claude-haiku-4-5"

    langsmith_api_key: str = ""
    langsmith_project: str = "ai-front-desk"

    database_path: str = "data/frontdesk.db"
    handbook_path: str = "backend/handbook"
    documents_path: str = "docs"
    operator_email: str = "maria@sunrise-daycare.example"
    center_name: str = "Sunrise Early Learning"

    enable_citation_guardrail: bool = True
    enable_numeric_guardrail: bool = True
    confidence_threshold_lookup: float = 0.75
    confidence_threshold_policy: float = 0.65

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


if settings.langsmith_api_key:
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
