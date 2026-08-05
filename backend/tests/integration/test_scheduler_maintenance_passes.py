"""Consecutive scheduler maintenance passes must not fail — against real Postgres.

The scheduler used to call ``asyncio.run(_maintenance_pass())`` once per tick,
creating AND closing a fresh event loop each time, while ``get_engine`` is
``@lru_cache``d process-wide. The pooled asyncpg connection stayed bound to the
previous, now-closed loop, so the next tick picked it up and the whole pass
aborted::

    RuntimeError: Event loop is closed
      asyncpg/connection.py:1682 in _cancel_current_command
      sqlalchemy/dialects/postgresql/asyncpg.py:912 in _terminate_graceful_close

The failed pass discarded the bad connection, so the following tick got a fresh
one and succeeded — passes alternated at exactly 50%. Half of every outbox relay,
stale-RUNNING recovery (INF-09) and lost-message redelivery (INF-03) was skipped
and delayed a further tick. Nothing was lost (the pass rolls back whole and rows
stay durably QUEUED), but recovery latency doubled and the log carried a
permanent ``scheduler.maintenance_failed`` stream.

This test drives the REAL entrypoint (``scheduler.run``) against the REAL cached,
POOLED engine — both properties are load-bearing. Substituting the integration
suite's per-test ``NullPool`` engine would hand every tick a brand-new connection
and the bug could not appear at all; the structural half of the invariant, which
needs no database, lives in ``tests/unit/test_scheduler_loop_lifetime.py``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from entropia.apps.scheduler import __main__ as scheduler
from entropia.config.settings import get_settings
from entropia.infrastructure.postgres import engine as engine_module
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.models import *  # noqa: F403 (register tables)

from .db import ensure_test_database, resolve_test_database_url

pytestmark = pytest.mark.integration

# More than the two ticks strictly needed to expose the alternation, so a run that
# only *sometimes* strands its connection still shows up.
PASSES = 6


async def _rebuild_schema(url: str) -> bool:
    if not await ensure_test_database(url):
        return False
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SET lock_timeout = '30s'"))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()
    return True


def _clear_process_caches() -> None:
    """Re-resolve the three process-wide singletons around the swapped database URL."""
    get_settings.cache_clear()
    engine_module.get_engine.cache_clear()
    engine_module.get_session_factory.cache_clear()


class _SweepLog:
    """Records the sweep's own log line, and ends the run once enough ticks passed.

    The stop condition counts BOTH outcomes, never just the successes: keying it
    on ``scheduler.maintenance`` alone would spin forever against a scheduler
    whose every pass fails — the exact state under test.
    """

    def __init__(self, passes: int) -> None:
        self._passes = passes
        self.succeeded: list[dict[str, Any]] = []
        self.failed: list[dict[str, Any]] = []
        self.other: list[str] = []

    def info(self, event: str, **fields: Any) -> None:
        if event == "scheduler.maintenance":
            self.succeeded.append(fields)
            self._maybe_stop()
        else:
            self.other.append(event)

    def warning(self, event: str, **fields: Any) -> None:
        if event == "scheduler.maintenance_failed":
            self.failed.append(fields)
            self._maybe_stop()
        else:
            self.other.append(event)

    def _maybe_stop(self) -> None:
        if len(self.succeeded) + len(self.failed) >= self._passes:
            scheduler.request_stop()


@pytest.fixture
def sweep_log(monkeypatch) -> _SweepLog:
    """A scheduler wired to the isolated test database, with the broker stubbed out."""
    url = resolve_test_database_url()
    if not asyncio.run(_rebuild_schema(url)):
        pytest.skip(f"No PostgreSQL reachable/provisionable at {url}")

    monkeypatch.setenv("DATABASE_URL", url)
    _clear_process_caches()

    monkeypatch.setattr(scheduler, "configure_logging", lambda: None)
    monkeypatch.setattr(scheduler, "tick_seconds", lambda: 0.001)
    monkeypatch.setattr(
        scheduler,
        "system_heartbeat",
        type("_Actor", (), {"send": staticmethod(lambda note: None)})(),
    )
    monkeypatch.setattr(scheduler, "send_job", lambda actor, job_id: None)

    recorder = _SweepLog(PASSES)
    monkeypatch.setattr(scheduler, "log", recorder)
    try:
        yield recorder
    finally:
        # The cached engine now points at the test database; drop it before the
        # monkeypatched DATABASE_URL is restored so nothing downstream inherits it.
        _clear_process_caches()


def test_consecutive_maintenance_passes_log_no_failure(sweep_log) -> None:
    scheduler.run()

    assert sweep_log.failed == [], (
        f"{len(sweep_log.failed)} of {PASSES} passes aborted: "
        f"{[fields.get('error') for fields in sweep_log.failed]}"
    )
    assert len(sweep_log.succeeded) == PASSES


def test_each_pass_really_swept_the_database(sweep_log) -> None:
    """Guards the test above: every pass must have run the sweep, not short-circuited.

    An empty schema has nothing to relay, recover or redeliver, so each summary is
    all-zero — but the keys must be present and complete, which only a pass that
    actually reached ``relay_unpublished`` / ``recover_stale_jobs`` /
    ``redeliverable_queued_jobs`` and committed can produce.
    """
    scheduler.run()

    assert (
        sweep_log.succeeded
        == [{"relayed": 0, "requeued": 0, "failed_terminal": 0, "redelivered": 0}] * PASSES
    )


def test_the_run_starts_and_stops_exactly_once(sweep_log) -> None:
    scheduler.run()

    assert sweep_log.other == ["scheduler.start", "scheduler.stop"]
