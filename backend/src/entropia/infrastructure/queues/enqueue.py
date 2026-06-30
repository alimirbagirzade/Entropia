"""Durable job enqueue helper (decision D4, CR-09).

The ``jobs`` table row is the authoritative source of truth — it survives browser
close, logout, and Redis restarts. ``enqueue_job`` INSERTs that row (no commit;
the caller commits in its transaction). After the surrounding transaction
commits, the caller dispatches the Dramatiq actor via ``send_job`` so the worker
picks it up. Keeping the two steps separate means this module imports cleanly
without a live broker.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import JobStatus
from entropia.infrastructure.postgres.models import Job
from entropia.shared.ids import new_id


def enqueue_job(
    session: AsyncSession,
    *,
    queue: str,
    payload: dict[str, Any] | None = None,
    actor_principal_id: str | None = None,
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
    max_attempts: int = 3,
) -> Job:
    """Insert a durable ``jobs`` row in QUEUED state. Does not commit or send."""
    job = Job(
        job_id=new_id("job"),
        queue=queue,
        status=JobStatus.QUEUED,
        actor_principal_id=actor_principal_id,
        idempotency_key=idempotency_key,
        payload=payload,
        correlation_id=correlation_id,
        max_attempts=max_attempts,
    )
    session.add(job)
    return job


def send_job(actor: Any, job_id: str) -> None:
    """Dispatch a registered Dramatiq actor for ``job_id`` after commit.

    ``actor`` is a ``@dramatiq.actor``-decorated callable exposing ``.send``.
    Imported lazily by callers so this module stays broker-free at import time.
    """
    actor.send(job_id)
