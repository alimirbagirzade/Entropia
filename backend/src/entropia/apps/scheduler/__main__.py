"""Maintenance scheduler — low-priority periodic sweeps (Module 20 §6, Stage 8b).

Each tick, in its own transaction: relay the transactional outbox (the durable
published checkpoint behind the SSE fan-out), recover stale RUNNING jobs
(INF-09), and re-dispatch durable QUEUED jobs whose broker message was lost
(INF-03) through the queue->actor registry. The ``data`` queue hosts several
actor types per queue and is deliberately NOT auto-redelivered (recovery marks
it back to QUEUED; re-dispatch is an operator action) — workers on every plane
are redelivery-idempotent, so an occasional double send is safe.
"""

from __future__ import annotations

import asyncio
import signal
import time
import types
from typing import Any

from entropia.application.jobs.maintenance import recover_stale_jobs, redeliverable_queued_jobs
from entropia.application.jobs.outbox_relay import relay_unpublished
from entropia.apps.worker.actors import (
    run_agent_tool,
    run_agent_tool_high,
    run_backtest_engine,
    run_trash_purge,
    system_heartbeat,
)
from entropia.config import get_settings
from entropia.infrastructure.observability import configure_logging, get_logger
from entropia.infrastructure.queues.enqueue import send_job

TICK_SECONDS = 30

# Queues with exactly ONE durable-job actor are safe to auto-redeliver.
ACTOR_BY_QUEUE: dict[str, Any] = {
    "backtest": run_backtest_engine,
    "agent": run_agent_tool,
    "agent-high": run_agent_tool_high,
    "maintenance": run_trash_purge,
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

    redelivered = 0
    for queue, job_id in [*recovered["requeued"], *redeliverable]:
        actor = ACTOR_BY_QUEUE.get(queue)
        if actor is None:
            continue
        try:
            send_job(actor, job_id)
        except Exception:  # rows stay durably QUEUED; next tick re-sweeps them
            continue
        redelivered += 1

    return {
        "relayed": len(relayed),
        "requeued": len(recovered["requeued"]),
        "failed_terminal": len(recovered["failed"]),
        "redelivered": redelivered,
    }


def run() -> None:
    configure_logging()
    log = get_logger("scheduler")
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
        time.sleep(TICK_SECONDS)
    log.info("scheduler.stop")


if __name__ == "__main__":
    run()
