"""P1: the batched tick-revision reader answers exactly what the per-item probe answers.

``find_approved_tick_revisions_for_instruments`` replaced a per-item N+1 in Ready
Check's tick leg (``_resolve_tick_data_issues``). A batch is only a safe substitution
if it is *indistinguishable* from the loop it replaces, so this module pins the
substitution itself rather than the batch in isolation: every case asserts the batch's
answer against the shipped per-item reader's answer on the same database.

The discriminating cases are the five SQL guards plus the ordering rule. If any guard
is dropped from the batch the map gains an instrument the loop would have called
unavailable, which silently turns a Ready Check BLOCKER into a pass — the exact defect
class this leg exists to raise.
"""

from __future__ import annotations

import pytest

from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.infrastructure.postgres.repositories import market_data as md_repo

pytestmark = pytest.mark.integration


async def _tick(
    session,
    instrument_id: str | None,
    *,
    state: MarketRevisionState = MarketRevisionState.APPROVED,
    data_type: MarketDataType = MarketDataType.TICK_TRADES,
    deleted: bool = False,
):
    """Seed one market dataset revision and return ``(root, revision)``."""
    root, revision = await md_repo.create_market_dataset(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        market_data_type=data_type,
        payload={"kind": "tick"},
        instrument_id=instrument_id,
        revision_state=state,
    )
    revision.instrument_id = instrument_id
    revision.market_data_type = data_type
    revision.revision_state = state
    if deleted:
        root.deletion_state = DeletionState.SOFT_DELETED
    await session.flush()
    return root, revision


async def _assert_parity(session, instrument_ids: list[str]) -> dict[str, object]:
    """The batch must equal the per-item reader for every id, and return the map."""
    batched = await md_repo.find_approved_tick_revisions_for_instruments(session, instrument_ids)
    for instrument_id in instrument_ids:
        one = await md_repo.find_approved_tick_revision_for_instrument(session, instrument_id)
        got = batched.get(instrument_id)
        if one is None:
            assert got is None, f"{instrument_id}: batch invented a revision the probe denies"
        else:
            assert got is not None, f"{instrument_id}: batch dropped a revision the probe finds"
            assert got.revision_id == one.revision_id, (
                f"{instrument_id}: batch picked {got.revision_id}, probe picked {one.revision_id}"
            )
    return batched


async def test_batch_matches_the_probe_across_every_guard(session) -> None:
    """One instrument per guard, all resolved in a single batched call."""
    await _tick(session, "APPROVED_TICK")
    await _tick(session, "DRAFT_TICK", state=MarketRevisionState.DRAFT)
    await _tick(session, "APPROVED_OHLCV", data_type=MarketDataType.OHLCV)
    await _tick(session, "DELETED_ROOT", deleted=True)

    ids = ["APPROVED_TICK", "DRAFT_TICK", "APPROVED_OHLCV", "DELETED_ROOT", "NEVER_SEEDED"]
    batched = await _assert_parity(session, ids)

    # Parity alone would also hold if BOTH readers were broken the same way, so the
    # expected shape is pinned independently: exactly one instrument qualifies.
    assert set(batched) == {"APPROVED_TICK"}


async def test_batch_picks_the_same_winner_when_an_instrument_has_many(session) -> None:
    """``DISTINCT ON`` under the probe's trailing order returns the probe's row."""
    for _ in range(4):
        await _tick(session, "CROWDED")
    # A non-qualifying newest revision must not win, and must not mask the older
    # qualifying one either.
    await _tick(session, "CROWDED", state=MarketRevisionState.DRAFT)

    batched = await _assert_parity(session, ["CROWDED"])
    assert batched["CROWDED"].revision_state == MarketRevisionState.APPROVED


async def test_duplicate_ids_collapse_and_empty_input_short_circuits(session) -> None:
    """Mirrors ``get_dataset_roots`` field for field (the idiom P1 was told to copy)."""
    await _tick(session, "DUPED")

    batched = await md_repo.find_approved_tick_revisions_for_instruments(
        session, ["DUPED", "DUPED", "DUPED"]
    )
    assert set(batched) == {"DUPED"}

    assert await md_repo.find_approved_tick_revisions_for_instruments(session, []) == {}


async def test_a_null_instrument_revision_is_unreachable_by_the_batch(session) -> None:
    """SQL ``NULL IN (...)`` never matches, so a NULL-instrument revision cannot leak.

    The comprehension's ``is not None`` narrowing exists for the type checker; this
    pins that it is narrowing an impossibility rather than hiding a real row.
    """
    await _tick(session, None)
    await _tick(session, "REAL")

    batched = await md_repo.find_approved_tick_revisions_for_instruments(session, ["REAL"])
    assert set(batched) == {"REAL"}
