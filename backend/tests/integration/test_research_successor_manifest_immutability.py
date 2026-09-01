"""RD-11.c3 — a successor Approved revision does not rewrite a finished run's manifest.

doc 12 §14 "Backtest reproducibility": *"Evidence Bundle exact research revision IDs,
feature definitions, time policies and mapping IDs pinler. New Approved revision
running/finished run manifestini değiştirmez."*

The bundle half of that row is covered (RD-11.c1/c2). The MANIFEST half never was:
nothing in the suite approved a successor revision and then re-read a run's manifest.
That is the gap this module closes, and the reason it needs a genuinely completed run
rather than a compiled bundle — the artefact under test is
``backtest_run_manifest`` / ``result_manifest_snapshot``, which only a run produces.

This module is also RD-09.c4's citation ("an existing run or result stays bound to
v1.0 after v1.1 is approved" — batch 05 cited these nodes rather than writing new
ones). i703 §Karar 3 (signed 2026-08-31) allows that closure only on a ref PRODUCTION
produced: until ADIM 152 the harness below hand-set ``instrument_mapping_ref``, and
once ADIM 149's writer landed that hand-set silently OVERWROTE what the shipped
command copies from the linked market revision. The harness now asserts the copy
instead of writing one, so the run under test pins a production-written ref.

Why the assertions are shaped the way they are: the manifest is persisted at admission
and the snapshot is copied at result time, so "the stored row did not change" is nearly
tautological on its own. The defect this criterion actually guards against is a READ
surface that re-resolves the pin live — a manifest that stored a root id and
dereferenced "latest approved" on the way out. So every stored assertion is paired with
a read-path assertion through the shipped query, and the successor is proven to have
really landed (approved, and the root's head) before anything is concluded from the
absence of change.
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.application.commands import research_data as rd_cmd
from entropia.application.queries import backtest_run as backtest_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    EventTimeSemantics,
    ResearchCategory,
    ResearchRevisionState,
    ResearchTimezoneMode,
    UsageScope,
)
from entropia.domain.research_data.value_objects import CategorySpec, ResearchTimezoneSpec
from entropia.infrastructure.postgres.models import (
    Principal,
    ResearchNativeAsset,
)
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import research_data as rd_repo
from tests.integration.test_backtest_persistence import (
    USER1,
    _e2e_bars,
    _ready_composition,
    _seed_principals,
)

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)

# The funding rows the engine replays. Injected, so the run needs no object store.
_FUNDING_ROWS: list[dict[str, Any]] = [
    {"event_time": "2024-02-01T00:00:00Z", "funding_rate": "0.0001"},
    {"event_time": "2024-02-15T00:00:00Z", "funding_rate": "0.0002"},
]


def _funding_rows(_object_key: str) -> list[dict[str, Any]]:
    return list(_FUNDING_ROWS)


async def _approved_funding_revision(
    session, market_entity_id: str, market_revision_id: str
) -> dict[str, Any]:
    """A research revision the Ready Check and the worker will BOTH accept as a funding source.

    Every field here is load-bearing, and each is demanded by a different gate — leaving
    any one out makes the composition unadmissible rather than making the test weaker:
      * ``category_key = funding_rate`` and a native asset — ``queries/funding.py``;
      * ``usage_scope = research_backtest`` + APPROVED — both that gate and readiness;
      * ``available_time_policy = fixed_delay`` with a POSITIVE delay — readiness'
        ``_available_time_is_undefined``;
      * ``linked_market_dataset_revision_id`` equal to the strategy's market pin —
        readiness' ``_research_market_compatibility_issues``. Pinned by the shipped
        command from ``market_entity_id``, not written here;
      * ``instrument_mapping_ref`` non-empty — ``instrument_mapping_is_valid`` requires
        the link and the mapping ref to be present together or absent together. Since
        ADIM 149 the shipped command writes it itself (GH #703 §Karar 1 = ``(b)``: a
        COPY of the linked market revision's own ``instrument_id``), so it is ASSERTED
        below, never written here — writing it would overwrite production's value and
        re-open the world i703 §Karar 3 refused to close RD-09.c4 in.
    """
    root, _revision = await rd_cmd.create_research_dataset(
        session,
        ADMIN,
        market_entity_id=market_entity_id,
        payload={"funding": 1},
        category=CategorySpec(category=ResearchCategory.FUNDING_RATE),
        usage_scope=UsageScope.RESEARCH_BACKTEST,
    )
    await session.flush()
    revision = await _head(session, root.entity_id)
    # The shipped command pins the link itself (DR3), so the compatibility gate is
    # satisfied by construction rather than by a hand-written column — and asserting it
    # here keeps the harness honest if that pinning ever changes.
    assert revision.linked_market_dataset_revision_id == market_revision_id
    # The same command copies the mapping ref from that market revision (GH #703
    # §Karar 1 = `(b)`). Two axes, two asserts: PRESENCE (production wrote one at all)
    # and IDENTITY (it wrote the market revision's own instrument_id, not a constant).
    assert revision.instrument_mapping_ref, "production wrote no instrument_mapping_ref"
    market_revision = await md_repo.get_revision(session, market_revision_id)
    assert market_revision is not None
    assert revision.instrument_mapping_ref == market_revision.instrument_id

    session.add(
        ResearchNativeAsset(
            asset_id="rnat_rd11_c3",
            entity_id=root.entity_id,
            object_key="s3://processed/funding-rd11.parquet",
            content_digest="dig_rd11",
            size_bytes=128,
            row_count=len(_FUNDING_ROWS),
            schema_descriptor={"columns": ["event_time", "funding_rate"]},
        )
    )
    revision.native_asset_id = "rnat_rd11_c3"
    revision.event_time_semantics = EventTimeSemantics.PROVIDER_EVENT_TIMESTAMP
    revision.available_time_policy = AvailableTimePolicy.FIXED_DELAY
    revision.available_delay_seconds = 120
    revision.source_timezone_mode = ResearchTimezoneMode.UTC
    revision.revision_state = ResearchRevisionState.VERIFIED
    await session.flush()
    await rd_cmd.approve_research_dataset_revision(
        session, ADMIN, entity_id=root.entity_id, revision_id=revision.revision_id
    )
    await session.flush()

    return {
        "enabled": True,
        "source_root_id": root.entity_id,
        "source_revision_id": revision.revision_id,
        "source_content_hash": revision.content_hash,
    }


async def _head(session, entity_id: str):
    root = await rd_repo.get_dataset_root(session, entity_id)
    assert root is not None
    revision = await rd_repo.get_revision(session, root.current_revision_id or "")
    assert revision is not None
    return revision


def _research_feed(manifest: dict[str, Any]) -> dict[str, Any]:
    """The one research feed the V1 engine consumes, out of the manifest's data/time group."""
    feeds = [
        feed
        for entry in manifest["data_time_context"]
        for feed in entry.get("research_datasets", [])
    ]
    assert len(feeds) == 1, f"expected exactly one pinned research feed, got {len(feeds)}"
    return feeds[0]


async def _completed_funded_run(session, composition_id: str) -> dict[str, Any]:
    """``_completed_run``'s funding-aware twin.

    The shared helper injects bars only; a composition with funding ON additionally
    needs the funding rows, or ``resolve_funding_schedule`` reaches for an object store
    that is not there. Injected the same way bars are (``queries/funding.FundingRowLoader``),
    so this stays an S3-free run of the REAL worker rather than a stubbed one.
    """
    from entropia.application.commands import backtest_run as backtest_cmd
    from entropia.application.jobs.backtest_engine import run_backtest

    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    out = await run_backtest(
        session, admit["job_id"], stream_bars=_e2e_bars, load_funding_rows=_funding_rows
    )
    await session.commit()
    assert out["state"] == "succeeded", out
    return {"run_id": admit["run_id"], **out}


async def _approve_successor(session, entity_id: str, market_entity_id: str) -> str:
    """Create and APPROVE a second revision under the same root; return its id.

    This is the event the criterion names. It goes through the shipped commands, so a
    successor that could not legally be approved would fail here rather than silently
    leaving the test asserting nothing.
    """
    await rd_cmd.create_research_dataset_revision(
        session,
        ADMIN,
        entity_id=entity_id,
        payload={"funding": 2},
        category=CategorySpec(category=ResearchCategory.FUNDING_RATE),
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        timezone_spec=ResearchTimezoneSpec(mode=ResearchTimezoneMode.UTC),
        # DR3 again: approval re-checks the link, so the successor must carry its own.
        market_entity_id=market_entity_id,
    )
    await session.flush()
    successor = await _head(session, entity_id)
    successor.event_time_semantics = EventTimeSemantics.PROVIDER_EVENT_TIMESTAMP
    successor.available_time_policy = AvailableTimePolicy.FIXED_DELAY
    successor.available_delay_seconds = 900
    successor.revision_state = ResearchRevisionState.VERIFIED
    await session.flush()
    await rd_cmd.approve_research_dataset_revision(
        session, ADMIN, entity_id=entity_id, revision_id=successor.revision_id
    )
    await session.commit()
    return successor.revision_id


async def test_a_successor_approval_leaves_a_finished_runs_manifest_unchanged(session) -> None:
    """RD-11.c3, doc 12 §14: a new Approved revision does not rewrite a finished run."""
    await _seed_principals(session)
    if await session.get(Principal, ADMIN.principal_id) is None:
        session.add(Principal(principal_id=ADMIN.principal_id, principal_type=PrincipalType.HUMAN))
        await session.flush()

    pinned: dict[str, Any] = {}

    async def _funding_for(market_entity_id: str, market_revision_id: str) -> dict[str, Any]:
        block = await _approved_funding_revision(session, market_entity_id, market_revision_id)
        pinned.update(block)
        pinned["market_entity_id"] = market_entity_id
        return block

    composition_id, _root, _rev = await _ready_composition(
        session,
        USER1,
        funding_for=_funding_for,
        # GH #703 §Karar 1a = `(b2)`: the funding revision copies its mapping ref
        # from this market revision, which therefore has to name an instrument.
        market_instrument_id="BTCUSDT",
    )
    run = await _completed_funded_run(session, composition_id)

    manifest_row = await bt_repo.get_manifest_by_run(session, run["run_id"])
    assert manifest_row is not None
    hash_before = manifest_row.manifest_hash
    feed_before = _research_feed(manifest_row.manifest)
    snapshot_before = await bt_repo.get_manifest_snapshot(session, run["result_id"])
    assert snapshot_before is not None
    snapshot_feed_before = _research_feed(snapshot_before.manifest)

    # The run really pinned the revision under test — otherwise everything below would
    # be asserting that an absent pin stayed absent.
    assert feed_before["revision_id"] == pinned["source_revision_id"]
    assert feed_before["revision"]["available_delay_seconds"] == 120
    # RD-09.c4's closure condition (i703 §Karar 3): the manifest pins the ref
    # PRODUCTION wrote — the market revision's own instrument_id, named once at the
    # `_ready_composition` call above — not a harness constant.
    assert feed_before["revision"]["instrument_mapping_ref"] == "BTCUSDT"

    # --- the event the criterion names -------------------------------------------- #
    successor_id = await _approve_successor(
        session, pinned["source_root_id"], pinned["market_entity_id"]
    )

    # NEGATIVE CONTROL: the successor must really be a new, Approved head. Without this
    # the test would also pass if `create_research_dataset_revision` had quietly failed.
    assert successor_id != pinned["source_revision_id"]
    successor = await rd_repo.get_revision(session, successor_id)
    assert successor is not None
    assert str(successor.revision_state) == "approved"
    root_now = await rd_repo.get_dataset_root(session, pinned["source_root_id"])
    assert root_now is not None and root_now.current_revision_id == successor_id

    # --- 1. the stored manifest did not move -------------------------------------- #
    session.expire_all()  # re-READ from the database, not from the identity map
    manifest_after = await bt_repo.get_manifest_by_run(session, run["run_id"])
    assert manifest_after is not None
    assert manifest_after.manifest_hash == hash_before
    assert _research_feed(manifest_after.manifest) == feed_before

    # --- 2. the RESULT's own snapshot did not move -------------------------------- #
    snapshot_after = await bt_repo.get_manifest_snapshot(session, run["result_id"])
    assert snapshot_after is not None
    assert _research_feed(snapshot_after.manifest) == snapshot_feed_before

    # --- 3. the READ SURFACE still reports the ORIGINAL revision ------------------- #
    # This is the assertion with teeth, and it reads the surface a HUMAN reads:
    # ``manifest_excerpt.research_data_revision_refs`` is the Results-History provenance
    # reader (doc 16 §8.2). A manifest that stored a root id and resolved "latest
    # approved" on the way out would satisfy 1 and 2 and still hand the reader the
    # successor here.
    detail = await backtest_query.get_backtest_result(session, USER1, result_id=run["result_id"])
    refs = detail["manifest_excerpt"]["research_data_revision_refs"]
    assert [ref["revision_id"] for ref in refs] == [pinned["source_revision_id"]]
    assert successor_id not in [ref["revision_id"] for ref in refs]
    assert detail["manifest_hash"] == hash_before


async def test_a_successor_approval_leaves_a_RUNNING_runs_manifest_unchanged(session) -> None:
    """The other half of RD-11.c3's own words: "running OR finished".

    The finished case above also exercises the ``backtest_run_manifest`` row, which is
    the same artefact a running run holds — but it holds it while the run is still
    QUEUED, before any Result or snapshot exists. That window is where a "re-resolve the
    latest approved pin before the worker starts" defect would live, so it is asserted
    on its own rather than inferred from the finished case.
    """
    from entropia.application.commands import backtest_run as backtest_cmd

    await _seed_principals(session)
    if await session.get(Principal, ADMIN.principal_id) is None:
        session.add(Principal(principal_id=ADMIN.principal_id, principal_type=PrincipalType.HUMAN))
        await session.flush()

    pinned: dict[str, Any] = {}

    async def _funding_for(market_entity_id: str, market_revision_id: str) -> dict[str, Any]:
        block = await _approved_funding_revision(session, market_entity_id, market_revision_id)
        pinned.update(block)
        pinned["market_entity_id"] = market_entity_id
        return block

    composition_id, _root, _rev = await _ready_composition(
        session,
        USER1,
        funding_for=_funding_for,
        # GH #703 §Karar 1a = `(b2)`: the funding revision copies its mapping ref
        # from this market revision, which therefore has to name an instrument.
        market_instrument_id="BTCUSDT",
    )
    admit = await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()
    assert admit["state"] == "queued"

    before = await bt_repo.get_manifest_by_run(session, admit["run_id"])
    assert before is not None
    hash_before = before.manifest_hash
    feed_before = _research_feed(before.manifest)
    assert feed_before["revision_id"] == pinned["source_revision_id"]
    # Same production-ref condition as the finished case: the QUEUED manifest's pinned
    # block carries the ref the shipped command copied, not a harness constant.
    assert feed_before["revision"]["instrument_mapping_ref"] == "BTCUSDT"

    successor_id = await _approve_successor(
        session, pinned["source_root_id"], pinned["market_entity_id"]
    )
    assert successor_id != pinned["source_revision_id"]

    session.expire_all()
    after = await bt_repo.get_manifest_by_run(session, admit["run_id"])
    assert after is not None
    assert after.manifest_hash == hash_before
    assert _research_feed(after.manifest) == feed_before
    # The QUEUED run still points at the revision it was admitted with, not the newest.
    assert _research_feed(after.manifest)["revision_id"] != successor_id
