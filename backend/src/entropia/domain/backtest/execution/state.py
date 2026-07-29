"""Engine value types and the raw-row coercion boundary (K-09).

The normalized bar, the live position and the ``Decimal`` coercion helpers that turn
an untrusted OHLCV row into either a typed bar or ``None``. They sit in their own leaf
module so ``engine`` and ``execution.fills`` can both import them DOWNWARD — ``fills``
is called from inside ``run_engine``, so a shared type held in ``engine`` would close
an import cycle.

Moved verbatim from ``domain.backtest.engine``. The coercion contract is unchanged and
is fail-closed by design: a row missing a field, carrying a non-numeric price or a
non-finite value yields ``None`` and is DROPPED rather than guessed — an unavailable
detail is never imitated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.execution.constants import _ZERO
from entropia.domain.backtest.execution.costs import FillCosts
from entropia.domain.strategy.config import StrategyConfig


@dataclass(frozen=True, slots=True)
class _Bar:
    """One normalized OHLCV bar (canonical market-data field names, doc 11)."""

    timestamp: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(slots=True)
class _Position:
    # F-10: lifecycle id + entry bar index so every decision-trace event of this position
    # (entry_signal -> entry_fill -> ... -> position_close) links back to one lifecycle and
    # a reviewer can compute the holding span.
    position_seq: int
    entry_bar_seq: int
    direction: str  # "long" | "short"
    entry_time: str
    entry_price: Decimal  # cost-adjusted effective fill
    size: Decimal
    # F-08: per-rule stop levels kept SEPARATELY (was a single merged ``static_stop``)
    # so the combination engine can evaluate percentage / absolute / trailing / logic
    # stops as distinct rules for the Any/All requirement and priority resolution.
    pct_stop: Decimal | None  # percentage stop level (entry-relative, fixed)
    abs_stop: Decimal | None  # absolute-price stop level (fixed)
    trail_pct: Decimal | None
    trail_anchor: Decimal  # best price seen since entry (favourable extreme)
    entry_notional: Decimal
    # F-07f: trailing stop profit-lock ACTIVATION threshold, as a fraction of entry price
    # (Master Ref §9.2 "Activate After Profit %", TrailingStop.lock_in_percentage). ``None``
    # when trailing is not configured (mirrors ``trail_pct``); see ``_trailing_activated``.
    trail_lock_in_pct: Decimal | None = None
    # F-07d same-direction scaling state. ``entry_price``/``size`` become the size-weighted
    # AVERAGE basis / total across layers (the single-position invariant extends, it does not
    # break: one lifecycle, one trade-per-lot accounting); each layer's own fill price lives in
    # its ``scale_layer_added`` trace event. ``scale_reference`` is the RAW (pre-cost) price
    # the next price-distance threshold is measured from — the initial entry's fill, advancing
    # to each trigger bar's close (spec §11.3: reference = initial entry OR previous filled
    # layer; the ladder form). Stop LEVELS stay as installed at the initial entry (documented
    # "fixed for the position's life" invariant) — re-anchoring policies are out of scope.
    # Defaulted (inert unless the ladder runs) so stop-combination tests constructing a
    # position directly stay valid; ``_open`` always sets all three explicitly.
    initial_size: Decimal = _ZERO
    layers_filled: int = 0
    scale_reference: Decimal = _ZERO
    # S5c per-layer timeframe ladder (doc 02 §5.7 custom_sequence). The layer-timeframe
    # candle index that was current when the CURRENT layer slot opened — set at entry for
    # layer 1 and RE-ANCHORED (with the next layer's own timeframe) after each fill. A
    # candidate is a decision point only once the bar's bucket differs from this anchor,
    # i.e. a full layer-timeframe candle has closed since the last fill. ``None`` under
    # same_strategy: the ladder is ungated and every base bar is a decision point, exactly
    # as before S5c.
    scale_layer_bucket: int | None = None
    # Portfolio-rules slice: the PEAK held notional over the position's life
    # (initial entry, then ratcheted at every stack/scale/remainder add) — the
    # conservative exposure figure a later item's portfolio cap replays against.
    peak_notional: Decimal = _ZERO


def _dec(value: Any) -> Decimal:
    """Coerce a Parquet cell (float/int/str/Decimal) to Decimal deterministically."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _volume(value: Any) -> Decimal:
    """Coerce an optional volume cell to a NON-NEGATIVE Decimal (post-V1 (d)).

    Volume drives the VWAP weighting; an absent or unparseable cell degrades to zero
    (non-blocking, mirroring the market-data validation policy) and a stray negative is
    clamped to zero so it can never invert the volume-weighted mean."""
    if value is None:
        return _ZERO
    try:
        return max(_dec(value), _ZERO)
    except (ArithmeticError, TypeError, ValueError):
        return _ZERO


def _normalize(raw: dict[str, Any]) -> _Bar | None:
    """Project a raw OHLCV row to a typed bar; drop rows missing a price field.

    Volume is optional (only a VWAP block reads it — post-V1 (d)); an absent or
    unparseable volume degrades to zero rather than dropping the bar."""
    try:
        return _Bar(
            timestamp=str(raw["timestamp"]),
            open=_dec(raw["open"]),
            high=_dec(raw["high"]),
            low=_dec(raw["low"]),
            close=_dec(raw["close"]),
            volume=_volume(raw.get("volume")),
        )
    except (KeyError, TypeError, ArithmeticError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class TradeRow:
    seq: int
    entry_time: str
    exit_time: str
    direction: str
    entry_price: Decimal
    exit_price: Decimal
    pnl: Decimal
    exit_reason: str


@dataclass(frozen=True, slots=True)
class EquityPoint:
    seq: int
    timestamp: str
    equity: Decimal
    drawdown: Decimal
    exposure: Decimal


@dataclass(frozen=True, slots=True)
class SignalEventRow:
    seq: int
    event_time: str
    event_type: str
    direction: str | None
    detail: dict[str, Any]


# I-02 — the decision classes that are FILTER VETOES: a candidate entry was rejected by
# a rule/policy BEFORE any fill was attempted, so the event is a no-entry trace rather
# than part of the signal/execution journal. They are journaled into
# ``_Ledger.filtered_events`` and persisted as the separate ``filtered_events`` artifact
# (doc 15 §3.2 "View Filtered Events", §16).
#
# The boundary is deliberately narrow and stays here so it is one edit, not a scattered
# predicate. ``entry_blocked`` / ``stack_entry_rejected`` / ``scale_layer_rejected`` are
# NOT filter vetoes: there the signal PASSED every filter and the no-fill came from
# sizing / sleeve / exposure capacity — an execution outcome, which belongs with the
# signal journal. Adding a new veto reason to ``filtered_no_entry``'s ``detail.reason``
# needs no change here; adding a new veto EVENT TYPE does.
FILTERED_EVENT_TYPES: frozenset[str] = frozenset({"filtered_no_entry"})


@dataclass(slots=True)
class _Ledger:
    """The bar loop's running tallies, as ONE mutable object instead of 24 ``nonlocal``
    rebindings (K-10a).

    Nothing here is new state and nothing is computed differently — each field replaces a
    local of the same name with the same initial value. What it buys is extractability:
    a closure that only needed to bump a counter had to be nested inside ``run_engine``
    to reach it via ``nonlocal``; now it can take a ``_Ledger`` and live at module level.

    Mutable and NOT frozen on purpose — this is the accumulator the loop writes to, and
    the engine stays deterministic because the writes are ordered by the bar replay, not
    because the object is immutable.
    """

    # The run's output journals. Append-only — they are never rebound, so they
    # needed no ``nonlocal``; they live here so an extracted booking function can take
    # ONE accumulator instead of separate list parameters.
    signal_events: list[SignalEventRow] = field(default_factory=list)
    # I-02: the FILTER vetoes, journaled apart from ``signal_events`` because doc 15
    # §3.2 exposes "View Signal Events" and "View Filtered Events" as two distinct
    # drill-downs and §16 keeps the no-entry trace readable in its own right. Its
    # ``seq`` runs independently, so a filtered event never reads as a gap in the
    # signal journal.
    filtered_events: list[SignalEventRow] = field(default_factory=list)
    trades: list[TradeRow] = field(default_factory=list)
    equity_points: list[EquityPoint] = field(default_factory=list)
    position_intervals: list[dict[str, Any]] = field(default_factory=list)

    # The account book. ``equity`` is what sizes an entry and what bounds the sleeve /
    # exposure caps, so it is the loop's single most load-bearing running value;
    # ``peak`` trails it for drawdown. Both start at the run's initial capital, which is
    # only known inside ``run_engine`` — hence the 0 default and the explicit seeding.
    equity: Decimal = _ZERO
    peak: Decimal = _ZERO
    winners: int = 0
    stops_hit: int = 0
    stop_streak: int = 0
    max_stop_streak: int = 0
    gross_profit: Decimal = _ZERO
    gross_loss: Decimal = _ZERO
    partial_closes: int = 0
    # F-07e restriction ledger: the UTC day's realized PnL and the consecutive-loss run.
    day_realized: Decimal = _ZERO
    loss_streak: int = 0
    lock_in_locks: int = 0
    partial_fills: int = 0
    limit_orders_filled: int = 0
    tick_resolved_entry_fills: int = 0
    same_bar_stop_limit_fills: int = 0
    logic_stop_triggers: int = 0
    tick_first_trigger_resolutions: int = 0
    strength_adjustments: int = 0
    # L4 flag: partial fills were active and the bar had prints, but none carried a size.
    partial_evidence_missing: bool = False
    portfolio_conflict_blocked_entries: int = 0
    portfolio_exposure_blocked_entries: int = 0
    portfolio_exposure_clamped_entries: int = 0
    portfolio_symbol_unknown_gate: bool = False
    portfolio_time_unparseable_gate: bool = False
    portfolio_block_reason: str | None = None

    # ---- K-11a: the provenance counters K-10a left behind -------------------------
    # These 22 stayed plain ``run_engine`` locals through K-10a, which is why the bar
    # loop's phases could not be lifted out: a phase that bumps ``limit_orders_placed``
    # has nowhere to write it once it stops being nested. Same values, same initial 0,
    # same increment sites — only the binding moved.
    #
    # ``bars_seen`` is the load-bearing one: it is the replay's bar index, and both
    # ``_Pending.target_seq`` and ``_WorkingLimit.expires_seq`` are expressed in it.
    bars_seen: int = 0
    # F-07a: fills deferred to a later bar's open/close by the execution-timing model.
    deferred_entry_fills: int = 0
    deferred_exit_fills: int = 0
    # F-07b: resting limit-order lifecycle (``limit_orders_filled`` is above — it was
    # the single counter K-10a did move, and it stays where it is).
    limit_orders_placed: int = 0
    limit_orders_cancelled: int = 0
    # F-07h: stop-trigger lifecycle. A stop-limit's armed limit leg then counts through
    # the limit_orders_* counters — the two machines compose, never double-count.
    stop_orders_placed: int = 0
    stop_orders_triggered: int = 0
    stop_orders_cancelled: int = 0
    # F-07i (C): tick-setting execution counts.
    touch_orders_placed: int = 0
    touch_exit_fills: int = 0
    tick_bars: int = 0
    # F-07d: same-direction scaling ladder outcomes.
    scale_layers_added: int = 0
    scale_layers_rejected: int = 0
    # F-07e: restriction gate + conflict/position-handling policy outcomes.
    entries_blocked_by_restriction: int = 0
    stack_entries_added: int = 0
    stack_entries_rejected: int = 0
    positions_replaced: int = 0
    opposite_signal_closes: int = 0
    conflict_signals_ignored: int = 0
    stop_exit_collisions: int = 0
    suppressed_entries: int = 0
    # F-11: funding charges actually applied (a due record against a held position).
    funding_charges: int = 0

    # ---- K-11b: the loop's terminal state, read only by the output assembly --------
    # ``first_ts`` / ``last_bar`` are the ACTUAL first and last bars replayed after
    # filtering — the summary reports these, never the requested backtest_range bounds,
    # which is what proves the manifest range matches the data actually processed.
    first_ts: str = ""
    last_bar: _Bar | None = None
    # Cumulative signed funding cost booked against equity (positive = net paid). It is
    # already reflected in ``equity``; it is carried separately so the funding
    # contribution stays auditable on its own.
    funding_paid: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class AllocationExecution:
    """Resolved shared-pool capital model for the item the engine replays (doc 13 §8.3).

    Built from the run manifest's immutable ``capital_execution`` snapshot by
    ``resolve_allocation_execution`` — a PURE projection, so the engine stays a
    function of ``(config, bars, allocation)`` with no I/O. The presence of this
    object means shared allocation is ON; ``None`` means independent / absent
    allocation and the engine sizes from the strategy's own ``initial_capital``
    exactly as it did pre-allocation.

    * ``initial_capital`` — P0, the shared portfolio pool (overrides the strategy's own).
    * ``reserve_percent`` — r, the fixed nominal reserve %, floored at 0.
    * ``compound`` — ``True`` recomputes the sleeve from live portfolio equity
      (``COMPOUND_PORTFOLIO_EQUITY``); ``False`` holds the sleeve at its initial value
      (``FIXED_INITIAL_PORTFOLIO_CAPITAL``).
    * ``item_share_percent`` — wi, the replayed item's active ``equity_share_percent``;
      ``0`` when the item has no active entry → a 0-capital sleeve → no fills (an L4
      warning, NEVER a silent fall-back to the strategy's independent capital).
    """

    initial_capital: Decimal
    reserve_percent: Decimal
    compound: bool
    item_share_percent: Decimal
    currency: str | None


@dataclass(frozen=True, slots=True)
class PriorItemInterval:
    """One EARLIER-pinned item's fully-closed held-position window, replayed against
    as a portfolio constraint by a LATER-pinned item (pin-order precedence).

    ``start_ms`` / ``end_ms`` are UTC epoch milliseconds; ``None`` means the bound
    could not be placed in time and the interval is UNBOUNDED on that side — fail
    closed: an unplaceable window can only over-cover (block/cap more), never
    under-cover. ``notional`` is the position's PEAK held notional over its life
    (scaling/stacking included) — a conservative over-approximation for a cap.
    ``symbol`` is the item's canonical ``instrument_id`` (``None`` = unknown —
    treated as potentially the SAME instrument for the conflict gate, fail closed).
    """

    item_id: str
    symbol: str | None
    direction: str  # "long" | "short"
    start_ms: int | None
    end_ms: int | None
    notional: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioRules:
    """Resolved PORTFOLIO-LEVEL rules for the item the engine replays (cross-item).

    Built from the manifest's immutable ``capital_execution`` snapshot by
    ``resolve_portfolio_rules`` (pure, no I/O) and per-item completed by the worker
    (``own_symbol`` + the accumulated ``prior_intervals`` of earlier-pinned items).
    ``None`` at ``run_engine`` means no portfolio-level rule is set — the replay is
    byte-identical to the pre-rules engine.

    Honest V1 boundary (sequential enforcement): items replay independently in
    deterministic pin order, so constraints propagate FORWARD only — an
    earlier-pinned item is never re-simulated because of a later one (doc 13 §8.4
    step 6: a blocked item's share is not transferred). Surfaced as an L4 warning
    on every rules-active run, never hidden. ``NET`` (offsetting the aggregate
    position) needs a unified-clock co-simulation and is executed conservatively
    as BLOCK_OPPOSITE (L4-disclosed). ``exposure_percent_invalid`` marks a
    SET-but-unreadable/non-positive cap: the engine fails closed to a ZERO cap
    (admits nothing) rather than silently running uncapped.
    """

    max_total_exposure_percent: Decimal | None
    conflict_policy: str | None  # canonical CrossItemConflictPolicy token, or None
    own_symbol: str | None
    prior_intervals: tuple[PriorItemInterval, ...]
    exposure_percent_invalid: bool = False


@dataclass(frozen=True, slots=True)
class _RunConfig:
    """The prologue's RESOLVED settings for one run, as one read-only value (K-10c).

    ``run_engine`` opens by turning the pinned strategy/allocation/rules snapshots into
    ~30 plain locals — is sizing modelled, what is the sleeve share, which costs apply.
    Closures that only READ those locals still had to be nested to see them, which is
    what kept ``_open`` and the sizing helpers inside the function.

    FROZEN on purpose: the mutation surface does not grow. ``_Ledger`` is what the run
    writes to; this is what it reads. Keeping the two apart is what makes an extracted
    function's contract obvious — ``(ctx, led)`` says "reads config, writes ledger"
    without further reading.
    """

    config: StrategyConfig
    fill_costs: FillCosts
    # Shared-pool allocation (doc 13 §8.3). ``alloc_on`` False leaves the rest inert.
    alloc_on: bool
    alloc_compound: bool
    allocatable_initial: Decimal
    item_share: Decimal
    reserve_nominal: Decimal
    # Cross-item portfolio rules (doc 13 §8.4); ``None`` = no rule configured.
    portfolio_rules: PortfolioRules | None
    # Fail-closed capability gates: any False opens NO position (F-05/F-09).
    sizing_ok: bool
    leverage_ok: bool
    strength_ok: bool
    capability_ok: bool

    # ---- K-11b: the rest of the resolved run --------------------------------------
    # K-10c stopped at what the SIZING helpers needed. The output assembly reads far
    # more: every fail-closed gate (to name the L4 warning), every saved policy token
    # and sub-config (to report provenance), and the resolved plan / funding / tick
    # state. They are all resolved once in the prologue and never rebound, so they
    # belong on the same frozen record rather than in a second parallel one.
    initial_capital: Decimal = _ZERO
    timeframe: str | None = None
    item_count: int = 1
    execution_key: str = ""
    future_dev_selected: tuple[Any, ...] = ()
    # The six remaining fail-closed gates (sizing / leverage / strength / capability
    # are above). Any False means the run opened NO position.
    timing_ok: bool = True
    order_ok: bool = True
    partial_close_ok: bool = True
    scaling_ok: bool = True
    restrictions_ok: bool = True
    conflict_ok: bool = True
    # Saved config sub-objects, reported verbatim in the diagnostics provenance block.
    order_cfg: Any = None
    exit_logic: Any = None
    scaling_cfg: Any = None
    restrictions_cfg: Any = None
    conflict_cfg: Any = None
    # Resolved policy tokens.
    strength_mode: str = ""
    partial_aftermath: str = ""
    restriction_rule: str = ""
    unmodelled_restriction_types: tuple[str, ...] = ()
    overlap_policy: str = ""
    stacking_policy: str = ""
    hedge_policy: str = ""
    stop_trigger_requirement: str = ""
    stop_conflict_resolution: str = ""
    stop_exit_conflict: str = ""
    trailing_lock_in_active: bool = False
    scaling_enabled: bool = False
    scale_max_total: Decimal | None = None
    # Portfolio-rules provenance (doc 13 §8.4). ``conflict_gate_on`` is the EXECUTED
    # policy; ``conflict_downgraded_from_net`` records that NET was conservatively
    # downgraded to block_opposite, which the L4 warning must keep visible.
    rules_active: bool = False
    conflict_gate_on: bool = False
    portfolio_cap_amount: Decimal | None = None
    conflict_downgraded_from_net: bool = False
    conflict_policy_unknown: bool = False
    # Indicator plan + compiled evaluators.
    indicator_plan: Any = None
    plan_active: bool = False
    entry_evals: tuple[Any, ...] | list[Any] = ()
    stop_evals: tuple[Any, ...] | list[Any] = ()
    # Funding + tick-path provenance.
    funding: Any = None
    funding_records: tuple[Any, ...] = ()
    tick_batches: Any = None
    tick_alignment_unavailable: bool = False
