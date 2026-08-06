"""Durable worker-liveness heartbeat (ADIM 25).

The scheduler already enqueues ``system_heartbeat`` every tick and the worker
already logs ``worker.heartbeat`` when it lands, which proves the
scheduler -> Redis -> worker round-trip works. That proof was **not recorded**
anywhere, so nothing outside a log tail could answer "is a worker still
consuming?" — the only queue-side signals are indirect (depth grows, a lease
ages), and both need a *pending job* before they say anything at all. A worker
that dies on an idle system stayed invisible until the next real request.

This module makes the round-trip durable by writing its completion timestamp to
the pre-existing ``app_metadata`` key/value table. That table is already mapped
and exported and had no writer, so recording liveness costs **no migration**.

Honest boundary — read this before trusting the gauge:

* The heartbeat is enqueued on the ``maintenance`` queue, so a fresh timestamp
  proves exactly one thing: *a worker consuming ``maintenance`` is alive*. It is
  NOT a per-queue liveness signal. A dead ``data`` or ``backtest`` worker leaves
  this timestamp perfectly fresh; catch those with queue depth and lease age
  instead (see ``docs/runbooks/worker-down.md``).
* A missing row is reported as ``None``, never as "0 seconds ago". Rendering an
  absent heartbeat as a healthy zero would advertise liveness that was never
  proven, and the exposition would be lying at exactly the moment an operator
  most needs it to be honest.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.infrastructure.postgres.models import AppMetadata

__all__ = [
    "MAINTENANCE_HEARTBEAT_KEY",
    "record_worker_heartbeat",
    "worker_heartbeat_age_seconds",
]

#: ``app_metadata`` key holding the last completed maintenance-queue round-trip.
#: The queue is named in the key so a future per-queue heartbeat can be added
#: alongside it without reinterpreting what this one already means.
MAINTENANCE_HEARTBEAT_KEY = "worker.maintenance.last_heartbeat_at"


async def record_worker_heartbeat(
    session: AsyncSession, *, now: datetime | None = None
) -> datetime:
    """Stamp the maintenance-queue round-trip as completed, and return the stamp.

    An idempotent upsert on the primary key: the heartbeat is a *latest value*,
    not a history, so a row per tick would be unbounded growth for no added
    signal. The timestamp is written explicitly into ``value`` rather than being
    left to the column's ``onupdate`` default — an upsert does not run the ORM
    -level hook, and a gauge whose freshness silently depended on that would be
    the kind of quiet breakage this slice exists to prevent.

    No commit here: the caller owns the transaction (one-tx no-commit).
    """
    stamped = (now or datetime.now(UTC)).astimezone(UTC)
    statement = (
        pg_insert(AppMetadata)
        .values(key=MAINTENANCE_HEARTBEAT_KEY, value=stamped.isoformat(), updated_at=stamped)
        .on_conflict_do_update(
            index_elements=[AppMetadata.key],
            set_={"value": stamped.isoformat(), "updated_at": stamped},
        )
    )
    await session.execute(statement)
    return stamped


async def worker_heartbeat_age_seconds(
    session: AsyncSession, *, now: datetime | None = None
) -> float | None:
    """Seconds since the last recorded round-trip, or ``None`` if never recorded.

    ``None`` is a distinct fact from ``0.0`` and the caller must keep it that
    way. Clamped at zero for the same reason the lease-age gauge is: a worker
    clock running ahead of the reader's is a skew problem, and a negative age is
    not a thing this gauge can mean.
    """
    statement = select(AppMetadata.value).where(AppMetadata.key == MAINTENANCE_HEARTBEAT_KEY)
    raw = (await session.execute(statement)).scalar_one_or_none()
    if raw is None:
        return None
    try:
        stamped = datetime.fromisoformat(raw)
    except ValueError:
        # A malformed value is corruption, not liveness. Report "never seen"
        # rather than guessing an age from an unparseable string.
        return None
    if stamped.tzinfo is None:
        stamped = stamped.replace(tzinfo=UTC)
    return max(0.0, ((now or datetime.now(UTC)) - stamped).total_seconds())
