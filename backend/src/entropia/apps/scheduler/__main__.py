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
import signal
import time
import types
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

_running = True


def _handle_stop(signum: int, _frame: types.FrameType | None) -> None:
    global _running
    _running = False


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


def run() -> None:
    configure_logging()
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    log.info("scheduler.start")
    while _running:
        try:
            system_heartbeat.send(note="scheduler-tick")
        except Exception as exc:  # never crash the scheduler on enqueue failure
            log.warning("scheduler.enqueue_failed", error=str(exc))
        try:
            summary = asyncio.run(_maintenance_pass())
            log.info("scheduler.maintenance", **summary)
        except Exception as exc:  # a failed pass rolls back whole; next tick retries
            log.warning("scheduler.maintenance_failed", error=str(exc))
        time.sleep(tick_seconds())
    log.info("scheduler.stop")


if __name__ == "__main__":
    run()
