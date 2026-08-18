"""P1 — the batched tick-revision reader picks the SAME row the per-instrument one does.

``_resolve_tick_data_issues`` used to call
``market_repo.find_approved_tick_revision_for_instrument`` once per require-tick Strategy;
it now issues one ``IN()`` read through
``market_repo.find_approved_tick_revisions_for_instruments``. That is a **performance**
change, so the only thing that may move is the statement count — never a readiness answer.

This file is the parity proof, and it is deliberately a PAIRWISE one: for every instrument
in a deliberately awkward fixture it asserts that the batch's answer and the per-instrument
reader's answer are the same object identity, rather than asserting each against a
hand-written expectation that could encode the same mistake twice.

Why the batch CAN be trusted to agree (and why leg 3 cannot): the per-instrument query
orders by ``created_at DESC, revision_id DESC LIMIT 1``, and that order is **total** —
``revision_id`` breaks every ``created_at`` tie — so "the newest approved tick revision for
this instrument" names exactly one row. ``DISTINCT ON (instrument_id)`` over the same
ordering therefore cannot resolve a tie differently. The fixture below includes an exact
``created_at`` tie precisely so that claim is tested rather than asserted.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event

from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.infrastructure.postgres.models import EntityRegistry, MarketDatasetRevision
from entropia.infrastructure.postgres.repositories import market_data as market_repo

pytestmark = pytest.mark.integration

_BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


async def _root(
    session,
    entity_id: str,
    *,
    entity_type: str = market_repo.ENTITY_TYPE,
    deletion_state: DeletionState = DeletionState.ACTIVE,
) -> None:
    session.add(
        EntityRegistry(
            entity_id=entity_id,
            entity_type=entity_type,
            owner_principal_id=None,
            created_by_principal_id=None,
            lifecycle_state="active",
            deletion_state=deletion_state,
            current_revision_id=None,
        )
    )
    await session.flush()


async def _revision(
    session,
    revision_id: str,
    *,
    entity_id: str,
    instrument_id: str,
    state: MarketRevisionState = MarketRevisionState.APPROVED,
    data_type: MarketDataType = MarketDataType.TICK_TRADES,
    minutes: int = 0,
    revision_no: int = 1,
) -> None:
    session.add(
        MarketDatasetRevision(
            revision_id=revision_id,
            entity_id=entity_id,
            revision_no=revision_no,
            market_data_type=data_type,
            revision_state=state,
            instrument_id=instrument_id,
            payload={},
            content_hash="c" * 64,
            created_by_principal_id=None,
            created_at=_BASE_TIME + timedelta(minutes=minutes),
        )
    )
    await session.flush()


async def _seed_every_shape(session) -> list[str]:
    """One instrument per shape the SQL guards must decide, including two ties.

    Returns every instrument id the parity assertion must cover — including the ones
    that must resolve to NOTHING, because "absent from the map" is the answer the
    caller's fail-closed branch depends on.
    """
    # NEWEST: three approved tick revisions, ascending created_at. The newest must win.
    await _root(session, "tick_root_newest")
    for i, minutes in enumerate((0, 30, 60)):
        await _revision(
            session,
            f"rev_newest_{i}",
            entity_id="tick_root_newest",
            instrument_id="INSTR_NEWEST",
            minutes=minutes,
            revision_no=i + 1,
        )

    # TIE: two approved tick revisions at the EXACT same created_at. Only revision_id
    # separates them, which is the whole reason the per-item order is total.
    await _root(session, "tick_root_tie")
    await _revision(
        session, "rev_tie_aaa", entity_id="tick_root_tie", instrument_id="INSTR_TIE", minutes=10
    )
    await _revision(
        session,
        "rev_tie_zzz",
        entity_id="tick_root_tie",
        instrument_id="INSTR_TIE",
        minutes=10,
        revision_no=2,
    )

    # DRAFT only — revision_state guard.
    await _root(session, "tick_root_draft")
    await _revision(
        session,
        "rev_draft",
        entity_id="tick_root_draft",
        instrument_id="INSTR_DRAFT",
        state=MarketRevisionState.DRAFT,
    )

    # Approved tick data on a SOFT-DELETED root — deletion_state guard.
    await _root(session, "tick_root_deleted", deletion_state=DeletionState.SOFT_DELETED)
    await _revision(
        session, "rev_deleted", entity_id="tick_root_deleted", instrument_id="INSTR_DELETED"
    )

    # Approved OHLCV, not tick/trade — market_data_type guard.
    await _root(session, "tick_root_ohlcv")
    await _revision(
        session,
        "rev_ohlcv",
        entity_id="tick_root_ohlcv",
        instrument_id="INSTR_OHLCV",
        data_type=MarketDataType.OHLCV,
    )

    # Approved tick data hanging off a root of the WRONG entity type — entity_type guard.
    await _root(session, "tick_root_alien", entity_type="research_dataset")
    await _revision(session, "rev_alien", entity_id="tick_root_alien", instrument_id="INSTR_ALIEN")

    await session.commit()
    return [
        "INSTR_NEWEST",
        "INSTR_TIE",
        "INSTR_DRAFT",
        "INSTR_DELETED",
        "INSTR_OHLCV",
        "INSTR_ALIEN",
        "INSTR_ABSENT",  # nothing seeded at all
    ]


async def test_batch_and_per_instrument_readers_agree_on_every_shape(session) -> None:
    """The batch's answer equals the per-instrument answer, instrument by instrument.

    This is the readiness-answer parity proof. Every guard the per-instrument reader
    applies stays in the batch's SQL, so an instrument that resolved to ``None`` is
    ABSENT from the map — the two are the same answer spelled two ways, and the caller's
    fail-closed branch cannot tell them apart.
    """
    instruments = await _seed_every_shape(session)

    batched = await market_repo.find_approved_tick_revisions_for_instruments(session, instruments)

    for instrument in instruments:
        single = await market_repo.find_approved_tick_revision_for_instrument(session, instrument)
        found = batched.get(instrument)
        if single is None:
            assert found is None, (
                f"{instrument}: the batch found {found and found.revision_id!r} where the "
                f"per-instrument reader found nothing — a readiness answer would change"
            )
        else:
            assert found is not None, (
                f"{instrument}: the batch lost the row {single.revision_id!r} the "
                f"per-instrument reader returns — a readiness answer would change"
            )
            assert found.revision_id == single.revision_id

    # Pin the two decisions that would otherwise only be asserted transitively, so a
    # future change that breaks BOTH readers the same way still fails here.
    assert batched["INSTR_NEWEST"].revision_id == "rev_newest_2"
    assert batched["INSTR_TIE"].revision_id == "rev_tie_zzz"
    for blocked in ("INSTR_DRAFT", "INSTR_DELETED", "INSTR_OHLCV", "INSTR_ALIEN", "INSTR_ABSENT"):
        assert blocked not in batched


async def test_empty_input_short_circuits_without_a_round_trip(session) -> None:
    """Empty input costs NO statement — the ``get_dataset_roots`` contract, field for field.

    A composition with no require-tick Strategy is the common case; it must not pay for
    the batch that exists for the uncommon one.
    """
    engine = session.get_bind()
    sync_engine = getattr(engine, "sync_engine", engine)
    seen: list[str] = []

    def _record(_conn, _cursor, statement, _params, _context, _many) -> None:
        seen.append(statement)

    event.listen(sync_engine, "before_cursor_execute", _record)
    try:
        assert await market_repo.find_approved_tick_revisions_for_instruments(session, []) == {}
    finally:
        event.remove(sync_engine, "before_cursor_execute", _record)

    assert seen == []


async def test_duplicate_instruments_collapse_into_one_read(session) -> None:
    """Eleven items on ONE instrument issue one read and resolve to one row.

    ``dict.fromkeys`` de-duplication is part of the mirrored idiom, and it is what keeps
    a composition of same-instrument strategies from re-sending the id eleven times.
    """
    await _root(session, "tick_root_dup")
    await _revision(session, "rev_dup", entity_id="tick_root_dup", instrument_id="INSTR_DUP")
    await session.commit()
    session.expunge_all()

    engine = session.get_bind()
    sync_engine = getattr(engine, "sync_engine", engine)
    seen: list[str] = []

    def _record(_conn, _cursor, statement, _params, _context, _many) -> None:
        seen.append(statement)

    event.listen(sync_engine, "before_cursor_execute", _record)
    try:
        found = await market_repo.find_approved_tick_revisions_for_instruments(
            session, ["INSTR_DUP"] * 11
        )
    finally:
        event.remove(sync_engine, "before_cursor_execute", _record)

    assert len(seen) == 1
    assert found["INSTR_DUP"].revision_id == "rev_dup"
