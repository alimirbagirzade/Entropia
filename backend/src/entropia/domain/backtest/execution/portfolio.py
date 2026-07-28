"""Portfolio composition — folding N per-item runs into ONE composite Result (K-09 e).

Extracted VERBATIM from ``domain.backtest.engine`` (the ``combine_item_runs`` tail of
the 5.2k-line god module). Nothing here reads the bar loop's mutable state: every
function is a pure fold over already-completed ``ItemRun`` outputs, which is exactly
why it separates cleanly and why it is now directly unit testable without replaying a
single bar.

Behaviour is unchanged by construction — the moved lines are byte-identical to their
pre-extraction form, ``ENGINE_VERSION`` is untouched, and the slice landed only after
the full-``EngineOutput`` digest over the fixture matrix matched the pre-refactor
baseline exactly. Imports point at ``engine`` and never back, so no cycle exists.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from math import sqrt
from typing import Any

from entropia.domain.backtest.engine import (
    EngineOutput,
    EquityPoint,
    ItemRun,
    SignalEventRow,
    TradeRow,
)
from entropia.domain.backtest.execution.constants import (
    _HUNDRED,
    _MONEY,
    _PCT,
    _RATIO,
    _ZERO,
)
from entropia.domain.backtest.execution.state import _dec

_DIAG_SUM_KEYS = (
    "bars_processed",
    "indicator_blocks",
    "condition_blocks",
    "multi_timeframe_blocks",
    "per_condition_timeframe_conditions",
    "nary_reference_conditions",
    "vwap_blocks",
    "stop_exit_collisions",
    "deferred_entry_fills",
    "deferred_exit_fills",
    "logic_stop_triggers",
    "funding_charges",
    "tick_bars",
    "tick_first_trigger_resolutions",
    "tick_resolved_entry_fills",
    "partial_fills",
    "same_bar_stop_limit_fills",
    "touch_orders_placed",
    "touch_exit_fills",
    "portfolio_conflict_blocked_entries",
    "portfolio_exposure_blocked_entries",
    "portfolio_exposure_clamped_entries",
)

# Sequential composite curve is NOT a unified-clock portfolio valuation (each strategy
# still replays over its own bar axis, then its realized PnL is concatenated onto the
# portfolio equity in deterministic pin order). A genuine multi-item co-simulation over
# one clock across heterogeneous bar sources stays deferred — surfaced, never hidden (L4).
COMPOSITION_CURVE_WARNING = "portfolio_curve_sequential_not_unified_clock"

# Contribution (doc 01 / video 3:35 — "what does an item add to the universe").
# Marginal deltas cover the pure performance metrics; ``initial_capital`` and
# ``final_equity`` stay OUT of the delta set because under independent allocation the
# without-item portfolio also starts with less capital, so their raw difference mixes
# the capital change into the performance change (they remain readable in
# ``without_item`` verbatim).
_CONTRIBUTION_DELTA_KEYS = (
    "net_profit",
    "net_profit_pct",
    "max_drawdown",
    "max_drawdown_pct",
    "romad",
    "win_rate",
    "profit_factor",
    "total_trades",
    "total_stops",
    "max_stop_streak",
    "total_winning_trades",
)


def _fold_composite_metrics(runs: list[ItemRun], initial: Decimal) -> dict[str, Any]:
    """Numeric core of the ``combine_item_runs`` fold — same order, same rebasing.

    Re-folds the supplied runs' EXISTING per-item outputs into the composite summary
    metric set without building trade/event/curve lists. Because each item's bar-replay
    is independent of the other items, calling this over a leave-one-out subset yields
    exactly what a real engine re-RUN of the composition-without-that-item would report
    (the INF-04 reuse: the "second run" is this cheap in-memory fold, never a
    re-simulation). Pinned against ``combine_item_runs`` drift by the unit test that
    compares this fold over the remaining items to an actual ``combine_item_runs`` call.
    """
    initial = initial.quantize(_MONEY)
    peak = initial
    running_net = _ZERO
    max_dd = _ZERO
    winners = 0
    stops = 0
    stop_streak = 0
    max_stop_streak = 0
    gross_profit = _ZERO
    gross_loss = _ZERO
    total_trades = 0
    for run in runs:
        out = run.output
        if out is None:
            continue
        run_initial = _dec(out.summary["initial_capital"])
        base = initial + running_net
        for idx, trade in enumerate(out.trades):
            total_trades += 1
            if trade.pnl > _ZERO:
                winners += 1
                gross_profit += trade.pnl
            else:
                gross_loss += -trade.pnl
            if trade.exit_reason == "stop_loss":
                stops += 1
                stop_streak += 1
                max_stop_streak = max(max_stop_streak, stop_streak)
            else:
                stop_streak = 0
            run_point = out.equity_points[idx + 1]
            portfolio_equity = (base + (run_point.equity - run_initial)).quantize(_MONEY)
            peak = max(peak, portfolio_equity)
            max_dd = max(max_dd, (peak - portfolio_equity).quantize(_MONEY))
        running_net += _dec(out.summary["net_profit"])
    final_equity = (initial + running_net).quantize(_MONEY)
    net_profit = running_net.quantize(_MONEY)
    net_profit_pct = (net_profit / initial * _HUNDRED).quantize(_PCT) if initial > _ZERO else None
    max_drawdown_pct = (
        (max_dd / peak * _HUNDRED).quantize(_PCT) if peak > _ZERO else _ZERO.quantize(_PCT)
    )
    win_rate = (
        (Decimal(winners) / Decimal(total_trades) * _HUNDRED).quantize(_PCT)
        if total_trades
        else None
    )
    profit_factor = (gross_profit / gross_loss).quantize(_RATIO) if gross_loss > _ZERO else None
    romad = (
        (net_profit_pct / max_drawdown_pct).quantize(_RATIO)
        if net_profit_pct is not None and max_drawdown_pct > _ZERO
        else None
    )
    return {
        "initial_capital": initial,
        "final_equity": final_equity,
        "net_profit": net_profit,
        "net_profit_pct": net_profit_pct,
        "max_drawdown": max_dd.quantize(_MONEY),
        "max_drawdown_pct": max_drawdown_pct,
        "romad": romad,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_trades": total_trades,
        "total_stops": stops,
        "max_stop_streak": max_stop_streak,
        "total_winning_trades": winners,
    }


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson r; ``None`` (never fabricated) below 2 points or on zero variance."""
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0.0 or var_y <= 0.0:
        return None
    return cov / sqrt(var_x * var_y)


def _correlation_block(executing: list[ItemRun]) -> dict[str, Any]:
    """Pairwise Pearson correlation of the items' per-trade realized-PnL series.

    Each executing item's series is its realized trade PnL keyed by trade close time
    (same-time closes summed), on the item's OWN capital basis. Series are aligned on
    the sorted union of all close times; a time where an item closed nothing
    contributes 0 (no position change realizes no PnL — not an imputed value). Cells
    with fewer than 2 aligned points or a zero-variance series are null.
    """
    series: list[dict[str, Decimal]] = []
    for run in executing:
        assert run.output is not None  # callers pass executing runs only
        by_close: dict[str, Decimal] = {}
        for trade in run.output.trades:
            by_close[trade.exit_time] = by_close.get(trade.exit_time, _ZERO) + trade.pnl
        series.append(by_close)
    axis = sorted({ts for s in series for ts in s})
    vectors = [[float(s.get(ts, _ZERO)) for ts in axis] for s in series]
    matrix: list[list[str | None]] = []
    pair_total = 0.0
    pair_count = 0
    for i, vi in enumerate(vectors):
        row: list[str | None] = []
        for j, vj in enumerate(vectors):
            r = _pearson(vi, vj)
            row.append(None if r is None else f"{r:.4f}")
            if r is not None and i < j:
                pair_total += r
                pair_count += 1
        matrix.append(row)
    return {
        "item_ids": [run.item_id for run in executing],
        "aligned_point_count": len(axis),
        "matrix": matrix,
        "average_pairwise": f"{pair_total / pair_count:.4f}" if pair_count else None,
    }


def _contribution_block(
    executing: list[ItemRun],
    *,
    portfolio_initial: Decimal,
    shared_pool: bool,
    full_summary: dict[str, Any],
) -> dict[str, Any]:
    """The composition's Contribution analysis — computed ONCE at run time (server-side)
    and persisted into the immutable Result artifact; the UI renders it verbatim.

    * ``correlation`` — pairwise Pearson matrix over the per-item realized-PnL series.
    * ``diversification`` — sum of the items' standalone max drawdowns vs the
      portfolio's (sequential-fold) max drawdown; the reduction is the diversification
      benefit of not suffering every strategy's worst stretch at once.
    * ``marginal`` — per item: the full composition re-folded WITHOUT the item
      (remaining items' own deterministic bar-replay outputs REUSED, not re-simulated —
      each item's simulation is independent of the others, the INF-04 reuse that makes
      the "second run" cheap) + ``delta = full - without`` per metric. Under the shared
      pool the without-run keeps the same P0; under independent capital it starts from
      the remaining items' summed capital.
    """
    correlation = _correlation_block(executing)
    item_dds = [
        _dec(run.output.summary.get("max_drawdown") or _ZERO)
        for run in executing
        if run.output is not None
    ]
    sum_item_dd = sum(item_dds, _ZERO).quantize(_MONEY)
    portfolio_dd = _dec(full_summary["max_drawdown"])
    marginal: list[dict[str, Any]] = []
    for excluded in executing:
        remaining = [run for run in executing if run.item_id != excluded.item_id]
        if shared_pool:
            loo_initial = portfolio_initial
        else:
            loo_initial = sum(
                (
                    _dec(run.output.summary["initial_capital"])
                    for run in remaining
                    if run.output is not None
                ),
                _ZERO,
            )
        without = _fold_composite_metrics(remaining, loo_initial)
        delta = {
            key: (
                None
                if full_summary.get(key) is None or without.get(key) is None
                else full_summary[key] - without[key]
            )
            for key in _CONTRIBUTION_DELTA_KEYS
        }
        marginal.append({"item_id": excluded.item_id, "without_item": without, "delta": delta})
    return {
        "method": {
            "correlation": (
                "Pearson correlation of per-trade realized PnL aligned on the union of "
                "trade close times (a time with no closed trade contributes 0), each "
                "series on the item's own capital basis. Cells with fewer than 2 "
                "aligned points or a zero-variance series are null, never fabricated."
            ),
            "marginal": (
                "The composition re-folded WITHOUT the item over the remaining items' "
                "own deterministic bar-replay outputs (reused, not re-simulated — each "
                "item's simulation is independent of the others), in the same pin "
                "order and capital-allocation rule. delta = full composition metric "
                "minus without-item metric."
            ),
        },
        "correlation": correlation,
        "diversification": {
            "sum_of_item_max_drawdowns": sum_item_dd,
            "portfolio_max_drawdown": portfolio_dd,
            "drawdown_reduction": (sum_item_dd - portfolio_dd).quantize(_MONEY),
            "average_pairwise_correlation": correlation["average_pairwise"],
        },
        "marginal": marginal,
    }


def combine_item_runs(
    runs: list[ItemRun],
    *,
    portfolio_initial_capital: Decimal,
    execution_key: str,
    item_count: int,
    shared_pool: bool = False,
) -> EngineOutput:
    """Assemble ONE composite ``EngineOutput`` from every enabled item's run (F-04).

    Every executing (Strategy) item's per-run output is folded into a single portfolio
    result: trades are concatenated and re-sequenced, decision events are tagged with
    their originating ``item_id`` and re-sequenced, and the portfolio equity curve is
    built by applying each run's realized-PnL progression onto the shared portfolio
    equity in the ORDER the runs are supplied (the worker supplies them in the
    manifest's deterministic pin order, so the composite is reproducible). Realized
    PnL is additive, so ``net_profit`` and the trade/decision sets are order-invariant;
    only the drawdown of the concatenated curve depends on the (deterministic) order.

    ``portfolio_initial_capital`` is the portfolio's starting capital: the shared pool
    ``P0`` under shared allocation (taken ONCE — not summed, since each sleeve reports
    the same pool), or the sum of the strategies' own ``initial_capital`` under
    independent capital. Non-executing items (Trading Signal / Trade Log) contribute no
    trades but ARE recorded in ``diagnostics.composition.items`` for traceability.

    The caller keeps the single-strategy path byte-identical by NOT routing a lone
    strategy through here; this function is for genuine multi-item compositions.
    """
    executing = [r for r in runs if r.output is not None]
    combined_trades: list[TradeRow] = []
    combined_events: list[SignalEventRow] = []
    initial = portfolio_initial_capital.quantize(_MONEY)
    combined_equity: list[EquityPoint] = [
        EquityPoint(0, "", initial, _ZERO.quantize(_MONEY), _ZERO.quantize(_PCT))
    ]
    peak = initial
    winners = 0
    stops = 0
    stop_streak = 0
    max_stop_streak = 0
    gross_profit = _ZERO
    gross_loss = _ZERO
    running_net = _ZERO
    warnings: list[str] = []
    symbols: set[Any] = set()
    timeframes: set[Any] = set()
    entry_models: set[str] = set()
    diag_totals = dict.fromkeys(_DIAG_SUM_KEYS, 0)
    per_item: list[dict[str, Any]] = []

    for run in runs:
        out = run.output
        if out is None:
            # A participating-but-non-executing object (Trading Signal / Trade Log):
            # pinned + recorded, but no standalone V1 bar-replay (its effect is defined
            # only as a Strategy data input). Recorded for traceability, never faked.
            per_item.append(
                {
                    "item_id": run.item_id,
                    "item_kind": run.item_kind,
                    "root_id": run.root_id,
                    "revision_id": run.revision_id,
                    "executed": False,
                    "symbol": None,
                    "timeframe": None,
                    "initial_capital": None,
                    "final_equity": None,
                    "net_profit": None,
                    "net_profit_pct": None,
                    "max_drawdown": None,
                    "max_drawdown_pct": None,
                    "total_trades": 0,
                    "winning_trades": 0,
                    "trade_seq_range": None,
                    # A non-executing object runs no bar-replay → it HAS no equity curve
                    # of its own (empty, never a fabricated flat line).
                    "equity_curve": [],
                    "note": "non_executing_participating_object",
                }
            )
            continue
        summary = out.summary
        run_initial = _dec(summary["initial_capital"])
        run_net = _dec(summary["net_profit"])
        base = initial + running_net  # portfolio equity before this run's trades
        lo_seq = len(combined_trades) + 1
        run_winners = 0
        for idx, trade in enumerate(out.trades):
            seq = len(combined_trades) + 1
            combined_trades.append(replace(trade, seq=seq))
            if trade.pnl > _ZERO:
                winners += 1
                run_winners += 1
                gross_profit += trade.pnl
            else:
                gross_loss += -trade.pnl
            if trade.exit_reason == "stop_loss":
                stops += 1
                stop_streak += 1
                max_stop_streak = max(max_stop_streak, stop_streak)
            else:
                stop_streak = 0
            # Each closed trade has exactly one equity point (index +1 past the seed);
            # rebase the run's realized equity onto the portfolio offset.
            run_point = out.equity_points[idx + 1]
            portfolio_equity = (base + (run_point.equity - run_initial)).quantize(_MONEY)
            peak = max(peak, portfolio_equity)
            drawdown = (peak - portfolio_equity).quantize(_MONEY)
            combined_equity.append(
                EquityPoint(
                    seq=seq,
                    timestamp=run_point.timestamp,
                    equity=portfolio_equity,
                    drawdown=drawdown,
                    exposure=run_point.exposure,
                )
            )
        hi_seq = len(combined_trades)
        for event in out.signal_events:
            combined_events.append(
                SignalEventRow(
                    seq=len(combined_events),
                    event_time=event.event_time,
                    event_type=event.event_type,
                    direction=event.direction,
                    # F-10: bind every decision-trace event to the exact executing item's
                    # pinned object revision, so a reviewer resolves the rule id back to the
                    # immutable Strategy/Package revision the run actually replayed.
                    detail={
                        **event.detail,
                        "item_id": run.item_id,
                        "root_id": run.root_id,
                        "revision_id": run.revision_id,
                    },
                )
            )
        running_net += run_net
        symbols.add(summary.get("symbol"))
        timeframes.add(summary.get("timeframe"))
        entry_models.add(str(out.diagnostics.get("entry_model")))
        for key in _DIAG_SUM_KEYS:
            diag_totals[key] += int(out.diagnostics.get(key) or 0)
        warnings.extend(f"item:{run.item_id}:{w}" for w in out.diagnostics.get("warnings", []))
        per_item.append(
            {
                "item_id": run.item_id,
                "item_kind": run.item_kind,
                "root_id": run.root_id,
                "revision_id": run.revision_id,
                "executed": True,
                "symbol": summary.get("symbol"),
                "timeframe": summary.get("timeframe"),
                # Per-item basic metrics are the item's OWN standalone bar-replay figures
                # (on its own ``initial_capital`` basis), NOT its portfolio-rebased slice —
                # so a per-item drawdown/PnL is the strategy's isolated performance, exactly
                # as if it had run alone. The composite (portfolio) figures live in
                # ``summary_out``; these attribute each contribution back to its strategy.
                "initial_capital": run_initial,
                "final_equity": _dec(summary["final_equity"]),
                "net_profit": run_net,
                "net_profit_pct": summary.get("net_profit_pct"),
                "max_drawdown": _dec(summary.get("max_drawdown") or _ZERO),
                "max_drawdown_pct": summary.get("max_drawdown_pct"),
                "total_trades": len(out.trades),
                "winning_trades": run_winners,
                "trade_seq_range": [lo_seq, hi_seq] if out.trades else None,
                # The item's OWN equity curve (one seed point + one per closed trade, on its
                # own capital basis). ``combine_item_runs`` previously discarded these and
                # kept only the portfolio-rebased composite curve; persisting them lets the
                # Result surface a per-strategy equity progression. Decimals stringify at
                # the JSONB persist boundary (``_jsonable``).
                "equity_curve": [
                    {
                        "seq": p.seq,
                        "timestamp": p.timestamp,
                        "equity": p.equity,
                        "drawdown": p.drawdown,
                    }
                    for p in out.equity_points
                ],
            }
        )

    total_trades = len(combined_trades)
    final_equity = (initial + running_net).quantize(_MONEY)
    net_profit = running_net.quantize(_MONEY)
    net_profit_pct = (net_profit / initial * _HUNDRED).quantize(_PCT) if initial > _ZERO else None
    max_drawdown = max((p.drawdown for p in combined_equity), default=_ZERO)
    max_drawdown_pct = (
        (max_drawdown / peak * _HUNDRED).quantize(_PCT) if peak > _ZERO else _ZERO.quantize(_PCT)
    )
    win_rate = (
        (Decimal(winners) / Decimal(total_trades) * _HUNDRED).quantize(_PCT)
        if total_trades
        else None
    )
    profit_factor = (gross_profit / gross_loss).quantize(_RATIO) if gross_loss > _ZERO else None
    romad = (
        (net_profit_pct / max_drawdown_pct).quantize(_RATIO)
        if net_profit_pct is not None and max_drawdown_pct > _ZERO
        else None
    )
    symbol = next(iter(symbols)) if len(symbols) == 1 else None
    timeframe = next(iter(timeframes)) if len(timeframes) == 1 else None

    summary_out: dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "initial_capital": initial,
        "final_equity": final_equity,
        "net_profit": net_profit,
        "net_profit_pct": net_profit_pct,
        "max_drawdown": max_drawdown.quantize(_MONEY),
        "max_drawdown_pct": max_drawdown_pct,
        "romad": romad,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_trades": total_trades,
        "total_stops": stops,
        "max_stop_streak": max_stop_streak,
        "total_winning_trades": winners,
    }
    if len(executing) > 1:
        warnings.append(COMPOSITION_CURVE_WARNING)
    composition: dict[str, Any] = {
        "strategy_count": len(executing),
        "participating_item_count": len(runs),
        "capital_allocation": "shared_pool" if shared_pool else "independent",
        "items": per_item,
    }
    if len(executing) > 1:
        # Contribution needs at least two executing strategies: a correlation matrix is
        # meaningless for one curve and "the composition without its only strategy" is
        # an empty universe. Computed here (server-side, run time) so it is part of the
        # immutable Result and the UI can only render it verbatim.
        composition["contribution"] = _contribution_block(
            executing,
            portfolio_initial=initial,
            shared_pool=shared_pool,
            full_summary=summary_out,
        )
    diagnostics = {
        "engine_kind": "v1_bar_replay_composition",
        "entry_model": next(iter(entry_models)) if len(entry_models) == 1 else "mixed",
        "reproducibility_note": (
            "Deterministic per-strategy bar-replay over each pinned market revision, "
            "composed in deterministic manifest pin order into one portfolio result."
        ),
        "item_count": item_count,
        "decision_trace_count": len(combined_events),
        "composition": composition,
        "execution_key": execution_key,
        "warnings": warnings,
        **diag_totals,
    }
    return EngineOutput(
        summary=summary_out,
        trades=combined_trades,
        equity_points=combined_equity,
        signal_events=combined_events,
        diagnostics=diagnostics,
    )
