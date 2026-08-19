"""The `C3` adapter's two invariants — P-C2 §C.3.3 (reconciliation) and §C.3.5 (sleeve parity).

``domain/backtest/participant.py`` puts the SHIPPED bar replay behind the phase loop's
``ItemParticipant``, which means every item keeps its own ``_Ledger`` while the shared
``PortfolioLedger`` books the same money. That dual booking is deliberate — it is what keeps
stop ladders, ``bars_seen``, trade rows and the decision trace behaving exactly as in a
single-item run, so the item's arithmetic stays comparable to the recorded goldens — and it is
the design's central trade-off. Two books can drift. These two oracles are what make the
arrangement safe rather than lucky.

Everything here runs the REAL engine: ``_build_stepper`` over real bars, a real
``sma_entry_plan``, real per-fill commission, driven by the shipped phase loop. No figure
below is computed by this module; each is read off one of the two ledgers and compared with
the other.

WHY THESE TWO, AND NOT A DIGEST
-------------------------------
A golden digest cannot see either defect. The adapter has no production caller (E5/`C4` is the
wiring, and ``SHARED_ALLOCATION_STATUS`` is still ``future_dev``), so no recorded Result moves
whatever this module proves. What CAN be observed is the shape of the seam:

* **Reconciliation.** ``ItemAttribution.net_contribution`` is accumulated by the pool out of
  four separately-attributed buckets, each quantized by ``PortfolioLedger._apply``; the item's
  ``led.equity`` is accumulated by ``booking.close_position`` and ``engine._book_carry``, each
  with its own quantization. They agree only if EVERY phase that moved the item's book was
  mirrored into the pool. A phase with no channel — a P2 deferred fill, a P8 scale layer, a
  tail-booked opposite-signal close — makes them disagree, which is exactly the class of
  silent wrongness a composite ``E(t)`` cannot disclose.
* **Sleeve parity.** ``Ci(t)`` is derived TWICE: by the engine from the injected ``E(t)``
  (``sizing.sleeve_capital``, reached through ``planned_size``) and by the pool as
  ``snapshot.sleeve_capacity[item_id]`` (``SleevePlan.sleeve_capacity``), which is what
  ``arbitrate`` caps against. P-C2 calls this seam #7 the weakest link in the design. They
  *should* agree — both read ``P0``, ``r`` and ``wi`` off the same frozen plan — and the
  assertion is what turns *should* into *does*.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest

from entropia.domain.backtest.engine import AllocationExecution, _build_stepper
from entropia.domain.backtest.execution.clock import ItemBarStream
from entropia.domain.backtest.execution.intents import ItemIdentity
from entropia.domain.backtest.execution.sizing import sleeve_capital
from entropia.domain.backtest.participant import (
    UnmirroredItemBookingError,
    _EngineParticipant,
)
from entropia.domain.backtest.portfolio_engine import PortfolioRun, run_portfolio
from entropia.domain.strategy.config import StrategyConfig
from tests.unit.engine_signal_plan import sma_entry_plan
from tests.unit.test_backtest_engine_allocation import _bar, _flat
from tests.unit.test_backtest_engine_allocation import _config as _base_config

_P0 = Decimal("10000.00")
_RESERVE_PERCENT = Decimal("10")
_COMMISSION = Decimal("5")
_ZERO = Decimal("0")
#: ``wi`` per item — deliberately unequal, so a sleeve computed with the wrong share cannot
#: coincide with the right one.
_SHARES: dict[str, Decimal] = {"item_a": Decimal("60"), "item_b": Decimal("30")}


def _config(*, commission: str, base_size: str = "1000000") -> StrategyConfig:
    """The canonical allocation fixture with ONE field patched.

    Re-validated from the shipped fixture's own dump rather than hand-written again: a second
    literal config would be a second reading of the schema, free to drift from the one every
    other allocation oracle runs against."""
    raw: dict[str, Any] = _base_config(base_size=base_size).model_dump(mode="python")
    raw["data"]["costs"]["commission"] = Decimal(commission)
    return StrategyConfig.model_validate(raw)


def _shift(bars: list[dict[str, Any]], hours: int) -> list[dict[str, Any]]:
    """The same bars on a DIFFERENT instant grid, so the merged axis genuinely interleaves.

    Two items sharing one timestamp set would exercise the loop with every item deciding at
    every tick, which is the easy case: it never produces a tick where one item is silent
    while its position is still in ``E(t)``."""
    return [dict(bar, timestamp=bar["timestamp"].replace("T00:", f"T{hours:02d}:")) for bar in bars]


def _two_trades() -> list[dict[str, Any]]:
    """20 flat warmup bars, a breakout entry, a losing exit, a second entry held to the end.

    Chosen so the run reaches every hook the adapter implements: P1 (no funding here, but the
    phase runs), P3 (the exit signal closes the first lot), P4/P7 (two admitted entries) and
    P10 (the second lot is still open at end of data)."""
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "90", "100", "90", "100"))  # breakout -> long @100
    bars.append(_bar("2024-01-22T00:00:00Z", "100", "100", "80", "80"))  # exit @80 (a loss)
    bars.append(_bar("2024-01-23T00:00:00Z", "80", "105", "80", "105"))  # breakout -> long @105
    bars.append(_bar("2024-01-24T00:00:00Z", "105", "115", "105", "115"))  # still open at EOD
    return bars


def _batches(bars: list[dict[str, Any]], size: int = 8) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(bars), size):
        yield bars[start : start + size]


def _participant(
    item_id: str,
    pin_ordinal: int,
    bars: list[dict[str, Any]],
    *,
    commission: str = "5",
    compound: bool = True,
) -> _EngineParticipant:
    """One item: the shipped stepper, its pinned bar stream, and the adapter over both."""
    allocation = AllocationExecution(
        initial_capital=_P0,
        reserve_percent=_RESERVE_PERCENT,
        compound=compound,
        item_share_percent=_SHARES[item_id],
        currency="USD",
    )
    stepper = _build_stepper(
        strategy_config=_config(commission=commission),
        execution_key="exec_key_participant",
        item_count=len(_SHARES),
        indicator_plan=sma_entry_plan(),
        allocation=allocation,
    )
    return _EngineParticipant(
        identity=ItemIdentity(item_id=item_id, item_kind="strategy", pin_ordinal=pin_ordinal),
        stream=ItemBarStream(item_id=item_id, pin_ordinal=pin_ordinal, batches=_batches(bars)),
        stepper=stepper,
        instrument_id=f"INSTR_{item_id}",
    )


def _run(
    participants: list[_EngineParticipant], *, compound: bool = True
) -> tuple[PortfolioRun, list[_EngineParticipant]]:
    run = run_portfolio(
        participants,
        pool_initial=_P0,
        shares=dict(_SHARES),
        reserve_percent=_RESERVE_PERCENT,
        compound=compound,
    )
    return run, participants


def _two_item_run(
    *, commission: str = "5", compound: bool = True
) -> tuple[PortfolioRun, list[_EngineParticipant]]:
    """The two-item fixture both invariants are asserted on."""
    return _run(
        [
            _participant("item_a", 0, _two_trades(), commission=commission, compound=compound),
            _participant(
                "item_b", 1, _shift(_two_trades(), 12), commission=commission, compound=compound
            ),
        ],
        compound=compound,
    )


# --------------------------------------------------------------------------------------- #
# The fixture is load-bearing: assert it actually exercises the seam                        #
# --------------------------------------------------------------------------------------- #


def test_the_fixture_actually_trades_on_a_merged_and_interleaved_axis() -> None:
    """Neither invariant means anything on a run where nothing happened.

    A fixture that opened no position would satisfy reconciliation trivially (both books at
    zero) and sleeve parity vacuously (no sizing ever ran). This pins that the run reaches
    both items, opens and closes real lots through arbitration, pays real commission, and
    walks a genuinely INTERLEAVED axis where each tick has exactly one deciding item."""
    run, participants = _two_item_run()

    assert len(run.ticks) == 2 * 24  # both items' bars, no instant shared
    assert all(len([view for view in tick.views if view.is_decision]) == 1 for tick in run.ticks), (
        "the two items share an instant; the axis is not interleaved"
    )

    for participant in participants:
        led = participant.stepper.ledger
        assert len(led.trades) >= 1, "the item never closed a lot"
        assert participant.stepper.ctx.fill_costs.commission == _COMMISSION

    admitted = [d for tick in run.ticks for d in tick.report.decisions if d.is_admitted]
    assert len(admitted) == 4, "two entries per item should have been admitted"
    assert {d.item_id for d in admitted} == set(_SHARES)
    # P10 closed the still-open second lot for BOTH items, so the finalize path ran.
    assert {close.item_id for close in run.final_closes} == set(_SHARES)


# --------------------------------------------------------------------------------------- #
# Invariant 1 — reconciliation (P-C2 §C.3.3)                                                #
# --------------------------------------------------------------------------------------- #


def test_the_pools_attribution_equals_each_items_own_realized_movement() -> None:
    """RECONCILIATION — the invariant that makes dual booking safe.

    ``net_contribution`` is ``realized_pnl - fees - funding - other_costs``, accumulated by
    the pool one booking at a time; ``led.equity - P0`` is the item's own book, accumulated by
    the engine. Under allocation ``_build_stepper`` seeds the item ledger with the shared pool
    P0 (not the sleeve), so the two are directly comparable with no conversion — and no figure
    on either side is recomputed here.

    Equality across BOTH items is the real assertion: a mirror that dropped one item's money
    would still balance the pool's own accounting identity, because the identity is a property
    of the ledger's four buckets and says nothing about which item earned them."""
    run, participants = _two_item_run()

    for participant in participants:
        item_id = participant.identity.item_id
        assert run.ledger.attribution[item_id].net_contribution == (
            participant.stepper.ledger.equity - _P0
        ), f"item '{item_id}' booked money the shared ledger never saw"

    # And the pool is internally consistent, so the equality above is not comparing against a
    # book that has itself drifted.
    assert run.ledger.accounting_identity == run.ledger.equity
    # E(t) moved by exactly the sum of what the two items realized.
    assert run.ledger.equity - _P0 == sum(
        (p.stepper.ledger.equity - _P0 for p in participants), _ZERO
    )


def test_every_per_fill_commission_reaches_the_pool_even_though_P7_has_no_fee_channel() -> None:
    """The one deferral, pinned as a bound rather than trusted as a narrative.

    Commission is PER FILL (#552 / PD-2), so an admitted entry charges the ITEM's ledger
    inside ``settle`` — at P7, where ``ItemParticipant`` returns ``None`` and the loop books
    only the position. The adapter carries that charge and reports it at the item's next P1
    (or folds it into the P10 close). This asserts both halves: nothing is outstanding once
    the run ends, and the pool's ``fees`` bucket carries every fill's commission.

    Four fills per item — two entries and two closes (an exit signal and the P10 close) — at
    a flat ``commission`` each. The count is derived from the two books, never assumed: it is
    the lots the item recorded plus the entries the pool admitted."""
    run, participants = _two_item_run()

    for participant in participants:
        item_id = participant.identity.item_id
        assert participant.deferred_entry_fee == _ZERO, "an entry fee never reached the pool"
        assert participant.unreported_equity == _ZERO

        entries = sum(
            1
            for tick in run.ticks
            for d in tick.report.decisions
            if d.item_id == item_id and d.is_admitted
        )
        fills = entries + len(participant.stepper.ledger.trades)
        assert run.ledger.attribution[item_id].fees == _COMMISSION * fills


def test_reconciliation_holds_with_a_fixed_sleeve_and_with_no_commission_at_all() -> None:
    """The invariant is not an artefact of the compound/commission fixture.

    Fixed sleeves take a different branch in BOTH derivations (the engine's
    ``ctx.allocatable_initial`` and the plan's ``initial_sleeves``), and a zero commission
    removes the deferral path entirely — so this reruns the equality on the two configurations
    where a mirror bug would hide behind a coincidence."""
    for commission, compound in (("0", True), ("5", False), ("0", False)):
        run, participants = _two_item_run(commission=commission, compound=compound)
        for participant in participants:
            assert run.ledger.attribution[participant.identity.item_id].net_contribution == (
                participant.stepper.ledger.equity - _P0
            ), f"commission={commission} compound={compound}"


# --------------------------------------------------------------------------------------- #
# Invariant 2 — sleeve parity (P-C2 §C.3.5, seam #7)                                        #
# --------------------------------------------------------------------------------------- #


def test_the_engines_sleeve_and_the_pools_sleeve_agree_at_every_tick_for_every_item() -> None:
    """SLEEVE PARITY — ``Ci(t)`` derived twice, asserted equal at every valuation point.

    The engine reaches ``sleeve_capital(ctx, E(t))`` through ``planned_size`` when it sizes an
    entry; the pool publishes ``snapshot.sleeve_capacity[item_id]``, which is what ``arbitrate``
    caps the grant against. A divergence means the item sized against a capacity the pool never
    granted — precisely the cross-item contamination the shared snapshot exists to remove.

    Asserted at EVERY tick and for EVERY item, not only at the ticks where an entry was
    formed: the capacity is republished each tick, so a divergence that only appeared on a
    silent tick would still be the pool's answer the next time an item asked."""
    run, participants = _two_item_run()
    by_id = {p.identity.item_id: p for p in participants}
    assert len(run.ticks) > 0

    checked = 0
    for tick in run.ticks:
        for item_id, participant in by_id.items():
            assert (
                sleeve_capital(participant.stepper.ctx, tick.snapshot.equity)
                == tick.snapshot.sleeve_capacity[item_id]
            ), f"item '{item_id}' and the pool disagree about Ci(t) at t_ms={tick.t_ms}"
            checked += 1
    assert checked == len(run.ticks) * len(_SHARES)

    # Non-vacuous: E(t) actually MOVED during the run, so the compound branch was exercised
    # rather than every comparison being made against the opening pool.
    assert len({tick.snapshot.equity for tick in run.ticks}) > 1


def test_sleeve_parity_also_holds_when_the_sleeve_is_fixed() -> None:
    """The fixed branch is a different expression on both sides — engine
    ``ctx.allocatable_initial`` vs plan ``initial_sleeves`` — so it is asserted separately."""
    run, participants = _two_item_run(compound=False)
    by_id = {p.identity.item_id: p for p in participants}

    for tick in run.ticks:
        for item_id, participant in by_id.items():
            assert (
                sleeve_capital(participant.stepper.ctx, tick.snapshot.equity)
                == tick.snapshot.sleeve_capacity[item_id]
            )


# --------------------------------------------------------------------------------------- #
# The adapter refuses rather than degrades                                                  #
# --------------------------------------------------------------------------------------- #


def test_an_item_booking_a_phase_the_loop_cannot_receive_stops_the_run() -> None:
    """The money-parity guard is derived, so it needs no list of unsupported settings.

    Simulated by moving the item's own ledger behind the adapter's back — which is exactly
    what a P2 deferred fill, a P8 scale layer or a tail-booked opposite-signal close do: they
    change ``led.equity`` in a phase that has no channel to the pool. The run must stop; the
    alternative is a composite ``E(t)`` quietly missing that money, with no warning, no flag
    and no version bump to make it visible."""
    participant = _participant("item_a", 0, _two_trades())
    participant.stepper.ledger.equity -= Decimal("13.00")

    with pytest.raises(UnmirroredItemBookingError, match="no phase to report it through"):
        run_portfolio(
            [participant],
            pool_initial=_P0,
            shares={"item_a": _SHARES["item_a"]},
            reserve_percent=_RESERVE_PERCENT,
        )


def test_the_item_books_what_the_pool_GRANTED_not_what_it_wanted() -> None:
    """ADR §6 clause 6 — the P7 grant is the size, and it is not the item's own answer.

    Set up so the two derivations genuinely DISAGREE: an item risk limit
    (``max_position_notional``) lives at Modül 11 §6.1 layer 3, above the allocation sleeve,
    and the replayed engine knows nothing about it — ``planned_size`` caps at the sleeve and
    stops. So the item would size itself larger than the pool admits, and only the granted
    figure reaching ``_open``'s ``size_override`` keeps the two books holding one position.

    Compared against the engine's OWN answer for the same tick, read off the identical run
    with the limit removed: without the override the item would open that larger size against
    a pool that booked the smaller one, and every later stop level, exit notional and realized
    PnL would be arithmetic nobody arbitrated. The size is read from the item's ``entry_fill``
    trace event, which records what ``_open`` actually opened — not from a figure this test
    recomputed."""
    cap = Decimal("500.00")
    capped = _participant("item_a", 0, _two_trades())
    capped_run = run_portfolio(
        [capped],
        pool_initial=_P0,
        shares={"item_a": _SHARES["item_a"]},
        reserve_percent=_RESERVE_PERCENT,
        max_position_notional={"item_a": cap},
    )
    uncapped = _participant("item_a", 0, _two_trades())
    run_portfolio(
        [uncapped],
        pool_initial=_P0,
        shares={"item_a": _SHARES["item_a"]},
        reserve_percent=_RESERVE_PERCENT,
    )

    granted = [
        d
        for tick in capped_run.ticks
        for d in tick.report.decisions
        if d.is_admitted and d.granted_units > _ZERO
    ]
    assert granted, "the item risk limit blocked every entry; nothing was granted to book"
    assert all(d.granted_units < d.requested_units for d in granted), "the cap never bound"

    booked = _fill_sizes(capped)
    assert booked == [d.granted_units for d in granted], (
        "the item opened a size the pool did not grant"
    )
    # And that size is genuinely NOT what the item would have chosen for itself: the same
    # ticks in the uncapped run opened strictly more, so the assertion above cannot be
    # satisfied by an implementation that ignores the override.
    own = _fill_sizes(uncapped)
    assert len(own) == len(booked)
    assert all(mine > theirs for mine, theirs in zip(own, booked, strict=True))


def _fill_sizes(participant: _EngineParticipant) -> list[Decimal]:
    """Every size ``_open`` actually opened, from the item's own F-10 execution trace."""
    return [
        Decimal(event.detail["size"])
        for event in participant.stepper.ledger.signal_events
        if event.event_type == "entry_fill"
    ]
