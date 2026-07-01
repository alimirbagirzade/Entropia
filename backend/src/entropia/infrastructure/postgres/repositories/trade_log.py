"""Trade Log support-table persistence (Stage 3d, doc 05 §10.1).

Thin helpers over ``canonical_trade_record_batch``. It is a standalone table (no
``entity_registry`` anchor); the Trade Log root/revision reuse the 3a Mainboard
work-object repo, and the raw upload uses the shared ``source_asset`` repo. These
helpers add rows and NEVER commit (the caller's tx owns the commit).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.trade_log.enums import RecordBatchStatus
from entropia.infrastructure.postgres.models import CanonicalTradeRecordBatch
from entropia.shared.ids import new_id


async def create_record_batch(
    session: AsyncSession,
    *,
    source_asset_id: str,
    job_id: str | None,
    status: RecordBatchStatus,
    instrument_id: str | None,
    accepted_count: int,
    skipped_count: int,
    records: list[dict[str, Any]],
    skipped_rows: list[dict[str, Any]],
    validation_summary: dict[str, Any] | None,
    earliest_entry_time: datetime | None,
    latest_exit_time: datetime | None,
    content_hash: str,
    created_by_principal_id: str | None,
) -> CanonicalTradeRecordBatch:
    """Insert an immutable canonical trade-record batch. No commit.

    ``source_asset`` must already exist (created + committed by the upload command
    that ran before this import), so the FK is satisfiable at flush time.
    """
    batch = CanonicalTradeRecordBatch(
        record_batch_id=new_id("tlbatch"),
        source_asset_id=source_asset_id,
        job_id=job_id,
        status=status,
        instrument_id=instrument_id,
        accepted_count=accepted_count,
        skipped_count=skipped_count,
        records=records,
        skipped_rows=skipped_rows,
        validation_summary=validation_summary,
        earliest_entry_time=earliest_entry_time,
        latest_exit_time=latest_exit_time,
        content_hash=content_hash,
        work_object_revision_id=None,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(batch)
    return batch


async def get_record_batch(
    session: AsyncSession, record_batch_id: str
) -> CanonicalTradeRecordBatch | None:
    return await session.get(CanonicalTradeRecordBatch, record_batch_id)


async def get_record_batch_for_job(
    session: AsyncSession, job_id: str
) -> CanonicalTradeRecordBatch | None:
    stmt = (
        select(CanonicalTradeRecordBatch)
        .where(CanonicalTradeRecordBatch.job_id == job_id)
        .order_by(CanonicalTradeRecordBatch.record_batch_id)
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


def link_batch_to_revision(batch: CanonicalTradeRecordBatch, work_object_revision_id: str) -> None:
    """Pin a record batch to the Trade Log work-object revision it backs."""
    batch.work_object_revision_id = work_object_revision_id


__all__ = [
    "create_record_batch",
    "get_record_batch",
    "get_record_batch_for_job",
    "link_batch_to_revision",
]
