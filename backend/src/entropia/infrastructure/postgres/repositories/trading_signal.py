"""Trading Signal support-table persistence (Stage 3c, doc 04 §9.1).

Thin helpers over ``normalized_signal_event_revision`` (a standalone table, no
``entity_registry`` anchor); the Trading Signal root/revision reuse the 3a Mainboard
work-object repo. The raw upload uses the shared ``source_asset`` repo — its helpers
are re-exported here for back-compat (they moved to
``repositories/source_asset.py`` in 3d when Trade Log began sharing the table). These
helpers add rows and NEVER commit (the caller's tx owns the commit).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.trading_signal.enums import NormalizedRevisionStatus
from entropia.infrastructure.postgres.models import NormalizedSignalEventRevision
from entropia.infrastructure.postgres.repositories.source_asset import (
    create_source_asset,
    find_source_asset_by_hash,
    get_source_asset,
)
from entropia.shared.ids import new_id


async def create_normalized_revision(
    session: AsyncSession,
    *,
    source_asset_id: str,
    job_id: str | None,
    status: NormalizedRevisionStatus,
    instrument_id: str | None,
    accepted_count: int,
    skipped_count: int,
    events: list[dict[str, Any]],
    skipped_rows: list[dict[str, Any]],
    validation_summary: dict[str, Any] | None,
    earliest_available_time: datetime | None,
    content_hash: str,
    created_by_principal_id: str | None,
) -> NormalizedSignalEventRevision:
    """Insert an immutable normalized signal-event revision. No commit.

    ``source_asset`` must already exist (created + committed by the upload command
    that ran before this import), so the FK is satisfiable at flush time.
    """
    revision = NormalizedSignalEventRevision(
        normalized_revision_id=new_id("normsig"),
        source_asset_id=source_asset_id,
        job_id=job_id,
        status=status,
        instrument_id=instrument_id,
        accepted_count=accepted_count,
        skipped_count=skipped_count,
        events=events,
        skipped_rows=skipped_rows,
        validation_summary=validation_summary,
        earliest_available_time=earliest_available_time,
        content_hash=content_hash,
        work_object_revision_id=None,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(revision)
    return revision


async def get_normalized_revision(
    session: AsyncSession, normalized_revision_id: str
) -> NormalizedSignalEventRevision | None:
    return await session.get(NormalizedSignalEventRevision, normalized_revision_id)


async def get_normalized_revision_for_job(
    session: AsyncSession, job_id: str
) -> NormalizedSignalEventRevision | None:
    stmt = (
        select(NormalizedSignalEventRevision)
        .where(NormalizedSignalEventRevision.job_id == job_id)
        .order_by(NormalizedSignalEventRevision.normalized_revision_id)
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


def link_normalized_to_revision(
    normalized: NormalizedSignalEventRevision, work_object_revision_id: str
) -> None:
    """Pin a normalized revision to the Trading Signal work-object revision it backs."""
    normalized.work_object_revision_id = work_object_revision_id


__all__ = [
    "create_normalized_revision",
    "create_source_asset",
    "find_source_asset_by_hash",
    "get_normalized_revision",
    "get_normalized_revision_for_job",
    "get_source_asset",
    "link_normalized_to_revision",
]
