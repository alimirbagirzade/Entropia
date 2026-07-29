"""Per-process metrics exposition (Module 20 §11, Stage 8b).

Golden signals come from the in-process registry; the operational gauges
(queue depth per queue/status, outbox lag, oldest RUNNING lease age) are
computed at scrape time from PostgreSQL and degrade gracefully: an unreachable
database omits the gauge block, it never fails the scrape.

The exposition is CREDENTIALED (finding O-22): those gauges are operational
intelligence — how deep each queue is, how far the outbox has fallen behind, how
long the oldest lease has been held — so the scraper presents the static
``ENTROPIA_METRICS_TOKEN`` as a Bearer credential and the gate runs BEFORE any
database work. The route deliberately does NOT depend on ``request_context``: a
scraper is not a domain actor, and binding one would open a request-scoped
session (plus an actor resolution round-trip) on every scrape. It also stays in
``hardening._EXEMPT_SUFFIXES``: shedding a monitoring scrape blinds the operator
exactly when load is highest, and an unauthenticated scrape is now rejected
before it costs a query anyway.
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select

from entropia.application.jobs.outbox_relay import outbox_lag_seconds
from entropia.apps.api.deps import bearer_token
from entropia.config import get_settings
from entropia.domain.lifecycle.enums import JobStatus
from entropia.infrastructure.observability import get_logger
from entropia.infrastructure.observability.metrics import render_process_metrics
from entropia.infrastructure.postgres.models import Job
from entropia.shared.errors import MetricsScrapeForbiddenError, MetricsScrapeUnauthorizedError

router = APIRouter(tags=["metrics"])
log = get_logger("metrics")


def require_metrics_scraper(request: Request) -> None:
    """Authorize a metrics scrape, or raise 401/403 (finding O-22).

    * Token configured -> constant-time compare against the Bearer credential;
      a missing credential is 401, a wrong one is 403.
    * Token NOT configured -> fail-closed in production (403: a deployment that
      forgot to set the credential must not publish its operational gauges to
      anyone who can reach the port), open in the local/dev profile so
      ``curl localhost/metrics`` keeps working during development.
    """
    settings = get_settings()
    configured = settings.metrics_token
    if not configured:
        if settings.is_production:
            raise MetricsScrapeForbiddenError(
                "Metrics scraping is disabled until ENTROPIA_METRICS_TOKEN is configured."
            )
        return
    token = bearer_token(request)
    if token is None:
        raise MetricsScrapeUnauthorizedError()
    if not hmac.compare_digest(token, configured):
        raise MetricsScrapeForbiddenError()


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
    except Exception as exc:
        # The scrape still degrades to the comment line — only the silence
        # changes. Log the exception CLASS, never str(exc): driver errors echo
        # the DSN, and this body is served to a scraper.
        log.warning("metrics.operational_gauges_probe_failed", error_type=type(exc).__name__)
        return "# operational gauges unavailable (database unreachable)\n"
    return "\n".join(lines) + "\n"


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
    dependencies=[Depends(require_metrics_scraper)],
)
async def metrics_endpoint() -> PlainTextResponse:
    body = render_process_metrics() + await _operational_gauges()
    return PlainTextResponse(content=body, media_type="text/plain; version=0.0.4")
