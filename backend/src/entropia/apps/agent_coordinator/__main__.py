"""Alpha Agent Coordinator — continuous backend process (doc 18 §14, AL-01).

The Agent is a non-login system actor whose main research loop runs independently
of the UI, browser, Analysis Lab, or any human session (doc 18 §14). Each tick
opens its own DB session, runs ONE ``run_coordinator_cycle`` (apply pending
control at a safe checkpoint -> consume the next directive -> materialize an
autonomous follow-up task + its durable executor Job, spec F-20), and commits. A
failing tick rolls back whole and the loop keeps running — canonical state is
re-read next tick (crash recovery, AL-14).

Dispatch, like an API route, happens only AFTER the commit that created the
durable Job row (``application/commands/agent_loop.py::_spawn_followup_task``) —
mirrors ``apps/scheduler/__main__.py``'s commit-then-``send_job`` ordering. A
crash between commit and dispatch never loses the task: the row stays QUEUED and
the scheduler's redelivery sweep (INF-03) re-sends it.

The tick crosses into its async body with ``async_runtime.run_sync``, never
``asyncio.run``: the latter closes its loop every tick while the ``@lru_cache``
asyncpg pool behind ``get_session_factory`` is process-wide, so tick N+1 checks
out a connection created on tick N's closed loop and asyncpg raises "attached to
a different loop". Here that surfaces as a tick that can never succeed again
rather than a stranded row — the loop logs ``agent_coordinator.cycle_failed``
forever and the Agent silently stops making progress.
"""

from __future__ import annotations


import signal

from entropia.application.commands.agent_loop import run_coordinator_cycle
from entropia.apps.worker.actors import run_agent_executor
from entropia.domain.agent_lab.enums import ALPHA_AGENT_ID
from entropia.infrastructure.async_runtime import run_sync
from entropia.infrastructure.observability import configure_logging, get_logger
from entropia.infrastructure.queues.enqueue import send_job

CYCLE_SLEEP_SECONDS = 10

# Module-level so the loop helpers below can report; mirrors ``apps/scheduler``.
log = get_logger("agent_coordinator")

# The live loop's stop flag, or ``None`` between runs — created per run, never at
# import, because an ``asyncio.Event`` binds to the first loop that awaits it and
# refuses every other one thereafter.
_stop: asyncio.Event | None = None


def request_stop() -> None:
    """End the loop after the current cycle — the signal handlers' entry point."""
    if _stop is not None:
        _stop.set()


async def _run_cycle() -> dict[str, object]:
    from entropia.infrastructure.postgres.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        try:
            summary = await run_coordinator_cycle(session, agent_id=ALPHA_AGENT_ID)
            await session.commit()
            return summary
        except Exception:
            await session.rollback()
            raise


def _install_stop_handlers(stop: asyncio.Event) -> None:
    """Route SIGTERM/SIGINT to ``stop`` as loop callbacks.

    ``loop.add_signal_handler`` rather than ``signal.signal`` so the handler runs
    as a loop callback and can set the event directly. Unix-only, which is what
    this process ships on (``docker-compose.yml`` service ``agent-coordinator``).
    """
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)


async def _wait_for_cycle(stop: asyncio.Event, seconds: float) -> None:
    """Wait one cycle, returning early once a stop has been requested.

    The old blocking ``time.sleep`` could not be interrupted: PEP 475 re-arms the
    sleep after the signal handler returns, so SIGTERM cost up to a full cycle of
    shutdown latency. Waiting on the event ends it the moment the signal lands.
    """
    # A whole cycle elapsing is the ordinary path; only a stop ends the wait early.
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=seconds)


async def _loop_until_stopped() -> None:
    global _stop
    from entropia.infrastructure.postgres.engine import get_engine

    stop = _stop = asyncio.Event()
    _install_stop_handlers(stop)
    log.info("agent_coordinator.start")



def _loggable(summary: dict[str, object]) -> dict[str, object]:
    consumed = summary.get("consumed")
    directive_id = consumed.get("consumed") if isinstance(consumed, dict) else None
    return {
        "runtime_status": summary.get("runtime_status"),
        "consumed_directive": directive_id,
        "followup_task_id": summary.get("followup_task_id"),
        "executor_job_id": summary.get("executor_job_id"),
    }


if __name__ == "__main__":
    run()
