"""Dramatiq broker wiring (Redis 7).

The Redis message is only transport. Job business rules, retry policy,
idempotency key, correlation, and final state live in the PostgreSQL job
table (Module 20 §6). Canonical queues:

    default, data, backtest, agent, agent-high, agent-executor, maintenance
"""

from __future__ import annotations

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from entropia.config import get_settings

CANONICAL_QUEUES = (
    "default",
    "data",
    "backtest",
    "agent",
    "agent-high",
    "agent-executor",
    "maintenance",
)


def get_broker() -> RedisBroker:
    settings = get_settings()
    return RedisBroker(  # type: ignore[no-untyped-call]
        url=settings.redis_url, namespace=settings.queue_namespace
    )


# Install the broker process-wide so @dramatiq.actor decorators bind to it.
broker = get_broker()
dramatiq.set_broker(broker)
