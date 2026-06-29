"""Alpha Agent Coordinator — continuous backend process (Module 20 §8).

The Agent is a non-login system actor whose main research loop runs
independently of the UI, browser, Analysis Lab, or any human session. Stage 0
ships the supervised loop shell (load -> inspect -> sleep) with NO task
selection, tool execution, or artifact production. Real cycle logic and the
safe-checkpoint directive model arrive in Stage 6.
"""

from __future__ import annotations

import signal
import time
import types

from entropia.infrastructure.observability import configure_logging, get_logger

CYCLE_SLEEP_SECONDS = 10

_running = True


def _handle_stop(signum: int, _frame: types.FrameType | None) -> None:
    global _running
    _running = False


def run() -> None:
    configure_logging()
    log = get_logger("agent_coordinator")
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    log.info("agent_coordinator.start")
    while _running:
        # Stage 0: heartbeat only. No directive consumption, no task enqueue.
        log.info("agent_coordinator.cycle", phase="idle")
        time.sleep(CYCLE_SLEEP_SECONDS)
    log.info("agent_coordinator.stop")


if __name__ == "__main__":
    run()
