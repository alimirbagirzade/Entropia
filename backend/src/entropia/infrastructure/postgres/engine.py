"""Async SQLAlchemy engine + session factory (PostgreSQL 16)."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from entropia.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


# NOTE: there is deliberately NO ``session_scope`` helper here. Every caller
# opens its own session from ``get_session_factory`` and owns its transaction
# boundary explicitly — the API through ``apps/api/deps.py`` (one request = one
# tx), workers/jobs through their own ``async with factory()`` blocks. The old
# commit-on-exit wrapper had no callers and was deleted in I-12.
