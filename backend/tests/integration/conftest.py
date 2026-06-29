"""Integration fixtures — require a reachable PostgreSQL (skips otherwise).

Uses DATABASE_URL from the environment (the Docker stack default). Creates the
full schema via Base.metadata.create_all, yields an async session factory, and
drops the schema at the end. When no database is reachable, every integration
test is skipped — so the unit/contract suite still runs anywhere.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.models import *  # noqa: F403 (register tables)

DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://entropia:entropia@localhost:5432/entropia"),
)


async def _reachable() -> bool:
    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.connect():
            return True
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    if not await _reachable():
        pytest.skip(f"No PostgreSQL reachable at {DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(session_factory) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        yield s
