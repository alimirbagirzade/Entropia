"""The `C3` adapter under the SHIPPED phase loop — the two invariants of P-C2 §C.1.

Every other portfolio oracle drives ``run_portfolio`` with ``_ScriptedParticipant``, which
states its decisions as fixture data and keeps no book of its own. That proves the LOOP.
It cannot prove the thing `C3` adds, because the whole risk of `C3` is that TWO books now
record the same run: the item's ``_Ledger`` (so stop ladders, trade rows and the decision
trace behave exactly as in a single-item run) and the shared ``PortfolioLedger`` (the only
authority for ``E(t)``).

Two books can drift, so the design names two invariants and this module is them:

* **Reconciliation** (§C.3.3) — the pool's attribution deltas equal the item ledger's
  realized deltas, on a TWO-item fixture. Asserted per item and in total, so an error that
  cancels between items cannot hide in the sum.
* **Sleeve parity** (§C.3.5) — seam #7, *"the weakest link in the whole design"*: ``Ci(t)``
  is derived twice, by ``sizing.planned_size`` from the injected ``E(t)`` and by the ledger
  as ``snapshot.sleeve_capacity``. Asserted at EVERY tick for EVERY item, from outside the
  adapter, so the test does not merely re-run the adapter's own guard.

The fixture is the ORACLE harness's geometry (20 flat bars, a 20-bar SMA cross on bar 21),
so the entries these tests arbitrate are the engine's real signals, not scripted ones. What
each number should be is hand-derived in the docstring that asserts it.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

import pytest

from entropia.domain.backtest.engine import _build_stepper
from entropia.domain.backtest.execution.arbitration import ArbitrationDecision
from entropia.domain.backtest.execution.clock import ItemBarStream, iter_ticks
from entropia.domain.backtest.execution.intents import ItemIdentity
from entropia.domain.backtest.execution.shared_shapes import unsupported_shared_shapes
from entropia.domain.backtest.execution.sizing import sleeve_capital
from entropia.domain.backtest.execution.state import AllocationExecution
from entropia.domain.backtest.participant import (
    ParticipantDivergenceError,
    UnsupportedStrategyShapeError,
    _EngineParticipant,
)
from entropia.domain.backtest.portfolio_engine import PortfolioRun, run_portfolio
from entropia.domain.strategy.config import StrategyConfig

from .harness import FLAT_BARS, bar, flat_run, oracle_config

_POOL = Decimal("10000.00")

#: The shared-clock conflict/exit shape. ``same_direction_stacking`` has to be stated: the
#: SCHEMA default is ``allow_stacking``, which the adapter refuses because a stack opens a
#: second entry inside ``_phase_tail``, outside arbitration. That refusal is a measured
#: finding of this slice, not a fixture convenience — see the module's PR notes.
_SHARED_CONFLICT: dict[str, Any] = {"same_direction_stacking": "ignore"}


def _config(**kwargs: Any) -> StrategyConfig:
    return oracle_config(direction="long", conflict=_SHARED_CONFLICT, **kwargs)


def _participant(
    item_id: str,
    ordinal: int,
    bars: list[dict[str, Any]],
    share: str,
    *,
    config: StrategyConfig | None = None,
    reserve_percent: str = "0",
    compound: bool = True,
    plan_direction: str = "long",
) -> _EngineParticipant:
    """One item behind the phase loop: a real ``_ItemStepper`` on a real bar stream.

    ``item_share_percent`` is the item's ``wi`` as the ENGINE sees it. The pool is told the
    same number separately (``shares=`` on the loop), and the sleeve-parity invariant is
    exactly the assertion that the worker cannot pass one to the engine and another to the
    ledger without something noticing."""
    from .harness import entry_plan

    stepper = _build_stepper(
        strategy_config=config if config is not None else _config(),
        execution_key="closure_c3_exec_key",
        item_count=2,
        indicator_plan=entry_plan(direction=plan_direction),
        allocation=AllocationExecution(
            initial_capital=_POOL,
            reserve_percent=Decimal(reserve_percent),
            compound=compound,
            item_share_percent=Decimal(share),
            currency=None,
        ),
    )
    return _EngineParticipant(
        identity=ItemIdentity(
            item_id=item_id,
            item_kind="strategy",
            pin_ordinal=ordinal,
            root_id=f"root_{item_id}",
            selected_revision_id=f"rev_{item_id}",
        ),
        stream=ItemBarStream(item_id=item_id, pin_ordinal=ordinal, batches=[bars]),
        stepper=stepper,
        instrument_id="BTCUSDT",
    )


#: Item A: crosses UP on bar 21 at 110, then bar 22 takes out the 1% protection stop
#: (110 * 0.99 = 108.90; the bar opens at 109 and prints down to 100).
_STOPPED_OUT = [
    *flat_run(),
    bar(21, "110", "110", "110", "110"),
    bar(22, "109", "109", "100", "105"),
]

#: Item B: crosses UP on the same bar and never stops (bar 22's low is 111, above 108.90),
#: so its position is still open at end of data and P10 is what closes it.
_HELD_TO_THE_END = [
    *flat_run(),
    bar(21, "110", "110", "110", "110"),
    bar(22, "112", "115", "111", "114"),
]


def _two_items(
    *,
    config_a: StrategyConfig | None = None,
    config_b: StrategyConfig | None = None,
) -> list[_EngineParticipant]:
    return [
        _participant("a", 0, _STOPPED_OUT, "60", config=config_a),
        _participant("b", 1, _HELD_TO_THE_END, "40", config=config_b),
    ]


def _run(
    participants: Sequence[_EngineParticipant],
    *,
    max_position_notional: dict[str, Decimal] | None = None,
) -> PortfolioRun:
    return run_portfolio(
        participants,
        pool_initial=_POOL,
        shares={"a": Decimal("60"), "b": Decimal("40")},
        max_position_notional=max_position_notional,
    )


def _item_delta(participant: _EngineParticipant) -> Decimal:
    """What the item's OWN ledger did over the run, seeded at the pool it replays from.

    Under allocation ``_build_stepper`` seeds ``led.equity`` at P0 (the shared pool), not at
    the strategy's own ``initial_capital`` — so the delta is the item's whole contribution
    and nothing else."""
    return participant.stepper.ledger.equity - _POOL


# --------------------------------------------------------------------------- #
# Invariant 1 — reconciliation (P-C2 §C.3.3)                                   #
# --------------------------------------------------------------------------- #
def test_the_pools_attribution_equals_each_items_own_realized_delta() -> None:
    """Dual booking is safe rather than lucky: neither book drifts from the other.

    Hand-derived, so a green run is not self-referential. Sleeves are ``A0 * wi/100`` with
    ``A0 = P0 = 10 000``: A gets 6 000, B gets 4 000. ``risk_based_sizing`` at 1% over a
    2.00 stop distance sizes off the SLEEVE (``SIZING_BASE_DIVERGENCE``), so A opens
    ``6000 * 1% / 2.00 = 30`` units and B opens ``4000 * 1% / 2.00 = 20``, both at 110.

    * **A** stops out at 108.90 on bar 22: ``(108.90 - 110) * 30 = -33.00``.
    * **B** is closed by P10 at bar 22's close of 114: ``(114 - 110) * 20 = +80.00``.

    The pool therefore ends at ``10 000 - 33 + 80 = 10 047.00``, and each item's tagged
    contribution is its own figure — which is the point: a shared pool cannot recover
    *"which item earned this"* from ``E(t)``."""
    participants = _two_items()
    run = _run(participants)

    assert [c.item_id for c in run.final_closes] == ["b"]  # P10 closed exactly one item
    assert {t.item_id for t in run.ticks[-1].mandatory} <= {"a"}

    assert _item_delta(participants[0]) == Decimal("-33.00")
    assert _item_delta(participants[1]) == Decimal("80.00")

    for participant in participants:
        item_id = participant.identity.item_id
        assert run.ledger.attribution[item_id].net_contribution == _item_delta(participant), (
            f"item '{item_id}' and the pool disagree about what it realized"
        )

    assert run.ledger.equity == Decimal("10047.00")
    assert run.ledger.equity - _POOL == sum((_item_delta(p) for p in participants), Decimal("0"))


def test_reconciliation_holds_when_arbitration_grants_less_than_the_item_planned() -> None:
    """The ``size_override`` leg: a capped grant is what the ITEM books, not what it wanted.

    A ``max_position_notional`` of 2 200 on item A caps its 30 planned units to
    ``2200 / 110 = 20`` — the same clamp ``_cap_to_sleeve`` applies, one layer out. The
    item must book 20, so its stop realizes ``(108.90 - 110) * 20 = -22.00`` instead of
    -33.00, and the pool's attribution must move with it.

    Without the override the item would book 30 while the pool holds 20: the two ledgers
    would still RECONCILE (both would record the item's own figure) and the run would still
    be wrong, which is why this test asserts the SIZE as well as the identity."""
    participants = _two_items()
    run = _run(participants, max_position_notional={"a": Decimal("2200")})

    capped = run.ticks[-2].report.decisions
    granted = {d.item_id: d.granted_units for d in capped if d.is_admitted}
    assert granted == {"a": Decimal("20.00000000"), "b": Decimal("20.00000000")}

    assert _item_delta(participants[0]) == Decimal("-22.00")
    for participant in participants:
        item_id = participant.identity.item_id
        assert run.ledger.attribution[item_id].net_contribution == _item_delta(participant)


def test_the_entry_fills_commission_is_the_one_leg_the_loop_cannot_mirror() -> None:
    """A measured GAP, pinned rather than papered over — and it is not this slice's to fix.

    ``_do_open`` charges the entry fill's commission to the item's equity at entry time
    (GH #552 / PD-2: commission is per-FILL). ``_phase_7_apply`` books no cost — the loop
    calls ``set_position`` and nothing else — and ``settle`` returns ``None``, so the
    adapter has no channel to state that charge at the tick it happens. The two books
    therefore part by EXACTLY the entry-side commissions, and by nothing else.

    Mirroring it through the NEXT tick's ``CarryCharges.fee`` would make the total right
    and the TIMING wrong (PD-2 records that equity dropping at entry is the point, because
    it moves ``peak`` and every drawdown-derived metric). Inventing that shift here would
    be a silent numerical change with no decision behind it, so the gap is measured and
    reported instead: it belongs to the loop (``portfolio_engine.py``), which `C3` does not
    touch.

    Two fills, one per item, at a commission of 7 → the divergence is 14.00 and the
    per-item halves are 7.00 each. A fixture with zero commission would have reported a
    clean identity for a leg that never ran."""
    commission = Decimal("7")
    costs = {"slippage_mode": "percentage_slippage", "slippage_value": "0", "commission": "7"}
    participants = _two_items(config_a=_config(costs=costs), config_b=_config(costs=costs))
    run = _run(participants)

    divergences = {
        p.identity.item_id: run.ledger.attribution[p.identity.item_id].net_contribution
        - _item_delta(p)
        for p in participants
    }
    assert divergences == {"a": commission, "b": commission}

    # The EXIT-side commission is mirrored — it travels in ``MandatoryExit.commission`` and
    # lands on the pool's ``fees`` line. Only the entry side is missing, so the gap is one
    # fill per position and not "commission is not booked at all".
    assert run.ledger.fees == commission * 2
    assert sum(divergences.values(), Decimal("0")) == commission * 2


# --------------------------------------------------------------------------- #
# Invariant 2 — sleeve parity (P-C2 §C.3.5, seam #7)                           #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("compound", "reserve_percent"),
    [(True, "0"), (True, "10"), (False, "10")],
)
def test_the_sleeve_the_engine_sizes_against_is_the_one_the_pool_published(
    compound: bool, reserve_percent: str
) -> None:
    """``Ci(t)`` derived twice, compared at every tick for every item — seam #7 closed.

    The engine computes ``sleeve_capital(ctx, E(t))`` inside ``planned_size`` from its OWN
    ``AllocationExecution``; the ledger computes ``SleevePlan.sleeve_capacity(E(t))`` from
    the plan the worker handed IT. Nothing structural forces those two resolutions to be
    the same object, so the equality is asserted rather than assumed.

    Run under all three capital models the plan can carry — compounding with and without a
    reserve, and fixed — because the two derivations take DIFFERENT branches in each
    (``max(0, E - R0) * wi`` versus a frozen ``Ci0``), and a parity that only held while
    ``E(t)`` never moved would be no parity at all."""
    participants = [
        _participant(
            "a", 0, _STOPPED_OUT, "60", reserve_percent=reserve_percent, compound=compound
        ),
        _participant(
            "b", 1, _HELD_TO_THE_END, "40", reserve_percent=reserve_percent, compound=compound
        ),
    ]
    run = run_portfolio(
        participants,
        pool_initial=_POOL,
        shares={"a": Decimal("60"), "b": Decimal("40")},
        reserve_percent=Decimal(reserve_percent),
        compound=compound,
    )

    checked = 0
    for tick in run.ticks:
        for participant in participants:
            item_id = participant.identity.item_id
            assert (
                sleeve_capital(participant.stepper.ctx, tick.snapshot.equity)
                == (tick.snapshot.sleeve_capacity[item_id])
            ), f"Ci(t) diverged for '{item_id}' at t_ms={tick.t_ms}"
            checked += 1

    # A run whose ticks never happened would satisfy the loop above vacuously, and E(t) has
    # to actually MOVE for the compound branch to be exercised at all.
    assert checked == len(run.ticks) * 2 > 0
    assert len({t.snapshot.equity for t in run.ticks}) > 1


def test_a_share_the_pool_never_published_refuses_instead_of_sizing() -> None:
    """The wiring bug the invariant exists to catch, driven end to end.

    The worker resolves ``wi`` twice — once into each item's ``AllocationExecution`` and
    once into the loop's ``shares`` map. Here they disagree by ten points. Nothing in the
    loop compares them: the intent would be sized against a 7 000 sleeve while the pool
    capped against 6 000, and the only visible symptom would be an entry slightly too big.
    The adapter refuses at P4 instead, before any capital is committed."""
    participants = [
        _participant("a", 0, _STOPPED_OUT, "70"),  # the ENGINE is told 70 …
        _participant("b", 1, _HELD_TO_THE_END, "40"),
    ]
    with pytest.raises(ParticipantDivergenceError, match="the pool published"):
        run_portfolio(
            participants,
            pool_initial=_POOL,
            shares={"a": Decimal("60"), "b": Decimal("40")},  # … the POOL is told 60
        )


# --------------------------------------------------------------------------- #
# The three traps (plan `C3` stop condition)                                   #
# --------------------------------------------------------------------------- #
#: A long cross on bar 21 and an OPPOSITE cross on bar 22 — the only geometry in which the
#: describe half still wants an entry at a bar the item is already holding through. Paired
#: with ``protection={}`` so the dip does not simply stop the position out first.
_REVERSING = [*flat_run(), bar(21, "110", "110", "110", "110"), bar(22, "95", "95", "95", "95")]


def test_entry_returns_none_while_the_item_already_holds_even_if_the_pool_forgets() -> None:
    """Trap 1 — the flat check lives in ``_step``'s DRIVER, not in ``_phase_entry_body``.

    ``_evaluate_entry``'s guard list carries ``pending`` / ``working_limit`` /
    ``working_stop`` but NOT ``position``: it is ``if not _phase_held(bar)`` in ``_step``
    that keeps a held item out of the entry phase. An adapter that forwarded P4 unguarded
    would let the pool arbitrate a SECOND entry — here an opposite-direction one — for an
    item that already holds a position.

    ``held=None`` is passed deliberately on the second call: that is the loop saying the
    POOL holds nothing for this item. The item's OWN book is consulted too, so the two
    would have to be wrong together before a second entry could be described.

    Driven as a SOLO participant over P0/P1/P4 only. P3 is not driven on purpose — the
    question this isolates is what P4 does with a held item, and letting the mandatory-exit
    phase close the position first would answer a different one. The trap is shown to be
    LIVE rather than assumed: at that same bar the describe half wants a short, so a green
    result is not the tautology of a bar that wanted nothing anyway."""
    reference = _run(_two_items())
    entry_tick = next(t for t in reference.ticks if t.intents)
    last_tick = reference.ticks[-1]

    solo = _participant(
        "b",
        1,
        _REVERSING,
        "40",
        config=oracle_config(direction="long_and_short", conflict=_SHARED_CONFLICT, protection={}),
        plan_direction="long_and_short",
    )
    held_view = None
    for tick in iter_ticks([solo.stream]):
        view = tick.view_for("b")
        assert view is not None and view.is_decision
        solo.carry(view)
        if tick.t_ms == entry_tick.t_ms:
            assert solo.entry(view, entry_tick.snapshot, held=None) is not None
            solo.settle(
                view, admitted=next(d for d in entry_tick.report.decisions if d.item_id == "b")
            )
            assert solo.stepper.open_position() is not None
        elif tick.t_ms == last_tick.t_ms:
            held_view = view
    assert held_view is not None

    described = solo.stepper.evaluate_entry(held_view.bars[-1])
    assert described is not None and described.want == "short", (
        "the describe half wants an entry at this bar, so the guard below is the only thing "
        "standing between a held item and a second arbitrated entry"
    )
    assert solo.entry(held_view, last_tick.snapshot, held=None) is None


def test_the_adapter_delegates_the_five_boundary_checks_to_the_loop() -> None:
    """Trap 2 — refusing a misformed intent is ``_validated_intent``'s job, not the
    adapter's.

    A source-level ratchet, because a behavioural test cannot see a check that is ABSENT:
    every duplicate would agree with the original until the day one of them changed. The
    adapter builds intents only through the shipped former and re-tests none of the five
    properties the loop checks at the boundary (right item, ``phase == "P4"``, not a
    mandatory kind, right ``t_ms``, right ``snapshot_identity``)."""
    from entropia.domain.backtest import participant as adapter

    source = _module_source(adapter)
    assert "form_intent(" in source
    assert "ItemIntent(" not in source, "the adapter must not hand-build an intent"
    for delegated in ("snapshot_identity", "MANDATORY_KINDS", "MisformedIntentError"):
        assert delegated not in source, (
            f"the adapter re-implements the loop's '{delegated}' boundary check; letting the "
            "loop refuse is the point of having it there"
        )


def test_the_bars_the_stepper_admits_are_the_clocks_own_objects() -> None:
    """Trap 3 — there is NO bar translation layer, and there may not be one.

    ``clock.py`` and ``engine.py`` both import ``_Bar`` and ``_normalize`` from
    ``execution/state.py``, so the clock's bars are already the ones the stepper consumes.
    A second normalization would be a second coercion policy: a row one of them dropped and
    the other kept would put the two books on different data.

    Asserted by IDENTITY, not by equality — an adapter that rebuilt an equal ``_Bar`` would
    pass an ``==`` check while having introduced exactly the layer this forbids."""
    from entropia.domain.backtest import participant as adapter

    source = _module_source(adapter)
    assert "_normalize(" not in source
    assert "_Bar(" not in source

    participants = _two_items()
    run = _run(participants)
    last_view = next(
        view for view in run.ticks[-1].views if view.item_id == "a" and view.is_decision
    )
    assert participants[0]._current is last_view.bars[-1]


def _module_source(module: Any) -> str:
    import inspect

    return inspect.getsource(module)


# --------------------------------------------------------------------------- #
# Fail-closed refusals                                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"entry_timing": "next_candle_open"}, "defers or rests the entry fill"),
        ({"exit_timing": "next_candle_close"}, "defers or rests the exit fill"),
        (
            {
                "order_config": {
                    "type": "limit_order",
                    "limit": {
                        "price_rule": "entry_signal_price",
                        "validity": "3_candles",
                        "unfilled_policy": "cancel_order",
                        "partial_fill_policy": "not_allowed",
                    },
                }
            },
            "rests a working order",
        ),
        (
            {"exit_logic": {"applies_to_direction": "long_and_short", "close_percentage": "50"}},
            "partial close",
        ),
        (
            {
                "scaling": {
                    "enabled": True,
                    "method": "price_distance_scaling",
                    "price_scaling": {"retracement_distance": "1", "layers": 2},
                    "add_size": "percent_of_initial",
                    "add_size_value": "50",
                }
            },
            "layer ladder",
        ),
        ({"conflict": {"same_direction_stacking": "allow_stacking"}}, "opens a second entry"),
        (
            {
                "conflict": {
                    "same_direction_stacking": "ignore",
                    "opposite_direction_hedge": "close_existing",
                }
            },
            "closes the position inside",
        ),
        (
            {"sizing": {"method": "risk_based_sizing", "risk_based": None}},
            "fail-closed capability gate is down",
        ),
    ],
)
def test_an_execution_shape_the_shared_clock_cannot_drive_is_refused_at_construction(
    kwargs: dict[str, Any], expected: str
) -> None:
    """Every refusal is a shape that would otherwise produce a WRONG run, not a slow one.

    The adapter drives four of ``_step``'s five phases and never calls ``tail``: its
    scaling section was measured INSEPARABLE at `C1`, and its stacking / hedge sections
    open and close positions with no ``PortfolioSnapshot`` behind them. Rather than run a
    phase that can commit capital outside arbitration — or drop a configured behaviour
    silently, which is the same defect wearing a quieter coat — the shape is refused before
    a single bar is admitted.

    These are the engine-side statement of what `C6` has to block at ADMISSION (P-C2 §C.3.7
    and §C.3.8 both recommend option (a)). Refusing here means a wrong shared run is
    impossible before `C6` exists, instead of merely improbable."""
    base = {"direction": "long", "conflict": _SHARED_CONFLICT}
    base.update(kwargs)
    with pytest.raises(UnsupportedStrategyShapeError, match=expected):
        _participant("a", 0, _STOPPED_OUT, "60", config=oracle_config(**base))


_SCALING_ON: dict[str, Any] = {
    "enabled": True,
    "method": "price_distance_scaling",
    "price_scaling": {"retracement_distance": "1", "layers": 2},
    "add_size": "percent_of_initial",
    "add_size_value": "50",
}

_LIMIT_ORDER: dict[str, Any] = {
    "type": "limit_order",
    "limit": {
        "price_rule": "entry_signal_price",
        "validity": "3_candles",
        "unfilled_policy": "cancel_order",
        "partial_fill_policy": "not_allowed",
    },
}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"entry_timing": "next_candle_open"},
        {"exit_timing": "next_candle_close"},
        {"order_config": _LIMIT_ORDER},
        {"scaling": _SCALING_ON},
    ],
    ids=["entry_timing", "exit_timing", "order_type", "scaling"],
)
def test_the_loop_refuses_the_shapes_admission_refuses_with_the_same_sentence(
    kwargs: dict[str, Any],
) -> None:
    """`C6` PARITY: one predicate, two moments — not two lists that agree today.

    ``G11`` and ``G12`` made these four rows user-visible blockers at ADMISSION, where a
    refusal leaves no run, manifest or job behind. The loop still refuses them at
    construction, after those rows already exist. Both refusals now read
    ``execution/shared_shapes.py``, and this test derives the expected sentence from that
    module instead of quoting it: a second hand-written copy in either home — or a splice
    dropped out of ``_unsupported_shapes`` — turns this red rather than leaving the two
    statements to drift apart silently.
    """
    config = _config(**kwargs)
    violations = unsupported_shared_shapes(config)
    assert violations, "the fixture must actually violate a signed gate"
    with pytest.raises(UnsupportedStrategyShapeError) as exc_info:
        _participant("a", 0, _STOPPED_OUT, "60", config=config)
    for violation in violations:
        assert violation.detail in str(exc_info.value)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"exit_logic": {"applies_to_direction": "long_and_short", "close_percentage": "50"}},
        {"conflict": {"same_direction_stacking": "allow_stacking"}},
        {
            "conflict": {
                "same_direction_stacking": "ignore",
                "opposite_direction_hedge": "close_existing",
            }
        },
    ],
    ids=["partial_close", "stacking", "hedge"],
)
def test_the_loop_refuses_more_than_admission_does_and_that_gap_is_deliberate(
    kwargs: dict[str, Any],
) -> None:
    """The WITHHELD rows, pinned so the omission cannot go quiet.

    Only ``G11`` and ``G12`` are signed. Partial closes, same-direction stacking and a
    ``close_existing`` hedge are refused by the loop for reasons just as financial, but
    no signature covers them, so `C6` emits no blocker for them and a run carrying one
    still fails LATE. That is the pre-`C6` status quo for these rows, not a regression —
    and it is a fact, not a preference, so it is measured here rather than described in a
    docstring nobody re-checks. Signing one of them is a one-row change in
    ``shared_shapes.py`` plus a mapping entry; this test going red is how that lands.
    """
    base: dict[str, Any] = {"direction": "long", "conflict": _SHARED_CONFLICT}
    base.update(kwargs)
    config = oracle_config(**base)
    assert unsupported_shared_shapes(config) == ()
    with pytest.raises(UnsupportedStrategyShapeError):
        _participant("a", 0, _STOPPED_OUT, "60", config=config)


def test_a_run_with_no_allocation_is_refused_rather_than_sized_off_a_private_ledger() -> None:
    """Without an ``AllocationExecution`` the sizing chain reads the item's OWN equity, and
    ``Ci(t)`` has no pool to be a slice of — so sleeve parity is not merely violated, it is
    undefined. A shared run is a run under one pool or it is not a shared run."""
    from .harness import entry_plan

    stepper = _build_stepper(
        strategy_config=_config(),
        execution_key="closure_c3_exec_key",
        item_count=2,
        indicator_plan=entry_plan(direction="long"),
    )
    with pytest.raises(UnsupportedStrategyShapeError, match="no AllocationExecution"):
        _EngineParticipant(
            identity=ItemIdentity(item_id="a", item_kind="strategy", pin_ordinal=0),
            stream=ItemBarStream(item_id="a", pin_ordinal=0, batches=[_STOPPED_OUT]),
            stepper=stepper,
        )


def test_settle_refuses_when_the_item_did_not_book_what_the_pool_opened() -> None:
    """The fail-closed half of dual booking, driven directly.

    ``_open`` takes ``min(planned, granted)``, so a grant LARGER than the plan leaves the
    pool holding more than the item does. Every later phase — the stop ladder, funding on
    notional, the exposure caps — would then be computed against a position one of the two
    books does not have, and nothing downstream re-checks it. The adapter refuses at the
    one moment both figures are in scope."""
    entry_tick = next(t for t in _run(_two_items()).ticks if t.intents)

    # A FRESH participant, driven phase by phase to the cross bar on the clock's own axis —
    # not the finished run's, whose stepper is already past this instant and whose P0 guard
    # would (correctly) refuse to decide on a bar it has moved beyond.
    solo = _participant("a", 0, _STOPPED_OUT, "60")
    view = None
    for tick in iter_ticks([solo.stream]):
        current = tick.view_for("a")
        assert current is not None and current.is_decision
        solo.carry(current)
        if tick.t_ms == entry_tick.t_ms:
            view = current
            break
    assert view is not None
    assert solo.entry(view, entry_tick.snapshot, held=None) is not None

    with pytest.raises(ParticipantDivergenceError, match="The pool holds a position"):
        solo.settle(
            view,
            admitted=ArbitrationDecision(
                item_id="a",
                pin_ordinal=0,
                kind="entry",
                direction="long",
                instrument_id="BTCUSDT",
                outcome="admitted",
                requested_units=Decimal("30"),
                granted_units=Decimal("999"),
                granted_notional=Decimal("109890"),
                reason=None,
                binding_constraint=None,
            ),
        )


def test_settle_refuses_a_grant_for_an_entry_the_item_never_described() -> None:
    """The mirror refusal: an admitted decision with no pending plan means the loop and the
    adapter disagree about which tick they are on. Booking "something" for it would open a
    position the item never asked for."""
    participants = _two_items()
    run = _run(participants)
    entry_tick = next(t for t in run.ticks if t.intents)
    view = next(v for v in entry_tick.views if v.item_id == "b")

    with pytest.raises(ParticipantDivergenceError, match="never described"):
        participants[1].settle(
            view,
            admitted=ArbitrationDecision(
                item_id="b",
                pin_ordinal=1,
                kind="entry",
                direction="long",
                instrument_id="BTCUSDT",
                outcome="admitted",
                requested_units=Decimal("20"),
                granted_units=Decimal("20"),
                granted_notional=Decimal("2200"),
                reason=None,
                binding_constraint=None,
            ),
        )


def test_a_tick_the_item_has_no_bar_at_reaches_no_hook_and_books_nothing() -> None:
    """ADR §5 — *"a tick at which item i has no bar is not a decision for item i"*.

    Item B's stream stops one bar early, so the last tick is A's alone. B's position is
    still valued at that tick, because the POOL holds it, not the view — and that is the
    whole reason a silent item still has to appear on the axis."""
    short_b = [*flat_run(), bar(21, "110", "110", "110", "110")]
    participants = [
        _participant("a", 0, _STOPPED_OUT, "60"),
        _participant("b", 1, short_b, "40"),
    ]
    run = _run(participants)

    final = run.ticks[-1]
    assert [v.item_id for v in final.views if v.is_decision] == ["a"]
    assert "b" in run.ledger.positions or [c.item_id for c in run.final_closes] == ["b"]
    assert len(participants[1].stepper.ledger.equity_points) >= 1
    assert run.ledger.attribution["b"].net_contribution == _item_delta(participants[1])


def test_the_axis_is_the_merged_clock_and_the_item_ledgers_are_not_the_curve() -> None:
    """``E(t)`` is the pool's, and the item ledgers are bookkeeping behind it.

    ``FLAT_BARS`` identical bars plus two divergent ones give 22 ticks on one merged axis,
    and the pool's curve is time-ordered by construction (A5). The item ledgers keep their
    own per-close points, which is exactly why the projection publishes the POOL's series
    and never a per-item curve."""
    participants = _two_items()
    run = _run(participants)

    assert len(run.ticks) == FLAT_BARS + 2
    assert list(run.instants) == sorted(run.instants)
    assert run.ledger.equity == _POOL + sum((_item_delta(p) for p in participants), Decimal("0"))


def test_the_mirrored_exit_commission_is_the_fee_charged_not_the_configured_rate() -> None:
    """Karar 1 (GH #552): ``MandatoryExit.commission`` must be MONEY, on either basis.

    ``_closed_by`` states the exit fill's commission to the pool, and the pool books it on
    its ``fees`` line. It used to read ``fill_costs.commission`` — correct only while that
    field WAS the fee. Once the basis became explicit, ``bps`` made it a RATE, and spending
    a rate as money reported 7.00 per item where the engine had charged well under one.

    Measured, both directions:
      * ``flat`` 7 -> 14.00 across the two items, unchanged from before the basis existed;
      * ``bps``  7 -> 3.89, the two exit fills' own notionals at 7 bps.

    The literals are pinned rather than recomputed through ``fee()``: deriving the expected
    value with the same function the fix calls would pass no matter what that function did.
    The `flat` half is the regression guard — it is the number every pre-Karar-1 run booked.
    """
    costs = {
        "slippage_mode": "percentage_slippage",
        "slippage_value": "0",
        "commission": "7",
        "commission_basis": "bps",
    }
    run = _run(_two_items(config_a=_config(costs=costs), config_b=_config(costs=costs)))

    assert run.ledger.fees == Decimal("3.89")
    # The defect this pins: reading the magnitude would have made these equal.
    assert run.ledger.fees != Decimal("7") * 2
