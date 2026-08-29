"""K-01 — the DECLARED timezone is applied at ingest, against a real DB.

Before K-01 the ingest parse path mapped columns and nothing else: ``TimezoneSpec.zone``
had no caller, and ``parse_timestamp`` read every naive cell as UTC. A dataset declared
``America/New_York`` was therefore stored — and replayed by the engine — at the wrong
instant, silently, while still auto-verifying.

These tests walk the real chain (CSV bytes -> deterministic schema map -> timezone
normalization -> validation -> processed Parquet) and assert the Parquet carries the
CORRECT UTC instant. Only S3 is faked; the Polars parse/write helpers are the real ones.
Auto-skips without PostgreSQL.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.jobs.market_data import (
    ParsedDataset,
    _parse_raw_bytes,
    _to_parquet_bytes,
    run_analysis,
)
from entropia.application.jobs.research_data import ParsedResearch
from entropia.application.jobs.research_data import run_analysis as run_research_analysis
from entropia.application.queries.timezone_audit import (
    market_revisions_at_risk,
    research_revisions_at_risk,
)
from entropia.domain.lifecycle.enums import JobStatus, PrincipalType, ValidationStatus
from entropia.domain.market_data.enums import (
    MarketDataType,
    MarketRevisionState,
    TimezoneMode,
)
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    ResearchRevisionState,
    ResearchTimezoneMode,
)
from entropia.infrastructure.postgres.models import (
    Job,
    MarketValidationIssue,
    Principal,
    ResearchNativeAsset,
    ResearchValidationIssue,
)
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import research_data as rd_repo
from entropia.shared.ids import new_id

pytestmark = pytest.mark.integration

# 09:30 wall clock on a July date. New York is EDT (UTC-4) then, so the true instant
# is 13:30Z — four hours away from the silent-UTC reading the old code produced.
_NAIVE_CSV = (
    "timestamp,open,high,low,close,volume\n"
    "2024-07-15 09:30:00,1,2,1,2,10\n"
    "2024-07-15 09:31:00,1,2,1,2,10\n"
)
_EXPECTED_UTC = ["2024-07-15T13:30:00+00:00", "2024-07-15T13:31:00+00:00"]


async def _seed_principal(session: AsyncSession) -> None:
    if await session.get(Principal, "user_admin") is None:
        session.add(Principal(principal_id="user_admin", principal_type=PrincipalType.HUMAN))
    await session.flush()


def _read_parquet_column(parquet_bytes: bytes, column: str) -> list[Any]:
    import io

    import polars as pl

    return pl.read_parquet(io.BytesIO(parquet_bytes))[column].to_list()


async def _run_market_ingest(
    session: AsyncSession, *, mode: TimezoneMode, iana: str | None
) -> tuple[Any, dict[str, Any], list[Any]]:
    """Run the real parse -> normalize -> validate -> Parquet chain; return the column."""
    await _seed_principal(session)
    root, revision = await md_repo.create_market_dataset(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        market_data_type=MarketDataType.OHLCV,
        payload={"v": 1},
        revision_state=MarketRevisionState.ANALYZING,
    )
    revision.timezone_mode = mode
    revision.timezone_iana = iana
    await session.flush()

    job = Job(
        job_id=new_id("job"),
        queue="data",
        status=JobStatus.QUEUED,
        payload={"entity_id": root.entity_id, "revision_id": revision.revision_id},
    )
    session.add(job)
    await session.flush()

    written: list[Any] = []

    async def _load(_s: AsyncSession, _e: str, r: Any) -> ParsedDataset:
        # The REAL parser: CSV bytes -> deterministic schema map -> normalized rows.
        return _parse_raw_bytes(r.market_data_type, _NAIVE_CSV.encode())

    async def _write(_s: AsyncSession, _e: str, _rid: str, parsed: ParsedDataset) -> str:
        # The REAL Parquet writer; we read the bytes back instead of shipping to S3.
        written.extend(_read_parquet_column(_to_parquet_bytes(parsed), "timestamp"))
        return "sha256:deadbeef"

    result = await run_analysis(session, job.job_id, load_and_parse=_load, write_processed=_write)
    await session.flush()
    return revision, result, written


async def test_custom_iana_lands_the_true_utc_instant_in_processed_parquet(
    session: AsyncSession,
) -> None:
    revision, result, written = await _run_market_ingest(
        session, mode=TimezoneMode.CUSTOM, iana="America/New_York"
    )
    # The whole point of K-01: 09:30 New York is 13:30Z, not 09:30Z.
    assert written == _EXPECTED_UTC
    assert result["validation_status"] == str(ValidationStatus.PASS)
    assert revision.revision_state == MarketRevisionState.VERIFIED
    # And the declared timezone metadata is preserved, not consumed by the conversion.
    assert revision.timezone_iana == "America/New_York"


async def test_utc_mode_leaves_the_wall_clock_untouched(session: AsyncSession) -> None:
    _, _, written = await _run_market_ingest(session, mode=TimezoneMode.UTC, iana=None)
    assert written == ["2024-07-15T09:30:00+00:00", "2024-07-15T09:31:00+00:00"]


async def test_istanbul_lands_the_true_utc_instant(session: AsyncSession) -> None:
    _, _, written = await _run_market_ingest(
        session, mode=TimezoneMode.CUSTOM, iana="Asia/Istanbul"
    )
    # Istanbul is a fixed UTC+3 -> 09:30 local is 06:30 UTC.
    assert written == ["2024-07-15T06:30:00+00:00", "2024-07-15T06:31:00+00:00"]


async def test_naive_source_with_no_resolvable_iana_fails_closed_and_never_verifies(
    session: AsyncSession,
) -> None:
    """Exchange mode carries no IANA identifier — the old code read this as UTC."""
    revision, result, written = await _run_market_ingest(
        session, mode=TimezoneMode.EXCHANGE, iana=None
    )
    # The cells are left VERBATIM — the normalizer never invents an instant.
    assert written == ["2024-07-15 09:30:00", "2024-07-15 09:31:00"]
    assert result["validation_status"] == str(ValidationStatus.BLOCKING_FAIL)
    assert revision.revision_state == MarketRevisionState.NEEDS_REVIEW

    codes = {
        issue.rule_code
        for issue in (await session.execute(select(MarketValidationIssue))).scalars().all()
    }
    assert "MARKET_DATA_TIMEZONE_UNRESOLVED" in codes


# --------------------------------------------------------------------------- #
# Research ingest — doc 12 §8.4 rule 1 (read in the source zone, store UTC,
# keep the source-timezone metadata)
# --------------------------------------------------------------------------- #

_RESEARCH_CSV = "event_time,open_interest\n2024-07-15 09:30:00,100\n2024-07-15 10:30:00,110\n"


async def _run_research_ingest(
    session: AsyncSession, *, mode: ResearchTimezoneMode, iana: str | None
) -> tuple[Any, dict[str, Any], list[Any]]:
    await _seed_principal(session)
    root, revision = await rd_repo.create_research_dataset(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        payload={"v": 1},
        revision_state=ResearchRevisionState.ANALYZING,
    )
    revision.available_time_policy = AvailableTimePolicy.SAME_AS_EVENT_TIME
    revision.source_timezone_mode = mode
    revision.source_timezone_iana = iana
    await session.flush()

    job = Job(
        job_id=new_id("job"),
        queue="data",
        status=JobStatus.QUEUED,
        payload={"entity_id": root.entity_id, "revision_id": revision.revision_id},
    )
    session.add(job)
    await session.flush()

    written: list[Any] = []

    async def _load(_s: AsyncSession, _e: str) -> ParsedResearch:
        from entropia.application.jobs.research_data import _parse_raw_bytes as parse_research

        return parse_research(_RESEARCH_CSV.encode())

    async def _write(
        s: AsyncSession, e: str, rid: str, parsed: ParsedResearch
    ) -> ResearchNativeAsset:
        from entropia.application.jobs.research_data import _to_parquet_bytes as to_parquet

        written.extend(_read_parquet_column(to_parquet(parsed), "event_time"))
        # Only the S3 write is faked; the asset ROW is written for real so the job's own
        # reverse pointer (``native_asset_id``, GH #703) is exercised, not stubbed.
        return rd_repo.add_native_asset(
            s,
            entity_id=e,
            object_key=f"s3://processed/{e}.parquet",
            content_digest="sha256:deadbeef",
            size_bytes=128,
            revision_id=rid,
            row_count=len(parsed.rows),
            schema_descriptor={"columns": parsed.columns},
        )

    result = await run_research_analysis(
        session, job.job_id, load_and_parse=_load, write_native=_write
    )
    await session.flush()
    return revision, result, written


async def test_research_custom_iana_lands_the_true_utc_instant_in_native_parquet(
    session: AsyncSession,
) -> None:
    revision, _result, written = await _run_research_ingest(
        session, mode=ResearchTimezoneMode.CUSTOM, iana="Asia/Istanbul"
    )
    # Istanbul is UTC+3 -> 09:30 / 10:30 local are 06:30 / 07:30 UTC.
    assert written == ["2024-07-15T06:30:00+00:00", "2024-07-15T07:30:00+00:00"]
    # Rule 1: the source-timezone metadata survives the normalization.
    assert revision.source_timezone_iana == "Asia/Istanbul"
    assert revision.revision_state == ResearchRevisionState.VERIFIED


async def test_research_naive_source_with_no_resolvable_iana_fails_closed(
    session: AsyncSession,
) -> None:
    revision, _result, written = await _run_research_ingest(
        session, mode=ResearchTimezoneMode.EXCHANGE, iana=None
    )
    assert written == ["2024-07-15 09:30:00", "2024-07-15 10:30:00"]  # left verbatim
    assert revision.revision_state == ResearchRevisionState.NEEDS_REVIEW
    codes = {
        issue.check_id
        for issue in (await session.execute(select(ResearchValidationIssue))).scalars().all()
    }
    assert "RESEARCH_DATA_TIMEZONE_UNRESOLVED" in codes


# --------------------------------------------------------------------------- #
# K-01 backward-compat audit — the detection query must actually detect
# --------------------------------------------------------------------------- #


async def _market_revision_with_tz(
    session: AsyncSession, *, mode: TimezoneMode, iana: str | None, state: MarketRevisionState
) -> str:
    await _seed_principal(session)
    _root, revision = await md_repo.create_market_dataset(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        market_data_type=MarketDataType.OHLCV,
        payload={"v": 1},
        revision_state=state,
    )
    revision.timezone_mode = mode
    revision.timezone_iana = iana
    await session.flush()
    return str(revision.revision_id)


async def test_audit_flags_custom_non_utc_and_exchange_but_not_utc(session: AsyncSession) -> None:
    """A zero result must mean 'no at-risk data', not 'the query is broken'."""
    new_york = await _market_revision_with_tz(
        session,
        mode=TimezoneMode.CUSTOM,
        iana="America/New_York",
        state=MarketRevisionState.APPROVED,
    )
    exchange = await _market_revision_with_tz(
        session, mode=TimezoneMode.EXCHANGE, iana=None, state=MarketRevisionState.VERIFIED
    )
    utc_declared = await _market_revision_with_tz(
        session, mode=TimezoneMode.UTC, iana=None, state=MarketRevisionState.APPROVED
    )
    # DRAFT is not consumable: nothing downstream reads it, so it is not at risk.
    draft = await _market_revision_with_tz(
        session,
        mode=TimezoneMode.CUSTOM,
        iana="America/New_York",
        state=MarketRevisionState.DRAFT,
    )

    flagged = {r.revision_id for r in await market_revisions_at_risk(session)}
    assert new_york in flagged
    assert exchange in flagged
    assert utc_declared not in flagged
    assert draft not in flagged


async def test_audit_flags_research_revisions_by_declared_source_timezone(
    session: AsyncSession,
) -> None:
    await _seed_principal(session)
    at_risk, _r = await _research_revision_with_tz(
        session, ResearchTimezoneMode.CUSTOM, "Asia/Tokyo"
    )
    safe, _s = await _research_revision_with_tz(session, ResearchTimezoneMode.UTC, None)
    flagged = {r.revision_id for r in await research_revisions_at_risk(session)}
    assert at_risk in flagged
    assert safe not in flagged


async def _research_revision_with_tz(
    session: AsyncSession, mode: ResearchTimezoneMode, iana: str | None
) -> tuple[str, Any]:
    _root, revision = await rd_repo.create_research_dataset(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        payload={"v": 1},
        revision_state=ResearchRevisionState.APPROVED,
    )
    revision.source_timezone_mode = mode
    revision.source_timezone_iana = iana
    await session.flush()
    return str(revision.revision_id), revision
