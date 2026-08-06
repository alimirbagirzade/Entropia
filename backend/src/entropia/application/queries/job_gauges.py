"""Operational gauge read model for the ``/metrics`` scrape (Module 20 §11, finding I-05).

The three gauges the exposition publishes — queue depth per ``(queue, status)``,
outbox relay lag, oldest RUNNING lease age — are READS over ``jobs`` and the
outbox. They used to be assembled as raw ``select(...)`` statements *inside*
``apps/api/routes/metrics.py``, which made that route the single place in the API
layer that imported an ORM model and bypassed the command/query layer entirely.
The statements live here now; the route keeps only the Prometheus text rendering
and the degrade-on-unreachable-database envelope.

The projection is value-only on purpose — no ORM entity escapes this module — so
the exposition formatter stays a pure function of :class:`JobGauges` and the same
scrape can be rendered in a test without a database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.jobs.heartbeat import worker_heartbeat_age_seconds
from entropia.application.jobs.outbox_relay import outbox_lag_seconds
from entropia.domain.lifecycle.enums import JobStatus
from entropia.infrastructure.postgres.models import Job

__all__ = ["JobGauges", "job_gauges"]


@dataclass(frozen=True, slots=True)
class JobGauges:
    """One scrape's worth of operational gauge values.

    ``outbox_lag_seconds`` stays ``float | None``: ``None`` means "nothing is
    unpublished", which is a different fact from "the lag is zero seconds". How
    that renders on the wire is the exposition's decision, not this layer's.
    """

    queue_depth: tuple[tuple[str, JobStatus, int], ...]
    outbox_lag_seconds: float | None
    oldest_lease_age_seconds: float
    #: Seconds since a worker last completed the maintenance-queue round-trip,
    #: or ``None`` when no heartbeat has ever been recorded. ``None`` must NOT
    #: collapse to ``0.0`` downstream: "never proven alive" and "alive one
    #: instant ago" are opposite operational facts.
    worker_heartbeat_age_seconds: float | None = None


async def job_gauges(session: AsyncSession, *, now: datetime | None = None) -> JobGauges:
    """Read the operational gauges in one pass over the given session.

    Statement order matches the pre-I-05 route body (depth -> outbox lag ->
    lease age) so the scrape keeps hitting the database in the same sequence.
    The lease age is clamped at zero here rather than at render time: a clock
    skew that puts ``started_at`` in the future is a value problem, and a
    negative age is not a thing this gauge can mean.
    """
    depth_stmt = select(Job.queue, Job.status, func.count()).group_by(Job.queue, Job.status)
    queue_depth = tuple(
        (queue, status, count) for queue, status, count in (await session.execute(depth_stmt)).all()
    )

    lag = await outbox_lag_seconds(session)

    lease_stmt = select(func.min(func.coalesce(Job.started_at, Job.claimed_at))).where(
        Job.status == JobStatus.RUNNING
    )
    oldest = (await session.execute(lease_stmt)).scalar_one_or_none()
    age = 0.0 if oldest is None else ((now or datetime.now(UTC)) - oldest).total_seconds()

    heartbeat_age = await worker_heartbeat_age_seconds(session, now=now)

    return JobGauges(
        queue_depth=queue_depth,
        outbox_lag_seconds=lag,
        oldest_lease_age_seconds=max(0.0, age),
        worker_heartbeat_age_seconds=heartbeat_age,
    )
