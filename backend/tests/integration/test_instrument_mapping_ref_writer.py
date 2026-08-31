"""GH #703 §Karar 1a = `(b2)`: an instrument-less market cannot be a link source.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).

`(b)` says ``instrument_mapping_ref`` is COPIED from the market revision the research
version links to. That leaves one question the copy cannot answer on its own: the source
column is itself nullable, and an ordinary create request that sends neither
``instrument_id`` nor ``instrument_scope`` produces a market revision naming no
instrument (measured on the shipped API, not assumed). `(b1)` -- let the ref fall
silently to ``None`` there -- was rejected in writing on 2026-08-31, because it moves the
identical incoherence one layer along and keeps #703's claim alive for a subset of rows.
`(b2)` refuses instead, flat, with no grandfathering.

Two things are load-bearing here and neither is visible from the refusal alone:

* The refusal reaches BOTH writing surfaces. A fix applied to ``create_research_dataset``
  only would pass the first case below and fail the third, because ``create_research_
  dataset_revision`` pins a link too.
* The refusal is raised OUTSIDE ``run_idempotent``. Inside, a rejected attempt would
  record its key, and the client whose remediation is "fix the market, then link"
  would be answered with a permanent replay of the error. The second case measures
  the placement directly rather than trusting the reading.

No new taxonomy code: ``DEPENDENCY_BLOCKED`` is the shipped code for "the upstream you
linked is not usable" (O-31 -- the shipped name wins), and the recovery block carries
``field_path=instrument_mapping_ref`` so the envelope names the half that is missing.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import market_data as md_cmd
from entropia.application.commands import research_data as rd_cmd
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.domain.research_data.enums import (
    ResearchCategory,
    ResearchTimezoneMode,
    UsageScope,
)
from entropia.domain.research_data.value_objects import CategorySpec, ResearchTimezoneSpec
from entropia.infrastructure.postgres.models.jobs import IdempotencyKey
from entropia.infrastructure.postgres.models.research_data import ResearchDatasetRevision
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.shared.errors import DependencyBlocked
from tests.integration.test_research_data_persistence import (
    ADMIN,
    OWNER,
    _approved_market,
    _seed_principals,
)

pytestmark = pytest.mark.integration

_UTC = ResearchTimezoneSpec(mode=ResearchTimezoneMode.UTC)


async def _instrumentless_market(session) -> str:
    """An APPROVED market dataset that names no instrument -- the shape `(b2)` refuses.

    Deliberately built through the same command ``_approved_market`` uses, with the one
    argument omitted: the point is that the shipped API accepts this, so the refusal
    below is about a reachable state and not about a hand-forged row.
    """
    root, _ = await md_cmd.create_market_dataset(
        session, ADMIN, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.flush()
    revision = await md_repo.get_revision(session, root.current_revision_id or "")
    assert revision is not None
    assert not revision.instrument_id, (
        "vacuity guard: the shipped create must really leave this empty, else the "
        "refusals below would be about something else"
    )
    revision.revision_state = MarketRevisionState.VERIFIED
    await session.flush()
    await md_cmd.approve_market_dataset_revision(
        session, ADMIN, entity_id=root.entity_id, revision_id=revision.revision_id
    )
    await session.flush()
    return str(root.entity_id)


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _create(session, market_id: str, *, idempotency_key: str | None = None):
    return await rd_cmd.create_research_dataset(
        session,
        OWNER,
        market_entity_id=market_id,
        payload={"seed": "funding"},
        category=CategorySpec(category=ResearchCategory.FUNDING_RATE),
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        display_name="funding source",
        idempotency_key=idempotency_key,
    )


@pytest.mark.asyncio
async def test_creating_against_an_instrumentless_market_is_refused(session) -> None:
    """The refusal, and the envelope that has to make it actionable (O-02)."""
    await _seed_principals(session)
    market_id = await _instrumentless_market(session)

    before = await _count(session, ResearchDatasetRevision)

    with pytest.raises(DependencyBlocked) as excinfo:
        await _create(session, market_id)

    error = excinfo.value
    assert error.code == "DEPENDENCY_BLOCKED"
    assert error.field_path == "instrument_mapping_ref"
    assert error.suggested_action == "link_instrumented_market_revision"
    assert error.scope_type == "market_dataset_revision"
    assert error.remediation, "a blocked dependency must say what to do about it"

    # Counting rows, not merely catching the raise: a guard placed after the insert
    # would raise identically while leaving a half-built dataset behind.
    assert await _count(session, ResearchDatasetRevision) == before


@pytest.mark.asyncio
async def test_the_refusal_burns_no_idempotency_key(session) -> None:
    """The placement, measured: the refusal happens before ``run_idempotent`` is entered.

    The positive control is the discriminating half. Without it, "zero keys" would also
    hold for a build that never records keys on this operation at all, and the case
    would pass while proving nothing about placement.
    """
    await _seed_principals(session)
    market_id = await _instrumentless_market(session)

    with pytest.raises(DependencyBlocked):
        await _create(session, market_id, idempotency_key="idem_rejected_1")

    assert await _count(session, IdempotencyKey) == 0, (
        "a rejected attempt must not record its key: the remediation is 'fix the market, "
        "then link', and a recorded key would replay the error forever"
    )

    # Positive control: the same operation DOES record a key when it is not refused.
    good_market = await _approved_market(session)
    await _create(session, good_market, idempotency_key="idem_accepted_1")
    await session.flush()
    assert await _count(session, IdempotencyKey) == 1


@pytest.mark.asyncio
async def test_revising_onto_an_instrumentless_market_is_refused_the_same_way(
    session,
) -> None:
    """The second writing surface. A create-only fix passes the first case and fails here."""
    await _seed_principals(session)
    good_market = await _approved_market(session)
    root, _draft = await _create(session, good_market)
    await session.flush()
    entity_id = str(root.entity_id)

    bad_market = await _instrumentless_market(session)
    before = await _count(session, ResearchDatasetRevision)

    with pytest.raises(DependencyBlocked) as excinfo:
        await rd_cmd.create_research_dataset_revision(
            session,
            OWNER,
            entity_id=entity_id,
            payload={"seed": "funding-2"},
            category=CategorySpec(category=ResearchCategory.FUNDING_RATE),
            usage_scope=UsageScope.RESEARCH_BACKTEST,
            timezone_spec=_UTC,
            market_entity_id=bad_market,
        )

    assert excinfo.value.field_path == "instrument_mapping_ref"
    assert await _count(session, ResearchDatasetRevision) == before


@pytest.mark.asyncio
async def test_a_revision_pinning_no_market_link_keeps_a_null_mapping(session) -> None:
    """`(b2)` did not widen into "every revision must name an instrument".

    ``instrument_mapping_is_valid`` calls a revision declaring NEITHER half coherent --
    it reaches a run pinned by revision id, not resolved through a mapping table. The
    check is scoped to the branch that actually pins a link, and this case is what keeps
    that scoping honest: a guard hoisted out of the ``if`` would refuse here too.
    """
    await _seed_principals(session)
    market_id = await _approved_market(session)
    root, _draft = await _create(session, market_id)
    await session.flush()

    revised = await rd_cmd.create_research_dataset_revision(
        session,
        OWNER,
        entity_id=str(root.entity_id),
        payload={"seed": "unlinked"},
        category=CategorySpec(category=ResearchCategory.FUNDING_RATE),
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        timezone_spec=_UTC,
    )
    await session.flush()

    row = await session.get(ResearchDatasetRevision, revised["revision_id"])
    assert row is not None
    assert row.linked_market_dataset_revision_id is None
    assert row.instrument_mapping_ref is None
