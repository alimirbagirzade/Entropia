"""I-01 — the null Metric statuses must name WHY the value is absent (doc 17 §9.2).

Doc 17 §9.2 forbids rendering ROMAD/Profit Factor as infinity and pins the two
reasons by name: "Max drawdown=0 ise null + `no_drawdown`" and "Gross loss=0 ise
null + `no_losing_trade`". Doc 16 §9.3 then sorts such a ROMAD null-last rather
than as a fake large value. These tests drive the REAL engine (never a hand-built
summary, except where a degenerate/absent key is the point) so the statuses are
proven against the fold that actually ships.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from entropia.domain.backtest.enums import MetricAvailability
from entropia.domain.backtest.metrics import DEFAULT_METRICS, derive_metric_values

# The engine fixture geometry (valid StrategyConfig + bar/batch helpers + the shared
# ``ta.sma`` entry plan) already lives in the engine unit module; reusing it keeps ONE
# definition of "what a production-reachable run looks like" instead of a second copy
# that could drift away from the config the engine actually validates.
from tests.unit.test_backtest_engine import _bar, _config, _flat, _run


def _winning_run_only() -> list[dict[str, Any]]:
    """20 flat bars → an upside cross entry → a higher close, no stop, no drawdown.

    The single trade closes at end-of-data in profit, so the realized equity curve
    only ever rises: ``max_drawdown == 0`` AND ``gross_loss == 0`` — both forbidden
    divide-by-zero cases in one run.
    """
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "102", "100", "102"))  # cross -> long
    bars.append(_bar("2024-01-22T00:00:00Z", "102", "112", "102", "110"))  # low never trips stop
    return bars


def _values(summary: dict[str, Any]) -> dict[str, Any]:
    return {v.key: v for v in derive_metric_values(summary)}


def test_metric_availability_no_drawdown_when_max_drawdown_is_zero() -> None:
    out = _run(_config(), _winning_run_only())
    assert out.summary["max_drawdown"] == Decimal("0.00")
    assert out.summary["romad"] is None  # never infinity (doc 17 §9.2)

    romad = _values(out.summary)["romad"]
    assert romad.value is None  # NOT a fabricated 0 (L4)
    assert romad.availability == MetricAvailability.NO_DRAWDOWN
    assert romad.availability != MetricAvailability.NOT_AVAILABLE


def test_metric_availability_no_losing_trade_when_gross_loss_is_zero() -> None:
    out = _run(_config(), _winning_run_only())
    assert out.summary["total_trades"] == 1
    assert out.summary["total_winning_trades"] == 1
    assert out.summary["profit_factor"] is None  # never infinity (doc 17 §9.2)

    profit_factor = _values(out.summary)["profit_factor"]
    assert profit_factor.value is None
    assert profit_factor.availability == MetricAvailability.NO_LOSING_TRADE
    assert profit_factor.availability != MetricAvailability.NO_QUALIFYING_TRADES


def test_metric_availability_zero_trade_run_never_blames_equity_metrics() -> None:
    """A run that closed no trades: only the trade-denominator metrics may say so.

    Net Profit / Max Drawdown come off the equity curve regardless of trade count,
    so labelling them ``no_qualifying_trades`` would state a false reason (I-01).
    """
    out = _run(_config(), _flat(20))
    assert out.summary["total_trades"] == 0

    values = _values(out.summary)
    # Equity metrics ARE computed here (a real 0), never blamed on missing trades.
    assert values["net_profit"].availability == MetricAvailability.COMPUTED
    assert values["max_drawdown"].availability == MetricAvailability.COMPUTED
    # ROMAD is null for the drawdown reason, not the trade reason.
    assert values["romad"].availability == MetricAvailability.NO_DRAWDOWN
    # Only the trade-denominator metrics carry the trade reason.
    assert values["win_rate"].availability == MetricAvailability.NO_QUALIFYING_TRADES
    assert values["profit_factor"].availability == MetricAvailability.NO_QUALIFYING_TRADES


def test_metric_availability_absent_summary_key_stays_not_available() -> None:
    """A key the fold never emitted carries no reason beyond "absent" (I-01 regression).

    The pre-I-01 code labelled EVERY null as ``no_qualifying_trades`` whenever the
    run closed no trades — including equity metrics whose absence has nothing to do
    with trade roots.
    """
    summary: dict[str, Any] = {"total_trades": 0}
    values = _values(summary)
    assert values["net_profit"].availability == MetricAvailability.NOT_AVAILABLE
    assert values["max_drawdown"].availability == MetricAvailability.NOT_AVAILABLE
    assert values["romad"].availability == MetricAvailability.NOT_AVAILABLE
    # Trade-dependent keys are still absent, so "absent" wins over the trade reason.
    assert values["win_rate"].availability == MetricAvailability.NOT_AVAILABLE


def test_metric_availability_derivation_never_emits_not_computed() -> None:
    """``not_computed`` belongs to the Arrange Metrics profile view, not to this fold.

    ``queries/metric_profile.py::_metric_card_not_computed`` is its ONLY producer: a
    metric the caller's profile selects but this immutable Result never calculated
    (doc 17 §6.1). An engine summary by construction ran every canonical metric, so
    the two producers stay disjoint.
    """
    winning = _run(_config(), _winning_run_only()).summary
    tradeless = _run(_config(), _flat(20)).summary
    for summary in (winning, tradeless, {}):
        emitted = {v.availability for v in derive_metric_values(summary)}
        assert MetricAvailability.NOT_COMPUTED not in emitted


def test_metric_availability_trade_dependency_flags_match_the_spec_registry() -> None:
    """doc 17 §9.2: only these metrics have a trade-root denominator."""
    trade_dependent = {d.key for d in DEFAULT_METRICS if d.trade_dependent}
    assert trade_dependent == {
        "win_rate",
        "profit_factor",
        "total_trades",
        "total_stops",
        "max_stop_streak",
        "total_winning_trades",
    }
