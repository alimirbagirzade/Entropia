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


@dramatiq.actor(queue_name="data", max_retries=3)
def run_trade_log_import(job_id: str) -> None:
    """Execute the durable Trade Log import job (Stage 3d, doc 05, CR-09).

    The ``jobs`` row created at enqueue time is the source of truth. This actor opens
    its own DB session, runs the parse/normalize/validate body, and commits — the
    request that enqueued it has long since returned (browser close never cancels it).
    """
    log.info("worker.trade_log_import.start", job_id=job_id)
    asyncio.run(_run_trade_log_import(job_id))
    log.info("worker.trade_log_import.done", job_id=job_id)


async def _run_trade_log_import(job_id: str) -> None:
    from entropia.application.jobs.trade_log import run_import
    from entropia.infrastructure.postgres.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        try:
            await run_import(session, job_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@dramatiq.actor(queue_name="backtest", max_retries=3)
def run_backtest_engine(job_id: str) -> None:
    """Execute the durable Backtest engine job (Stage 5a, doc 15, CR-09).

    The ``jobs`` + ``backtest_run`` rows created at admission time are the source of
    truth. This actor opens its own DB session, runs the manifest-pinned engine +
    result materialization, and commits — the request that admitted it has long
    since returned (browser close never cancels it, doc 15 §8.2).
    """
    log.info("worker.backtest_engine.start", job_id=job_id)
    asyncio.run(_run_backtest_engine(job_id))
    log.info("worker.backtest_engine.done", job_id=job_id)


async def _run_backtest_engine(job_id: str) -> None:
    from entropia.application.jobs.backtest_engine import run_backtest
    from entropia.infrastructure.postgres.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        try:
            await run_backtest(session, job_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@dramatiq.actor(queue_name="agent", max_retries=3)
def run_agent_tool(job_id: str) -> None:
    """Execute a durable agent Tool Gateway job on the ``agent`` plane (doc 18 §9.2).

    The ``jobs`` + ``agent_tool_call`` rows are the source of truth. The Tool
    Gateway's idempotency guard makes a redelivered call replay its recorded
    outcome instead of re-executing (AL-14)."""
    log.info("worker.agent_tool.start", job_id=job_id)
    asyncio.run(_run_agent_tool(job_id))
    log.info("worker.agent_tool.done", job_id=job_id)


@dramatiq.actor(queue_name="agent-high", max_retries=3)
def run_agent_tool_high(job_id: str) -> None:
    """Execute a durable agent Tool Gateway job on the ``agent-high`` plane — the
    heavier execution-scoped tools (backtest ready-check / request), doc 18 §9.2."""
    log.info("worker.agent_tool_high.start", job_id=job_id)
    asyncio.run(_run_agent_tool(job_id))
    log.info("worker.agent_tool_high.done", job_id=job_id)


async def _run_agent_tool(job_id: str) -> None:
    from entropia.application.jobs.agent_tools import run_tool_job
    from entropia.infrastructure.postgres.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        try:
            await run_tool_job(session, job_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@dramatiq.actor(queue_name="maintenance", max_retries=3)
def run_trash_purge(job_id: str) -> None:
    """Execute the durable Trash purge job (Stage 6c, doc 20 §8.3, §9.3).

    The ``jobs`` + ``trash_entries`` rows created at request time are the source
    of truth. This actor opens its own DB session, re-checks purge eligibility
    and commits the terminal purged/tombstone (or purge_failed) outcome — the
    Admin request that accepted it returned 202 long ago."""
    log.info("worker.trash_purge.start", job_id=job_id)
    asyncio.run(_run_trash_purge(job_id))
    log.info("worker.trash_purge.done", job_id=job_id)


async def _run_trash_purge(job_id: str) -> None:
    from entropia.application.jobs.purge import run_purge
    from entropia.infrastructure.postgres.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        try:
            await run_purge(session, job_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
