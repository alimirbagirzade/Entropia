"""Per-process metrics exposition (Module 20 §11, Stage 8b).

Golden signals come from the in-process registry; the operational gauges
(queue depth per queue/status, outbox lag, oldest RUNNING lease age) are
computed at scrape time from PostgreSQL and degrade gracefully: an unreachable
database omits the gauge block, it never fails the scrape.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select

from entropia.application.jobs.outbox_relay import outbox_lag_seconds
from entropia.domain.lifecycle.enums import JobStatus
from entropia.infrastructure.observability.metrics import render_process_metrics
from entropia.infrastructure.postgres.models import Job

router = APIRouter(tags=["metrics"])


async def _operational_gauges() -> str:
    from entropia.infrastructure.postgres.engine import get_session_factory

    lines: list[str] = []
    try:
        factory = get_session_factory()
        async with factory() as session:
            depth_stmt = select(Job.queue, Job.status, func.count()).group_by(Job.queue, Job.status)
            lines.append("# TYPE entropia_jobs_depth gauge")
            for queue, status, count in (await session.execute(depth_stmt)).all():
                lines.append(f'entropia_jobs_depth{{queue="{queue}",status="{status!s}"}} {count}')

            lag = await outbox_lag_seconds(session)
            lines.append("# TYPE entropia_outbox_lag_seconds gauge")
            lines.append(f"entropia_outbox_lag_seconds {0.0 if lag is None else lag:.3f}")

            lease_stmt = select(func.min(func.coalesce(Job.started_at, Job.claimed_at))).where(
                Job.status == JobStatus.RUNNING
            )
            oldest = (await session.execute(lease_stmt)).scalar_one_or_none()
            age = 0.0 if oldest is None else (datetime.now(UTC) - oldest).total_seconds()
            lines.append("# TYPE entropia_job_lease_age_seconds gauge")
            lines.append(f"entropia_job_lease_age_seconds {max(0.0, age):.3f}")
    except Exception:
        return "# operational gauges unavailable (database unreachable)\n"
    return "\n".join(lines) + "\n"


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics_endpoint() -> PlainTextResponse:
    body = render_process_metrics() + await _operational_gauges()
    return PlainTextResponse(content=body, media_type="text/plain; version=0.0.4")
