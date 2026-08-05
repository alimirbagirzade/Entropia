"""The per-tick phase loop — ``run_portfolio`` (ADR 0002 §8, ADIM 18).

Proves the sentence this slice implements and nothing wider: at every valuation point the
mandatory events resolve first, then EXACTLY ONE ``E(t)`` is published, and every active
item forms its intent against that one number — so the outer loop is the merged timestamp
axis rather than the item list, the composite equity curve is time-ordered *by
construction*, and neither the order a caller lists the items in nor the way each item's
bars were chunked can change a single figure.

The four proofs canon names, in one place:

* **doc 13 §14 test 11** — one ``E(t)`` per tick, read by every item; permuting the
  mainboard items yields an identical run digest;
* **removal condition #5** — the curve's instants are strictly increasing without being
  sorted, and the ADR §1.2 fixture's 5000.00 overstatement becomes 3000.00 on one clock;
* **ADR §11** — cross-item batch invariance, which no test covered before this file;
* **ADR §8.1** — nothing writes to the ledger between ``PV`` and ``P7``.

Containment is part of the contract: nothing in production imports the loop, ``run_engine``
is not routed through it, and no shipped digest or ``ENGINE_VERSION`` moves because it
exists. The rollback is still "revert the commit"."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from entropia.domain.backtest import portfolio_engine
from entropia.domain.backtest.execution.arbitration import (
    ArbitrationDecision,
    UnsupportedConflictPolicyError,
)
from entropia.domain.backtest.execution.clock import (
    ClockTick,
    ItemBarStream,
    ItemTickView,
    iter_ticks,
)
from entropia.domain.backtest.execution.costs import FillCosts
from entropia.domain.backtest.execution.intents import (
    ClosingSize,
    EntrySizing,
    ItemDecision,
    ItemIdentity,
    ItemIntent,
    PortfolioSnapshot,
)
from entropia.domain.backtest.execution.portfolio_ledger import (
    LedgerFrozenError,
    OpenPosition,
    PortfolioLedger,
    SleevePlan,
    build_sleeve_plan,
    ledger_for_items,
)
from entropia.domain.backtest.manifest import ENGINE_VERSION
from entropia.domain.backtest.portfolio_engine import (
    PHASE_LOOP_VERSION,
    AppliedFill,
    CashEvent,
    CloseEvent,
    FillEvent,
    IncoherentRunInputsError,
    ItemProposal,
    MandatoryEvent,
    MisdirectedEventError,
    PortfolioRun,
    ScaleBasisNotSuppliedError,
    SnapshotLeakError,
    TickOrderError,
    default_fill,
    run_portfolio,
)
from entropia.domain.strategy.config import StrategyConfig

_ZERO = Decimal("0")
_P0 = Decimal("10000.00")
_COSTS = FillCosts(half_spread=_ZERO, slippage=_ZERO, commission=_ZERO)
_HOURS = [f"2024-01-01T{hour:02d}:00:00Z" for hour in range(6)]


# --------------------------------------------------------------------------- #
# Fixtures — bars, identities, and a scripted driver                           #
# --------------------------------------------------------------------------- #


def _row(timestamp: str, close: str = "100") -> dict[str, Any]:
    price = Decimal(close)
    return {
        "timestamp": timestamp,
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": Decimal("1"),
    }


def _stream(
    item_id: str,
    pin_ordinal: int,
    timestamps: Sequence[str],
    *,
    chunk: int = 0,
) -> ItemBarStream:
    """One item's pinned bar source. ``chunk=0`` means a single batch.

    The chunking is a parameter because it MUST NOT matter: the same instants delivered as
    one batch, as one-row batches, or unevenly, are the same pinned data (ADR §11)."""
    rows = [_row(timestamp) for timestamp in timestamps]
    size = chunk if chunk > 0 else len(rows) or 1
    batches = [rows[index : index + size] for index in range(0, len(rows), size)] or [[]]
    return ItemBarStream(item_id=item_id, pin_ordinal=pin_ordinal, batches=batches)


def _identity(item_id: str, pin_ordinal: int, *, kind: str = "strategy") -> ItemIdentity:
    return ItemIdentity(
        item_id=item_id,
        item_kind=kind,
        pin_ordinal=pin_ordinal,
        root_id=f"root_{item_id}",
        selected_revision_id=f"rev_{item_id}",
        item_label=f"Label {item_id}",
    )


def _config() -> StrategyConfig:
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Phase Loop Fixture",
            "rationale_family_id": "rf_1",
            "data": {
                "instrument_id": "BTCUSDT",
                "market_dataset_root_id": "md_root_1",
                "market_dataset_revision_id": "md_rev_1",
                "market_dataset_content_hash": "mdhash_1",
                "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-12-31T23:59:59Z"},
                "initial_capital": "10000.00",
                "execution": {
                    "entry_timing": "current_candle_close",
                    "exit_timing": "current_candle_close",
                },
                "order_config": {"type": "market_order"},
                "costs": {"slippage_mode": "percentage_slippage", "slippage_value": "0"},
                "intrabar_policy": {"tick_policy": "inherit"},
                "funding": {"enabled": False},
            },
            "position_entry_logic": {
                "direction_mode": "long_and_short",
                "signal_block": {"rule": "required_indicator_blocks_only"},
                "indicator_blocks": [
                    {
                        "block_id": "blk_1",
                        "display_order": 0,
                        "package_ref": {
                            "package_root_id": "pkg_1",
                            "package_revision_id": "pkgrev_1",
                            "package_content_hash": "pkghash_1",
                        },
                        "trigger_source": "indicator_native_trigger",
                        "requirement": "required",
                    }
                ],
            },
            "position_exit_logic": {
                "applies_to_direction": "long_and_short",
                "close_percentage": "100",
            },
            "protection_stop_logic": {
                "percentage_stop": {"enabled": True, "loss_percentage": "1.0"}
            },
            "position_sizing": {"method": "base_position_size", "base_position_size": "50"},
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {},
        }
    )


def _entry(direction: str = "long", base: str = "10000") -> ItemProposal:
    return (
        ItemDecision(kind="entry", direction=direction, reason="entry_signal"),
        EntrySizing(
            config=_config(),
            fill_costs=_COSTS,
            base=Decimal(base),
            base_source="portfolio_equity",
        ),
    )


def _exit_close(units: str = "1") -> ItemDecision:
    return ItemDecision(kind="exit", direction=None, reason="exit_signal")


class ScriptedDriver:
    """A driver whose per-tick facts are stated up front.

    Stands in for the resumable stepper ADR §12 assigns to ADIM 16 and which was never
    written (``engine.py:1782`` is still a monolithic bar loop). It reports facts and
    performs no ledger write — the same contract the real stepper will have, so the phase
    loop under test here is the one that will drive it."""

    def __init__(
        self,
        item_id: str,
        *,
        events: Mapping[str, Sequence[MandatoryEvent]] | None = None,
        proposals: Mapping[str, ItemProposal] | None = None,
        fills: Mapping[str, AppliedFill] | None = None,
        ledger: PortfolioLedger | None = None,
    ) -> None:
        self.item_id = item_id
        self._events = dict(events or {})
        self._proposals = dict(proposals or {})
        self._fills = dict(fills or {})
        self._ledger = ledger
        self.seen_equity: list[tuple[int, Decimal]] = []
        self.seen_sleeve: list[tuple[int, Decimal]] = []
        self.frozen_while_deciding: list[bool] = []
        self.consulted: list[str] = []

    def mandatory(self, view: ItemTickView) -> Sequence[MandatoryEvent]:
        self.consulted.append(f"mandatory@{view.t_ms}")
        return self._events.get(_stamp(view.t_ms), ())

    def propose(self, view: ItemTickView, snapshot: PortfolioSnapshot) -> ItemProposal | None:
        self.consulted.append(f"propose@{view.t_ms}")
        self.seen_equity.append((view.t_ms, snapshot.equity))
        self.seen_sleeve.append((view.t_ms, snapshot.sleeve_capacity[self.item_id]))
        if self._ledger is not None:
            self.frozen_while_deciding.append(self._ledger.is_frozen)
        return self._proposals.get(_stamp(view.t_ms))

    def apply(
        self,
        *,
        grant: ArbitrationDecision,
        intent: ItemIntent,
        held: OpenPosition | None,
    ) -> AppliedFill:
        self.consulted.append(f"apply@{grant.item_id}")
        scripted = self._fills.get(_stamp(intent.t_ms))
        if scripted is not None:
            return scripted
        return default_fill(grant=grant, intent=intent, held=held)


_STAMPS: dict[int, str] = {}


def _stamp(t_ms: int) -> str:
    """The wall-clock label of a tick, so a script can be written in timestamps."""
    return _STAMPS[t_ms]


def _t(hour: int) -> int:
    """The tick key of ``_HOURS[hour]``, registered so ``_stamp`` can invert it."""
    from entropia.domain.backtest.execution.clock import tick_key

    key = tick_key(_HOURS[hour])
    assert key is not None
    _STAMPS[key] = _HOURS[hour]
    return key


for _hour in range(len(_HOURS)):
    _t(_hour)


def _plan(*, compound: bool = True, reserve: str = "0") -> SleevePlan:
    return build_sleeve_plan(
        pool_initial=_P0,
        reserve_percent=Decimal(reserve),
        shares={"item_a": Decimal("50"), "item_b": Decimal("50")},
        compound=compound,
    )


def _seed_fill(size: str = "1", price: str = "100") -> FillEvent:
    return FillEvent(
        item_id="",
        fill=AppliedFill(direction="long", size=Decimal(size), entry_price=Decimal(price)),
    )


def _fill_for(item_id: str, size: str = "1", price: str = "100") -> FillEvent:
    return FillEvent(
        item_id=item_id,
        fill=AppliedFill(direction="long", size=Decimal(size), entry_price=Decimal(price)),
    )


def _close_for(item_id: str, pnl: str) -> CloseEvent:
    return CloseEvent(
        item_id=item_id,
        gross_pnl=Decimal(pnl),
        commission=_ZERO,
        decision=_exit_close(),
        closing=ClosingSize(units=Decimal("1")),
    )


def _run(
    *,
    order: Sequence[str] = ("item_a", "item_b"),
    timestamps: Mapping[str, Sequence[str]] | None = None,
    drivers: Mapping[str, ScriptedDriver],
    ledger: PortfolioLedger | None = None,
    chunk: Mapping[str, int] | None = None,
    instruments: Mapping[str, str | None] | None = None,
    policy: str | None = None,
    **kwargs: Any,
) -> PortfolioRun:
    """Run the loop with the items presented in ``order``.

    ``order`` is the ORDER A CALLER LISTS THEM IN — a UI row order, a DB query order, an
    API arrival order. The pinned ordinal is a property of the manifest and stays fixed, so
    permuting ``order`` must change nothing (doc 13 §13)."""
    ordinals = {"item_a": 0, "item_b": 1}
    stamps = dict(timestamps or {item: list(_HOURS[:5]) for item in ordinals})
    chunks = dict(chunk or {})
    streams = [
        _stream(item, ordinals[item], stamps[item], chunk=chunks.get(item, 0)) for item in order
    ]
    identities = {item: _identity(item, ordinals[item]) for item in order}
    return run_portfolio(
        streams=streams,
        identities=identities,
        drivers={item: drivers[item] for item in order},
        ledger=ledger if ledger is not None else PortfolioLedger(_plan()),
        instruments=instruments,
        policy=policy,
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# doc 13 §14 test 11 — one E(t), and item order cannot change it               #
# --------------------------------------------------------------------------- #


def _interleaved_drivers(ledger: PortfolioLedger | None = None) -> dict[str, ScriptedDriver]:
    """The ADR §1.2 fixture, replayed on one clock.

    Item A moves at 01:00 and 04:00; item B moves BETWEEN them, at 02:00 and 03:00 — the
    exact four closes ``test_composite_portfolio_curve_is_not_time_ordered`` folds in item
    order to reach a 5000.00 drawdown that never happened."""
    return {
        "item_a": ScriptedDriver(
            "item_a",
            events={
                _HOURS[0]: (_fill_for("item_a"),),
                _HOURS[1]: (_close_for("item_a", "3000.00"),),
                _HOURS[4]: (_fill_for("item_a"), _close_for("item_a", "-2000.00")),
            },
            ledger=ledger,
        ),
        "item_b": ScriptedDriver(
            "item_b",
            events={
                _HOURS[0]: (_fill_for("item_b"),),
                _HOURS[2]: (_close_for("item_b", "-3000.00"),),
                _HOURS[3]: (_fill_for("item_b"), _close_for("item_b", "3000.00")),
            },
            ledger=ledger,
        ),
    }


def test_every_item_at_a_tick_reads_exactly_one_published_equity() -> None:
    """doc 13 §8.3 / §14 test 11: *"Ayni timestampteki tum itemler ayni valuation
    snapshotini gorur"* — asserted on what the items actually READ, not on the loop's
    intention."""
    drivers = _interleaved_drivers()
    run = _run(drivers=drivers)

    assert [t for t, _ in drivers["item_a"].seen_equity] == list(run.tick_instants)
    assert drivers["item_a"].seen_equity == drivers["item_b"].seen_equity

    for record in run.ticks:
        identities = {intent.snapshot_identity for intent in record.intents}
        assert identities == {record.snapshot.identity}
        equities = {intent.dependencies["portfolio_equity"] for intent in record.intents}
        assert equities == {record.snapshot.equity}


def test_permuting_the_mainboard_items_yields_an_identical_run() -> None:
    """doc 13 §13: *"UI row sirasi, DOM orderi veya API arrival orderi allocation sonucu
    degistiremez."* One digest comparison, because the run identity covers every published
    valuation, every arbitration outcome and the final book."""
    forward = _run(order=("item_a", "item_b"), drivers=_interleaved_drivers())
    reversed_run = _run(order=("item_b", "item_a"), drivers=_interleaved_drivers())

    assert forward.identity == reversed_run.identity
    assert [point.equity for point in forward.equity_points] == [
        point.equity for point in reversed_run.equity_points
    ]
    assert [record.snapshot.identity for record in forward.ticks] == [
        record.snapshot.identity for record in reversed_run.ticks
    ]
    # The pinned order is what the ledger-writing phases obey, and it is unchanged by the
    # permutation — that is WHY the digests match, and asserting it keeps the test from
    # passing for the wrong reason (e.g. both runs collapsing to one item).
    for record in forward.ticks:
        assert [decision.item_id for decision in record.arbitration.decisions] == [
            "item_a",
            "item_b",
        ]


def test_a_run_with_no_ticks_reports_no_contribution_rather_than_an_empty_one() -> None:
    """An empty report would read as *"no contribution"*, which is a different claim from
    *"there were no valuation points"*."""
    run = _run(
        timestamps={"item_a": [], "item_b": []},
        drivers={"item_a": ScriptedDriver("item_a"), "item_b": ScriptedDriver("item_b")},
    )

    assert run.ticks == ()
    assert run.contribution is None
    assert run.phase_loop_version == PHASE_LOOP_VERSION


# --------------------------------------------------------------------------- #
# Removal condition #5 — the curve is time-ordered BY CONSTRUCTION             #
# --------------------------------------------------------------------------- #


def test_the_composite_curve_is_time_ordered_without_being_sorted() -> None:
    """``capability.py:88-89``. The instants are increasing because the AXIS is; nothing
    in the loop sorts the curve afterwards, and a sorted-looking curve that had to be
    sorted would not prove the property."""
    run = _run(drivers=_interleaved_drivers())

    stamps = [point.t_ms for point in run.equity_points if point.t_ms is not None]
    assert stamps == sorted(stamps)
    assert len(stamps) == len(set(stamps))
    # The seed carries no instant — it is the run's opening balance, not a valuation point.
    assert run.equity_points[0].t_ms is None
    assert run.equity_points[0].equity == _P0


def test_the_adr_fixture_reports_3000_on_one_clock_instead_of_5000() -> None:
    """ADR §1.2 states the defect as a number: folding item A whole and THEN item B walks
    10000 -> 13000 -> 11000 -> 8000 -> 11000 and reports a 5000.00 trough that never
    happened. The SAME four closes on one clock walk 10000 -> 13000 -> 10000 -> 13000 ->
    11000, and the worst drawdown is 3000.00 — a 66 % overstatement removed.

    The shipped containment test still asserts 5000.00 against ``combine_item_runs``, and
    must: this loop is not wired to anything, so that path is unchanged. This is the
    contained proof that the replacement produces the honest figure."""
    run = _run(drivers=_interleaved_drivers())

    walk = [point.equity for point in run.equity_points]
    assert walk == [
        Decimal("10000.00"),
        Decimal("13000.00"),
        Decimal("10000.00"),
        Decimal("13000.00"),
        Decimal("11000.00"),
    ]
    assert max(point.drawdown for point in run.equity_points) == Decimal("3000.00")
    assert run.ledger.equity == Decimal("11000.00")
    assert run.ledger.realized_pnl == Decimal("1000.00")


def test_a_tick_that_moves_nothing_appends_no_point() -> None:
    """ADR §7: ``E(t)`` is realized-only, so a point at every tick would add flat repeats
    and no information. The 00:00 tick opens two positions and realizes nothing."""
    run = _run(drivers=_interleaved_drivers())

    assert run.ticks[0].t_ms == _t(0)
    assert run.ticks[0].equity_point is None
    assert run.ticks[1].equity_point is not None


# --------------------------------------------------------------------------- #
# ADR §11 — cross-item batch invariance (nothing covered this before)          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "chunking",
    [
        {"item_a": 1, "item_b": 1},
        {"item_a": 1, "item_b": 0},
        {"item_a": 2, "item_b": 3},
        {"item_a": 4, "item_b": 1},
    ],
)
def test_cross_item_batch_invariance(chunking: dict[str, int]) -> None:
    """*"the merged axis result must not depend on how each item's bars were chunked"*
    (ADR §11). The chunking is the worker's streaming detail; it is not data."""
    baseline = _run(drivers=_interleaved_drivers())
    chunked = _run(drivers=_interleaved_drivers(), chunk=chunking)

    assert chunked.identity == baseline.identity
    assert chunked.tick_instants == baseline.tick_instants
    assert [point.equity for point in chunked.equity_points] == [
        point.equity for point in baseline.equity_points
    ]


def test_batch_invariance_and_item_order_compose() -> None:
    """The two invariances are independent, so their composition must hold too — the case
    a worker actually produces, where items arrive in some order AND stream in chunks."""
    baseline = _run(drivers=_interleaved_drivers())
    both = _run(
        order=("item_b", "item_a"),
        drivers=_interleaved_drivers(),
        chunk={"item_a": 3, "item_b": 1},
    )

    assert both.identity == baseline.identity


# --------------------------------------------------------------------------- #
# ADR §8.1 — the phase order, enforced at the site                             #
# --------------------------------------------------------------------------- #


class _RecordingLedger(PortfolioLedger):
    """Records the ORDER of the ledger writes a tick performs."""

    __slots__ = ("calls",)

    def __init__(self, plan: SleevePlan) -> None:
        super().__init__(plan)
        self.calls: list[str] = []

    def book_funding(self, item_id: str, *, amount: Decimal) -> Decimal:
        self.calls.append(f"P1:funding:{item_id}")
        return super().book_funding(item_id, amount=amount)

    def set_position(
        self, item_id: str, *, direction: str, size: Decimal, entry_price: Decimal
    ) -> OpenPosition:
        self.calls.append(f"fill:{item_id}")
        return super().set_position(
            item_id, direction=direction, size=size, entry_price=entry_price
        )

    def close_position(self, item_id: str) -> OpenPosition:
        self.calls.append(f"P3:close:{item_id}")
        return super().close_position(item_id)

    def publish_snapshot(self, t_ms: int) -> PortfolioSnapshot:
        self.calls.append(f"PV:{t_ms}")
        return super().publish_snapshot(t_ms)

    def begin_apply(self, t_ms: int) -> None:
        self.calls.append(f"P7:{t_ms}")
        super().begin_apply(t_ms)


def test_exactly_one_snapshot_is_published_per_tick() -> None:
    """ADR §8.1: ``PV`` is *the* single point at which portfolio state is frozen. Two
    publications in a tick would mean two ``E(t)``s, which is the defect restated."""
    ledger = _RecordingLedger(_plan())
    run = _run(drivers=_interleaved_drivers(), ledger=ledger)

    published = [call for call in ledger.calls if call.startswith("PV:")]
    assert published == [f"PV:{t_ms}" for t_ms in run.tick_instants]


def test_the_ledger_is_frozen_while_items_decide_and_reopens_only_to_apply() -> None:
    """Property (i) of ADR §8.1: nothing between ``PV`` and ``P7`` may write, so every
    item provably reads the same ``E(t)``. Checked from inside the decision phase, and
    checked by trying to write."""
    ledger = PortfolioLedger(_plan())
    drivers = _interleaved_drivers(ledger)
    run = _run(drivers=drivers, ledger=ledger)

    assert drivers["item_a"].frozen_while_deciding == [True] * len(run.ticks)
    assert drivers["item_b"].frozen_while_deciding == [True] * len(run.ticks)
    assert not ledger.is_frozen  # reopened by the last tick's P7

    ledger.publish_snapshot(_t(5))
    with pytest.raises(LedgerFrozenError):
        ledger.book_fee("item_a", amount=Decimal("1"))


def test_each_phase_sweeps_every_item_before_the_next_phase_starts() -> None:
    """Modül 12 §9.2 numbers funding (100), scheduled fills (101) and stop/exit (102) as
    three separate clock steps. Item B's funding must therefore be booked before item A's
    close, even though A is pinned first — a per-item sweep would interleave three
    canonical steps into one."""
    ledger = _RecordingLedger(_plan())
    drivers = {
        "item_a": ScriptedDriver(
            "item_a",
            events={
                _HOURS[0]: (_fill_for("item_a"),),
                _HOURS[1]: (_fill_for("item_a"), _close_for("item_a", "100.00")),
            },
        ),
        "item_b": ScriptedDriver(
            "item_b",
            events={
                _HOURS[1]: (
                    CashEvent(item_id="item_b", kind="funding", amount=Decimal("5.00")),
                    _fill_for("item_b"),
                ),
            },
        ),
    }
    _run(drivers=drivers, ledger=ledger, timestamps=dict.fromkeys(drivers, _HOURS[:2]))

    # The fixture is built so the two readings DISAGREE: item A (pinned first) has a P2
    # fill and item B has a P1 funding charge, so a per-item sweep would book A's fill
    # before B's funding. A fixture where they happen to agree would pass either way and
    # prove nothing.
    after_first_apply = ledger.calls[ledger.calls.index(f"P7:{_t(0)}") + 1 :]
    assert after_first_apply[: after_first_apply.index(f"PV:{_t(1)}")] == [
        "P1:funding:item_b",
        "fill:item_a",
        "fill:item_b",
        "P3:close:item_a",
    ]


def test_mandatory_events_move_the_equity_the_snapshot_publishes() -> None:
    """Modül 11 §5.2: the valuation point is the ledger state AFTER the mandatory events.
    A funding charge that landed after ``E(t)`` would let an item size against equity it
    no longer has."""
    drivers = {
        "item_a": ScriptedDriver(
            "item_a",
            events={
                _HOURS[0]: (CashEvent(item_id="item_a", kind="funding", amount=Decimal("40.00")),)
            },
        ),
        "item_b": ScriptedDriver("item_b"),
    }
    run = _run(drivers=drivers, timestamps=dict.fromkeys(drivers, _HOURS[:1]))

    assert run.ticks[0].snapshot.equity == Decimal("9960.00")
    # A(t) = max(0, E(t) - R0) with R0 = 0; each 50 % sleeve is half of it.
    assert run.ticks[0].snapshot.sleeve_capacity["item_b"] == Decimal("4980.00")
    assert drivers["item_b"].seen_equity == [(_t(0), Decimal("9960.00"))]


def test_p3_events_are_traced_as_intents_that_name_no_snapshot() -> None:
    """ADR §6 rules 4 and 5: a mandatory event is resolved before ``E(t)`` exists and is
    still emitted to the trace. A close that booked PnL without appearing anywhere would
    be the silent suppression the contract forbids."""
    run = _run(drivers=_interleaved_drivers())

    closes = [intent for record in run.ticks for intent in record.mandatory_intents]
    assert [intent.item_id for intent in closes] == ["item_a", "item_b", "item_b", "item_a"]
    assert {intent.phase for intent in closes} == {"P3"}
    assert {intent.snapshot_identity for intent in closes} == {None}
    assert {intent.phase for record in run.ticks for intent in record.intents} == {"P4"}


def test_every_item_is_traced_at_every_tick_even_when_it_wants_nothing() -> None:
    """ADR §6 rule 5. Two items, five ticks, ten intents — a silence is a traced ``no_op``
    with its own reason, never an absence."""
    run = _run(drivers=_interleaved_drivers())

    assert sum(len(record.intents) for record in run.ticks) == 2 * len(run.ticks)
    kinds = {intent.kind for record in run.ticks for intent in record.intents}
    assert kinds == {"no_op"}
    assert all(len(record.arbitration.decisions) == 2 for record in run.ticks), (
        "arbitration drops nothing either"
    )


# --------------------------------------------------------------------------- #
# A6 — compound sleeves see a sibling's result; fixed sleeves do not           #
# --------------------------------------------------------------------------- #


def _sibling_loss_drivers() -> dict[str, ScriptedDriver]:
    """Item B loses 2000 at 01:00; item A decides at 02:00."""
    return {
        "item_a": ScriptedDriver("item_a", proposals={_HOURS[2]: _entry()}),
        "item_b": ScriptedDriver(
            "item_b",
            events={
                _HOURS[0]: (_fill_for("item_b"),),
                _HOURS[1]: (_close_for("item_b", "-2000.00"),),
            },
        ),
    }


def test_a_siblings_loss_shrinks_the_next_sleeve_in_compound_mode() -> None:
    """doc 13 §8.3 / §14 test 11 (A6): under ``COMPOUND_PORTFOLIO_EQUITY`` the sleeve is a
    share of ``A(t) = max(0, E(t) - R0)`` computed from the ONE portfolio equity, so item
    B's loss reaches item A. That is the sharing the sequential fold could never do."""
    drivers = _sibling_loss_drivers()
    run = _run(
        drivers=drivers,
        ledger=PortfolioLedger(_plan(compound=True, reserve="10")),
        timestamps=dict.fromkeys(drivers, _HOURS[:3]),
    )

    # R0 = 1000 fixed nominal. Before the loss A(t) = 9000 -> 4500 each; after it
    # E(t) = 8000, A(t) = 7000 -> 3500 each.
    #
    # The shrink lands at 01:00, not at 02:00, and that placement is the canonical order
    # rather than an off-by-one: item B's close is a MANDATORY P3 event resolved before
    # the 01:00 valuation point exists (Modul 11 §5.2), so the very snapshot item A reads
    # at that tick already carries its sibling's loss. Under the sequential fold it could
    # never carry it at all.
    assert drivers["item_a"].seen_sleeve == [
        (_t(0), Decimal("4500.00")),
        (_t(1), Decimal("3500.00")),
        (_t(2), Decimal("3500.00")),
    ]
    assert run.ticks[-1].snapshot.reserve_nominal == Decimal("1000.00")


def test_fixed_mode_holds_the_sleeve_at_its_opening_amount() -> None:
    """Modül 11 §5.3: in fixed mode ``Ci_fixed = A0*wi/100`` and PnL still books to the
    ledger. The sibling's loss is visible in ``E(t)`` and absent from the sleeve — both,
    not one."""
    drivers = _sibling_loss_drivers()
    run = _run(
        drivers=drivers,
        ledger=PortfolioLedger(_plan(compound=False, reserve="10")),
        timestamps=dict.fromkeys(drivers, _HOURS[:3]),
    )

    assert {sleeve for _, sleeve in drivers["item_a"].seen_sleeve} == {Decimal("4500.00")}
    assert run.ticks[-1].snapshot.equity == Decimal("8000.00")


def test_the_reserve_is_never_lent_to_a_sleeve() -> None:
    """doc 13 §0.2 / Modül 11 §1.2.6: ``R0`` is fixed nominal and never re-derived from
    ``E(t)``, so a drawdown shrinks the sleeves rather than the reserve."""
    drivers = {
        "item_a": ScriptedDriver("item_a"),
        "item_b": ScriptedDriver(
            "item_b",
            events={
                _HOURS[0]: (_fill_for("item_b"),),
                _HOURS[1]: (_close_for("item_b", "-9500.00"),),
            },
        ),
    }
    run = _run(
        drivers=drivers,
        ledger=PortfolioLedger(_plan(compound=True, reserve="10")),
        timestamps=dict.fromkeys(drivers, _HOURS[:2]),
    )

    final = run.ticks[-1].snapshot
    assert final.reserve_nominal == Decimal("1000.00")
    assert final.equity == Decimal("500.00")
    assert final.allocatable == _ZERO
    assert set(final.sleeve_capacity.values()) == {_ZERO}


# --------------------------------------------------------------------------- #
# Arbitration through the loop — no share transfer, capacity respected         #
# --------------------------------------------------------------------------- #


def test_a_blocked_items_share_is_never_transferred() -> None:
    """doc 13 §8.4 step 6 / §13 (A9). Two items on the SAME instrument intend opposite
    directions; one is blocked, and the survivor's sleeve is exactly what it was."""
    drivers = {
        "item_a": ScriptedDriver("item_a", proposals={_HOURS[0]: _entry("long")}),
        "item_b": ScriptedDriver("item_b", proposals={_HOURS[0]: _entry("short")}),
    }
    run = _run(
        drivers=drivers,
        instruments={"item_a": "BTCUSDT", "item_b": "BTCUSDT"},
        policy="BLOCK_OPPOSITE",
        timestamps=dict.fromkeys(drivers, _HOURS[:1]),
    )

    report = run.ticks[0].arbitration
    assert report.by_item("item_b").outcome == "blocked"
    assert report.by_item("item_b").counterparty_item_id == "item_a"
    assert report.released_capacity_reallocated is False
    assert run.ticks[0].snapshot.sleeve_capacity["item_a"] == Decimal("5000.00")
    assert "item_b" not in run.ledger.positions


def test_the_run_identity_covers_the_arbitration_outcome() -> None:
    """Two runs whose valuations and equity curve are IDENTICAL, differing only in how the
    conflict resolved, must not share an identity.

    Without this the digest that ``test_permuting_the_mainboard_items_yields_an_identical_run``
    compares would be blind to the decisions it is supposed to be pinning: a permutation
    that changed every outcome and no number would still look invariant."""

    def _pair() -> dict[str, ScriptedDriver]:
        return {
            "item_a": ScriptedDriver("item_a", proposals={_HOURS[0]: _entry("long")}),
            "item_b": ScriptedDriver("item_b", proposals={_HOURS[0]: _entry("short")}),
        }

    shared = {
        "instruments": {"item_a": "BTCUSDT", "item_b": "BTCUSDT"},
        "timestamps": dict.fromkeys(("item_a", "item_b"), _HOURS[:1]),
    }
    blocking = _run(drivers=_pair(), policy="BLOCK_OPPOSITE", **shared)
    separate = _run(drivers=_pair(), policy="KEEP_SEPARATE", **shared)

    # Everything the ledger published is the same — no trade closed, so E(t) never moved.
    assert [record.snapshot.identity for record in blocking.ticks] == [
        record.snapshot.identity for record in separate.ticks
    ]
    assert [point.equity for point in blocking.equity_points] == [
        point.equity for point in separate.equity_points
    ]
    # The outcomes are not, and the identity says so.
    assert blocking.ticks[0].arbitration.by_item("item_b").outcome == "blocked"
    assert separate.ticks[0].arbitration.by_item("item_b").is_admitted
    assert blocking.identity != separate.identity


def test_the_commission_a_fill_pays_is_booked_before_the_position() -> None:
    """One of the five equity-mutation sites of ADR §2 (``booking.py:222`` and the
    stack/ladder commissions). Booking it AFTER the position would let the ledger's
    no-borrow check see capital the fee has already spent."""
    drivers = {
        "item_a": ScriptedDriver(
            "item_a",
            events={
                _HOURS[0]: (
                    FillEvent(
                        item_id="item_a",
                        fill=AppliedFill(
                            direction="long",
                            size=Decimal("1"),
                            entry_price=Decimal("100"),
                            commission=Decimal("7.50"),
                        ),
                    ),
                )
            },
        ),
        "item_b": ScriptedDriver("item_b"),
    }
    run = _run(drivers=drivers, timestamps=dict.fromkeys(drivers, _HOURS[:1]))

    assert run.ledger.fees == Decimal("7.50")
    assert run.ledger.equity == Decimal("9992.50")
    assert run.ticks[0].snapshot.equity == Decimal("9992.50")
    assert run.ticks[0].attribution.by_item("item_a").fees == Decimal("7.50")
    assert run.ledger.accounting_identity == run.ledger.equity


def test_an_unexecutable_conflict_policy_fails_before_the_first_tick() -> None:
    """GH #544: ``NET`` has no canonical semantics. Failing at tick zero rather than after
    an hour of replay is the difference between a refusal and a wasted run."""
    drivers = {"item_a": ScriptedDriver("item_a"), "item_b": ScriptedDriver("item_b")}

    with pytest.raises(UnsupportedConflictPolicyError):
        _run(drivers=drivers, policy="NET")

    assert drivers["item_a"].consulted == []
    assert drivers["item_b"].consulted == []


def test_an_admitted_grant_is_capped_by_the_sleeve_and_applied_at_pinned_order() -> None:
    """doc 13 §14 test 13 (A8): the sleeve caps a size deterministically, and the cap is
    computed against the ONE published snapshot rather than a ledger a sibling has moved."""
    drivers = {
        "item_a": ScriptedDriver("item_a", proposals={_HOURS[0]: _entry("long")}),
        "item_b": ScriptedDriver("item_b", proposals={_HOURS[0]: _entry("long")}),
    }
    run = _run(
        drivers=drivers,
        instruments={"item_a": "BTCUSDT", "item_b": "ETHUSDT"},
        timestamps=dict.fromkeys(drivers, _HOURS[:1]),
    )

    report = run.ticks[0].arbitration
    assert [decision.item_id for decision in report.decisions] == ["item_a", "item_b"]
    for decision in report.decisions:
        assert decision.is_admitted
        assert decision.granted_notional <= Decimal("5000.00")
    assert set(run.ledger.positions) == {"item_a", "item_b"}


# --------------------------------------------------------------------------- #
# Fail closed — never a degraded tick                                          #
# --------------------------------------------------------------------------- #


def test_an_item_without_a_driver_fails_the_run() -> None:
    with pytest.raises(IncoherentRunInputsError, match="no driver"):
        run_portfolio(
            streams=[_stream("item_a", 0, _HOURS[:1]), _stream("item_b", 1, _HOURS[:1])],
            identities={"item_a": _identity("item_a", 0), "item_b": _identity("item_b", 1)},
            drivers={"item_a": ScriptedDriver("item_a")},
            ledger=PortfolioLedger(_plan()),
        )


def test_an_item_with_a_sleeve_but_no_bar_stream_fails_rather_than_idling() -> None:
    """OD-6 is open: whether a non-executing kind may hold a sleeve is a product decision.
    Giving one a silent per-tick presence would answer it here, in a loop."""
    with pytest.raises(IncoherentRunInputsError, match="OD-6"):
        run_portfolio(
            streams=[_stream("item_a", 0, _HOURS[:1])],
            identities={"item_a": _identity("item_a", 0)},
            drivers={"item_a": ScriptedDriver("item_a")},
            ledger=PortfolioLedger(_plan()),
        )


def test_a_driver_cannot_report_an_event_for_another_item() -> None:
    """Booking one item's PnL against another's sleeve is cross-item contamination
    arriving through the mandatory window instead of the intent window."""
    drivers = {
        "item_a": ScriptedDriver("item_a", events={_HOURS[0]: (_fill_for("item_b"),)}),
        "item_b": ScriptedDriver("item_b"),
    }

    with pytest.raises(MisdirectedEventError, match="item_b"):
        _run(drivers=drivers, timestamps=dict.fromkeys(drivers, _HOURS[:1]))


def test_an_unnamed_cash_line_is_refused_rather_than_absorbed() -> None:
    """doc 13 §8.3 counts realized PnL, fees and funding apart; a line that belongs to
    none of them would vanish from the accounting identity."""
    drivers = {
        "item_a": ScriptedDriver(
            "item_a",
            events={_HOURS[0]: (CashEvent(item_id="item_a", kind="rebate", amount=_ZERO),)},
        ),
        "item_b": ScriptedDriver("item_b"),
    }

    with pytest.raises(portfolio_engine.PhaseLoopError, match="rebate"):
        _run(drivers=drivers, timestamps=dict.fromkeys(drivers, _HOURS[:1]))


def test_an_axis_that_does_not_advance_fails_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every "no future data" guarantee downstream rests on a strictly forward axis, so a
    repeated instant is refused rather than producing a curve whose order must be trusted."""

    def _stuck(streams: Sequence[ItemBarStream]) -> Iterator[ClockTick]:
        for tick in iter_ticks(streams):
            yield tick
            yield tick

    monkeypatch.setattr(portfolio_engine, "iter_ticks", _stuck)
    drivers = {"item_a": ScriptedDriver("item_a"), "item_b": ScriptedDriver("item_b")}

    with pytest.raises(TickOrderError, match="strictly forward"):
        _run(drivers=drivers, timestamps=dict.fromkeys(drivers, _HOURS[:2]))


def test_intents_naming_two_valuations_fail_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard's only route is a fabricated intent, which is exactly the smuggling the
    single-snapshot rule exists to close — so that is how it is tested."""
    real = portfolio_engine.form_intents

    def _forked(
        tick: ClockTick,
        snapshot: PortfolioSnapshot,
        identities: Mapping[str, ItemIdentity],
        decisions: Mapping[str, ItemProposal],
    ) -> tuple[ItemIntent, ...]:
        intents = real(tick, snapshot, identities, decisions)
        forged = {**dict(intents[0].dependencies), "snapshot_identity": "another-valuation"}
        return (
            type(intents[0])(
                **{
                    **{
                        field: getattr(intents[0], field)
                        for field in intents[0].__slots__
                        if field != "dependencies"
                    },
                    "dependencies": forged,
                }
            ),
            *intents[1:],
        )

    monkeypatch.setattr(portfolio_engine, "form_intents", _forked)
    drivers = {"item_a": ScriptedDriver("item_a"), "item_b": ScriptedDriver("item_b")}

    with pytest.raises(SnapshotLeakError, match="test 11"):
        _run(drivers=drivers, timestamps=dict.fromkeys(drivers, _HOURS[:1]))


def test_default_fill_refuses_to_invent_a_scale_basis() -> None:
    """The averaging rule for a scale-in is the engine's ladder path. A second
    implementation here would be free to drift from the one that books the trade."""
    drivers = {
        "item_a": ScriptedDriver(
            "item_a",
            events={_HOURS[0]: (_fill_for("item_a"),)},
            proposals={_HOURS[0]: _entry("long")},
        ),
        "item_b": ScriptedDriver("item_b"),
    }

    with pytest.raises(ScaleBasisNotSuppliedError, match="ladder rule"):
        _run(
            drivers=drivers,
            instruments={"item_a": "BTCUSDT", "item_b": "ETHUSDT"},
            timestamps=dict.fromkeys(drivers, _HOURS[:1]),
        )


def test_a_driver_may_supply_the_scale_basis_the_loop_refuses_to_guess() -> None:
    """The refusal is a boundary, not a limitation: an item that knows its ladder rule
    states the resulting position and the loop books it."""
    drivers = {
        "item_a": ScriptedDriver(
            "item_a",
            events={_HOURS[0]: (_fill_for("item_a", size="1", price="100"),)},
            proposals={_HOURS[0]: _entry("long")},
            fills={
                _HOURS[0]: AppliedFill(
                    direction="long", size=Decimal("3"), entry_price=Decimal("100")
                )
            },
        ),
        "item_b": ScriptedDriver("item_b"),
    }
    run = _run(
        drivers=drivers,
        instruments={"item_a": "BTCUSDT", "item_b": "ETHUSDT"},
        timestamps=dict.fromkeys(drivers, _HOURS[:1]),
    )

    assert run.ledger.positions["item_a"].size == Decimal("3")


# --------------------------------------------------------------------------- #
# Attribution and provenance ride on the run, not beside it                    #
# --------------------------------------------------------------------------- #


def test_every_tick_reconciles_the_parts_against_the_whole() -> None:
    """PR #581's identity, now proven per tick rather than once: the per-item realised
    contributions sum to ``E(t) - P0`` exactly, with zero residual."""
    run = _run(drivers=_interleaved_drivers())

    for record in run.ticks:
        assert record.attribution.realized_reconciled
        assert record.attribution.realized_residual == _ZERO
    assert run.contribution is not None
    final = run.contribution.attribution
    assert final.by_item("item_a").net_realized == Decimal("1000.00")
    assert final.by_item("item_b").net_realized == _ZERO


def test_an_open_position_is_reported_unmarked_rather_than_valued_at_zero() -> None:
    """OD-2 is open, so the loop supplies no mark. An unmarkable position is disclosed,
    never imputed."""
    drivers = {
        "item_a": ScriptedDriver("item_a", events={_HOURS[0]: (_fill_for("item_a"),)}),
        "item_b": ScriptedDriver("item_b"),
    }
    run = _run(drivers=drivers, timestamps=dict.fromkeys(drivers, _HOURS[:1]))

    assert run.ticks[0].attribution.unmarked_items == ("item_a",)
    assert run.ticks[0].attribution.unrealized_total is None


def _allocation_provenance() -> Any:
    """The frozen allocation record, built through the shipped derivation.

    Reusing ``validate_allocation`` -> ``allocation_provenance_from_derived`` rather than
    hand-writing amounts is what makes the manifest's cross-check meaningful: the sleeves
    it compares against ``run.ledger.plan`` come from the same rules the readiness gate
    runs, so a divergence would be a real one."""
    from entropia.domain.allocation.config import PortfolioAllocationConfigV1
    from entropia.domain.allocation.rules import AllocationItemRef, validate_allocation
    from entropia.domain.backtest.execution.provenance import allocation_provenance_from_derived

    config = PortfolioAllocationConfigV1.model_validate(
        {
            "enabled": True,
            "initial_capital": {"amount": "10000.00", "currency": "USDT"},
            "compounding_mode": "COMPOUND_PORTFOLIO_EQUITY",
            "reserve_cash_percent": "0",
            "entries": [
                {
                    "composition_item_id": item,
                    "item_type": "STRATEGY",
                    "active": True,
                    "equity_share_percent": "50.00",
                }
                for item in ("item_a", "item_b")
            ],
        }
    )
    refs = {
        entry.composition_item_id: AllocationItemRef(
            kind=entry.item_type, available=True, settlement_currency="USDT"
        )
        for entry in config.entries
    }
    _issues, derived = validate_allocation(config, item_refs=refs)
    assert derived is not None
    return allocation_provenance_from_derived(
        derived.as_dict(),
        plan_id="pal_1",
        plan_revision_id="palr_1",
        config_hash="cfg_hash",
        compounding_mode="COMPOUND_PORTFOLIO_EQUITY",
        item_revision_ids={"item_a": "rev_item_a", "item_b": "rev_item_b"},
        fx_refs=(),
    )


def test_the_manifest_section_describes_the_run_that_executed() -> None:
    """ADR §10.2 records R-1: a manifest that names a revision while describing something
    else. The adapter reads the instants, the curve and the plan from the RUN, and the
    frozen sleeve amounts are cross-checked against the plan that actually executed."""
    run = _run(drivers=_interleaved_drivers())
    manifest = portfolio_engine.portfolio_manifest_for(
        run,
        engine_version=ENGINE_VERSION,
        allocation=_allocation_provenance(),
        identities=[_identity("item_a", 0), _identity("item_b", 1)],
    )

    assert manifest.tick_count == len(run.ticks)
    assert manifest.first_t_ms == run.tick_instants[0]
    assert manifest.last_t_ms == run.tick_instants[-1]
    assert manifest.ledger_artifact is not None
    assert manifest.engine_version == ENGINE_VERSION
    # The plan the loop executed and the amounts the allocation froze agree, so a
    # divergence reported later would be a real one rather than fixture drift.
    assert manifest.divergences == ()


# --------------------------------------------------------------------------- #
# Containment — the rollback stays "revert the commit"                         #
# --------------------------------------------------------------------------- #


def test_nothing_imports_the_phase_loop() -> None:
    """ADR §12: no step lifts containment except ADIM 20. ``run_engine`` keeps its
    signature AND its semantics (§3.2), the worker still runs its item loop, and this
    module is reachable from no production path — which is why all 46 golden digests and
    ``ENGINE_VERSION`` are untouched by this slice."""
    src = Path(__file__).resolve().parents[2] / "src" / "entropia"
    importers = sorted(
        path.relative_to(src).as_posix()
        for path in src.rglob("*.py")
        if path.name != "portfolio_engine.py"
        and "backtest.portfolio_engine" in path.read_text(encoding="utf-8")
    )

    assert importers == []


def test_the_worker_still_loops_over_items() -> None:
    """The other half of the same claim, asserted on the file that would have to change:
    ``run_portfolio`` is not called from the worker, so no multi-item composition — shared
    or independent — has changed behaviour."""
    worker = (
        Path(__file__).resolve().parents[2] / "src/entropia/application/jobs/backtest_engine.py"
    ).read_text(encoding="utf-8")

    assert "run_portfolio" not in worker
    assert "for prepared in prepared_items:" in worker
    assert "combine_item_runs" in worker


def test_no_phase_loop_field_ships_in_the_manifest_yet() -> None:
    """ADR §10.3 places the policy-version fields in ADIM 20, together with the
    ``ENGINE_VERSION`` bump they must land with. No namespace may shift here."""
    manifest_src = (
        Path(__file__).resolve().parents[2] / "src/entropia/domain/backtest/manifest.py"
    ).read_text(encoding="utf-8")

    assert ENGINE_VERSION == "backtest-engine-v18-gap-adjusted-stop-fill"
    assert PHASE_LOOP_VERSION not in manifest_src
    for field in ("clock_policy_version", "arbitration_policy_version", "phase_loop_version"):
        assert field not in manifest_src


def test_shared_mode_is_still_failed_closed() -> None:
    """ADR §11: the one-constant rollback must stay intact until ADIM 20."""
    from entropia.domain.allocation.capability import SHARED_ALLOCATION_STATUS

    assert SHARED_ALLOCATION_STATUS == "future_dev"


def test_the_ledger_factory_is_reused_rather_than_reimplemented() -> None:
    """``ledger_for_items`` is ADIM 17's one-call constructor, described there as the one
    the phase loop will use. A second construction path would be a second place for the
    reserve arithmetic to live."""
    ledger = ledger_for_items(
        pool_initial=_P0,
        reserve_percent=Decimal("10"),
        shares={"item_a": Decimal("50"), "item_b": Decimal("50")},
        compound=True,
    )
    run = _run(drivers=_interleaved_drivers(), ledger=ledger)

    assert run.ledger is ledger
    assert run.ticks[0].snapshot.reserve_nominal == Decimal("1000.00")
