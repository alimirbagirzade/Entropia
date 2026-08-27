"""Unified-clock portfolio oracles — the CAPITAL half: one pool, many items, over time.

The sibling module pins the clock (one valuation per tick, time-order, no lookahead). This
one pins what that valuation BUYS: the sleeve arithmetic across ticks, the fixed reserve, the
compounding axis, and what happens when two items want the same cash at the same instant.

Every expected figure is hand-derived from doc 13 §0.2/§6.1/§8.3/§8.4 and §14 tests 10/12/13,
Master Reference Modül 11 §5.1/§5.3/§6.1, and ADR 0002 §7/§9 — written as a literal. No engine
arithmetic helper builds an expectation here.

Since ADIM 18 the phase loop is the SHIPPED one
(``domain/backtest/portfolio_engine.py::run_portfolio``); these oracles were carried over
unchanged across that substitution. Read ``portfolio_harness`` §"WHAT MOVED AT ADIM 18" for
what is still fixture-owned and for the gap that keeps the containment closed.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from entropia.domain.backtest.execution.arbitration import (
    UnsupportedConflictPolicyError,
)
from entropia.domain.backtest.execution.attribution import attribute
from entropia.domain.backtest.execution.portfolio_ledger import (
    EXPOSURE_CONSTRAINT,
    LEDGER_INSOLVENT,
    SLEEVE_CONSTRAINT,
    SOLVENCY_CONSTRAINT,
)

from .portfolio_harness import ScriptedItem, simulate

_HOURS = [f"2024-01-01T{h:02d}:00:00Z" for h in range(6)]
_FLAT = [(h, "100") for h in _HOURS[:4]]


# ------------------------------------------------------------------ the opening split


def test_the_first_valuation_publishes_doc13_acceptance_test_10() -> None:
    """P0=10000, r=10% -> R0=1000, A0=9000; shares 40/35/15 -> 3600/3150/1350, U0=900.

    The ledger's own unit tests pin this arithmetic. What is pinned HERE is that the figure a
    running portfolio's first ``PortfolioSnapshot`` hands every item is that same split — the
    preview the user was shown and the number the engine sizes against are one value."""
    items = [
        ScriptedItem(item_id="a", share="40", bars=_FLAT),
        ScriptedItem(item_id="b", share="35", bars=_FLAT),
        ScriptedItem(item_id="c", share="15", bars=_FLAT),
    ]
    snapshot = simulate(items, pool="10000", reserve_percent="10").ticks[0].snapshot

    assert snapshot.equity == Decimal("10000.00")
    assert snapshot.reserve_nominal == Decimal("1000")
    assert snapshot.allocatable == Decimal("9000.00")
    assert dict(snapshot.sleeve_capacity) == {
        "a": Decimal("3600.00"),
        "b": Decimal("3150.00"),
        "c": Decimal("1350.00"),
    }
    assert snapshot.unallocated == Decimal("900.00")


# ------------------------------------------------------------------------- the reserve


def test_the_reserve_stays_a_fixed_nominal_amount_across_a_multi_tick_drawdown() -> None:
    """doc 13 §0.2 / Modül 11 §1.2.6: R0 is a nominal set once, not a percentage re-applied
    to whatever equity later becomes.

    P0=10000, r=10% -> R0=1000. Item A loses 5000 at 01:00, so E=5000 and A(t)=4000. Were the
    reserve re-derived it would be 500 and A(t) would be 4500 — the pool would quietly lend
    out 500 of protected cash. Item B then asks for 6000 and is capped to its 2000 sleeve."""
    items = [
        ScriptedItem(
            item_id="a",
            share="50",
            bars=_FLAT,
            entries={_HOURS[0]: ("long", "40")},
            exits={_HOURS[1]: "-5000.00"},
        ),
        ScriptedItem(item_id="b", share="50", bars=_FLAT, entries={_HOURS[2]: ("long", "60")}),
    ]
    run = simulate(items, pool="10000", reserve_percent="10")

    after_loss = run.tick_at(_HOURS[1])
    assert after_loss.snapshot.equity == Decimal("5000.00")
    assert after_loss.snapshot.reserve_nominal == Decimal("1000")
    assert after_loss.snapshot.allocatable == Decimal("4000.00")

    at_entry = run.tick_at(_HOURS[2])
    assert at_entry.snapshot.sleeve_capacity["b"] == Decimal("2000.00")
    assert at_entry.report.by_item("b").granted_units == Decimal("20")
    assert at_entry.report.by_item("b").binding_constraint == SLEEVE_CONSTRAINT
    # Cash never dips into R0: E - committed = 5000 - 2000 = 3000, and R0 is 1000.
    assert run.ledger.equity - run.ledger.gross_exposure == Decimal("3000.00")


# ------------------------------------------------------- compounding vs fixed, over ticks


def _loss_then_two_entries() -> list[ScriptedItem]:
    """Item B loses 4000 at 01:00; both items then ask for 5000 each at 02:00."""
    return [
        ScriptedItem(item_id="a", share="50", bars=_FLAT, entries={_HOURS[2]: ("long", "50")}),
        ScriptedItem(
            item_id="b",
            share="50",
            bars=_FLAT,
            entries={_HOURS[0]: ("long", "40"), _HOURS[2]: ("long", "50")},
            exits={_HOURS[1]: "-4000.00"},
        ),
    ]


def test_a_siblings_loss_shrinks_the_survivors_sleeve_only_under_compounding() -> None:
    """doc 13 §8.3 / ADR §14 A6-A7 on ONE fixture, so the compounding axis is isolated.

    P0=10000, r=10% -> R0=1000, A0=9000, 50/50 -> Ci0=4500. B realises -4000 at 01:00, so at
    02:00 E=6000 and A(t)=5000.

    COMPOUND: Ci = 5000 * 50/100 = 2500 — item A's sleeve shrank because its SIBLING lost
    money, which is the whole point of a shared pool and is exactly what the shipped
    sequential engine cannot do (each item compounds off its own equity there).
    FIXED: the sizing base stays Ci_fixed = 9000 * 50/100 = 4500 (doc 13 §14 test 12 — no
    auto-compounding), even though A(t) has fallen below the sum of the sleeves."""
    compounded = simulate(_loss_then_two_entries(), pool="10000", reserve_percent="10")
    fixed = simulate(_loss_then_two_entries(), pool="10000", reserve_percent="10", compound=False)

    for run in (compounded, fixed):
        assert run.tick_at(_HOURS[2]).snapshot.equity == Decimal("6000.00")
        assert run.tick_at(_HOURS[2]).snapshot.allocatable == Decimal("5000.00")

    assert dict(compounded.tick_at(_HOURS[2]).snapshot.sleeve_capacity) == {
        "a": Decimal("2500.00"),
        "b": Decimal("2500.00"),
    }
    assert dict(fixed.tick_at(_HOURS[2]).snapshot.sleeve_capacity) == {
        "a": Decimal("4500.00"),
        "b": Decimal("4500.00"),
    }


def test_jointly_insolvent_entries_reject_the_later_pin_whole_and_never_trim_it() -> None:
    """Modül 11 §5.3 — *"engine orderi reddeder, kismi fill veya sessiz borrow yapmaz"*
    (ADR §9.2, §14 A10); selection order is OD-3's recommended pin-order admission.

    FIXED mode at 02:00: A(t)=5000 but each fixed sleeve is still 4500, which is the one place
    genuine contention arises (ADR §9.1). A (pin 0) is capped by its sleeve to 4500 and fits.
    B (pin 1) is capped to 4500 too, but only 500 of solvency headroom is left. 500 buys 5
    units — and 5 units is exactly what must NOT be granted."""
    run = simulate(_loss_then_two_entries(), pool="10000", reserve_percent="10", compound=False)
    contended = run.tick_at(_HOURS[2])

    first = contended.report.by_item("a")
    assert first.outcome == "capped"
    assert first.granted_units == Decimal("45")
    assert first.granted_notional == Decimal("4500.00")
    assert first.binding_constraint == SLEEVE_CONSTRAINT

    second = contended.report.by_item("b")
    assert second.outcome == "rejected"
    assert second.granted_units == Decimal("0")
    assert second.granted_notional == Decimal("0")
    assert second.binding_constraint == SOLVENCY_CONSTRAINT
    assert second.reason == LEDGER_INSOLVENT
    # Not trimmed to the 5 units the remaining 500 would have bought.
    assert second.limits[SOLVENCY_CONSTRAINT] == Decimal("500.00")

    # And no borrow: committed 4500 against 5000 allocatable, reserve untouched.
    assert run.ledger.gross_exposure == Decimal("4500.00")
    assert run.ledger.gross_exposure <= contended.snapshot.allocatable
    assert run.ledger.equity - run.ledger.gross_exposure == Decimal("1500.00")


def test_a_rejected_items_sleeve_is_never_handed_to_the_admitted_sibling() -> None:
    """doc 13 §8.4/6 and §13 / ADR §14 A9: share structure is fixed for the life of the run
    snapshot. B's rejection releases 4500 of unused sleeve and A must not see a cent of it."""
    run = simulate(_loss_then_two_entries(), pool="10000", reserve_percent="10", compound=False)
    contended = run.tick_at(_HOURS[2])

    assert contended.snapshot.sleeve_capacity["b"] == Decimal("4500.00")
    assert contended.report.by_item("a").granted_notional == Decimal("4500.00")
    assert contended.report.released_capacity_reallocated is False
    for decision in contended.report.decisions:
        assert decision.diagnostics["share_transferred"] is False


def test_the_composition_wide_exposure_cap_clamps_the_later_pin_at_the_same_tick() -> None:
    """doc 13 §14 test 13 / Modül 11 §6.1: a CAP layer clamps where solvency would reject.

    Cap = 6000 with 5000/5000 sleeves. A takes 5000 untouched; B's exposure headroom is the
    remaining 1000, so it is admitted at 10 units — a smaller admitted order, not a partial
    fill."""
    items = [
        ScriptedItem(item_id="a", share="50", bars=_FLAT, entries={_HOURS[0]: ("long", "50")}),
        ScriptedItem(item_id="b", share="50", bars=_FLAT, entries={_HOURS[0]: ("long", "50")}),
    ]
    run = simulate(items, pool="10000", max_total_exposure_notional="6000")
    opening = run.ticks[0]

    assert opening.report.by_item("a").outcome == "admitted"
    assert opening.report.by_item("a").granted_units == Decimal("50")

    clamped = opening.report.by_item("b")
    assert clamped.outcome == "capped"
    assert clamped.granted_units == Decimal("10")
    assert clamped.binding_constraint == EXPOSURE_CONSTRAINT
    assert run.ledger.gross_exposure == Decimal("6000.00")


def test_an_opposite_direction_entry_is_blocked_and_leaves_the_pool_untouched() -> None:
    """doc 13 §8.4.6 under ``BLOCK_OPPOSITE``: the lower pinned item wins, the blocked item
    is traced with its counterparty, and the pool commits only the admitted side."""
    items = [
        ScriptedItem(item_id="a", share="50", bars=_FLAT, entries={_HOURS[0]: ("long", "20")}),
        ScriptedItem(item_id="b", share="50", bars=_FLAT, entries={_HOURS[0]: ("short", "20")}),
    ]
    run = simulate(items, pool="10000", policy="BLOCK_OPPOSITE")
    opening = run.ticks[0]

    assert opening.report.by_item("a").outcome == "admitted"
    blocked = opening.report.by_item("b")
    assert blocked.outcome == "blocked"
    assert blocked.counterparty_item_id == "a"
    assert blocked.conflict_source == "same_tick_intent"
    assert blocked.granted_units == Decimal("0")
    assert run.ledger.gross_exposure == Decimal("2000.00")
    assert opening.snapshot.sleeve_capacity["b"] == Decimal("5000.00")


def test_net_stays_fail_closed_for_the_whole_run_rather_than_downgrading() -> None:
    """GH #544 / ADR §9.4. Canon defines no netting price, no position custody and no PnL
    attribution for NET, so the unified path refuses the policy outright instead of running
    it as ``BLOCK_OPPOSITE`` and calling the result netting. Lifting the shared-capital
    containment does not make NET supported.

    Still driven by the LITERAL token after G14 decision ``B`` removed the enum member
    (migration 0044): a Backtest Result's pinned ``capital_execution`` snapshot is an
    immutable historical record, so the string can still arrive here even though no new plan
    can select it. What the removal changed is which branch of ``resolve_policy`` refuses
    it — the run still produces nothing, which is the property this test owns."""
    items = [
        ScriptedItem(item_id="a", share="50", bars=_FLAT, entries={_HOURS[0]: ("long", "20")}),
        ScriptedItem(item_id="b", share="50", bars=_FLAT, entries={_HOURS[0]: ("short", "20")}),
    ]
    with pytest.raises(UnsupportedConflictPolicyError) as raised:
        simulate(items, pool="10000", policy="NET")

    message = str(raised.value)
    assert "NET" in message
    # The refusal names what CAN be run, so the operator is not left guessing.
    assert "BLOCK_OPPOSITE" in message and "KEEP_SEPARATE" in message


# --------------------------------------------------- conservation and per-item totals


def _costed_pair() -> list[ScriptedItem]:
    """A run with every cost bucket exercised, so reconciliation has something to reconcile."""
    return [
        ScriptedItem(
            item_id="a",
            share="50",
            bars=_FLAT,
            entries={_HOURS[0]: ("long", "20")},
            exits={_HOURS[2]: "1500.00"},
            commissions={_HOURS[2]: "25.00"},
            funding={_HOURS[1]: "200.00"},
        ),
        ScriptedItem(
            item_id="b",
            share="50",
            bars=_FLAT,
            entries={_HOURS[1]: ("long", "20")},
            exits={_HOURS[3]: "-800.00"},
            commissions={_HOURS[3]: "15.00"},
            fees={_HOURS[2]: "50.00"},
        ),
    ]


def test_the_accounting_identity_is_exact_at_every_valuation_of_the_run() -> None:
    """``E(t) = P0 + realized - fees - funding - other`` (doc 13 §8.3), asserted as the
    published series rather than once at the end.

    00:00 10000 (no cost yet) · 01:00 9800 (A pays 200 funding) · 02:00 11225 (B's 50 fee
    then A's +1500 gross less 25 commission) · 03:00 10410 (B's -800 gross less 15)."""
    run = simulate(_costed_pair(), pool="10000", reserve_percent="10")

    assert [str(r.snapshot.equity) for r in run.ticks] == [
        "10000.00",
        "9800.00",
        "11225.00",
        "10410.00",
    ]
    assert run.ledger.equity == run.ledger.accounting_identity == Decimal("10410.00")
    assert run.ledger.realized_pnl == Decimal("700.00")  # +1500 - 800
    assert run.ledger.fees == Decimal("90.00")  # 25 + 15 commissions + 50 standalone
    assert run.ledger.funding == Decimal("200.00")


def test_per_item_rows_reconcile_with_the_portfolio_and_carry_their_own_costs() -> None:
    """ADR §14 reconciliation: the additive decomposition must close to ZERO residual, and
    each row must be the item's OWN scripted arithmetic.

    A: +1500 gross, 25 commission, 200 funding -> net 1275.
    B: -800 gross, 15 commission, 50 fee       -> net -865.
    Sum 410 = 10410 - 10000."""
    run = simulate(_costed_pair(), pool="10000", reserve_percent="10")
    report = attribute(ledger=run.ledger, t_ms=run.ticks[-1].t_ms, pin_ordinals={"a": 0, "b": 1})

    assert report.realized_residual == Decimal("0")
    assert report.realized_reconciled is True

    row_a = report.by_item("a")
    assert row_a.realized_pnl == Decimal("1500.00")
    assert row_a.fees == Decimal("25.00")
    assert row_a.funding == Decimal("200.00")
    assert row_a.net_realized == Decimal("1275.00")

    row_b = report.by_item("b")
    assert row_b.realized_pnl == Decimal("-800.00")
    assert row_b.fees == Decimal("65.00")
    assert row_b.net_realized == Decimal("-865.00")

    assert sum((r.net_realized for r in report.rows), Decimal("0")) == Decimal("410.00")
    assert report.equity - report.pool_initial == Decimal("410.00")


def test_a_cost_booked_before_the_valuation_moves_the_next_sleeve_not_the_last_one() -> None:
    """Funding and fees are P1 writers (ADR §8.2), so they land BEFORE ``E(t)`` is published
    and every item at that tick sizes against the reduced pool.

    P0=10000, r=0, 50/50. 01:00 A pays 200 funding -> E=9800, Ci=4900 each. 02:00 B pays a
    100 fee -> E=9700, Ci=4850 each."""
    items = [
        ScriptedItem(
            item_id="a",
            share="50",
            bars=_FLAT,
            entries={_HOURS[0]: ("long", "40")},
            funding={_HOURS[1]: "200.00"},
        ),
        ScriptedItem(item_id="b", share="50", bars=_FLAT, fees={_HOURS[2]: "100.00"}),
    ]
    run = simulate(items, pool="10000")

    assert run.ticks[0].snapshot.sleeve_capacity["b"] == Decimal("5000.00")
    assert run.tick_at(_HOURS[1]).snapshot.sleeve_capacity["b"] == Decimal("4900.00")
    assert run.tick_at(_HOURS[2]).snapshot.sleeve_capacity["a"] == Decimal("4850.00")
