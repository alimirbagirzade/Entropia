"""K-08 — Trading Signal OHLCV dependency resolved against a real database.

The pure validator (``tests/unit/test_ts_price_policy_ohlcv_fallback.py``) proves a
DECLARED reference is required. This suite proves the two facts only a DB read can
establish, per doc 04 §5 "Fallback options require **compatible approved** Market Data
at Ready Check":

* *approved* — a pinned revision that is not APPROVED on an ACTIVE root still blocks
  with ``MARKET_DATA_DEPENDENCY_BLOCKED``; approving it clears the blocker;
* *compatible* — ``ohlcv_intrabar_if_available`` pinned to a bar-only OHLCV dataset
  blocks with ``INTRABAR_DATA_UNAVAILABLE`` (doc 04 §5.2 intrabar row); repinning to an
  approved tick/trade dataset clears it.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.domain.identity import Actor
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.domain.trading_signal.enums import NormalizedRevisionStatus
from entropia.infrastructure.postgres.models import EntityRegistry, MarketDatasetRevision
from entropia.infrastructure.postgres.repositories import trading_signal as ts_repo
from entropia.shared.ids import new_id
from tests.integration.test_readiness_persistence import (
    USER1,
    _empty_composition,
    _seed_principals,
)

pytestmark = pytest.mark.integration

_INSTRUMENT = "BTCUSDT"
_OHLCV_REF = "k08_md_rev_ohlcv"
_TICK_REF = "k08_md_rev_tick"


async def _seed_dataset(
    session,
    *,
    root_id: str,
    revision_id: str,
    data_type: MarketDataType,
    state: MarketRevisionState,
) -> None:
    """Seed (or re-state) one market dataset revision under its own ACTIVE root."""
    root = await session.get(EntityRegistry, root_id)
    if root is None:
        root = EntityRegistry(
            entity_id=root_id,
            entity_type="market_dataset",
            owner_principal_id="user_1",
            created_by_principal_id="user_1",
            lifecycle_state="active",
            current_revision_id=None,
        )
        session.add(root)
        await session.flush()
        session.add(
            MarketDatasetRevision(
                revision_id=revision_id,
                entity_id=root_id,
                revision_no=1,
                market_data_type=data_type,
                revision_state=state,
                instrument_id=_INSTRUMENT,
                payload={},
                content_hash=revision_id.ljust(64, "0")[:64],
                created_by_principal_id="user_1",
            )
        )
        root.current_revision_id = revision_id
    else:
        revision = await session.get(MarketDatasetRevision, revision_id)
        assert revision is not None
        revision.revision_state = state
    await session.flush()


def _signal_payload(
    source_asset_id: str, normalized_revision_id: str, price_policy: dict[str, Any]
) -> dict[str, Any]:
    return {
        "kind": "trading_signal",
        "identity": {"display_name": "K-08 signal source"},
        "source": {"provider_name": "Provider X", "source_kind": "file"},
        "instrument_scope": {"instrument_id": _INSTRUMENT, "display_symbol": _INSTRUMENT},
        "event_model": {"resolution_kind": "event_based", "base_timeframe": None},
        "classification": {"rationale_family_id": None},
        "data_quality": {"mode": "signal_events_only"},
        "time_policy": {"source_timezone": "Europe/Istanbul", "normalization_timezone": "UTC"},
        "price_policy": price_policy,
        "ohlcv_policy": {"use_mode": "use_if_supplied_and_needed"},
        "capital": {"independent_initial_capital": "10000"},
        "import_binding": {
            "source_asset_id": source_asset_id,
            "normalized_event_revision_id": normalized_revision_id,
        },
    }


async def _composition_with_signal(session, actor: Actor, price_policy: dict[str, Any]) -> str:
    """A one-item composition holding a Trading Signal with the given price policy."""
    workspace_id = await _empty_composition(session, actor)
    asset = await ts_repo.create_source_asset(
        session,
        source_asset_id=new_id("srcast"),
        owner_principal_id=actor.principal_id,
        draft_id=None,
        object_key="signal/raw/k08/seed.csv",
        raw_asset_hash="9" * 64,
        size_bytes=128,
        content_type="text/csv",
        original_filename="signals.csv",
        uploaded_by_principal_id=actor.principal_id,
    )
    await session.flush()
    normalized = await ts_repo.create_normalized_revision(
        session,
        source_asset_id=asset.source_asset_id,
        job_id=None,
        status=NormalizedRevisionStatus.SUCCEEDED,
        instrument_id=_INSTRUMENT,
        accepted_count=2,
        skipped_count=0,
        events=[],
        skipped_rows=[],
        validation_summary={"source_timezone": "Europe/Istanbul", "mapping_hash": "7" * 64},
        earliest_available_time=None,
        content_hash="8" * 64,
        created_by_principal_id=actor.principal_id,
    )
    await session.flush()
    work_object = await mb_cmd.create_work_object(
        session,
        actor,
        object_kind="trading_signal",
        payload=_signal_payload(
            asset.source_asset_id, normalized.normalized_revision_id, price_policy
        ),
        available_time=datetime(2024, 1, 1, tzinfo=UTC),
    )
    ts_repo.link_normalized_to_revision(normalized, work_object["revision_id"])
    await mb_cmd.attach_mainboard_item(
        session,
        actor,
        workspace_id=workspace_id,
        root_id=work_object["root_id"],
        revision_id=work_object["revision_id"],
        item_kind="trading_signal",
    )
    await session.commit()
    return workspace_id


def _codes(result: dict[str, Any]) -> set[str]:
    return {i["code"] for i in result["issues"]}


async def test_ohlcv_fallback_without_any_pin_blocks_the_signal(session) -> None:
    """The regression K-08 fixes: this composition used to reach Ready PASS."""
    await _seed_principals(session)
    composition_id = await _composition_with_signal(
        session, USER1, {"source": "ohlcv_close_if_needed", "fallback": None}
    )
    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert result["state"] == "not_ready"
    assert "MARKET_DATA_DEPENDENCY_BLOCKED" in _codes(result)


async def test_unapproved_pin_blocks_then_approving_it_passes(session) -> None:
    await _seed_principals(session)
    await _seed_dataset(
        session,
        root_id="k08_ohlcv_root",
        revision_id=_OHLCV_REF,
        data_type=MarketDataType.OHLCV,
        state=MarketRevisionState.NEEDS_REVIEW,
    )
    composition_id = await _composition_with_signal(
        session,
        USER1,
        {
            "source": "ohlcv_close_if_needed",
            "fallback": None,
            "approved_market_data_revision_ref": _OHLCV_REF,
        },
    )

    blocked = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert blocked["state"] == "not_ready"
    assert "MARKET_DATA_DEPENDENCY_BLOCKED" in _codes(blocked)

    await _seed_dataset(
        session,
        root_id="k08_ohlcv_root",
        revision_id=_OHLCV_REF,
        data_type=MarketDataType.OHLCV,
        state=MarketRevisionState.APPROVED,
    )
    await session.commit()
    approved = await readiness_cmd.run_readiness_check(
        session, USER1, composition_id=composition_id
    )
    assert "MARKET_DATA_DEPENDENCY_BLOCKED" not in _codes(approved)
    assert approved["state"] == "ready"


async def test_intrabar_over_a_bar_only_dataset_blocks(session) -> None:
    """doc 04 §5.2: an approved OHLCV pin is still not INTRABAR-capable."""
    await _seed_principals(session)
    await _seed_dataset(
        session,
        root_id="k08_ohlcv_root",
        revision_id=_OHLCV_REF,
        data_type=MarketDataType.OHLCV,
        state=MarketRevisionState.APPROVED,
    )
    composition_id = await _composition_with_signal(
        session,
        USER1,
        {
            "source": "ohlcv_intrabar_if_available",
            "fallback": None,
            "approved_market_data_revision_ref": _OHLCV_REF,
        },
    )
    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert result["state"] == "not_ready"
    codes = _codes(result)
    assert "INTRABAR_DATA_UNAVAILABLE" in codes
    # The pin IS approved, so the dependency blocker must not double-report.
    assert "MARKET_DATA_DEPENDENCY_BLOCKED" not in codes


async def test_intrabar_over_an_approved_tick_dataset_passes(session) -> None:
    await _seed_principals(session)
    await _seed_dataset(
        session,
        root_id="k08_tick_root",
        revision_id=_TICK_REF,
        data_type=MarketDataType.TICK_TRADES,
        state=MarketRevisionState.APPROVED,
    )
    composition_id = await _composition_with_signal(
        session,
        USER1,
        {
            "source": "ohlcv_intrabar_if_available",
            "fallback": None,
            "approved_market_data_revision_ref": _TICK_REF,
        },
    )
    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert "INTRABAR_DATA_UNAVAILABLE" not in _codes(result)
    assert result["state"] == "ready"


async def test_suggested_signal_price_never_demands_market_data(session) -> None:
    """No regression for the default source: no pin, no blocker, still Ready."""
    await _seed_principals(session)
    composition_id = await _composition_with_signal(
        session, USER1, {"source": "suggested_signal_price", "fallback": None}
    )
    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    codes = _codes(result)
    assert "MARKET_DATA_DEPENDENCY_BLOCKED" not in codes
    assert "INTRABAR_DATA_UNAVAILABLE" not in codes
    assert result["state"] == "ready"
