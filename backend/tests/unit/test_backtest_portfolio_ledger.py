"""The ONE shared portfolio ledger — pure unit tests (ADR 0002 §7, ADIM 17).

Proves the arithmetic canon states in five lines and the repository has never executed:
``P0``/``R0``/``A0``/``Ci0``/``U0`` resolved once; ``E(t)`` realized-only and equal to
``P0 + realized - fees - funding - other`` to the cent at every point; ``Ci(t)`` derived from
ONE equity reading, recomputed under compound and frozen under fixed; a requested size clamped
by sleeve, item risk limit and exposure cap but REJECTED — never trimmed — by solvency; gross
and net exposure measured without netting anything; and a mark applied at one valuation point
that never touches ``E(t)``.

Every expected value here was computed by hand from the rule and written as a literal, in the
same spirit as ``tests/unit/oracles/``. Where a number can be traced to a shipped helper, the
test names that helper and compares against it (``sizing.sleeve_capital``,
``sizing._cap_to_sleeve``, ``allocation.rules.validate_allocation``, a real ``run_engine``
replay) — so the parity claims are checked rather than asserted.

Containment is part of the contract: nothing in production imports this layer, so the rollback
stays "delete the module" and no shipped digest can move because it exists.
"""

from __future__ import annotations

import time
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

import pytest

from entropia.domain.allocation.config import PortfolioAllocationConfigV1
from entropia.domain.allocation.rules import AllocationItemRef, validate_allocation
from entropia.domain.backtest.engine import run_engine
from entropia.domain.backtest.execution.costs import FillCosts
from entropia.domain.backtest.execution.portfolio_ledger import (
    EXPOSURE_CONSTRAINT,
    LEDGER_INSOLVENT,
    LEDGER_LAYER_REASONS,
    LEDGER_POLICY_VERSION,
    MARK_STALE_AFTER_MS,
    MAX_POSITION_CONSTRAINT,
    MAX_POSITION_NOTIONAL_EXCEEDED,
    MONEY_QUANTUM,
    MONEY_ROUNDING,
    NO_REQUESTED_SIZE,
    PORTFOLIO_MAX_TOTAL_EXPOSURE,
    QTY_QUANTUM,
    SLEEVE_CONSTRAINT,
    SLEEVE_ZERO_CAPACITY,
    SOLVENCY_CONSTRAINT,
    UNPRICEABLE_CAPACITY,
    InvalidCapitalPlanError,
    LedgerFrozenError,
    LedgerSolvencyViolation,
    MarkPrice,
    MismatchedSnapshotError,
    PortfolioLedger,
    PositionStateError,
    SleevePlan,
    UnknownLedgerItemError,
    build_sleeve_plan,
    ledger_for_items,
)
from entropia.domain.backtest.execution.sizing import _cap_to_sleeve, sleeve_capital
from entropia.domain.backtest.execution.state import AllocationExecution, _RunConfig
from entropia.domain.backtest.manifest import ENGINE_VERSION
from entropia.domain.mainboard.enums import MainboardItemKind

from .oracles.harness import bar, batched, entry_plan, flat_run, oracle_config

_ZERO = Decimal("0")

#: doc 13 §14 test 10 — the one worked example canon states as an acceptance criterion.
_DOC13_SHARES = {"item_a": Decimal("40"), "item_b": Decimal("35"), "item_c": Decimal("15")}


def _plan(
    *,
    pool: str = "10000",
    reserve: str = "10",
    shares: dict[str, Decimal] | None = None,
    compound: bool = True,
) -> SleevePlan:
    return build_sleeve_plan(
        pool_initial=Decimal(pool),
        reserve_percent=Decimal(reserve),
        shares=shares if shares is not None else dict(_DOC13_SHARES),
        compound=compound,
    )


def _ledger(**kwargs: object) -> PortfolioLedger:
    return PortfolioLedger(_plan(**kwargs))  # type: ignore[arg-type]


def _solo(
    *, pool: str = "10000", reserve: str = "10", share: str = "40", compound: bool = True
) -> PortfolioLedger:
    """A one-item pool — the shape ADR §3.2 makes the boundary of the whole programme."""
    return ledger_for_items(
        pool_initial=Decimal(pool),
        reserve_percent=Decimal(reserve),
        shares={"item_a": Decimal(share)},
        compound=compound,
    )


# ------------------------------------------------------------------ the capital structure


def test_the_initial_split_is_doc_13_acceptance_test_10() -> None:
    """P0=10,000, r=10% -> R0=1,000, A0=9,000; shares 40/35/15 -> 3,600 / 3,150 / 1,350 with
    U0=900. Doc 13 §14 test 10 states these six numbers verbatim; they are the only fully
    worked example canon gives, so they are the ledger's foundation test."""
    plan = _plan()

    assert plan.pool_initial == Decimal("10000.00")
    assert plan.reserve_nominal == Decimal("1000.00")
    assert plan.allocatable_initial == Decimal("9000.00")
    assert plan.initial_sleeves["item_a"] == Decimal("3600")
    assert plan.initial_sleeves["item_b"] == Decimal("3150")
    assert plan.initial_sleeves["item_c"] == Decimal("1350")
    assert plan.unallocated_initial == Decimal("900")


def test_the_initial_split_is_also_the_master_reference_worked_example() -> None:
    """Modül 11 §5.4 works the same pool with 40/30/20: 3,600 / 2,700 / 1,800, U0=900. Two
    independent statements of the same rule; both must land, or the rule is being read."""
    plan = _plan(
        shares={"a": Decimal("40"), "b": Decimal("30"), "c": Decimal("20")},
    )

    assert [plan.initial_sleeves[i] for i in ("a", "b", "c")] == [
        Decimal("3600"),
        Decimal("2700"),
        Decimal("1800"),
    ]
    assert plan.unallocated_initial == Decimal("900")


def test_the_ledger_agrees_with_the_allocation_preview_the_user_was_shown() -> None:
    """Modül 11 §5.1: *"Bu hesap Run Manifestte decimal deger olarak kaydedilir; UI preview
    ile engine arasinda fark olamaz."*

    The preview (``allocation.rules.validate_allocation`` -> ``DerivedAmounts``) and the
    ledger are two independent implementations of one formula, on opposite sides of the
    product. This is the test that stops them drifting. The preview quantizes for DISPLAY
    with ROUND_HALF_UP at the last step over the same unrounded arithmetic, which is why the
    comparison is on the parsed values."""
    config = PortfolioAllocationConfigV1.model_validate(
        {
            "enabled": True,
            "initial_capital": {"amount": "10000", "currency": "USDT"},
            "compounding_mode": "COMPOUND_PORTFOLIO_EQUITY",
            "reserve_cash_percent": "10",
            "entries": [
                {"composition_item_id": item, "active": True, "equity_share_percent": str(share)}
                for item, share in _DOC13_SHARES.items()
            ],
        }
    )
    refs = {
        item: AllocationItemRef(kind=MainboardItemKind.STRATEGY, available=True)
        for item in _DOC13_SHARES
    }
    _issues, derived = validate_allocation(config, item_refs=refs)
    assert derived is not None

    plan = _plan()
    assert Decimal(derived.reserved_cash) == plan.reserve_nominal
    assert Decimal(derived.capital_available) == plan.allocatable_initial
    assert Decimal(derived.unallocated) == plan.unallocated_initial
    assert {s.composition_item_id: Decimal(s.initial_sleeve_capital) for s in derived.sleeves} == {
        item: plan.initial_sleeves[item] for item in _DOC13_SHARES
    }


def test_compound_recomputes_every_sleeve_from_one_equity_reading() -> None:
    """Modül 11 §5.4, literally: *"portfolio equity 10,500 USDT ise R0 yine 1,000 USDT kalir;
    allocatable equity 9,500 USDT olur. Strategy Anin yeni pozisyonlar icin hedef sleevei
    3,800 USDT olur."*"""
    plan = _plan(compound=True)

    assert plan.allocatable(Decimal("10500")) == Decimal("9500")
    assert plan.sleeve_capacity(Decimal("10500"))["item_a"] == Decimal("3800")


def test_fixed_holds_the_sizing_base_at_the_run_start_sleeve() -> None:
    """Modül 11 §5.3: *"Ci_fixed zamanla degismez."* Doc 13 §14 test 12 makes it acceptance:
    a profit must not silently enlarge the next position. PnL is still booked — fixed mode
    refuses to let it move the sizing base, it does not hide it."""
    plan = _plan(compound=False)

    for equity in ("10500", "8000", "10000", "0"):
        assert plan.sleeve_capacity(Decimal(equity))["item_a"] == Decimal("3600")


def test_the_reserve_is_a_fixed_nominal_amount_across_a_drawdown() -> None:
    """Doc 13 §6.1: *"Reserve orani her barda current equitye yeniden uygulanmaz."* A ledger
    that re-applied 10% would hold back 500 at an equity of 5,000 and free capital exactly
    when the portfolio can least afford it — A11 in the ADR acceptance matrix."""
    plan = _plan(compound=True)

    assert plan.allocatable(Decimal("5000")) == Decimal("4000")
    assert plan.allocatable(Decimal("1000")) == _ZERO
    assert plan.allocatable(Decimal("500")) == _ZERO  # floored, never negative
    assert plan.reserve_nominal == Decimal("1000.00")


def test_a_negative_reserve_percent_cannot_inflate_the_pool() -> None:
    """It would otherwise drive A0 ABOVE P0 — capital from nowhere. Floored at 0, exactly as
    ``engine.resolve_allocation_execution`` floors it."""
    assert _plan(reserve="-25").allocatable_initial == Decimal("10000.00")


def test_a_reserve_larger_than_the_pool_leaves_nothing_allocatable() -> None:
    assert _plan(reserve="150").allocatable_initial == _ZERO
    assert _plan(reserve="150").initial_sleeves["item_a"] == _ZERO


@pytest.mark.parametrize("pool", ["0", "-1"])
def test_a_non_positive_pool_cannot_found_a_ledger(pool: str) -> None:
    with pytest.raises(InvalidCapitalPlanError):
        _plan(pool=pool)


def test_a_negative_share_is_refused() -> None:
    with pytest.raises(InvalidCapitalPlanError):
        _plan(shares={"a": Decimal("-1")})


def test_shares_totalling_over_one_hundred_percent_are_refused() -> None:
    """Doc 13 §10.1 / Modül 11 §7.1 make it a Ready-Check blocker. Refused here too, so a
    bypassed readiness state cannot seed a pool whose sleeves oversubscribe it."""
    with pytest.raises(InvalidCapitalPlanError):
        _plan(shares={"a": Decimal("60"), "b": Decimal("41")})


def test_a_zero_share_item_is_a_real_zero_capacity_sleeve_not_an_omission() -> None:
    """Doc 13 is explicit that an unallocated item must NOT fall back to its own capital
    (pinned for the single-item engine by ``test_an_unallocated_item_gets_no_sleeve...``).
    It stays a participating item with a zero sleeve, so the snapshot still values it."""
    ledger = ledger_for_items(
        pool_initial=Decimal("10000"),
        reserve_percent=Decimal("10"),
        shares={"item_a": Decimal("40"), "idle": _ZERO},
        compound=True,
    )
    snapshot = ledger.publish_snapshot(1)

    assert snapshot.sleeve_capacity["idle"] == _ZERO
    assert snapshot.remaining_sleeve_capacity("idle") == _ZERO
    assert set(snapshot.item_ids) == {"item_a", "idle"}


def test_unallocated_cash_is_reported_and_never_lent_to_a_hungry_item() -> None:
    """Doc 13 §6.1: *"fark unallocated cash olarak bosta kalir ve baska itemler tarafindan
    otomatik kullanilmaz."* U0=900 here; item_a asks for far more than its 3,600 sleeve and
    is capped at the sleeve, not topped up from U."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(1)

    assert snapshot.unallocated == Decimal("900")
    decision = ledger.resolve_capacity(
        item_id="item_a",
        snapshot=snapshot,
        requested_units=Decimal("1000"),
        price=Decimal("100"),
    )
    assert decision.outcome == "capped"
    assert decision.granted_units == Decimal("36")  # 3600 / 100 — the sleeve, not 4500
    assert decision.binding_constraint == SLEEVE_CONSTRAINT


# --------------------------------------------------------------------- accounting identity


def test_the_accounting_identity_holds_after_every_kind_of_booking() -> None:
    """``E(t) = P0 + realized - fees - funding - other_realized_costs`` (doc 13 §8.3). The
    four terms are booked through four different methods; the identity is what proves none of
    them writes into the wrong bucket or moves equity twice."""
    ledger = _ledger()

    ledger.book_trade("item_a", gross_pnl=Decimal("250.00"), commission=Decimal("4.00"))
    ledger.book_fee("item_b", amount=Decimal("1.50"))
    ledger.book_funding("item_a", amount=Decimal("7.25"))
    ledger.book_other_cost("item_c", amount=Decimal("0.75"))

    assert ledger.realized_pnl == Decimal("250.00")
    assert ledger.fees == Decimal("5.50")
    assert ledger.funding == Decimal("7.25")
    assert ledger.other_costs == Decimal("0.75")
    assert ledger.equity == Decimal("10236.50")
    assert ledger.accounting_identity == ledger.equity


def test_a_trade_books_gross_and_commission_apart_but_moves_equity_once() -> None:
    """``booking.py:94-96`` computes ``pnl = (gross - commission).quantize(0.01)`` and applies
    that ONE figure. Two equity writes would round twice and could land a cent from the
    per-item ledger this replaces — while doc 13 §8.3 still counts realized PnL and fees as
    two terms."""
    ledger = _ledger()
    applied = ledger.book_trade("item_a", gross_pnl=Decimal("100.00"), commission=Decimal("2.00"))

    assert applied == Decimal("98.00")
    assert ledger.realized_pnl == Decimal("100.00")
    assert ledger.fees == Decimal("2.00")
    assert ledger.equity == Decimal("10098.00")


def test_funding_paid_and_funding_received_move_equity_in_opposite_directions() -> None:
    """``costs.FundingCharge.amount`` is signed: positive = the position pays (a long under a
    positive perp rate), negative = it receives (a short). The ledger books the sign as given
    rather than taking an absolute value, which would make every short pay."""
    ledger = _ledger()
    ledger.book_funding("item_a", amount=Decimal("12.00"))
    assert ledger.equity == Decimal("9988.00")

    ledger.book_funding("item_b", amount=Decimal("-5.00"))
    assert ledger.equity == Decimal("9993.00")
    assert ledger.funding == Decimal("7.00")
    assert ledger.accounting_identity == ledger.equity


def test_spread_and_slippage_are_inside_the_price_and_are_never_booked_again() -> None:
    """The shipped cost model folds them into the FILL PRICE (``costs._effective_fill``)
    before any PnL exists, so a gross PnL already carries them. Booking them a second time as
    a cost line would double-count every fill.

    Checked against the engine's own numbers: a 1% slippage long in at 102 fills at 103.02 and
    out at 104 fills at 102.96, so the gross on 50 units is (102.96 - 103.02) x 50 = -3.00 —
    and the ledger's only cost lines stay empty."""
    costs = {"slippage_mode": "percentage_slippage", "slippage_value": "1"}
    out = run_engine(
        strategy_config=oracle_config(direction="long", protection={}, costs=costs),
        bar_batches=batched(_ORACLE_BARS, 8),
        execution_key="ledger_costs_key",
        indicator_plan=entry_plan(),
    )
    trade = out.trades[0]
    assert (trade.entry_price, trade.exit_price) == (Decimal("103.02"), Decimal("102.96"))

    ledger = _solo()
    gross = (trade.exit_price - trade.entry_price) * Decimal("50")
    ledger.book_trade("item_a", gross_pnl=gross)

    assert gross == Decimal("-3.00")
    assert ledger.equity - ledger.plan.pool_initial == trade.pnl
    assert (ledger.fees, ledger.funding, ledger.other_costs) == (_ZERO, _ZERO, _ZERO)


def test_the_bucket_records_the_delta_that_was_actually_applied() -> None:
    """The half-cent trap, and the reason the buckets are not accumulated independently.

    Rounding is translation-invariant across an exact multiple of the quantum only when the
    half-even tie-break agrees, and here it does not. At an equity of 10,000.01 a 0.005 fee
    makes the SUM 10,000.005, whose tie resolves to the even 10,000.00 — so a FULL cent is
    applied. The same fee rounded on its OWN is 0.00 (0 is even), so an independently
    accumulated ``fees`` would read 0.00 against an equity that moved by 0.01 and the identity
    would be off by a cent from the very first fill.

    Recording the delta the ledger actually applied is what makes that impossible."""
    ledger = _solo()
    ledger.book_trade("item_a", gross_pnl=Decimal("0.01"))
    assert ledger.equity == Decimal("10000.01")

    applied = ledger.book_fee("item_a", amount=Decimal("0.005"))

    assert Decimal("0.005").quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING) == _ZERO
    assert applied == Decimal("-0.01")
    assert ledger.fees == Decimal("0.01")
    assert ledger.equity == Decimal("10000.00")
    assert ledger.accounting_identity == ledger.equity


def test_equity_tracks_the_shipped_incremental_quantization_step_for_step() -> None:
    """``_Ledger.equity`` is quantized on the SUM at every mutation site (``booking.py:96``,
    ``engine.py:1953``). This replays a mixed sequence through a hand-written copy of that
    rule and asserts the shared ledger never diverges — the single-item reduction of ADR §3.2
    at the level of the account book itself."""
    ledger = _solo()
    shipped = ledger.plan.pool_initial
    for raw in ("12.345", "-0.005", "7.891", "-3.336", "0.004", "-99.999"):
        delta = Decimal(raw)
        shipped = (shipped + delta).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN)
        ledger.book_trade("item_a", gross_pnl=delta)
        assert ledger.equity == shipped
    assert ledger.accounting_identity == ledger.equity


def test_every_write_is_tagged_with_the_item_that_caused_it() -> None:
    """ADR §7: the pool is shared, so *"which item earned this"* is not recoverable from
    ``E(t)`` afterwards. It is recorded as the booking happens or it is gone."""
    ledger = _ledger()
    ledger.book_trade("item_a", gross_pnl=Decimal("300"), commission=Decimal("10"))
    ledger.book_funding("item_b", amount=Decimal("20"))

    assert ledger.attribution["item_a"].realized_pnl == Decimal("300")
    assert ledger.attribution["item_a"].fees == Decimal("10")
    assert ledger.attribution["item_a"].net_contribution == Decimal("290")
    assert ledger.attribution["item_b"].net_contribution == Decimal("-20")
    assert ledger.attribution["item_c"].net_contribution == _ZERO
    total = sum(a.net_contribution for a in ledger.attribution.values())
    assert ledger.plan.pool_initial + total == ledger.equity


@pytest.mark.parametrize(
    "call",
    [
        lambda led: led.book_trade("ghost", gross_pnl=Decimal("1")),
        lambda led: led.book_fee("ghost", amount=Decimal("1")),
        lambda led: led.book_funding("ghost", amount=Decimal("1")),
        lambda led: led.book_other_cost("ghost", amount=Decimal("1")),
        lambda led: led.set_position(
            "ghost", direction="long", size=Decimal("1"), entry_price=Decimal("1")
        ),
    ],
)
def test_an_item_outside_the_share_plan_is_refused(call) -> None:  # type: ignore[no-untyped-def]
    """An absent item would be valued by nothing at all; a zero share is the way to say
    "participates, has no capacity"."""
    with pytest.raises(UnknownLedgerItemError):
        call(_ledger())


# ------------------------------------------------------------------------ phase discipline


def test_publishing_the_snapshot_freezes_every_writer_until_the_apply_phase() -> None:
    """ADR §8.1: *"FROZEN: no writer may run until P7"*. Structural rather than a discipline —
    a booking inside the window would move ``E(t)`` under items that have already sized
    against it, which is the per-item drift the unified clock exists to remove."""
    ledger = _ledger()
    ledger.publish_snapshot(1_700_000_000_000)

    assert ledger.is_frozen
    with pytest.raises(LedgerFrozenError):
        ledger.book_trade("item_a", gross_pnl=Decimal("1"))
    with pytest.raises(LedgerFrozenError):
        ledger.set_position(
            "item_a", direction="long", size=Decimal("1"), entry_price=Decimal("100")
        )
    with pytest.raises(LedgerFrozenError):
        ledger.commit_tick(1_700_000_000_000)

    ledger.begin_apply(1_700_000_000_000)
    assert not ledger.is_frozen
    ledger.book_trade("item_a", gross_pnl=Decimal("1"))


def test_the_apply_phase_belongs_to_the_tick_that_published_the_snapshot() -> None:
    """Reopening at another instant would apply this tick's admitted work against the next
    tick's valuation — the phase order broken in a way no arithmetic would reveal."""
    ledger = _ledger()
    ledger.publish_snapshot(1_000)
    with pytest.raises(LedgerFrozenError):
        ledger.begin_apply(2_000)


def test_a_capacity_question_cannot_mix_two_valuation_points() -> None:
    """The sleeve headroom comes from the snapshot and the solvency headroom from the ledger.
    A snapshot from another tick would answer half the question from each — the per-item drift
    the unified clock exists to remove, arriving through the front door rather than through a
    missed phase order."""
    ledger = _ledger()
    stale = ledger.publish_snapshot(1_000)
    ledger.begin_apply(1_000)
    ledger.book_trade("item_a", gross_pnl=Decimal("500"))
    ledger.publish_snapshot(2_000)

    with pytest.raises(MismatchedSnapshotError):
        ledger.resolve_capacity(
            item_id="item_a",
            snapshot=stale,
            requested_units=Decimal("1"),
            price=Decimal("100"),
        )


def test_every_item_at_a_tick_is_handed_one_valuation_with_one_identity() -> None:
    """Doc 13 §8.3: *"Tum aktif itemler ayni snapshotla entry/scale intent uretir."* The
    snapshot is a value, so "the same one" is checkable as an identity equality rather than
    as object identity a serialization boundary would lose."""
    ledger = _ledger()
    ledger.book_trade("item_a", gross_pnl=Decimal("500"))
    snapshot = ledger.publish_snapshot(42)

    assert snapshot.equity == Decimal("10500.00")
    assert snapshot.allocatable == Decimal("9500.00")
    assert snapshot.sleeve_capacity["item_a"] == Decimal("3800")
    assert set(snapshot.deployed_notional) == set(_DOC13_SHARES)
    # Re-publishing the same unchanged ledger state is the same valuation, byte for byte.
    ledger.begin_apply(42)
    assert ledger.publish_snapshot(42).identity == snapshot.identity


# ---------------------------------------------------------------------- positions, exposure


def test_gross_exposure_is_the_capital_actually_committed() -> None:
    ledger = _ledger()
    ledger.set_position("item_a", direction="long", size=Decimal("10"), entry_price=Decimal("120"))
    ledger.set_position("item_b", direction="long", size=Decimal("5"), entry_price=Decimal("200"))

    assert ledger.gross_exposure == Decimal("2200.00")
    assert ledger.deployed_notional() == {
        "item_a": Decimal("1200.00"),
        "item_b": Decimal("1000.00"),
        "item_c": _ZERO,
    }
    assert ledger.available_capital == Decimal("6800.00")  # A0 9,000 - 2,200


def test_net_exposure_is_measured_and_offsets_nothing() -> None:
    """A long and an equal short net to zero as a MEASUREMENT, and free no capital: both
    positions still hold their notional and both still count against solvency. Netting
    semantics are undefined in canon (ADR §9.4, GH #544); computing a cap or a headroom from
    the net figure would ship ``NET`` by accident."""
    ledger = _ledger()
    ledger.set_position("item_a", direction="long", size=Decimal("10"), entry_price=Decimal("100"))
    ledger.set_position("item_b", direction="short", size=Decimal("10"), entry_price=Decimal("100"))

    assert ledger.net_exposure == _ZERO
    assert ledger.gross_exposure == Decimal("2000.00")
    assert ledger.available_capital == Decimal("7000.00")


def test_an_open_position_is_never_force_rebalanced_when_equity_falls() -> None:
    """Doc 13 §8.3 / §6.1: *"mevcut acik pozisyonlar equity degisti diye zorla rebalance
    edilmez."* So the no-borrow guard bounds the INCREASE in committed capital, never the
    standing total — a position already past its sleeve is left exactly as it is (OD-4(a),
    the literal canonical reading, recorded because the drift it permits is counter-intuitive)."""
    ledger = _ledger()
    ledger.set_position("item_a", direction="long", size=Decimal("30"), entry_price=Decimal("100"))
    ledger.book_funding("item_a", amount=Decimal("8000"))  # A(t) collapses to 1,000

    assert ledger.plan.allocatable(ledger.equity) == Decimal("1000.00")
    assert ledger.gross_exposure == Decimal("3000.00")
    assert ledger.available_capital == _ZERO
    assert ledger.positions["item_a"].size == Decimal("30")
    # ...and no further capital may be deployed while the pool is underwater.
    with pytest.raises(LedgerSolvencyViolation):
        ledger.set_position(
            "item_b", direction="long", size=Decimal("1"), entry_price=Decimal("100")
        )


def test_only_the_increase_in_committed_capital_is_checked_against_the_pool() -> None:
    """The guard bounds the DELTA, not the standing total — which is the whole content of
    "existing positions are never force-rebalanced" (doc 13 §8.3) once equity moves.

    Two directions, because bounding the total would break both: a scale-in that exactly
    consumes the remaining pool must be admitted, and a REDUCTION of a position that is
    already larger than the pool must never be refused for solvency — refusing it would trap
    an underwater item in a position it is trying to shrink."""
    ledger = ledger_for_items(
        pool_initial=Decimal("10000"),
        reserve_percent=_ZERO,
        shares={"item_a": Decimal("100")},
        compound=True,
    )
    ledger.set_position("item_a", direction="long", size=Decimal("60"), entry_price=Decimal("100"))
    assert ledger.available_capital == Decimal("4000.00")

    # Exactly consumes the headroom: increase 4,000 against 4,000 available.
    ledger.set_position("item_a", direction="long", size=Decimal("100"), entry_price=Decimal("100"))
    assert ledger.gross_exposure == Decimal("10000.00")
    assert ledger.available_capital == _ZERO

    ledger.book_trade("item_a", gross_pnl=Decimal("-9000"))
    assert ledger.plan.allocatable(ledger.equity) == Decimal("1000.00")

    # Shrinking while underwater is not a new deployment and must not be refused.
    ledger.set_position("item_a", direction="long", size=Decimal("50"), entry_price=Decimal("100"))
    assert ledger.gross_exposure == Decimal("5000.00")


def test_deploying_past_the_pool_is_refused_rather_than_silently_borrowed() -> None:
    """Reserve is capital active items cannot use (Modül 11 §5.1) and U is never auto-borrowed
    (doc 13 §6.1). Reaching this means a caller deployed without asking ``resolve_capacity``,
    so it fails closed instead of overdrawing."""
    ledger = _ledger()
    with pytest.raises(LedgerSolvencyViolation):
        ledger.set_position(
            "item_a", direction="long", size=Decimal("100"), entry_price=Decimal("100")
        )
    assert ledger.positions == {}


def test_closing_a_position_releases_its_capital_but_realizes_nothing_by_itself() -> None:
    """Releasing committed capital and realizing a result are two different ledger facts, and
    the engine emits them as two (``booking.close_position`` books the PnL; the position is
    dropped separately). Conflating them here would make a close that realizes nothing
    impossible to express."""
    ledger = _ledger()
    ledger.set_position("item_a", direction="long", size=Decimal("10"), entry_price=Decimal("100"))
    released = ledger.close_position("item_a")

    assert released.notional == Decimal("1000.00")
    assert ledger.gross_exposure == _ZERO
    assert ledger.equity == Decimal("10000.00")
    with pytest.raises(PositionStateError):
        ledger.close_position("item_a")


def test_a_held_position_cannot_be_reversed_in_place() -> None:
    """Flipping long to short in place would net the new notional against the old and check
    only the difference — but a reversal releases one commitment and takes another. The engine
    models it as a close then an open (``positions_replaced``); so must the ledger, or a
    reversal into a pool that cannot afford the new leg would pass the no-borrow guard."""
    ledger = _ledger()
    ledger.set_position("item_a", direction="long", size=Decimal("30"), entry_price=Decimal("100"))

    with pytest.raises(PositionStateError):
        ledger.set_position(
            "item_a", direction="short", size=Decimal("30"), entry_price=Decimal("100")
        )

    ledger.close_position("item_a")
    reopened = ledger.set_position(
        "item_a", direction="short", size=Decimal("30"), entry_price=Decimal("100")
    )
    assert reopened.direction == "short"
    assert ledger.net_exposure == Decimal("-3000.00")


@pytest.mark.parametrize(
    ("direction", "size"),
    [("sideways", Decimal("1")), ("long", _ZERO), ("long", Decimal("-1"))],
)
def test_a_position_must_have_a_known_direction_and_a_positive_size(
    direction: str, size: Decimal
) -> None:
    ledger = _ledger()
    with pytest.raises(PositionStateError):
        ledger.set_position("item_a", direction=direction, size=size, entry_price=Decimal("100"))


# ------------------------------------------------------------------------------- valuation


def test_a_mark_reports_unrealized_pnl_and_never_moves_equity() -> None:
    """Doc 13 §8.3's ``E(t)`` is realized-only. Sizing the next entry off a marked-to-market
    equity would be a different, uncanonical capital model — so the unrealized figure is
    reported beside ``E(t)``, never folded into it."""
    ledger = _ledger()
    ledger.set_position("item_a", direction="long", size=Decimal("10"), entry_price=Decimal("100"))
    ledger.set_position("item_b", direction="short", size=Decimal("4"), entry_price=Decimal("50"))

    valuation = ledger.valuation(
        7,
        {
            "item_a": MarkPrice(price=Decimal("110"), authority="fresh_bar_close", staleness_ms=0),
            "item_b": MarkPrice(price=Decimal("45"), authority="fresh_bar_close", staleness_ms=0),
        },
    )

    assert valuation.unrealized_pnl == Decimal("120.00")  # +100 long, +20 short
    assert valuation.equity == Decimal("10000.00") == ledger.equity
    assert valuation.marked_gross_exposure == Decimal("1280.00")
    assert valuation.marked_net_exposure == Decimal("920.00")
    assert valuation.unmarked_items == ()


def test_an_unmarkable_position_is_reported_rather_than_valued_at_zero() -> None:
    """OD-2 is open: how a position with no fresh bar is marked is a decision canon does not
    supply. Reporting a partial unrealized figure would state a portfolio value that nobody
    computed; ``None`` plus the item id states exactly what is known."""
    ledger = _ledger()
    ledger.set_position("item_a", direction="long", size=Decimal("10"), entry_price=Decimal("100"))
    ledger.set_position("item_b", direction="long", size=Decimal("2"), entry_price=Decimal("50"))

    valuation = ledger.valuation(
        7, {"item_a": MarkPrice(price=Decimal("110"), authority="fresh_bar_close")}
    )

    assert valuation.unmarked_items == ("item_b",)
    assert valuation.unrealized_pnl is None
    assert valuation.marked_gross_exposure is None
    assert valuation.marked_net_exposure is None
    # The entry-basis figures the caps read are unaffected — they need no mark.
    assert valuation.gross_exposure == Decimal("1100.00")
    assert valuation.gross_exposure_percent == Decimal("11.00")


def test_a_carried_forward_mark_values_a_position_only_within_the_od2_bound() -> None:
    """OD-2(a), BUILT (ADIM 20): carry the last closed bar's close forward under a declared
    ``stale_after`` bound, with a diagnostic counter.

    This test replaces ``..._staleness_is_recorded_not_judged``, which asserted the OPPOSITE
    and was correct until the bound landed: before ADIM 20 the ledger recorded staleness and
    refused to judge it, because judging without recording the policy would have shipped the
    OD-2 decision unrecorded. It is now recorded — ``carry_forward_bounded_v1`` in the run
    manifest — so the judgment is finally honest to make.

    Both sides of the bound are exercised. Asserting only the refusal would pass under a
    policy that refused EVERY carry-forward, which is the fail-closed zero-bound the PO
    explicitly did not choose (it would nullify the carry-forward (a) selected)."""
    ledger = _ledger()
    ledger.set_position("item_a", direction="long", size=Decimal("10"), entry_price=Decimal("100"))
    within = MarkPrice(
        price=Decimal("105"), authority="stale_last_close", staleness_ms=MARK_STALE_AFTER_MS
    )
    beyond = MarkPrice(
        price=Decimal("105"), authority="stale_last_close", staleness_ms=MARK_STALE_AFTER_MS + 1
    )
    unavailable = MarkPrice(price=Decimal("105"), authority="unavailable")

    # carry-forward still happens — the bound is a bound, not a ban.
    assert within.is_usable
    assert not within.is_stale_refused
    assert ledger.valuation(7, {"item_a": within}).unrealized_pnl == Decimal("50.00")

    # one millisecond past it, the position is REPORTED, never valued at zero.
    assert not beyond.is_usable
    assert beyond.is_stale_refused
    aged = ledger.valuation(7, {"item_a": beyond})
    assert aged.unrealized_pnl is None
    assert aged.marked_gross_exposure is None
    assert aged.unmarked_items == ("item_a",)
    assert aged.stale_refused_items == ("item_a",)

    # the counter is NARROWER than "unmarked": an unavailable authority is not an age event,
    # so counting it as one would over-report staleness.
    assert not unavailable.is_usable
    assert not unavailable.is_stale_refused
    absent = ledger.valuation(7, {"item_a": unavailable})
    assert absent.unmarked_items == ("item_a",)
    assert absent.stale_refused_items == ()


def test_a_non_positive_mark_price_cannot_value_a_position() -> None:
    ledger = _solo()
    ledger.set_position("item_a", direction="long", size=Decimal("1"), entry_price=Decimal("100"))
    broken = MarkPrice(price=_ZERO, authority="fresh_bar_close")
    assert ledger.valuation(1, {"item_a": broken}).unmarked_items == ("item_a",)


# -------------------------------------------------------------------------- the equity curve


def test_one_point_is_appended_per_tick_at_which_equity_moved() -> None:
    """ADR §7: a point at every tick would add flat repeats and no information, because
    ``E(t)`` is realized-only and moves at exactly three kinds of event. The seed point plus
    "append when it moved" captures every movement exactly."""
    ledger = _solo()
    assert [p.seq for p in ledger.equity_points] == [0]

    ledger.book_trade("item_a", gross_pnl=Decimal("100"))
    assert ledger.commit_tick(1_000) is not None
    assert ledger.commit_tick(2_000) is None  # nothing moved
    ledger.book_funding("item_a", amount=Decimal("25"))
    point = ledger.commit_tick(3_000)

    assert point is not None
    assert (point.seq, point.t_ms, point.equity) == (2, 3_000, Decimal("10075.00"))
    assert point.drawdown == Decimal("25.00")
    assert [p.t_ms for p in ledger.equity_points] == [None, 1_000, 3_000]


def test_the_portfolio_curve_is_time_ordered_by_construction() -> None:
    """Removal condition #5 in ``allocation/capability.py``. The shipped composite curve is
    not a time series at all — it concatenates finished per-item runs in pin order, so its
    stamps carry item-order time. Here the stamps are the axis, so ordering is not something
    the ledger has to get right; it is something it cannot get wrong."""
    ledger = _ledger()
    for tick, pnl in enumerate(("10", "-40", "35", "-5"), start=1):
        ledger.book_trade("item_a" if tick % 2 else "item_b", gross_pnl=Decimal(pnl))
        ledger.commit_tick(tick * 60_000)

    stamps = [p.t_ms for p in ledger.equity_points if p.t_ms is not None]
    assert stamps == sorted(stamps)
    assert len(stamps) == 4


# ----------------------------------------------------------------------------- the capacity


def test_the_sleeve_caps_a_size_the_strategy_asked_for() -> None:
    """Doc 13 §8.3: ``allowed_size = min(desired, remaining_sleeve_capacity, ...)``. The cap
    layers CLAMP (doc 13 §14 test 13 — a deterministic cap or reject)."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(1)
    decision = ledger.resolve_capacity(
        item_id="item_b",
        snapshot=snapshot,
        requested_units=Decimal("100"),
        price=Decimal("105"),
    )

    assert decision.outcome == "capped"
    assert decision.granted_units == Decimal("30")  # 3150 / 105
    assert decision.granted_notional == Decimal("3150.00")
    assert decision.binding_constraint == SLEEVE_CONSTRAINT
    assert decision.policy_version == LEDGER_POLICY_VERSION


def test_a_request_inside_every_layer_is_admitted_untouched() -> None:
    ledger = _ledger()
    decision = ledger.resolve_capacity(
        item_id="item_a",
        snapshot=ledger.publish_snapshot(1),
        requested_units=Decimal("5"),
        price=Decimal("100"),
    )

    assert decision.outcome == "admitted"
    assert decision.granted_units == Decimal("5")
    assert decision.binding_constraint is None
    assert decision.reason is None
    assert decision.is_admitted


def test_a_spent_sleeve_rejects_in_the_engines_own_vocabulary() -> None:
    """``sizing.blocked_reason`` already writes ``sleeve_zero_capacity`` into the decision
    trace. Reusing the token keeps one vocabulary; a second one would make the same refusal
    read two ways depending on which layer produced it."""
    ledger = _ledger()
    ledger.set_position("item_a", direction="long", size=Decimal("36"), entry_price=Decimal("100"))
    decision = ledger.resolve_capacity(
        item_id="item_a",
        snapshot=ledger.publish_snapshot(1),
        requested_units=Decimal("1"),
        price=Decimal("100"),
    )

    assert decision.outcome == "rejected"
    assert decision.reason == SLEEVE_ZERO_CAPACITY
    assert decision.binding_constraint == SLEEVE_CONSTRAINT
    assert decision.granted_units == _ZERO


def test_the_exposure_cap_clamps_and_a_spent_cap_blocks() -> None:
    """The composition-wide Max Total Exposure of doc 13 §8.4, with the shipped engine's own
    token (``engine.py:1474``) and the shipped shape: over-cap clamps down, zero headroom
    blocks outright — never a phantom over-cap trade."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(1)
    clamped = ledger.resolve_capacity(
        item_id="item_a",
        snapshot=snapshot,
        requested_units=Decimal("20"),
        price=Decimal("100"),
        max_total_exposure_notional=Decimal("1500"),
    )
    assert clamped.outcome == "capped"
    assert clamped.granted_units == Decimal("15")
    assert clamped.binding_constraint == EXPOSURE_CONSTRAINT

    ledger.begin_apply(1)
    ledger.set_position("item_b", direction="long", size=Decimal("15"), entry_price=Decimal("100"))
    blocked = ledger.resolve_capacity(
        item_id="item_a",
        snapshot=ledger.publish_snapshot(2),
        requested_units=Decimal("1"),
        price=Decimal("100"),
        max_total_exposure_notional=Decimal("1500"),
    )
    assert blocked.outcome == "rejected"
    assert blocked.reason == PORTFOLIO_MAX_TOTAL_EXPOSURE


def test_an_item_risk_limit_caps_only_when_the_caller_supplies_one() -> None:
    """Modül 11 §6.1 puts item risk limits at layer 3, whose authority is Strategy Details
    (``sizing._clamp_to_limits`` at P6a). The ledger honours one it is handed and never
    invents one — an omitted limit is absent from ``limits``, not a fabricated infinity."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(1)

    capped = ledger.resolve_capacity(
        item_id="item_a",
        snapshot=snapshot,
        requested_units=Decimal("20"),
        price=Decimal("100"),
        max_position_notional=Decimal("800"),
    )
    assert capped.outcome == "capped"
    assert capped.granted_units == Decimal("8")
    assert capped.binding_constraint == MAX_POSITION_CONSTRAINT

    zero = ledger.resolve_capacity(
        item_id="item_a",
        snapshot=snapshot,
        requested_units=Decimal("20"),
        price=Decimal("100"),
        max_position_notional=_ZERO,
    )
    assert zero.reason == MAX_POSITION_NOTIONAL_EXCEEDED

    unlimited = ledger.resolve_capacity(
        item_id="item_a", snapshot=snapshot, requested_units=Decimal("20"), price=Decimal("100")
    )
    assert MAX_POSITION_CONSTRAINT not in unlimited.limits


def test_a_solvency_shortfall_rejects_the_whole_order_and_never_trims_it() -> None:
    """Modül 11 §5.3: *"Ledger insolvency veya gerekli teminat yetersizse engine orderi
    reddeder, kismi fill veya sessiz borrow yapmaz."*

    Fixed mode is where this genuinely bites (ADR §9.1): the sleeves stay at ``Ci_fixed``
    while ``A(t)`` falls below them, so a request that fits its sleeve no longer fits the
    pool. The cap layers would have granted 30 units; solvency grants none."""
    ledger = ledger_for_items(
        pool_initial=Decimal("10000"),
        reserve_percent=Decimal("10"),
        shares={"item_a": Decimal("40"), "item_b": Decimal("35")},
        compound=False,
    )
    ledger.book_trade("item_b", gross_pnl=Decimal("-8500"))
    assert ledger.plan.allocatable(ledger.equity) == Decimal("500.00")

    decision = ledger.resolve_capacity(
        item_id="item_a",
        snapshot=ledger.publish_snapshot(1),
        requested_units=Decimal("30"),
        price=Decimal("100"),
    )

    assert decision.outcome == "rejected"
    assert decision.reason == LEDGER_INSOLVENT
    assert decision.binding_constraint == SOLVENCY_CONSTRAINT
    assert decision.granted_units == _ZERO
    assert decision.limits[SLEEVE_CONSTRAINT] == Decimal("3600")  # the sleeve still fits
    assert decision.limits[SOLVENCY_CONSTRAINT] == Decimal("500.00")  # the pool does not


def test_the_decision_reports_every_layers_headroom_not_only_the_binding_one() -> None:
    """A reviewer reading a capped fill needs the layer that bound it AND the ones that did
    not — otherwise "why was this 8 units" is unanswerable from the trace alone."""
    ledger = _ledger()
    decision = ledger.resolve_capacity(
        item_id="item_a",
        snapshot=ledger.publish_snapshot(1),
        requested_units=Decimal("20"),
        price=Decimal("100"),
        max_position_notional=Decimal("800"),
        max_total_exposure_notional=Decimal("5000"),
    )

    assert decision.limits == {
        SLEEVE_CONSTRAINT: Decimal("3600"),
        MAX_POSITION_CONSTRAINT: Decimal("800"),
        EXPOSURE_CONSTRAINT: Decimal("5000"),
        SOLVENCY_CONSTRAINT: Decimal("9000.00"),
    }
    assert decision.requested_notional == Decimal("2000.00")
    assert decision.granted_notional == Decimal("800.00")


@pytest.mark.parametrize(
    ("units", "price", "reason"),
    [
        (_ZERO, Decimal("100"), NO_REQUESTED_SIZE),
        (Decimal("-1"), Decimal("100"), NO_REQUESTED_SIZE),
        (Decimal("1"), _ZERO, UNPRICEABLE_CAPACITY),
        (Decimal("1"), Decimal("-5"), UNPRICEABLE_CAPACITY),
    ],
)
def test_an_unaskable_request_is_refused_rather_than_priced(
    units: Decimal, price: Decimal, reason: str
) -> None:
    """A capacity in money cannot become units without a price, and a fabricated one would
    size a real order — the same reason ``_cap_to_sleeve`` returns 0 for a non-positive
    price."""
    ledger = _ledger()
    decision = ledger.resolve_capacity(
        item_id="item_a",
        snapshot=ledger.publish_snapshot(1),
        requested_units=units,
        price=price,
    )
    assert decision.outcome == "rejected"
    assert decision.reason == reason


def test_the_same_question_gets_the_same_answer_every_time() -> None:
    """Determinism at the layer, not just in the axis: no set/dict iteration, no wall clock,
    no randomness (ADR §11)."""
    ledger = _ledger()
    snapshot = ledger.publish_snapshot(1)
    answers = [
        ledger.resolve_capacity(
            item_id="item_a",
            snapshot=snapshot,
            requested_units=Decimal("77.12345678"),
            price=Decimal("103.7"),
            max_total_exposure_notional=Decimal("4000"),
        )
        for _ in range(5)
    ]
    assert all(answer == answers[0] for answer in answers)
    assert answers[0].granted_units == Decimal("34.71552555")  # 3600 / 103.7, quantized to 1e-8


def test_the_reason_vocabulary_this_layer_adds_is_closed_and_does_not_shadow_the_engine() -> None:
    """Only the states that exist once capital is genuinely shared are new. The two reused
    tokens are the engine's own, so a rejection reads in one vocabulary."""
    assert {
        NO_REQUESTED_SIZE,
        UNPRICEABLE_CAPACITY,
        MAX_POSITION_NOTIONAL_EXCEEDED,
        LEDGER_INSOLVENT,
    } == LEDGER_LAYER_REASONS
    assert SLEEVE_ZERO_CAPACITY not in LEDGER_LAYER_REASONS
    assert PORTFOLIO_MAX_TOTAL_EXPOSURE not in LEDGER_LAYER_REASONS


# ------------------------------------------------------------- two items, one shared pool


def test_two_items_compete_for_one_pool_without_a_directional_conflict() -> None:
    """The point of the whole programme, in one fixture: both items are LONG, so nothing here
    is a conflict decision (that is ADIM 19 / GH #544). They compete only for cash.

    Fixed mode, P0=10,000, r=0 -> A0=10,000, shares 60/40 -> sleeves 6,000 / 4,000. Item B
    loses 6,000, so A(t) falls to 4,000. Item A's sleeve still says 6,000 and its own request
    of 5,000 fits it — but the pool holds 4,000, so the order is REJECTED whole. A 4,000
    partial fill would be exactly the silent trim canon forbids."""
    ledger = ledger_for_items(
        pool_initial=Decimal("10000"),
        reserve_percent=_ZERO,
        shares={"item_a": Decimal("60"), "item_b": Decimal("40")},
        compound=False,
    )
    ledger.book_trade("item_b", gross_pnl=Decimal("-6000"))
    snapshot = ledger.publish_snapshot(1)

    a = ledger.resolve_capacity(
        item_id="item_a", snapshot=snapshot, requested_units=Decimal("50"), price=Decimal("100")
    )
    b = ledger.resolve_capacity(
        item_id="item_b", snapshot=snapshot, requested_units=Decimal("10"), price=Decimal("100")
    )

    assert a.outcome == "rejected"
    assert a.reason == LEDGER_INSOLVENT
    assert b.outcome == "admitted"  # 1,000 fits both its sleeve and the pool
    assert snapshot.identity == ledger.publish_snapshot(1).identity  # one valuation, both items


def test_a_rejected_items_share_is_never_transferred_to_its_sibling() -> None:
    """Doc 13 §8.4 step 6 / §13, Modül 11 §6.3: *"o itemin sharei diger itemlere run icinde
    otomatik devredilmez."* The share structure is fixed for the life of the run snapshot, so
    a rejection must leave every OTHER sleeve exactly where it was."""
    ledger = _ledger()
    before = dict(ledger.publish_snapshot(1).sleeve_capacity)
    ledger.begin_apply(1)
    ledger.set_position("item_a", direction="long", size=Decimal("36"), entry_price=Decimal("100"))

    snapshot = ledger.publish_snapshot(2)
    rejected = ledger.resolve_capacity(
        item_id="item_a", snapshot=snapshot, requested_units=Decimal("1"), price=Decimal("100")
    )

    assert rejected.outcome == "rejected"
    assert snapshot.sleeve_capacity["item_b"] == before["item_b"]
    assert snapshot.sleeve_capacity["item_c"] == before["item_c"]
    assert snapshot.unallocated == Decimal("900")


# ------------------------------------------------------------------- single-item parity

_ORACLE_BARS = [
    *flat_run(),
    bar(21, "100", "102", "100", "102"),
    bar(22, "102", "104", "102", "104"),
]


def _run_config(*, compound: bool, share: str, pool: str = "100000.00") -> _RunConfig:
    """The shipped ``sleeve_capital`` reads exactly these five fields off ``_RunConfig``."""
    allocation = AllocationExecution(
        initial_capital=Decimal(pool),
        reserve_percent=Decimal("10"),
        compound=compound,
        item_share_percent=Decimal(share),
        currency="USD",
    )
    p0 = Decimal(pool).quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING)
    reserve_nominal = p0 * allocation.reserve_percent / Decimal("100")
    return _RunConfig(
        config=oracle_config(),
        fill_costs=FillCosts(_ZERO, _ZERO, _ZERO),
        alloc_on=True,
        alloc_compound=compound,
        allocatable_initial=max(_ZERO, p0 - reserve_nominal),
        item_share=allocation.item_share_percent,
        reserve_nominal=reserve_nominal,
        portfolio_rules=None,
        sizing_ok=True,
        leverage_ok=True,
        strength_ok=True,
        capability_ok=True,
    )


@pytest.mark.parametrize("compound", [True, False])
@pytest.mark.parametrize("share", ["5", "40", "0"])
@pytest.mark.parametrize("equity", ["100000.00", "120000.00", "50000.00", "9000.00"])
def test_the_shared_sleeve_equals_the_shipped_per_item_sleeve(
    compound: bool, share: str, equity: str
) -> None:
    """ADR §3.2's single-item reduction, at the level of the sleeve formula: with one item the
    shared ledger's ``Ci(t)`` must be the number ``sizing.sleeve_capital`` already produces.
    Checked across both modes, three shares (including the zero sleeve) and four equities —
    including one below the reserve, where the floor bites."""
    ctx = _run_config(compound=compound, share=share)
    plan = build_sleeve_plan(
        pool_initial=Decimal("100000.00"),
        reserve_percent=Decimal("10"),
        shares={"item_a": Decimal(share)},
        compound=compound,
    )

    assert plan.sleeve_capacity(Decimal(equity))["item_a"] == sleeve_capital(ctx, Decimal(equity))


@pytest.mark.parametrize("price", ["102", "0.37", "1999.99"])
@pytest.mark.parametrize("desired", ["1000000", "1", "0.00000001"])
def test_granted_units_quantize_exactly_like_the_shipped_sleeve_cap(
    price: str, desired: str
) -> None:
    """``sizing._cap_to_sleeve`` is ``min(desired, (sleeve / price).quantize(1e-8))``. The
    ledger's cap layer must land on the same unit, or a shared run and a single-item run would
    fill different sizes from the same sleeve."""
    ledger = ledger_for_items(
        pool_initial=Decimal("100000.00"),
        reserve_percent=Decimal("10"),
        shares={"item_a": Decimal("5")},
        compound=False,
    )
    decision = ledger.resolve_capacity(
        item_id="item_a",
        snapshot=ledger.publish_snapshot(1),
        requested_units=Decimal(desired),
        price=Decimal(price),
    )

    assert decision.granted_units == _cap_to_sleeve(
        Decimal(desired), Decimal("4500"), Decimal(price)
    )


def test_the_shared_ledger_reproduces_the_single_item_sleeve_oracle() -> None:
    """The parity that matters: the shipped oracle
    ``test_the_sleeve_caps_a_size_the_strategy_asked_for`` pins P0=100,000 / r=10% / wi=5% ->
    Ci=4,500, a 4,500/102 = 44.11764706-unit fill, pnl 88.24 and a final book of 100,088.24.
    Driving the SHARED ledger by hand over the same run must land on the same four numbers.

    Non-tautological on both ends: the size comes from ``resolve_capacity`` (not from the
    engine), the PnL is computed from the engine's own emitted entry/exit prices (not from
    ``TradeRow.pnl``), and the engine is actually run in the same test to supply them."""
    out = run_engine(
        strategy_config=oracle_config(
            direction="long",
            protection={},
            sizing={"method": "base_position_size", "base_position_size": "1000000"},
        ),
        bar_batches=batched(_ORACLE_BARS, 8),
        execution_key="ledger_parity_key",
        indicator_plan=entry_plan(),
        allocation=AllocationExecution(
            initial_capital=Decimal("100000.00"),
            reserve_percent=Decimal("10"),
            compound=False,
            item_share_percent=Decimal("5"),
            currency="USD",
        ),
    )
    fill = next(e for e in out.signal_events if e.event_type == "entry_fill")
    engine_size = Decimal(str(fill.detail["size"]))
    trade = out.trades[0]

    ledger = ledger_for_items(
        pool_initial=Decimal("100000.00"),
        reserve_percent=Decimal("10"),
        shares={"item_a": Decimal("5")},
        compound=False,
    )
    admitted = ledger.resolve_capacity(
        item_id="item_a",
        snapshot=ledger.publish_snapshot(1),
        requested_units=Decimal("1000000"),
        price=trade.entry_price,
    )
    ledger.begin_apply(1)
    ledger.set_position(
        "item_a", direction="long", size=admitted.granted_units, entry_price=trade.entry_price
    )
    ledger.close_position("item_a")
    ledger.book_trade(
        "item_a", gross_pnl=(trade.exit_price - trade.entry_price) * admitted.granted_units
    )
    ledger.commit_tick(2)

    assert admitted.granted_units == Decimal("44.11764706") == engine_size
    assert ledger.equity - ledger.plan.pool_initial == trade.pnl == Decimal("88.24")
    assert ledger.equity == out.summary["final_equity"] == Decimal("100088.24")
    assert ledger.accounting_identity == ledger.equity


def test_a_zero_share_item_fills_nothing_exactly_as_the_engine_refuses_to() -> None:
    """The shipped oracle ``test_an_unallocated_item_gets_no_sleeve_and_therefore_no_fill``
    asserts the engine opens nothing and the book stays at P0. The shared ledger must refuse
    the same request rather than fall back to any other capital figure."""
    ledger = ledger_for_items(
        pool_initial=Decimal("100000.00"),
        reserve_percent=Decimal("10"),
        shares={"item_a": _ZERO},
        compound=False,
    )
    decision = ledger.resolve_capacity(
        item_id="item_a",
        snapshot=ledger.publish_snapshot(1),
        requested_units=Decimal("50"),
        price=Decimal("102"),
    )

    assert decision.outcome == "rejected"
    assert decision.reason == SLEEVE_ZERO_CAPACITY
    assert ledger.equity == Decimal("100000.00")


# ---------------------------------------------------------------------- performance sanity


def test_a_valuation_point_stays_linear_in_the_item_count() -> None:
    """Performance sanity, not a benchmark: publishing one snapshot and answering every
    item's capacity question must stay linear in the item count — the one loop the whole
    programme exists to make linear. The wall-clock bound is a smoke guard against an
    accidental quadratic, deliberately generous for a shared CI box."""
    item_count, tick_count = 150, 20
    shares = {f"item_{n:03d}": Decimal("0.5") for n in range(item_count)}
    ledger = ledger_for_items(
        pool_initial=Decimal("1000000"),
        reserve_percent=Decimal("10"),
        shares=shares,
        compound=True,
    )
    started = time.monotonic()
    decisions = 0
    for tick in range(1, tick_count + 1):
        snapshot = ledger.publish_snapshot(tick * 60_000)
        assert len(snapshot.sleeve_capacity) == item_count
        for item_id in shares:
            decision = ledger.resolve_capacity(
                item_id=item_id,
                snapshot=snapshot,
                requested_units=Decimal("1"),
                price=Decimal("100"),
            )
            assert decision.outcome == "admitted"
            decisions += 1
        ledger.begin_apply(tick * 60_000)

    assert decisions == item_count * tick_count
    assert time.monotonic() - started < 20.0


# ------------------------------------------------------------------------------ containment


def test_the_shared_ledger_is_reachable_only_through_the_phase_loop() -> None:
    """ADR §12: the ADIM 17 rollback is "revert; the single-item path is untouched", and it
    stays true only while nothing reaches this module. When the phase loop wires
    ``run_portfolio`` in, this is the test that must be updated deliberately — it should never
    fail by accident.

    **Widened deliberately at `C3` (E4c), by ONE NAMED module.** ``domain/backtest/participant.py``
    is the engine-backed ``ItemParticipant`` adapter; it names the phase loop's own types in
    its signatures, so it cannot exist without appearing here. It sits OUTSIDE ``execution/``
    on purpose — inside, the containment gate's importer scan would have exempted it and the
    guard would have gone blind rather than satisfied. The widening is a named entry, never a
    wildcard, so a THIRD importer is still a red build. Signed 2026-08-18, Option A:
    ``docs/decisions/closure_participant_importer_allowlist_2026-08-18.md``.

    It has been updated deliberately once, in the same shape the clock's and the intent
    layer's own containment tests were: the cross-item arbitration layer
    (``execution/arbitration.py``) asks this ledger the capacity question, so it is named here
    as the ONE permitted importer rather than the assertion being loosened to "some importers
    are fine". That module is itself contained — ``test_backtest_cross_item_arbitration.py``
    asserts nothing imports IT — so the property this test defends is unchanged: no production
    path reaches the shared ledger, and the rollback is still "delete the modules".

    Updated deliberately again (ADIM 19): ``execution/attribution.py`` decomposes this
    ledger into per-item rows and ``execution/provenance.py`` pins its policy version and
    equity series into the manifest. Both are contained; their own test files assert nothing
    imports THEM.

    **ADIM 18 adds ``portfolio_engine.py``, which is NOT contained — it is the production
    phase loop, and it is the only writer.** Every ledger mutation in a shared run happens
    inside ``run_portfolio``'s P1/P3/P7/P9, in that order, between one ``publish_snapshot``
    and one ``commit_tick``. That single-writer property is what the freeze discipline
    enforces at runtime; this list is what stops a second writer appearing at all. The ADIM 17
    rollback is unchanged in substance: revert the loop and the single-item path — which never
    reaches this module — is untouched."""
    src = Path(__file__).resolve().parents[2] / "src" / "entropia"
    importers = sorted(
        path.relative_to(src).as_posix()
        for path in src.rglob("*.py")
        if path.name != "portfolio_ledger.py"
        and _imports_portfolio_ledger(path.read_text(encoding="utf-8"))
    )
    assert importers == [
        "domain/backtest/execution/arbitration.py",
        "domain/backtest/execution/attribution.py",
        "domain/backtest/execution/provenance.py",
        "domain/backtest/participant.py",
        "domain/backtest/portfolio_engine.py",
    ]


def _imports_portfolio_ledger(source: str) -> bool:
    """Every spelling that would actually import the module — matching only the dotted path
    would pin the rollback for one import style and quietly unpin it for two."""
    return (
        "execution.portfolio_ledger" in source
        or "execution import portfolio_ledger" in source
        or "from . import portfolio_ledger" in source
    )


def test_no_ledger_field_ships_in_the_manifest_yet_and_the_engine_version_stands() -> None:
    """NARROWED at `C7`: the ALLOCATION policy version ships; the LEDGER's does not.

    `C7` shipped A16's four and bumped ``ENGINE_VERSION`` with them.
    ``engine_allocation_policy_version`` is one of the four.
    ``portfolio_ledger_policy_version`` is NOT: it identifies the shared-ledger
    implementation this contained layer owns, and A16 does not list it. A sequential
    manifest naming it would claim a single shared ledger held ``P0``/``R0``/``U0``, which
    is precisely the co-simulation that did not run. That is `C9`'s to ship. The name is
    kept because it is cited; this docstring carries the correction."""
    manifest_src = (
        Path(__file__).resolve().parents[2] / "src/entropia/domain/backtest/manifest.py"
    ).read_text(encoding="utf-8")

    # The literal moves only when something OUTSIDE the contained work bumps the version;
    # #550/#551/#552 (percent sizing, the zero-size guard, per-fill commission) did, `C9`
    # did as the act of lifting, and GH #532 did again to register ``entry_exit_collision``
    # in the decision trace. The tripwire is unchanged by any of them: it still fails the
    # moment a namespace shift happens, because it would have to move this line to do so.
    assert ENGINE_VERSION == "backtest-engine-v18-increasing-tf-ladder"
    assert "engine_allocation_policy_version" in manifest_src, "A16 requires it (shipped at `C7`)"
    for absent in ("portfolio_ledger_policy_version", LEDGER_POLICY_VERSION):
        assert absent not in manifest_src


def test_the_quantization_contract_is_pinned_by_a_named_version() -> None:
    """Doc 13 §13 forbids float money and requires preview and manifest to agree; ADR §10.3
    makes the policy a versioned manifest field. Changing a quantum or the rounding is a
    result-moving change, so it must move this constant with it."""
    assert (Decimal("0.01"), Decimal("0.00000001")) == (MONEY_QUANTUM, QTY_QUANTUM)
    assert MONEY_ROUNDING == ROUND_HALF_EVEN
    assert LEDGER_POLICY_VERSION == "portfolio-ledger-v1"
