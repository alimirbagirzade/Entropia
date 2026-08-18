"""P4 — batching RUN admission's tick-pin leg changes NOTHING a caller can observe.

``commands/backtest_run.py::_resolve_tick_pins`` used to issue two reads per
tick-demanding Strategy item: the doc 02 §7.1 mirror deref and the per-instrument
approved-tick probe. Both are now batched. This file is the parity half of that
change — the budget row (``docs/performance/query_budgets.json`` ->
``backtest_run.admission_tick_pins``) proves the cost moved, and these tests prove
the ANSWER did not.

Two properties carry real weight here, and neither is about speed:

* the leg is **fail-closed**. An unpinnable requirement is a 422
  ``TICK_DATA_UNAVAILABLE`` admission reject, never a silently tickless run, and the
  envelope promotes the leading blocker's ``field_path``/``scope_id``
  (``_readiness_blocked``). So the tests assert the typed code AND those two promoted
  fields AND — with a composition whose SECOND item is the unpinnable one — that the
  item named is still the first failing item in MANIFEST order. Collecting the
  demands before deciding them must not reorder that.
* **which revision is pinned is an input, not a detail.** The id goes into the
  immutable manifest, so two runs sharing an ``execution_key`` must never replay
  different tick paths (doc 15 §15, INF-04/INF-05). The per-instrument reader orders
  by ``created_at DESC, revision_id DESC`` — a TOTAL order — and the batch resolves
  the same row with ``DISTINCT ON``. An equal-``created_at`` fixture is the only way
  to test that claim rather than restate it: with distinct timestamps the tie-break
  never runs and any implementation passes.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from entropia.application.commands.backtest_run import _resolve_tick_pins
from entropia.domain.lifecycle.enums import PrincipalType
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.domain.readiness.enums import ReadinessIssueCode
from entropia.domain.strategy.enums import ValidationStatusEnum
from entropia.infrastructure.postgres.models import (
    EntityRegistry,
    MarketDatasetRevision,
    Principal,
)
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import market_data as market_repo
from entropia.infrastructure.postgres.repositories import strategy as strat_repo
from entropia.shared.errors import ReadinessBlockedError
from tests.integration.test_readiness_query_count import _config

pytestmark = pytest.mark.integration

#: A fixed instant every revision in a tie shares. The point of the tie is that
#: ``created_at`` cannot break it, so ``revision_id DESC`` must.
_TIE = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)


async def _principal(session) -> None:
    if await session.get(Principal, "user_1") is None:
        session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
        await session.flush()


def _tick_config(instrument_id: str, *, require: bool = True) -> dict[str, Any]:
    payload = _config(
        indicator_rev="pkg_x",
        condition_rev="pkg_y",
        reference_rev="pkg_z",
        leg_revs=[],
        market_rev="md_rev_parity",
    ).model_dump(mode="json")
    payload["data"]["intrabar_policy"]["tick_policy"] = "require" if require else "inherit"
    payload["data"]["instrument_id"] = instrument_id
    return payload


async def _tick_revision(
    session,
    *,
    revision_id: str,
    instrument_id: str,
    state: MarketRevisionState = MarketRevisionState.APPROVED,
    created_at: datetime = _TIE,
    root_id: str | None = None,
) -> str:
    """One tick/trade revision on an ACTIVE market-dataset root."""
    entity_id = root_id or f"root_of_{revision_id}"
    root = await session.get(EntityRegistry, entity_id)
    if root is None:
        root = EntityRegistry(
            entity_id=entity_id,
            entity_type="market_dataset",
            owner_principal_id="user_1",
            created_by_principal_id="user_1",
            lifecycle_state="active",
        )
        session.add(root)
        await session.flush()
    session.add(
        MarketDatasetRevision(
            revision_id=revision_id,
            entity_id=entity_id,
            revision_no=1,
            market_data_type=MarketDataType.TICK_TRADES,
            revision_state=state,
            instrument_id=instrument_id,
            payload={},
            content_hash="c" * 64,
            created_by_principal_id="user_1",
            created_at=created_at,
        )
    )
    await session.flush()
    return revision_id


async def _mirror_item(session, *, item_id: str, instrument_id: str, require: bool = True) -> dict:
    """A manifest entry in the doc 02 §7.1 MIRROR shape.

    The work-object revision carries only ``strategy_revision_id``; the config that
    decides whether tick data is demanded lives on the typed StrategyRevision behind
    it. An item built this way therefore only reaches the tick probe if the mirror was
    dereferenced correctly — which is what makes it the right shape for this file.
    """
    registry_root, strategy_root, _work_root, _draft = await strat_repo.create_strategy(
        session,
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        display_name=f"Parity {item_id}",
        rationale_family_id=None,
        initial_payload={"data": {}},
    )
    await session.flush()
    strategy_revision = await strat_repo.append_strategy_revision(
        session,
        strategy_root,
        payload=_tick_config(instrument_id, require=require),
        config_hash="0" * 64,
        validation_status=ValidationStatusEnum.VALID,
        created_by_principal_id="user_1",
    )
    await session.flush()
    mirror = await mb_repo.append_work_object_revision(
        session,
        registry_root,
        object_kind=MainboardItemKind.STRATEGY,
        payload={"strategy_revision_id": strategy_revision.revision_id},
        source_provenance={"strategy_revision_id": strategy_revision.revision_id},
        created_by_principal_id="user_1",
    )
    await session.flush()
    return {
        "item_id": item_id,
        "kind": str(MainboardItemKind.STRATEGY),
        "root_id": registry_root.entity_id,
        "revision_id": mirror.revision_id,
        "enabled": True,
    }


async def _direct_item(session, *, item_id: str, instrument_id: str, require: bool = True) -> dict:
    """The other pinning shape: the work-object revision carries the config itself."""
    registry_root, _strategy_root, _work_root, _draft = await strat_repo.create_strategy(
        session,
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        display_name=f"Direct {item_id}",
        rationale_family_id=None,
        initial_payload={"data": {}},
    )
    await session.flush()
    direct = await mb_repo.append_work_object_revision(
        session,
        registry_root,
        object_kind=MainboardItemKind.STRATEGY,
        payload=_tick_config(instrument_id, require=require),
        created_by_principal_id="user_1",
    )
    await session.flush()
    return {
        "item_id": item_id,
        "kind": str(MainboardItemKind.STRATEGY),
        "root_id": registry_root.entity_id,
        "revision_id": direct.revision_id,
        "enabled": True,
    }


# ------------------------------------------------------------------ which row is pinned


async def test_batch_pins_the_same_revision_the_per_instrument_reader_returns(session) -> None:
    """The batch and the per-instrument reader agree — on a deliberate created_at TIE.

    Three APPROVED tick revisions for one instrument share the SAME ``created_at``, so
    the primary sort key cannot separate them and ``revision_id DESC`` is the only
    thing deciding the winner. The assertion is an ORACLE comparison rather than a
    hardcoded id: whatever ``find_approved_tick_revision_for_instrument`` picks is what
    the manifest must carry, because that reader is what the pin meant before P4.
    """
    await _principal(session)
    for revision_id in ("tickrev_aaa", "tickrev_ccc", "tickrev_bbb"):
        await _tick_revision(session, revision_id=revision_id, instrument_id="TIEUSDT")
    item = await _mirror_item(session, item_id="item_tie", instrument_id="TIEUSDT")
    await session.commit()

    oracle = await market_repo.find_approved_tick_revision_for_instrument(session, "TIEUSDT")
    assert oracle is not None
    pins = await _resolve_tick_pins(session, {"items": [item]})

    assert pins == {
        "item_tie": {"tick_revision_id": oracle.revision_id, "instrument_id": "TIEUSDT"}
    }
    # And the total order really is what decided it, so the test would notice a batch
    # that returned "some approved row for the instrument".
    assert oracle.revision_id == "tickrev_ccc"


async def test_only_approved_revisions_on_active_roots_are_pinnable(session) -> None:
    """Every guard the per-instrument reader applied still applies, in SQL.

    A DRAFT revision with the HIGHEST id and a revision on a SOFT-DELETED root both
    lose to the one APPROVED revision on an ACTIVE root, even though all three share
    the tie instant. Without this the batch could pass the tie test by picking the
    newest row of any state.
    """
    await _principal(session)
    await _tick_revision(
        session,
        revision_id="tickrev_zzz_draft",
        instrument_id="GUARDUSDT",
        state=MarketRevisionState.DRAFT,
    )
    await _tick_revision(
        session,
        revision_id="tickrev_yyy_deleted_root",
        instrument_id="GUARDUSDT",
        root_id="root_soft_deleted",
    )
    deleted_root = await session.get(EntityRegistry, "root_soft_deleted")
    assert deleted_root is not None
    deleted_root.deletion_state = "soft_deleted"
    await _tick_revision(session, revision_id="tickrev_aaa_ok", instrument_id="GUARDUSDT")
    item = await _mirror_item(session, item_id="item_guard", instrument_id="GUARDUSDT")
    await session.commit()

    oracle = await market_repo.find_approved_tick_revision_for_instrument(session, "GUARDUSDT")
    assert oracle is not None and oracle.revision_id == "tickrev_aaa_ok"
    pins = await _resolve_tick_pins(session, {"items": [item]})
    assert pins is not None
    assert pins["item_guard"]["tick_revision_id"] == "tickrev_aaa_ok"


async def test_every_item_gets_its_own_instruments_pin(session) -> None:
    """A composition of many items pins each item's OWN instrument, not a shared row."""
    await _principal(session)
    items = []
    for index in range(4):
        await _tick_revision(
            session, revision_id=f"tickrev_multi_{index}", instrument_id=f"MULTI_{index}"
        )
        items.append(
            await _mirror_item(session, item_id=f"item_{index}", instrument_id=f"MULTI_{index}")
        )
    await session.commit()

    pins = await _resolve_tick_pins(session, {"items": items})
    assert pins == {
        f"item_{index}": {
            "tick_revision_id": f"tickrev_multi_{index}",
            "instrument_id": f"MULTI_{index}",
        }
        for index in range(4)
    }


# ------------------------------------------------------------------ the 422 is unchanged


async def test_unpinnable_requirement_is_still_a_typed_422(session) -> None:
    """The fail-closed reject keeps its code and both promoted envelope fields."""
    await _principal(session)
    item = await _mirror_item(session, item_id="item_blocked", instrument_id="NOTICKUSDT")
    await session.commit()

    with pytest.raises(ReadinessBlockedError) as caught:
        await _resolve_tick_pins(session, {"items": [item]})

    error = caught.value
    assert error.field_path == "data.intrabar_policy.tick_policy"
    assert error.scope_id == "item_blocked"
    assert [detail["code"] for detail in error.details] == [
        ReadinessIssueCode.TICK_DATA_UNAVAILABLE.value
    ]
    assert error.details[0]["field"] == "data.intrabar_policy.tick_policy"
    assert error.details[0]["scope_id"] == "item_blocked"
    assert error.remediation


async def test_the_blocker_names_the_first_failing_item_in_manifest_order(session) -> None:
    """Batching the reads must not reorder WHICH item is reported.

    The old loop resolved and decided one item at a time, so it raised on the first
    unpinnable item it reached. The new shape resolves every demand before deciding
    any of them, which is exactly where that guarantee could be lost.

    The two unpinnable instruments are named so the two candidate orderings DISAGREE:
    ``item_b`` is second in the manifest but its instrument (``ZZZ_B``) sorts last,
    while ``item_c`` is third but sorts first (``AAA_C``). A deciding pass that walked
    the batch's own instrument ordering — or its misses — would name ``item_c``. Only
    manifest order names ``item_b``.
    """
    await _principal(session)
    await _tick_revision(session, revision_id="tickrev_ok_a", instrument_id="MMM_A")
    items = [
        await _mirror_item(session, item_id="item_a", instrument_id="MMM_A"),
        await _mirror_item(session, item_id="item_b", instrument_id="ZZZ_B"),
        await _mirror_item(session, item_id="item_c", instrument_id="AAA_C"),
    ]
    await session.commit()

    with pytest.raises(ReadinessBlockedError) as caught:
        await _resolve_tick_pins(session, {"items": items})
    assert caught.value.scope_id == "item_b"


# ------------------------------------------------------ what the leg still skips silently


async def test_a_strategy_that_does_not_demand_tick_data_pins_nothing(session) -> None:
    """``inherit`` is not a requirement, so the whole leg returns ``None``.

    The manifest then carries an explicit ``tick_data: null``. This is also the
    fixture mistake the budget row warns about: measure THIS shape and a leg that
    never ran reports a perfectly flat slope.
    """
    await _principal(session)
    await _tick_revision(session, revision_id="tickrev_unused", instrument_id="INHERITUSDT")
    item = await _mirror_item(
        session, item_id="item_inherit", instrument_id="INHERITUSDT", require=False
    )
    await session.commit()

    assert await _resolve_tick_pins(session, {"items": [item]}) is None


async def test_a_directly_pinned_config_needs_no_mirror_deref(session) -> None:
    """The non-mirror shape still resolves — the mirror batch must not become required.

    ``get_strategy_revisions`` is asked only for the refs that exist, so an item whose
    work-object revision carries the config itself contributes no id to it and reads
    its config straight off the revision, exactly as before.
    """
    await _principal(session)
    await _tick_revision(session, revision_id="tickrev_direct", instrument_id="DIRECTUSDT")
    item = await _direct_item(session, item_id="item_direct", instrument_id="DIRECTUSDT")
    await session.commit()

    pins = await _resolve_tick_pins(session, {"items": [item]})
    assert pins is not None
    assert pins["item_direct"]["tick_revision_id"] == "tickrev_direct"


async def test_an_unresolvable_mirror_falls_through_exactly_as_the_per_id_miss_did(
    session,
) -> None:
    """A mirror ref with no row is ABSENT from the batch — the same as ``session.get``
    returning ``None``.

    ``_resolve_strategy_payload`` then returns the mirror payload unchanged, it fails
    ``StrategyConfig`` validation, and the item is skipped for readiness'
    ``STRATEGY_CONFIG_INVALID`` to report. The equivalence matters because it is the
    reason the batch may be consulted INSTEAD of the read rather than in addition to
    it — a batch that omitted rows for any other reason would silently turn a real
    config into a skipped item.
    """
    await _principal(session)
    await _tick_revision(session, revision_id="tickrev_dangling", instrument_id="DANGLEUSDT")
    registry_root, _strategy_root, _work_root, _draft = await strat_repo.create_strategy(
        session,
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        display_name="Dangling mirror",
        rationale_family_id=None,
        initial_payload={"data": {}},
    )
    await session.flush()
    dangling = await mb_repo.append_work_object_revision(
        session,
        registry_root,
        object_kind=MainboardItemKind.STRATEGY,
        payload={"strategy_revision_id": "strev_does_not_exist"},
        created_by_principal_id="user_1",
    )
    await session.flush()
    await session.commit()

    item = {
        "item_id": "item_dangling",
        "kind": str(MainboardItemKind.STRATEGY),
        "root_id": registry_root.entity_id,
        "revision_id": dangling.revision_id,
        "enabled": True,
    }
    assert await _resolve_tick_pins(session, {"items": [item]}) is None
