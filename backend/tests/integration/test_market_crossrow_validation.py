"""R3 — cross-row validation feeds the approval gate (doc 11 §7.4), against a real DB.

A per-row-clean but non-monotonic/duplicated OHLCV series must NOT auto-verify: it
lands in NEEDS_REVIEW with a blocking cross-row issue and cannot be APPROVED into the
money-sizing engine (GAP-02). A genuinely clean series verifies, records a coverage
slice (``add_coverage_slice`` — previously never called), and can be approved. A
cadence gap is a WARNING that records split coverage. Auto-skips without PostgreSQL.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import market_data as md_cmd
from entropia.application.jobs.market_data import ParsedDataset, run_analysis
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    JobStatus,
    PrincipalType,
    Role,
    ValidationStatus,
)
from entropia.domain.market_data.enums import (
    MarketDataType,
    MarketRevisionState,
    ResolutionKind,
)
from entropia.domain.market_data.state_machine import IllegalMarketRevisionTransition
from entropia.infrastructure.postgres.models import (
    DatasetCoverageSlice,
    Job,
    MarketValidationIssue,
    Principal,
)
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.shared.ids import new_id

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)


def _ohlcv(ts: str) -> dict[str, Any]:
    return {"timestamp": ts, "open": "1", "high": "2", "low": "1", "close": "2", "volume": "10"}


async def _seed_admin(session: AsyncSession) -> None:
    if await session.get(Principal, "user_admin") is None:
        session.add(Principal(principal_id="user_admin", principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _run(
    session: AsyncSession, rows: list[dict[str, Any]], *, resolution_value: str | None = None
) -> tuple[Any, Any, dict[str, Any]]:
    """Create an ANALYZING OHLCV revision and run the analysis job over injected rows."""
    root, revision = await md_repo.create_market_dataset(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        market_data_type=MarketDataType.OHLCV,
        payload={"v": 1},
        revision_state=MarketRevisionState.ANALYZING,
    )
    if resolution_value is not None:
        revision.resolution_kind = ResolutionKind.BAR
        revision.resolution_value = resolution_value
    await session.flush()

    job = Job(
        job_id=new_id("job"),
        queue="data",
        status=JobStatus.QUEUED,
        payload={"entity_id": root.entity_id, "revision_id": revision.revision_id},
    )
    session.add(job)
    await session.flush()

    parsed = ParsedDataset(
        market_data_type=MarketDataType.OHLCV,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
        rows=rows,
    )

    async def _load(_s: AsyncSession, _e: str, _r: Any) -> ParsedDataset:
        return parsed

    async def _write(_s: AsyncSession, _e: str, _rid: str, _p: ParsedDataset) -> str:
        return "sha256:deadbeef"

    result = await run_analysis(session, job.job_id, load_and_parse=_load, write_processed=_write)
    await session.flush()
    return root, revision, result


async def _issue_codes(session: AsyncSession) -> set[str]:
    rows = (await session.execute(select(MarketValidationIssue))).scalars().all()
    return {issue.rule_code for issue in rows}


async def _coverage(session: AsyncSession, revision_id: str) -> list[DatasetCoverageSlice]:
    result = await session.execute(
        select(DatasetCoverageSlice)
        .where(DatasetCoverageSlice.revision_id == revision_id)
        .order_by(DatasetCoverageSlice.start_at)
    )
    return list(result.scalars().all())


async def test_clean_series_verifies_records_coverage_and_can_be_approved(
    session: AsyncSession,
) -> None:
    await _seed_admin(session)
    rows = [_ohlcv(f"2026-01-01T00:0{i}:00Z") for i in range(3)]  # monotonic, unique, 1m
    root, revision, result = await _run(session, rows, resolution_value="1m")

    assert result["validation_status"] == str(ValidationStatus.PASS)
    assert revision.revision_state == MarketRevisionState.VERIFIED

    slices = await _coverage(session, revision.revision_id)
    assert len(slices) == 1
    assert slices[0].row_count == 3
    assert slices[0].gap_seconds is None

    await md_cmd.approve_market_dataset_revision(
        session, ADMIN, entity_id=root.entity_id, revision_id=revision.revision_id
    )
    await session.flush()
    assert revision.revision_state == MarketRevisionState.APPROVED


async def test_duplicate_series_blocks_and_cannot_be_approved(session: AsyncSession) -> None:
    await _seed_admin(session)
    rows = [
        _ohlcv("2026-01-01T00:00:00Z"),
        _ohlcv("2026-01-01T00:00:00Z"),  # duplicate instrument+timestamp+resolution
        _ohlcv("2026-01-01T00:01:00Z"),
    ]
    root, revision, result = await _run(session, rows, resolution_value="1m")

    assert result["validation_status"] == str(ValidationStatus.BLOCKING_FAIL)
    assert revision.revision_state == MarketRevisionState.NEEDS_REVIEW
    assert "DUPLICATE_TIMESTAMP" in await _issue_codes(session)

    with pytest.raises(IllegalMarketRevisionTransition):
        await md_cmd.approve_market_dataset_revision(
            session, ADMIN, entity_id=root.entity_id, revision_id=revision.revision_id
        )


async def test_non_monotonic_series_blocks(session: AsyncSession) -> None:
    await _seed_admin(session)
    rows = [_ohlcv("2026-01-01T00:05:00Z"), _ohlcv("2026-01-01T00:01:00Z")]  # out of order
    _root, revision, result = await _run(session, rows, resolution_value="1m")

    assert result["validation_status"] == str(ValidationStatus.BLOCKING_FAIL)
    assert revision.revision_state == MarketRevisionState.NEEDS_REVIEW
    assert "TIMESTAMP_NON_MONOTONIC" in await _issue_codes(session)


async def test_cadence_gap_records_split_coverage_and_warns(session: AsyncSession) -> None:
    await _seed_admin(session)
    rows = [
        _ohlcv("2026-01-01T00:00:00Z"),
        _ohlcv("2026-01-01T00:01:00Z"),
        _ohlcv("2026-01-01T00:10:00Z"),  # 9-minute gap at 1m cadence
    ]
    _root, revision, result = await _run(session, rows, resolution_value="1m")

    # a gap is contextual (WARNING), not blocking -> NEEDS_REVIEW, never auto-verified
    assert result["validation_status"] == str(ValidationStatus.WARNING)
    assert revision.revision_state == MarketRevisionState.NEEDS_REVIEW
    assert "CADENCE_GAP" in await _issue_codes(session)

    slices = await _coverage(session, revision.revision_id)
    assert len(slices) == 2
    assert slices[0].gap_seconds is not None
    assert slices[1].gap_seconds is None
