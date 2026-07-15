"""Centralized, environment-driven configuration (Module 20 §12).

Secrets and credentials are loaded from the environment only. They are never
written to logs, audit payloads, or the frontend build.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Runtime ----
    environment: Environment = Field(default="local", alias="ENTROPIA_ENV")
    log_level: str = Field(default="INFO", alias="ENTROPIA_LOG_LEVEL")
    log_format: Literal["json", "console"] = Field(default="json", alias="ENTROPIA_LOG_FORMAT")

    # ---- API ----
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_base_path: str = Field(default="/api/v1", alias="API_BASE_PATH")
    api_cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:8080", alias="API_CORS_ORIGINS"
    )

    # ---- PostgreSQL ----
    database_url: str = Field(
        default="postgresql+asyncpg://entropia:entropia@localhost:5432/entropia",
        alias="DATABASE_URL",
    )

    # ---- Redis / queues ----
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    queue_namespace: str = Field(default="entropia", alias="QUEUE_NAMESPACE")

    # ---- Object storage ----
    object_storage_endpoint: str = Field(
        default="http://localhost:9000", alias="OBJECT_STORAGE_ENDPOINT"
    )
    object_storage_region: str = Field(default="us-east-1", alias="OBJECT_STORAGE_REGION")
    object_storage_access_key: str = Field(default="entropia", alias="OBJECT_STORAGE_ACCESS_KEY")
    object_storage_secret_key: str = Field(
        default="entropia-secret", alias="OBJECT_STORAGE_SECRET_KEY"
    )
    object_storage_bucket: str = Field(default="entropia-artifacts", alias="OBJECT_STORAGE_BUCKET")
    object_storage_use_ssl: bool = Field(default=False, alias="OBJECT_STORAGE_USE_SSL")

    # ---- Workers ----
    worker_concurrency: int = Field(default=4, alias="WORKER_CONCURRENCY")
    backtest_worker_concurrency: int = Field(default=2, alias="BACKTEST_WORKER_CONCURRENCY")

    # ---- Event fan-out (Module 20 §10) ----
    sse_poll_interval_seconds: float = Field(default=1.0, alias="SSE_POLL_INTERVAL_SECONDS")
    outbox_relay_batch_size: int = Field(default=200, alias="OUTBOX_RELAY_BATCH_SIZE")

    # ---- Scheduler / job recovery (Module 20 §6; INF-03/INF-09) ----
    job_stale_after_seconds: int = Field(default=600, alias="JOB_STALE_AFTER_SECONDS")
    job_redeliver_grace_seconds: int = Field(default=600, alias="JOB_REDELIVER_GRACE_SECONDS")

    # ---- Authentication (M1 §4 / Master §20) ----
    # "dev": trust the X-Actor-Id header (local/dev + test default).
    # "session": require a Bearer session token (human) or the service token (agent).
    auth_mode: Literal["dev", "session"] = Field(default="dev", alias="AUTH_MODE")
    auth_session_ttl_minutes: int = Field(default=720, alias="AUTH_SESSION_TTL_MINUTES")
    # Static service-line credential for non-human runtimes (agent/scheduler).
    # Empty string disables the service line entirely.
    service_token: str = Field(default="", alias="ENTROPIA_SERVICE_TOKEN")
    # First-Admin bootstrap (explicit operator opt-in). When set, a Sign Up whose
    # email matches (case-normalized) is provisioned as Admin — ONLY while no
    # active Admin exists. Empty string (default) disables the mechanism.
    bootstrap_admin_email: str = Field(default="", alias="ENTROPIA_BOOTSTRAP_ADMIN_EMAIL")
    # F-21: how long a re-authentication proof (POST /auth/reauth) stays valid
    # before a sensitive action (Trash Permanent Delete) must request a fresh one.
    reauth_proof_ttl_minutes: int = Field(default=5, alias="REAUTH_PROOF_TTL_MINUTES")

    # ---- Rate limiting (Module 20 §11; opt-in per deployment) ----
    rate_limit_enabled: bool = Field(default=False, alias="RATE_LIMIT_ENABLED")
    rate_limit_anonymous_per_minute: int = Field(default=60, alias="RATE_LIMIT_ANON_PER_MINUTE")
    rate_limit_authenticated_per_minute: int = Field(
        default=600, alias="RATE_LIMIT_AUTH_PER_MINUTE"
    )
    rate_limit_write_per_minute: int = Field(default=120, alias="RATE_LIMIT_WRITE_PER_MINUTE")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        """Alembic uses a synchronous driver; derive it from the async URL."""
        return self.database_url.replace("+asyncpg", "+psycopg2").replace(
            "postgresql+psycopg2", "postgresql"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _restrict_dev_auth_to_local(self) -> Settings:
        """F-22: ``AUTH_MODE=dev`` trusts the client-supplied ``X-Actor-Id``
        header outright (no login, no session, no token). That trust model is
        acceptable only in the explicitly-named local dev profile. Any other
        environment (``staging``, ``production``) MUST run ``AUTH_MODE=session``
        so every request is a real login + live session + server-resolved role
        — fail closed at startup rather than let a misconfigured deployment
        silently accept actor impersonation."""
        if self.environment != "local" and self.auth_mode == "dev":
            raise ValueError(
                "AUTH_MODE=dev is restricted to ENTROPIA_ENV=local (dev profile); "
                f"ENTROPIA_ENV={self.environment!r} requires AUTH_MODE=session."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide singleton. Cleared in tests via get_settings.cache_clear()."""
    return Settings()
