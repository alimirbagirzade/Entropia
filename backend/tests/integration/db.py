"""Isolated integration-test database resolution and provisioning (audit §10).

The integration fixtures rebuild the schema (``drop_all`` + ``create_all``) on
*every* test. They must therefore NEVER target the developer's data-bearing local
database:

* a running local dev stack holds locks on that database, so the per-test DDL
  rebuild waits on ``ACCESS EXCLUSIVE`` behind the stack's live DML — across a
  full ``pytest`` invocation that surfaces as the schema-fixture "deadlock" that
  aborts dozens of tests with fixture errors, while running one file at a time is
  quick enough to slip through (audit §11 "isolated tests pass");
* a *successful* rebuild would silently delete real local data.

Resolution order:

1. ``TEST_DATABASE_URL`` — explicit, honored verbatim (CI / power users).
2. otherwise an isolated ``<db>_test`` database derived from ``DATABASE_URL`` (or
   the local default), so the bare ``uv run pytest`` invocation the guides
   document is safe *by construction* — it never points at the live database.

:func:`ensure_test_database` auto-creates the isolated database once per process
(via the always-present ``postgres`` maintenance database) so the suite never
silently skips just because the dedicated database has not been created yet.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

DEFAULT_URL = "postgresql+asyncpg://entropia:entropia@localhost:5432/entropia"

_ensured: bool | None = None


def resolve_test_database_url() -> str:
    """The isolated URL the integration suite must use (never the live database)."""
    explicit = os.getenv("TEST_DATABASE_URL")
    if explicit:
        return explicit
    base = os.getenv("DATABASE_URL", DEFAULT_URL)
    parts = urlsplit(base)
    name = parts.path.lstrip("/") or "entropia"
    if name.endswith("_test"):  # already an isolated database — keep it
        return base
    return urlunsplit(parts._replace(path=f"/{name}_test"))


def _database_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def _maintenance_url(url: str) -> str:
    # ``CREATE DATABASE`` cannot run from inside the target database; connect to
    # the always-present ``postgres`` maintenance database to provision it once.
    return urlunsplit(urlsplit(url)._replace(path="/postgres"))


async def _provision(url: str) -> bool:
    # Fast path: the isolated database already exists and is reachable.
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect():
            return True
    except Exception:
        pass
    finally:
        await engine.dispose()

    # Create the isolated database via the maintenance database. A failure here
    # (no server, or no CREATEDB privilege) means the suite cannot run isolated —
    # the caller skips rather than falling back onto the live database.
    name = _database_name(url)
    maint = create_async_engine(
        _maintenance_url(url), poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    try:
        async with maint.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}
            )
            if not exists:
                # ``name`` is derived from our own env, never user input; quote it
                # defensively all the same. AUTOCOMMIT keeps CREATE DATABASE out of
                # a transaction block.
                await conn.execute(text(f'CREATE DATABASE "{name}"'))
        return True
    except Exception:
        return False
    finally:
        await maint.dispose()


async def ensure_test_database(url: str) -> bool:
    """Ensure the isolated test database exists; provision it once per process.

    Returns ``True`` when the database is reachable/usable, ``False`` when no
    PostgreSQL can be reached or provisioned (so the caller skips the suite).
    """
    global _ensured
    if _ensured is None:
        _ensured = await _provision(url)
    return _ensured
