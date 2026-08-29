"""The engine's output assembly: summary, L4 warnings and the diagnostics block (K-11b).

``run_engine`` ends by turning the finished ``_Ledger`` and the run's resolved settings
into an ``EngineOutput``. That tail was 390 lines of the function — a third of everything
outside the bar loop — and none of it replays a bar: it is a pure projection of
``(ctx, led)``, which is exactly why it separates cleanly.

Why this is worth its own module rather than more lines in ``engine``: the diagnostics
dict is PERSISTED into the immutable Result artifact and read back by users, so its
contents are contract, not debug output. Until now the only way to exercise a
provenance key was to replay a strategy that reached the branch that sets it; now the
projection can be tested directly.

Leaf by construction — it imports from ``execution.*`` and ``indicators`` and NEVER from
``engine``, so the dependency stays one-way and no cycle forms. ``EngineOutput`` itself
is deliberately still built by ``run_engine``: keeping the return type in ``engine``
avoids moving a public dataclass for no behavioural gain.

The three reporting constants blocks below moved here verbatim from ``engine``, which
re-exports them so existing imports keep resolving.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from entropia.domain.backtest.execution.constants import _HUNDRED, _MONEY, _PCT, _RATIO, _ZERO
from entropia.domain.backtest.execution.sizing import _leverage_multiplier
from entropia.domain.backtest.execution.state import FILTERED_EVENT_TYPES, _Ledger, _RunConfig
from entropia.domain.backtest.indicators import BUILTIN_ENTRY_MODEL, VOLUME_WEIGHTED_KEYS

# Rolling look-back for the TEST-ONLY breakout entry/exit fixture (F-04). A constant of
# the engine version (part of the reproducibility contract via ``engine_version``), NOT a
# strategy input; production runs always drive entries from a resolved indicator plan.
_BREAKOUT_WINDOW = 20
ENTRY_MODEL = "deterministic_bar_breakout_proxy_v1"


# F-10 complete decision trace (doc 15 §9.3 step 8, §14, §16). The full event taxonomy the
# bar-replay engine emits, so a reviewer can reconstruct WHY every position opened / did not
# open / changed / closed. A signal/decision event is never conflated with a real fill.
DECISION_TRACE_SCHEMA = "v1"
DECISION_TRACE_EVENT_TYPES = (
    "entry_signal",  # strategy decided to enter (rule id + per-condition evidence)
    "entry_fill",  # a position actually opened (execution)
    "entry_scheduled",  # a deferred entry was scheduled to a future bar (F-07a timing)
    "limit_order_placed",  # a resting limit ENTRY order was placed (F-07b, §2)
    "limit_order_cancelled",  # a resting limit order expired/ended unfilled (F-07b, §2)
    "stop_order_placed",  # a resting stop ENTRY trigger was placed (F-07h, §6.2/§6.3)
    "stop_order_triggered",  # a stop trigger fired: market-like fill or limit armed (F-07h)
    "stop_order_cancelled",  # a stop trigger never fired by end-of-data (F-07h)
    "entry_blocked",  # a wanted entry produced no fill (sizing / sleeve capacity)
    # a signal was filtered with NO fill attempt; the detail's ``reason`` says why:
    # "direction_restriction" (direction bias), "restriction_blocked" (an active
    # Restrictions/Filters rule, F-07e), "stacking_ignored" / "stacking_scale_only"
    # (same-direction conflict policy, F-07e), "hedge_ignored" (opposite-direction
    # conflict policy, F-07e).
    "filtered_no_entry",
    "exit_scheduled",  # a deferred exit was scheduled to a future bar (F-07a timing)
    "position_partial_close",  # an exit signal closed part of the position (F-07c close_percentage)
    "scale_layer_added",  # a same-direction layer was added to the open position (F-07d scaling)
    "scale_layer_rejected",  # a scaling candidate was rejected by an exposure/size cap (F-07d)
    "stack_entry_added",  # a same-direction signal STACKED onto the open position (F-07e)
    "stack_entry_rejected",  # a stack candidate was rejected by a size/sleeve cap (F-07e)
    "position_close",  # a position closed (trade linkage + exit reason + realized pnl)
    "stop_resolution",  # multi-rule / logic stop resolution (F-08 combination engine)
    "stop_exit_collision",  # same-bar stop+exit tie-break decision (§5.9)
    # §5.9 flat-position entry+exit tie-break: while FLAT, an entry and an explicit
    # exit are close-confirmed by the same bar and OHLCV carries no ordering between
    # them; the traced decision names the governing policy and its resolution (PR #513).
    "entry_exit_collision",
    "funding_charge",  # a funding rate applied to the open position (F-11, doc 12 §8.4)
    # F-07i (C): a limit order filled PARTIALLY — the fraction computed from the intrabar
    # print path's trade sizes vs the intended size; the detail carries the governing
    # partial-fill policy + the remainder's disposition (rest / market / cancel / reject).
    "partial_fill",
)
# F-07i (C): every decision class the taxonomy names is now modelled. ``partial_fill``
# left this list when the intrabar print path (tick sizes) made the filled fraction of a
# limit order computable — over plain OHLCV it stays fail-closed via
# ``order_execution_is_modelled`` (a non-``not_allowed`` policy without tick data is a
# Ready Check blocker + an inert run), never a fabricated fraction.
UNMODELLED_DECISION_CLASSES: tuple[str, ...] = ()


# Portfolio-level rules enforce FORWARD-only in deterministic pin order: a later-pinned
# item replays against the earlier items' completed held windows, and an earlier item is
# never re-simulated because of a later one (a genuine unified-clock co-simulation stays
# deferred — the ``execution.portfolio.COMPOSITION_CURVE_WARNING`` boundary). Emitted on
# every rules-active run so the precedence is auditable (L4), never an implicit assumption.
PORTFOLIO_RULES_SEQUENTIAL_WARNING = "portfolio_rules_sequential_pin_order_precedence"


def build_summary(ctx: _RunConfig, led: _Ledger) -> dict[str, Any]:
    """The run's headline metrics, quantized through the reproducibility constants.

    Every ratio here is None rather than 0 when its denominator is absent — no trades
    means no win rate, no losses means no profit factor. A fabricated 0.0 would read as
    a real measurement of a bad strategy instead of an absent one."""
    total_trades = len(led.trades)
    net_profit = (led.equity - ctx.initial_capital).quantize(_MONEY)
    net_profit_pct = (
        (net_profit / ctx.initial_capital * _HUNDRED).quantize(_PCT)
        if ctx.initial_capital > _ZERO
        else None
    )
    max_drawdown = max((p.drawdown for p in led.equity_points), default=_ZERO)
    max_drawdown_pct = (
        (max_drawdown / led.peak * _HUNDRED).quantize(_PCT)
        if led.peak > _ZERO
        else _ZERO.quantize(_PCT)
    )
    win_rate = (
        (Decimal(led.winners) / Decimal(total_trades) * _HUNDRED).quantize(_PCT)
        if total_trades
        else None
    )
    profit_factor = (
        (led.gross_profit / led.gross_loss).quantize(_RATIO) if led.gross_loss > _ZERO else None
    )
    romad = (
        (net_profit_pct / max_drawdown_pct).quantize(_RATIO)
        if net_profit_pct is not None and max_drawdown_pct > _ZERO
        else None
    )

    summary: dict[str, Any] = {
        "symbol": ctx.config.data.instrument_id,
        "timeframe": ctx.timeframe,
        # F-05: the ACTUAL first/last bar timestamps replayed (post-filter), never
        # the requested config.data.backtest_range bounds — proves the manifest
        # range matches the data actually processed (spec F-05 acceptance).
        "period_start": led.first_ts or None,
        "period_end": led.last_bar.timestamp if led.last_bar is not None else None,
        "initial_capital": ctx.initial_capital,
        "final_equity": led.equity,
        "net_profit": net_profit,
        "net_profit_pct": net_profit_pct,
        "max_drawdown": max_drawdown.quantize(_MONEY),
        "max_drawdown_pct": max_drawdown_pct,
        "romad": romad,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_trades": total_trades,
        "total_stops": led.stops_hit,
        "max_stop_streak": led.max_stop_streak,
        "total_winning_trades": led.winners,
        # F-11: cumulative signed funding cost booked against equity (positive = net paid).
        # Already reflected in ``final_equity`` / ``net_profit``; surfaced so the funding
        # contribution is auditable on its own.
        "funding_paid": led.funding_paid.quantize(_MONEY),
    }
    return summary


def build_warnings(ctx: _RunConfig, led: _Ledger) -> list[str]:
    """The L4 warning list: every boundary the run hit, surfaced and never hidden.

    Two kinds of line appear. A ``*_unsupported`` / ``capability_not_in_build`` warning
    is the engine's fail-closed BACKSTOP — Ready Check should have blocked the run, so
    reaching here means a stale readiness state got past admission and the run opened NO
    position. The rest record a modelling boundary the run legitimately ran into (a
    single-currency pool assumption, a degraded partial-fill evidence set).

    Order is deliberate and pinned by the golden digest: it is the order a reader of the
    Result sees, so it is part of the output, not an implementation detail."""
    warnings: list[str] = []
    if not led.bars_seen:
        warnings.append("no_bars_in_source")
    if ctx.rules_active:
        # Portfolio-rules provenance (L4 — every boundary surfaced, never silent):
        # sequential pin-order precedence is inherent to every rules-active run; the
        # rest fire only when their condition actually held.
        warnings.append(PORTFOLIO_RULES_SEQUENTIAL_WARNING)
        if ctx.conflict_downgraded_from_net:
            warnings.append("conflict_policy_net_executed_as_block_opposite")
        if ctx.conflict_policy_unknown:
            warnings.append("portfolio_conflict_policy_unknown_fail_closed")
        if ctx.portfolio_rules is not None and ctx.portfolio_rules.exposure_percent_invalid:
            warnings.append("portfolio_max_exposure_unparseable_zero_cap")
        if led.portfolio_symbol_unknown_gate:
            warnings.append("portfolio_conflict_symbol_unknown_fail_closed")
        if led.portfolio_time_unparseable_gate:
            warnings.append("portfolio_rules_time_unparseable_fail_closed")
    if ctx.tick_alignment_unavailable:
        # F-07i (B): a tick stream was injected but the pinned revision carries no
        # supported bar timeframe, so prints cannot be attributed to bar windows — the
        # run stayed on the conservative OHLCV model (L4, never silently guessed).
        warnings.append("tick_alignment_unavailable")
    if led.partial_evidence_missing:
        # F-07i (C): a partial-fill policy was active but the touching prints carried no
        # usable trade sizes — the filled fraction is unknowable from this revision, so
        # those fills degraded to the coarse full-fill model (L4, never a fabricated
        # fraction).
        warnings.append("partial_fill_evidence_unavailable")
    for option in ctx.future_dev_selected:
        # F-05: the strategy selected an option this build does not execute at all, so the
        # run opened NO position. Ready Check raises STRATEGY_CAPABILITY_NOT_IN_BUILD — this
        # L4 warning is the engine backstop when a stale readiness state reaches the worker.
        # One warning PER selection (not one summary line) so the Result's diagnostics name
        # every offending option, matching how the other fail-closed gates report.
        warnings.append(f"capability_not_in_build:{option.field_path}={option.value}")
    if not ctx.sizing_ok:
        # formula sizing (and a risk_based request without its sub-config) is not
        # modelled; the run opened NO position (fail closed, F-09) rather than a
        # notional all-in. Surface the divergence rather than hide it (L4).
        # risk_based_sizing with a sub-config IS honored.
        warnings.append(f"position_sizing_method_unsupported:{ctx.config.position_sizing.method}")
    if not ctx.leverage_ok:
        # Cross-margin (needs a portfolio risk model the engine does not implement) or a
        # non-positive saved multiplier is not modelled; the run opened NO position (fail
        # closed, F-07f). Ready Check raises STRATEGY_LEVERAGE_UNSUPPORTED — this L4
        # warning is the engine backstop when a stale readiness state reaches the worker.
        warnings.append(f"leverage_unsupported:{ctx.config.position_sizing.leverage_mode}")
    if not ctx.strength_ok:
        # A trend- / divergence-adjusted signal-strength mode is not modelled (the saved
        # schema carries no condition refs / multiplier / band config to execute it,
        # Master Ref §10.3); the run opened NO position (fail closed, F-07g) rather than
        # silently sizing un-adjusted. Ready Check raises
        # STRATEGY_SIGNAL_STRENGTH_UNSUPPORTED — this L4 warning is the engine backstop
        # when a stale readiness state reaches the worker.
        warnings.append(f"signal_strength_unsupported:{ctx.strength_mode}")
    if not ctx.timing_ok:
        # An unsupported entry/exit execution timing (intrabar_touch / a limit or
        # stop-limit simulation) is not modelled over plain OHLCV; the run opened NO
        # position (fail closed, F-07a) rather than silently filling at the candle
        # close. Ready Check raises STRATEGY_EXECUTION_TIMING_UNSUPPORTED — this L4
        # warning is the engine backstop when a stale readiness state reaches the worker.
        execution = ctx.config.data.execution
        warnings.append(
            f"execution_timing_unsupported:{execution.entry_timing}/{execution.exit_timing}"
        )
    if not ctx.order_ok:
        # An unsupported order variant (a stop / stop-limit with a missing or invalid
        # trigger, a best_bid_ask price rule — no quote series over OHLCV — or a
        # partial-fill policy other than not_allowed) is not modelled; the run opened NO
        # position (fail closed, F-07b/F-07h) rather than silently market-filling.
        # Ready Check raises STRATEGY_ORDER_TYPE_UNSUPPORTED — this L4 warning is the engine
        # backstop when a stale readiness state reaches the worker.
        warnings.append(f"order_type_unsupported:{ctx.order_cfg.type}")
    if not ctx.partial_close_ok:
        # A partial close (close_percentage < 100) with a trailing-stop aftermath but NO
        # protection-level trailing_stop configured/enabled is not modelled (post-V1 (f):
        # the aftermath has no trailing parameters of its own to reuse); the run opened NO
        # position (fail closed, F-07c/f) rather than silently ignoring the aftermath.
        # Ready Check raises STRATEGY_PARTIAL_CLOSE_UNSUPPORTED — this L4 warning is the
        # engine backstop. move_stop_to_entry / lock_in_profit / close_all are always
        # modelled and never reach here.
        warnings.append(f"partial_close_unsupported:{ctx.partial_aftermath}")
    if not ctx.scaling_ok:
        # An enabled scaling config the ladder cannot execute (logic-based scaling, a
        # per-layer timeframe override, a missing/non-positive add size, or a misconfigured
        # cap) is not modelled; the run opened NO position (fail closed, F-07d) rather than
        # silently running un-scaled. Ready Check raises STRATEGY_SCALING_UNSUPPORTED —
        # this L4 warning is the engine backstop.
        unsupported_method = (
            ctx.scaling_cfg.method
            if ctx.scaling_cfg is not None and ctx.scaling_cfg.method is not None
            else "unconfigured"
        )
        warnings.append(f"scaling_unsupported:{unsupported_method}")
    if not ctx.restrictions_ok:
        # An enabled restriction filter the replay cannot decide (volatility / spread /
        # volume / correlation, a non-block action, or an unparseable config) is not
        # modelled; the run opened NO position (fail closed, F-07e) rather than silently
        # trading through the filter. Ready Check raises STRATEGY_RESTRICTIONS_UNSUPPORTED —
        # this L4 warning is the engine backstop.
        # The set comes from the prologue's own parse (the same one that decided
        # ``restrictions_ok``) rather than being re-derived here: a warning that named a
        # different set than the gate which opened no position would misreport why the
        # run was inert. Already sorted at the source, so the string is stable.
        warnings.append("restrictions_unsupported:" + ",".join(ctx.unmodelled_restriction_types))
    if not ctx.conflict_ok:
        # A true hedge (allow_hedge with exit-on-opposite off) needs two concurrent
        # opposite positions the single-position replay cannot honestly simulate; the run
        # opened NO position (fail closed, F-07e). Ready Check raises
        # STRATEGY_CONFLICT_HANDLING_UNSUPPORTED — this L4 warning is the engine backstop.
        warnings.append("conflict_handling_unsupported:allow_hedge_without_exit_on_opposite")
    if ctx.indicator_plan is not None:
        # Blocks the native-trigger foundation could not compute (deferred sources,
        # timeframe overrides, non-directional keys) are surfaced, never hidden (L4).
        warnings.extend(ctx.indicator_plan.unresolved)
        if not ctx.plan_active:
            # Reachable ONLY under builtin_breakout_fixture=True (a test passing an empty
            # plan); production fails closed before this point (F-04, UnresolvedStrategyError).
            warnings.append("indicator_plan_empty_fallback_proxy")
    if ctx.alloc_on:
        # FX conversion across a mixed-currency pool is out of scope (GAP-16); the run
        # assumes a single-currency portfolio pool — surfaced, never hidden (L4).
        warnings.append("allocation_single_currency_pool_assumed")
        if ctx.item_share <= _ZERO:
            # Allocation is enabled but the replayed item has no active entry → a
            # 0-capital sleeve → no fills. Surface it rather than silently fall back to
            # the strategy's own independent capital (L4).
            warnings.append("allocation_item_not_in_active_plan")
    return warnings


def build_diagnostics(ctx: _RunConfig, led: _Ledger, warnings: list[str]) -> dict[str, Any]:
    """The provenance block persisted into the immutable Result artifact.

    For each modelled capability it reports the SAVED setting, whether this engine
    version models it, and the outcome counts — so a Result can be read back to the
    exact configuration that produced it without re-deriving anything. The
    saved-vs-executed pairs matter most: ``portfolio_conflict_policy`` next to
    ``portfolio_conflict_policy_executed`` is what keeps NET's conservative downgrade
    visible instead of silently reported as honored."""
    condition_count = (
        sum(len(spec.conditions) for spec in ctx.indicator_plan.entry_specs)
        + sum(len(spec.conditions) for spec in ctx.indicator_plan.exit_specs)
        if ctx.plan_active and ctx.indicator_plan is not None
        else 0
    )
    multi_timeframe_blocks = (
        sum(1 for spec in ctx.indicator_plan.entry_specs if spec.resample_seconds)
        + sum(1 for spec in ctx.indicator_plan.exit_specs if spec.resample_seconds)
        if ctx.plan_active and ctx.indicator_plan is not None
        else 0
    )
    # Conditions whose RHS reference indicator computes on a coarser per-condition
    # timeframe than its parent block (post-V1 (i)) — surfaced for reproducibility audits.
    per_condition_timeframe_conditions = (
        sum(
            1
            for spec in (*ctx.indicator_plan.entry_specs, *ctx.indicator_plan.exit_specs)
            for cond in spec.conditions
            if cond.reference_resample_seconds
        )
        if ctx.plan_active and ctx.indicator_plan is not None
        else 0
    )
    # Conditions whose RHS is an N-ary reference chain (>2 packages compared — post-V1 (ii)):
    # source vs a monotonic fan of separately-pinned indicators — surfaced for audits.
    nary_reference_conditions = (
        sum(
            1
            for spec in (*ctx.indicator_plan.entry_specs, *ctx.indicator_plan.exit_specs)
            for cond in spec.conditions
            if cond.extra_references
        )
        if ctx.plan_active and ctx.indicator_plan is not None
        else 0
    )
    # Blocks/reference legs computed as a volume-weighted price line (VWAP — post-V1 (d)):
    # the first directional key whose compute consumes the bars' volume — surfaced for audits.
    vwap_blocks = (
        sum(
            1
            for spec in (*ctx.indicator_plan.entry_specs, *ctx.indicator_plan.exit_specs)
            if spec.canonical_key in VOLUME_WEIGHTED_KEYS
        )
        + sum(
            1
            for spec in (*ctx.indicator_plan.entry_specs, *ctx.indicator_plan.exit_specs)
            for cond in spec.conditions
            if cond.reference_key in VOLUME_WEIGHTED_KEYS
            or any(leg.key in VOLUME_WEIGHTED_KEYS for leg in cond.extra_references)
        )
        if ctx.plan_active and ctx.indicator_plan is not None
        else 0
    )
    entry_model = BUILTIN_ENTRY_MODEL if ctx.plan_active else ENTRY_MODEL
    reproducibility_note = (
        "Deterministic bar-replay over the pinned market revision; real bars, "
        "protection stops and built-in indicator native triggers."
        if ctx.plan_active
        else "Deterministic bar-replay over the pinned market revision; real bars and "
        "protection stops, deterministic breakout entry fixture (test-only — production "
        "requires a resolved indicator plan)."
    )
    diagnostics = {
        "engine_kind": "v1_bar_replay",
        "entry_model": entry_model,
        "reproducibility_note": reproducibility_note,
        "bars_processed": led.bars_seen,
        "breakout_window": _BREAKOUT_WINDOW,
        "indicator_blocks": len(ctx.entry_evals),
        "condition_blocks": condition_count,
        "multi_timeframe_blocks": multi_timeframe_blocks,
        "per_condition_timeframe_conditions": per_condition_timeframe_conditions,
        "nary_reference_conditions": nary_reference_conditions,
        "vwap_blocks": vwap_blocks,
        "position_size_limits_active": ctx.config.position_sizing.position_size_limits is not None,
        # F-05: capability-matrix provenance. ``capabilities_modelled`` false means at least
        # one selected option is future_dev in this build, so the run was financially inert;
        # ``capability_not_in_build`` names each one as "<field_path>=<value>" so a Result can
        # be read back to the exact options that blocked it without re-deriving the matrix.
        "capabilities_modelled": ctx.capability_ok,
        "capability_not_in_build": [
            f"{option.field_path}={option.value}" for option in ctx.future_dev_selected
        ],
        # F-07f: leverage provenance (§10.2) — the resolved multiplier actually applied to
        # every computed position size (1x when unleveraged or 'no_leverage' normalized).
        "leverage_mode": ctx.config.position_sizing.leverage_mode,
        "leverage_modelled": ctx.leverage_ok,
        "leverage_multiplier": (str(_leverage_multiplier(ctx.config)) if ctx.leverage_ok else None),
        # F-07g: signal-strength provenance (§10.3) — the saved adjustment mode, whether
        # this engine version models it, and how many signal-driven entry decisions
        # computed a non-neutral (≠1x) multiplier.
        "signal_strength_mode": ctx.strength_mode,
        "signal_strength_modelled": ctx.strength_ok,
        "strength_adjustments": led.strength_adjustments,
        "entry_timing": ctx.config.data.execution.entry_timing,
        "exit_timing": ctx.config.data.execution.exit_timing,
        "execution_timing_modelled": ctx.timing_ok,
        "deferred_entry_fills": led.deferred_entry_fills,
        "deferred_exit_fills": led.deferred_exit_fills,
        # F-07b: order-type execution provenance + limit-order working-order counts.
        "order_type": ctx.order_cfg.type,
        "order_execution_modelled": ctx.order_ok,
        "limit_orders_placed": led.limit_orders_placed,
        "limit_orders_filled": led.limit_orders_filled,
        "limit_orders_cancelled": led.limit_orders_cancelled,
        "stop_orders_placed": led.stop_orders_placed,
        "stop_orders_triggered": led.stop_orders_triggered,
        "stop_orders_cancelled": led.stop_orders_cancelled,
        # F-07c: partial-close provenance + count (an exit signal closed part of a position).
        "close_percentage": str(ctx.exit_logic.close_percentage),
        "partial_aftermath": ctx.partial_aftermath,
        "partial_close_modelled": ctx.partial_close_ok,
        "partial_closes": led.partial_closes,
        # F-07f: trailing stop profit-lock provenance — whether the protection-level
        # activation threshold is configured at all, and how many lock events (a
        # lock_in_profit ratchet, or a trailing_stop aftermath force-activation) fired.
        "trailing_lock_in_active": ctx.trailing_lock_in_active,
        "lock_in_locks": led.lock_in_locks,
        # F-07d: same-direction scaling provenance + ladder counts.
        "scaling_enabled": ctx.scaling_enabled,
        "scaling_method": ctx.scaling_cfg.method
        if ctx.scaling_enabled and ctx.scaling_cfg
        else None,
        "scaling_modelled": ctx.scaling_ok,
        "scale_layers_added": led.scale_layers_added,
        "scale_layers_rejected": led.scale_layers_rejected,
        "max_total_exposure_active": ctx.scale_max_total is not None,
        # F-07e: restrictions & filters provenance + entry-gate counts.
        "restrictions_rule": ctx.restriction_rule,
        "restrictions_modelled": ctx.restrictions_ok,
        "active_filter_types": sorted(
            {rf.filter_type for rf in ctx.restrictions_cfg.filters if rf.enabled}
        ),
        "entries_blocked_by_restriction": led.entries_blocked_by_restriction,
        # F-07e: conflict / position handling provenance + policy-outcome counts.
        "conflict_handling_modelled": ctx.conflict_ok,
        "overlapping_signal_policy": ctx.overlap_policy,
        "same_direction_stacking": ctx.stacking_policy,
        "opposite_direction_hedge": ctx.hedge_policy,
        "exit_on_opposite_signal": bool(ctx.conflict_cfg.exit_on_opposite_signal),
        "stack_entries_added": led.stack_entries_added,
        "stack_entries_rejected": led.stack_entries_rejected,
        "positions_replaced": led.positions_replaced,
        "opposite_signal_closes": led.opposite_signal_closes,
        "conflict_signals_ignored": led.conflict_signals_ignored,
        "stop_exit_conflict": ctx.stop_exit_conflict,
        "stop_exit_collisions": led.stop_exit_collisions,
        "logic_stop_blocks": len(ctx.stop_evals),
        "stop_trigger_requirement": ctx.stop_trigger_requirement,
        "stop_conflict_resolution": ctx.stop_conflict_resolution,
        "logic_stop_triggers": led.logic_stop_triggers,
        # #549: how many stop exits filled at the bar OPEN because the bar gapped past the
        # level. Reported beside the stop policy because it explains a result the policy
        # alone cannot: two runs of the same strategy differ here purely by the data's gaps.
        "gap_adjusted_stops": led.gap_adjusted_stops,
        "allocation_enabled": ctx.alloc_on,
        "allocation_compounding": ("compound" if ctx.alloc_compound else "fixed")
        if ctx.alloc_on
        else None,
        "allocation_items_executed": 1 if (ctx.alloc_on and ctx.item_share > _ZERO) else 0,
        "allocation_sleeve_cap_active": ctx.alloc_on and ctx.item_share > _ZERO,
        # Portfolio-level rules provenance (cross-item, doc 13 §8.4): the SAVED policy
        # token vs the EXECUTED one (NET's conservative downgrade stays visible), the
        # resolved money cap, how many prior-item windows constrained this replay and
        # every gate outcome count.
        "portfolio_rules_active": ctx.rules_active,
        "portfolio_conflict_policy": (
            ctx.portfolio_rules.conflict_policy if ctx.portfolio_rules is not None else None
        ),
        "portfolio_conflict_policy_executed": (
            ("block_opposite" if ctx.conflict_gate_on else "keep_separate")
            if ctx.rules_active
            else None
        ),
        "portfolio_max_total_exposure_cap": (
            str(ctx.portfolio_cap_amount) if ctx.portfolio_cap_amount is not None else None
        ),
        "portfolio_prior_intervals": (
            len(ctx.portfolio_rules.prior_intervals) if ctx.portfolio_rules is not None else 0
        ),
        "portfolio_conflict_blocked_entries": led.portfolio_conflict_blocked_entries,
        "portfolio_exposure_blocked_entries": led.portfolio_exposure_blocked_entries,
        "portfolio_exposure_clamped_entries": led.portfolio_exposure_clamped_entries,
        # F-11: funding provenance + application counts (the used revision is pinned in the
        # manifest via the strategy config; surfaced here for the decision-trace audit).
        "funding_enabled": ctx.funding is not None,
        "funding_source_revision_id": ctx.funding.source_revision_id
        if ctx.funding is not None
        else None,
        "funding_records": len(ctx.funding_records),
        "funding_charges": led.funding_charges,
        # F-07i (B): intrabar tick-path provenance — whether a pinned tick stream was
        # injected, how many bars carried a print sub-path, and how many
        # first_trigger_wins stops the REAL print order resolved (vs the flagged
        # conservative OHLCV approximation).
        "tick_path_enabled": ctx.tick_batches is not None,
        "tick_bars": led.tick_bars,
        "tick_first_trigger_resolutions": led.tick_first_trigger_resolutions,
        # F-07i (C): tick-setting execution provenance — print-resolved resting-order
        # fills, partial fills (initial + remainder lots), same-bar stop-then-limit
        # sequences, touch-order placements and touch-exit fills.
        "tick_resolved_entry_fills": led.tick_resolved_entry_fills,
        "partial_fills": led.partial_fills,
        "same_bar_stop_limit_fills": led.same_bar_stop_limit_fills,
        "touch_orders_placed": led.touch_orders_placed,
        "touch_exit_fills": led.touch_exit_fills,
        "item_count": ctx.item_count,
        "decision_trace_count": len(led.signal_events),
        # I-02: the filter vetoes are their own artifact, so they are counted (and
        # named) separately — ``decision_trace_count`` is the SIGNAL journal's length,
        # never a merged total that would hide which trace a reader is looking at.
        "filtered_event_count": len(led.filtered_events),
        "filtered_event_types": sorted(FILTERED_EVENT_TYPES),
        "decision_trace_schema": DECISION_TRACE_SCHEMA,
        "decision_trace_event_types": list(DECISION_TRACE_EVENT_TYPES),
        "unmodelled_decision_classes": list(UNMODELLED_DECISION_CLASSES),
        "suppressed_entries": led.suppressed_entries,
        "execution_key": ctx.execution_key,
        "warnings": warnings,
    }
    return diagnostics
