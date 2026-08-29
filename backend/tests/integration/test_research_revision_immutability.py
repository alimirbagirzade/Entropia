"""An approved Research Data revision is immutable, and finished evidence keeps
pointing at what it pinned (doc 12 §5.2, §11, §14).

Auto-skips without PostgreSQL (see tests/integration/conftest.py).

Batch 03 of the class-B acceptance ledger (ADIM 54). Every row here shares one
claim: *approving a revision freezes it*, and the recovery for a changed rule is a
NEW revision rather than a mutation of the old one. Before this module nothing
asserted that claim from the revision's own columns.

Acceptance (doc 12 §14) by test:

- ``RD-04.c3`` retiming an APPROVED revision is refused; the replacement revision is
  born DRAFT and cannot reach APPROVED without going through analysis again
- ``RD-06.c2`` a non-OHLCV category (Order Book) keeps its native columns — the
  backend never reshapes them into OHLCV columns
- ``RD-09.c3`` v1.0's own content is byte-unchanged after v1.1 is written

Helpers are reused from ``test_research_data_persistence`` (``_approved_market``,
``_seed_principals``) and ``test_backtest_persistence`` (``_ready_composition``,
``_e2e_bars``) rather than re-seeded here.

NOT covered here, deliberately — three doc 12 clauses name behaviour that does not
ship, so no test can close them (see the ledger notes):

* ``RD-01.c4`` wants the ANALYSIS command to raise DEPENDENCY_BLOCKED.
  ``request_research_dataset_analysis`` has no such gate, and it needs none:
  ``market_entity_id`` is REQUIRED at create, so a dataset without an approved
  market link cannot exist in the first place.
* ``RD-05.c5`` wants an Agent to drive its own draft/analysis commands.
  ``domain/agent_lab/tool_gateway.py::ToolName`` exposes no research draft or
  analysis tool at all.
* ``RD-11.c2`` wants the evidence bundle to pin feature definitions, time policies
  and mapping ids. ``jobs/research_data.py::_seal_bundle`` members carry five
  fields, and none of those three is among them.

``RD-09.c4`` ("an existing run stays bound to v1.0") is NOT closed here either, for a
different reason: it is closable, but only through a funding-enabled run, and a
funding run needs a readable native asset whose rows the worker can resolve. Wiring
that end to end outgrew this batch, so RD-09 stays `partial` rather than being
marked on a half proof. It is the natural first item of the next batch — the
readiness cross-check (funding revision must be linked to the strategy's OWN market
revision) and ``run_backtest(load_funding_rows=...)`` are the two anchors.
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.application.commands import research_data as rd_cmd
from entropia.application.jobs import research_data as rd_jobs
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    EventTimeSemantics,
    ResearchCategory,
    ResearchRevisionState,
    ResearchTimezoneMode,
    UsageScope,
)
from entropia.domain.research_data.state_machine import (
    IllegalResearchRevisionTransition,
    next_research_revision_state,
)
from entropia.domain.research_data.value_objects import (
    AvailableTimeSpec,
    CategorySpec,
    ResearchTimezoneSpec,
)
from entropia.infrastructure.postgres.repositories import research_data as rd_repo
from entropia.shared.errors import LifecycleBlocked
from tests.integration.test_research_data_persistence import (
    ADMIN,
    OWNER,
    _approved_market,
    _seed_principals,
)

pytestmark = pytest.mark.integration

_OPEN_INTEREST = CategorySpec(category=ResearchCategory.OPEN_INTEREST)
_ORDER_BOOK = CategorySpec(category=ResearchCategory.ORDER_BOOK)
_UTC = ResearchTimezoneSpec(mode=ResearchTimezoneMode.UTC)


async def _dataset(session, *, category: CategorySpec = _OPEN_INTEREST) -> tuple[Any, str]:
    """Returns ``(root, market_entity_id)`` — the market id is needed again for every
    later revision, because approval re-resolves the link fail-closed."""
    market_id = await _approved_market(session)
    root, _revision = await rd_cmd.create_research_dataset(
        session,
        OWNER,
        market_entity_id=market_id,
        payload={"seed": 1},
        category=category,
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        display_name="research seed",
    )
    await session.commit()
    return root, market_id


async def _head(session, entity_id: str):
    root = await rd_repo.get_dataset_root(session, entity_id)
    assert root is not None
    revision = await rd_repo.get_revision(session, root.current_revision_id or "")
    assert revision is not None
    return revision


async def _drive_to_approved(session, entity_id: str) -> Any:
    """Walk the head revision DRAFT -> ANALYZING -> VERIFIED -> APPROVED.

    The states are set through the SAME state machine the commands use, so an
    illegal shortcut would raise here rather than silently seeding an impossible
    row (which is what makes the refusal assertions below meaningful).
    """
    # The time policy must be set through its own command while the revision is
    # still mutable — approval refuses a revision whose policy row is missing.
    await rd_cmd.set_time_policy(
        session,
        OWNER,
        entity_id=entity_id,
        event_time_semantics=EventTimeSemantics.PROVIDER_EVENT_TIMESTAMP,
        available_time=AvailableTimeSpec(policy=AvailableTimePolicy.FIXED_DELAY, delay_seconds=120),
        timezone_spec=_UTC,
    )
    await session.flush()
    revision = await _head(session, entity_id)
    for target in (
        ResearchRevisionState.ANALYZING,
        ResearchRevisionState.VERIFIED,
    ):
        revision.revision_state = next_research_revision_state(revision.revision_state, target)
    await session.flush()
    # Approval is Admin-only (doc 12 §2); using OWNER here would make the refusal
    # assertions below fire on the ROLE gate instead of the state machine.
    await rd_cmd.approve_research_dataset_revision(
        session, ADMIN, entity_id=entity_id, revision_id=revision.revision_id
    )
    await session.commit()
    revision = await _head(session, entity_id)
    assert revision.revision_state == ResearchRevisionState.APPROVED
    return revision


# --------------------------------------------------------------------------- #
# RD-04.c3 — a rule change on an approved revision is a NEW revision, re-analysed
# --------------------------------------------------------------------------- #


async def test_retiming_an_approved_revision_is_refused_and_the_replacement_is_re_analysed(
    session,
) -> None:
    """RD-04.c3: the prior analysis cannot be silently re-used under a new rule.

    The row is worded "the prior analysis is marked stale and re-analysis is
    required". What ships is stronger and structural: an APPROVED revision cannot be
    retimed at all (``ensure_time_policy_mutable``), and the replacement revision is
    born DRAFT — and DRAFT -> APPROVED is not a legal transition, so it cannot reach
    Approved without going through analysis. Both halves are asserted here; neither
    was asserted anywhere before.
    """
    await _seed_principals(session)
    root, market_id = await _dataset(session)
    entity_id = str(root.entity_id)
    approved = await _drive_to_approved(session, entity_id)
    # Read as plain values NOW: a later rollback expires the ORM object, and touching
    # it afterwards would attempt lazy IO outside the async context.
    approved_revision_id = str(approved.revision_id)
    delay_before = approved.available_delay_seconds

    # 1. In-place retime of the APPROVED head is refused.
    with pytest.raises(LifecycleBlocked):
        await rd_cmd.set_time_policy(
            session,
            OWNER,
            entity_id=entity_id,
            event_time_semantics=EventTimeSemantics.PROVIDER_EVENT_TIMESTAMP,
            available_time=AvailableTimeSpec(
                policy=AvailableTimePolicy.FIXED_DELAY, delay_seconds=900
            ),
            timezone_spec=_UTC,
        )
    await session.rollback()

    # The approved rule is untouched by the refusal.
    head = await _head(session, entity_id)
    assert head.revision_state == ResearchRevisionState.APPROVED
    assert head.available_delay_seconds == delay_before

    # 2. The recovery is a NEW revision — and it is born DRAFT.
    revised = await rd_cmd.create_research_dataset_revision(
        session,
        OWNER,
        entity_id=entity_id,
        payload={"seed": 2},
        category=_OPEN_INTEREST,
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        timezone_spec=_UTC,
        market_entity_id=market_id,
        display_name="research seed v2",
    )
    await session.commit()
    new_head = await _head(session, entity_id)
    assert new_head.revision_id == revised["revision_id"] != approved_revision_id
    assert new_head.revision_state == ResearchRevisionState.DRAFT

    # 3. Re-analysis is MANDATORY. The replacement's time policy is declared FIRST so
    #    the refusal below can only be the DRAFT -> APPROVED transition: without this
    #    the approve call fails earlier, on the missing-policy gate, and the test
    #    would be proving the wrong refusal.
    await rd_cmd.set_time_policy(
        session,
        OWNER,
        entity_id=entity_id,
        event_time_semantics=EventTimeSemantics.PROVIDER_EVENT_TIMESTAMP,
        available_time=AvailableTimeSpec(policy=AvailableTimePolicy.FIXED_DELAY, delay_seconds=900),
        timezone_spec=_UTC,
    )
    await session.commit()

    with pytest.raises(IllegalResearchRevisionTransition):
        await rd_cmd.approve_research_dataset_revision(
            session,
            ADMIN,  # Admin, so the refusal can only be the DRAFT -> APPROVED transition
            entity_id=entity_id,
            revision_id=new_head.revision_id,
        )
    await session.rollback()
    assert (await _head(session, entity_id)).revision_state == ResearchRevisionState.DRAFT


# --------------------------------------------------------------------------- #
# RD-06.c2 — a non-OHLCV category keeps its native columns                     #
# --------------------------------------------------------------------------- #


async def test_order_book_dataset_keeps_its_native_columns(session) -> None:
    """RD-06.c2: the backend never reshapes a non-OHLCV category into OHLCV columns.

    No fixture in the suite exercised a non-OHLCV research category at all — grepping
    for ORDER_BOOK / MACRO_CALENDAR across backend/tests found nothing — so "native
    fields survive" was an argument about ``_advance_revision`` rather than an
    assertion. The parse step is injected so this stays object-storage-free; what is
    asserted is what the REVISION ends up carrying.
    """
    await _seed_principals(session)
    root, _market_id = await _dataset(session, category=_ORDER_BOOK)
    revision = await _head(session, root.entity_id)
    revision.revision_state = next_research_revision_state(
        revision.revision_state, ResearchRevisionState.ANALYZING
    )
    revision.event_time_semantics = EventTimeSemantics.PROVIDER_EVENT_TIMESTAMP
    revision.available_time_policy = AvailableTimePolicy.SAME_AS_EVENT_TIME
    revision.available_delay_seconds = None
    await session.flush()

    native_columns = ["event_time", "bid_price", "bid_size", "ask_price", "ask_size"]
    parsed = rd_jobs.ParsedResearch(
        columns=list(native_columns),
        rows=[
            {
                "event_time": "2024-01-01T00:00:00Z",
                "bid_price": "42000",
                "bid_size": "1.5",
                "ask_price": "42010",
                "ask_size": "2.0",
            }
        ],
    )

    async def _fake_load(_session, _entity_id):
        return parsed

    async def _fake_write(session_, entity_id_, revision_id_, parsed_):
        # Only the S3 write is faked; the asset ROW is written for real so the job's own
        # reverse pointer (``native_asset_id``, GH #703) is exercised, not stubbed.
        return rd_repo.add_native_asset(
            session_,
            entity_id=entity_id_,
            object_key=f"s3://processed/{entity_id_}.parquet",
            content_digest="digest-order-book",
            size_bytes=128,
            revision_id=revision_id_,
            row_count=len(parsed_.rows),
            schema_descriptor={"columns": parsed_.columns},
        )

    requested = await rd_cmd.request_research_dataset_analysis(
        session, OWNER, entity_id=root.entity_id
    )
    await session.commit()
    await rd_jobs.run_analysis(
        session, requested["job_id"], load_and_parse=_fake_load, write_native=_fake_write
    )
    await session.commit()

    stored = await _head(session, root.entity_id)
    assert stored.category_key == ResearchCategory.ORDER_BOOK.value
    assert stored.native_schema_descriptor is not None
    assert stored.native_schema_descriptor["columns"] == native_columns
    # The discriminating half: no OHLCV column was invented on the way through.
    for ohlcv in ("open", "high", "low", "close", "volume"):
        assert ohlcv not in stored.native_schema_descriptor["columns"]


# --------------------------------------------------------------------------- #
# RD-09 — v1.0 is frozen, and what pinned it keeps resolving it                #
# --------------------------------------------------------------------------- #


async def test_approved_revision_content_survives_the_next_revision(session) -> None:
    """RD-09.c3: writing v1.1 leaves v1.0's own columns byte-unchanged.

    The append path was already exercised, but nothing read v1.0's fields before and
    after — which is the actual claim of the row. The three the criterion names by
    word are checked by name (available time, linked market, content hash) rather
    than by comparing an opaque blob.
    """
    await _seed_principals(session)
    root, market_id = await _dataset(session)
    entity_id = str(root.entity_id)
    v1 = await _drive_to_approved(session, entity_id)

    v1_id = str(v1.revision_id)
    before = {
        "content_hash": v1.content_hash,
        "available_time_policy": v1.available_time_policy,
        "available_delay_seconds": v1.available_delay_seconds,
        "event_time_semantics": v1.event_time_semantics,
        "linked_market": v1.linked_market_dataset_revision_id,
        "payload": dict(v1.payload or {}),
        "revision_state": v1.revision_state,
    }
    assert before["content_hash"] and before["linked_market"]

    revised = await rd_cmd.create_research_dataset_revision(
        session,
        OWNER,
        entity_id=entity_id,
        payload={"seed": 2, "changed": True},
        category=_OPEN_INTEREST,
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        timezone_spec=_UTC,
        market_entity_id=market_id,
        display_name="research seed v1.1",
    )
    await session.commit()
    assert revised["revision_id"] != v1_id

    # Re-READ v1.0 from the database; the identity map must not answer for it.
    session.expire_all()
    after = await rd_repo.get_revision(session, v1_id)
    assert after is not None
    assert after.content_hash == before["content_hash"]
    assert after.available_time_policy == before["available_time_policy"]
    assert after.available_delay_seconds == before["available_delay_seconds"]
    assert after.event_time_semantics == before["event_time_semantics"]
    assert after.linked_market_dataset_revision_id == before["linked_market"]
    assert dict(after.payload or {}) == before["payload"]
    # v1.0 also keeps its own lifecycle: appending v1.1 does not demote it.
    assert after.revision_state == before["revision_state"] == ResearchRevisionState.APPROVED
    # …and the two revisions are genuinely different content, so the equality above
    # is not the trivial case of an unchanged payload.
    new_head = await _head(session, entity_id)
    assert new_head.content_hash != before["content_hash"]
