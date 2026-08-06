"""The heartbeat upsert against a real PostgreSQL (ADIM 25).

The unit tests cover the age arithmetic with a fake session. What they cannot
cover is the part that actually touches the database: that the write is an
``ON CONFLICT`` upsert on the primary key, so a heartbeat every 30s forever
leaves exactly ONE row rather than growing ``app_metadata`` without bound, and
that ``updated_at`` is written explicitly rather than being left to a column
default the upsert path never triggers.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from entropia.application.jobs.heartbeat import (
    MAINTENANCE_HEARTBEAT_KEY,
    record_worker_heartbeat,
    worker_heartbeat_age_seconds,
)
from entropia.application.queries.job_gauges import job_gauges
from entropia.infrastructure.postgres.models import AppMetadata

pytestmark = pytest.mark.integration


async def _row_count(session) -> int:
    statement = (
        select(func.count())
        .select_from(AppMetadata)
        .where(AppMetadata.key == MAINTENANCE_HEARTBEAT_KEY)
    )
    return (await session.execute(statement)).scalar_one()


async def test_the_first_heartbeat_creates_the_row(session) -> None:
    assert await worker_heartbeat_age_seconds(session) is None

    now = datetime.now(UTC)
    stamped = await record_worker_heartbeat(session, now=now)
    await session.commit()

    assert stamped == now.astimezone(UTC)
    assert await _row_count(session) == 1
    assert await worker_heartbeat_age_seconds(session, now=now) == pytest.approx(0.0)


async def test_repeated_heartbeats_update_in_place_and_never_accumulate(session) -> None:
    """Every 30s forever must not grow the table — this is the upsert's whole job."""
    base = datetime.now(UTC) - timedelta(minutes=10)
    for tick in range(20):
        await record_worker_heartbeat(session, now=base + timedelta(seconds=30 * tick))
    await session.commit()

    assert await _row_count(session) == 1


async def test_the_stored_stamp_is_the_one_the_reader_sees(session) -> None:
    now = datetime.now(UTC)
    await record_worker_heartbeat(session, now=now - timedelta(seconds=95))
    await session.commit()

    age = await worker_heartbeat_age_seconds(session, now=now)
    assert age == pytest.approx(95.0, abs=0.5)

    stored = (
        await session.execute(
            select(AppMetadata.value, AppMetadata.updated_at).where(
                AppMetadata.key == MAINTENANCE_HEARTBEAT_KEY
            )
        )
    ).one()
    # updated_at is written explicitly: an upsert does not fire the ORM-level
    # `onupdate` hook, so a gauge relying on that default would silently freeze.
    assert datetime.fromisoformat(stored.value) == stored.updated_at.astimezone(UTC)


async def test_a_later_heartbeat_overwrites_an_earlier_one(session) -> None:
    now = datetime.now(UTC)
    await record_worker_heartbeat(session, now=now - timedelta(minutes=5))
    await record_worker_heartbeat(session, now=now - timedelta(seconds=3))
    await session.commit()

    assert await worker_heartbeat_age_seconds(session, now=now) == pytest.approx(3.0, abs=0.5)


async def test_the_scrape_gauges_carry_the_heartbeat(session) -> None:
    """End to end: what the worker wrote is what GET /metrics will publish."""
    now = datetime.now(UTC)

    gauges = await job_gauges(session, now=now)
    assert gauges.worker_heartbeat_age_seconds is None, "an unproven worker must not read as fresh"

    await record_worker_heartbeat(session, now=now - timedelta(seconds=12))
    await session.commit()

    gauges = await job_gauges(session, now=now)
    assert gauges.worker_heartbeat_age_seconds == pytest.approx(12.0, abs=0.5)
