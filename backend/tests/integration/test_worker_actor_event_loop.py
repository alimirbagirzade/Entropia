"""Concurrent ``data``-queue actor bodies must never cross event loops.

Regression for the defect that stranded durable jobs permanently. Every actor
body used to run its coroutine under ``asyncio.run``, which closes its loop per
message, while ``postgres/engine.py::get_engine`` is ``@lru_cache(maxsize=1)`` —
so the asyncpg pool outlived every loop. With several dramatiq worker threads a
connection born on one thread's loop was checked out on another's and asyncpg
raised ``got Future ... attached to a different loop``; the message burned its
``max_retries`` and the broker DISCARDED it. Observed on a live dev stack with 8
concurrent Market Data analyses: 11 ``start`` events, 7 ``done``, 4 loop crashes,
one message discarded — and its ``jobs`` row left ``queued`` with ``attempts=0``
forever, because the multi-actor ``data`` queue is deliberately excluded from the
scheduler's ``ACTOR_BY_QUEUE`` (re-dispatch is an operator action). A crash is not
required: any two ``data`` jobs in parallel are enough.

These tests drive the REAL actor callables against the REAL process-wide engine
(``pool_pre_ping=True``, the pooled path the defect lived in), through a delivery
envelope shaped like dramatiq's, and assert the two things that failed in the
field: zero cross-loop errors, and zero deliveries lost.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.jobs.data_queue import DATA_QUEUE, MARKET_DATA_ANALYSIS
from entropia.apps.worker.actors import (
    run_market_data_analysis,
    run_package_import,
    run_research_data_analysis,
    run_trade_log_import,
    run_trading_signal_import,
)
from entropia.domain.lifecycle.enums import JobStatus
from entropia.infrastructure.async_runtime import run_sync, shutdown_runtime
from entropia.infrastructure.postgres.models import Job
from entropia.shared.ids import new_id

from .db import resolve_test_database_url

pytestmark = pytest.mark.integration

# Every durable actor multiplexed onto the single ``data`` queue.
DATA_ACTORS = (
    run_market_data_analysis,
    run_research_data_analysis,
    run_trading_signal_import,
    run_trade_log_import,
    run_package_import,
)

CONCURRENCY = 8  # the field repro used 8 parallel Market Data analyses
ROUNDS = 3
MAX_ATTEMPTS = 3  # mirrors @dramatiq.actor(max_retries=3)

CROSS_LOOP_MARKER = "attached to a different loop"


@pytest.fixture
def process_wide_engine(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point the ``@lru_cache`` process-wide engine at the isolated test database.

    The actor bodies resolve their session factory from that cache, so this is
    the only way to exercise the pool the defect lived in (the per-test fixture
    engine is NullPool — it cannot reproduce a recycled connection at all).
    Teardown disposes it: leaving pooled connections open would make the next
    test's ``drop_all`` wait on an ACCESS EXCLUSIVE lock.
    """
    from entropia.config import get_settings
    from entropia.infrastructure.postgres import engine as engine_module

    monkeypatch.setenv("DATABASE_URL", resolve_test_database_url())
    get_settings.cache_clear()
    engine_module.get_engine.cache_clear()
    engine_module.get_session_factory.cache_clear()
    try:
        yield
    finally:
        run_sync(engine_module.get_engine().dispose())
        engine_module.get_engine.cache_clear()
        engine_module.get_session_factory.cache_clear()
        get_settings.cache_clear()
        shutdown_runtime()


def _deliver(actor: Any, job_id: str) -> dict[str, Any]:
    """One broker delivery of ``job_id`` to ``actor``, with dramatiq's retries.

    A ``ValueError`` is the body's own domain verdict — the message was processed.
    Anything else is an infrastructure failure, which dramatiq retries and then
    DISCARDS; that discard is what stranded the durable row.
    """
    infra_errors: list[str] = []
    for _ in range(MAX_ATTEMPTS):
        try:
            actor(job_id)
        except ValueError as exc:
            return {"delivered": True, "verdict": str(exc), "infra_errors": infra_errors}
        except Exception as exc:  # classified below, never swallowed
            infra_errors.append(f"{type(exc).__name__}: {exc}")
        else:
            return {"delivered": True, "verdict": None, "infra_errors": infra_errors}
    return {"delivered": False, "verdict": None, "infra_errors": infra_errors}


async def test_concurrent_data_actor_bodies_never_cross_event_loops(
    session: AsyncSession, process_wide_engine: None
) -> None:
    deliveries = [(actor, new_id("job")) for _ in range(ROUNDS) for actor in DATA_ACTORS]

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        outcomes = list(pool.map(lambda item: _deliver(*item), deliveries))

    assert len(outcomes) == len(deliveries)

    all_infra = [error for outcome in outcomes for error in outcome["infra_errors"]]
    cross_loop = [error for error in all_infra if CROSS_LOOP_MARKER in error]
    assert cross_loop == [], f"pooled connection used on a foreign loop: {cross_loop}"

    assert all_infra == [], f"actor body failed on infrastructure: {all_infra}"

    dropped = [outcome for outcome in outcomes if not outcome["delivered"]]
    assert dropped == [], f"{len(dropped)} delivery(ies) exhausted max_retries and were discarded"

    # Every body really reached the database (its verdict is the row lookup),
    # so the run above is not vacuously green.
    assert all("not found" in str(outcome["verdict"]) for outcome in outcomes)


async def _insert_job_on_process_engine(job_id: str) -> int:
    """Insert + COMMIT through the process-wide factory; return the serving loop."""
    from entropia.infrastructure.postgres.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as worker_session:
        worker_session.add(
            Job(
                job_id=job_id,
                queue=DATA_QUEUE,
                status=JobStatus.QUEUED,
                payload={"job_kind": MARKET_DATA_ANALYSIS, "entity_id": new_id("md")},
            )
        )
        await worker_session.commit()
    return id(asyncio.get_running_loop())


async def test_every_worker_thread_commits_through_one_loop(
    session: AsyncSession, process_wide_engine: None
) -> None:
    """The write path, which is where a discarded message loses its effect.

    The field failure was an effect that never happened (a job stuck QUEUED with
    ``attempts = 0``), so the assertion that matters is exactly-once: one durable
    row per delivery, all of them committed through the single process loop.
    """
    job_ids = [new_id("job") for _ in range(CONCURRENCY * ROUNDS)]

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        serving_loops = set(
            pool.map(lambda jid: run_sync(_insert_job_on_process_engine(jid)), job_ids)
        )

    assert len(serving_loops) == 1, "worker threads ran on more than one event loop"

    committed = (
        (await session.execute(select(Job.job_id).where(Job.job_id.in_(job_ids)))).scalars().all()
    )
    assert sorted(committed) == sorted(job_ids)
