"""R9 — deep research validation feeds the lifecycle gate (doc 12 §10), real DB.

A per-row-clean research payload that is empty or majority-duplicated must NOT
auto-verify: it lands in NEEDS_REVIEW with a blocking quality issue. A null-heavy /
type-inconsistent / non-finite / instrument-mapping-incoherent payload records a
WARNING but still VERIFIES (only a blocker forces review, §10.1), and the persisted
issue carries structured evidence + occurrences. Auto-skips without PostgreSQL.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.jobs.research_data import ParsedResearch, run_analysis
from entropia.domain.lifecycle.enums import JobStatus, PrincipalType, ValidationStatus
from entropia.domain.research_data.enums import AvailableTimePolicy, ResearchRevisionState
from entropia.infrastructure.postgres.models import (
    Job,
    Principal,
    ResearchValidationIssue,
    ResearchValidationRun,
)
from entropia.infrastructure.postgres.repositories import research_data as rd_repo
from entropia.shared.ids import new_id

pytestmark = pytest.mark.integration


async def _seed_admin(session: AsyncSession) -> None:
    if await session.get(Principal, "user_admin") is None:
        session.add(Principal(principal_id="user_admin", principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _run(
    session: AsyncSession,
    columns: list[str],
    rows: list[dict[str, Any]],
    *,
    linked_market_dataset_revision_id: str | None = None,
    instrument_mapping_ref: str | None = None,
) -> tuple[Any, Any, dict[str, Any]]:
    """Create an ANALYZING research revision with a valid time policy and run the
    analysis job over injected parsed rows (no MinIO)."""
    root, revision = await rd_repo.create_research_dataset(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        payload={"v": 1},
        linked_market_dataset_revision_id=linked_market_dataset_revision_id,
        revision_state=ResearchRevisionState.ANALYZING,
    )
    revision.available_time_policy = AvailableTimePolicy.SAME_AS_EVENT_TIME
    revision.instrument_mapping_ref = instrument_mapping_ref
    await session.flush()

    job = Job(
        job_id=new_id("job"),
        queue="data",
        status=JobStatus.QUEUED,
        payload={"entity_id": root.entity_id, "revision_id": revision.revision_id},
    )
    session.add(job)
    await session.flush()

    parsed = ParsedResearch(columns=columns, rows=rows)

    async def _load(_s: AsyncSession, _e: str) -> ParsedResearch:
        return parsed

    async def _write(_s: AsyncSession, _e: str, _rid: str, _p: ParsedResearch) -> str:
        return "sha256:deadbeef"

    result = await run_analysis(session, job.job_id, load_and_parse=_load, write_native=_write)
    await session.flush()
    return root, revision, result


async def _issues(session: AsyncSession) -> list[ResearchValidationIssue]:
    rows = await session.execute(select(ResearchValidationIssue))
    return list(rows.scalars().all())


async def _issue_codes(session: AsyncSession) -> set[str]:
    return {issue.check_id for issue in await _issues(session)}


async def test_clean_research_verifies(session: AsyncSession) -> None:
    await _seed_admin(session)
    rows = [{"x": i, "label": f"r{i}"} for i in range(5)]
    _root, revision, result = await _run(session, ["x", "label"], rows)

    assert result["validation_status"] == str(ValidationStatus.PASS)
    assert revision.revision_state == ResearchRevisionState.VERIFIED
    assert await _issue_codes(session) == set()


async def test_empty_payload_blocks_and_needs_review(session: AsyncSession) -> None:
    await _seed_admin(session)
    _root, revision, result = await _run(session, ["x"], [])

    assert result["validation_status"] == str(ValidationStatus.BLOCKING_FAIL)
    assert revision.revision_state == ResearchRevisionState.NEEDS_REVIEW
    assert "COVERAGE_INSUFFICIENT" in await _issue_codes(session)


async def test_duplicate_payload_blocks(session: AsyncSession) -> None:
    await _seed_admin(session)
    rows = [{"x": 1, "y": "a"} for _ in range(4)]  # 3/4 duplicate -> majority
    _root, revision, result = await _run(session, ["x", "y"], rows)

    assert result["validation_status"] == str(ValidationStatus.BLOCKING_FAIL)
    assert revision.revision_state == ResearchRevisionState.NEEDS_REVIEW
    assert "DUPLICATE_EXCESSIVE" in await _issue_codes(session)


async def test_null_heavy_warns_but_verifies_with_evidence(session: AsyncSession) -> None:
    await _seed_admin(session)
    rows = [{"x": 1, "oi": None}, {"x": 2, "oi": None}, {"x": 3, "oi": 9}, {"x": 4, "oi": None}]
    _root, revision, result = await _run(session, ["x", "oi"], rows)

    # A warning is recorded but the revision still auto-verifies (§10.1).
    assert result["validation_status"] == str(ValidationStatus.WARNING)
    assert revision.revision_state == ResearchRevisionState.VERIFIED

    issues = await _issues(session)
    null_issue = next(i for i in issues if i.check_id == "NULL_DENSITY_HIGH")
    assert null_issue.severity == ValidationStatus.WARNING
    assert null_issue.occurrences == 1
    assert null_issue.evidence["columns"][0]["column"] == "oi"


async def test_run_summary_records_severity_breakdown(session: AsyncSession) -> None:
    await _seed_admin(session)
    # Null-heavy `x` -> one warning; the distinct `id` keeps the null rows from
    # also colliding as full-row duplicates.
    rows = [{"x": None, "id": 1}, {"x": None, "id": 2}, {"x": 3, "id": 3}]
    _root, revision, _result = await _run(session, ["x", "id"], rows)

    run = (
        (
            await session.execute(
                select(ResearchValidationRun).where(
                    ResearchValidationRun.revision_id == revision.revision_id
                )
            )
        )
        .scalars()
        .one()
    )
    assert run.summary["issues_by_severity"][ValidationStatus.WARNING.value] == 1
    assert run.summary["issues_by_severity"][ValidationStatus.BLOCKING_FAIL.value] == 0


async def test_instrument_mapping_gap_warns(session: AsyncSession) -> None:
    await _seed_admin(session)
    rows = [{"x": i} for i in range(3)]
    _root, revision, result = await _run(
        session, ["x"], rows, linked_market_dataset_revision_id="mdr_fake"
    )

    assert result["validation_status"] == str(ValidationStatus.WARNING)
    assert revision.revision_state == ResearchRevisionState.VERIFIED
    assert "INSTRUMENT_MAPPING_INVALID" in await _issue_codes(session)
