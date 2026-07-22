"""Integration fixtures — require a reachable PostgreSQL (skips otherwise).

Each test gets its own function-scoped async engine, created and disposed within
the test's own event loop (NullPool, no cross-loop connection sharing — this is
the pytest-asyncio-safe pattern). The schema is rebuilt per test for isolation.

The rebuild runs against an ISOLATED test database, never the developer's live
one (see ``db.py`` / audit §10): rebuilding the schema on the database a running
dev stack is holding locks on turns the per-test DDL into an ``ACCESS EXCLUSIVE``
lock-wait that, across a full invocation, aborts dozens of tests — the exact
"deadlock" audit §11 requires be fixed so isolated tests pass. When no database
is reachable (and none can be provisioned), every integration test is skipped.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.models import *  # noqa: F403 (register tables)

from .db import ensure_test_database, resolve_test_database_url

# The isolated integration-test database URL — resolved once, reused by every
# fixture and by tests that open their own second connection (e.g. the concurrent
# demotion race). Never the developer's live database (audit §10).
DATABASE_URL = resolve_test_database_url()


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    if not await ensure_test_database(DATABASE_URL):
        pytest.skip(f"No PostgreSQL reachable/provisionable at {DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        # Defense in depth: on an isolated database the rebuild never contends, but
        # if someone points TEST_DATABASE_URL at a busy database a bounded
        # lock_timeout turns the old indefinite hang into a fast, explicit error.
        await conn.execute(text("SET lock_timeout = '30s'"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with factory() as s:
            yield s
    finally:
        await engine.dispose()
