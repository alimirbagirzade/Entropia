"""Deterministic V1 bar-replay backtest engine (Stage 5a → post-V1 Slice B, doc 15 §9.3).

Replaces the pure-from-key V1 stub with a real, deterministic bar-replay over the
pinned market revision's processed OHLCV bars (INF-12 Slice A: ``resolve_bar_source``
→ ``iter_bar_batches``). The simulation is a PURE function of
``(strategy_config, bars)``: the same pinned strategy revision + the same immutable
pinned market revision always yield byte-identical output (doc 15 §17 async
reproducibility). No DB, clock, network or real randomness.

Fail-closed entry model (F-04): production entry/exit timing uses REAL built-in
indicator signals — a run REQUIRES a resolved ``indicator_plan`` (post-V1 Slice C:
SMA/EMA/RMA/WMA/RSI/VWAP native triggers, condition blocks, multi-timeframe resampling).
A run with NO resolved trigger plan cannot materialize a Result: admission (Ready Check
``STRATEGY_INDICATOR_UNRESOLVED``) and the worker (``RUN_FAILED_UNRESOLVED_DEPENDENCY``)
both refuse it, and ``run_engine`` itself now raises ``UnresolvedStrategyError`` rather
than fabricate metrics from a strategy the user never defined. The historical
``entry_model=deterministic_bar_breakout_proxy_v1`` breakout is retained ONLY as an
explicit TEST-ONLY fixture (``run_engine(..., builtin_breakout_fixture=True)``) that
exercises the price/stop/cost/sizing machinery without a real indicator layer — it is
NEVER a production fallback. What is real either way: the bars, their timestamps/prices,
the strategy's protection stops (percentage / trailing / absolute), the direction bias,
the costs (commission / spread / slippage) and the position sizing.

Engine order is the CANONICAL, versioned doc 15 §9.3 sequence. Per bar, in this order:

  (1) include only Market/Research data available by the clock time — the bar itself
      (replayed strictly forward from the pinned revision) plus every research feed,
      each gated by ``research_data.time_policy.is_eligible_for_decision`` (K-02);
  (2) apply funding/fee/carry (K-03) — BEFORE anything this bar sizes or caps;
  (3) evaluate pending fills — (3) deferred open, (3b/3b2) resting limit + its partial
      remainder, (3c) resting stop trigger, (3d) deferred close (which by construction
      resolves at the bar's close, i.e. later in the code than steps 4-6 below);
  (4) evaluate protection/stop/exit rules against THIS bar's high/low (intrabar touch);
  (5) evaluate conflict/exposure/allocation constraints — the F-07e conflict/hedge policy
      plus the sleeve / ``max_total_exposure`` / position-size caps, which are evaluated
      at each sizing decision point (``_sized`` / ``_sleeve_capital``) rather than as one
      standalone block;
  (6) evaluate entry signals and schedule orders — (6a) the resolved indicator plan or
      (6b) the test-only breakout fixture;
  (7) evaluate same-direction scaling (the F-07d price-distance ladder);
  (8) write the state snapshot, decision trace and diagnostic counters.

K-03: step 2 is the ordering that makes the rest of the sequence honest. ``equity`` is
what sizes an entry and what bounds the allocation sleeve and exposure caps, so applying
funding at the END of the bar (the pre-K-03 order) sized every entry and every scale layer
off equity that had not yet paid its carry — under perp funding a one-directional
CUMULATIVE bias toward systematically larger positions and a late-binding
``max_total_exposure``. Steps 5 and 6 are interleaved in the code because the exposure /
sleeve / size caps bind at the point a size is computed; steps 3d and 4/6 are likewise
interleaved because a fill deferred to the bar's CLOSE cannot resolve before the close.
Those two deviations are structural, not a reordering of the economics — every other step
runs in canonical position, and the in-loop ``# (n)`` markers name their canonical step.

State/decision-trace counters are emitted per trade (bounded memory — never O(bars)); the
OHLCV stream is consumed one batch at a time.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from entropia.domain.allocation.enums import CompoundingMode
from entropia.domain.backtest.capabilities import (
    capabilities_are_modelled,
    future_dev_selections,
)
from entropia.domain.backtest.execution.booking import (
    absorb_remainder,
    close_position,
    emit_event,
)
from entropia.domain.backtest.execution.constants import (
    _HUNDRED,
    _MONEY,
    _ONE,
    _PCT,
    _QTY,
    _ZERO,
)
from entropia.domain.backtest.execution.costs import (
    FillCosts,
    FundingCharge,
    _cost_params,
    _effective_fill,
    due_funding_charges,
    resolve_funding_decision_time,
)
from entropia.domain.backtest.execution.fills import (
    _LIMIT_BACKED_ORDER_TYPES,
    _TICK_ENTRY_TIMINGS,
    _abs_stop_level,
    _fill_schedule,
    _first_trigger_index,
    _limit_price,
    _pct_stop_level,
    _resolve_stop,
    _StopOutcome,
    _Tick,
    _TickCursor,
    _touching_ticks,
    _trail_lock_in_pct,
    _trail_pct,
    decide_partial_fill,
    execution_timing_is_modelled,
    limit_touch_evidence,
    order_execution_is_modelled,
    tick_data_required,
)
from entropia.domain.backtest.execution.output import (
    _BREAKOUT_WINDOW,
    DECISION_TRACE_EVENT_TYPES,
    DECISION_TRACE_SCHEMA,
    ENTRY_MODEL,
    UNMODELLED_DECISION_CLASSES,
    build_diagnostics,
    build_summary,
    build_warnings,
)
from entropia.domain.backtest.execution.rules import (
    bar_epoch_ms,
    conflicts_with_prior,
    interval_covers,
    prior_exposure_at,
)
from entropia.domain.backtest.execution.scaling import (
    apply_partial_aftermath,
    layer_bucket,
    layer_timeframe,
    partial_close_is_modelled,
    resolve_scale_layer_size,
    resolve_scale_rejection,
    scale_threshold_crossed,
    scaling_is_modelled,
)
from entropia.domain.backtest.execution.sizing import (
    SIZE_RESOLVED_TO_ZERO,
    _cap_to_sleeve,
    _position_size,
    _sizing_is_honored,
    blocked_reason,
    leverage_is_modelled,
    max_position_size_cap,
    planned_size,
    sleeve_capital,
)
from entropia.domain.backtest.execution.state import (
    FILTERED_EVENT_TYPES,
    AllocationExecution,
    EquityPoint,
    PortfolioRules,
    PriorItemInterval,
    SignalEventRow,
    TradeRow,
    _Bar,
    _Ledger,
    _normalize,
    _Position,
    _RunConfig,
)
from entropia.domain.backtest.funding import FundingSchedule, parse_utc
from entropia.domain.backtest.indicators import (
    BlockEvaluator,
    IndicatorPlan,
    aggregate,
    build_evaluators,
    timeframe_seconds,
)

if TYPE_CHECKING:
    from entropia.domain.strategy.config import (
        RestrictionFilter,
        StrategyConfig,
    )


class UnresolvedStrategyError(ValueError):
    """``run_engine`` was invoked without a resolved indicator plan and without the
    explicit test-only breakout fixture opt-in (F-04). The engine FAILS CLOSED — it
    never fabricates metrics from a strategy the user did not define, so an unresolved
    or empty trigger plan can never materialize a Result. Production is already guarded
    twice upstream (Ready Check ``STRATEGY_INDICATOR_UNRESOLVED`` at admission + the
    worker's ``RUN_FAILED_UNRESOLVED_DEPENDENCY`` re-check); this is the engine's own
    last line of defence against a caller that bypasses both."""


@dataclass(frozen=True, slots=True)
class EngineOutput:
    summary: dict[str, Any]
    trades: list[TradeRow]
    equity_points: list[EquityPoint]
    signal_events: list[SignalEventRow]
    diagnostics: dict[str, Any]
    # Portfolio-rules slice: every FULLY-closed position's held window
    # ({entry_time, exit_time, direction, peak_notional}) — the raw material a
    # LATER-pinned item's portfolio constraints are built from
    # (``build_prior_intervals``). Not persisted into the Result artifact.
    position_intervals: list[dict[str, Any]] = field(default_factory=list)
    # I-02: the filter-veto journal, kept APART from ``signal_events`` and persisted as
    # its own ``filtered_events`` artifact (doc 15 §3.2 "View Filtered Events"; §16 —
    # the no-entry/filtered decision trace stays readable in its own right and is never
    # forced into the shape of a real fill). Appended LAST so every existing positional
    # construction keeps its meaning; ``run_engine`` and ``combine_item_runs`` set it.
    filtered_events: list[SignalEventRow] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ItemRun:
    """One enabled Mainboard composition item's contribution to a run (F-04, doc 01).

    The worker builds one ``ItemRun`` per ENABLED item in the immutable snapshot, in
    the manifest's deterministic pin order, and hands the list to
    ``combine_item_runs`` to assemble the single composite Result. ``output`` is:

    * the per-strategy ``EngineOutput`` for a Strategy item (an executing item), or
    * ``None`` for a participating-but-NON-executing item (Trading Signal / Trade Log):
      pinned + recorded for full traceability, but the V1 bar-replay engine runs no
      standalone simulation for it — its execution effect is defined only as a data
      input consumed by a Strategy (the honest V1 boundary, surfaced in diagnostics,
      never a silent phantom contribution).
    """

    item_id: str
    item_kind: str
    root_id: str | None
    revision_id: str | None
    output: EngineOutput | None
    # F-07 §4.4 — the item's human name as PINNED in the run manifest
    # (``mainboard_item_labels``), never looked up live. Carried through to the
    # immutable Result so its per-item and leave-one-out rows can be named; None
    # when the item had no label, in which case the UI shows the raw id.
    item_label: str | None = None


@dataclass(slots=True)
class _Pending:
    """A fill deferred to a FUTURE bar by the execution-timing setting (F-07a, §2).

    ``current_candle_close`` / ``market_fill_simulation`` fill immediately at the
    signal bar's close and never create a ``_Pending``. ``next_candle_open`` /
    ``next_candle_close`` defer the fill to the following bar: ``target_seq`` is the
    ``led.bars_seen`` index at which the fill executes (always the bar right after the
    signal), and ``at_open`` chooses that bar's open (resolved before the intrabar
    stop path) versus its close (resolved at end-of-bar, so an intrabar stop on the
    same bar pre-empts a scheduled close exit). At most one ``_Pending`` is ever
    outstanding: an entry pending exists only while flat, an exit pending only while
    in a position."""

    kind: str  # "entry" | "exit"
    at_open: bool  # fill at the target bar's OPEN (else its CLOSE)
    target_seq: int  # led.bars_seen index at which the fill executes (the next bar)
    direction: str  # entry direction ("" for an exit)
    reason: str  # exit reason ("" for an entry)
    # F-07g: the signal bar's strength multiplier — a deferred entry fill inherits its
    # SIGNAL bar's strength (the F-07e restriction-verdict precedent), never re-priced
    # at the fill bar. Inert 1x for exits and when no adjustment is active.
    strength: Decimal = _ONE


@dataclass(slots=True)
class _WorkingLimit:
    """A resting limit ENTRY order spanning bars until filled or expired (F-07b, §2).

    A ``limit_order`` does not fill at the decision bar (the signal is only known at that
    bar's close — a same-bar fill would look ahead). The order rests from the NEXT bar and
    fills at ``limit_price`` only if a bar's low (long buy) / high (short sell) reaches it
    within the validity window. ``expires_seq`` is the last ``led.bars_seen`` index the order is
    live (``None`` = until_cancelled → until fill or end-of-data). On the expiry bar, an
    unfilled order applies its ``unfilled_policy``: cancel / keep-until-validity (no fill),
    convert-to-market (fill at that bar's close), or re-price (a fresh limit each live bar,
    recomputed from the prior bar's close — no look-ahead). At most one is ever outstanding
    (it exists only while flat)."""

    direction: str  # "long" | "short"
    limit_price: Decimal  # current resting limit level (may re-price)
    offset: Decimal  # signed offset magnitude for re-pricing
    price_rule: str  # entry_signal_price / signal_price_(minus|plus)_offset
    unfilled_policy: str
    expires_seq: int | None  # last live led.bars_seen index (None = until_cancelled)
    # F-07g: the signal bar's strength multiplier — a limit fill (touch or convert-to-
    # market) inherits its SIGNAL bar's strength (the F-07e restriction-verdict
    # precedent), never re-priced at the fill bar. Inert 1x when no adjustment is active.
    strength: Decimal = _ONE
    # F-07i (C): ``remaining_size`` is the order-remaining ledger after a PARTIAL fill
    # (Master Ref §6.3 Partial Fill): while set, the order rests AGAINST the open
    # position it partially filled (``for_position_seq`` — the F-07b flat-only invariant
    # is deliberately relaxed for the remainder), topping the position up on later
    # touches until the validity/unfilled policy disposes of it; the remainder dies with
    # its position. An ``intrabar_touch`` ENTRY reuses this machinery verbatim (an
    # entry-signal-price rule, no offset, until-cancelled — see the placement site).
    remaining_size: Decimal | None = None
    for_position_seq: int | None = None
    # The bar_seq the remainder was (last) written — the top-up block never consumes the
    # SAME bar's evidence twice (the initial partial fill already exhausted it).
    remainder_placed_seq: int | None = None


@dataclass(slots=True)
class _WorkingStop:
    """A resting stop ENTRY trigger spanning bars until fired or end-of-data (F-07h, §6.2).

    A stop entry does not fill at the decision bar (the signal is only known at that bar's
    close — a same-bar trigger would look ahead). The trigger rests from the NEXT bar and
    fires when a bar's high (long buy-stop) / low (short sell-stop) reaches
    ``trigger_price``. A plain ``stop_order`` then fills market-like at
    ``max(trigger, open)`` (long; short mirror ``min``) — a gap through the trigger fills
    at the open, the trigger price no longer exists. A ``stop_limit_order``
    (``limit_price`` is not None) instead ARMS the F-07b ``_WorkingLimit`` machine: the
    limit rests from the bar AFTER the trigger bar (same-bar stop-then-limit ordering
    needs tick data — never modelled over OHLCV) and validity/unfilled policy apply
    verbatim from the trigger bar. The stop leg itself carries no validity (Master Ref
    §6.3: limit-specific fields are not used by the stop leg) — it rests until fired or
    end-of-data. At most one is ever outstanding (it exists only while flat)."""

    direction: str  # "long" | "short"
    trigger_price: Decimal  # the stop activation level (signal-derived, fixed)
    # Stop-limit only — the pre-computed limit leg armed on trigger (None = plain stop):
    limit_price: Decimal | None
    limit_offset: Decimal  # signed offset magnitude for limit re-pricing
    limit_rule: str  # limit price rule (entry_signal_price / signal±offset)
    unfilled_policy: str  # limit leg unfilled policy
    validity_bars: int | None  # limit live-bar count from the trigger bar (None = until_cancelled)
    # F-07g: the signal bar's strength multiplier — a stop fill (direct or via the armed
    # limit) inherits its SIGNAL bar's strength, never re-priced at the fill bar.
    strength: Decimal = _ONE


def _direction_flags(mode: str) -> tuple[bool, bool]:
    """(long_allowed, short_allowed) from the entry ``direction_mode``."""
    return mode in ("long", "long_and_short"), mode in ("short", "long_and_short")


# §10.3 Signal Strength Sizing (F-07g, Master Ref §10.3). ``no_adjustment`` is inert (a 1x
# multiplier — byte-identical baseline; Master Ref: "engineye dahil edilmez").
# ``volatility_adjusted`` IS executed: a deterministic, config-free inverse-volatility
# multiplier computed from the bars already replayed at the signal bar (doc 02 §6's canonical
# volatility-adjustment example: "düşük volatilitede daha büyük, yüksek volatilitede daha
# küçük pozisyon") — a calm recent tape relative to the look-back baseline reads as a
# STRONGER signal context (larger size), a turbulent one as WEAKER (smaller size). It derives
# from the BAR SERIES both entry models replay, so proxy mode and plan mode share one metric.
# ``trend_adjusted`` / ``divergence_adjusted`` are NOT modelled and FAIL CLOSED: the saved
# schema carries only the mode literal — none of the condition-package refs, adjustment
# formula or upper/lower band caps Master Ref §10.3 requires in the canonical payload — and
# there is no canonical trend/divergence formula to derive from OHLCV alone (never silently
# imitated; blocked at Ready Check + an inert engine run).
_MODELLED_STRENGTH_MODES = frozenset({"no_adjustment", "volatility_adjusted"})
# The strength look-back re-uses the engine's reproducibility-pinned window constant as the
# long baseline; the short window reads the most recent tape. Both are engine-version
# constants (part of the ``engine_version`` contract), NOT strategy inputs.
_STRENGTH_SHORT_WINDOW = 5
_STRENGTH_LONG_WINDOW = _BREAKOUT_WINDOW
_STRENGTH_MULT_MIN = Decimal("0.5")
_STRENGTH_MULT_MAX = Decimal("2.0")
_STRENGTH_QUANT = Decimal("0.0001")


def signal_strength_is_modelled(config: StrategyConfig) -> bool:
    """Public predicate: is this strategy's signal-strength adjustment modelled (F-07g)?

    The single shared source of truth for the readiness
    ``STRATEGY_SIGNAL_STRENGTH_UNSUPPORTED`` blocker and the engine's fail-closed entry
    gate. ``no_adjustment`` (inert 1x) and ``volatility_adjusted`` (the deterministic
    look-back volatility multiplier) are modelled; ``trend_adjusted`` /
    ``divergence_adjusted`` are blocked at Ready Check AND open no position if a stale
    readiness state slips through to the worker — never a silently un-adjusted run."""
    return config.position_sizing.signal_strength_adjustment in _MODELLED_STRENGTH_MODES


def _mean_relative_range(bars: tuple[_Bar, ...]) -> Decimal:
    """Mean per-bar relative range ``(high - low) / close`` over ``bars``.

    A degenerate non-positive close collapses the whole measure to 0 so the caller
    resolves NEUTRAL (1x) rather than dividing by a nonsense denominator."""
    total = _ZERO
    for b in bars:
        if b.close <= _ZERO:
            return _ZERO
        total += (b.high - b.low) / b.close
    return total / len(bars)


def _volatility_strength(history: tuple[_Bar, ...]) -> Decimal:
    """The ``volatility_adjusted`` strength multiplier at a signal bar (F-07g, §10.3).

    ``history`` is every COMPLETED bar up to and including the signal bar (decisions
    happen at bar close — look-back only, no look-ahead). The multiplier is the ratio of
    the long-window baseline volatility to the short-window recent volatility, clamped to
    [``_STRENGTH_MULT_MIN``, ``_STRENGTH_MULT_MAX``]: recent tape calmer than baseline →
    ratio > 1 (a stronger signal context, larger size); recent tape more turbulent →
    ratio < 1 (weaker, smaller size). Warm-up (history shorter than the long window) and
    a zero/degenerate volatility on either side resolve NEUTRAL (exactly 1x) — the MODE
    stays modelled; neutrality is the deterministic no-evidence default, never a fail."""
    if len(history) < _STRENGTH_LONG_WINDOW:
        return _ONE
    recent = history[-_STRENGTH_LONG_WINDOW:]
    long_vol = _mean_relative_range(recent)
    short_vol = _mean_relative_range(recent[-_STRENGTH_SHORT_WINDOW:])
    if long_vol <= _ZERO or short_vol <= _ZERO:
        return _ONE
    ratio = (long_vol / short_vol).quantize(_STRENGTH_QUANT)
    return min(max(ratio, _STRENGTH_MULT_MIN), _STRENGTH_MULT_MAX)


# Order Validity → the number of decision intervals (future bars) the unfilled order stays
# live. ``current_candle_only`` and ``1_candle`` both give ONE live bar in the bar-replay
# (the signal bar's intrabar is unavailable, so the first fill opportunity is the next bar);
# ``until_cancelled`` rests until fill or end-of-data.
_VALIDITY_BARS: dict[str, int | None] = {
    "current_candle_only": 1,
    "1_candle": 1,
    "2_candles": 2,
    "3_candles": 3,
    "4_candles": 4,
    "until_cancelled": None,
}


# §7 Same-direction scaling modelled by the bar-replay (F-07d, Master Ref §11). The engine
# previously never scaled: a saved scaling config was silently ignored. Now PRICE-DISTANCE
# scaling on the strategy's own timeframe is executed as a deterministic ladder — each
# ``retracement_distance``% adverse close from the reference (initial entry, then the
# previous trigger close) creates ONE layer candidate; candidates pass the layer-count caps
# at CREATION (a capped ladder simply generates no candidate, §11.4 "yeni layer oluşturulmaz")
# and the exposure/size caps at ACCEPTANCE (an over-cap layer is REJECTED with a ledger
# reason, never auto-trimmed — §11.4 exposure binding).
#
# S5c added the SECOND method, ``logic_based_scaling``: its blocks resolve through the same
# plan resolver as entry/exit/stop (``IndicatorPlan.scale_specs``) and propose a layer when
# they aggregate to a signal in the OPEN POSITION'S OWN direction — on the signal's EDGE, so
# a signal that merely stays true does not add a layer every bar, and same-direction only
# (§5.7: an opposite signal is never scaling; the §9 conflict rules resolve it). This is
# also the ONLY ladder the per-layer timeframe sequence gates, per doc 02 §6.1: "Price-
# Distance Based Scaling doğrudan fiyat mesafesiyle tetiklendiğinden bu timeframe dizisini
# kullanmaz" — a price comparison evaluates no indicator, so it has no candle to close on.
#
# NOT modelled (fail closed):
#   * a scaling ``timeframe`` other than ``same_as_base_tf`` — that field picks ONE
#     evaluation timeframe for the whole ladder and honouring it needs resampled bars;
#   * ``timeframe_mode="increasing_by_layer"`` — doc 02 §5.7 names the mode but declares no
#     step increment (next rung vs. doubling are different ladders), so it fails closed
#     rather than being guessed. S5c DID lift ``timeframe_mode="custom_sequence"``: layer N
#     is gated on the closed candle of sequence entry N (``layer_timeframe`` /
#     ``layer_bucket``, the same bucketing the multi-TF indicator path uses), which needs no
#     resampling because the gate only restricts WHICH base bars are decision points;
#   * an UNBOUNDED logic ladder — logic-based scaling has no ``layers`` field of its own, so
#     without ``max_scaling_layers`` or a custom sequence it has no declared depth;
#   * a missing / non-positive ``add_size_value`` (no layer size is derivable);
#   * a negative ``max_scaling_layers`` or a non-positive ``max_total_position_size``
#     (misconfigurations the schema does not reject — spec §11.4 requires int >= 0).
# ``enabled=false`` / an absent subtree is trivially modelled (nothing to scale — the
# disabled-section filter collapses it to None; byte-identical baseline).


# §8 Restrictions / Filters modelled by the bar-replay (F-07e, Master Ref §12). The engine
# previously never evaluated ``restrictions_filters`` — a saved filter set was silently
# ignored. Now the ENTRY-ELIGIBILITY gate runs over the filters the replay can decide
# deterministically from its own bars + realized trade ledger:
#   * ``date_blackout_filter`` — the bar's event date (UTC) inside any configured
#     ``date_ranges`` window (inclusive, "YYYY-MM-DD") → active (§12.3);
#   * ``max_daily_loss_filter`` — the UTC day's realized trade PnL at or beyond
#     ``limit_percent`` of the run's initial capital → active (capital basis + UTC day
#     are engine-version-pinned V1 choices, §12.4);
#   * ``consecutive_loss_filter`` — the realized losing-lot streak at or beyond
#     ``max_losses`` → active (each realized lot counts, incl. partial-close lots —
#     the V1 aggregation policy §12.4 requires be fixed, pinned by the engine version).
# The modelled ACTION is "block entries" only; a filter requesting another action
# (reduce / close / disable / warn) FAILS CLOSED. NOT modelled (fail closed): volatility /
# spread / volume / correlation filters — each needs a data series (ATR dependency, bid/ask
# quotes, a volume-regime definition, a second instrument) OHLCV alone cannot honestly
# supply (§12.2: a fake spread must never be derived from last price alone). ``rule`` combines
# ACTIVE filters: "any" blocks when at least one enabled filter is active, "all" only when
# every enabled filter is active. A disabled filter is not an active engine rule (mirrors
# the disabled-child convention); no enabled filters → trivially modelled.
_MODELLED_FILTER_TYPES = frozenset(
    {"date_blackout_filter", "max_daily_loss_filter", "consecutive_loss_filter"}
)
_MODELLED_FILTER_ACTIONS = frozenset({"block", "block_entries"})


@dataclass(frozen=True, slots=True)
class _RestrictionSpec:
    """One enabled restriction filter parsed to its modelled, typed form (F-07e)."""

    filter_id: str
    filter_type: str
    date_ranges: tuple[tuple[date, date], ...] = ()
    limit_percent: Decimal | None = None
    max_losses: int | None = None


def _parse_iso_date(value: Any) -> date | None:
    """A strict ``YYYY-MM-DD`` calendar date from an untyped config cell, else ``None``."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_restriction(rf: RestrictionFilter) -> _RestrictionSpec | None:
    """Parse ONE filter into its modelled spec; ``None`` = not modelled (fail closed).

    The saved ``config`` is a free-form JSONB dict (the schema enforces no keys), so the
    engine defines the canonical keys it executes: ``date_ranges`` (non-empty list of
    ``{"start", "end"}`` ISO dates, start <= end), ``limit_percent`` (finite > 0),
    ``max_losses`` (int >= 1). Anything missing / malformed — and any explicit ``action``
    other than block-entries — is unmodellable and fails closed rather than guessed."""
    if rf.filter_type not in _MODELLED_FILTER_TYPES:
        return None
    cfg = rf.config or {}
    action = cfg.get("action")
    if action is not None and action not in _MODELLED_FILTER_ACTIONS:
        return None
    if rf.filter_type == "date_blackout_filter":
        raw_ranges = cfg.get("date_ranges")
        if not isinstance(raw_ranges, list) or not raw_ranges:
            return None
        ranges: list[tuple[date, date]] = []
        for item in raw_ranges:
            if not isinstance(item, dict):
                return None
            start = _parse_iso_date(item.get("start"))
            end = _parse_iso_date(item.get("end"))
            if start is None or end is None or start > end:
                return None
            ranges.append((start, end))
        return _RestrictionSpec(rf.filter_id, rf.filter_type, date_ranges=tuple(ranges))
    if rf.filter_type == "max_daily_loss_filter":
        limit = _safe_decimal(cfg.get("limit_percent"))
        if limit is None or limit <= _ZERO:
            return None
        return _RestrictionSpec(rf.filter_id, rf.filter_type, limit_percent=limit)
    max_losses = cfg.get("max_losses")
    if isinstance(max_losses, bool) or not isinstance(max_losses, int) or max_losses < 1:
        return None
    return _RestrictionSpec(rf.filter_id, rf.filter_type, max_losses=max_losses)


def restrictions_are_modelled(config: StrategyConfig) -> bool:
    """Public predicate: is this strategy's Restrictions/Filters section modelled (F-07e)?

    The single shared source of truth for the readiness ``STRATEGY_RESTRICTIONS_UNSUPPORTED``
    blocker and the engine's fail-closed entry gate. No enabled filters is trivially
    modelled; every enabled filter must be a modelled type (date-blackout / max-daily-loss /
    consecutive-loss) with a parseable canonical config and a block-entries action —
    anything else is blocked at Ready Check AND opens no position if a stale readiness
    state slips through to the worker (never a silently unfiltered run)."""
    return all(
        _parse_restriction(rf) is not None
        for rf in config.restrictions_filters.filters
        if rf.enabled
    )


def conflict_handling_is_modelled(config: StrategyConfig) -> bool:
    """Public predicate: is this strategy's conflict/position handling modelled (F-07e)?

    The single shared source of truth for the readiness
    ``STRATEGY_CONFLICT_HANDLING_UNSUPPORTED`` blocker and the engine's fail-closed entry
    gate. The single-position bar-replay models every ``same_direction_stacking`` policy
    (stack = fold-in add, replace, scale-delegate, ignore) and the opposite-direction
    policies that resolve to ONE open position (exit-on-opposite close, ``close_existing``,
    ``ignore``). A true HEDGE — ``opposite_direction_hedge="allow_hedge"`` with
    ``exit_on_opposite_signal`` off — needs two concurrent opposite positions the engine
    cannot honestly simulate, so it fails closed (with exit-on-opposite ON the opposite
    signal closes the position first, so the hedge branch is never reached and every hedge
    value is modelled). ``overlapping_signal_policy`` is vacuously modelled in V1: the
    engine derives at most ONE aggregated signal per evaluation window (the signal-block
    rule + the deterministic long-wins tie-break resolve same-window concurrency before
    the policy could bite), so all its values share the executed behaviour."""
    conflict = config.conflict_position_handling
    if conflict.exit_on_opposite_signal:
        return True
    return conflict.opposite_direction_hedge != "allow_hedge"


def _safe_decimal(value: Any) -> Decimal | None:
    """Best-effort finite ``Decimal`` from an untyped JSON snapshot cell, else ``None``.

    The allocation snapshot is a validated plan config, but it reaches the engine as
    an untyped ``dict[str, Any]``; ``str()`` first so a non-numeric value fails closed
    rather than surprising ``Decimal`` coercion, and a ``NaN`` / ``Infinity`` is
    rejected (it would raise on the ordered comparisons that consume it)."""
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return parsed if parsed.is_finite() else None


def _active_item_share(entries: Any, item_id: str) -> Decimal:
    """The replayed item's active ``equity_share_percent`` (0 if absent/inactive/invalid).

    Validation forbids a duplicate active entry, so the first active match for
    ``item_id`` is authoritative; a non-positive or unparseable share yields 0 (an
    unallocated item → no sleeve → no fills)."""
    if not isinstance(entries, list):
        return _ZERO
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("composition_item_id")) != item_id or not entry.get("active"):
            continue
        share = _safe_decimal(entry.get("equity_share_percent"))
        if share is not None and share > _ZERO:
            return share
    return _ZERO


def resolve_allocation_execution(
    capital_execution: dict[str, Any] | None, *, item_id: str
) -> AllocationExecution | None:
    """Project the manifest ``capital_execution`` snapshot into the replayed item's
    resolved capital model (doc 13 §8.3), or ``None`` for independent / absent
    allocation (the engine then behaves byte-identically to the pre-allocation build).

    Pure and defensive. The snapshot is a validated plan config, but it is read here
    as an untyped JSON dict, so a missing / non-finite / non-positive pool ``P0`` fails
    closed to ``None`` — there is genuinely nothing to allocate without a pool, and a
    non-positive ``P0`` is itself a validation blocker that cannot pin a real revision.
    A negative reserve is floored at 0 (it could otherwise inflate the allocatable
    pool above P0); an over-100 reserve needs no upper clamp — the engine's
    ``max(0, P0 - R0)`` drives the allocatable pool to 0. The replayed item's share is
    0 when it has no active entry, so an enabled allocation is NEVER silently downgraded
    to the strategy's own independent capital."""
    if not isinstance(capital_execution, dict) or not capital_execution.get("enabled"):
        return None
    config = capital_execution.get("config")
    if not isinstance(config, dict):
        return None
    pool = config.get("initial_capital")
    if not isinstance(pool, dict):
        return None
    p0 = _safe_decimal(pool.get("amount"))
    if p0 is None or p0 <= _ZERO:
        return None
    reserve = max(_safe_decimal(config.get("reserve_cash_percent")) or _ZERO, _ZERO)
    currency = pool.get("currency")
    return AllocationExecution(
        initial_capital=p0,
        reserve_percent=reserve,
        compound=config.get("compounding_mode") == CompoundingMode.COMPOUND_PORTFOLIO_EQUITY.value,
        item_share_percent=_active_item_share(config.get("entries"), item_id),
        currency=str(currency) if currency is not None else None,
    )


def resolve_portfolio_rules(capital_execution: dict[str, Any] | None) -> PortfolioRules | None:
    """Project the manifest ``capital_execution`` snapshot's PORTFOLIO-LEVEL rules
    (cross-item Max Total Exposure + conflict policy, doc 13 §8.4), or ``None``
    when no rule is set — the engine then replays byte-identically to the
    pre-rules build.

    Pure and defensive (the ``resolve_allocation_execution`` twin). Rules live on
    the shared allocation plan, so a disabled/absent allocation carries none. A
    SET-but-unreadable or non-positive exposure percent does NOT fall back to
    "no cap" (that would silently under-enforce a cap the user configured) — it
    is flagged ``exposure_percent_invalid`` and the engine fails closed to a ZERO
    cap + L4 warning. An explicit KEEP_SEPARATE with no cap is the pre-rules
    behaviour and resolves to ``None``."""
    if not isinstance(capital_execution, dict) or not capital_execution.get("enabled"):
        return None
    config = capital_execution.get("config")
    if not isinstance(config, dict):
        return None
    raw_pct = config.get("max_total_exposure_percent")
    pct: Decimal | None = None
    pct_invalid = False
    if raw_pct is not None:
        pct = _safe_decimal(raw_pct)
        if pct is None or pct <= _ZERO:
            pct = None
            pct_invalid = True
    raw_policy = config.get("conflict_policy")
    policy = None
    if raw_policy is not None and str(raw_policy).strip():
        policy = str(raw_policy).strip().upper()
    if pct is None and not pct_invalid and policy in (None, "KEEP_SEPARATE"):
        return None
    return PortfolioRules(
        max_total_exposure_percent=pct,
        conflict_policy=policy,
        own_symbol=None,
        prior_intervals=(),
        exposure_percent_invalid=pct_invalid,
    )


def _epoch_ms_or_none(value: Any) -> int | None:
    """UTC epoch ms for an ISO-8601 timestamp, else ``None`` (= unplaceable).

    ``source_zone=None`` (K-01): replayed data is UTC-normalized at ingest and carries
    an offset, so there is no source zone to apply here. A naive value is therefore an
    honest ``None`` (unplaceable, handled fail-closed) rather than a guessed UTC."""
    if not isinstance(value, str) or not value:
        return None
    parsed = parse_utc(value, source_zone=None)
    return int(parsed.timestamp() * 1000) if parsed is not None else None


def build_prior_intervals(
    *,
    item_id: str,
    symbol: str | None,
    position_intervals: list[dict[str, Any]],
) -> tuple[PriorItemInterval, ...]:
    """Convert one COMPLETED item run's closed-position windows
    (``EngineOutput.position_intervals``) into the constraint intervals a
    later-pinned item replays against.

    An unparseable bound becomes ``None`` = unbounded on that side (fail closed:
    over-covers, never under-covers). A window whose peak notional cannot be read
    as a positive figure constrains nothing and is dropped — it cannot block a
    conflict either, but a fabricated notional would corrupt the cap arithmetic
    (the honest trade-off, and unreachable from engine-produced windows)."""
    out: list[PriorItemInterval] = []
    for iv in position_intervals:
        notional = _safe_decimal(iv.get("peak_notional"))
        if notional is None or notional <= _ZERO:
            continue
        out.append(
            PriorItemInterval(
                item_id=item_id,
                symbol=symbol,
                direction=str(iv.get("direction")),
                start_ms=_epoch_ms_or_none(iv.get("entry_time")),
                end_ms=_epoch_ms_or_none(iv.get("exit_time")),
                notional=notional,
            )
        )
    return tuple(out)


# F-07i (B): the intrabar tick path. The worker injects the PINNED tick/trade
# revision's processed print stream only when the strategy demands tick data
# (``tick_data_required``); the engine aligns it to per-bar windows and uses the true
# print order to resolve what OHLCV alone cannot — for this slice, the
# ``first_trigger_wins`` stop-conflict order that was previously approximated
# conservative (``approximated_first``). Without ticks every path stays byte-identical.


def _exit_proxy(position: _Position, bar: _Bar, window: deque[_Bar]) -> bool:
    """Opposite-breakout exit: a long exits on a new window low, a short on a new high."""
    if len(window) < _BREAKOUT_WINDOW:
        return False
    if position.direction == "long":
        return bar.close < min(b.low for b in window)
    return bar.close > max(b.high for b in window)


@dataclass(frozen=True, slots=True)
class _LedgerEffect:
    """One ledger counter bump and, optionally, the trace event that explains it.

    A describe half COMPUTES these and applies none of them; the matching booking half
    replays them in order. Carrying them instead of applying them inline is what makes an
    evaluation genuinely read-only — the pre-split code bumped three counters and emitted
    ``filtered_no_entry`` while it was still only deciding, so "evaluate" and "write to the
    ledger" could not be told apart (ADR-0002 §15 R-4)."""

    counter: str
    event: str = ""
    direction: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _CarryPlan:
    """P1 described: which funding records fire at this bar and what each costs.

    ``next_index`` is the advanced cursor — it advances even when ``charges`` is empty,
    because a record that becomes available while FLAT is consumed without a charge (the
    perp convention ``due_funding_charges`` implements)."""

    next_index: int
    charges: tuple[FundingCharge, ...]


@dataclass(frozen=True, slots=True)
class _HeldDecision:
    """P3 described: which protection/exit arm this bar takes against a held position.

    ``branch`` names the arm of the former ``if``/``elif`` chain verbatim, so the booking
    half reproduces the chain's exclusivity without re-deciding anything. ``"none"`` means
    a position is held and no arm fired — distinct from ``_evaluate_held`` returning
    ``None``, which means there is no position at all."""

    branch: str
    stop_outcome: _StopOutcome | None = None
    executed_reason: str = ""
    touch_level: Decimal | None = None
    touched: bool = False


@dataclass(frozen=True, slots=True)
class _EntryDecision:
    """P4 described: the entry this bar wants, formed but not placed.

    ``want`` is ``None`` when the signal was suppressed — the suppression's counter and
    trace event travel in ``effects`` rather than having been written already. ``strength``
    is the signal bar's multiplier (F-07g), computed once here and inherited verbatim by
    whichever fill path the booking half executes."""

    want: str | None
    strength: Decimal
    effects: tuple[_LedgerEffect, ...] = ()
    entry_detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _ItemStepper:
    """One item's replay, suspended between bars instead of run to completion.

    ``run_engine`` drives it over its own bar stream; a caller that owns a MERGED clock
    (ADR-0002 §8) drives the same object bar by bar to advance this item to a given ``t``.
    The record is deliberately thin — the replay state stays in the factory's closure,
    exactly where the bar loop already kept it, so lifting the loop out moved no state
    between scopes and could not move a number."""

    step: Callable[[_Bar], None]
    """Advance the replay by ONE normalized bar (the caller normalizes: ``_normalize``)."""
    finalize: Callable[[], None]
    """End-of-data: cancel a resting order, close an open position. Call once, after the
    last ``step``."""
    output: Callable[[], EngineOutput]
    """Project (ctx, led) into the run's ``EngineOutput``. Replays nothing."""
    open_position: Callable[[], _Position | None]
    """The position currently held, or ``None`` — what a portfolio participant must read
    to decide carry / mandatory exit without reaching into the replay's internals."""
    admit: Callable[[_Bar], None]
    """Phase (1): admit the bar and derive its decision inputs. Books nothing."""
    carry: Callable[[_Bar], None]
    """Phase (2) / ADR-0002 P1: funding and carry on a held position."""
    compute_carry: Callable[[_Bar], _CarryPlan | None]
    """P1 DESCRIBED: what carry is due, booked nowhere. ``None`` when the item has no
    funding schedule at all. Read-only — safe to call before the pool has arbitrated."""
    book_carry: Callable[[_Bar, _CarryPlan], None]
    """P1 BOOKED: apply a plan ``compute_carry`` produced. Advances the funding cursor."""
    open_fills: Callable[[_Bar], None]
    """Phases (3)/(3b)/(3c): fills deferred to this bar's open, resting orders."""
    held: Callable[[_Bar], bool]
    """Phase (4) / P3: protection, stop and exit. Returns whether a position was held, which
    is what keeps the former ``if``/``elif`` exclusive once the two arms are called apart."""
    evaluate_held: Callable[[_Bar], _HeldDecision | None]
    """P3 DESCRIBED: which exit this bar forces, closed nowhere. ``None`` means flat.

    Advances the position's trail anchor, and ONLY that: the anchor is a high-water mark of
    the market, not a booking — it moves because the bar printed that extreme, whatever the
    pool later admits, and ``max``/``min`` makes re-describing the same bar idempotent. The
    stop level ``_resolve_stop`` reads is derived from it, so it must be current here."""
    apply_held: Callable[[_Bar, _HeldDecision], None]
    """P3 BOOKED: execute the arm ``evaluate_held`` chose. Closes, emits, clears state."""
    entry: Callable[..., None]
    """Phase (5) / P4: a fresh entry while flat, sized against ``equity`` when one is given —
    the SHARED ``E(t)`` for a portfolio participant, this item's own ledger otherwise."""
    evaluate_entry: Callable[[_Bar], _EntryDecision | None]
    """P4 DESCRIBED: the entry this bar wants, placed nowhere and sized nowhere.

    ``None`` means the item is not open for a fresh entry (holding, committed, or a
    fail-closed backstop is down). Genuinely read-only: it writes no ledger field, emits no
    event and touches no lifecycle state, so a pool may call it, refuse what it hears and
    leave the item exactly as it was (ADR-0002 §6)."""
    apply_entry: Callable[..., None]
    """P4 BOOKED: place what ``evaluate_entry`` described — resting order, deferred fill or
    an immediate open sized against ``equity`` when one is given."""
    tail: Callable[[_Bar], None]
    """Phases (3d)/(6)/(7)/(8): close-deferred fill, stacking rules, scale ladder, snapshot."""
    ledger: _Ledger
    ctx: _RunConfig


def _build_stepper(
    *,
    strategy_config: StrategyConfig,
    execution_key: str,
    item_count: int = 1,
    indicator_plan: IndicatorPlan | None = None,
    timeframe: str | None = None,
    allocation: AllocationExecution | None = None,
    funding: FundingSchedule | None = None,
    tick_batches: Iterator[list[dict[str, Any]]] | None = None,
    portfolio_rules: PortfolioRules | None = None,
    builtin_breakout_fixture: bool = False,
) -> _ItemStepper:
    """Resolve one run's pinned settings and hand back its suspendable replay.

    This is ``run_engine``'s body up to the bar loop, unchanged: the same fail-closed
    ``UnresolvedStrategyError``, the same ledger seed, the same ``_RunConfig`` snapshot and
    the same decision closures. It exists so the bar loop can be entered one bar at a time
    (ADR-0002 §12 ADIM 16) — nothing here decides anything a bar does."""
    config = strategy_config
    alloc_on = allocation is not None
    alloc_compound = False
    reserve_nominal = _ZERO
    allocatable_initial = _ZERO
    item_share = _ZERO
    if allocation is not None:
        # Shared allocation: the run is capitalised from the PORTFOLIO POOL P0 (not the
        # strategy's own initial_capital); R0 is held back nominally, A0 = P0 - R0 is the
        # allocatable pool, and Ci0 = A0 * wi / 100 is this item's initial sleeve (§8.3).
        portfolio_pool = allocation.initial_capital.quantize(_MONEY)
        reserve_nominal = portfolio_pool * allocation.reserve_percent / _HUNDRED
        allocatable_initial = max(_ZERO, portfolio_pool - reserve_nominal)
        item_share = allocation.item_share_percent
        alloc_compound = allocation.compound
        initial_capital = portfolio_pool
    else:
        initial_capital = Decimal(config.data.initial_capital).quantize(_MONEY)
    # The account book opens at the run's initial capital, and the equity curve opens
    # with the corresponding zero-drawdown point; every other tally starts empty/0.
    led = _Ledger(
        equity=initial_capital,
        peak=initial_capital,
        equity_points=[
            EquityPoint(0, "", initial_capital, _ZERO.quantize(_MONEY), _ZERO.quantize(_PCT))
        ],
    )

    # Portfolio-level rules (cross-item, doc 13 §8.4). The cap basis is the pinned
    # capital this run replays from: the shared pool P0 under allocation (the normal
    # rules path — rules live on the allocation plan), else the strategy's own
    # initial capital (defensive; unreachable through the real manifest flow).
    rules_active = portfolio_rules is not None
    portfolio_cap_amount: Decimal | None = None
    conflict_gate_on = False
    conflict_downgraded_from_net = False
    conflict_policy_unknown = False
    if portfolio_rules is not None:
        policy_token = (portfolio_rules.conflict_policy or "").strip().upper()
        if policy_token and policy_token != "KEEP_SEPARATE":
            # NET downgrades to the conservative block (L4-disclosed); an UNKNOWN
            # token (a tampered/foreign snapshot) also fails closed to block —
            # never silently ignored.
            conflict_gate_on = True
            conflict_downgraded_from_net = policy_token == "NET"
            conflict_policy_unknown = policy_token not in ("NET", "BLOCK_OPPOSITE")
        if portfolio_rules.exposure_percent_invalid:
            # A SET-but-unreadable/non-positive cap admits NOTHING (fail closed +
            # L4 warning) rather than silently running uncapped.
            portfolio_cap_amount = _ZERO.quantize(_MONEY)
        elif portfolio_rules.max_total_exposure_percent is not None:
            portfolio_cap_amount = (
                initial_capital * portfolio_rules.max_total_exposure_percent / _HUNDRED
            ).quantize(_MONEY)
    long_ok, short_ok = _direction_flags(config.position_entry_logic.direction_mode)
    half_spread, slippage, commission = _cost_params(config)
    fill_costs = FillCosts(half_spread, slippage, commission)
    trail_pct = _trail_pct(config)
    # F-07f: trailing stop profit-lock activation threshold (Master Ref §9.2 "Activate
    # After Profit %") — mirrors ``trail_pct``, threaded into every opened position.
    trail_lock_in_pct = _trail_lock_in_pct(config)
    trailing_lock_in_active = trail_lock_in_pct is not None
    # §5.9 Stop+Exit same-bar collision policy (read straight from the pinned config so it
    # applies in BOTH plan and breakout-proxy modes; default "stop_has_priority" = V18).
    stop_exit_conflict = str(config.conflict_position_handling.stop_exit_conflict)
    # S5b residual: the flat-position Entry+Exit collision is a separate policy from
    # Stop+Exit. Both indicator decisions are close-confirmed, so the default never
    # fabricates an intrabar ordering; only explicit ``exit_first`` admits the entry
    # after treating the flat-position exit as a no-op.
    same_candle_entry_exit = str(config.conflict_position_handling.same_candle_entry_exit)
    # F-08 stop-combination modes (read once; drive _resolve_stop + the ledger record).
    _protection = config.protection_stop_logic
    stop_trigger_requirement = (
        _protection.stop_trigger_requirement if _protection is not None else "any_active"
    )
    stop_conflict_resolution = (
        _protection.stop_conflict_resolution if _protection is not None else "most_conservative"
    )

    # F-07i (B): the optional intrabar tick path. Aligning prints to bars needs the base
    # bar span; an un-timeframed revision leaves the cursor unset and the run on the
    # conservative OHLCV model (surfaced as a warning, L4 — never guessed).
    tick_cursor: _TickCursor | None = None
    tick_alignment_unavailable = False
    if tick_batches is not None:
        tick_span = timeframe_seconds(timeframe) if timeframe is not None else None
        if tick_span is None:
            tick_alignment_unavailable = True
        else:
            tick_cursor = _TickCursor(tick_batches, tick_span)

    # F-09: an unmodelled / misconfigured sizing method opens NO position at all — the
    # engine is a fail-closed backstop to the Ready Check STRATEGY_SIZING_UNSUPPORTED
    # blocker, so a stale/bypassed readiness state reaching the worker still produces a
    # financially inert run (no phantom 0-size or all-in led.trades).
    sizing_ok = _sizing_is_honored(config)

    # F-07f: an unmodelled leverage configuration (cross-margin, or a non-positive saved
    # multiplier) opens NO position — the fail-closed backstop to the Ready Check
    # STRATEGY_LEVERAGE_UNSUPPORTED blocker, never a silently un-leveraged or
    # mis-leveraged run.
    leverage_ok = leverage_is_modelled(config)

    # F-07g: signal-strength adjustment (§10.3). ``no_adjustment`` is inert (1x —
    # byte-identical baseline); ``volatility_adjusted`` scales every SIGNAL-driven entry
    # size by the deterministic look-back volatility multiplier computed at the signal
    # bar; ``trend_adjusted`` / ``divergence_adjusted`` open NO position — the fail-closed
    # backstop to the Ready Check STRATEGY_SIGNAL_STRENGTH_UNSUPPORTED blocker, never a
    # silently un-adjusted run.
    strength_mode = config.position_sizing.signal_strength_adjustment
    strength_ok = signal_strength_is_modelled(config)
    strength_active = strength_ok and strength_mode == "volatility_adjusted"

    # F-07a: entry/exit execution timing. Immediate modes fill at the signal bar's
    # close; the next-candle modes defer the fill to the following bar (removing the
    # hardcoded current-candle-close assumption). An UNSUPPORTED timing (intrabar_touch /
    # a limit or stop-limit simulation) opens NO position — the fail-closed backstop to
    # the Ready Check STRATEGY_EXECUTION_TIMING_UNSUPPORTED blocker, never silently
    # downgraded to a close fill it did not request.
    timing_ok = execution_timing_is_modelled(config)
    entry_sched = _fill_schedule(config.data.execution.entry_timing)
    exit_sched = _fill_schedule(config.data.execution.exit_timing)

    # F-07b/F-07h: order-type execution. ``market_order`` / ``simulation_only`` fill at the
    # timing-chosen price (byte-identical to the pre-F-07b market path); ``limit_order``
    # rests a working order that fills only on a limit touch within the validity window;
    # ``stop_order`` / ``stop_limit_order`` rest a stop trigger — a plain stop fills
    # market-like on trigger, a stop-limit arms the limit machine from the NEXT bar. An
    # unmodelled variant (missing/invalid trigger, best_bid_ask, partial fill) opens NO
    # position — the fail-closed backstop to the Ready Check
    # STRATEGY_ORDER_TYPE_UNSUPPORTED blocker.
    order_cfg = config.data.order_config
    order_ok = order_execution_is_modelled(config)
    order_is_limit = order_cfg.type == "limit_order" and order_ok
    order_is_stop = order_cfg.type in ("stop_order", "stop_limit_order") and order_ok

    # F-07i (C): the tick-dependent execution settings. They pass the predicates only
    # when the strategy DEMANDS tick data ('Use Tick Data' = Yes), so the worker streams
    # the pinned print path whenever these are active. ``tick_entry_authority``: under a
    # tick-backed ENTRY timing, a bar WITH prints makes the print path authoritative for
    # a resting order's touch (a print-less bar keeps the coarse bar-touch — data
    # sparsity is never proof of no fill). ``stop_limit_sim``: the same-bar
    # stop-then-limit sequence resolves over the observed prints in (1c).
    # ``partial_active``: the configured limit's partial-fill policy is executed from
    # print SIZE evidence (fraction never fabricated — size-less evidence degrades to
    # the coarse full-fill model, flagged L4).
    tick_entry_authority = config.data.execution.entry_timing in _TICK_ENTRY_TIMINGS
    stop_limit_sim = config.data.execution.exit_timing == "stop_limit_priority_simulation"
    partial_policy = "not_allowed"
    if order_cfg.limit is not None and order_cfg.type in _LIMIT_BACKED_ORDER_TYPES:
        partial_policy = order_cfg.limit.partial_fill_policy
    partial_active = partial_policy != "not_allowed" and order_ok
    exit_touch: tuple[Decimal, int] | None = None  # (touch level, placed bar_seq)

    # F-07c: partial close. An EXIT SIGNAL closes ``close_fraction`` of the position and holds
    # the remainder (aftermath governs it); a stop / end-of-data always closes fully (a risk
    # event is never partial). ``close_all`` collapses to a full close. An unmodelled aftermath
    # (trailing / lock-in, slice (f)) opens NO position — the fail-closed backstop to the Ready
    # Check STRATEGY_PARTIAL_CLOSE_UNSUPPORTED blocker.
    exit_logic = config.position_exit_logic
    partial_aftermath = exit_logic.partial_aftermath
    partial_close_ok = partial_close_is_modelled(config)
    close_fraction = (exit_logic.close_percentage / _HUNDRED) if partial_close_ok else _ONE
    if partial_aftermath == "close_all":
        close_fraction = _ONE  # the exit signal closes 100% regardless of close_percentage

    # F-07d: same-direction scaling. A modelled price-distance config runs the layer ladder
    # against the open position; an unsupported config (logic-based / TF override / missing
    # add size / misconfigured cap) opens NO position — the fail-closed backstop to the Ready
    # Check STRATEGY_SCALING_UNSUPPORTED blocker, never a silently un-scaled run.
    scaling_cfg = config.scaling_logic
    scaling_enabled = scaling_cfg is not None and scaling_cfg.enabled
    scaling_ok = scaling_is_modelled(config)
    scaling_active = scaling_enabled and scaling_ok
    scale_distance = _ZERO
    scale_max_layers = 0
    scale_add_basis = ""
    scale_add_value = _ZERO
    scale_max_total: Decimal | None = None
    # S5c: which ladder is running. The logic ladder reads a resolved indicator signal and
    # is the ONLY consumer of the per-layer timeframe sequence (doc 02 §6.1); the
    # price-distance ladder compares price and ignores it.
    scale_logic_mode = (
        scaling_active and scaling_cfg is not None and (scaling_cfg.method == "logic_based_scaling")
    )
    if (
        scaling_active
        and scaling_cfg is not None
        and (scaling_cfg.price_scaling is not None or scale_logic_mode)
    ):
        scale_limits = scaling_cfg.scaling_limits
        if scaling_cfg.price_scaling is not None:
            price_scaling = scaling_cfg.price_scaling
            scale_distance = price_scaling.retracement_distance
            # The method's planned ladder depth, further capped by the optional global limit
            # (§11.4 Max Additional Layers, int >= 0 — 0 legally disables the ladder).
            scale_max_layers = price_scaling.layers
        else:
            # The logic ladder has no ``layers`` field of its own (§5.7 gives depth to the
            # price method only), so its depth comes from the global cap — or, under
            # custom_sequence, from the sequence length below. With neither, an unbounded
            # logic ladder is refused by ``scaling_is_modelled`` rather than run.
            scale_max_layers = (
                scale_limits.max_scaling_layers
                if scale_limits is not None and scale_limits.max_scaling_layers is not None
                else 0
            )
        if scale_limits is not None and scale_limits.max_scaling_layers is not None:
            scale_max_layers = min(scale_max_layers, scale_limits.max_scaling_layers)
        # S5c: under custom_sequence the SEQUENCE LENGTH is itself a layer bound. Doc 02
        # §5.7 gives the ladder one timeframe per layer and says nothing about running past
        # the last entry, so the run stops there rather than inventing a repeat-the-last or
        # fall-back-to-base rule. This also makes ``layer_timeframe``'s past-the-end branch
        # unreachable, i.e. no layer can ever slip through ungated.
        tf_sequence = scaling_cfg.custom_timeframe_sequence
        if scaling_cfg.timeframe_mode == "custom_sequence" and tf_sequence:
            scale_max_layers = (
                min(scale_max_layers, len(tf_sequence)) if scale_max_layers else len(tf_sequence)
            )
        scale_max_total = scale_limits.max_total_position_size if scale_limits is not None else None
        scale_add_basis = scaling_cfg.add_size
        scale_add_value = scaling_cfg.add_size_value or _ZERO

    # F-07e: Restrictions / Filters. The modelled filters (date-blackout / max-daily-loss /
    # consecutive-loss, block-entries action) gate every ENTRY decision — flat entries AND
    # conflict-driven entries (stack / replace); an unmodelled filter type or config opens
    # NO position — the fail-closed backstop to the Ready Check
    # STRATEGY_RESTRICTIONS_UNSUPPORTED blocker, never a silently unfiltered run.
    restrictions_cfg = config.restrictions_filters
    restriction_rule = restrictions_cfg.rule
    # I-15a: N for the Minimum-N-of-M combination. The compiler already rejects an N
    # above the enabled filter count, so the engine only needs the floor of 1 for a
    # config that reached the worker without one (never a gate that blocks on zero
    # active filters — that would veto every entry).
    restriction_min_true = max(1, restrictions_cfg.min_true_count or 1)
    restrictions_ok = restrictions_are_modelled(config)
    # K-11b: the filter types the replay cannot decide, resolved HERE from the same parse
    # that decides ``restrictions_ok`` rather than re-parsed later by the output assembly.
    # Keeping the parse in one place is the point: a warning that named a different set
    # than the gate that opened no position would be a lie about why the run was inert.
    unmodelled_restriction_types = tuple(
        sorted(
            {
                rf.filter_type
                for rf in restrictions_cfg.filters
                if rf.enabled and _parse_restriction(rf) is None
            }
        )
    )
    restriction_specs: list[_RestrictionSpec] = (
        [
            spec
            for spec in (_parse_restriction(rf) for rf in restrictions_cfg.filters if rf.enabled)
            if spec is not None
        ]
        if restrictions_ok
        else []
    )

    # F-07e: conflict / position handling. A NEW aggregated signal EDGE while a position is
    # open resolves per policy: same direction → stack / replace / scale-delegate / ignore;
    # opposite direction (when exit-on-opposite is off) → close_existing / ignore. A true
    # hedge (allow_hedge with exit-on-opposite off) opens NO position — the fail-closed
    # backstop to the Ready Check STRATEGY_CONFLICT_HANDLING_UNSUPPORTED blocker.
    conflict_cfg = config.conflict_position_handling
    stacking_policy = str(conflict_cfg.same_direction_stacking)
    hedge_policy = str(conflict_cfg.opposite_direction_hedge)
    overlap_policy = str(conflict_cfg.overlapping_signal_policy)
    conflict_ok = conflict_handling_is_modelled(config)

    # F-05: the MATRIX-driven capability gate (see domain/backtest/capabilities.py). The nine
    # predicates above each answer a whole-CONFIG question for one domain; this one enumerates
    # per option VALUE, which is what closes the class of hole they structurally cannot see —
    # an option nothing was gating at all. The concrete case that motivated it:
    # ``data.costs.slippage_mode = 'historical_slippage_if_available'`` passed all nine
    # predicates, so Ready Check admitted the run and ``_cost_params`` (which never branches on
    # the MODE) silently resolved slippage to ZERO — the schema makes ``slippage_value``
    # optional under that mode — handing back an over-optimistic fill model the user never
    # asked for. Any ``future_dev`` selection now opens NO position, exactly like the other
    # nine, and Ready Check raises STRATEGY_CAPABILITY_NOT_IN_BUILD ahead of it.
    capability_ok = capabilities_are_modelled(config)

    future_dev_selected = future_dev_selections(config)

    plan_active = indicator_plan is not None and indicator_plan.has_entry
    if not plan_active and not builtin_breakout_fixture:
        # F-04 fail closed: no resolved trigger plan and no explicit test-only fixture
        # opt-in → refuse before any state is built, so an unresolved/empty plan can never
        # materialize a Result. The engine never invents entries the user did not define;
        # the labelled breakout is reachable ONLY via builtin_breakout_fixture=True (tests).
        raise UnresolvedStrategyError(
            "run_engine requires a resolved indicator_plan with at least one computable "
            "entry block; it refuses to fabricate a result from the deterministic breakout "
            "fixture unless builtin_breakout_fixture=True is explicitly passed (test-only)."
        )
    entry_evals: list[BlockEvaluator] = (
        build_evaluators(indicator_plan.entry_specs) if plan_active and indicator_plan else []
    )
    exit_evals: list[BlockEvaluator] = (
        build_evaluators(indicator_plan.exit_specs) if plan_active and indicator_plan else []
    )
    # F-08 Logic-Based Stop evaluators are INDEPENDENT of the entry plan (a strategy may
    # protect with a logic stop regardless of its entry model). Each stop spec's UUID keys
    # its rule for the combination engine + ledger. Empty when no logic stops are pinned,
    # so the pure price-stop path is byte-identical to pre-F-08.
    stop_specs = indicator_plan.stop_specs if indicator_plan is not None else ()
    stop_evals: list[BlockEvaluator] = build_evaluators(stop_specs)
    stop_pairs = list(zip(stop_specs, stop_evals, strict=True))
    logic_enabled = [f"logic:{spec.block_id}" for spec in stop_specs]

    # S5c Logic-Based SCALING evaluators — INDEPENDENT of the entry plan for the same reason
    # the stop evaluators are: a strategy may scale on a different indicator than it enters
    # on. Empty when no logic-based scaling is pinned, so the price-distance ladder is
    # byte-identical to pre-S5c.
    scale_specs = indicator_plan.scale_specs if indicator_plan is not None else ()
    scale_evals: list[BlockEvaluator] = build_evaluators(scale_specs)
    scale_signal: str | None = None
    prev_scale_signal: str | None = None

    window: deque[_Bar] = deque(maxlen=_BREAKOUT_WINDOW)
    position: _Position | None = None
    pending: _Pending | None = None  # a fill deferred to a future bar (F-07a timing)
    working_limit: _WorkingLimit | None = None  # a resting limit ENTRY order (F-07b)
    working_stop: _WorkingStop | None = None  # a resting stop ENTRY trigger (F-07h)
    # Per-BAR working state (ADIM 16b). These were locals of the former single-body step;
    # they live here so each phase the stepper exposes can be called on its own. Every one
    # is re-initialised at the top of ``_phase_admit``, so none of them carries across bars.
    bar_ticks: tuple[_Tick, ...] = ()
    trades_before_bar = 0
    bar_date: date | None = None
    entry_signal: str | None = None
    exit_hit = False
    # The valuation an entry is sized against. ``None`` means "this item's own ledger",
    # which is the only answer a standalone run has. A portfolio participant sets it to the
    # SHARED E(t) for the duration of P4 and clears it again (ADR-0002 §7).
    sizing_equity: Decimal | None = None
    # F-07h: stop-trigger lifecycle counts (a stop-limit's armed limit leg then counts
    # through the limit_orders_* counters — the two machines compose, never double-count).
    # F-07i (C): tick-setting execution counts — print-resolved entry fills (a resting
    # order whose touch the print path proved), partial fills (initial + remainder lots),
    # same-bar stop-then-limit fills, touch-order placements and touch-exit fills.
    # F-07f: count of partial-close aftermaths that locked in profit on the remainder
    # (``lock_in_profit`` moving the stop to the current price, or ``trailing_stop``
    # force-activating the trailing rule) — surfaced as a diagnostics count.
    # F-07g: count of signal-driven entry decisions whose computed strength multiplier
    # was NOT the neutral 1x (flat entries, deferred/limit entries at their signal bar,
    # and conflict-driven stack/replace entries) — surfaced as a diagnostics count.
    # F-07e: restriction-gate + conflict-policy counters and their realized-ledger state.
    # ``current_day`` / ``led.day_realized`` track the UTC calendar day's realized trade PnL
    # (max-daily-loss basis); ``led.loss_streak`` counts consecutive realized losing lots
    # (consecutive-loss basis); ``prev_entry_signal`` detects a NEW aggregated signal EDGE
    # (a held signal is one entry event, never a per-bar stack/replace/ignore storm).
    current_day: date | None = None
    prev_entry_signal: str | None = None
    # Portfolio-rules gate counters + the per-block reason handoff to _blocked_reason,
    # and every fully-closed position's held window (the later items' constraint input).
    # F-11: funding cost state. ``funding_records`` is the ascending, available-time-safe
    # series (empty when funding is off → the whole funding path is inert, byte-identical to
    # pre-F-11). ``funding_idx`` is the as-of cursor (a record fires at most once, in order);
    # ``funding_paid`` is the cumulative signed cost booked against equity.
    funding_records = funding.records if funding is not None else ()

    # Every resolved setting the run READS, pinned once as one frozen value. Built HERE
    # because ``funding_records`` is the last of its fields to resolve; nothing below this
    # point rebinds any of them, so the snapshot cannot go stale. (K-10c built this from
    # ``capability_ok``; K-11b moved the construction down so the plan / evaluator /
    # funding fields the output assembly reports could join it — the bar loop does not
    # touch ``ctx`` until its first closure runs, long after this line.)
    ctx = _RunConfig(
        config=config,
        fill_costs=fill_costs,
        alloc_on=alloc_on,
        alloc_compound=alloc_compound,
        allocatable_initial=allocatable_initial,
        item_share=item_share,
        reserve_nominal=reserve_nominal,
        portfolio_rules=portfolio_rules,
        sizing_ok=sizing_ok,
        leverage_ok=leverage_ok,
        strength_ok=strength_ok,
        capability_ok=capability_ok,
        # ---- K-11b: the rest of the resolved run, for the output assembly ----------
        initial_capital=initial_capital,
        timeframe=timeframe,
        item_count=item_count,
        execution_key=execution_key,
        future_dev_selected=future_dev_selected,
        # Fail-closed capability gates (the four above plus these six). Any False means
        # the run opened NO position and an L4 warning names the offending option.
        timing_ok=timing_ok,
        order_ok=order_ok,
        partial_close_ok=partial_close_ok,
        scaling_ok=scaling_ok,
        restrictions_ok=restrictions_ok,
        conflict_ok=conflict_ok,
        # Saved config sub-objects the provenance block reports verbatim.
        order_cfg=order_cfg,
        exit_logic=exit_logic,
        scaling_cfg=scaling_cfg,
        restrictions_cfg=restrictions_cfg,
        conflict_cfg=conflict_cfg,
        # Resolved policy tokens.
        strength_mode=strength_mode,
        partial_aftermath=partial_aftermath,
        restriction_rule=restriction_rule,
        unmodelled_restriction_types=unmodelled_restriction_types,
        overlap_policy=overlap_policy,
        stacking_policy=stacking_policy,
        hedge_policy=hedge_policy,
        stop_trigger_requirement=stop_trigger_requirement,
        stop_conflict_resolution=stop_conflict_resolution,
        stop_exit_conflict=stop_exit_conflict,
        trailing_lock_in_active=trailing_lock_in_active,
        scaling_enabled=scaling_enabled,
        scale_max_total=scale_max_total,
        # Portfolio-rules provenance: the SAVED policy vs the EXECUTED one stays visible.
        rules_active=rules_active,
        conflict_gate_on=conflict_gate_on,
        portfolio_cap_amount=portfolio_cap_amount,
        conflict_downgraded_from_net=conflict_downgraded_from_net,
        conflict_policy_unknown=conflict_policy_unknown,
        # Indicator plan + compiled evaluators.
        indicator_plan=indicator_plan,
        plan_active=plan_active,
        entry_evals=entry_evals,
        stop_evals=stop_evals,
        # Funding + tick provenance.
        funding=funding,
        funding_records=funding_records,
        tick_batches=tick_batches,
        tick_alignment_unavailable=tick_alignment_unavailable,
    )
    # K-02: rule 2's mapping conjunct, resolved ONCE before the bar loop — the engine only
    # ever sees the pre-resolved schedule, never the revision it came from.
    funding_has_mapping = funding.has_instrument_mapping if funding is not None else False
    funding_idx = 0
    # F-10: monotonic position-lifecycle id linking every decision-trace event of one
    # position (entry_signal -> entry_fill -> ... -> position_close) so a reviewer can
    # reconstruct WHY each position opened / did not open / closed. Incremented only on a
    # real fill (a gap is a no-fill, never a phantom position).
    position_seq = 0

    def _emit(
        event_type: str,
        *,
        event_time: str,
        direction: str | None,
        bar_seq: int,
        detail: dict[str, Any],
    ) -> None:
        """Bind the run's ledger to the extracted decision-trace journal."""
        emit_event(
            led,
            event_type,
            event_time=event_time,
            direction=direction,
            bar_seq=bar_seq,
            detail=detail,
        )

    def _entry_rule_snapshot(want: str) -> dict[str, Any]:
        """The entry DECISION evidence as-of the signal bar (F-10 rule id + conditions).

        Plan mode: the aggregation rule + every evaluated block's pinned ``rule_id``,
        its per-bar ``signal`` and its nested condition pass/fail. Proxy mode: the
        breakout look-back that produced the intent. Read-only — no re-evaluation."""
        if plan_active and indicator_plan is not None:
            return {
                "mode": "plan",
                "rule": indicator_plan.entry_rule.rule,
                "min_supporting_count": indicator_plan.entry_rule.min_supporting_count,
                "blocks": [
                    {
                        "rule_id": ev.block_id,
                        "key": ev.canonical_key,
                        "requirement": ev.requirement,
                        "signal": ev.current_signal,
                        "conditions": ev.condition_snapshot(),
                    }
                    for ev in entry_evals
                ],
            }
        return {"mode": "breakout_proxy", "window": _BREAKOUT_WINDOW, "direction": want}

    def _blocked_reason() -> str:
        return blocked_reason(ctx, led)

    def _strength_value(bar: _Bar) -> Decimal:
        """The strength multiplier at THIS signal bar (F-07g, §10.3) — PURE.

        Computed at DECISION time from the bars already replayed (``window`` holds the
        prior look-back; the signal bar itself is complete at its close) — look-back
        only, no look-ahead. Inert (exactly 1x, zero extra work) unless the
        ``volatility_adjusted`` mode is active, so every other mode stays byte-identical.

        The diagnostic counter lives in :func:`_signal_strength` rather than here, so a
        describe half can price a signal it may never place without moving the ledger."""
        if not strength_active:
            return _ONE
        return _volatility_strength((*window, bar))

    def _signal_strength(bar: _Bar) -> Decimal:
        """:func:`_strength_value`, plus the diagnostic count of a non-neutral multiplier.

        The booking-side spelling, for the two ``_phase_tail`` callers that compute and
        place a multiplier in one step. P4 splits the two (``_EntryDecision.effects``)."""
        multiplier = _strength_value(bar)
        if multiplier != _ONE:
            led.strength_adjustments += 1
        return multiplier

    def _book_effects(bar: _Bar, effects: tuple[_LedgerEffect, ...]) -> None:
        """Apply the counter bumps and trace events a describe half deferred, in order.

        The counter is dispatched explicitly rather than by ``setattr`` so that mypy sees
        every field this can write and an unrecognised name fails loudly instead of
        silently creating an attribute nothing reports."""
        for effect in effects:
            if effect.counter == "suppressed_entries":
                led.suppressed_entries += 1
            elif effect.counter == "entries_blocked_by_restriction":
                led.entries_blocked_by_restriction += 1
            elif effect.counter == "strength_adjustments":
                led.strength_adjustments += 1
            else:  # pragma: no cover — unreachable; the constructors are all above
                raise AssertionError(f"unknown ledger effect counter '{effect.counter}'")
            if effect.event:
                _emit(
                    effect.event,
                    event_time=bar.timestamp,
                    direction=effect.direction,
                    bar_seq=led.bars_seen,
                    detail=effect.detail,
                )

    def _close(
        exit_time: str,
        exit_price_raw: Decimal,
        reason: str,
        pos: _Position,
        *,
        bar_seq: int,
        fraction: Decimal = _ONE,
    ) -> bool:
        """Bind the run's ledger and pinned costs to the extracted close/book routine."""
        return close_position(
            led,
            pos,
            fill_costs,
            exit_time=exit_time,
            exit_price_raw=exit_price_raw,
            reason=reason,
            bar_seq=bar_seq,
            fraction=fraction,
        )

    def _apply_partial_aftermath(pos: _Position, exit_price_raw: Decimal) -> None:
        """Bind the pinned aftermath policy + cost params to the extracted ratchet."""
        if apply_partial_aftermath(
            pos,
            exit_price_raw,
            aftermath=partial_aftermath,
            half_spread=half_spread,
            slippage=slippage,
        ):
            led.lock_in_locks += 1

    def _sleeve_capital(current_equity: Decimal) -> Decimal:
        return sleeve_capital(ctx, current_equity)

    def _active_restrictions(bar_date: date | None) -> list[dict[str, str]]:
        """The enabled filters ACTIVE at this bar (F-07e, Master Ref §12) as trace evidence.

        Date-blackout: the bar's UTC date inside any configured window — an UNPARSEABLE
        bar timestamp counts as inside (fail closed: a bar whose date the engine cannot
        place must never trade through a blackout). Max-daily-loss: the UTC day's realized
        trade PnL at/beyond ``limit_percent`` of the run's initial capital (the pinned V1
        capital basis). Consecutive-loss: the realized losing-lot streak at/beyond
        ``max_losses``."""
        active: list[dict[str, str]] = []
        for spec in restriction_specs:
            if spec.filter_type == "date_blackout_filter":
                hit = bar_date is None or any(
                    start <= bar_date <= end for start, end in spec.date_ranges
                )
            elif spec.filter_type == "max_daily_loss_filter":
                assert spec.limit_percent is not None  # guaranteed by _parse_restriction
                limit_amount = initial_capital * spec.limit_percent / _HUNDRED
                hit = led.day_realized <= -limit_amount
            else:  # consecutive_loss_filter
                assert spec.max_losses is not None  # guaranteed by _parse_restriction
                hit = led.loss_streak >= spec.max_losses
            if hit:
                active.append({"filter_id": spec.filter_id, "filter_type": spec.filter_type})
        return active

    def _restrictions_block(active: list[dict[str, str]]) -> bool:
        """Combine ACTIVE filters per the §12.1 rule: "any" = OR, "all" = AND,
        "min_n_of_m" = at least N of the modelled filters active (I-15a, doc 02 §5.8).

        Minimum-N sits strictly between the two: N=1 reproduces "any" and
        N=len(specs) reproduces "all", so the existing two rules keep their exact
        pre-I-15a behaviour byte-for-byte.
        """
        if not restriction_specs:
            return False
        if restriction_rule == "all":
            return len(active) == len(restriction_specs)
        if restriction_rule == "min_n_of_m":
            return len(active) >= restriction_min_true
        return bool(active)

    def _bar_epoch_ms(ts: str) -> int | None:
        return bar_epoch_ms(ts)

    def _interval_covers(iv: PriorItemInterval, t_ms: int | None) -> bool:
        return interval_covers(iv, t_ms)

    def _conflicts_with_prior(direction: str, t_ms: int | None) -> bool:
        assert portfolio_rules is not None
        return conflicts_with_prior(led, portfolio_rules, direction, t_ms)

    def _prior_exposure_at(t_ms: int | None) -> Decimal:
        assert portfolio_rules is not None
        return prior_exposure_at(led, portfolio_rules, t_ms)

    def _planned_size(direction: str, fill_raw: Decimal, strength: Decimal) -> Decimal:
        return planned_size(
            ctx,
            led,
            direction=direction,
            fill_raw=fill_raw,
            strength=strength,
            equity=sizing_equity,
        )

    def _open(
        direction: str,
        bar: _Bar,
        fill_raw: Decimal,
        *,
        bar_seq: int,
        strength: Decimal = _ONE,
        size_override: Decimal | None = None,
    ) -> _Position | None:
        """Open a position at the cost-adjusted fill of ``fill_raw``, or ``None`` for a
        no-fill.

        ``fill_raw`` is the raw (pre-cost) execution price chosen by the entry timing:
        the signal bar's close (immediate), or the next bar's open / close (deferred) —
        removing the hardcoded current-candle-close assumption (F-07a). ``strength`` is
        the SIGNAL bar's strength multiplier (F-07g, 1x unless volatility-adjusted
        sizing is active). Under allocation a 0-capacity sleeve (an unallocated item, or
        a compound pool busted below its reserve) yields no fill at all — ``None`` —
        rather than a phantom 0-size trade (doc 13 §8.4 step 5/6). **Independent mode now
        refuses it too (GH #551).** This sentence used to read "Independent mode books even
        a bust-equity 0-size fill (preserving the risk-based no-phantom-profit invariant)",
        and that WAS the shipped behaviour — a documented invariant, not an oversight. It is
        deliberately reversed here: a position carrying no risk is not a trade, and booking
        one polluted `total_trades`, the win-rate denominator, average trade and expectancy,
        and wrote a zero-notional `position_intervals` row. Nothing about the risk-based
        path needs the phantom fill to stay honest — a refused entry books no profit either.
        An UNMODELLED sizing method (F-09), leverage
        configuration (F-07f), signal-strength mode (F-07g) or any ``future_dev`` capability
        selection (F-05) opens nothing at all — no phantom trade for a strategy the user
        never validly configured.

        ``capability_ok`` is enforced HERE because ``_open`` is the single choke point every
        entry path funnels through (flat entry, conflict-driven stack / replace, and the
        scaling ladder), so one check covers them all with no path left un-gated."""
        if not capability_ok or not sizing_ok or not leverage_ok or not strength_ok:
            return None
        rules_t_ms = _bar_epoch_ms(bar.timestamp) if rules_active else None
        if rules_active and conflict_gate_on and _conflicts_with_prior(direction, rules_t_ms):
            # Portfolio conflict gate (cross-item, doc 13 §8.4 step 6): an
            # earlier-pinned item holds the opposite direction on this instrument —
            # the later item's entry is blocked, its share never re-routed.
            led.portfolio_conflict_blocked_entries += 1
            led.portfolio_block_reason = "portfolio_conflict_blocked"
            return None
        is_long = direction == "long"
        entry_eff = _effective_fill(
            fill_raw, is_buy=is_long, half_spread=half_spread, slip=slippage
        )
        # Strategy Details sizing/risk constraints (within the item's sleeve under
        # allocation, then the remaining-sleeve outer cap, §8.4 step 5) — via
        # ``_planned_size`` so the F-07i (C) partial-fill evidence comparison and the
        # booked size can never diverge.
        size = _planned_size(direction, fill_raw, strength)
        if size <= _ZERO:
            # GH #551. This guard used to read ``if alloc_on and size <= _ZERO``, so it only
            # fired under allocation, and independent mode — the DEFAULT — opened a phantom
            # 0-size position that closed as a 0.00-PnL trade. The paths that reach a
            # non-positive size without allocation: a ``min > max`` window (``_clamp_to_limits``
            # fails closed to 0), a ``max`` of 0, ``base_position_size`` saved as 0 or NEGATIVE,
            # a non-positive Kelly edge, and any method run on bust equity — ``risk_based_sizing``
            # included, whose ``stop_loss_point`` is schema-guarded ``gt=0`` but whose EQUITY leg
            # is not. ``<= _ZERO`` covers all of them, the negative case included: a stored
            # ``-5`` used to open a -5-unit long and book a LOSS on a bar that moved in the
            # position's favour, because the size's sign inverts the PnL.
            #
            # What this actually closes, measured rather than assumed: the trade count, the
            # win-rate denominator, average trade and expectancy, the zero-notional
            # ``position_intervals`` row, and — with a commission configured — real money, since
            # a 0-unit position paid the same flat per-fill fee as a full one.
            #
            # It does NOT close a cross-item leak, and an earlier version of this comment
            # claimed it did. ``execution/rules.py::conflicts_with_prior`` does read an interval
            # by ``direction`` alone, but it never sees a phantom: the only producer of
            # ``PriorItemInterval`` is ``build_prior_intervals`` above, which drops any window
            # whose ``peak_notional`` is not positive before the gate runs. That filter is
            # pinned by ``test_backtest_portfolio_rules.py``'s
            # ``test_build_prior_intervals_fails_closed_on_bad_bounds_and_drops_zero_notional``.
            #
            # Under allocation the reason stays ``sleeve_zero_capacity`` (more specific, and
            # already contracted) — the ladder in ``sizing.blocked_reason`` reaches it via
            # ``ctx.alloc_on`` when nothing was handed over, so this sets the reason only for
            # the independent case that previously reported the uninformative ``no_fill``.
            if not alloc_on:
                led.portfolio_block_reason = SIZE_RESOLVED_TO_ZERO
            return None
        if rules_active and portfolio_cap_amount is not None and size > _ZERO:
            # Composition-wide Max Total Exposure: the entry may only deploy the
            # headroom left under the cap after the earlier-pinned items' concurrent
            # notional (the item itself is flat when opening — single-position
            # invariant). Over-cap clamps down (an outer cap, the sleeve precedent);
            # zero headroom blocks the fill outright — never a phantom over-cap trade.
            headroom = portfolio_cap_amount - _prior_exposure_at(rules_t_ms)
            allowed = (
                (headroom / entry_eff).quantize(_QTY)
                if headroom > _ZERO and entry_eff > _ZERO
                else _ZERO
            )
            if size > allowed:
                if allowed <= _ZERO:
                    led.portfolio_exposure_blocked_entries += 1
                    led.portfolio_block_reason = "portfolio_max_total_exposure"
                    return None
                size = allowed
                led.portfolio_exposure_clamped_entries += 1
        if size_override is not None:
            # F-07i (C): a partial fill books the print-evidenced fraction of the planned
            # size (already sized/capped above — the override is strictly smaller than
            # the plan; the portfolio cap may have clamped further, so keep the smaller).
            size = min(size, size_override)
        nonlocal position_seq
        position_seq += 1
        return _Position(
            position_seq=position_seq,
            entry_bar_seq=bar_seq,
            direction=direction,
            entry_time=bar.timestamp,
            entry_price=entry_eff,
            size=size,
            pct_stop=_pct_stop_level(config, is_long=is_long, entry_price=entry_eff),
            abs_stop=_abs_stop_level(config),
            trail_pct=trail_pct,
            trail_anchor=fill_raw,
            entry_notional=(entry_eff * size).quantize(_MONEY),
            trail_lock_in_pct=trail_lock_in_pct,
            initial_size=size,
            layers_filled=0,
            scale_reference=fill_raw,
            # S5c: anchor layer 1's closed-bar gate to the ENTRY bar's candle. The entry
            # bar's own layer-TF candle has not closed yet, so the first candidate must
            # wait for the next bucket — the no-lookahead half of §5.7's alignment rule.
            scale_layer_bucket=layer_bucket(
                _bar_epoch_ms(bar.timestamp), layer_timeframe(config, 0)
            ),
            peak_notional=(entry_eff * size).quantize(_MONEY),
        )

    def _do_open(
        direction: str,
        bar: _Bar,
        fill_raw: Decimal,
        *,
        bar_seq: int,
        deferred: bool,
        strength: Decimal = _ONE,
        size_override: Decimal | None = None,
        extra_detail: dict[str, Any] | None = None,
    ) -> _Position | None:
        """Open a position AND emit the F-10 fill/blocked decision-trace event.

        On a real fill: ``entry_fill`` (the execution — position_seq, price, size, timing).
        On a no-fill: ``entry_blocked`` with the concrete reason (sizing/sleeve), so a
        signalled-but-unfilled entry is never a silent gap in the trace. ``strength`` is
        the SIGNAL bar's multiplier (F-07g), carried verbatim from the decision point.
        ``extra_detail`` (F-07i C) stamps tick-execution provenance onto the fill event
        ONLY when present, so tick-less traces stay byte-identical."""
        pos = _open(
            direction,
            bar,
            fill_raw,
            bar_seq=bar_seq,
            strength=strength,
            size_override=size_override,
        )
        if pos is not None:
            if commission > _ZERO:
                # GH #552 / PD-2: commission is PER-FILL, and this is the entry fill.
                # It used to be free — the whole round trip was billed at the close — so
                # equity only fell when the position closed. Charging it here is not a
                # different total, it is a different TIME: equity drops at entry, which
                # moves ``peak``, drawdown and every metric derived from them. That is
                # why this change refreshes the equity curve and not only the trade rows.
                #
                # The same seam the scale ladder and ``absorb_remainder`` already use:
                # the charge lands on equity, not in the trade row's pnl, so the exit's
                # own ``commission`` in ``close_position`` is the only one that lot
                # carries. Booking it in both places would double-count.
                led.equity = (led.equity - commission).quantize(_MONEY)
            fill_detail: dict[str, Any] = {
                "position_seq": pos.position_seq,
                "fill_price": str(pos.entry_price),
                "size": str(pos.size),
                "entry_notional": str(pos.entry_notional),
                "timing": config.data.execution.entry_timing,
                "order_type": order_cfg.type,
                "deferred": deferred,
            }
            if extra_detail:
                fill_detail.update(extra_detail)
            _emit(
                "entry_fill",
                event_time=bar.timestamp,
                direction=direction,
                bar_seq=bar_seq,
                detail=fill_detail,
            )
        else:
            _emit(
                "entry_blocked",
                event_time=bar.timestamp,
                direction=direction,
                bar_seq=bar_seq,
                detail={"reason": _blocked_reason(), "deferred": deferred},
            )
        return pos

    def _limit_touch_evidence(
        wl: _WorkingLimit, bar: _Bar, ticks: tuple[_Tick, ...]
    ) -> tuple[bool, tuple[_Tick, ...]]:
        """Bind the pinned ``tick_entry_authority`` to the extracted touch rule."""
        return limit_touch_evidence(
            wl.limit_price,
            wl.direction,
            bar,
            ticks,
            tick_entry_authority=tick_entry_authority,
        )

    def _absorb_remainder(
        pos: _Position, bar: _Bar, price_raw: Decimal, add_size: Decimal, *, action: str
    ) -> None:
        """Bind the run's ledger, pinned costs and partial policy to the extracted
        remainder top-up."""
        absorb_remainder(
            led,
            pos,
            fill_costs,
            bar=bar,
            price_raw=price_raw,
            add_size=add_size,
            action=action,
            bar_seq=led.bars_seen,
            partial_policy=partial_policy,
        )

    def _fill_resting_limit(
        wl: _WorkingLimit,
        bar: _Bar,
        prints: tuple[_Tick, ...],
        *,
        bar_seq: int,
        armed_same_bar: bool = False,
    ) -> None:
        """Fill a TOUCHED resting entry order, applying the partial-fill policy (F-07i C).

        The full-fill path (policy ``not_allowed``, no usable print-size evidence, or
        evidence covering the whole planned size) is the F-07b model verbatim: the whole
        planned size books at the limit level. With print-size evidence SHORT of the
        planned size the policy governs: ``minimum_50_percent`` rejects a sub-50% bar
        (the order keeps resting); otherwise the evidenced fraction books at the level
        (a ``partial_fill`` trace event) and the remainder is disposed per policy —
        ``cancel_remaining`` drops it, ``fill_remaining_as_market`` books it at this
        bar's close, ``allowed`` / ``minimum_50_percent`` rest it against the open
        position for later top-ups. Size-less evidence degrades to the coarse full-fill
        model, flagged L4 (a fraction is never fabricated)."""
        nonlocal position, working_limit
        extra: dict[str, Any] = {}
        if prints:
            extra["tick_resolved"] = True
        if armed_same_bar:
            extra["same_bar_stop_limit"] = True
        planned = _planned_size(wl.direction, wl.limit_price, wl.strength)
        decision = decide_partial_fill(
            planned=planned,
            prints=prints,
            partial_active=partial_active,
            partial_policy=partial_policy,
        )
        available = decision.filled_size
        if decision.evidence_missing:
            led.partial_evidence_missing = True
        if decision.outcome == "full":
            led.limit_orders_filled += 1
            if prints:
                led.tick_resolved_entry_fills += 1
            if armed_same_bar:
                led.same_bar_stop_limit_fills += 1
            position = _do_open(
                wl.direction,
                bar,
                wl.limit_price,
                bar_seq=bar_seq,
                deferred=True,
                strength=wl.strength,
                extra_detail=extra or None,
            )
            working_limit = None
            return
        if decision.outcome == "rejected_below_minimum":
            led.partial_fills += 1
            _emit(
                "partial_fill",
                event_time=bar.timestamp,
                direction=wl.direction,
                bar_seq=bar_seq,
                detail={
                    "policy": partial_policy,
                    "action": "rejected_below_minimum",
                    "planned_size": str(planned),
                    "available_size": str(available),
                    "limit_price": str(wl.limit_price),
                },
            )
            return  # the order keeps resting whole; validity/unfilled policy still apply
        led.limit_orders_filled += 1
        led.tick_resolved_entry_fills += 1
        if armed_same_bar:
            led.same_bar_stop_limit_fills += 1
        position = _do_open(
            wl.direction,
            bar,
            wl.limit_price,
            bar_seq=bar_seq,
            deferred=True,
            strength=wl.strength,
            size_override=available,
            extra_detail={**extra, "partial_fill": True},
        )
        if position is None:
            working_limit = None
            return
        remainder = decision.remainder
        led.partial_fills += 1
        disposition_detail: dict[str, Any] = {
            "position_seq": position.position_seq,
            "policy": partial_policy,
            "planned_size": str(planned),
            "filled_size": str(available),
            "remaining_size": str(remainder),
            "limit_price": str(wl.limit_price),
        }
        if partial_policy == "cancel_remaining":
            disposition_detail["action"] = "remainder_cancelled"
            working_limit = None
        elif partial_policy == "fill_remaining_as_market":
            disposition_detail["action"] = "remainder_market_filled"
            _emit(
                "partial_fill",
                event_time=bar.timestamp,
                direction=wl.direction,
                bar_seq=bar_seq,
                detail=disposition_detail,
            )
            _absorb_remainder(position, bar, bar.close, remainder, action="market_remainder")
            working_limit = None
            return
        else:  # allowed / minimum_50_percent (>= 50% already ensured above)
            disposition_detail["action"] = "remainder_resting"
            wl.remaining_size = remainder
            wl.for_position_seq = position.position_seq
            wl.remainder_placed_seq = bar_seq
        _emit(
            "partial_fill",
            event_time=bar.timestamp,
            direction=wl.direction,
            bar_seq=bar_seq,
            detail=disposition_detail,
        )

    def _plan_exit(pos: _Position, entry_signal: str | None, exit_hit: bool) -> bool:
        """Exit on an explicit exit signal or (opt-in) an opposite entry signal."""
        if exit_hit:
            return True
        opposite = entry_signal is not None and entry_signal != pos.direction
        return bool(opposite and indicator_plan is not None and indicator_plan.exit_on_opposite)

    def _emit_stop_resolution(outcome: _StopOutcome, event_time: str, direction: str) -> None:
        """Record the resolved stop (Master Ref §9.2: ledger carries priority + sources).

        Emits a ``stop_resolution`` decision-trace event whenever more than one rule fired,
        the executed rule was a Logic-Based Stop, the OHLCV first-trigger approximation
        applied, or the bar GAPPED past the winning level so the fill differs from the
        trigger. The plain single-price-stop path still emits nothing extra.

        The gap case earns an event of its own precisely because it is the one where the
        executed price cannot be re-derived from the config: every other stop fill IS the
        rule's own level, so a reader who could not see ``trigger_price`` beside ``price``
        would have no way to tell a gapped exit from a mis-computed one (#549)."""
        if any(k.startswith("logic:") for k in outcome.triggered):
            led.logic_stop_triggers += 1
        if outcome.tick_resolved:
            led.tick_first_trigger_resolutions += 1
        if outcome.gap_adjusted:
            led.gap_adjusted_stops += 1
        if (
            len(outcome.triggered) > 1
            or outcome.approximated_first
            or outcome.tick_resolved
            or outcome.gap_adjusted
            or outcome.executed_key.startswith("logic:")
        ):
            detail: dict[str, Any] = {
                "executed": outcome.executed_key,
                "triggered": list(outcome.triggered),
                "requirement": stop_trigger_requirement,
                "resolution": stop_conflict_resolution,
                "first_trigger_approximated": outcome.approximated_first,
            }
            # F-07i (B): only stamped when the REAL tick order resolved the winner, so
            # tick-less traces stay byte-identical.
            if outcome.tick_resolved:
                detail["first_trigger_tick_resolved"] = True
            # #549: BOTH prices, and only when they diverge — a non-gapped trace keeps its
            # existing shape rather than growing a field that always echoes ``price``.
            if outcome.gap_adjusted:
                # Quantized to the money step like every other price the trace publishes:
                # these two come from different sources (a configured level vs a bar's
                # open), so raw ``str()`` would render "101.50" beside "90" purely from how
                # the inputs were written.
                detail["trigger_price"] = str(outcome.trigger_price.quantize(_MONEY))
                detail["executed_price"] = str(outcome.price.quantize(_MONEY))
                detail["gap_adjusted"] = True
            led.signal_events.append(
                SignalEventRow(
                    seq=len(led.signal_events),
                    event_time=event_time,
                    event_type="stop_resolution",
                    direction=direction,
                    detail=detail,
                )
            )

    def _phase_admit(bar: _Bar) -> None:
        """P0 / doc 15 §9.3 step (1) — admit this bar and derive its decision inputs.

        Bookkeeping, the tick cursor, the restriction clock, then the evaluators and the
        signals they aggregate. It decides nothing and books no money; what it leaves behind
        (``entry_signal``, ``exit_hit``, ``bar_ticks``, ``bar_date``, ``trades_before_bar``)
        is what the later phases read. Those five were per-bar locals of the former ``_step``
        and are now function-scope state for the same reason the ten carried names are: a
        phase the caller invokes separately cannot reach another phase's locals. Each is
        re-initialised HERE, at the top of every bar, so nothing leaks from the previous one."""
        nonlocal bar_date, bar_ticks, current_day, entry_signal, exit_hit
        nonlocal scale_signal, trades_before_bar

        led.bars_seen += 1
        if not led.first_ts:
            led.first_ts = bar.timestamp
        led.last_bar = bar
        # F-07i (B): advance the tick cursor EVERY bar (position open or not) so the
        # forward-only stream stays aligned to the bar clock.
        bar_ticks = ()
        if tick_cursor is not None:
            bar_ticks = tick_cursor.for_bar(bar.timestamp)
            if bar_ticks:
                led.tick_bars += 1
        # F-07d: an exit lot (full or partial) realized on THIS bar appends a trade row;
        # the scale ladder below never adds to a position a bar has already reduced.
        trades_before_bar = len(led.trades)

        # F-07e: the restriction filters' clock. The bar's UTC calendar date drives the
        # date-blackout windows and rolls the max-daily-loss accumulator at each new
        # day; an unparseable timestamp yields ``None`` (date-dependent filters then
        # fail closed) and never resets the day. Skipped entirely when no modelled
        # filter is enabled — the hot loop stays byte-identical.
        bar_date = None
        if restriction_specs:
            parsed_bar_time = parse_utc(bar.timestamp, source_zone=None)
            bar_date = parsed_bar_time.date() if parsed_bar_time is not None else None
            if bar_date is not None and bar_date != current_day:
                current_day = bar_date
                led.day_realized = _ZERO

        # (1) doc 15 §9.3 step 1 — admit only the Market/Research data available by this
        # bar's clock time. The market side is the bar itself (the pinned revision is
        # replayed strictly forward, so a later bar can never be read early); the
        # research side is the K-02 available-time gate applied in step (2) below and in
        # every other research feed. Real indicator signals (when a plan resolved);
        # evaluators see EVERY bar.
        entry_signal = None
        exit_hit = False
        if plan_active and indicator_plan is not None:
            for ev in entry_evals:
                ev.update(
                    bar.close,
                    bar.high,
                    bar.low,
                    bar.open,
                    volume=bar.volume,
                    timestamp=bar.timestamp,
                )
            for ev in exit_evals:
                ev.update(
                    bar.close,
                    bar.high,
                    bar.low,
                    bar.open,
                    volume=bar.volume,
                    timestamp=bar.timestamp,
                )
            entry_signal = aggregate(indicator_plan.entry_rule, entry_evals)
            if exit_evals and indicator_plan.exit_rule is not None:
                exit_hit = aggregate(indicator_plan.exit_rule, exit_evals) is not None

        # §5.9 Same Candle Entry / Exit — when FLAT, an entry and an explicit exit
        # decision can be close-confirmed by the same bar. There is no position for
        # the exit to close and no honest intrabar ordering between two close-derived
        # signals. The default and every conservative policy suppress the new entry;
        # explicit ``exit_first`` processes the exit as a no-op, then admits it.
        if position is None and entry_signal is not None and exit_hit:
            admits_entry = same_candle_entry_exit == "exit_first"
            _emit(
                "entry_exit_collision",
                event_time=bar.timestamp,
                direction=entry_signal,
                bar_seq=led.bars_seen,
                detail={
                    "policy": same_candle_entry_exit,
                    "resolution": (
                        "flat_exit_noop_then_entry"
                        if admits_entry
                        else "ambiguous_entry_suppressed"
                    ),
                    "intrabar_order_available": False,
                },
            )
            if not admits_entry:
                led.suppressed_entries += 1
                entry_signal = None

        # F-08: logic-stop evaluators advance EVERY bar (independent of the entry plan)
        # so a logic-based stop can fire against the open position.
        for ev in stop_evals:
            ev.update(
                bar.close,
                bar.high,
                bar.low,
                bar.open,
                volume=bar.volume,
                timestamp=bar.timestamp,
            )

        # S5c: logic-SCALING evaluators advance every bar for the same reason. The
        # aggregated direction is this bar's scaling proposal; the ladder below turns it
        # into a layer only on an EDGE, in the open position's own direction, and only
        # on a bar that closes the layer's timeframe candle.
        if scale_evals and indicator_plan is not None and indicator_plan.scale_rule is not None:
            for ev in scale_evals:
                ev.update(
                    bar.close,
                    bar.high,
                    bar.low,
                    bar.open,
                    volume=bar.volume,
                    timestamp=bar.timestamp,
                )
            scale_signal = aggregate(indicator_plan.scale_rule, scale_evals)

    def _phase_carry(bar: _Bar) -> None:
        """P1 / doc 15 §9.3 step (2) — funding and carry, charged at the TOP of the bar."""
        plan = _compute_carry(bar)
        if plan is not None:
            _book_carry(bar, plan)

    def _compute_carry(bar: _Bar) -> _CarryPlan | None:
        """P1 DESCRIBED — which funding records fire here and what each costs.

        Pure: ``due_funding_charges`` takes the cursor by value and hands back the advanced
        one, so nothing moves until :func:`_book_carry` accepts the plan."""
        if not funding_records:
            return None
        # (2) K-03 / F-11 funding cost — doc 15 §9.3 step 2: funding/fee/carry is applied
        # at the TOP of the bar, BEFORE any fill, stop, exposure check, entry or scaling
        # of this bar. That ordering is not cosmetic: ``led.equity`` is what sizes an entry
        # (``_position_size``) and what bounds the allocation sleeve / exposure caps
        # (``_sleeve_capital``). Charging funding at the END of the bar (the pre-K-03
        # order) sized every entry and every scale layer off an equity that had not yet
        # paid its carry — under perp funding, a one-directional cumulative bias toward
        # systematically LARGER positions and a late-binding ``max_total_exposure``.
        #
        # A backward/as-of join over the available-time-safe schedule (doc 12 §8.4
        # rule 3). Every funding record now AVAILABLE at this bar
        # (``available_at <= bar_time``) fires exactly once; while a position is held it
        # charges ``notional * rate`` (a long pays a positive rate, a short receives),
        # reducing equity mid-run so funding-on and funding-off produce a verifiably
        # different result. A record dated after the last replayed bar never fires — a
        # future value can never leak into the run. Records that become available while
        # flat are consumed without a charge: funding is paid only for the interval the
        # position is actually held (perp funding convention). Two consequences of the
        # step-2 placement follow directly from that convention: a position still open at
        # the START of this bar pays a record available now even if the bar later closes
        # it (the pre-K-03 order silently DROPPED that charge), and a position OPENED on
        # this bar does not pay it (it was not held when the record became available).
        #
        # K-02: the as-of comparison is NOT written inline here — it is delegated to
        # ``research_data.time_policy.is_eligible_for_decision``, the single canonical
        # rule-2 gate (mapping AND ``available_at <= t``). This bar's timestamp is the
        # decision time, and ``schedule.has_instrument_mapping`` is the resolved mapping
        # conjunct, so every research value the engine consumes passes one audited
        # predicate rather than a hand-rolled comparison that can drift.
        #
        # FAIL CLOSED on an unresolvable bar timestamp: with no decision time, eligibility
        # cannot be evaluated at all, and silently firing nothing would book an
        # over-optimistic ZERO funding cost for the whole run. This deliberately differs
        # from the date-blackout precedent below, where a restrictive reading exists
        # (treat the bar as inside the window); a cost has no such reading.
        # ``due_funding_charges`` decides WHICH records fire and what each costs;
        # applying them (equity/peak/counters + the decision event) stays in the booking
        # half. Records that become available while FLAT are still consumed — the cursor
        # advances even when nothing is charged.
        next_index, due_charges = due_funding_charges(
            funding_records,
            start_index=funding_idx,
            decision_time=resolve_funding_decision_time(bar.timestamp),
            has_instrument_mapping=funding_has_mapping,
            position_direction=position.direction if position is not None else None,
            position_notional=(position.entry_notional if position is not None else _ZERO),
        )
        return _CarryPlan(next_index=next_index, charges=tuple(due_charges))

    def _book_carry(bar: _Bar, plan: _CarryPlan) -> None:
        """P1 BOOKED — charge the plan against equity and trace every record that fired."""
        nonlocal funding_idx

        funding_idx = plan.next_index
        if position is not None:
            for due in plan.charges:
                rec = due.record
                charge = due.amount
                if charge != _ZERO:
                    led.equity = (led.equity - charge).quantize(_MONEY)
                    led.peak = max(led.peak, led.equity)
                    led.funding_paid += charge
                led.funding_charges += 1
                _emit(
                    "funding_charge",
                    event_time=bar.timestamp,
                    direction=position.direction,
                    bar_seq=led.bars_seen,
                    detail={
                        "position_seq": position.position_seq,
                        "rate": str(rec.rate),
                        "charge": str(charge),
                        "available_at": rec.available_at.isoformat(),
                        "event_at": rec.event_at.isoformat(),
                        "source_revision_id": (
                            funding.source_revision_id if funding is not None else None
                        ),
                    },
                )

    def _phase_open_fills(bar: _Bar) -> None:
        """Steps (3)/(3b)/(3c) — fills deferred to this bar's OPEN, resting limit orders and
        a resting stop trigger while flat. ADR-0002 calls this P2 and the phase loop does not
        model it; it stays on the item's own timeline, which is where it already lived."""
        nonlocal pending, position, working_limit, working_stop

        # (3) Resolve a fill deferred to THIS bar's OPEN (next_candle_open). Runs
        # before the intrabar stop path so the open fill precedes the bar's high/low.
        if pending is not None and pending.target_seq == led.bars_seen and pending.at_open:
            if pending.kind == "entry" and position is None:
                led.deferred_entry_fills += 1
                position = _do_open(
                    pending.direction,
                    bar,
                    bar.open,
                    bar_seq=led.bars_seen,
                    deferred=True,
                    strength=pending.strength,
                )
            elif pending.kind == "exit" and position is not None:
                led.deferred_exit_fills += 1
                # F-07c: a deferred exit SIGNAL closes ``close_fraction`` and holds the
                # remainder under the aftermath (a full close nulls the position).
                if _close(
                    bar.timestamp,
                    bar.open,
                    pending.reason,
                    position,
                    bar_seq=led.bars_seen,
                    fraction=close_fraction,
                ):
                    position = None
                else:
                    _apply_partial_aftermath(position, bar.open)
            pending = None

        # (3b) Resolve a RESTING limit ENTRY order against THIS bar (F-07b/F-07i C).
        # Resolves before the position block (like a next_open fill), so a same-bar
        # protective stop can hit the just-filled position — consistent with the
        # deferred-open path. A touch fills at the limit via ``_fill_resting_limit``
        # (print-authoritative under a tick-backed timing; partial-fill policy from
        # print-size evidence); on the expiry bar an order still resting applies its
        # policy (convert-to-market fills at the close, else cancel); otherwise a
        # re-price policy recomputes the limit from THIS bar's close for the next bar.
        if (
            working_limit is not None
            and working_limit.remaining_size is None  # a remainder is (1b2)'s, never a fresh entry
            and position is None
        ):
            wl = working_limit
            touched, touch_prints = _limit_touch_evidence(wl, bar, bar_ticks)
            if touched:
                _fill_resting_limit(wl, bar, touch_prints, bar_seq=led.bars_seen)
            if working_limit is not None and position is None:
                expired = wl.expires_seq is not None and led.bars_seen >= wl.expires_seq
                if expired:
                    if wl.unfilled_policy == "convert_to_market_order":
                        led.limit_orders_filled += 1
                        position = _do_open(
                            wl.direction,
                            bar,
                            bar.close,
                            bar_seq=led.bars_seen,
                            deferred=True,
                            strength=wl.strength,
                        )
                    else:
                        led.limit_orders_cancelled += 1
                        _emit(
                            "limit_order_cancelled",
                            event_time=bar.timestamp,
                            direction=wl.direction,
                            bar_seq=led.bars_seen,
                            detail={
                                "reason": "validity_expired",
                                "unfilled_policy": wl.unfilled_policy,
                                "limit_price": str(wl.limit_price),
                            },
                        )
                    working_limit = None
                elif wl.unfilled_policy == "re_price_next_candle":
                    wl.limit_price = _limit_price(wl.price_rule, bar.close, wl.offset)

        # (3b2) F-07i (C): a PARTIAL fill's remaining order rests AGAINST its open
        # position (the order-remaining ledger, Master Ref §6.3): later touches top
        # the position up at the limit level until the validity/unfilled policy
        # disposes of the remainder. The remainder dies with its position — a
        # stop/exit closing the position cancels the order's remaining intent.
        if working_limit is not None and working_limit.remaining_size is not None:
            wl = working_limit
            remaining = working_limit.remaining_size
            if position is None or position.position_seq != wl.for_position_seq:
                # The order's position is gone — the remaining intent is cancelled,
                # traced (never a silent gap, and NEVER re-armed as a fresh entry).
                led.limit_orders_cancelled += 1
                _emit(
                    "limit_order_cancelled",
                    event_time=bar.timestamp,
                    direction=wl.direction,
                    bar_seq=led.bars_seen,
                    detail={
                        "reason": "position_closed",
                        "unfilled_policy": wl.unfilled_policy,
                        "limit_price": str(wl.limit_price),
                        "remaining_size": str(remaining),
                    },
                )
                working_limit = None
            elif wl.remainder_placed_seq is not None and led.bars_seen > wl.remainder_placed_seq:
                touched, touch_prints = _limit_touch_evidence(wl, bar, bar_ticks)
                if touched:
                    sized = [t for t in touch_prints if t.size is not None]
                    if touch_prints and not sized:
                        led.partial_evidence_missing = True
                    top_up = (
                        min(
                            remaining,
                            sum((t.size for t in sized if t.size is not None), _ZERO),
                        )
                        if sized
                        # no size evidence -> coarse model: the whole remainder fills
                        else remaining
                    )
                    if top_up > _ZERO:
                        _absorb_remainder(
                            position, bar, wl.limit_price, top_up, action="remainder_touch"
                        )
                        remaining = remaining - top_up
                        if remaining <= _ZERO:
                            working_limit = None
                        else:
                            wl.remaining_size = remaining
                            wl.remainder_placed_seq = led.bars_seen
                if working_limit is not None:
                    expired = wl.expires_seq is not None and led.bars_seen >= wl.expires_seq
                    if expired:
                        if wl.unfilled_policy == "convert_to_market_order":
                            _absorb_remainder(
                                position,
                                bar,
                                bar.close,
                                remaining,
                                action="remainder_validity_market",
                            )
                        else:
                            led.limit_orders_cancelled += 1
                            _emit(
                                "limit_order_cancelled",
                                event_time=bar.timestamp,
                                direction=wl.direction,
                                bar_seq=led.bars_seen,
                                detail={
                                    "reason": "partial_remainder_expired",
                                    "unfilled_policy": wl.unfilled_policy,
                                    "limit_price": str(wl.limit_price),
                                    "remaining_size": str(wl.remaining_size),
                                },
                            )
                        working_limit = None
                    elif wl.unfilled_policy == "re_price_next_candle":
                        wl.limit_price = _limit_price(wl.price_rule, bar.close, wl.offset)

        # (3c) Resolve a RESTING stop ENTRY trigger against THIS bar (F-07h). A long
        # buy-stop fires when the bar's high reaches the trigger (short mirror: low).
        # A plain stop then fills market-like at max(trigger, open) — a gap through
        # the trigger fills at the open (the trigger price no longer exists),
        # deterministic over OHLCV. A stop-limit instead ARMS the (1b) limit machine:
        # placed HERE (below the (1b) block), the armed limit is first examined on the
        # NEXT bar — the same-bar stop-then-limit sequence needs tick ordering, so a
        # same-bar limit touch never fills (doc 02 §5.2: the trigger may fire and the
        # position still never open). Validity counts from the trigger bar, and the
        # (3b) unfilled/re-price policies then apply verbatim.
        if working_stop is not None and position is None:
            ws = working_stop
            fired = (
                bar.high >= ws.trigger_price
                if ws.direction == "long"
                else bar.low <= ws.trigger_price
            )
            if fired:
                led.stop_orders_triggered += 1
                trigger_detail: dict[str, Any] = {
                    "trigger_price": str(ws.trigger_price),
                    "order_type": order_cfg.type,
                }
                if ws.limit_price is None:
                    fill_price = (
                        max(ws.trigger_price, bar.open)
                        if ws.direction == "long"
                        else min(ws.trigger_price, bar.open)
                    )
                    trigger_detail["fill_price"] = str(fill_price)
                    _emit(
                        "stop_order_triggered",
                        event_time=bar.timestamp,
                        direction=ws.direction,
                        bar_seq=led.bars_seen,
                        detail=trigger_detail,
                    )
                    position = _do_open(
                        ws.direction,
                        bar,
                        fill_price,
                        bar_seq=led.bars_seen,
                        deferred=True,
                        strength=ws.strength,
                    )
                else:
                    working_limit = _WorkingLimit(
                        direction=ws.direction,
                        limit_price=ws.limit_price,
                        offset=ws.limit_offset,
                        price_rule=ws.limit_rule,
                        unfilled_policy=ws.unfilled_policy,
                        expires_seq=(
                            None if ws.validity_bars is None else led.bars_seen + ws.validity_bars
                        ),
                        strength=ws.strength,
                    )
                    led.limit_orders_placed += 1
                    trigger_detail["limit_price"] = str(ws.limit_price)
                    _emit(
                        "stop_order_triggered",
                        event_time=bar.timestamp,
                        direction=ws.direction,
                        bar_seq=led.bars_seen,
                        detail=trigger_detail,
                    )
                    _emit(
                        "limit_order_placed",
                        event_time=bar.timestamp,
                        direction=ws.direction,
                        bar_seq=led.bars_seen,
                        detail={
                            "limit_price": str(ws.limit_price),
                            "price_rule": ws.limit_rule,
                            "unfilled_policy": ws.unfilled_policy,
                            "expires_bar_seq": working_limit.expires_seq,
                            "armed_by": "stop_order_triggered",
                        },
                    )
                    # F-07i (C): under ``stop_limit_priority_simulation`` the
                    # same-bar stop-then-limit sequence is resolved by the OBSERVED
                    # print path: if a print AFTER the trigger's first touch reaches
                    # the armed limit, the limit fills THIS bar (doc 02 §5.2 stays
                    # true — the trigger may fire and the position still never open
                    # when the later prints never come back to the limit). A
                    # print-less trigger bar keeps the conservative next-bar model
                    # (Master Ref §9.1: no assumed/implicit price path — the
                    # sequence is only ever taken from observed prints).
                    if stop_limit_sim and bar_ticks:
                        trigger_idx = _first_trigger_index(
                            bar_ticks,
                            ws.trigger_price,
                            is_long=ws.direction == "long",
                        )
                        if trigger_idx is not None:
                            armed = working_limit
                            after_trigger = _touching_ticks(
                                bar_ticks[trigger_idx + 1 :],
                                armed.limit_price,
                                is_buy=armed.direction == "long",
                            )
                            if after_trigger:
                                _fill_resting_limit(
                                    armed,
                                    bar,
                                    after_trigger,
                                    bar_seq=led.bars_seen,
                                    armed_same_bar=True,
                                )
                working_stop = None

    def _phase_held(bar: _Bar) -> bool:
        """P3 / step (4) — protection, stop and exit against a HELD position.

        Returns whether it took the branch, which is how the former ``if/elif`` chain keeps
        its exclusivity across the split: a bar that closes a position here must NOT then be
        offered a fresh entry by :func:`_phase_entry`, exactly as the ``elif`` guaranteed."""
        decision = _evaluate_held(bar)
        if decision is None:
            return False
        _apply_held(bar, decision)
        return True

    def _evaluate_held(bar: _Bar) -> _HeldDecision | None:
        """P3 DESCRIBED — which protection/exit arm this bar takes, closing nothing.

        Returns ``None`` while flat, which is what the caller turns back into the former
        ``if``/``elif`` exclusivity. The arm is named rather than taken, so a pool can hear
        what the item must do before it decides whether the item may do it (ADR-0002 §6).

        The one thing this DOES write is the position's trail anchor, and deliberately: the
        anchor is a high-water mark of the market, not a booking. It moves because the bar
        printed that extreme — no arbitration can un-print it — and ``max``/``min`` makes
        re-describing the same bar idempotent. ``_resolve_stop`` derives the trailing level
        from it, so an un-advanced anchor would describe last bar's stop."""
        if position is None:
            return None
        # (4) protection / stop / exit against this bar (intrabar touch).
        if position.direction == "long":
            position.trail_anchor = max(position.trail_anchor, bar.high)
        else:
            position.trail_anchor = min(position.trail_anchor, bar.low)
        opp = "short" if position.direction == "long" else "long"
        logic_triggered = [
            f"logic:{spec.block_id}" for spec, ev in stop_pairs if ev.current_signal == opp
        ]
        stop_outcome = _resolve_stop(
            config,
            position,
            bar,
            logic_enabled=logic_enabled,
            logic_triggered=logic_triggered,
            ticks=bar_ticks,
        )
        stop_touched = stop_outcome is not None
        # A fresh exit signal is evaluated only when no exit is already committed:
        # a deferred exit from a prior bar (``pending``) — or a resting touch
        # exit (F-07i C) — is pinned and cannot be pre-empted by a new signal;
        # only an intrabar stop below can cancel it.
        exit_wanted = (
            pending is None
            and exit_touch is None
            and (
                _plan_exit(position, entry_signal, exit_hit)
                if plan_active
                else _exit_proxy(position, bar, window)
            )
        )
        if stop_touched and exit_wanted and exit_sched == "immediate":
            # §5.9 same-bar Stop+Exit collision — only when the exit ALSO fills this bar
            # (immediate timing). A deferred exit would fill strictly later, so an intrabar
            # stop simply wins (the "stop" arm below). Only "exit_has_priority" changes the
            # OUTCOME (close at close as an exit); the other three execute the stop.
            return _HeldDecision(
                branch="stop_exit_collision",
                stop_outcome=stop_outcome,
                executed_reason=(
                    "exit_signal" if stop_exit_conflict == "exit_has_priority" else "stop_loss"
                ),
            )
        if stop_touched:
            return _HeldDecision(branch="stop", stop_outcome=stop_outcome)
        if exit_touch is not None and led.bars_seen > exit_touch[1]:
            # F-07i (C) ``intrabar_touch`` EXIT: the resting exit fills when price comes back
            # to TOUCH the exit-signal level (a long SELLS at the level — prints at/above it;
            # short mirror). Print-authoritative on a bar with prints; a print-less bar keeps
            # the coarse bar-extreme touch. Never on the signal bar itself (the level IS that
            # bar's close — an instant self-touch would just be a close fill). An intrabar
            # stop the same bar wins above (the risk event pre-empts the resting exit, the
            # deferred-exit precedent). The arm is taken whether or not price touched — that
            # is what the former ``elif`` did — so ``touched`` carries the answer.
            touch_level, _placed_seq = exit_touch
            is_long_pos = position.direction == "long"
            if bar_ticks:
                touched = bool(_touching_ticks(bar_ticks, touch_level, is_buy=not is_long_pos))
            else:
                touched = bar.high >= touch_level if is_long_pos else bar.low <= touch_level
            return _HeldDecision(branch="touch_exit", touch_level=touch_level, touched=touched)
        if exit_wanted:
            return _HeldDecision(branch="exit")
        return _HeldDecision(branch="none")

    def _apply_held(bar: _Bar, decision: _HeldDecision) -> None:
        """P3 BOOKED — execute the arm :func:`_evaluate_held` named. Decides nothing."""
        nonlocal exit_touch, pending, position

        assert position is not None  # a decision exists only for a held position
        if decision.branch == "stop_exit_collision":
            stop_outcome = decision.stop_outcome
            executed_reason = decision.executed_reason
            # F-10: the CONFLICT decision is ALWAYS traced (was only under
            # record_both_reasons) — which rule executed, which also triggered, and
            # the governing policy — so a reviewer can reconstruct the tie-break.
            led.stop_exit_collisions += 1
            _emit(
                "stop_exit_collision",
                event_time=bar.timestamp,
                direction=position.direction,
                bar_seq=led.bars_seen,
                detail={
                    "position_seq": position.position_seq,
                    "executed": executed_reason,
                    "also_triggered": (
                        "stop_loss" if executed_reason == "exit_signal" else "exit_signal"
                    ),
                    "policy": stop_exit_conflict,
                },
            )
            if stop_exit_conflict == "exit_has_priority":
                _close(bar.timestamp, bar.close, "exit_signal", position, bar_seq=led.bars_seen)
            else:
                assert stop_outcome is not None  # implied by the collision arm
                _close(
                    bar.timestamp,
                    stop_outcome.price,
                    "stop_loss",
                    position,
                    bar_seq=led.bars_seen,
                )
                _emit_stop_resolution(stop_outcome, bar.timestamp, position.direction)
            position = None
        elif decision.branch == "stop":
            # An intrabar stop fires immediately and subsumes any deferred exit
            # scheduled for later this bar (or a later bar) — the stop is hit first.
            stop_outcome = decision.stop_outcome
            assert stop_outcome is not None  # implied by the stop arm
            _close(
                bar.timestamp,
                stop_outcome.price,
                "stop_loss",
                position,
                bar_seq=led.bars_seen,
            )
            _emit_stop_resolution(stop_outcome, bar.timestamp, position.direction)
            position = None
            pending = None
        elif decision.branch == "touch_exit":
            touch_level = decision.touch_level
            assert touch_level is not None  # the touch arm always names its level
            if decision.touched:
                led.touch_exit_fills += 1
                if _close(
                    bar.timestamp,
                    touch_level,
                    "exit_signal",
                    position,
                    bar_seq=led.bars_seen,
                    fraction=close_fraction,
                ):
                    position = None
                else:
                    _apply_partial_aftermath(position, touch_level)
                exit_touch = None
        elif decision.branch == "exit":
            if exit_sched == "immediate":
                # F-07c: an exit signal closes ``close_fraction`` and holds the
                # remainder under the aftermath; a full close (fraction 1) nulls it.
                if _close(
                    bar.timestamp,
                    bar.close,
                    "exit_signal",
                    position,
                    bar_seq=led.bars_seen,
                    fraction=close_fraction,
                ):
                    position = None
                else:
                    _apply_partial_aftermath(position, bar.close)
            elif exit_sched == "touch":
                # F-07i (C): rest the exit as a TOUCH order at the signal bar's
                # close level; it fills only when a later bar's prints (or, on a
                # print-less bar, its extreme) come back to the level — resolved
                # by the touch branch above. Protection stops stay live on the
                # position throughout (the touch exit is opportunity, the stop is
                # risk).
                _emit(
                    "exit_scheduled",
                    event_time=bar.timestamp,
                    direction=position.direction,
                    bar_seq=led.bars_seen,
                    detail={
                        "position_seq": position.position_seq,
                        "reason": "exit_signal",
                        "timing": config.data.execution.exit_timing,
                        "touch_level": str(bar.close),
                    },
                )
                exit_touch = (bar.close, led.bars_seen)
            else:
                # Defer the exit to the next bar's open / close (F-07a); trace the
                # scheduling decision so the two-phase timing is reconstructable.
                _emit(
                    "exit_scheduled",
                    event_time=bar.timestamp,
                    direction=position.direction,
                    bar_seq=led.bars_seen,
                    detail={
                        "position_seq": position.position_seq,
                        "reason": "exit_signal",
                        "timing": config.data.execution.exit_timing,
                        "target_bar_seq": led.bars_seen + 1,
                    },
                )
                pending = _Pending(
                    "exit", exit_sched == "next_open", led.bars_seen + 1, "", "exit_signal"
                )

    def _phase_entry(bar: _Bar, *, equity: Decimal | None = None) -> None:
        """P4 / step (5) — flat and uncommitted: evaluate and place a fresh entry.

        The former ``elif`` arm. Reached only when :func:`_phase_held` did not take its
        branch, so the condition below is evaluated in exactly the state it used to be.

        ``equity`` is the valuation the entry is sized against and is scoped to the BOOKING
        half, which is the only half that sizes anything (``_planned_size`` is the lone
        reader). Evaluation never consults it, so describing an entry costs nothing and
        commits nothing."""
        decision = _evaluate_entry(bar)
        if decision is not None:
            _apply_entry(bar, decision, equity=equity)

    def _evaluate_entry(bar: _Bar) -> _EntryDecision | None:
        """P4 DESCRIBED — the entry this bar wants, placed nowhere and sized nowhere.

        Read-only, and that is the point of the split: every counter the pre-split code
        bumped while it was still deciding (``suppressed_entries``,
        ``entries_blocked_by_restriction``, ``strength_adjustments``) now travels in
        ``effects`` for :func:`_apply_entry` to book, so a pool may hear this answer and
        refuse it without having moved the item's ledger (ADR-0002 §6).

        ``None`` means the item is not open for a fresh entry at all — holding, already
        committed, or a fail-closed backstop is down."""
        if not (
            timing_ok
            and order_ok
            and partial_close_ok
            and scaling_ok
            and restrictions_ok
            and conflict_ok
            and pending is None
            and working_limit is None
            and working_stop is None
        ):
            # Flat and uncommitted is the precondition. ``timing_ok``, ``order_ok``,
            # ``partial_close_ok``, ``scaling_ok``, ``restrictions_ok`` and ``conflict_ok``
            # are the fail-closed backstops — an unsupported timing / order type /
            # partial-close aftermath / scaling config / restriction filter / hedge policy
            # opens nothing (F-07a / F-07b / F-07c / F-07d / F-07e).
            return None
        effects: list[_LedgerEffect] = []
        want: str | None = None
        if plan_active:
            # (6a) real indicator entry, respecting the direction bias.
            if entry_signal is not None:
                if (entry_signal == "long" and not long_ok) or (
                    entry_signal == "short" and not short_ok
                ):
                    effects.append(
                        _LedgerEffect(
                            counter="suppressed_entries",
                            event="filtered_no_entry",
                            direction=entry_signal,
                            detail={
                                "reason": "direction_restriction",
                                "direction_mode": config.position_entry_logic.direction_mode,
                            },
                        )
                    )
                else:
                    want = entry_signal
        elif len(window) == _BREAKOUT_WINDOW:
            # (6b) breakout entry proxy, with a full look-back.
            highest = max(b.high for b in window)
            lowest = min(b.low for b in window)
            want_long = bar.close > highest
            want_short = bar.close < lowest
            if (want_long and not long_ok) or (want_short and not short_ok):
                effects.append(
                    _LedgerEffect(
                        counter="suppressed_entries",
                        event="filtered_no_entry",
                        direction="long" if want_long else "short",
                        detail={
                            "reason": "direction_restriction",
                            "direction_mode": config.position_entry_logic.direction_mode,
                        },
                    )
                )
            elif want_long or want_short:
                # long wins a same-bar tie (deterministic); sides are exclusive.
                want = "long" if want_long else "short"
        if want is not None and restriction_specs:
            # F-07e: the Restrictions/Filters ENTRY gate (Master Ref §12.1 "block
            # entry"). Evaluated AFTER the signal + direction bias produced a wanted
            # entry, so the trace shows a real signal the filters vetoed — never a
            # phantom suppression. The gate runs at DECISION time (the signal bar);
            # a deferred/limit fill inherits its signal bar's verdict (V1 boundary,
            # engine-version-pinned).
            active_filters = _active_restrictions(bar_date)
            if _restrictions_block(active_filters):
                effects.append(
                    _LedgerEffect(
                        counter="entries_blocked_by_restriction",
                        event="filtered_no_entry",
                        direction=want,
                        detail={
                            "reason": "restriction_blocked",
                            "rule": restriction_rule,
                            "active_filters": active_filters,
                            "context": "flat_entry",
                        },
                    )
                )
                want = None
        if want is None:
            return _EntryDecision(want=None, strength=_ONE, effects=tuple(effects))
        # F-07g: the SIGNAL bar's strength multiplier, computed once at the decision
        # point (after the restriction gate — a vetoed signal never computes strength)
        # and inherited verbatim by whichever fill path executes (immediate / deferred /
        # limit) — never re-priced later.
        strength = _strength_value(bar)
        if strength != _ONE:
            effects.append(_LedgerEffect(counter="strength_adjustments"))
        entry_detail: dict[str, Any] = {"rule": _entry_rule_snapshot(want)}
        if strength_active:
            entry_detail["signal_strength"] = {
                "mode": strength_mode,
                "multiplier": str(strength),
            }
        return _EntryDecision(
            want=want, strength=strength, effects=tuple(effects), entry_detail=entry_detail
        )

    def _apply_entry(
        bar: _Bar,
        decision: _EntryDecision,
        *,
        equity: Decimal | None = None,
        size_override: Decimal | None = None,
    ) -> None:
        """P4 BOOKED — place what :func:`_evaluate_entry` described. Decides nothing.

        ``equity`` is scoped to THIS call: set on the way in, cleared on the way out, so a
        later phase can never size against a snapshot that has since been superseded.
        ``None`` — what ``_step`` passes — leaves the sizing chain reading this item's own
        ledger, unchanged.

        ``size_override`` is the size an OUTER authority granted, and reaches ``_open``'s
        existing parameter unchanged — ``_open`` takes ``min(planned, override)``, so the
        override can only ever narrow. It exists for ADR-0002 §6 clause 6: arbitration caps,
        and an item that booked ``intent.desired_size`` instead of the granted figure would
        have re-decided what the pool already decided. ``None`` — what ``_step`` and every
        non-immediate branch pass — is byte-identical to the pre-parameter behaviour."""
        nonlocal pending, position, sizing_equity, working_limit, working_stop

        sizing_equity = equity
        try:
            _book_effects(bar, decision.effects)
            want = decision.want
            if want is None:
                return
            strength = decision.strength
            # F-10: the entry DECISION (signal fired + bias allowed), carrying the
            # evaluated rule id(s) and each nested condition's pass/fail — distinct
            # from the ``entry_fill`` execution event (doc 15 §16).
            _emit(
                "entry_signal",
                event_time=bar.timestamp,
                direction=want,
                bar_seq=led.bars_seen,
                detail=decision.entry_detail,
            )
            if order_is_limit:
                # F-07b: rest a limit order at the signal-derived price; it fills
                # only on a later touch within the validity window (resolved by the
                # (3b) block on subsequent bars), never on this signal bar.
                limit = order_cfg.limit
                assert limit is not None  # guaranteed by order_ok
                offset = limit.price_offset or _ZERO
                limit_level = _limit_price(limit.price_rule, bar.close, offset)
                validity_bars = _VALIDITY_BARS[limit.validity]
                working_limit = _WorkingLimit(
                    direction=want,
                    limit_price=limit_level,
                    offset=offset,
                    price_rule=limit.price_rule,
                    unfilled_policy=limit.unfilled_policy,
                    expires_seq=(None if validity_bars is None else led.bars_seen + validity_bars),
                    strength=strength,
                )
                led.limit_orders_placed += 1
                _emit(
                    "limit_order_placed",
                    event_time=bar.timestamp,
                    direction=want,
                    bar_seq=led.bars_seen,
                    detail={
                        "limit_price": str(limit_level),
                        "price_rule": limit.price_rule,
                        "validity": limit.validity,
                        "unfilled_policy": limit.unfilled_policy,
                        "expires_bar_seq": working_limit.expires_seq,
                    },
                )
            elif order_is_stop:
                # F-07h: rest a stop trigger at the signal-derived level; it fires
                # only on a later touch (resolved by the (1c) block on subsequent
                # bars), never on this signal bar. For a stop-limit the limit leg
                # is pre-computed HERE from the same signal close, so the armed
                # limit is signal-derived exactly like a plain limit order's.
                stop = order_cfg.stop
                assert stop is not None  # guaranteed by order_ok
                trigger_level = _limit_price(
                    stop.activation_rule, bar.close, stop.trigger_offset or _ZERO
                )
                limit = order_cfg.limit  # present iff stop_limit_order
                limit_offset = (limit.price_offset or _ZERO) if limit else _ZERO
                place_detail: dict[str, Any] = {
                    "trigger_price": str(trigger_level),
                    "activation_rule": stop.activation_rule,
                    "order_type": order_cfg.type,
                }
                stop_limit_level: Decimal | None = None
                if limit is not None:
                    stop_limit_level = _limit_price(limit.price_rule, bar.close, limit_offset)
                    place_detail["limit_price"] = str(stop_limit_level)
                    place_detail["validity"] = limit.validity
                    place_detail["unfilled_policy"] = limit.unfilled_policy
                working_stop = _WorkingStop(
                    direction=want,
                    trigger_price=trigger_level,
                    limit_price=stop_limit_level,
                    limit_offset=limit_offset,
                    limit_rule=limit.price_rule if limit else "",
                    unfilled_policy=limit.unfilled_policy if limit else "",
                    validity_bars=(_VALIDITY_BARS[limit.validity] if limit else None),
                    strength=strength,
                )
                led.stop_orders_placed += 1
                _emit(
                    "stop_order_placed",
                    event_time=bar.timestamp,
                    direction=want,
                    bar_seq=led.bars_seen,
                    detail=place_detail,
                )
            elif entry_sched == "touch":
                # F-07i (C) ``intrabar_touch`` ENTRY: rest a TOUCH order at the
                # signal price (the signal bar's close) and fill only when a
                # later bar's prints come back to the level — reusing the F-07b
                # working-limit machinery verbatim (entry-signal-price rule, no
                # offset, until-cancelled). With a limit/stop order type the
                # branches above already govern the fill (the order's own touch
                # semantics subsume the timing).
                working_limit = _WorkingLimit(
                    direction=want,
                    limit_price=bar.close,
                    offset=_ZERO,
                    price_rule="entry_signal_price",
                    unfilled_policy="keep_until_validity_ends",
                    expires_seq=None,
                    strength=strength,
                )
                led.touch_orders_placed += 1
                _emit(
                    "limit_order_placed",
                    event_time=bar.timestamp,
                    direction=want,
                    bar_seq=led.bars_seen,
                    detail={
                        "limit_price": str(bar.close),
                        "price_rule": "entry_signal_price",
                        "mode": "intrabar_touch",
                        "unfilled_policy": "keep_until_validity_ends",
                        "expires_bar_seq": None,
                    },
                )
            elif entry_sched == "immediate":
                position = _do_open(
                    want,
                    bar,
                    bar.close,
                    bar_seq=led.bars_seen,
                    deferred=False,
                    strength=strength,
                    size_override=size_override,
                )
            else:
                _emit(
                    "entry_scheduled",
                    event_time=bar.timestamp,
                    direction=want,
                    bar_seq=led.bars_seen,
                    detail={
                        "timing": config.data.execution.entry_timing,
                        "target_bar_seq": led.bars_seen + 1,
                    },
                )
                pending = _Pending(
                    "entry",
                    entry_sched == "next_open",
                    led.bars_seen + 1,
                    want,
                    "",
                    strength,
                )
        finally:
            sizing_equity = None

    def _phase_tail(bar: _Bar) -> None:
        """Steps (3d)/(6)/(7)/(8) — the close-deferred fill, the stacking and opposite-signal
        rules, the scale ladder and the end-of-bar snapshot."""
        nonlocal exit_touch, pending, position, prev_entry_signal, prev_scale_signal

        # (3d) Resolve a fill deferred to THIS bar's CLOSE (next_candle_close). Runs at
        # end-of-bar so an intrabar stop (above) pre-empts a scheduled close exit, and
        # so a pending set THIS bar (target bars_seen+1) is never resolved early.
        if pending is not None and pending.target_seq == led.bars_seen and not pending.at_open:
            if pending.kind == "entry" and position is None:
                led.deferred_entry_fills += 1
                position = _do_open(
                    pending.direction,
                    bar,
                    bar.close,
                    bar_seq=led.bars_seen,
                    deferred=True,
                    strength=pending.strength,
                )
            elif pending.kind == "exit" and position is not None:
                led.deferred_exit_fills += 1
                # F-07c: a deferred exit SIGNAL at the close closes ``close_fraction`` and
                # holds the remainder under the aftermath (a full close nulls the position).
                if _close(
                    bar.timestamp,
                    bar.close,
                    pending.reason,
                    position,
                    bar_seq=led.bars_seen,
                    fraction=close_fraction,
                ):
                    position = None
                else:
                    _apply_partial_aftermath(position, bar.close)
            pending = None

        # (5) F-07e conflict / position handling — a NEW aggregated entry-signal EDGE
        # while a position is OPEN (Master Ref §13; plan mode only — the breakout proxy
        # computes no signals while a position is held, so it stays byte-identical).
        # Runs AFTER the bar's exit/stop resolution so a risk event always dominates
        # (§13 priority order: exit/stop before entry candidates): a bar that closed or
        # reduced the position (``trades_before_bar``) or committed an exit (``pending``)
        # never also stacks/replaces it. The EDGE guard (``prev_entry_signal``) makes a
        # HELD signal one entry event — never a per-bar stack/replace/churn storm.
        # An opposite signal only reaches here when exit-on-opposite left the position
        # open (otherwise it already closed above); ``allow_hedge`` in that state is
        # unreachable — the ``conflict_ok`` fail-closed gate opened no position at all.
        if (
            position is not None
            # The signal edge that OPENED the position this bar (flat entry, deferred
            # fill or limit touch) is one entry event — it must never also stack /
            # replace / close its own position on the same bar.
            and position.entry_bar_seq != led.bars_seen
            and plan_active
            and pending is None
            and len(led.trades) == trades_before_bar
            and entry_signal is not None
            and entry_signal != prev_entry_signal
        ):
            if entry_signal == position.direction:
                if stacking_policy == "ignore":
                    led.conflict_signals_ignored += 1
                    _emit(
                        "filtered_no_entry",
                        event_time=bar.timestamp,
                        direction=entry_signal,
                        bar_seq=led.bars_seen,
                        detail={
                            "reason": "stacking_ignored",
                            "policy": stacking_policy,
                            "position_seq": position.position_seq,
                        },
                    )
                elif stacking_policy == "scale_existing":
                    # The repeated signal itself adds nothing — position growth is
                    # DELEGATED to the scaling ladder (§13 "only if scaling allows");
                    # with scaling disabled the signal is a traced no-op.
                    led.conflict_signals_ignored += 1
                    _emit(
                        "filtered_no_entry",
                        event_time=bar.timestamp,
                        direction=entry_signal,
                        bar_seq=led.bars_seen,
                        detail={
                            "reason": "stacking_scale_only",
                            "policy": stacking_policy,
                            "scaling_enabled": scaling_active,
                            "position_seq": position.position_seq,
                        },
                    )
                else:
                    # allow_stacking / replace_existing EXECUTE a new entry — the same
                    # Restrictions/Filters gate that vets a flat entry vets it (§12.1
                    # "block entry" is entry-scoped, not flat-scoped).
                    conflict_active = _active_restrictions(bar_date) if restriction_specs else []
                    if _restrictions_block(conflict_active):
                        led.entries_blocked_by_restriction += 1
                        _emit(
                            "filtered_no_entry",
                            event_time=bar.timestamp,
                            direction=entry_signal,
                            bar_seq=led.bars_seen,
                            detail={
                                "reason": "restriction_blocked",
                                "rule": restriction_rule,
                                "active_filters": conflict_active,
                                "context": "conflict_entry",
                            },
                        )
                    elif stacking_policy == "replace_existing":
                        # Close the held position and re-enter fresh at the decision
                        # bar's close (the deterministic decision point — the scale-
                        # layer fill precedent; the F-07a deferral remains the FLAT
                        # entry's contract). The close emits ``position_close`` with
                        # the "replaced_by_signal" reason; the re-open emits its own
                        # ``entry_signal`` + ``entry_fill`` so the F-10 chain stays
                        # complete.
                        replaced_seq = position.position_seq
                        led.positions_replaced += 1
                        # F-07g: the conflict entry is a SIGNAL entry — it gets its
                        # own decision bar's strength multiplier, exactly like a
                        # flat entry.
                        conflict_strength = _signal_strength(bar)
                        replace_detail: dict[str, Any] = {
                            "rule": _entry_rule_snapshot(entry_signal),
                            "conflict": "replace_existing",
                            "replaced_position_seq": replaced_seq,
                        }
                        if strength_active:
                            replace_detail["signal_strength"] = {
                                "mode": strength_mode,
                                "multiplier": str(conflict_strength),
                            }
                        _emit(
                            "entry_signal",
                            event_time=bar.timestamp,
                            direction=entry_signal,
                            bar_seq=led.bars_seen,
                            detail=replace_detail,
                        )
                        _close(
                            bar.timestamp,
                            bar.close,
                            "replaced_by_signal",
                            position,
                            bar_seq=led.bars_seen,
                        )
                        position = _do_open(
                            entry_signal,
                            bar,
                            bar.close,
                            bar_seq=led.bars_seen,
                            deferred=False,
                            strength=conflict_strength,
                        )
                    else:  # allow_stacking — fold a signal-driven tranche into the position
                        stack_eff = _effective_fill(
                            bar.close,
                            is_buy=position.direction == "long",
                            half_spread=half_spread,
                            slip=slippage,
                        )
                        # F-07g: a stack tranche is a SIGNAL entry — its size gets its
                        # own decision bar's strength multiplier (the traced
                        # ``stack_size`` reflects it).
                        stack_strength = _signal_strength(bar)
                        if alloc_on:
                            sleeve = _sleeve_capital(led.equity)
                            tranche = _cap_to_sleeve(
                                _position_size(config, stack_eff, sleeve, stack_strength),
                                sleeve,
                                stack_eff,
                            )
                        else:
                            tranche = _position_size(config, stack_eff, led.equity, stack_strength)
                        stacked_size = position.size + tranche
                        # GH #550: the configured cap is a PERCENT of resolved capital, so
                        # it is converted at THIS tranche's price (and against the sleeve
                        # when allocation is on, which is the capital the tranche itself
                        # was sized against) before it can be compared with a quantity.
                        stack_size_cap = max_position_size_cap(
                            config,
                            stack_eff,
                            _sleeve_capital(led.equity) if alloc_on else led.equity,
                        )
                        stack_reject: str | None = None
                        stack_cap: str | None = None
                        if tranche <= _ZERO:
                            stack_reject = "stack_size_not_positive"
                        elif stack_size_cap is not None and stacked_size > stack_size_cap:
                            stack_reject = "position_size_limit"
                            stack_cap = str(stack_size_cap)
                        elif alloc_on:
                            sleeve_remaining = _sleeve_capital(led.equity) - position.entry_notional
                            if (stack_eff * tranche) > sleeve_remaining:
                                stack_reject = "sleeve_capacity"
                                stack_cap = str(max(sleeve_remaining, _ZERO).quantize(_MONEY))
                        if (
                            stack_reject is None
                            and rules_active
                            and portfolio_cap_amount is not None
                        ):
                            # Composition-wide cap on the ADD: prior items' concurrent
                            # notional + this position's own. An over-cap tranche is
                            # REJECTED, never auto-trimmed (the §11.4 acceptance rule).
                            headroom = (
                                portfolio_cap_amount
                                - _prior_exposure_at(_bar_epoch_ms(bar.timestamp))
                                - position.entry_notional
                            )
                            if (stack_eff * tranche) > headroom:
                                stack_reject = "portfolio_max_total_exposure"
                                stack_cap = str(max(headroom, _ZERO).quantize(_MONEY))
                        if stack_reject is not None:
                            led.stack_entries_rejected += 1
                            _emit(
                                "stack_entry_rejected",
                                event_time=bar.timestamp,
                                direction=position.direction,
                                bar_seq=led.bars_seen,
                                detail={
                                    "position_seq": position.position_seq,
                                    "reason": stack_reject,
                                    "cap": stack_cap,
                                    "candidate_size": str(tranche),
                                    "policy": stacking_policy,
                                },
                            )
                        else:
                            # One lifecycle, one trade-per-lot accounting: the tranche
                            # folds into a size-weighted average basis exactly like a
                            # scale layer; stop LEVELS stay as installed at entry and
                            # the ladder's own reference/caps are untouched (a stack is
                            # a SIGNAL entry, not a ladder layer). The tranche's fill
                            # pays one commission now — the close still books one round
                            # trip.
                            new_basis = (
                                (position.entry_price * position.size + stack_eff * tranche)
                                / stacked_size
                            ).quantize(_MONEY)
                            position.entry_price = new_basis
                            position.size = stacked_size
                            position.entry_notional = (new_basis * stacked_size).quantize(_MONEY)
                            position.peak_notional = max(
                                position.peak_notional, position.entry_notional
                            )
                            led.stack_entries_added += 1
                            if commission > _ZERO:
                                led.equity = (led.equity - commission).quantize(_MONEY)
                            _emit(
                                "stack_entry_added",
                                event_time=bar.timestamp,
                                direction=position.direction,
                                bar_seq=led.bars_seen,
                                detail={
                                    "position_seq": position.position_seq,
                                    "fill_price": str(stack_eff),
                                    "stack_size": str(tranche),
                                    "new_size": str(stacked_size),
                                    "entry_basis": str(new_basis),
                                    "exposure": str(position.entry_notional),
                                    "policy": stacking_policy,
                                },
                            )
            elif hedge_policy == "close_existing":
                # An opposite signal with exit-on-opposite OFF: the policy closes the
                # held position at the decision bar's close ("Close" §13 — the flat
                # rules take over from the next bar; no same-bar reverse).
                led.opposite_signal_closes += 1
                _close(bar.timestamp, bar.close, "opposite_signal", position, bar_seq=led.bars_seen)
                position = None
            elif hedge_policy == "ignore":
                led.conflict_signals_ignored += 1
                _emit(
                    "filtered_no_entry",
                    event_time=bar.timestamp,
                    direction=entry_signal,
                    bar_seq=led.bars_seen,
                    detail={
                        "reason": "hedge_ignored",
                        "policy": hedge_policy,
                        "position_seq": position.position_seq,
                    },
                )

        # (7) F-07d same-direction scaling — the price-distance ladder over the OPEN
        # position (Master Ref §11.3/§11.4). Runs AFTER every entry/exit/stop resolution
        # of the bar so it sees the position's final state: a bar that closed or reduced
        # the position (``trades_before_bar``) or committed an exit (``pending``) never
        # also scales it. One threshold cross = ONE candidate: crossing
        # ``retracement_distance``% ADVERSE from the reference (initial entry fill, then
        # each trigger close) creates the candidate and ADVANCES the reference whether or
        # not the candidate is accepted — bounded events (each further candidate needs a
        # further full step), no O(bars) re-trigger spam. The layer-count caps gate
        # candidate CREATION (an exhausted ladder generates nothing, §11.4); the
        # exposure/size caps gate ACCEPTANCE — an over-cap layer is REJECTED with a
        # ledger reason, never auto-trimmed (§11.4 exposure binding). An accepted layer
        # fills at the trigger bar's CLOSE (the deterministic decision point — the
        # F-07a deferral remains the initial entry's contract), pays one fill's
        # commission at fill time (the close still books the round trip), and folds into
        # the single position as a size-weighted average basis; stop LEVELS stay as
        # installed at entry.
        if (
            position is not None
            and scaling_active
            and pending is None
            and len(led.trades) == trades_before_bar
            and position.layers_filled < scale_max_layers
        ):
            # Captured BEFORE the cross advances it — the trace reports the
            # reference the candidate was measured from, not the new one.
            scale_ref = position.scale_reference
            scale_long = position.direction == "long"
            # S5c per-layer closed-bar gate (doc 02 §5.7), applied ONLY to the
            # LOGIC-BASED ladder. doc 02 §6.1's ⓘ panel is explicit and its reasoning is
            # mechanical, not incidental: "Price-Distance Based Scaling doğrudan fiyat
            # mesafesiyle tetiklendiğinden bu timeframe dizisini kullanmaz" — a price
            # comparison evaluates no indicator, so it has no candle to close on. The
            # sequence therefore governs which candle a logic-based SIGNAL is read from,
            # and the price-distance ladder below stays exactly as it was pre-S5c.
            # ``next_layer_tf`` is None under same_strategy, leaving even the logic
            # ladder ungated (every base bar is a decision point).
            next_layer_tf = (
                layer_timeframe(config, position.layers_filled) if scale_logic_mode else None
            )
            this_bucket = layer_bucket(_bar_epoch_ms(bar.timestamp), next_layer_tf)
            layer_bar_ready = next_layer_tf is None or (
                this_bucket is not None and this_bucket != position.scale_layer_bucket
            )
            if scale_logic_mode:
                # The logic ladder proposes a layer when the resolved scaling blocks
                # aggregate to a signal in the POSITION'S OWN direction (§5.7's
                # same-direction-only canonical rule — an opposite signal is never
                # scaling; it is resolved by the §9 conflict rules). An EDGE is
                # required, mirroring the F-07e conflict detector: a signal that simply
                # stays true must not add a layer on every subsequent bar.
                scale_fires = (
                    layer_bar_ready
                    and scale_signal == position.direction
                    and prev_scale_signal != position.direction
                )
            else:
                scale_fires = scale_threshold_crossed(
                    reference=scale_ref,
                    distance_pct=scale_distance,
                    close=bar.close,
                    is_long=scale_long,
                )
            if scale_fires:
                position.scale_reference = bar.close  # the ladder steps from this trigger
                # S5c: this candle has now been SPENT on a decision, accepted or not —
                # advance the gate anchor so a gated logic ladder makes at most one
                # decision per layer-timeframe candle. Under same_strategy (and on the
                # whole price-distance path) ``this_bucket`` is None, which restores the
                # pre-S5c inert anchor exactly.
                position.scale_layer_bucket = this_bucket
                layer_size = resolve_scale_layer_size(
                    basis=scale_add_basis,
                    value=scale_add_value,
                    initial_size=position.initial_size,
                    current_size=position.size,
                )
                layer_eff = _effective_fill(
                    bar.close, is_buy=scale_long, half_spread=half_spread, slip=slippage
                )
                scaled_size = position.size + layer_size
                # The composition-wide cap is a MONEY basis, distinct from the
                # per-strategy size-units "max_total_exposure"; both bind here and
                # the precedence order decides which name reaches the ledger.
                # GH #550: the §6 cap is a PERCENT, converted at this layer's price (and
                # against the sleeve under allocation) so the ladder binds it exactly
                # where the entry sizing chain did.
                reject_reason, reject_cap = resolve_scale_rejection(
                    layer_size=layer_size,
                    layer_notional=layer_eff * layer_size,
                    scaled_size=scaled_size,
                    max_total_size=scale_max_total,
                    max_position_size=max_position_size_cap(
                        config, layer_eff, _sleeve_capital(led.equity) if alloc_on else led.equity
                    ),
                    sleeve_remaining=(
                        _sleeve_capital(led.equity) - position.entry_notional if alloc_on else None
                    ),
                    portfolio_headroom=(
                        portfolio_cap_amount
                        - _prior_exposure_at(_bar_epoch_ms(bar.timestamp))
                        - position.entry_notional
                        if rules_active and portfolio_cap_amount is not None
                        else None
                    ),
                )
                if reject_reason is not None:
                    led.scale_layers_rejected += 1
                    _emit(
                        "scale_layer_rejected",
                        event_time=bar.timestamp,
                        direction=position.direction,
                        bar_seq=led.bars_seen,
                        detail={
                            "position_seq": position.position_seq,
                            "reason": reject_reason,
                            "cap": reject_cap,
                            "reference": str(scale_ref),
                            "candidate_size": str(layer_size),
                            "layers_filled": position.layers_filled,
                        },
                    )
                else:
                    new_basis = (
                        (position.entry_price * position.size + layer_eff * layer_size)
                        / scaled_size
                    ).quantize(_MONEY)
                    position.entry_price = new_basis
                    position.size = scaled_size
                    position.entry_notional = (new_basis * scaled_size).quantize(_MONEY)
                    position.peak_notional = max(position.peak_notional, position.entry_notional)
                    position.layers_filled += 1
                    # S5c: the NEXT layer has its own timeframe, so the gate must be
                    # re-anchored in that timeframe's buckets — not left in the one the
                    # layer just filled used. Re-anchoring to THIS bar means the next
                    # layer waits for a full candle of its own (coarser) timeframe.
                    position.scale_layer_bucket = layer_bucket(
                        _bar_epoch_ms(bar.timestamp),
                        layer_timeframe(config, position.layers_filled),
                    )
                    led.scale_layers_added += 1
                    if commission > _ZERO:
                        # The layer's own entry fill pays its commission NOW; the close
                        # still books one round trip (initial entry + exit) — N layers
                        # pay exactly N extra fills, no double counting.
                        led.equity = (led.equity - commission).quantize(_MONEY)
                    _emit(
                        "scale_layer_added",
                        event_time=bar.timestamp,
                        direction=position.direction,
                        bar_seq=led.bars_seen,
                        detail={
                            "position_seq": position.position_seq,
                            "layer_seq": position.layers_filled,
                            "reference": str(scale_ref),
                            "fill_price": str(layer_eff),
                            "layer_size": str(layer_size),
                            "new_size": str(scaled_size),
                            "entry_basis": str(new_basis),
                            "exposure": str(position.entry_notional),
                            "method": (
                                "logic_based_scaling"
                                if scale_logic_mode
                                else "price_distance_scaling"
                            ),
                            # S5c: which timeframe's closed candle authorized this
                            # layer. None under same_strategy and on the whole
                            # price-distance path (both ungated) — the trace states the
                            # ladder's structure, it never implies one.
                            "layer_timeframe": next_layer_tf,
                        },
                    )

        # (8) doc 15 §9.3 step 8 — state snapshot + decision-trace tail.
        # F-07e: the conflict EDGE detector's memory — this bar's aggregated signal is
        # the next bar's "previous" (None in proxy mode, so the detector stays inert).
        prev_entry_signal = entry_signal
        # S5c: this bar's scaling proposal becomes the next bar's "previous" so the
        # ladder fires on the signal's EDGE, not on every bar it stays true.
        prev_scale_signal = scale_signal

        # F-07i (C): a resting touch exit dies with its position — whatever closed it
        # (stop / deferred exit / the touch itself) consumed the exit intent; a later
        # position never inherits a stale touch level.
        if position is None:
            exit_touch = None

        window.append(bar)

    def _step(bar: _Bar) -> None:
        """Replay ONE bar as the ordered phases of doc 15 §9.3, unchanged in order or effect.

        The phases were the numbered sections of the former single-body step and are now
        separately callable, because a participant driven by a MERGED clock (ADR-0002 §8) has
        to ask one item what it is charged, what it must close and what it wants at three
        different points of a shared tick — not run a whole bar in one call. Driving them in
        this order from here is byte-identical to the former body: the same statements in the
        same sequence over the same state."""
        _phase_admit(bar)
        _phase_carry(bar)
        _phase_open_fills(bar)
        if not _phase_held(bar):
            _phase_entry(bar)
        _phase_tail(bar)

    def _finalize() -> None:
        """End-of-data settlement — the former tail of ``run_engine``, unchanged."""
        nonlocal position, working_limit, working_stop

        # End-of-data: a limit order still resting past the last bar never filled → cancel it
        # (F-07b), so an unfilled limit is an auditable no-fill, never a silent gap.
        if working_limit is not None and led.last_bar is not None:
            led.limit_orders_cancelled += 1
            _emit(
                "limit_order_cancelled",
                event_time=led.last_bar.timestamp,
                direction=working_limit.direction,
                bar_seq=led.bars_seen,
                detail={
                    "reason": "end_of_data",
                    "unfilled_policy": working_limit.unfilled_policy,
                    "limit_price": str(working_limit.limit_price),
                },
            )
            working_limit = None

        # End-of-data: a stop trigger still resting past the last bar never fired → cancel it
        # (F-07h), so an unfired stop is an auditable no-fill, never a silent gap.
        if working_stop is not None and led.last_bar is not None:
            led.stop_orders_cancelled += 1
            _emit(
                "stop_order_cancelled",
                event_time=led.last_bar.timestamp,
                direction=working_stop.direction,
                bar_seq=led.bars_seen,
                detail={
                    "reason": "end_of_data",
                    "trigger_price": str(working_stop.trigger_price),
                    "order_type": order_cfg.type,
                },
            )
            working_stop = None

        # End-of-data: close any open position at the last bar's close (never left dangling).
        if position is not None and led.last_bar is not None:
            _close(
                led.last_bar.timestamp,
                led.last_bar.close,
                "end_of_data",
                position,
                bar_seq=led.bars_seen,
            )
            position = None

    def _output() -> EngineOutput:
        """The run's result, assembled from the state the steps accumulated."""
        # K-11b: the output assembly is a pure projection of (ctx, led) — no bar is replayed
        # here. ``warnings`` is threaded into the diagnostics block because the Result carries
        # it under a diagnostics key, not as a field of its own.
        summary = build_summary(ctx, led)
        warnings = build_warnings(ctx, led)
        diagnostics = build_diagnostics(ctx, led, warnings)
        return EngineOutput(
            summary=summary,
            trades=led.trades,
            equity_points=led.equity_points,
            signal_events=led.signal_events,
            diagnostics=diagnostics,
            position_intervals=led.position_intervals,
            filtered_events=led.filtered_events,
        )

    def _open_position() -> _Position | None:
        return position

    return _ItemStepper(
        step=_step,
        finalize=_finalize,
        output=_output,
        open_position=_open_position,
        admit=_phase_admit,
        carry=_phase_carry,
        compute_carry=_compute_carry,
        book_carry=_book_carry,
        open_fills=_phase_open_fills,
        held=_phase_held,
        evaluate_held=_evaluate_held,
        apply_held=_apply_held,
        entry=_phase_entry,
        evaluate_entry=_evaluate_entry,
        apply_entry=_apply_entry,
        tail=_phase_tail,
        ledger=led,
        ctx=ctx,
    )


def run_engine(
    *,
    strategy_config: StrategyConfig,
    bar_batches: Iterator[list[dict[str, Any]]],
    execution_key: str,
    item_count: int = 1,
    indicator_plan: IndicatorPlan | None = None,
    timeframe: str | None = None,
    allocation: AllocationExecution | None = None,
    funding: FundingSchedule | None = None,
    tick_batches: Iterator[list[dict[str, Any]]] | None = None,
    portfolio_rules: PortfolioRules | None = None,
    builtin_breakout_fixture: bool = False,
) -> EngineOutput:
    """Deterministically bar-replay one strategy over its pinned OHLCV bars.

    Entry/exit timing uses real built-in indicator signals: the run REQUIRES an
    ``indicator_plan`` that resolves to at least one computable entry block. F-04 —
    FAIL CLOSED: with no such plan the engine raises ``UnresolvedStrategyError`` and
    materializes NOTHING, rather than fabricate metrics from a strategy the user never
    defined (production is also guarded at admission and in the worker). The historical
    deterministic breakout is available ONLY as an explicit test-only fixture: pass
    ``builtin_breakout_fixture=True`` to exercise the price/stop/cost/sizing machinery
    without a real indicator layer. That opt-in is the sole way to reach the proxy — it
    is never a production fallback.

    ``timeframe`` is the pinned market revision's base bar timeframe, resolved by
    the CALLER (the engine is pure — no I/O); ``None`` means the revision is not
    bar-timeframed (event-based / unknown) and is surfaced as-is, never guessed.

    ``allocation`` applies the pinned shared-pool capital model (doc 13 §8.3/§8.4): the
    run is capitalised from the portfolio pool P0 (minus the fixed nominal reserve R0),
    and every entry is bounded by the item's sleeve cap ``Ci(t) = A(t) * wi / 100`` as
    an OUTER ``allowed_size`` limit — compound mode recomputes A(t) from live portfolio
    equity each valuation point, fixed mode holds it at the initial A0. ``None`` (the
    default, independent mode) sizes from the strategy's own ``initial_capital`` and is
    BYTE-IDENTICAL to the pre-allocation engine. Honest V1 boundary: this is the
    single-item foundation — the replayed strategy is capitalised and capped as one
    portfolio sleeve; a genuine multi-item co-simulation over a unified clock across
    heterogeneous bar sources, and cross-currency FX conversion (GAP-16), stay
    deferred (surfaced as L4 diagnostics, never hidden).

    ``funding`` applies a pinned ``funding_rate`` Research revision as a real cost on the
    open position (F-11, doc 12 §8.4). It is an already-resolved, available-time-safe
    ``FundingSchedule`` (each record carries the first moment it could truly have been used —
    event time shifted by the revision's available-time policy). The engine consumes it with
    a backward/as-of join: a record fires at the first bar whose time is >= its
    ``available_at`` and, while a position is held, charges ``notional * rate`` (a long pays
    a positive rate, a short receives). A value dated after the last replayed bar can never
    fire, so future leakage is impossible by construction. ``None`` (the default) books no
    funding and is BYTE-IDENTICAL to the pre-F-11 engine.

    ``portfolio_rules`` applies the plan's PORTFOLIO-LEVEL rules (cross-item, doc 13
    §8.4): a composition-wide Max Total Exposure cap (percent of the pool P0, enforced
    against the prior-pinned items' held windows + this item's own open notional at
    every entry/stack/scale acceptance) and the opposing same-instrument conflict
    policy (BLOCK_OPPOSITE blocks this item's entry while an earlier-pinned item held
    the opposite direction on the same instrument; NET executes conservatively AS
    BLOCK_OPPOSITE — L4-disclosed, never silently netted). Enforcement is sequential
    in pin order (an earlier item is never re-simulated because of a later one — the
    honest V1 boundary, surfaced as an L4 warning). ``None`` (the default) is
    BYTE-IDENTICAL to the pre-rules engine.

    ``tick_batches`` injects the PINNED tick/trade revision's processed print stream
    (F-07i B) — the worker resolves it from the manifest pin ONLY when the strategy
    demands tick data (``tick_data_required``), mirroring the bar path (the engine stays
    pure — no I/O). The prints are aligned to per-bar windows via ``timeframe`` (an
    un-timeframed revision cannot be aligned — surfaced as a warning, L4, and the run
    stays on the conservative OHLCV model) and resolve the ``first_trigger_wins``
    stop-conflict order by TRUE first touch instead of the flagged conservative
    approximation. ``None`` (the default) is BYTE-IDENTICAL to the pre-F-07i engine."""
    stepper = _build_stepper(
        strategy_config=strategy_config,
        execution_key=execution_key,
        item_count=item_count,
        indicator_plan=indicator_plan,
        timeframe=timeframe,
        allocation=allocation,
        funding=funding,
        tick_batches=tick_batches,
        portfolio_rules=portfolio_rules,
        builtin_breakout_fixture=builtin_breakout_fixture,
    )
    for batch in bar_batches:
        for raw in batch:
            bar = _normalize(raw)
            if bar is None:
                continue
            stepper.step(bar)
    stepper.finalize()
    return stepper.output()


__all__ = [
    "DECISION_TRACE_EVENT_TYPES",
    "DECISION_TRACE_SCHEMA",
    "ENTRY_MODEL",
    "FILTERED_EVENT_TYPES",
    "UNMODELLED_DECISION_CLASSES",
    "AllocationExecution",
    "EngineOutput",
    "EquityPoint",
    "ItemRun",
    "PortfolioRules",
    "PriorItemInterval",
    "SignalEventRow",
    "TradeRow",
    "UnresolvedStrategyError",
    "conflict_handling_is_modelled",
    "execution_timing_is_modelled",
    "order_execution_is_modelled",
    "partial_close_is_modelled",
    "resolve_allocation_execution",
    "restrictions_are_modelled",
    "run_engine",
    "scaling_is_modelled",
    "tick_data_required",
]
