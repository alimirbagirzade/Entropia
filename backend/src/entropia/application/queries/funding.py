"""Resolve a strategy's pinned Funding source into an available-time-safe schedule (F-11).

The backtest worker calls ``resolve_funding_schedule`` when a strategy's ``FundingPolicy``
is enabled. It dereferences the pinned ``funding_rate`` Research revision, enforces the
consumption policy (Approved + Research-Backtest scope + funding category + content-hash
integrity — doc 12 §2/§9.2), loads its native rows from object storage, and builds the pure
``FundingSchedule`` the engine consumes. Every failure is a fail-closed
``FundingSourceInvalid`` (422) — a funding-enabled run never silently books zero cost.

The row loader is injectable (default: the S3-backed native-asset reader) so integration
tests exercise the full resolve → build chain without object storage — mirroring how the
bar source injects ``stream_bars`` (the engine + this resolver stay I/O-testable).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.backtest.funding import FundingSchedule, build_funding_schedule
from entropia.domain.research_data.enums import (
    ResearchCategory,
    ResearchRevisionState,
    UsageScope,
)
from entropia.domain.strategy.config import FundingPolicy
from entropia.infrastructure.postgres.repositories import research_data as research_repo
from entropia.infrastructure.s3.parquet_stream import stream_processed_batches
from entropia.shared.errors import FundingSourceInvalid

# object_key -> the native funding rows (materialized; a funding series is small).
FundingRowLoader = Callable[[str], list[dict[str, Any]]]


def _load_native_rows_from_s3(object_key: str) -> list[dict[str, Any]]:
    """Read every row of a research native Parquet asset (funding series are small)."""
    rows: list[dict[str, Any]] = []
    for batch in stream_processed_batches(object_key):
        rows.extend(batch)
    return rows


async def resolve_funding_schedule(
    session: AsyncSession,
    funding: FundingPolicy,
    *,
    load_rows: FundingRowLoader = _load_native_rows_from_s3,
) -> FundingSchedule | None:
    """Resolve the pinned funding source, or ``None`` when funding is off.

    Fail-closed (``FundingSourceInvalid``) on any provenance/policy/schema violation so a
    funding-enabled run either applies a verifiable cost or fails — never a silent no-op."""
    if not funding.enabled:
        return None
    revision_id = funding.source_revision_id
    if not revision_id:
        raise FundingSourceInvalid("Funding is enabled but no source revision is pinned.")

    revision = await research_repo.get_revision(session, revision_id)
    if revision is None:
        raise FundingSourceInvalid(f"Pinned funding revision '{revision_id}' was not found.")
    if funding.source_content_hash and revision.content_hash != funding.source_content_hash:
        raise FundingSourceInvalid(
            f"Funding revision '{revision_id}' content hash does not match the pinned hash.",
        )
    if revision.revision_state != ResearchRevisionState.APPROVED:
        raise FundingSourceInvalid(
            f"Funding revision '{revision_id}' is not Approved (state={revision.revision_state}).",
        )
    if revision.usage_scope != UsageScope.RESEARCH_BACKTEST:
        raise FundingSourceInvalid(
            f"Funding revision '{revision_id}' usage scope '{revision.usage_scope}' forbids "
            "backtest consumption.",
        )
    if revision.category_key != ResearchCategory.FUNDING_RATE.value:
        raise FundingSourceInvalid(
            f"Funding revision '{revision_id}' category '{revision.category_key}' is not "
            f"'{ResearchCategory.FUNDING_RATE.value}'.",
        )
    if revision.available_time_policy is None:
        raise FundingSourceInvalid(
            f"Funding revision '{revision_id}' has no available-time policy.",
        )
    if revision.native_asset_id is None:
        raise FundingSourceInvalid(
            f"Funding revision '{revision_id}' has no parsed native asset to read.",
        )

    native = await research_repo.get_native_asset(session, revision.native_asset_id)
    if native is None or not native.object_key:
        raise FundingSourceInvalid(
            f"Funding revision '{revision_id}' native asset is missing its stored object.",
        )

    rows = load_rows(native.object_key)
    descriptor = native.schema_descriptor or {}
    columns = list(descriptor.get("columns") or (rows[0].keys() if rows else []))
    return build_funding_schedule(
        rows,
        source_revision_id=revision.revision_id,
        columns=columns,
        policy=revision.available_time_policy,
        delay_seconds=revision.available_delay_seconds,
    )


__all__ = ["FundingRowLoader", "resolve_funding_schedule"]
