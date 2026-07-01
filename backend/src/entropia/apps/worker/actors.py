"""Infrastructure-level actors (no product domain yet).

Importing the broker first binds it process-wide, so the @dramatiq.actor
decorators below register against the canonical Redis broker.
"""

from __future__ import annotations

import asyncio

import dramatiq

from entropia.infrastructure.observability import get_logger
from entropia.infrastructure.queues import broker as _broker  # noqa: F401  (installs broker)

log = get_logger("worker")


@dramatiq.actor(queue_name="maintenance", max_retries=3)
def system_heartbeat(note: str = "ping") -> None:
    """Proves the queue/worker round-trip works end to end."""
    log.info("worker.heartbeat", note=note)


@dramatiq.actor(queue_name="data", max_retries=3)
def run_market_data_analysis(job_id: str) -> None:
    """Execute the durable market-data analysis job (decision D4).

    The ``jobs`` row created at enqueue time is the source of truth. This actor
    opens its own DB session, runs the analysis body, and commits — the request
    that enqueued it has long since returned (browser close never cancels it).
    """
    log.info("worker.market_analysis.start", job_id=job_id)
    asyncio.run(_run_market_data_analysis(job_id))
    log.info("worker.market_analysis.done", job_id=job_id)


async def _run_market_data_analysis(job_id: str) -> None:
    from entropia.application.jobs.market_data import run_analysis
    from entropia.infrastructure.postgres.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        try:
            await run_analysis(session, job_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@dramatiq.actor(queue_name="data", max_retries=3)
def run_research_data_analysis(job_id: str) -> None:
    """Execute the durable research-data analysis job (decision DR8).

    The ``jobs`` row created at enqueue time is the source of truth. This actor
    opens its own DB session, runs the analysis body, and commits — the request
    that enqueued it has long since returned (browser close never cancels it).
    """
    log.info("worker.research_analysis.start", job_id=job_id)
    asyncio.run(_run_research_data_analysis(job_id))
    log.info("worker.research_analysis.done", job_id=job_id)


async def _run_research_data_analysis(job_id: str) -> None:
    from entropia.application.jobs.research_data import run_analysis
    from entropia.infrastructure.postgres.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        try:
            await run_analysis(session, job_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@dramatiq.actor(queue_name="data", max_retries=3)
def run_trading_signal_import(job_id: str) -> None:
    """Execute the durable Trading Signal import job (Stage 3c, doc 04, CR-09).

    The ``jobs`` row created at enqueue time is the source of truth. This actor opens
    its own DB session, runs the parse/map/validate body, and commits — the request
    that enqueued it has long since returned (browser close never cancels it).
    """
    log.info("worker.trading_signal_import.start", job_id=job_id)
    asyncio.run(_run_trading_signal_import(job_id))
    log.info("worker.trading_signal_import.done", job_id=job_id)


async def _run_trading_signal_import(job_id: str) -> None:
    from entropia.application.jobs.trading_signal import run_import
    from entropia.infrastructure.postgres.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        try:
            await run_import(session, job_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
