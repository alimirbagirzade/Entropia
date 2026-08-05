"""Maintenance scheduler — low-priority periodic sweeps (Module 20 §6, Stage 8b).

Each tick, in its own transaction: relay the transactional outbox (the durable
published checkpoint behind the SSE fan-out), recover stale RUNNING jobs
(INF-09), and re-dispatch durable QUEUED jobs whose broker message was lost
(INF-03) through the queue->actor registry. The ``data`` queue hosts several
actor types per queue and is deliberately NOT auto-redelivered (recovery marks
it back to QUEUED; re-dispatch is an operator action).

An occasional double send is safe because every plane guards its own delivery,
and each guard is named rather than assumed: ``backtest``/``agent-executor``/
``default`` hold a domain-row lock and check a domain terminal state, ``agent``/
``agent-high`` replay on the AL-14 tool-call key, and the five ``data`` actors go
through ``application/jobs/delivery.py::claim_job_for_delivery``. Until ADIM 21
this paragraph claimed the property for every plane while the ``data`` five had
no guard at all; ``tests/integration/test_worker_delivery_recovery.py`` now
executes the double delivery per plane instead of asserting it in prose.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from collections.abc import Sequence
from typing import Any

from entropia.application.jobs.maintenance import recover_stale_jobs, redeliverable_queued_jobs
from entropia.application.jobs.outbox_relay import relay_unpublished
from entropia.apps.worker.actors import (
    run_agent_executor,
    run_agent_tool,
    run_agent_tool_high,
    run_backtest_engine,
    run_create_package_job,
    run_trash_purge,
    system_heartbeat,
)
from entropia.config import get_settings
from entropia.infrastructure.observability import configure_logging, get_logger
from entropia.infrastructure.queues.enqueue import send_job

DEFAULT_TICK_SECONDS = 30.0


def tick_seconds() -> float:
    """Seconds between maintenance passes (``SCHEDULER_TICK_SECONDS``).

    This tick also relays the outbox, so it is the upper bound on how long a
    completed worker step waits before its ``resource.changed`` reaches SSE: a
    lifecycle with N advertised-async steps costs up to N ticks end to end. 30s
    is the right cadence for a production sweep, but it made the four-step
    Create Package E2E spend ~90s purely waiting on ticks — right at the test
    budget, so a run passed or failed on the sum. A hermetic E2E stack now
    lowers this instead of the suite raising its timeout, which would have
    hidden the latency rather than removed it.

    A non-positive value would spin the sweep at full CPU against Postgres, so
    it falls back to the default rather than being honoured.
    """
    configured = get_settings().scheduler_tick_seconds
    return configured if configured > 0 else DEFAULT_TICK_SECONDS


# Module-level logger (the repo pattern — see ``apps/api/errors.py``) so the
# redelivery sweep can report a failed enqueue instead of swallowing it.
log = get_logger("scheduler")

# Queues with exactly ONE durable-job actor are safe to auto-redeliver.
ACTOR_BY_QUEUE: dict[str, Any] = {
    "backtest": run_backtest_engine,
    "agent": run_agent_tool,
    "agent-high": run_agent_tool_high,
    "agent-executor": run_agent_executor,
    "maintenance": run_trash_purge,
    # Create-Package (F-01a): the single kind-dispatching durable actor on ``default``
    # gives Pre-Check the generic stale-RUNNING recovery + lost-message redelivery
    # sweeps (INF-03/INF-09) for free.
    "default": run_create_package_job,
}

# The live sweep's stop flag, or ``None`` between runs. An ``asyncio.Event``
# rather than the old ``bool`` because waiting on it makes a signal land at once
# instead of waiting out the remainder of the tick — and it is created per run,
# never at import, because an Event binds to the first loop that awaits it and
# refuses every other one thereafter (one more reason the loop below is single
# and long-lived).
_stop: asyncio.Event | None = None


def request_stop() -> None:
    """End the sweep after the current tick — the signal handlers' entry point."""
    if _stop is not None:
        _stop.set()


async def _maintenance_pass() -> dict[str, Any]:
    from entropia.infrastructure.postgres.engine import get_session_factory

    settings = get_settings()
    factory = get_session_factory()
    async with factory() as session:
        try:
            relayed = await relay_unpublished(session, batch_size=settings.outbox_relay_batch_size)
            recovered = await recover_stale_jobs(
                session, stale_after_seconds=settings.job_stale_after_seconds
            )
            redeliverable = await redeliverable_queued_jobs(
                session, grace_seconds=settings.job_redeliver_grace_seconds
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    return {
        "relayed": len(relayed),
        "requeued": len(recovered["requeued"]),
        "failed_terminal": len(recovered["failed"]),
        "redelivered": _redeliver([*recovered["requeued"], *redeliverable]),
    }


def _redeliver(candidates: Sequence[tuple[str, str]]) -> int:
    """Re-dispatch ``(queue, job_id)`` pairs to their actor; return the send count.

    A broker send that fails is NOT fatal and NOT a data loss — the row stays
    durably QUEUED and the next tick re-sweeps it — but it must not be silent
    either (finding O-23): a broker that rejects every send would otherwise look
    identical to "nothing needed redelivery" in the ``scheduler.maintenance``
    summary. The recovery behaviour is unchanged; only the evidence is added.
    """
    redelivered = 0
    for queue, job_id in candidates:
        actor = ACTOR_BY_QUEUE.get(queue)
        if actor is None:
            continue
        try:
            send_job(actor, job_id)
        except Exception as exc:  # rows stay durably QUEUED; next tick re-sweeps them
            log.warning("scheduler.redeliver_failed", job_id=job_id, queue=queue, error=str(exc))
            continue
        redelivered += 1
    return redelivered


def _install_stop_handlers(stop: asyncio.Event) -> None:
    """Route SIGTERM/SIGINT to ``stop`` as loop callbacks.

    ``loop.add_signal_handler`` rather than ``signal.signal`` so the handler runs
    as a loop callback and can set the event directly. Unix-only, which is what
    the scheduler ships on (``docker-compose.yml`` service ``scheduler``).
    """
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)


def _send_heartbeat() -> None:
    try:
        system_heartbeat.send(note="scheduler-tick")
    except Exception as exc:  # never crash the scheduler on enqueue failure
        log.warning("scheduler.enqueue_failed", error=str(exc))


async def _wait_for_tick(stop: asyncio.Event, seconds: float) -> None:
    """Wait one tick, returning early once a stop has been requested.

    The old blocking ``time.sleep`` could not be interrupted: PEP 475 re-arms the
    sleep after the signal handler returns, so SIGTERM cost up to a full tick
    (30s in production) of shutdown latency. Waiting on the event instead ends
    the tick the moment the signal lands.
    """
    # A whole tick elapsing is the ordinary path; only a stop ends the wait early.
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=seconds)


async def _sweep_until_stopped() -> None:
    global _stop
    from entropia.infrastructure.postgres.engine import get_engine

    stop = _stop = asyncio.Event()
    _install_stop_handlers(stop)
    log.info("scheduler.start")
    try:
        while not stop.is_set():
            _send_heartbeat()
            try:
                summary = await _maintenance_pass()
                log.info("scheduler.maintenance", **summary)
            except Exception as exc:  # a failed pass rolls back whole; next tick retries
                log.warning("scheduler.maintenance_failed", error=str(exc))
            await _wait_for_tick(stop, tick_seconds())
    finally:
        _stop = None
        # Hand the pool back while its loop is still open, for the same reason the
        # loop is long-lived at all: a connection outliving its loop is exactly the
        # failure :func:`run` describes, and at exit it returns as shutdown noise.
        await get_engine().dispose()
        log.info("scheduler.stop")


def run() -> None:
    """Run the maintenance sweep until stopped, on ONE event loop.

    The loop must outlive the engine's connection pool. ``get_engine`` is
    ``@lru_cache``d process-wide, so a pooled asyncpg connection stays bound to
    the loop that first opened it — and the previous shape, ``asyncio.run`` per
    tick, closed that loop underneath it. The next tick then checked out a
    connection attached to a dead loop and the whole pass aborted with "got
    Future attached to a different loop" / "Event loop is closed"
    (``asyncpg/connection.py::_cancel_current_command``). Because the failed pass
    discarded the bad connection, the following tick got a fresh one and
    succeeded: passes alternated OK/FAILED at exactly 50%, so half of every
    outbox relay, stale-RUNNING recovery (INF-09) and lost-message redelivery
    (INF-03) was skipped and delayed a further tick. Nothing was ever lost — the
    pass rolls back whole and rows stay durably QUEUED — but recovery latency
    doubled and the log carried a permanent warning stream. One loop for the
    process lifetime also drops the per-tick connection setup cost.
    """
    configure_logging()
    asyncio.run(_sweep_until_stopped())


if __name__ == "__main__":
    run()
