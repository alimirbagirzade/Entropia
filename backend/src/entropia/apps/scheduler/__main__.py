"""Maintenance scheduler — low-priority periodic jobs (Module 20 §6).

Stage 0: emits a heartbeat into the maintenance queue so the worker plane is
observably alive. Real schedules (retention checks, stale-job recovery,
projection rebuilds) arrive with their owning stages.
"""

from __future__ import annotations

import signal
import time
import types

from entropia.apps.worker.actors import system_heartbeat
from entropia.infrastructure.observability import configure_logging, get_logger

TICK_SECONDS = 30

_running = True


def _handle_stop(signum: int, _frame: types.FrameType | None) -> None:
    global _running
    _running = False


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
        time.sleep(TICK_SECONDS)
    log.info("scheduler.stop")


if __name__ == "__main__":
    run()
