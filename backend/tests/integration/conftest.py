"""Integration fixtures — require a reachable PostgreSQL (skips otherwise).

Each test gets its own function-scoped async engine, created and disposed within
the test's own event loop (NullPool, no cross-loop connection sharing — this is
the pytest-asyncio-safe pattern). The schema is rebuilt per test for isolation.
When no database is reachable, every integration test is skipped.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.models import *  # noqa: F403 (register tables)

DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://entropia:entropia@localhost:5432/entropia"),
)


async def _reachable() -> bool:
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.connect():
            return True
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    if not await _reachable():
        pytest.skip(f"No PostgreSQL reachable at {DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with factory() as s:
            yield s
    finally:
        await engine.dispose()
