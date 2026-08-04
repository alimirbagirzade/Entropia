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


# --------------------------------------------------------------------------- #
# Sizing methods                                                               #
# --------------------------------------------------------------------------- #
def test_base_position_size_is_taken_as_the_size() -> None:
    """50 units at 102 = 5100 notional; pnl = (104 - 102) * 50 = 100.00.

    SPEC BOUNDARY: doc 02 labels this field a PERCENT of resolved capital (its V18 form
    input carries a ``%`` suffix and its worked example reads "Equity 10.000 USD ve
    Position Size %10 -> 1.000 USD nominal"). The shipped engine reads it as an absolute
    quantity of units. This oracle pins the SHIPPED reading; the divergence is filed as
    issue #550."""
    out = _sized({"method": "base_position_size", "base_position_size": "50"})

    assert _entry_size(out) == Decimal("50")
    assert out.trades[0].pnl == Decimal("100.00")


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
    """W = 0.3, R = 1 -> edge = 0.3 - 0.7 / 1 = -0.40. A negative edge must clamp to 0
    (size 0), never invert into a bet AGAINST the edge."""
    out = _sized(
        {
            "method": "formula_based_sizing",
            "formula_based": {
                "formula_type": "kelly_criterion",
                "formula_params": {"win_probability": "0.3", "payoff_ratio": "1"},
            },
        }
    )

    assert _entry_size(out) == Decimal("0")


# --------------------------------------------------------------------------- #
# Limits and leverage                                                          #
# --------------------------------------------------------------------------- #
def test_a_max_limit_pulls_the_size_down() -> None:
    """50 requested, cap 20 -> 20 units. pnl = 2.00 * 20 = 40.00."""
    out = _sized(
        {
            "method": "base_position_size",
            "base_position_size": "50",
            "position_size_limits": {"max_position_size": "20"},
        }
    )

    assert (_entry_size(out), out.trades[0].pnl) == (Decimal("20"), Decimal("40.00"))


def test_a_min_limit_pushes_the_size_up() -> None:
    """50 requested, floor 80 -> 80 units. pnl = 2.00 * 80 = 160.00."""
    out = _sized(
        {
            "method": "base_position_size",
            "base_position_size": "50",
            "position_size_limits": {"min_position_size": "80"},
        }
    )

    assert (_entry_size(out), out.trades[0].pnl) == (Decimal("80"), Decimal("160.00"))


def test_isolated_leverage_multiplies_the_computed_size() -> None:
    """50 * 3 = 150 units. pnl = 2.00 * 150 = 300.00 — leverage scales the size, so it
    scales every downstream notional, exposure and PnL figure with it."""
    out = _sized(
        {
            "method": "base_position_size",
            "base_position_size": "50",
            "leverage_mode": "isolated",
            "leverage": "3",
        }
    )

    assert (_entry_size(out), out.trades[0].pnl) == (Decimal("150"), Decimal("300.00"))


def test_no_leverage_normalizes_to_one_x_whatever_multiplier_is_saved() -> None:
    """Master Ref §10.2: "No Leverage modunda 1x olarak normalize edilir." A stale 3
    in the saved field must NOT leak through: 50 units, pnl 100.00."""
    out = _sized(
        {
            "method": "base_position_size",
            "base_position_size": "50",
            "leverage_mode": "no_leverage",
            "leverage": "3",
        }
    )

    assert (_entry_size(out), out.trades[0].pnl) == (Decimal("50"), Decimal("100.00"))


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


def test_a_min_above_max_window_books_a_zero_size_trade() -> None:
    """A window no size can satisfy (floor 80 above cap 20) resolves to size 0.

    DIVERGENCE, pinned deliberately: the engine still OPENS the position and books a
    0.00-PnL trade row, so ``total_trades`` counts a position that never carried risk and
    the 0-PnL lot lands on the loss side of the win/loss split. Fail-closed elsewhere in
    the engine means "open nothing" (the unmodelled-sizing path opens no position at all).
    Filed as issue #551."""
    out = _sized(
        {
            "method": "base_position_size",
            "base_position_size": "50",
            "position_size_limits": {"min_position_size": "80", "max_position_size": "20"},
        }
    )

    assert _entry_size(out) == Decimal("0")
    assert out.trades[0].pnl == Decimal("0.00")
    assert out.summary["total_trades"] == 1


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
