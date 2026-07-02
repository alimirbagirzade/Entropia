"""Scheduler maintenance sweeps (Module 20 §6; INF-03, INF-09, Stage 8b).

Pure DB logic, one call per scheduler tick, no commit here (the scheduler tick
commits). Two sweeps:

- ``recover_stale_jobs`` — a worker crash leaves a job RUNNING forever (INF-09).
  A RUNNING job whose ``started_at``/``claimed_at`` is older than the stale
  threshold is recovered: attempts += 1, then either back to QUEUED (for
  redelivery) or terminally FAILED once ``max_attempts`` is exhausted. Every
  recovery is audited. Workers are redelivery-idempotent (proven per plane), so
  a half-produced artifact is never published as a result.

- ``redeliverable_queued_jobs`` — a Redis restart may lose queued messages while
  the durable ``jobs`` row survives (INF-03). QUEUED rows older than the grace
  window are re-dispatched by the scheduler through the queue->actor registry.
  Re-sending an in-flight message is safe (at-least-once + idempotent workers).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import ActorKind, JobStatus
from entropia.infrastructure.postgres.models import Job
from entropia.infrastructure.postgres.repositories import audit as audit_repo

_JOB_TARGET = "job"
STALE_RECOVERY_CODE = "STALE_JOB_RECOVERED"


async def recover_stale_jobs(
    session: AsyncSession,
    *,
    stale_after_seconds: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Recover RUNNING jobs abandoned by a crashed worker. Does not commit."""
    reference = now or datetime.now(UTC)
    threshold = reference - timedelta(seconds=stale_after_seconds)
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.RUNNING)
        .where(func_started(Job) < threshold)
        .with_for_update(skip_locked=True)
    )
    jobs = list((await session.execute(stmt)).scalars().all())

    requeued: list[tuple[str, str]] = []
    failed: list[str] = []
    for job in jobs:
        job.attempts += 1
        if job.attempts >= job.max_attempts:
            job.status = JobStatus.FAILED_FINAL
            job.finished_at = reference
            job.error = {
                "code": STALE_RECOVERY_CODE,
                "message": "Worker abandoned the job past the stale threshold; "
                "max attempts exhausted.",
            }
            failed.append(job.job_id)
            new_state = JobStatus.FAILED_FINAL.value
        else:
            job.status = JobStatus.QUEUED
            job.claimed_at = None
            job.started_at = None
            requeued.append((job.queue, job.job_id))
            new_state = JobStatus.QUEUED.value
        audit_repo.add_audit_event(
            session,
            event_kind="job.stale_recovered",
            actor_principal_id=None,
            actor_kind=ActorKind.SYSTEM_SERVICE,
            target_entity_id=job.job_id,
            target_entity_type=_JOB_TARGET,
            previous_state=JobStatus.RUNNING.value,
            new_state=new_state,
            reason=STALE_RECOVERY_CODE,
            correlation_id=job.correlation_id,
        )
    return {"requeued": requeued, "failed": failed}


def func_started(job_model: type[Job]) -> Any:
    """The stale clock: ``started_at`` when set, else ``claimed_at``, else the
    row's creation time (a job can crash between claim and start)."""
    from sqlalchemy import func as sa_func

    return sa_func.coalesce(job_model.started_at, job_model.claimed_at, job_model.created_at)


async def redeliverable_queued_jobs(
    session: AsyncSession,
    *,
    grace_seconds: int,
    now: datetime | None = None,
) -> list[tuple[str, str]]:
    """QUEUED jobs older than the grace window -> ``(queue, job_id)`` for
    re-dispatch (INF-03). Read-only; the durable row is already the truth."""
    reference = now or datetime.now(UTC)
    threshold = reference - timedelta(seconds=grace_seconds)
    stmt = (
        select(Job.queue, Job.job_id)
        .where(Job.status == JobStatus.QUEUED)
        .where(Job.created_at < threshold)
        .order_by(Job.created_at)
    )
    return [(str(queue), str(job_id)) for queue, job_id in (await session.execute(stmt)).all()]


__all__ = [
    "STALE_RECOVERY_CODE",
    "recover_stale_jobs",
    "redeliverable_queued_jobs",
]
