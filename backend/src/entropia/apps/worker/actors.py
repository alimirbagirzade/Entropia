"""Infrastructure-level actors (no product domain yet).

Importing the broker first binds it process-wide, so the @dramatiq.actor
decorators below register against the canonical Redis broker.
"""

from __future__ import annotations

import dramatiq

from entropia.infrastructure.observability import get_logger
from entropia.infrastructure.queues import broker as _broker  # noqa: F401  (installs broker)

log = get_logger("worker")


@dramatiq.actor(queue_name="maintenance", max_retries=3)
def system_heartbeat(note: str = "ping") -> None:
    """Proves the queue/worker round-trip works end to end."""
    log.info("worker.heartbeat", note=note)
