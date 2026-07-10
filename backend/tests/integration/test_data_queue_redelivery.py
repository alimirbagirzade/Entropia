"""Data-queue operator redelivery (INF-03, doc 20 §6) against a real DB.

Covers: the read helper returns only ``data``-queue rows still QUEUED past the
grace window, ordered oldest-first, with the payload ``job_kind`` resolved (legacy
rows -> ``None``); the Admin operator command routes the known kinds, counts the
un-routable legacy rows, and audits the recovery action once; and a non-Admin is
rejected before any work.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from entropia.application.commands.data_queue import redeliver_data_queue_jobs
from entropia.application.jobs.data_queue import (
    MARKET_DATA_ANALYSIS,
    RESEARCH_DATA_ANALYSIS,
    TRADE_LOG_IMPORT,
    list_redeliverable_data_jobs,
)
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import JobStatus, PrincipalType, Role
from entropia.infrastructure.postgres.models import AuditEvent, Job
from entropia.shared.errors import AdminPanelAccessRequiredError

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)


def _job(job_id: str, *, queue: str, status: JobStatus, payload: dict, created_at: datetime) -> Job:
    return Job(job_id=job_id, queue=queue, status=status, payload=payload, created_at=created_at)


async def test_list_returns_only_stale_queued_data_jobs_ordered(session) -> None:
    now = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    oldest = now - timedelta(hours=2)
    older = now - timedelta(hours=1)
    fresh = now - timedelta(seconds=5)
    session.add_all(
        [
            _job(
                "job_data_a",
                queue="data",
                status=JobStatus.QUEUED,
                payload={"job_kind": MARKET_DATA_ANALYSIS, "entity_id": "e1"},
                created_at=oldest,
            ),
            _job(
                "job_data_legacy",
                queue="data",
                status=JobStatus.QUEUED,
                payload={"entity_id": "e2"},  # pre-discriminator row
                created_at=older,
            ),
            _job(
                "job_data_fresh",
                queue="data",
                status=JobStatus.QUEUED,
                payload={"job_kind": TRADE_LOG_IMPORT},
                created_at=fresh,  # inside grace -> excluded
            ),
            _job(
                "job_data_running",
                queue="data",
                status=JobStatus.RUNNING,  # not QUEUED -> excluded
                payload={"job_kind": TRADE_LOG_IMPORT},
                created_at=oldest,
            ),
            _job(
                "job_backtest",
                queue="backtest",  # other queue -> excluded
                status=JobStatus.QUEUED,
                payload={},
                created_at=oldest,
            ),
        ]
    )
    await session.commit()

    rows = await list_redeliverable_data_jobs(session, grace_seconds=600, now=now)

    assert rows == [(MARKET_DATA_ANALYSIS, "job_data_a"), (None, "job_data_legacy")]


async def test_command_routes_known_skips_legacy_and_audits(session) -> None:
    past = datetime.now(UTC) - timedelta(hours=1)
    session.add_all(
        [
            _job(
                "job_md",
                queue="data",
                status=JobStatus.QUEUED,
                payload={"job_kind": MARKET_DATA_ANALYSIS},
                created_at=past,
            ),
            _job(
                "job_rd",
                queue="data",
                status=JobStatus.QUEUED,
                payload={"job_kind": RESEARCH_DATA_ANALYSIS},
                created_at=past,
            ),
            _job(
                "job_legacy",
                queue="data",
                status=JobStatus.QUEUED,
                payload={"entity_id": "e"},
                created_at=past,
            ),
        ]
    )
    await session.commit()

    result = await redeliver_data_queue_jobs(session, ADMIN, grace_seconds=0)
    await session.commit()

    assert result["scanned"] == 3
    assert result["skipped_unknown_kind"] == 1
    routed = {item["job_id"]: item["job_kind"] for item in result["redeliverable"]}
    assert routed == {"job_md": MARKET_DATA_ANALYSIS, "job_rd": RESEARCH_DATA_ANALYSIS}

    events = (
        (
            await session.execute(
                select(AuditEvent).where(AuditEvent.event_kind == "data_queue.redelivery_requested")
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].actor_principal_id == "user_admin"
    assert events[0].event_metadata == {
        "scanned": 3,
        "routable": 2,
        "skipped_unknown_kind": 1,
    }


async def test_command_requires_admin(session) -> None:
    before = int((await session.execute(select(func.count()).select_from(AuditEvent))).scalar_one())
    with pytest.raises(AdminPanelAccessRequiredError):
        await redeliver_data_queue_jobs(session, USER, grace_seconds=0)
    after = int((await session.execute(select(func.count()).select_from(AuditEvent))).scalar_one())
    assert after == before  # rejected before any audit
