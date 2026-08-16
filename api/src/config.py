"""Application configuration — os.environ driven, SQLite default.

Values are read lazily from the environment so tests can override them
per-fixture without import-order side effects.
"""

import os
import sys

TESTING = os.getenv("AGENTTRACE_TESTING") == "1" or "pytest" in sys.modules


class Settings:
    @property
    def app_name(self) -> str:
        return "AgentTrace"

    @property
    def debug(self) -> bool:
        return os.getenv("DEBUG", "false").lower() == "true"

    @property
    def database_path(self) -> str:
        return os.getenv(
            "AGENTTRACE_DB_PATH", "./agenttrace.sqlite"
        )

    @property
    def memory_path(self) -> str:
        return os.getenv("AGENTTRACE_MEMORY_PATH", "./MEMORY.md")

    @property
    def max_steps(self) -> int:
        return int(os.getenv("AGENTTRACE_MAX_STEPS", "20"))

    @property
    def tool_timeout_s(self) -> int:
        return int(os.getenv("AGENTTRACE_TOOL_TIMEOUT_S", "60"))

    @property
    def cors_origins(self) -> list[str]:
        base = os.getenv("AGENTTRACE_CORS_ORIGINS", "")
        origins = [
            "http://localhost:3000",
            "http://localhost:3001",
        ]
        if base:
            origins.extend(o.strip() for o in base.split(",") if o.strip())
        return origins

    # Live tool credentials (Module 3) — read from env, never hard-coded.
    @property
    def supabase_url(self) -> str | None:
        return os.getenv("SUPABASE_URL") or None

    @property
    def supabase_service_key(self) -> str | None:
        return os.getenv("SUPABASE_SERVICE_KEY") or None

    @property
    def gmail_client_id(self) -> str | None:
        return os.getenv("GMAIL_CLIENT_ID") or None

    @property
    def gmail_client_secret(self) -> str | None:
        return os.getenv("GMAIL_CLIENT_SECRET") or None

    @property
    def gmail_refresh_token(self) -> str | None:
        return os.getenv("GMAIL_REFRESH_TOKEN") or None


settings = Settings()