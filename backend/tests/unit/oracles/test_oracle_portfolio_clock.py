"""Unified-clock portfolio oracles — the CLOCK half: one valuation per tick, and time.

Scope this file adds over the 216 unit tests already covering the six unified-clock modules:
those are all single-tick or single-module. Nothing yet runs a MULTI-TICK, MULTI-ITEM
portfolio through clock -> intents -> ledger -> arbitration together, which is where the
defect ``allocation/capability.py`` contains actually lives — a curve folded per item rather
than walked per timestamp. These oracles walk it.

Every expected number below is hand-derived from doc 13 §8.3/§8.4/§13 and ADR 0002 §7/§8 and
written as a literal. Nothing here calls an engine arithmetic helper to build an expectation.

Since ADIM 18 these oracles drive the SHIPPED phase loop
(``domain/backtest/portfolio_engine.py::run_portfolio``) — they were carried over unchanged
across that substitution, which is the acceptance evidence ADR §14 asks for. Read
``portfolio_harness`` §"WHAT MOVED AT ADIM 18" for what is still fixture-owned (the per-item
DECISIONS) and for the remaining gap (the worker still folds per-item runs).
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.execution.intents import (
    ItemDecision,
    PortfolioSnapshot,
    form_intents,
)

from .portfolio_harness import ScriptedItem, simulate

_HOURS = [f"2024-01-01T{h:02d}:00:00Z" for h in range(6)]


def _interleaved_pair() -> list[ScriptedItem]:
    """The containment fixture's four closes, as two items whose trades INTERLEAVE.

    Item A realises +3000 at 01:00 and -2000 at 04:00; item B realises -3000 at 02:00 and
    +3000 at 03:00 — B's moves fall BETWEEN A's. This is the exact trade set
    ``test_shared_allocation_containment.py::test_composite_portfolio_curve_is_not_time_ordered``
    folds sequentially, where it reports ``max_drawdown == 5000.00``."""
    bars = [(h, "100") for h in _HOURS[:5]]
    return [
        ScriptedItem(
            item_id="a",
            share="50",
            bars=bars,
            entries={_HOURS[0]: ("long", "30"), _HOURS[2]: ("long", "30")},
            exits={_HOURS[1]: "3000.00", _HOURS[4]: "-2000.00"},
        ),
        ScriptedItem(
            item_id="b",
            share="50",
            bars=bars,
            entries={_HOURS[0]: ("long", "30"), _HOURS[2]: ("long", "30")},
            exits={_HOURS[2]: "-3000.00", _HOURS[3]: "3000.00"},
        ),
    ]


def test_the_unified_clock_reports_the_drawdown_the_sequential_fold_overstated() -> None:
    """The headline acceptance number (ADR §14 A5, removal condition #5).

    Walking the SAME four closes on one merged axis:
    ``10000 -> 13000 (01:00) -> 10000 (02:00) -> 13000 (03:00) -> 11000 (04:00)``.
    The worst trough from the 13000 peak is 3000, and the later 13000 -> 11000 leg is only
    2000. The sequential fold replays item A whole and THEN item B
    (``10000 -> 13000 -> 11000 -> 8000 -> 11000``) and measures 5000 from the same peak — a
    66% overstatement of a number the user reads as the portfolio's drawdown."""
    run = simulate(_interleaved_pair(), pool="10000")

    assert [str(p.equity) for p in run.dated_points] == [
        "13000.00",
        "10000.00",
        "13000.00",
        "11000.00",
    ]
    assert run.max_drawdown == Decimal("3000.00")


def test_the_curve_is_time_ordered_by_construction_across_a_whole_run() -> None:
    """Not "sorted afterwards" — the axis IS the loop, so an out-of-order point cannot be
    constructed (doc 13 §8.3, ADR §7). The sequential fold's stamps run 01:00, 04:00, 02:00,
    03:00; these run monotonically because the outer loop is the merged timestamp axis."""
    run = simulate(_interleaved_pair(), pool="10000")

    instants = run.instants
    assert list(instants) == sorted(instants)
    assert len(set(instants)) == len(instants)
    # One point per tick at which E(t) moved, and never two for one instant.
    assert [r.t_ms for r in run.ticks if r.equity_point is not None] == list(instants)


def test_every_item_at_a_tick_sizes_against_exactly_one_published_valuation() -> None:
    """doc 13 §14 test 11 / ADR §14 A3. Both items' intents and the arbitration report that
    judged them all name the SAME snapshot identity — the structural form of "one E(t)"."""
    run = simulate(_interleaved_pair(), pool="10000")

    contended = [r for r in run.ticks if len(r.intents) > 1]
    assert contended, "fixture never put two items on one tick — it proves nothing"
    for record in contended:
        identities = {intent.snapshot_identity for intent in record.intents}
        assert identities == {record.snapshot.identity}
        assert record.report.snapshot_identity == record.snapshot.identity
        assert record.snapshot.t_ms == record.t_ms


def test_a_stop_that_fires_at_a_tick_shrinks_its_siblings_sleeve_at_that_same_tick() -> None:
    """The mandatory-before-valuation rule, priced (ADR §8.2 P1-P3 then PV; doc 13 §8.4/3).

    P0=10000, reserve 10% -> R0=1000, A0=9000, 50/50 -> Ci0=4500 each.
    Item B's stop realises -2000 at 01:00. Because P3 runs BEFORE PV, the valuation item A
    sizes against at 01:00 is E=8000, so A(t)=7000 and Ci=3500 — not the 4500 A would have
    seen had the stop been resolved after the snapshot. A asks for 50 units at 100 (5000)
    and is capped to 35."""
    bars = [(h, "100") for h in _HOURS[:3]]
    items = [
        ScriptedItem(item_id="a", share="50", bars=bars, entries={_HOURS[1]: ("long", "50")}),
        ScriptedItem(
            item_id="b",
            share="50",
            bars=bars,
            entries={_HOURS[0]: ("long", "20")},
            exits={_HOURS[1]: "-2000.00"},
        ),
    ]
    run = simulate(items, pool="10000", reserve_percent="10")

    at_open = run.tick_at(_HOURS[0])
    assert at_open.snapshot.sleeve_capacity["a"] == Decimal("4500.00")

    at_stop = run.tick_at(_HOURS[1])
    assert len(at_stop.mandatory) == 1
    assert at_stop.mandatory[0].phase == "P3"
    assert at_stop.mandatory[0].snapshot_identity is None
    assert at_stop.snapshot.equity == Decimal("8000.00")
    assert at_stop.snapshot.allocatable == Decimal("7000.00")
    assert at_stop.snapshot.sleeve_capacity["a"] == Decimal("3500.00")
    assert at_stop.report.by_item("a").granted_units == Decimal("35")


def test_no_view_at_any_tick_of_a_whole_run_carries_data_from_the_future() -> None:
    """No-lookahead, asserted over the run rather than one axis (doc 15 §9.3, ADR §4).

    At every tick every item's cursor sits at-or-before ``t``, including the items that had
    no bar at that instant — a merged axis must not let a sibling's clock pull an item's
    data forward."""
    bars_a = [(h, "100") for h in _HOURS[:5]]
    bars_b = [(_HOURS[0], "100"), (_HOURS[3], "100")]
    items = [
        ScriptedItem(item_id="a", share="50", bars=bars_a),
        ScriptedItem(item_id="b", share="50", bars=bars_b),
    ]
    run = simulate(items, pool="10000")

    assert [r.t_ms for r in run.ticks] == sorted(r.t_ms for r in run.ticks)
    assert len(run.ticks) == 5  # the union of both axes, deduplicated

    for record in run.ticks:
        assert {view.item_id for view in record.views} == {"a", "b"}
        for view in record.views:
            # Nothing the item can read is dated after the instant being valued.
            for bar in view.bars:
                assert bar.timestamp == record.timestamp
            if view.last_closed_t_ms is not None:
                assert view.last_closed_t_ms <= record.t_ms
            # An item with no fresh bar is present but cannot decide (doc 13 §8.4/4).
            if not view.bars:
                assert view.is_decision is False

    # B's second bar is at 03:00, so at 02:00 its cursor must still sit at 00:00 — a merged
    # axis must not let A's clock pull B's data forward.
    at_two = run.tick_at(_HOURS[2])
    b_view = next(v for v in at_two.views if v.item_id == "b")
    assert b_view.bars == ()
    assert b_view.last_closed is not None
    assert b_view.last_closed.timestamp == _HOURS[0]


def test_a_sparser_item_competes_for_capital_only_at_its_own_decision_times() -> None:
    """Heterogeneous timeframes contending for ONE pool — the combination no existing test
    covers (the clock proves the interleave, the ledger proves the contention; neither runs
    them together).

    Item A is hourly, item B four-hourly. At 01:00 and 02:00 B has no fresh bar, so it forms
    no intent and cannot take capital; at 04:00 both decide and both compete."""
    hours = [f"2024-01-01T{h:02d}:00:00Z" for h in range(0, 9)]
    items = [
        ScriptedItem(
            item_id="a",
            share="50",
            bars=[(h, "100") for h in hours],
            entries={hours[1]: ("long", "10")},
        ),
        ScriptedItem(
            item_id="b",
            share="50",
            bars=[(hours[0], "100"), (hours[4], "100"), (hours[8], "100")],
            entries={hours[4]: ("long", "10")},
        ),
    ]
    run = simulate(items, pool="10000")

    # Every instant on A's hourly axis produced exactly one valuation, and B was valued at
    # all of them even though it decided at only three.
    assert len(run.ticks) == 9
    b_decided = [
        r.timestamp for r in run.ticks if next(v for v in r.views if v.item_id == "b").is_decision
    ]
    assert b_decided == [hours[0], hours[4], hours[8]]

    at_one = run.tick_at(hours[1])
    assert [i.item_id for i in at_one.intents] == ["a"]

    at_four = run.tick_at(hours[4])
    assert [i.item_id for i in at_four.intents] == ["b"]
    # A entered at 01:00 and is still committed at 04:00 even though it decided nothing new.
    assert at_four.snapshot.deployed_notional["a"] == Decimal("1000.00")
    assert run.ledger.gross_exposure == Decimal("2000.00")


def test_the_order_the_caller_visits_items_in_cannot_move_a_number() -> None:
    """doc 13 §13 / ADR §14 A4, asserted over a whole run rather than one tick.

    ``caller_order`` is the DOM/request order canon forbids from mattering; the pinned
    ordinals are untouched. Every equity point and every arbitration report identity must be
    identical."""
    forward = simulate(_interleaved_pair(), pool="10000")
    reversed_visit = simulate(_interleaved_pair(), pool="10000", caller_order=[1, 0])

    assert forward.instants == reversed_visit.instants
    assert [str(p.equity) for p in forward.dated_points] == [
        str(p.equity) for p in reversed_visit.dated_points
    ]
    assert forward.max_drawdown == reversed_visit.max_drawdown
    assert [r.report.identity for r in forward.ticks] == [
        r.report.identity for r in reversed_visit.ticks
    ]
    assert [r.snapshot.identity for r in forward.ticks] == [
        r.snapshot.identity for r in reversed_visit.ticks
    ]


def test_chunking_each_items_bars_differently_cannot_move_a_number() -> None:
    """Cross-item batch invariance (ADR §11, §14 A18). The worker streams bars in batches;
    the batch size is an I/O detail and must never reach a financial figure."""
    whole = simulate(_interleaved_pair(), pool="10000")
    chunked = simulate(_interleaved_pair(), pool="10000", batch=2)

    assert whole.instants == chunked.instants
    assert [str(p.equity) for p in whole.dated_points] == [
        str(p.equity) for p in chunked.dated_points
    ]
    assert [r.report.identity for r in whole.ticks] == [r.report.identity for r in chunked.ticks]


def _load_items(count: int, ticks: int) -> list[ScriptedItem]:
    hours = [f"2024-01-{1 + t // 24:02d}T{t % 24:02d}:00:00Z" for t in range(ticks)]
    items: list[ScriptedItem] = []
    for i in range(count):
        entry = hours[(i * 3) % (ticks - 2)]
        exit_at = hours[(i * 3 + 2) % (ticks - 2) + 1]
        items.append(
            ScriptedItem(
                item_id=f"item_{i:02d}",
                share=str(Decimal("100") / count),
                bars=[(h, "100") for h in hours],
                instrument_id=f"SYM{i:02d}",
                entries={entry: ("long", "5")},
                exits={exit_at: "10.00" if i % 2 == 0 else "-10.00"},
            )
        )
    return items


def test_a_realistic_composition_stays_conservative_and_deterministic_under_load() -> None:
    """Load sanity at a realistic item count, not a benchmark.

    12 items over 72 ticks. The properties that must survive scale are the ones a small
    fixture cannot stress: the curve stays time-ordered, the accounting identity stays exact,
    the pool is never overspent, and a rerun is bit-identical."""
    items = _load_items(12, 72)
    run = simulate(items, pool="120000", reserve_percent="10")

    assert list(run.instants) == sorted(run.instants)
    assert run.ledger.equity == run.ledger.accounting_identity
    for record in run.ticks:
        committed = sum(
            (d.granted_notional for d in record.report.decisions if d.is_admitted),
            Decimal("0"),
        )
        assert committed <= record.snapshot.allocatable
    assert run.ledger.gross_exposure <= run.ledger.plan.allocatable(run.ledger.equity)

    again = simulate(_load_items(12, 72), pool="120000", reserve_percent="10")
    assert [str(p.equity) for p in run.dated_points] == [str(p.equity) for p in again.dated_points]
    assert [r.report.identity for r in run.ticks] == [r.report.identity for r in again.ticks]


def test_the_driver_arbitrates_what_the_shipped_former_actually_produces() -> None:
    """Guard for the one shortcut in the harness: ``_p4_intent`` builds an entry intent
    directly rather than carrying a whole ``StrategyConfig`` per item. If the shipped former's
    shape ever drifts from it, this fails.

    ``form_intents`` is run over the same tick with a ``no_op`` decision (the one actionable-
    free kind that needs no sizing inputs), and the fields the harness pins by hand —
    contract version, phase, snapshot dependency — must match."""
    run = simulate(_interleaved_pair(), pool="10000")
    record = run.tick_at(_HOURS[0])
    assert record.intents, "fixture must put at least one intent on the opening tick"

    snapshot: PortfolioSnapshot = record.snapshot
    formed = form_intents(
        tick=_tick_for(record.t_ms),
        snapshot=snapshot,
        identities={"a": _identity_a(), "b": _identity_b()},
        decisions={"a": (ItemDecision(kind="no_op", reason="no_signal_at_tick"), None)},
    )
    reference = next(i for i in formed if i.item_id == "a")
    harness_built = next(i for i in record.intents if i.item_id == "a")

    assert harness_built.contract_version == reference.contract_version
    assert harness_built.phase == reference.phase == "P4"
    assert harness_built.snapshot_identity == reference.snapshot_identity == snapshot.identity
    # The former records strictly more provenance than the shortcut needs; what the shortcut
    # DOES record must be a subset of it, spelled the same way and carrying the same values.
    assert set(harness_built.dependencies) <= set(reference.dependencies)
    for key in harness_built.dependencies:
        assert harness_built.dependencies[key] == reference.dependencies[key]
    assert harness_built.is_actionable is True
    assert reference.is_actionable is False  # a no_op asks for no order


def _tick_for(t_ms: int):
    from entropia.domain.backtest.execution.clock import ItemBarStream, iter_ticks

    from .portfolio_harness import row

    streams = [
        ItemBarStream(item_id="a", pin_ordinal=0, batches=[[row(_HOURS[0], "100")]]),
        ItemBarStream(item_id="b", pin_ordinal=1, batches=[[row(_HOURS[0], "100")]]),
    ]
    tick = next(iter_ticks(streams))
    assert tick.t_ms == t_ms
    return tick


def _identity_a():
    return ScriptedItem(item_id="a", share="50", bars=()).identity(0)


def _identity_b():
    return ScriptedItem(item_id="b", share="50", bars=()).identity(1)
