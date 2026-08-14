"""Oracle — position sizing, limits, leverage and the allocation sleeve (ADIM 12).

Canonical rules under test (doc 02 §6 / §5.10, doc 13 §8.3, Master Ref §10.1-§10.2):

* exactly ONE sizing method is active;
* RISK PER TRADE risks a fixed % of equity across the configured stop distance
  (doc 02's worked example: 10 000 equity at 1% risks 100 USD);
* MAX / MIN position limits are the final word, applied after leverage;
* NO LEVERAGE normalizes to 1x; CROSS margin is not modelled and opens nothing;
* under shared allocation the sleeve ``Ci = A0 * wi / 100`` with ``A0 = P0 - R0`` is an
  OUTER cap on the size the strategy's own sizing asked for (doc 13 §8.3, verbatim
  formula block).

Geometry: long in at 102, out at 104 (end of data), zero costs — so pnl is exactly
``2.00 * size`` and the size is readable straight off the pnl.
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.engine import EngineOutput, run_engine
from entropia.domain.backtest.execution.portfolio_ledger import SLEEVE_ZERO_CAPACITY
from entropia.domain.backtest.execution.sizing import SIZE_RESOLVED_TO_ZERO
from entropia.domain.backtest.execution.state import AllocationExecution
from tests.unit.oracles.harness import (
    bar,
    batched,
    entry_plan,
    flat_run,
    oracle_config,
    run_oracle,
)

_BARS = [*flat_run(), bar(21, "100", "102", "100", "102"), bar(22, "102", "104", "102", "104")]


def _sized(sizing: dict[str, object]) -> EngineOutput:
    return run_oracle(oracle_config(direction="long", protection={}, sizing=sizing), _BARS)


def _entry_size(out: EngineOutput) -> Decimal:
    fill = next(e for e in out.signal_events if e.event_type == "entry_fill")
    return Decimal(str(fill.detail["size"]))


def _blocked_reason(out: EngineOutput) -> str:
    """The reason attached to the ``entry_blocked`` event (F-10 restriction trace).

    Added at GH #551: once a non-positive size opens nothing, the interesting assertion is
    no longer the size that was computed but the reason the entry was refused."""
    blocked = next(e for e in out.signal_events if e.event_type == "entry_blocked")
    return str(blocked.detail["reason"])


# --------------------------------------------------------------------------- #
# Sizing methods                                                               #
# --------------------------------------------------------------------------- #
def test_base_position_size_is_a_percent_of_resolved_capital() -> None:
    """Doc 02's worked example, run: "Equity 10.000 USD ve Position Size %10 -> 1.000 USD
    nominal". 10% of 10 000 is a 1 000 NOTIONAL, and at an entry of 102 that notional buys
    1 000 / 102 = 9.80392156862... -> 9.80392157 units at the engine's 8-decimal step.
    pnl = 2.00 * 9.80392157 = 19.60784314 -> 19.61.

    The notional is the invariant worth reading twice: 9.80392157 * 102 = 1 000.00 to the
    cent, at ANY price the fixture could have used. That is the whole of GH #550. Until it
    was fixed this test read ``base_position_size: "50"`` -> 50 units and asserted a
    5 100 notional from a field the shipped UI has always labelled ``%``, under the name
    ``test_base_position_size_is_taken_as_the_size`` — the divergence pinned as an oracle,
    which is what an oracle is for. A user who typed 10 meaning 10% of the account opened
    10 units: 1 020 of notional here, 100 000 at an instrument costing 10 000."""
    out = _sized({"method": "base_position_size", "base_position_size": "10"})

    size = _entry_size(out)
    assert size == Decimal("9.80392157")
    assert (size * Decimal("102")).quantize(Decimal("0.01")) == Decimal("1000.00")
    assert out.trades[0].pnl == Decimal("19.61")


def test_risk_based_sizing_spends_the_risk_budget_across_the_stop_distance() -> None:
    """risk 2% of 10 000 = 200.00 of risk budget; a 4.00 stop distance buys
    200 / 4 = 50 units. pnl = 2.00 * 50 = 100.00. Note it is independent of entry price —
    risk sizing divides by a DISTANCE, not by a level."""
    out = _sized(
        {
            "method": "risk_based_sizing",
            "risk_based": {"risk_percentage_per_trade": "2", "stop_loss_point": "4"},
        }
    )

    assert _entry_size(out) == Decimal("50.00000000")
    assert out.trades[0].pnl == Decimal("100.00")


def test_fractional_kelly_allocates_a_capital_slice_and_converts_it_at_the_entry_price() -> None:
    """f* = kelly_fraction * (W - (1 - W) / R) = 0.5 * (0.6 - 0.4 / 2) = 0.5 * 0.4 = 0.20.
    Capital 10 000 * 0.20 = 2 000; units = 2 000 / 102 = 19.60784313725... -> 19.60784314
    at the engine's 8-decimal quantity step.
    pnl = 2.00 * 19.60784314 = 39.21568628 -> 39.22 at the 2-decimal money step."""
    out = _sized(
        {
            "method": "formula_based_sizing",
            "formula_based": {
                "formula_type": "kelly_criterion",
                "formula_params": {
                    "win_probability": "0.6",
                    "payoff_ratio": "2",
                    "kelly_fraction": "0.5",
                },
            },
        }
    )

    assert _entry_size(out) == Decimal("19.60784314")
    assert out.trades[0].pnl == Decimal("39.22")


def test_an_absent_kelly_fraction_means_full_kelly() -> None:
    """f* = 1 * (0.6 - 0.4 / 2) = 0.40; units = 4 000 / 102 = 39.21568627.
    pnl = 2.00 * 39.21568627 = 78.43137254 -> 78.43 — exactly double the half-Kelly case,
    which is the whole point of the fraction."""
    out = _sized(
        {
            "method": "formula_based_sizing",
            "formula_based": {
                "formula_type": "kelly_criterion",
                "formula_params": {"win_probability": "0.6", "payoff_ratio": "2"},
            },
        }
    )

    assert _entry_size(out) == Decimal("39.21568627")
    assert out.trades[0].pnl == Decimal("78.43")


def test_a_non_positive_kelly_edge_opens_nothing() -> None:
    """W = 0.3, R = 1 -> edge = 0.3 - 0.7 / 1 = -0.40. A negative edge must clamp to 0,
    never invert into a bet AGAINST the edge — and then open NOTHING.

    The name always promised this; until GH #551 the body only asserted the SIZE was 0,
    which the engine satisfied while still opening a 0-size position and booking a
    0.00-PnL trade. Asserting the size alone is what let the divergence sit under a
    correct-sounding name, so the assertions now go to the trade rows."""
    out = _sized(
        {
            "method": "formula_based_sizing",
            "formula_based": {
                "formula_type": "kelly_criterion",
                "formula_params": {"win_probability": "0.3", "payoff_ratio": "1"},
            },
        }
    )

    assert not [e for e in out.signal_events if e.event_type == "entry_fill"]
    assert out.trades == []
    assert out.position_intervals == []
    assert _blocked_reason(out) == "size_resolved_to_zero"


# --------------------------------------------------------------------------- #
# Limits and leverage                                                          #
# --------------------------------------------------------------------------- #
def test_a_max_limit_pulls_the_size_down() -> None:
    """The caps are percentages too (GH #550, doc 02's ⓘ panel: a 25% Max Single Position
    means the position may not exceed 25% of equity). 50% asked for, 20% allowed:
    5 000 / 102 = 49.01960784 requested, capped to 2 000 / 102 = 19.60784314.
    pnl = 2.00 * 19.60784314 = 39.21568628 -> 39.22.

    Both numbers used to be unit counts (50 pulled down to 20), which made a "25% max" cap
    mean twenty-five UNITS — a cap that tightens as the instrument gets cheaper and is
    meaningless above it."""
    out = _sized(
        {
            "method": "base_position_size",
            "base_position_size": "50",
            "position_size_limits": {"max_position_size": "20"},
        }
    )

    assert (_entry_size(out), out.trades[0].pnl) == (Decimal("19.60784314"), Decimal("39.22"))


def test_a_min_limit_pushes_the_size_up() -> None:
    """50% asked for, floor 80%: 49.01960784 pushed up to 8 000 / 102 = 78.43137255.
    pnl = 2.00 * 78.43137255 = 156.8627451 -> 156.86."""
    out = _sized(
        {
            "method": "base_position_size",
            "base_position_size": "50",
            "position_size_limits": {"min_position_size": "80"},
        }
    )

    assert (_entry_size(out), out.trades[0].pnl) == (Decimal("78.43137255"), Decimal("156.86"))


def test_isolated_leverage_multiplies_the_computed_size() -> None:
    """49.01960784 * 3 = 147.05882352 units. pnl = 2.00 * 147.05882352 = 294.11764704
    -> 294.12 — leverage scales the size, so it scales every downstream notional, exposure
    and PnL figure with it."""
    out = _sized(
        {
            "method": "base_position_size",
            "base_position_size": "50",
            "leverage_mode": "isolated",
            "leverage": "3",
        }
    )

    assert (_entry_size(out), out.trades[0].pnl) == (Decimal("147.05882352"), Decimal("294.12"))


def test_no_leverage_normalizes_to_one_x_whatever_multiplier_is_saved() -> None:
    """Master Ref §10.2: "No Leverage modunda 1x olarak normalize edilir." A stale 3
    in the saved field must NOT leak through: the unlevered 49.01960784 units,
    pnl = 2.00 * 49.01960784 = 98.03921568 -> 98.04."""
    out = _sized(
        {
            "method": "base_position_size",
            "base_position_size": "50",
            "leverage_mode": "no_leverage",
            "leverage": "3",
        }
    )

    assert (_entry_size(out), out.trades[0].pnl) == (Decimal("49.01960784"), Decimal("98.04"))


def test_cross_margin_opens_no_position_at_all() -> None:
    """Cross margin needs a portfolio-level risk model this engine does not implement, so
    it fails CLOSED — no trade, and the refusal is named rather than silently degraded to
    isolated semantics."""
    out = _sized(
        {
            "method": "base_position_size",
            "base_position_size": "50",
            "leverage_mode": "cross",
            "leverage": "3",
        }
    )

    assert out.trades == []
    assert out.summary["final_equity"] == Decimal("10000.00")
    assert any("leverage_unsupported" in w for w in out.diagnostics["warnings"])


def test_a_min_above_max_window_opens_nothing() -> None:
    """A window no size can satisfy (floor 80 above cap 20) resolves to size 0 and opens
    NOTHING — GH #551, fixed. This test previously pinned the divergence under the name
    ``..._books_a_zero_size_trade``: the engine opened the position anyway and booked a
    0.00-PnL row, because the guard read ``if alloc_on and size <= _ZERO`` and so never
    fired in independent mode. It now reads ``if size <= _ZERO``.

    What it closes, stated as measured rather than as argued: ``total_trades`` no longer
    counts a position that never carried risk, so the win/loss split is not diluted by a
    0-PnL lot landing on the loss side, and no ``position_intervals`` record is written.
    With a commission configured it is also money — a 0-unit position used to pay the same
    flat per-fill fee as a full one.

    It is NOT a cross-item leak, and #551's own text calls that "the load-bearing one".
    ``execution/rules.py::conflicts_with_prior`` does match an interval on ``direction``
    alone without reading ``peak_notional``, but it never sees a phantom: the only producer
    of ``PriorItemInterval`` is ``engine.py::build_prior_intervals``, which drops a window
    whose notional is not positive before the gate runs
    (``test_backtest_portfolio_rules.py::
    test_build_prior_intervals_fails_closed_on_bad_bounds_and_drops_zero_notional``)."""
    out = _sized(
        {
            "method": "base_position_size",
            "base_position_size": "50",
            "position_size_limits": {"min_position_size": "80", "max_position_size": "20"},
        }
    )

    assert not [e for e in out.signal_events if e.event_type == "entry_fill"]
    assert out.trades == []
    assert out.summary["total_trades"] == 0
    assert out.position_intervals == []
    assert _blocked_reason(out) == "size_resolved_to_zero"


def test_a_negative_size_opens_nothing_rather_than_inverting_the_pnl_sign() -> None:
    """The severe variant of GH #551, and the one its text does not mention.

    ``_raw_position_size`` returned the stored base value verbatim and
    ``_clamp_to_limits`` short-circuits on a non-positive size (so a ``min`` floor cannot
    resurrect the 0 "do not open" sentinel), which together let a NEGATIVE size through
    untouched. A stored ``-5`` opened a -5-unit long and booked a LOSS on this fixture's
    bar, which moves +2.00 in the position's favour: the size multiplies the price delta,
    so its sign inverts the result. The schema enforces neither Master Ref §10.1's
    positive-only rule nor doc 02's "required >0".

    ``if size <= _ZERO`` covers it with the same comparison that covers zero — there is no
    separate negative branch, which is why this case is worth pinning rather than assuming:
    a future refactor that split the guard into ``== 0`` would silently reopen it."""
    out = _sized({"method": "base_position_size", "base_position_size": "-5"})

    assert not [e for e in out.signal_events if e.event_type == "entry_fill"]
    assert out.trades == []
    assert out.summary["total_trades"] == 0
    assert out.summary["final_equity"] == Decimal("10000.00")
    assert _blocked_reason(out) == "size_resolved_to_zero"


# --------------------------------------------------------------------------- #
# Allocation sleeve (doc 13 §8.3)                                              #
# --------------------------------------------------------------------------- #
def test_the_sleeve_caps_a_size_the_strategy_asked_for() -> None:
    """P0 = 100 000, r = 10% -> R0 = 10 000, A0 = 90 000, wi = 5% -> Ci = 4 500.
    The strategy asks for 1 000 000 units, so the sleeve binds:
    4 500 / 102 = 44.11764705882... -> 44.11764706 units.
    pnl = 2.00 * 44.11764706 = 88.23529412 -> 88.24, on a book that opens at P0."""
    allocation = AllocationExecution(
        initial_capital=Decimal("100000.00"),
        reserve_percent=Decimal("10"),
        compound=False,
        item_share_percent=Decimal("5"),
        currency="USD",
    )
    out = run_engine(
        strategy_config=oracle_config(
            direction="long",
            protection={},
            sizing={"method": "base_position_size", "base_position_size": "1000000"},
        ),
        bar_batches=batched(_BARS, 8),
        execution_key="oracle_exec_key",
        indicator_plan=entry_plan(),
        allocation=allocation,
    )

    assert _entry_size(out) == Decimal("44.11764706")
    assert out.trades[0].pnl == Decimal("88.24")
    assert out.summary["final_equity"] == Decimal("100088.24")


def test_an_unallocated_item_gets_no_sleeve_and_therefore_no_fill() -> None:
    """wi = 0 -> Ci = 0. Doc 13 is explicit that this must NOT fall back to the strategy's
    own capital: no sleeve, no fill, and the book stays at P0."""
    allocation = AllocationExecution(
        initial_capital=Decimal("100000.00"),
        reserve_percent=Decimal("10"),
        compound=False,
        item_share_percent=Decimal("0"),
        currency="USD",
    )
    out = run_engine(
        strategy_config=oracle_config(direction="long", protection={}),
        bar_batches=batched(_BARS, 8),
        execution_key="oracle_exec_key",
        indicator_plan=entry_plan(),
        allocation=allocation,
    )

    assert out.trades == []
    assert out.summary["final_equity"] == Decimal("100000.00")

    # Negative control for the constant promoted in F1/A-2. Under allocation the ladder in
    # ``sizing.blocked_reason`` reaches ``sleeve_zero_capacity`` via ``ctx.alloc_on``, which
    # is the MORE SPECIFIC and already-contracted reason; ``_open()`` sets the independent
    # token only when ``not alloc_on``. Without this pin a refactor that dropped the
    # ``alloc_on`` test at the assignment site would relabel this refusal and no test would
    # notice — the value assertion below would still pass, because it never runs the engine.
    # Verified by mutation: forcing that branch to ``if True`` turns this red with
    # ``assert 'size_resolved_to_zero' == 'sleeve_zero_capacity'``.
    reason = _blocked_reason(out)
    assert reason == "sleeve_zero_capacity"
    assert reason != SIZE_RESOLVED_TO_ZERO


def test_the_two_zero_size_refusal_tokens_are_pinned_by_value_and_stay_distinct() -> None:
    """GH #551 shipped the refusal; F1/A-2 publishes its REASON.

    Pinned by **value**, not by symbol: the O-31 lesson is that asserting the type or the
    symbol lets a wire spelling drift silently, and this token is read by a human in an F-10
    restriction trace. It is deliberately NOT an HTTP error code — no ``ErrorBody`` is
    emitted on this path, so O-02's ``ErrorCategory`` does not apply and no
    ``shared/errors.py`` class was added.

    The distinctness assertion is the point of the pair: collapsing the two onto one token
    would erase the difference between *"your sizing produced nothing"* (independent) and
    *"your sleeve had no capacity"* (allocation), which are different user actions.

    The two constants deliberately live in DIFFERENT modules. ``portfolio_ledger`` is a
    contained phase-loop module with an enumerated production-importer allowlist, and the
    shipped engine is not on it; naming the independent-mode token beside the ladder that
    returns it keeps that containment tripwire intact. This test imports both anyway,
    because a TEST importing the ledger is not a production importer — both containment
    gates scan ``src/`` only."""
    assert SIZE_RESOLVED_TO_ZERO == "size_resolved_to_zero"
    assert SLEEVE_ZERO_CAPACITY == "sleeve_zero_capacity"
    assert SIZE_RESOLVED_TO_ZERO != SLEEVE_ZERO_CAPACITY
