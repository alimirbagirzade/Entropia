"""Market Data persistence (doc 11, decision D1).

The Root is the shared ``entity_registry`` (entity_type="market_dataset"); these
helpers create/append ``market_dataset_revision`` rows and the supporting asset/
mapping/validation/coverage rows. Sync mutators mirror ``repositories/entities.py``
(no commit); async readers return ORM rows for the queries layer.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import DeletionState, ValidationStatus
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState, ResolutionKind
from entropia.domain.revision.hashing import content_hash
from entropia.domain.revision.head import next_revision_no
from entropia.infrastructure.postgres.models import (
    DatasetCoverageSlice,
    EntityRegistry,
    MarketDatasetRevision,
    MarketProcessedAsset,
    MarketRawAsset,
    MarketSchemaMapping,
    MarketValidationIssue,
    MarketValidationRun,
)
from entropia.shared.ids import new_id

ENTITY_TYPE = "market_dataset"


async def create_market_dataset(
    session: AsyncSession,
    *,
    owner_principal_id: str | None,
    created_by_principal_id: str | None,
    market_data_type: MarketDataType,
    payload: dict[str, Any],
    title: str | None = None,
    instrument_id: str | None = None,
    revision_state: MarketRevisionState = MarketRevisionState.DRAFT,
    lifecycle_state: str | None = "active",
) -> tuple[EntityRegistry, MarketDatasetRevision]:
    """Create the registry Root + first market revision; point head at it.

    The root is flushed BEFORE the revision is added: SQLAlchemy's unit-of-work
    does not derive parent-before-child INSERT order from a bare ``ForeignKey``
    (there is no ``relationship()`` on the generic registry), so the two-table
    create order is made explicit to satisfy ``entity_id`` FK at flush time.
    """
    entity_id = new_id("mds")
    root = EntityRegistry(
        entity_id=entity_id,
        entity_type=ENTITY_TYPE,
        owner_principal_id=owner_principal_id,
        created_by_principal_id=created_by_principal_id,
        lifecycle_state=lifecycle_state,
        deletion_state=DeletionState.ACTIVE,
        current_revision_id=None,
        row_version=1,
    )
    session.add(root)
    await session.flush()
    revision = MarketDatasetRevision(
        revision_id=new_id("mrev"),
        entity_id=entity_id,
        revision_no=next_revision_no(None),
        parent_revision_id=None,
        supersedes_revision_id=None,
        market_data_type=market_data_type,
        revision_state=revision_state,
        title=title,
        instrument_id=instrument_id,
        payload=payload,
        content_hash=content_hash(payload),
        created_by_principal_id=created_by_principal_id,
    )
    session.add(revision)
    root.current_revision_id = revision.revision_id
    return root, revision


async def append_market_dataset_revision(
    session: AsyncSession,
    root: EntityRegistry,
    *,
    market_data_type: MarketDataType,
    payload: dict[str, Any],
    created_by_principal_id: str | None,
    revision_state: MarketRevisionState = MarketRevisionState.DRAFT,
    supersedes_revision_id: str | None = None,
    title: str | None = None,
    instrument_id: str | None = None,
) -> MarketDatasetRevision:
    """Insert revision N+1, advance the head pointer + row_version."""
    prior_no = await _max_revision_no(session, root.entity_id)
    revision = MarketDatasetRevision(
        revision_id=new_id("mrev"),
        entity_id=root.entity_id,
        revision_no=next_revision_no(prior_no),
        parent_revision_id=root.current_revision_id,
        supersedes_revision_id=supersedes_revision_id or root.current_revision_id,
        market_data_type=market_data_type,
        revision_state=revision_state,
        title=title,
        instrument_id=instrument_id,
        payload=payload,
        content_hash=content_hash(payload),
        created_by_principal_id=created_by_principal_id,
    )
    session.add(revision)
    root.current_revision_id = revision.revision_id
    root.row_version += 1
    return revision


async def find_raw_asset_by_hash(
    session: AsyncSession, *, entity_id: str, content_digest: str
) -> MarketRawAsset | None:
    """Return an existing identical raw-asset upload for this dataset (content
    dedup) — makes a retried upload idempotent regardless of Idempotency-Key."""
    stmt = (
        select(MarketRawAsset)
        .where(
            MarketRawAsset.entity_id == entity_id,
            MarketRawAsset.content_digest == content_digest,
        )
        .order_by(MarketRawAsset.asset_id)
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


def add_raw_asset(
    session: AsyncSession,
    *,
    entity_id: str,
    object_key: str,
    content_digest: str,
    size_bytes: int,
    revision_id: str | None = None,
    content_type: str | None = None,
    original_filename: str | None = None,
    uploaded_by_principal_id: str | None = None,
) -> MarketRawAsset:
    asset = MarketRawAsset(
        asset_id=new_id("mraw"),
        entity_id=entity_id,
        revision_id=revision_id,
        object_key=object_key,
        content_digest=content_digest,
        size_bytes=size_bytes,
        content_type=content_type,
        original_filename=original_filename,
        uploaded_by_principal_id=uploaded_by_principal_id,
    )
    session.add(asset)
    return asset


def add_processed_asset(
    session: AsyncSession,
    *,
    entity_id: str,
    object_key: str,
    content_digest: str,
    size_bytes: int,
    revision_id: str | None = None,
    raw_asset_id: str | None = None,
    row_count: int | None = None,
    schema_descriptor: dict[str, Any] | None = None,
) -> MarketProcessedAsset:
    asset = MarketProcessedAsset(
        asset_id=new_id("mproc"),
        entity_id=entity_id,
        revision_id=revision_id,
        raw_asset_id=raw_asset_id,
        object_key=object_key,
        content_digest=content_digest,
        size_bytes=size_bytes,
        row_count=row_count,
        schema_descriptor=schema_descriptor,
    )
    session.add(asset)
    return asset


async def get_processed_asset_for_revision(
    session: AsyncSession, revision_id: str
) -> MarketProcessedAsset | None:
    """The revision's processed Parquet asset (newest first if re-processed).

    Ordering note: real re-processing runs as SEPARATE analysis jobs, so rival
    assets differ in ``created_at`` (transaction start). Within one transaction
    (same ``created_at``) the ULID ``asset_id`` tiebreak is time-ordered only
    across milliseconds — same-millisecond writes are unspecified. Do not write
    two processed assets for one revision in a single transaction.
    """
    result = await session.execute(
        select(MarketProcessedAsset)
        .where(MarketProcessedAsset.revision_id == revision_id)
        .order_by(MarketProcessedAsset.created_at.desc(), MarketProcessedAsset.asset_id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_base_timeframe_for_revision(session: AsyncSession, revision_id: str) -> str | None:
    """The base bar timeframe a revision resolves to, when it is bar-timeframed.

    Read-only. ``None`` when the revision is missing, event-based, or carries no
    resolution value — callers then treat the base timeframe as unknown (a higher-TF
    override still resolves but cannot be validated as strictly coarser than the base).
    Read from the pinned immutable revision, so it is reproducibility-safe."""
    result = await session.execute(
        select(MarketDatasetRevision.resolution_value).where(
            MarketDatasetRevision.revision_id == revision_id,
            MarketDatasetRevision.resolution_kind == ResolutionKind.BAR,
        )
    )
    return result.scalar_one_or_none()


def upsert_schema_mapping(
    session: AsyncSession,
    *,
    entity_id: str,
    market_data_type: MarketDataType,
    proposed_mapping: dict[str, Any],
    revision_id: str | None = None,
    confirmed_mapping: dict[str, Any] | None = None,
    review_required: bool = False,
    mapping_version: int = 1,
    confirmed_by_principal_id: str | None = None,
) -> MarketSchemaMapping:
    """Insert a new mapping row (mapping is versioned, not mutated in place)."""
    mapping = MarketSchemaMapping(
        mapping_id=new_id("mmap"),
        entity_id=entity_id,
        revision_id=revision_id,
        market_data_type=market_data_type,
        mapping_version=mapping_version,
        proposed_mapping=proposed_mapping,
        confirmed_mapping=confirmed_mapping,
        review_required=review_required,
        confirmed_by_principal_id=confirmed_by_principal_id,
    )
    session.add(mapping)
    return mapping


def add_validation_run(
    session: AsyncSession,
    *,
    entity_id: str,
    status: ValidationStatus,
    revision_id: str | None = None,
    job_id: str | None = None,
    rows_checked: int | None = None,
    summary: dict[str, Any] | None = None,
) -> MarketValidationRun:
    run = MarketValidationRun(
        run_id=new_id("mval"),
        entity_id=entity_id,
        revision_id=revision_id,
        job_id=job_id,
        status=status,
        rows_checked=rows_checked,
        summary=summary,
    )
    session.add(run)
    return run


def add_validation_issue(
    session: AsyncSession,
    *,
    run_id: str,
    severity: ValidationStatus,
    rule_code: str,
    message: str,
    occurrences: int = 1,
    sample: dict[str, Any] | None = None,
) -> MarketValidationIssue:
    issue = MarketValidationIssue(
        issue_id=new_id("miss"),
        run_id=run_id,
        severity=severity,
        rule_code=rule_code,
        message=message,
        occurrences=occurrences,
        sample=sample,
    )
    session.add(issue)
    return issue


def add_coverage_slice(
    session: AsyncSession,
    *,
    entity_id: str,
    start_at: Any,
    end_at: Any,
    revision_id: str | None = None,
    row_count: int | None = None,
    gap_seconds: Any | None = None,
) -> DatasetCoverageSlice:
    slice_row = DatasetCoverageSlice(
        slice_id=new_id("mcov"),
        entity_id=entity_id,
        revision_id=revision_id,
        start_at=start_at,
        end_at=end_at,
        row_count=row_count,
        gap_seconds=gap_seconds,
    )
    session.add(slice_row)
    return slice_row


async def summarize_coverage_for_revisions(
    session: AsyncSession, revision_ids: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """Aggregate the contiguous coverage slices per revision into a compact digest.

    Returns ``{revision_id: {start_at, end_at, row_count, slice_count}}`` for the
    revisions that have at least one coverage slice; a revision the analysis job
    has not covered yet is simply ABSENT from the map, so the registry projection
    renders an honest "—" rather than a fabricated span (finding P-09). Values are
    JSON-safe (``isoformat`` / ``int``). One bounded aggregate query keyed by the
    current page's revision ids — never a per-row N+1.
    """
    ids = list(revision_ids)
    if not ids:
        return {}
    stmt = (
        select(
            DatasetCoverageSlice.revision_id,
            func.min(DatasetCoverageSlice.start_at),
            func.max(DatasetCoverageSlice.end_at),
            func.sum(DatasetCoverageSlice.row_count),
            func.count(),
        )
        .where(DatasetCoverageSlice.revision_id.in_(ids))
        .group_by(DatasetCoverageSlice.revision_id)
    )
    summary: dict[str, dict[str, Any]] = {}
    for revision_id, start_at, end_at, row_count, slice_count in (
        await session.execute(stmt)
    ).all():
        if revision_id is None:
            continue
        summary[revision_id] = {
            "start_at": start_at.isoformat() if start_at is not None else None,
            "end_at": end_at.isoformat() if end_at is not None else None,
            "row_count": int(row_count) if row_count is not None else None,
            "slice_count": int(slice_count),
        }
    return summary


async def find_approved_tick_revision_for_instrument(
    session: AsyncSession, instrument_id: str
) -> MarketDatasetRevision | None:
    """Newest APPROVED tick/trade revision for an instrument on an ACTIVE root (F-07i).

    The tick-data availability probe behind Ready Check's tick requirement: 'Use Tick
    Data = Yes' needs an approved tick/trade revision for the strategy's selected
    instrument (Master Ref §6.4). Mirrors ``_resolve_market_data_issues`` approval
    semantics — APPROVED revision + ACTIVE dataset root, matched by the dataset-level
    ``instrument_id``. Processed-asset presence is deliberately NOT required here (an
    asset can exist before approval, and a missing processed asset is a worker-time
    ``ASSET_UNAVAILABLE`` failure, not a readiness fact). ``None`` when none exists.
    """
    stmt = (
        select(MarketDatasetRevision)
        .join(EntityRegistry, EntityRegistry.entity_id == MarketDatasetRevision.entity_id)
        .where(
            MarketDatasetRevision.market_data_type == MarketDataType.TICK_TRADES,
            MarketDatasetRevision.revision_state == MarketRevisionState.APPROVED,
            MarketDatasetRevision.instrument_id == instrument_id,
            EntityRegistry.entity_type == ENTITY_TYPE,
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
        )
        .order_by(
            MarketDatasetRevision.created_at.desc(),
            MarketDatasetRevision.revision_id.desc(),
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_dataset_root(session: AsyncSession, entity_id: str) -> EntityRegistry | None:
    """Return the registry Root iff it is a market dataset."""
    root = await session.get(EntityRegistry, entity_id)
    if root is None or root.entity_type != ENTITY_TYPE:
        return None
    return root


async def get_revision(session: AsyncSession, revision_id: str) -> MarketDatasetRevision | None:
    return await session.get(MarketDatasetRevision, revision_id)


async def list_revisions(
    session: AsyncSession, entity_id: str, *, limit: int = 50
) -> Sequence[MarketDatasetRevision]:
    stmt = (
        select(MarketDatasetRevision)
        .where(MarketDatasetRevision.entity_id == entity_id)
        .order_by(MarketDatasetRevision.revision_no.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def query_revisions_for_owner(
    session: AsyncSession,
    *,
    owner_principal_id: str,
    limit: int = 50,
) -> Sequence[MarketDatasetRevision]:
    """Latest revision rows for datasets owned by the given principal (active)."""
    stmt = (
        select(MarketDatasetRevision)
        .join(EntityRegistry, EntityRegistry.entity_id == MarketDatasetRevision.entity_id)
        .where(
            EntityRegistry.entity_type == ENTITY_TYPE,
            EntityRegistry.owner_principal_id == owner_principal_id,
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
            MarketDatasetRevision.revision_id == EntityRegistry.current_revision_id,
        )
        .order_by(MarketDatasetRevision.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def _max_revision_no(session: AsyncSession, entity_id: str) -> int | None:
    stmt = select(func.max(MarketDatasetRevision.revision_no)).where(
        MarketDatasetRevision.entity_id == entity_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


__all__ = [
    "ENTITY_TYPE",
    "add_coverage_slice",
    "add_processed_asset",
    "add_raw_asset",
    "add_validation_issue",
    "add_validation_run",
    "append_market_dataset_revision",
    "create_market_dataset",
    "get_dataset_root",
    "get_processed_asset_for_revision",
    "get_revision",
    "list_revisions",
    "query_revisions_for_owner",
    "summarize_coverage_for_revisions",
    "upsert_schema_mapping",
]
