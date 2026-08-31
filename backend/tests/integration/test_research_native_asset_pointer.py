"""GH #703 — the analysis job pins the revision to the native asset it just wrote.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).

``ResearchDatasetRevision.native_asset_id`` is dereferenced by the funding resolver
(``queries/funding.py`` -> ``get_native_asset``) but was never written by production
code: ``_write_native`` created the asset row and returned only its digest, so the
reverse pointer stayed NULL on every revision the application produced. The defect was
invisible because all three funding tests seed the revision by hand and set the pointer
themselves — the green suite was consistent with the bug.

The rule these cases enforce is therefore about PROVENANCE, not about a value: the
pointer must be written by the pipeline, so no case here assigns ``native_asset_id``.
The revision is created, time-policied, analysed and approved through the real commands
and the real ``run_analysis``; only the S3 half is faked, and the fake writes the asset
ROW for real (that is the seam's stated contract — swap S3/Polars, keep the database).

ADIM 138 left an honest boundary here: this alone did NOT make funding reachable,
because a second gap sat behind the same door -- ``instrument_mapping_ref`` was also
never written by production while ``linked_market_dataset_revision_id`` always was, so
``instrument_mapping_is_valid``'s ``has_link == has_ref`` was False for every
application-created revision and the resolver failed closed on it. That boundary is
GONE: ADIM 149 shipped the mapping writer (GH #703 §Karar 1 = `(b)`, signed
2026-08-31), so BOTH halves of the issue's title claim are now written by production.

The case that used to assert "the mapping gate still stops the run" was rewritten, not
deleted -- inverted onto the same axis, it is now the worker-plane proof that nothing
stops it. And the schedule case no longer hand-sets the mapping ref: assigning it would
overwrite what production wrote and re-hide the very provenance this file exists to
prove, which is the same fixture mistake in a third disguise.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from entropia.application.commands import research_data as rd_cmd
from entropia.application.jobs import research_data as rd_jobs
from entropia.application.jobs.research_data import ParsedResearch
from entropia.application.queries.funding import resolve_funding_schedule
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    EventTimeSemantics,
    ResearchCategory,
    ResearchRevisionState,
    ResearchTimezoneMode,
    UsageScope,
)
from entropia.domain.research_data.value_objects import (
    AvailableTimeSpec,
    CategorySpec,
    ResearchTimezoneSpec,
)
from entropia.domain.strategy.config import FundingPolicy
from entropia.infrastructure.postgres.models import ResearchNativeAsset
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import research_data as rd_repo
from tests.integration.test_research_data_persistence import (
    ADMIN,
    OWNER,
    _approved_market,
    _seed_principals,
)

pytestmark = pytest.mark.integration

_COLUMNS = ["event_time", "funding_rate"]
_ROWS: list[dict[str, Any]] = [
    {"event_time": "2024-01-02T00:00:00Z", "funding_rate": "0.0002"},
    {"event_time": "2024-01-01T00:00:00Z", "funding_rate": "0.0001"},
]
_DIGEST = "sha256:funding-native"


def _rows(_object_key: str) -> list[dict[str, Any]]:
    return list(_ROWS)


async def _analysed_funding_revision(session) -> tuple[str, Any]:
    """Drive the REAL pipeline: create -> time policy -> request analysis -> run_analysis.

    Nothing here touches ``native_asset_id``; that is the claim under test.
    """
    await _seed_principals(session)
    market_id = await _approved_market(session)
    root, _draft = await rd_cmd.create_research_dataset(
        session,
        OWNER,
        market_entity_id=market_id,
        payload={"seed": "funding"},
        category=CategorySpec(category=ResearchCategory.FUNDING_RATE),
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        display_name="funding source",
    )
    await rd_cmd.set_time_policy(
        session,
        OWNER,
        entity_id=root.entity_id,
        event_time_semantics=EventTimeSemantics.PROVIDER_EVENT_TIMESTAMP,
        available_time=AvailableTimeSpec(policy=AvailableTimePolicy.SAME_AS_EVENT_TIME),
        timezone_spec=ResearchTimezoneSpec(mode=ResearchTimezoneMode.UTC),
    )
    await session.flush()
    requested = await rd_cmd.request_research_dataset_analysis(
        session, OWNER, entity_id=root.entity_id
    )

    parsed = ParsedResearch(columns=list(_COLUMNS), rows=list(_ROWS))

    async def _load(_s, _e) -> ParsedResearch:
        return parsed

    async def _write(s, e, rid, p) -> ResearchNativeAsset:
        # Only the S3 write is faked; the asset ROW is written for real, so the pointer
        # under test is written by PRODUCTION rather than by this fake.
        return rd_repo.add_native_asset(
            s,
            entity_id=e,
            object_key=f"s3://processed/{e}.parquet",
            content_digest=_DIGEST,
            size_bytes=128,
            revision_id=rid,
            row_count=len(p.rows),
            schema_descriptor={"columns": p.columns},
        )

    await rd_jobs.run_analysis(
        session, requested["job_id"], load_and_parse=_load, write_native=_write
    )
    await session.flush()
    # Read the pointer back from PostgreSQL, not from the identity map: the integration
    # session is built with ``expire_on_commit=False``, so a stale in-memory attribute
    # would answer the question the assertions are asking. The entity id is captured as a
    # plain string first — expiring detaches every loaded row.
    entity_id = str(root.entity_id)
    session.expire_all()
    revision = await rd_repo.get_revision(session, requested["revision_id"])
    assert revision is not None
    return entity_id, revision


async def _assets(session, entity_id: str) -> list[ResearchNativeAsset]:
    rows = await session.execute(
        select(ResearchNativeAsset).where(ResearchNativeAsset.entity_id == entity_id)
    )
    return list(rows.scalars().all())


async def _approve(session, entity_id: str, revision) -> Any:
    """Approve through the real Admin-only command and re-read from PostgreSQL.

    The id is captured before expiring: ``expire_all`` detaches the loaded row, so
    reading an attribute off it afterwards would be sync IO inside an async test.
    """
    revision_id = str(revision.revision_id)
    await rd_cmd.approve_research_dataset_revision(
        session, ADMIN, entity_id=entity_id, revision_id=revision_id
    )
    await session.flush()
    session.expire_all()
    approved = await rd_repo.get_revision(session, revision_id)
    assert approved is not None
    return approved


@pytest.mark.asyncio
async def test_analysis_pins_the_revision_to_the_native_asset_it_wrote(session) -> None:
    entity_id, revision = await _analysed_funding_revision(session)

    # Vacuity guard: an asset row was actually written, so "the pointer is set" is a
    # statement about a real row rather than about a value nobody can dereference.
    assets = await _assets(session, entity_id)
    assert len(assets) == 1, "the job must write exactly one native asset for one analysis"

    assert revision.native_asset_id is not None, (
        "GH #703: production left the funding resolver's pointer NULL"
    )
    # Identity, not mere presence: the pointer names THE asset this run wrote.
    assert revision.native_asset_id == assets[0].asset_id
    # The digest the manifest hashes still comes from the same row.
    assert assets[0].content_digest == _DIGEST


@pytest.mark.asyncio
async def test_both_of_the_issues_gates_are_passed_by_a_pipeline_built_revision(
    session,
) -> None:
    """GH #703's two written-by-nobody fields, both now written, measured together.

    ADIM 138 could only assert WHICH gate refused, because the mapping half was still
    unwritten and the resolver still failed closed. With the writer shipped there is no
    refusal left to name, so the claim inverts: the resolve completes.

    The two halves are asserted as PROVENANCE, not presence -- nothing in this file
    assigns either one, and the mapping ref is compared to the linked market revision's
    own ``instrument_id`` rather than to a literal.
    """
    entity_id, revision = await _analysed_funding_revision(session)
    revision = await _approve(session, entity_id, revision)
    assert revision.revision_state == ResearchRevisionState.APPROVED

    linked_id = revision.linked_market_dataset_revision_id
    assert linked_id is not None
    linked_market = await md_repo.get_revision(session, linked_id)
    assert linked_market is not None and linked_market.instrument_id
    assert revision.instrument_mapping_ref == linked_market.instrument_id
    assert revision.native_asset_id is not None

    policy = FundingPolicy(
        enabled=True,
        source_root_id=entity_id,
        source_revision_id=revision.revision_id,
        source_content_hash=revision.content_hash,
    )
    # No ``pytest.raises``: the fail-closed resolver has nothing left to refuse.
    schedule = await resolve_funding_schedule(session, policy, load_rows=_rows)
    assert schedule is not None


@pytest.mark.asyncio
async def test_a_pipeline_written_pointer_feeds_a_real_funding_schedule(session) -> None:
    """The end the issue names: a funding schedule built off an app-created revision.

    ADIM 138 had to hand-set ``instrument_mapping_ref`` here to get past rule 2's other
    conjunct. That line is GONE, and its removal is the point: assigning the field would
    overwrite what production now writes, so the schedule below is reached through TWO
    production-written halves instead of one plus a fixture.
    """
    entity_id, revision = await _analysed_funding_revision(session)
    revision = await _approve(session, entity_id, revision)
    pipeline_written_pointer = revision.native_asset_id
    assert pipeline_written_pointer is not None
    assert revision.instrument_mapping_ref is not None, (
        "no longer supplied by this test: production must have written it"
    )

    policy = FundingPolicy(
        enabled=True,
        source_root_id=entity_id,
        source_revision_id=revision.revision_id,
        source_content_hash=revision.content_hash,
    )
    schedule = await resolve_funding_schedule(session, policy, load_rows=_rows)
    assert schedule is not None
    assert schedule.source_revision_id == revision.revision_id
    assert len(schedule.records) == len(_ROWS)
    # The rows were reached THROUGH the pointer production wrote.
    assert revision.native_asset_id == pipeline_written_pointer
