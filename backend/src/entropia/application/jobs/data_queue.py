"""Data-queue job-kind taxonomy + operator redelivery listing (INF-03, Module 20 §6).

The ``data`` queue multiplexes four durable actor types — market-data analysis,
research-data analysis, Trading Signal import, Trade Log import. A lost broker
message leaves the durable ``jobs`` row QUEUED; the scheduler's stale/redeliver
sweeps mark it back to QUEUED but — unlike the single-actor queues in
``ACTOR_BY_QUEUE`` — deliberately do NOT auto-redeliver it, because the row alone
cannot say which of the four actors to re-dispatch (doc 20 §6). This module gives
each data job an explicit ``job_kind`` discriminator in its payload so an operator
recovery action can route a stuck job back to the correct actor.

Re-dispatch stays an EXPLICIT operator action — nothing here runs automatically
and the scheduler is untouched. Rows enqueued before the discriminator existed
carry no ``job_kind`` (``data_job_kind`` returns ``None``); the operator tool
counts them as un-routable rather than guessing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import JobStatus
from entropia.infrastructure.postgres.models import Job

DATA_QUEUE = "data"

MARKET_DATA_ANALYSIS = "market_data_analysis"
RESEARCH_DATA_ANALYSIS = "research_data_analysis"
TRADING_SIGNAL_IMPORT = "trading_signal_import"
TRADE_LOG_IMPORT = "trade_log_import"

DATA_JOB_KINDS: frozenset[str] = frozenset(
    {
        MARKET_DATA_ANALYSIS,
        RESEARCH_DATA_ANALYSIS,
        TRADING_SIGNAL_IMPORT,
        TRADE_LOG_IMPORT,
    }
)


def data_job_kind(payload: dict[str, Any] | None) -> str | None:
    """The canonical ``job_kind`` carried by a data-queue job payload, or ``None``
    when the row predates the discriminator or carries an unrecognized value."""
    if not payload:
        return None
    kind = payload.get("job_kind")
    if isinstance(kind, str) and kind in DATA_JOB_KINDS:
        return kind
    return None


async def list_redeliverable_data_jobs(
    session: AsyncSession,
    *,
    grace_seconds: int,
    now: datetime | None = None,
) -> list[tuple[str | None, str]]:
    """Durable ``data``-queue jobs still QUEUED past the grace window -> ordered
    ``(job_kind, job_id)`` pairs (``job_kind`` is ``None`` for un-routable legacy
    rows). Read-only; the durable row is already the source of truth (INF-03)."""
    reference = now or datetime.now(UTC)
    threshold = reference - timedelta(seconds=grace_seconds)
    stmt = (
        select(Job.payload, Job.job_id)
        .where(Job.queue == DATA_QUEUE)
        .where(Job.status == JobStatus.QUEUED)
        .where(Job.created_at < threshold)
        .order_by(Job.created_at)
    )
    return [
        (data_job_kind(payload), str(job_id))
        for payload, job_id in (await session.execute(stmt)).all()
    ]


__all__ = [
    "DATA_JOB_KINDS",
    "DATA_QUEUE",
    "MARKET_DATA_ANALYSIS",
    "RESEARCH_DATA_ANALYSIS",
    "TRADE_LOG_IMPORT",
    "TRADING_SIGNAL_IMPORT",
    "data_job_kind",
    "list_redeliverable_data_jobs",
]
