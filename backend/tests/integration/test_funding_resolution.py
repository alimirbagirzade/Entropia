"""F-11 — worker-side funding source resolution + provenance gate (doc 12 §2/§8.4).

DB-backed (isolated schema) but object-storage-free: ``resolve_funding_schedule`` takes an
injected ``load_rows`` so the resolve → build chain is exercised without S3 (mirroring the
bar-source ``stream_bars`` injection). Proves the fail-closed provenance gate: only an
Approved + Research-Backtest + funding-category revision whose content hash matches is
consumed; anything else raises ``FundingSourceInvalid`` (never a silent zero-cost run).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from entropia.application.queries.funding import resolve_funding_schedule
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    ResearchCategory,
    ResearchRevisionState,
    UsageScope,
)
from entropia.domain.strategy.config import FundingPolicy
from entropia.infrastructure.postgres.models.registry import EntityRegistry
from entropia.infrastructure.postgres.models.research_data import (
    ResearchDatasetRevision,
    ResearchNativeAsset,
)
from entropia.shared.errors import FundingSourceInvalid

pytestmark = pytest.mark.asyncio

_HASH = "fundinghash_1"
_ROWS = [
    {"event_time": "2024-01-02T00:00:00Z", "funding_rate": "0.0002"},
    {"event_time": "2024-01-01T00:00:00Z", "funding_rate": "0.0001"},
]


def _rows(_object_key: str) -> list[dict[str, Any]]:
    return list(_ROWS)


async def _seed_funding_revision(
    session: Any,
    *,
    state: ResearchRevisionState = ResearchRevisionState.APPROVED,
    scope: UsageScope = UsageScope.RESEARCH_BACKTEST,
    category: str = ResearchCategory.FUNDING_RATE.value,
    with_native: bool = True,
    content_hash: str = _HASH,
) -> str:
    """Insert a minimal funding Research revision (+ native asset) directly; return its id."""
    entity_id = "rdent_fund_1"
    session.add(EntityRegistry(entity_id=entity_id, entity_type="research_dataset", row_version=1))
    native_id = "rnat_fund_1"
    if with_native:
        session.add(
            ResearchNativeAsset(
                asset_id=native_id,
                entity_id=entity_id,
                object_key="s3://processed/funding.parquet",
                content_digest="dig_1",
                size_bytes=128,
                row_count=len(_ROWS),
                schema_descriptor={"columns": ["event_time", "funding_rate"]},
            )
        )
    revision_id = "rdrev_fund_1"
    session.add(
        ResearchDatasetRevision(
            revision_id=revision_id,
            entity_id=entity_id,
            revision_no=1,
            revision_state=state,
            category_key=category,
            native_asset_id=native_id if with_native else None,
            available_time_policy=AvailableTimePolicy.SAME_AS_EVENT_TIME,
            available_delay_seconds=None,
            usage_scope=scope,
            payload={},
            content_hash=content_hash,
        )
    )
    await session.flush()
    return revision_id


def _policy(revision_id: str, *, content_hash: str = _HASH, enabled: bool = True) -> FundingPolicy:
    return FundingPolicy(
        enabled=enabled,
        source_root_id="rdent_fund_1",
        source_revision_id=revision_id,
        source_content_hash=content_hash,
    )


async def test_resolves_an_approved_funding_revision_into_a_sorted_schedule(session) -> None:
    revision_id = await _seed_funding_revision(session)
    sched = await resolve_funding_schedule(session, _policy(revision_id), load_rows=_rows)
    assert sched is not None
    assert sched.source_revision_id == revision_id
    assert [r.available_at for r in sched.records] == [
        datetime(2024, 1, 1, tzinfo=UTC),
        datetime(2024, 1, 2, tzinfo=UTC),
    ]
    assert sched.records[0].rate == Decimal("0.0001")


async def test_funding_disabled_returns_none_and_touches_nothing(session) -> None:
    sched = await resolve_funding_schedule(
        session, _policy("rdrev_missing", enabled=False), load_rows=_rows
    )
    assert sched is None


async def test_unapproved_revision_fails_closed(session) -> None:
    revision_id = await _seed_funding_revision(session, state=ResearchRevisionState.DRAFT)
    with pytest.raises(FundingSourceInvalid):
        await resolve_funding_schedule(session, _policy(revision_id), load_rows=_rows)


async def test_wrong_usage_scope_fails_closed(session) -> None:
    revision_id = await _seed_funding_revision(session, scope=UsageScope.AGENT_RESEARCH_ONLY)
    with pytest.raises(FundingSourceInvalid):
        await resolve_funding_schedule(session, _policy(revision_id), load_rows=_rows)


async def test_wrong_category_fails_closed(session) -> None:
    revision_id = await _seed_funding_revision(session, category="open_interest")
    with pytest.raises(FundingSourceInvalid):
        await resolve_funding_schedule(session, _policy(revision_id), load_rows=_rows)


async def test_content_hash_mismatch_fails_closed(session) -> None:
    revision_id = await _seed_funding_revision(session, content_hash="different_hash")
    with pytest.raises(FundingSourceInvalid):
        await resolve_funding_schedule(session, _policy(revision_id), load_rows=_rows)


async def test_missing_native_asset_fails_closed(session) -> None:
    revision_id = await _seed_funding_revision(session, with_native=False)
    with pytest.raises(FundingSourceInvalid):
        await resolve_funding_schedule(session, _policy(revision_id), load_rows=_rows)
