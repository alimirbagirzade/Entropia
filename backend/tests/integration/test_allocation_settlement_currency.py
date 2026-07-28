"""Lock the settlement-currency resolver, per item kind (doc 13 §5.1).

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).

``queries/allocation_currency.py::resolve_settlement_currencies`` feeds the pure FX
cross-check used by allocation validate, plan-revision and Ready Check. No test
referenced it directly; ``test_allocation_fx_dependency.py`` reaches it only through
the STRATEGY direct-payload branch, so the mirror deref and the TRADING_SIGNAL /
TRADE_LOG branches were unguarded — and every failure mode of this resolver is
SILENT by design (an unresolved link yields ``None`` and the FX check SKIPS the
item), so a broken branch degrades a blocker into a pass with nothing to notice.

Covers each resolution route (strategy direct, strategy §7.1 mirror deref, trading
signal, trade log) and every documented reason to yield ``None``. The resolver reads
only ``item_id`` / ``item_kind`` / ``pinned_revision_id`` off each item, so items are
built detached — the pins they carry are real, committed rows. Behaviour is
unchanged; this only pins it.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.queries.allocation_currency import resolve_settlement_currencies
from entropia.domain.identity import Actor
from entropia.domain.instrument.enums import ContractType
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.strategy.enums import ValidationStatusEnum
from entropia.domain.trade_log.enums import RecordBatchStatus
from entropia.domain.trading_signal.enums import NormalizedRevisionStatus
from entropia.infrastructure.postgres.models import MainboardWorkingItem, Principal
from entropia.infrastructure.postgres.repositories import instrument as instrument_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import source_asset as asset_repo
from entropia.infrastructure.postgres.repositories import strategy as strat_repo
from entropia.infrastructure.postgres.repositories import trade_log as tl_repo
from entropia.infrastructure.postgres.repositories import trading_signal as ts_repo
from entropia.shared.ids import new_id

pytestmark = pytest.mark.integration

USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_AVAILABLE_TIME = datetime(2024, 5, 1, 10, 0, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# Seeding                                                                      #
# --------------------------------------------------------------------------- #


async def _seed_principal(session) -> None:
    if await session.get(Principal, "user_1") is None:
        session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _seed_instrument(session, *, symbol: str, settlement: str | None) -> str:
    instrument = instrument_repo.create_instrument(
        session,
        resolution_key=f"binance:{symbol.lower()}:perpetual",
        venue_id="binance",
        symbol=symbol,
        contract_type=ContractType.PERPETUAL,
        display_name=f"{symbol} Perpetual",
        settlement_asset=settlement,
        created_by_principal_id="user_1",
    )
    await session.flush()
    return instrument.instrument_id


def _item(kind: MainboardItemKind, pinned_revision_id: str) -> MainboardWorkingItem:
    """A detached stand-in carrying only what the resolver reads."""
    return MainboardWorkingItem(
        item_id=new_id("mbitem"),
        item_kind=kind,
        pinned_revision_id=pinned_revision_id,
    )


async def _strategy_revision(session, payload: dict) -> str:
    """A strategy work-object revision pinning ``payload`` directly."""
    work_object = await mb_cmd.create_work_object(
        session, USER, object_kind="strategy", payload=payload
    )
    await session.flush()
    return str(work_object["revision_id"])


async def _mirror_revision(session, *, instrument_id: str | None) -> str:
    """The doc 02 §7.1 shape: the pinned work-object revision holds only a
    ``strategy_revision_id``; the instrument lives on the typed strategy revision."""
    registry_root, strategy_root, _work_root, _draft = await strat_repo.create_strategy(
        session,
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        display_name="Mirrored Strategy",
        rationale_family_id=None,
        initial_payload={"data": {}},
    )
    await session.flush()
    strategy_revision = await strat_repo.append_strategy_revision(
        session,
        strategy_root,
        payload={"data": {"instrument_id": instrument_id}},
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
    return str(mirror.revision_id)


async def _source_asset_id(session) -> str:
    asset_id = new_id("srcasset")
    await asset_repo.create_source_asset(
        session,
        source_asset_id=asset_id,
        owner_principal_id="user_1",
        object_key=f"source/{asset_id}/data",
        raw_asset_hash="a" * 64,
        size_bytes=32,
        content_type="text/csv",
        original_filename="data.csv",
        draft_id=None,
        uploaded_by_principal_id="user_1",
    )
    await session.flush()
    return asset_id


async def _signal_revision(session, *, instrument_id: str | None) -> str:
    work_object = await mb_cmd.create_work_object(
        session,
        USER,
        object_kind="trading_signal",
        payload={"display_name": "Signal"},
        available_time=_AVAILABLE_TIME,
    )
    await session.flush()
    normalized = await ts_repo.create_normalized_revision(
        session,
        source_asset_id=await _source_asset_id(session),
        job_id=None,
        status=NormalizedRevisionStatus.SUCCEEDED,
        instrument_id=instrument_id,
        accepted_count=1,
        skipped_count=0,
        events=[],
        skipped_rows=[],
        validation_summary=None,
        earliest_available_time=_AVAILABLE_TIME,
        content_hash="b" * 64,
        created_by_principal_id="user_1",
    )
    normalized.work_object_revision_id = str(work_object["revision_id"])
    await session.flush()
    return str(work_object["revision_id"])


async def _trade_log_revision(session, *, instrument_id: str | None) -> str:
    work_object = await mb_cmd.create_work_object(
        session,
        USER,
        object_kind="trade_log",
        payload={"display_name": "Trade Log"},
        available_time=_AVAILABLE_TIME,
    )
    await session.flush()
    batch = await tl_repo.create_record_batch(
        session,
        source_asset_id=await _source_asset_id(session),
        job_id=None,
        status=RecordBatchStatus.SUCCEEDED,
        instrument_id=instrument_id,
        accepted_count=1,
        skipped_count=0,
        records=[],
        skipped_rows=[],
        validation_summary=None,
        earliest_entry_time=_AVAILABLE_TIME,
        latest_exit_time=_AVAILABLE_TIME,
        content_hash="c" * 64,
        created_by_principal_id="user_1",
    )
    batch.work_object_revision_id = str(work_object["revision_id"])
    await session.flush()
    return str(work_object["revision_id"])


# --------------------------------------------------------------------------- #
# Resolution routes                                                            #
# --------------------------------------------------------------------------- #


async def test_resolves_a_strategy_pin_through_its_payload_instrument(session) -> None:
    await _seed_principal(session)
    instrument_id = await _seed_instrument(session, symbol="BTCUSDT", settlement="USDT")
    revision_id = await _strategy_revision(session, {"data": {"instrument_id": instrument_id}})
    item = _item(MainboardItemKind.STRATEGY, revision_id)

    assert await resolve_settlement_currencies(session, [item]) == {item.item_id: "USDT"}


async def test_resolves_a_strategy_pin_through_the_mirror_strategy_revision(session) -> None:
    await _seed_principal(session)
    instrument_id = await _seed_instrument(session, symbol="ETHUSD", settlement="USD")
    revision_id = await _mirror_revision(session, instrument_id=instrument_id)
    item = _item(MainboardItemKind.STRATEGY, revision_id)

    assert await resolve_settlement_currencies(session, [item]) == {item.item_id: "USD"}


async def test_resolves_a_trading_signal_pin_through_its_normalized_revision(session) -> None:
    await _seed_principal(session)
    instrument_id = await _seed_instrument(session, symbol="SOLEUR", settlement="EUR")
    revision_id = await _signal_revision(session, instrument_id=instrument_id)
    item = _item(MainboardItemKind.TRADING_SIGNAL, revision_id)

    assert await resolve_settlement_currencies(session, [item]) == {item.item_id: "EUR"}


async def test_resolves_a_trade_log_pin_through_its_record_batch(session) -> None:
    await _seed_principal(session)
    instrument_id = await _seed_instrument(session, symbol="XRPUSDC", settlement="USDC")
    revision_id = await _trade_log_revision(session, instrument_id=instrument_id)
    item = _item(MainboardItemKind.TRADE_LOG, revision_id)

    assert await resolve_settlement_currencies(session, [item]) == {item.item_id: "USDC"}


# --------------------------------------------------------------------------- #
# Unresolvable links yield None (never a fabricated currency)                  #
# --------------------------------------------------------------------------- #


async def test_returns_none_when_the_strategy_payload_carries_no_instrument(session) -> None:
    await _seed_principal(session)
    revision_id = await _strategy_revision(session, {"note": "no instrument here"})
    item = _item(MainboardItemKind.STRATEGY, revision_id)

    assert await resolve_settlement_currencies(session, [item]) == {item.item_id: None}


async def test_returns_none_when_the_strategy_instrument_id_is_blank(session) -> None:
    await _seed_principal(session)
    revision_id = await _strategy_revision(session, {"data": {"instrument_id": "   "}})
    item = _item(MainboardItemKind.STRATEGY, revision_id)

    assert await resolve_settlement_currencies(session, [item]) == {item.item_id: None}


async def test_returns_none_when_the_mirror_target_has_no_instrument(session) -> None:
    await _seed_principal(session)
    revision_id = await _mirror_revision(session, instrument_id=None)
    item = _item(MainboardItemKind.STRATEGY, revision_id)

    assert await resolve_settlement_currencies(session, [item]) == {item.item_id: None}


async def test_returns_none_when_the_pinned_revision_does_not_exist(session) -> None:
    await _seed_principal(session)
    item = _item(MainboardItemKind.STRATEGY, "worev_missing")

    assert await resolve_settlement_currencies(session, [item]) == {item.item_id: None}


async def test_returns_none_when_no_normalized_revision_pins_the_signal(session) -> None:
    await _seed_principal(session)
    work_object = await mb_cmd.create_work_object(
        session,
        USER,
        object_kind="trading_signal",
        payload={"display_name": "Unpinned"},
        available_time=_AVAILABLE_TIME,
    )
    await session.flush()
    item = _item(MainboardItemKind.TRADING_SIGNAL, str(work_object["revision_id"]))

    assert await resolve_settlement_currencies(session, [item]) == {item.item_id: None}


async def test_returns_none_when_no_record_batch_pins_the_trade_log(session) -> None:
    await _seed_principal(session)
    work_object = await mb_cmd.create_work_object(
        session,
        USER,
        object_kind="trade_log",
        payload={"display_name": "Unpinned"},
        available_time=_AVAILABLE_TIME,
    )
    await session.flush()
    item = _item(MainboardItemKind.TRADE_LOG, str(work_object["revision_id"]))

    assert await resolve_settlement_currencies(session, [item]) == {item.item_id: None}


async def test_returns_none_when_the_instrument_row_is_absent(session) -> None:
    await _seed_principal(session)
    revision_id = await _strategy_revision(session, {"data": {"instrument_id": "instr_missing"}})
    item = _item(MainboardItemKind.STRATEGY, revision_id)

    assert await resolve_settlement_currencies(session, [item]) == {item.item_id: None}


async def test_returns_none_when_the_instrument_declares_no_settlement_asset(session) -> None:
    await _seed_principal(session)
    instrument_id = await _seed_instrument(session, symbol="NOSETTLE", settlement=None)
    revision_id = await _strategy_revision(session, {"data": {"instrument_id": instrument_id}})
    item = _item(MainboardItemKind.STRATEGY, revision_id)

    assert await resolve_settlement_currencies(session, [item]) == {item.item_id: None}


# --------------------------------------------------------------------------- #
# Mapping shape                                                                #
# --------------------------------------------------------------------------- #


async def test_returns_an_entry_for_every_item_including_unresolved_ones(session) -> None:
    await _seed_principal(session)
    instrument_id = await _seed_instrument(session, symbol="ADAUSDT", settlement="USDT")
    resolved = _item(
        MainboardItemKind.STRATEGY,
        await _strategy_revision(session, {"data": {"instrument_id": instrument_id}}),
    )
    unresolved = _item(MainboardItemKind.STRATEGY, await _strategy_revision(session, {"data": {}}))

    result = await resolve_settlement_currencies(session, [resolved, unresolved])

    assert result == {resolved.item_id: "USDT", unresolved.item_id: None}


async def test_returns_an_empty_mapping_for_an_empty_composition(session) -> None:
    assert await resolve_settlement_currencies(session, []) == {}
