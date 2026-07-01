"""Alpha Agent Coordinator — continuous backend process (doc 18 §14, AL-01).

The Agent is a non-login system actor whose main research loop runs independently
of the UI, browser, Analysis Lab, or any human session (doc 18 §14). Each tick
opens its own DB session, runs ONE ``run_coordinator_cycle`` (apply pending
control at a safe checkpoint -> consume the next directive -> materialize an
autonomous follow-up task), and commits. A failing tick rolls back whole and the
loop keeps running — canonical state is re-read next tick (crash recovery, AL-14).
"""

from __future__ import annotations

import asyncio
import signal
import time
import types

from entropia.application.commands.agent_loop import run_coordinator_cycle
from entropia.domain.agent_lab.enums import ALPHA_AGENT_ID
from entropia.infrastructure.observability import configure_logging, get_logger

CYCLE_SLEEP_SECONDS = 10

_running = True


def _handle_stop(signum: int, _frame: types.FrameType | None) -> None:
    global _running
    _running = False


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


def run() -> None:
    configure_logging()
    log = get_logger("agent_coordinator")
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    log.info("agent_coordinator.start")
    while _running:
        try:
            summary = asyncio.run(_run_cycle())
            log.info("agent_coordinator.cycle", **_loggable(summary))
        except Exception as exc:  # never crash the loop on a single bad tick
            log.warning("agent_coordinator.cycle_failed", error=str(exc))
        time.sleep(CYCLE_SLEEP_SECONDS)
    log.info("agent_coordinator.stop")


def _loggable(summary: dict[str, object]) -> dict[str, object]:
    consumed = summary.get("consumed")
    directive_id = consumed.get("consumed") if isinstance(consumed, dict) else None
    return {
        "runtime_status": summary.get("runtime_status"),
        "consumed_directive": directive_id,
        "followup_task_id": summary.get("followup_task_id"),
    }


if __name__ == "__main__":
    run()
