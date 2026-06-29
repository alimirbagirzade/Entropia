"""Centralized, environment-driven configuration (Module 20 §12).

Secrets and credentials are loaded from the environment only. They are never
written to logs, audit payloads, or the frontend build.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide singleton. Cleared in tests via get_settings.cache_clear()."""
    return Settings()
