"""Stage 8b — hardening integration: outbox relay/fan-out feed + job recovery.

Auto-skips without PostgreSQL. Covers the scheduler's durable outbox checkpoint
(publish batches + lag reporting), the SSE hub's loss-tolerant cursor feed over
the SAME outbox rows (Module 20 §10 fan-out taxonomy for every domain), stale
RUNNING recovery (INF-09: requeue then terminal FAILED at max attempts, each
audited) and the INF-03 QUEUED redelivery sweep.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from entropia.application.jobs.maintenance import (
    STALE_RECOVERY_CODE,
    recover_stale_jobs,
    redeliverable_queued_jobs,
)
from entropia.application.jobs.outbox_relay import (
    fetch_events_after,
    latest_event_id,
    outbox_lag_seconds,
    relay_unpublished,
)
from entropia.apps.api.sse import SseHub, sse_event_name
from entropia.domain.lifecycle.enums import JobStatus
from entropia.infrastructure.postgres.models import AuditEvent, Job
from entropia.infrastructure.postgres.models.audit import OutboxEvent
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.queues.enqueue import enqueue_job

pytestmark = pytest.mark.integration


def _add_event(
    session, event_type: str, resource_type: str, resource_id: str, *, event_id: str
) -> None:
    """Insert with an EXPLICIT id: within one millisecond ``new_id`` suffixes are
    random, so tests pin ids to make relay/feed ordering deterministic."""
    event = audit_repo.add_outbox_event(
        session,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        payload={"resource_id": resource_id},
        correlation_id="corr_hard",
    )
    event.id = event_id


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


# --------------------------------------------------------------------------- #
# Outbox relay — the scheduler's durable checkpoint                            #
# --------------------------------------------------------------------------- #


async def test_outbox_relay_marks_published_and_reports_lag(session) -> None:
    _add_event(session, "backtest_requested", "backtest_run", "btrun_1", event_id="obx_a1")
    _add_event(session, "market.revision_approved", "market_dataset", "md_1", event_id="obx_a2")
    _add_event(session, "agent_task_created", "agent_task", "agttask_1", event_id="obx_a3")
    await session.commit()

    lag_before = await outbox_lag_seconds(session)
    assert lag_before is not None and lag_before >= 0.0

    relayed = await relay_unpublished(session, batch_size=10)
    await session.commit()
    assert [e["resource_id"] for e in relayed] == ["btrun_1", "md_1", "agttask_1"]

    unpublished = await _count_unpublished(session)
    assert unpublished == 0
    assert await outbox_lag_seconds(session) is None  # fully relayed

    # A second pass finds nothing — the checkpoint is durable, not repeated.
    assert await relay_unpublished(session, batch_size=10) == []


async def _count_unpublished(session) -> int:
    stmt = select(func.count()).where(OutboxEvent.published_at.is_(None))
    return int((await session.execute(stmt)).scalar_one())


async def test_relay_batch_respects_limit_and_order(session) -> None:
    for index in range(5):
        _add_event(session, "resource.changed", "demo", f"res_{index}", event_id=f"obx_b{index}")
    await session.commit()

    first = await relay_unpublished(session, batch_size=2)
    await session.commit()
    second = await relay_unpublished(session, batch_size=10)
    await session.commit()

    assert [e["resource_id"] for e in first] == ["res_0", "res_1"]
    assert [e["resource_id"] for e in second] == ["res_2", "res_3", "res_4"]


# --------------------------------------------------------------------------- #
# SSE feed — loss-tolerant cursor tail over the same outbox                    #
# --------------------------------------------------------------------------- #


async def test_sse_feed_streams_only_events_after_cursor(session) -> None:
    _add_event(session, "market.dataset_created", "market_dataset", "md_old", event_id="obx_c1")
    await session.commit()

    cursor = await latest_event_id(session)  # boot-time tail: history never streams
    assert cursor is not None

    _add_event(session, "backtest_requested", "backtest_run", "btrun_new", event_id="obx_c2")
    _add_event(session, "trash.restored", "trash_entry", "trash_new", event_id="obx_c3")
    await session.commit()

    events = await fetch_events_after(session, cursor_id=cursor)
    assert [e["resource_id"] for e in events] == ["btrun_new", "trash_new"]
    # The feed is independent of the scheduler's published checkpoint.
    await relay_unpublished(session, batch_size=10)
    await session.commit()
    assert [e["resource_id"] for e in await fetch_events_after(session, cursor_id=cursor)] == [
        "btrun_new",
        "trash_new",
    ]


async def test_sse_hub_broadcast_and_taxonomy(session) -> None:
    hub = SseHub()
    queue_a = hub.subscribe()
    queue_b = hub.subscribe()
    hub.publish({"id": "obx_1", "event_type": "x", "resource_type": "demo"})
    assert queue_a.get_nowait()["id"] == "obx_1"
    assert queue_b.get_nowait()["id"] == "obx_1"
    hub.unsubscribe(queue_b)
    hub.publish({"id": "obx_2", "event_type": "x", "resource_type": "demo"})
    assert queue_a.get_nowait()["id"] == "obx_2"
    assert queue_b.qsize() == 0
    assert hub.subscriber_count == 1

    # Module 20 §10 taxonomy across all domains.
    assert sse_event_name("backtest_requested", "backtest_run") == "backtest.run.updated"
    assert sse_event_name("result.soft_deleted", "backtest_result") == "backtest.run.updated"
    assert sse_event_name("job.updated", "job") == "job.updated"
    assert sse_event_name("agent_task_created", "agent_task") == "agent.task.updated"
    assert sse_event_name("artifact_created", "hypothesis_artifact") == "agent.task.updated"
    assert sse_event_name("market.revision_approved", "market_dataset") == "resource.changed"
    assert sse_event_name("manual.document_published", "manual_document") == "resource.changed"


# --------------------------------------------------------------------------- #
# INF-09: stale RUNNING recovery                                               #
# --------------------------------------------------------------------------- #


def _job(session, *, queue: str, status: JobStatus, age_seconds: int, attempts: int = 0) -> Job:
    job = enqueue_job(session, queue=queue, payload={"run_id": "r"}, max_attempts=3)
    stamp = datetime.now(UTC) - timedelta(seconds=age_seconds)
    job.status = status
    job.attempts = attempts
    job.created_at = stamp
    if status is JobStatus.RUNNING:
        job.claimed_at = stamp
        job.started_at = stamp
    return job


async def test_stale_running_job_requeues_then_fails_terminally(session) -> None:
    stale = _job(session, queue="backtest", status=JobStatus.RUNNING, age_seconds=3600)
    fresh = _job(session, queue="backtest", status=JobStatus.RUNNING, age_seconds=10)
    await session.commit()

    outcome = await recover_stale_jobs(session, stale_after_seconds=600)
    await session.commit()

    assert outcome["requeued"] == [("backtest", stale.job_id)]
    assert outcome["failed"] == []
    assert stale.status is JobStatus.QUEUED
    assert stale.attempts == 1
    assert stale.started_at is None and stale.claimed_at is None
    assert fresh.status is JobStatus.RUNNING  # untouched

    # Exhaust the budget: recovered twice more -> terminal FAILED (no zombie
    # result is ever published; workers are idempotent on redelivery).
    for _ in range(2):
        stamp = datetime.now(UTC) - timedelta(seconds=3600)
        stale.status = JobStatus.RUNNING
        stale.started_at = stamp
        await session.commit()
        outcome = await recover_stale_jobs(session, stale_after_seconds=600)
        await session.commit()

    assert stale.status is JobStatus.FAILED_FINAL
    assert stale.attempts == 3
    assert stale.error is not None and stale.error["code"] == STALE_RECOVERY_CODE

    kinds = (
        (
            await session.execute(
                select(AuditEvent.event_kind).where(AuditEvent.target_entity_id == stale.job_id)
            )
        )
        .scalars()
        .all()
    )
    assert list(kinds).count("job.stale_recovered") == 3  # every recovery audited


# --------------------------------------------------------------------------- #
# INF-03: durable QUEUED redelivery sweep                                      #
# --------------------------------------------------------------------------- #


async def test_redeliverable_sweep_targets_only_old_queued_jobs(session) -> None:
    old_backtest = _job(session, queue="backtest", status=JobStatus.QUEUED, age_seconds=3600)
    old_data = _job(session, queue="data", status=JobStatus.QUEUED, age_seconds=3600)
    _job(session, queue="backtest", status=JobStatus.QUEUED, age_seconds=5)
    _job(session, queue="backtest", status=JobStatus.RUNNING, age_seconds=3600)
    await session.commit()

    rows = await redeliverable_queued_jobs(session, grace_seconds=600)

    # Both durable rows are reported (the sweep is queue-agnostic); the
    # scheduler's ACTOR_BY_QUEUE registry decides what is safe to re-send —
    # the multi-actor ``data`` queue is deliberately absent from it.
    assert ("backtest", old_backtest.job_id) in rows
    assert ("data", old_data.job_id) in rows
    assert len(rows) == 2

    from entropia.apps.scheduler.__main__ import ACTOR_BY_QUEUE

    assert "data" not in ACTOR_BY_QUEUE
    assert {"backtest", "agent", "agent-high", "maintenance"} <= set(ACTOR_BY_QUEUE)
