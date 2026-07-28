"""K-09 (e) — the portfolio COMPOSE fold, tested directly.

``combine_item_runs`` and its numeric core used to live inside the 5.2k-line engine
module, so the only way to reach them was through a bar replay. They are pure folds
over already-completed ``ItemRun`` outputs, so after the extraction into
``execution.portfolio`` they are unit testable on their own — including the two
never-fabricate rules the compose layer owns:

* ``_pearson`` returns ``None`` (never 0.0) below two points or on a flat series;
* ``_fold_composite_metrics`` over a leave-one-out subset must equal a REAL
  ``combine_item_runs`` over that same subset — the INF-04 reuse claim that makes the
  Contribution block's "without this item" figure honest rather than an approximation.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import EngineOutput, EquityPoint, ItemRun, TradeRow
from entropia.domain.backtest.execution.portfolio import (
    COMPOSITION_CURVE_WARNING,
    _contribution_block,
    _correlation_block,
    _fold_composite_metrics,
    _pearson,
    combine_item_runs,
)
from tests.unit.test_backtest_engine import _config, _long_breakout_then_stop, _run

_INITIAL = Decimal("10000.00")


# --------------------------------------------------------------------------- #
# _pearson — the never-fabricated correlation                                  #
# --------------------------------------------------------------------------- #
def test_pearson_is_unity_for_a_perfectly_correlated_series() -> None:
    assert _pearson([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == 1.0


def test_pearson_is_minus_unity_for_a_perfectly_anticorrelated_series() -> None:
    assert _pearson([1.0, 2.0, 3.0], [6.0, 4.0, 2.0]) == -1.0


def test_pearson_returns_none_below_two_points() -> None:
    assert _pearson([1.0], [2.0]) is None
    assert _pearson([], []) is None


def test_pearson_returns_none_on_a_flat_series_rather_than_zero() -> None:
    """A zero-variance series has NO correlation — reporting 0.0 would read as a
    measured independence the data cannot support."""
    assert _pearson([5.0, 5.0, 5.0], [1.0, 2.0, 3.0]) is None


# --------------------------------------------------------------------------- #
# _correlation_block — alignment on the union of close times                   #
# --------------------------------------------------------------------------- #
def _synthetic(item_id: str, closes: list[tuple[str, str]]) -> ItemRun:
    """An ItemRun whose only meaningful content is its realized trade PnL series."""
    trades = [
        TradeRow(
            seq=i + 1,
            entry_time="2024-01-01T00:00:00Z",
            exit_time=ts,
            direction="long",
            entry_price=Decimal("100"),
            exit_price=Decimal("100"),
            pnl=Decimal(pnl),
            exit_reason="exit_signal",
        )
        for i, (ts, pnl) in enumerate(closes)
    ]
    equity = _INITIAL
    points = [EquityPoint(0, "", equity, Decimal("0.00"), Decimal("0.0000"))]
    for t in trades:
        equity = equity + t.pnl
        points.append(EquityPoint(t.seq, t.exit_time, equity, Decimal("0.00"), Decimal("0.0000")))
    summary: dict[str, Any] = {
        "initial_capital": _INITIAL,
        "net_profit": equity - _INITIAL,
        "final_equity": equity,
        "max_drawdown": Decimal("0.00"),
        "max_drawdown_pct": Decimal("0.0000"),
    }
    out = EngineOutput(
        summary=summary, trades=trades, equity_points=points, signal_events=[], diagnostics={}
    )
    return ItemRun(
        item_id=item_id, item_kind="strategy", root_id="wo", revision_id="rev", output=out
    )


def test_correlation_block_aligns_on_the_union_of_close_times() -> None:
    a = _synthetic("mbi_a", [("t1", "10"), ("t2", "20")])
    b = _synthetic("mbi_b", [("t2", "5"), ("t3", "7")])
    block = _correlation_block([a, b])
    assert block["item_ids"] == ["mbi_a", "mbi_b"]
    # union {t1, t2, t3} — a time an item closed nothing at contributes 0, it is not dropped
    assert block["aligned_point_count"] == 3


def test_correlation_block_diagonal_is_unity() -> None:
    a = _synthetic("mbi_a", [("t1", "10"), ("t2", "-4"), ("t3", "6")])
    b = _synthetic("mbi_b", [("t1", "3"), ("t2", "9"), ("t3", "-2")])
    matrix = _correlation_block([a, b])["matrix"]
    assert matrix[0][0] == "1.0000"
    assert matrix[1][1] == "1.0000"
    assert matrix[0][1] == matrix[1][0]  # symmetric


def test_correlation_block_average_pairwise_is_none_for_a_single_item() -> None:
    """One item has no PAIR — an average over zero pairs is null, never 0."""
    block = _correlation_block([_synthetic("mbi_a", [("t1", "10"), ("t2", "20")])])
    assert block["average_pairwise"] is None


def test_correlation_block_average_pairwise_excludes_the_diagonal() -> None:
    a = _synthetic("mbi_a", [("t1", "10"), ("t2", "20")])
    b = _synthetic("mbi_b", [("t1", "20"), ("t2", "40")])
    # perfectly correlated pair -> the single off-diagonal cell is 1.0; a diagonal-
    # inclusive average would be 1.0 too, so use an ANTI-correlated pair to separate them
    c = _synthetic("mbi_c", [("t1", "40"), ("t2", "20")])
    assert _correlation_block([a, b])["average_pairwise"] == "1.0000"
    assert _correlation_block([a, c])["average_pairwise"] == "-1.0000"


# --------------------------------------------------------------------------- #
# _fold_composite_metrics — the leave-one-out reuse claim                      #
# --------------------------------------------------------------------------- #
def _real_runs() -> list[ItemRun]:
    long_out = _run(_config(), _long_breakout_then_stop())
    short_out = _run(_config(direction="short"), _long_breakout_then_stop())
    return [
        ItemRun(
            item_id="mbi_1",
            item_kind="strategy",
            root_id="wo_a",
            revision_id="rev_a",
            output=long_out,
        ),
        ItemRun(
            item_id="mbi_2",
            item_kind="strategy",
            root_id="wo_b",
            revision_id="rev_b",
            output=short_out,
        ),
    ]


def _combined_summary(runs: list[ItemRun], initial: Decimal) -> dict[str, Any]:
    return combine_item_runs(
        runs,
        portfolio_initial_capital=initial,
        execution_key="exec_key_compose",
        item_count=len(runs),
    ).summary


def test_fold_matches_a_real_combine_over_the_same_runs() -> None:
    """The numeric core and the full compose must not drift apart."""
    runs = _real_runs()
    initial = Decimal("20000.00")
    folded = _fold_composite_metrics(runs, initial)
    combined = _combined_summary(runs, initial)
    for key, value in folded.items():
        assert combined[key] == value, key


def test_fold_leave_one_out_equals_a_real_combine_over_the_remainder() -> None:
    """The Contribution block's "without this item" figure is a cheap in-memory
    re-fold, NOT a re-simulation — it is only honest if it equals the real thing."""
    runs = _real_runs()
    remainder = runs[1:]
    folded = _fold_composite_metrics(remainder, _INITIAL)
    combined = _combined_summary(remainder, _INITIAL)
    for key, value in folded.items():
        assert combined[key] == value, key


def test_fold_skips_non_executing_items() -> None:
    """A Trading Signal / Trade Log item contributes no trades — it must not shift a
    single metric, and must not be counted as a zero-PnL participant."""
    runs = _real_runs()
    with_signal = [
        *runs,
        ItemRun(
            item_id="mbi_3",
            item_kind="trading_signal",
            root_id="wo_c",
            revision_id="rev_c",
            output=None,
        ),
    ]
    assert _fold_composite_metrics(with_signal, _INITIAL) == _fold_composite_metrics(runs, _INITIAL)


def test_fold_of_no_executing_items_reports_a_flat_portfolio() -> None:
    folded = _fold_composite_metrics([], _INITIAL)
    assert folded["total_trades"] == 0
    assert folded["net_profit"] == Decimal("0.00")
    assert folded["final_equity"] == _INITIAL
    # never-0 missing metrics: no trades means no win rate / profit factor / romad
    assert folded["win_rate"] is None
    assert folded["profit_factor"] is None
    assert folded["romad"] is None


# --------------------------------------------------------------------------- #
# _contribution_block                                                          #
# --------------------------------------------------------------------------- #
def test_contribution_block_reports_one_marginal_entry_per_executing_item() -> None:
    runs = _real_runs()
    initial = Decimal("20000.00")
    full = _combined_summary(runs, initial)
    block = _contribution_block(
        runs, portfolio_initial=initial, shared_pool=False, full_summary=full
    )
    assert [m["item_id"] for m in block["marginal"]] == ["mbi_1", "mbi_2"]
    assert block["correlation"]["item_ids"] == ["mbi_1", "mbi_2"]


def test_contribution_marginal_delta_is_full_minus_without() -> None:
    runs = _real_runs()
    initial = Decimal("20000.00")
    full = _combined_summary(runs, initial)
    block = _contribution_block(
        runs, portfolio_initial=initial, shared_pool=True, full_summary=full
    )
    for marginal in block["marginal"]:
        without = marginal["without_item"]
        assert marginal["delta"]["net_profit"] == full["net_profit"] - without["net_profit"]
        assert marginal["delta"]["total_trades"] == full["total_trades"] - without["total_trades"]


# --------------------------------------------------------------------------- #
# Reproducibility contract                                                     #
# --------------------------------------------------------------------------- #
def test_composition_curve_warning_token_is_stable() -> None:
    """The L4 token is persisted into immutable Result artifacts — the K-09 move
    between modules must not have changed its value."""
    assert COMPOSITION_CURVE_WARNING == "portfolio_curve_sequential_not_unified_clock"
