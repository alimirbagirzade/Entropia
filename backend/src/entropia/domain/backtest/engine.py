"""Deterministic V1 bar-replay backtest engine (Stage 5a → post-V1 Slice B, doc 15 §9.3).

Replaces the pure-from-key V1 stub with a real, deterministic bar-replay over the
pinned market revision's processed OHLCV bars (INF-12 Slice A: ``resolve_bar_source``
→ ``iter_bar_batches``). The simulation is a PURE function of
``(strategy_config, bars)``: the same pinned strategy revision + the same immutable
pinned market revision always yield byte-identical output (doc 15 §17 async
reproducibility). No DB, clock, network or real randomness.

Honest V1 boundary: real indicator packages are still V1 stubs, so entry/exit timing
uses a DETERMINISTIC breakout PROXY derived purely from the bars (labelled
``entry_model=deterministic_bar_breakout_proxy_v1`` in diagnostics), NOT real
indicator signals. What IS real: the bars, their timestamps/prices, the strategy's
protection stops (percentage / trailing / absolute), the direction bias, the costs
(commission / spread / slippage) and the position sizing. When the indicator layer
lands, only the entry/exit evaluation here changes; the run, manifest and result
contracts stay put.

Engine order follows doc 15 §9.3 (bounded to the foundation scope): per bar —
(1) update the rolling breakout window; (2) if in a position, evaluate
protection/stop/exit against THIS bar's high/low (intrabar touch); (3) if flat,
evaluate the breakout entry proxy and open a position. State/decision-trace
counters are emitted per trade (bounded memory — never O(bars)); the OHLCV stream
is consumed one batch at a time.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from entropia.domain.allocation.enums import CompoundingMode
from entropia.domain.backtest.funding import FundingSchedule, parse_utc
from entropia.domain.backtest.indicators import (
    BUILTIN_ENTRY_MODEL,
    VOLUME_WEIGHTED_KEYS,
    BlockEvaluator,
    IndicatorPlan,
    aggregate,
    build_evaluators,
)

if TYPE_CHECKING:
    from entropia.domain.strategy.config import (
        PositionSizeLimits,
        PositionSizing,
        StrategyConfig,
    )

_MONEY = Decimal("0.01")
_PCT = Decimal("0.0001")
_RATIO = Decimal("0.01")
_QTY = Decimal("0.00000001")
_HUNDRED = Decimal("100")
_ZERO = Decimal("0")
_ONE = Decimal("1")

# Rolling look-back for the breakout entry/exit proxy. A constant of the engine
# version (part of the reproducibility contract via ``engine_version``), NOT a
# strategy input — real indicator look-backs arrive with the indicator layer.
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
    "entry_blocked",  # a wanted entry produced no fill (sizing / sleeve capacity)
    "filtered_no_entry",  # a signal was filtered by the direction bias (no fill attempt)
    "exit_scheduled",  # a deferred exit was scheduled to a future bar (F-07a timing)
    "position_close",  # a position closed (trade linkage + exit reason + realized pnl)
    "stop_resolution",  # multi-rule / logic stop resolution (F-08 combination engine)
    "stop_exit_collision",  # same-bar stop+exit tie-break decision (§5.9)
    "funding_charge",  # a funding rate applied to the open position (F-11, doc 12 §8.4)
)
# Honest V1 boundary: the bar-replay engine holds at most ONE full-size position, so these
# decision classes never occur — surfaced (never fabricated as phantom events).
UNMODELLED_DECISION_CLASSES = (
    "same_direction_scaling",
    "partial_fill",
    "partial_close",
)


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


@dataclass(frozen=True, slots=True)
class EngineOutput:
    summary: dict[str, Any]
    trades: list[TradeRow]
    equity_points: list[EquityPoint]
    signal_events: list[SignalEventRow]
    diagnostics: dict[str, Any]


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


@dataclass(slots=True)
class _Pending:
    """A fill deferred to a FUTURE bar by the execution-timing setting (F-07a, §2).

    ``current_candle_close`` / ``market_fill_simulation`` fill immediately at the
    signal bar's close and never create a ``_Pending``. ``next_candle_open`` /
    ``next_candle_close`` defer the fill to the following bar: ``target_seq`` is the
    ``bars_seen`` index at which the fill executes (always the bar right after the
    signal), and ``at_open`` chooses that bar's open (resolved before the intrabar
    stop path) versus its close (resolved at end-of-bar, so an intrabar stop on the
    same bar pre-empts a scheduled close exit). At most one ``_Pending`` is ever
    outstanding: an entry pending exists only while flat, an exit pending only while
    in a position."""

    kind: str  # "entry" | "exit"
    at_open: bool  # fill at the target bar's OPEN (else its CLOSE)
    target_seq: int  # bars_seen index at which the fill executes (the next bar)
    direction: str  # entry direction ("" for an exit)
    reason: str  # exit reason ("" for an entry)


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


def _direction_flags(mode: str) -> tuple[bool, bool]:
    """(long_allowed, short_allowed) from the entry ``direction_mode``."""
    return mode in ("long", "long_and_short"), mode in ("short", "long_and_short")


def _cost_params(config: StrategyConfig) -> tuple[Decimal, Decimal, Decimal]:
    """(half_spread, slippage_fraction, per_fill_commission) — all non-negative."""
    costs = config.data.costs
    spread = (costs.spread or _ZERO) / Decimal("2")
    slippage = (costs.slippage_value or _ZERO) / _HUNDRED
    commission = costs.commission or _ZERO
    return spread, slippage, commission


def _effective_fill(
    price: Decimal, *, is_buy: bool, half_spread: Decimal, slip: Decimal
) -> Decimal:
    """Adverse-side fill: a buy pays up, a sell receives less (spread + slippage)."""
    adjusted = price + half_spread if is_buy else price - half_spread
    factor = Decimal("1") + slip if is_buy else Decimal("1") - slip
    return (adjusted * factor).quantize(_MONEY)


def _decimal_param(params: dict[str, Any], key: str) -> Decimal | None:
    """Best-effort ``Decimal`` from a free-form ``formula_params`` entry.

    Returns ``None`` when the key is absent, the value cannot be parsed as a number,
    or it parses to a NON-FINITE ``Decimal`` (``NaN`` / ``Infinity``). ``str()`` first
    so a non-numeric value fails closed rather than a ``Decimal`` coercion surprise;
    the finiteness guard is load-bearing because ``formula_params`` is an unvalidated
    ``dict[str, Any]`` — a user-supplied ``"nan"`` constructs a quiet ``Decimal('NaN')``
    without error but then RAISES ``InvalidOperation`` on the ordered comparisons in
    the caller (crashing the run), and an ``"Infinity"`` payoff would otherwise be
    silently honoured as a real edge. Both must fail closed to notional + the L4
    warning instead."""
    if key not in params:
        return None
    try:
        value = Decimal(str(params[key]))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return value if value.is_finite() else None


def _kelly_capital_fraction(sizing: PositionSizing) -> Decimal | None:
    """Fractional-Kelly capital fraction for a ``kelly_criterion`` formula config.

    Grounded, deterministic and path-INDEPENDENT: the win probability ``W``, the
    payoff ratio ``R`` (average win / average loss) and the optional fractional-Kelly
    multiplier all come from the strategy's own ``formula_params`` — user-supplied
    edge estimates, NOT statistics estimated from the running backtest's realized
    trades. That adaptive form is deliberately DEFERRED: estimating ``W`` / ``R`` from
    outcomes-so-far is path-dependent and look-ahead-prone, so it is not modelled here
    (the honest boundary, symmetric with ``risk_based`` reading fixed config
    constants). Kelly capital fraction::

        f* = kelly_fraction * (W - (1 - W) / R)

    clamped at the LOWER bound to 0 — a non-positive edge yields 0 (do not trade),
    never a negative (bet-against-the-edge) size. No upper clamp is needed: since
    ``(1 - W) / R >= 0`` and ``W < 1``, the edge is always ``< 1`` and so is ``f*``.
    An absent ``kelly_fraction`` defaults to full Kelly (``1``); a present but
    unparseable / non-finite / out-of-range one fails closed. Returns ``None`` when
    the config is not a modelled ``kelly_criterion`` request (``custom_formula``, or a
    missing / non-finite / out-of-range ``W`` / ``R`` / explicit ``kelly_fraction``),
    so the caller falls back to notional sizing and surfaces the L4 diagnostics
    warning."""
    formula = sizing.formula_based
    if sizing.method != "formula_based_sizing" or formula is None:
        return None
    if formula.formula_type != "kelly_criterion":
        return None  # custom_formula: no safe arbitrary-expression evaluation
    win = _decimal_param(formula.formula_params, "win_probability")
    payoff = _decimal_param(formula.formula_params, "payoff_ratio")
    if win is None or payoff is None or not (_ZERO < win < _ONE) or payoff <= _ZERO:
        return None
    if "kelly_fraction" not in formula.formula_params:
        fraction = _ONE  # ABSENT → full Kelly (the documented default)
    else:
        # PRESENT: must be a valid finite multiplier in (0, 1]. An unparseable /
        # non-finite / out-of-range value fails closed to notional — never silently
        # upgraded to the most aggressive (full-Kelly) sizing.
        parsed = _decimal_param(formula.formula_params, "kelly_fraction")
        if parsed is None or not (_ZERO < parsed <= _ONE):
            return None
        fraction = parsed
    edge = win - (_ONE - win) / payoff
    return max(fraction * edge, _ZERO)


def _sizing_is_honored(config: StrategyConfig) -> bool:
    """Whether the requested sizing method is modelled by this engine version.

    ``base_position_size`` (explicit size), ``risk_based_sizing`` (a fixed % of equity
    risked across the stop distance) and ``formula_based_sizing`` with a valid
    ``kelly_criterion`` config are honored. A ``formula_based_sizing`` request that is
    ``custom_formula`` or carries missing / out-of-range Kelly params — and a
    ``risk_based_sizing`` request that carries no ``risk_based`` sub-config — are not
    modelled and FAIL CLOSED: the engine opens no position for them (F-09), surfaced
    as a diagnostics warning, never hidden — L4."""
    sizing = config.position_sizing
    if sizing.method == "base_position_size" and sizing.base_position_size is not None:
        return True
    if sizing.method == "risk_based_sizing" and sizing.risk_based is not None:
        return True
    return _kelly_capital_fraction(sizing) is not None


def sizing_is_modelled(config: StrategyConfig) -> bool:
    """Public predicate: is this strategy's position sizing modelled by the engine?

    The single shared source of truth for "modelled sizing", imported by the readiness
    validator so Ready Check's ``STRATEGY_SIZING_UNSUPPORTED`` blocker and the engine's
    fail-closed ``_open`` gate agree on exactly one definition — an unsupported method
    is blocked at Ready Check AND opens no position if a stale readiness state slips
    through to the worker (F-09)."""
    return _sizing_is_honored(config)


# §2 Execution timing modelled by the deterministic OHLCV bar-replay (F-07a). The
# "immediate" modes fill at the SIGNAL bar's close (a market fill at the decision
# point); the "next candle" modes defer the fill to the following bar's open/close,
# removing the hardcoded current-candle-close assumption. ``intrabar_touch`` and the
# limit / stop-limit simulation modes need an intrabar (tick) price path or the
# limit-order machinery (later F-07 slices) and MUST NOT be silently imitated over
# plain OHLCV (doc 02 Entry/Exit Execution row: "cannot silently imitate unavailable
# detail") — they FAIL CLOSED as a Ready Check blocker + an inert engine run.
_ENTRY_TIMING_IMMEDIATE = frozenset({"current_candle_close", "market_fill_simulation"})
_EXIT_TIMING_IMMEDIATE = frozenset({"current_candle_close", "market_fill_simulation"})
_ENTRY_TIMING_MODELLED = _ENTRY_TIMING_IMMEDIATE | {"next_candle_open", "next_candle_close"}
_EXIT_TIMING_MODELLED = _EXIT_TIMING_IMMEDIATE | {"next_candle_open", "next_candle_close"}


def execution_timing_is_modelled(config: StrategyConfig) -> bool:
    """Public predicate: are BOTH entry and exit execution timings modelled (F-07a)?

    The single shared source of truth for "modelled timing", imported by the readiness
    validator so Ready Check's ``STRATEGY_EXECUTION_TIMING_UNSUPPORTED`` blocker and the
    engine's fail-closed entry gate agree on exactly one definition. An unsupported
    value (``intrabar_touch`` / a limit or stop-limit simulation mode) is blocked at
    Ready Check AND opens no position if a stale readiness state slips through to the
    worker — never silently downgraded to a current-candle-close fill it did not
    request."""
    execution = config.data.execution
    return (
        execution.entry_timing in _ENTRY_TIMING_MODELLED
        and execution.exit_timing in _EXIT_TIMING_MODELLED
    )


def _fill_schedule(timing: str) -> str:
    """Map a timing enum to a fill schedule: ``immediate`` / ``next_open`` / ``next_close``.

    Immediate / market-fill (and any unsupported value) map to ``immediate`` — the
    unsupported case is inert because the entry gate blocks trading unless
    ``execution_timing_is_modelled`` holds (fail-closed backstop to Ready Check)."""
    if timing == "next_candle_open":
        return "next_open"
    if timing == "next_candle_close":
        return "next_close"
    return "immediate"


def _clamp_to_limits(size: Decimal, limits: PositionSizeLimits | None) -> Decimal:
    """Clamp a computed size to the strategy's configured min/max position caps (§6).

    A no-op when no ``position_size_limits`` are configured OR the size is already
    non-positive: ``0`` is the fail-closed "do not open" sentinel returned by
    ``_raw_position_size`` (bust equity / non-positive entry price), and a ``min`` cap
    must NOT resurrect it into a live position, nor may a stray negative be lifted
    positive. A misconfigured window (``min > max`` — no size can satisfy both) fails
    closed to ``0`` rather than silently honouring one bound and violating the other.
    Only a genuinely positive size is pulled DOWN to ``max`` then UP to ``min``; the
    final ``max(., 0)`` also neutralises a nonsensical negative cap. Caps are in the
    same UNITS as the size (contracts/coins), applied verbatim (unquantized) — mirrors
    the unquantized ``base_position_size`` branch."""
    if limits is None or size <= _ZERO:
        return size
    minimum = limits.min_position_size
    maximum = limits.max_position_size
    if minimum is not None and maximum is not None and minimum > maximum:
        return _ZERO
    if maximum is not None and size > maximum:
        size = maximum
    if minimum is not None and size < minimum:
        size = minimum
    return max(size, _ZERO)


def _raw_position_size(config: StrategyConfig, entry_price: Decimal, equity: Decimal) -> Decimal:
    """Deterministic sizing: explicit base size, risk-based, Kelly, else fail closed.

    ``base_position_size`` returns the explicit size. ``risk_based_sizing`` risks a
    fixed % of (non-negative) equity across the configured stop distance —
    ``size = equity * risk% / 100 / stop_loss_point`` — and is therefore independent
    of the entry price. ``formula_based_sizing`` with a valid ``kelly_criterion`` config
    allocates a fractional-Kelly slice of (non-negative) equity —
    ``size = equity * f* / entry_price`` — and is therefore entry-price DEPENDENT
    (Kelly sizes a fraction of CAPITAL; converting that to units divides by price),
    unlike risk-based. An unmodelled formula (``custom_formula`` / bad params) and any
    request missing its sub-config FAIL CLOSED to size 0 — never an all-in notional
    (F-09; surfaced as a diagnostics warning, L4). Every branch clamps to NON-NEGATIVE
    equity: a bust
    account yields size 0, never a negative size — a negative size would invert the
    PnL sign of every subsequent trade (review CRITICAL). The result is then clamped
    to the configured ``position_size_limits`` by ``_position_size``."""
    sizing = config.position_sizing
    if sizing.method == "base_position_size" and sizing.base_position_size is not None:
        return Decimal(sizing.base_position_size)
    usable_equity = max(equity, _ZERO)
    if sizing.method == "risk_based_sizing" and sizing.risk_based is not None:
        risk = sizing.risk_based
        if risk.stop_loss_point > _ZERO:
            risk_capital = usable_equity * risk.risk_percentage_per_trade / _HUNDRED
            return (risk_capital / risk.stop_loss_point).quantize(_QTY)
        return _ZERO
    kelly = _kelly_capital_fraction(sizing)
    if kelly is not None:
        if entry_price > _ZERO:
            return (usable_equity * kelly / entry_price).quantize(_QTY)
        return _ZERO
    # F-09 (fail closed): the requested sizing method is NOT modelled by this engine
    # version (``custom_formula``, out-of-range / missing Kelly params, or a request
    # missing its sub-config). It opens NO position — the account is never "all-in'd"
    # by dividing all available equity by the entry price (the prior behaviour, which
    # could fabricate a full-notional trade for a strategy the user never validly
    # configured). Ready Check raises a ``STRATEGY_SIZING_UNSUPPORTED`` blocker so this
    # state cannot reach a real RUN; ``run_engine`` additionally refuses to open any
    # position when the sizing is unmodelled, so a stale/bypassed readiness state
    # reaching the worker still produces a financially inert run. The divergence is
    # surfaced (L4) via the ``position_sizing_method_unsupported`` diagnostics warning.
    return _ZERO


def _position_size(config: StrategyConfig, entry_price: Decimal, equity: Decimal) -> Decimal:
    """Deterministic sizing (see ``_raw_position_size``) clamped to the configured
    ``position_size_limits`` min/max caps (§6). The clamp applies uniformly to EVERY
    sizing method — base, risk-based, Kelly and the notional fallback — so a global cap
    is honoured regardless of which sizing path produced the size. A missing limits
    subtree is a no-op, so behaviour is byte-identical to the pre-wiring engine."""
    size = _raw_position_size(config, entry_price, equity)
    return _clamp_to_limits(size, config.position_sizing.position_size_limits)


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


def _cap_to_sleeve(desired: Decimal, sleeve_capital: Decimal, entry_price: Decimal) -> Decimal:
    """Clamp a desired size to the sleeve's remaining capacity (doc 13 §8.3/§8.4 step 5).

    ``allowed_size = min(desired, remaining_sleeve_capacity / entry_price)``. The engine
    holds at most one position at a time, so when it opens, the item's deployed capital
    is 0 and the FULL sleeve is available (the single-item foundation — a genuine
    multi-item co-simulation over a unified clock stays deferred). A non-positive sleeve
    or entry price yields 0 (the item is unallocated / cannot fill)."""
    if sleeve_capital <= _ZERO or entry_price <= _ZERO:
        return _ZERO
    cap_units = (sleeve_capital / entry_price).quantize(_QTY)
    return min(desired, cap_units)


def _pct_stop_level(
    config: StrategyConfig, *, is_long: bool, entry_price: Decimal
) -> Decimal | None:
    """Enabled percentage stop level (entry-relative, fixed for the position's life)."""
    protection = config.protection_stop_logic
    if protection is None or protection.percentage_stop is None:
        return None
    pct = protection.percentage_stop
    if not pct.enabled:
        return None
    distance = entry_price * (pct.loss_percentage / _HUNDRED)
    return entry_price - distance if is_long else entry_price + distance


def _abs_stop_level(config: StrategyConfig) -> Decimal | None:
    """Enabled absolute-price stop level (fixed)."""
    protection = config.protection_stop_logic
    if protection is None or protection.absolute_stop is None:
        return None
    absolute = protection.absolute_stop
    if not absolute.enabled or absolute.absolute_price is None:
        return None
    return Decimal(absolute.absolute_price)


def _trail_pct(config: StrategyConfig) -> Decimal | None:
    protection = config.protection_stop_logic
    if protection is None or protection.trailing_stop is None:
        return None
    trailing = protection.trailing_stop
    return trailing.trail_percentage / _HUNDRED if trailing.enabled else None


def _trailing_level(position: _Position) -> Decimal | None:
    """Current trailing-stop level from the favourable extreme (None if inactive)."""
    if position.trail_pct is None:
        return None
    if position.direction == "long":
        return position.trail_anchor * (Decimal("1") - position.trail_pct)
    return position.trail_anchor * (Decimal("1") + position.trail_pct)


# Canonical §9.2 stop precedence AFTER any logic blocks (which come first, in display
# order): percentage, then trailing, then absolute. Used for priority_order resolution
# when no explicit stop_priority_order is configured, and as the deterministic tie-break
# for most_conservative.
_CANONICAL_PRICE_STOP_ORDER = ("percentage", "trailing", "absolute")


def _stop_priority_index(custom_order: list[str] | None, logic_keys: list[str]) -> dict[str, int]:
    """Map every stop key to a precedence index (lower = higher priority).

    The canonical default (``custom_order is None``) is logic blocks in display order,
    then percentage, trailing, absolute (Master Ref §9.2). An explicit
    ``stop_priority_order`` leads; any key it omits is appended in canonical order so the
    result is always total and deterministic.
    """
    ordered: list[str] = list(custom_order) if custom_order else []
    for key in [*logic_keys, *_CANONICAL_PRICE_STOP_ORDER]:
        if key not in ordered:
            ordered.append(key)
    return {key: idx for idx, key in enumerate(ordered)}


@dataclass(frozen=True, slots=True)
class _StopOutcome:
    """Resolved protection-stop firing for one bar (F-08 combination engine)."""

    price: Decimal  # executed exit price of the winning rule
    executed_key: str  # winning stop key (e.g. "percentage" / "logic:<block_id>")
    triggered: tuple[str, ...]  # every stop key that fired this bar (sorted)
    approximated_first: bool  # first_trigger_wins resolved to conservative over OHLCV


def _resolve_stop(
    config: StrategyConfig,
    position: _Position,
    bar: _Bar,
    *,
    logic_enabled: list[str],
    logic_triggered: list[str],
) -> _StopOutcome | None:
    """Combine every enabled protection stop rule for THIS bar (Master Ref §9.1/§9.3).

    Enabled rules = each enabled price stop (percentage / absolute / trailing) plus each
    enabled Logic-Based Stop Block (``logic_enabled``). A price stop TRIGGERS when the
    bar's adverse extreme touches its level (long: ``low <= level``; short:
    ``high >= level``) and executes at that level. A logic block triggers when it emits a
    signal against the open position (``logic_triggered``) and executes at the bar close
    (signal-confirmed). ``stop_trigger_requirement`` decides WHETHER protection fires
    (``any_active`` = any rule; ``all_active`` = every enabled rule this bar);
    ``stop_conflict_resolution`` decides WHICH triggered rule's price/reason executes.
    Returns ``None`` when protection does not fire.
    """
    protection = config.protection_stop_logic
    is_long = position.direction == "long"
    entry = position.entry_price

    price_levels: dict[str, Decimal] = {}
    if position.pct_stop is not None:
        price_levels["percentage"] = position.pct_stop
    if position.abs_stop is not None:
        price_levels["absolute"] = position.abs_stop
    trailing = _trailing_level(position)
    if trailing is not None:
        price_levels["trailing"] = trailing

    enabled_keys = set(price_levels) | set(logic_enabled)
    if not enabled_keys:
        return None

    triggered: dict[str, Decimal] = {}
    for key, level in price_levels.items():
        touched = (is_long and bar.low <= level) or (not is_long and bar.high >= level)
        if touched:
            triggered[key] = level
    for key in logic_triggered:
        triggered[key] = bar.close  # logic stop fills at the signal-confirmed bar close

    if not triggered:
        return None

    requirement = protection.stop_trigger_requirement if protection is not None else "any_active"
    if requirement == "all_active" and set(triggered) != enabled_keys:
        return None

    resolution = (
        protection.stop_conflict_resolution if protection is not None else "most_conservative"
    )
    approximated_first = False
    if resolution == "first_trigger_wins":
        # OHLCV carries no intrabar tick path, so true first-touch order is unknowable;
        # resolve to the conservative model and flag it (Master Ref §9.3), never faked.
        resolution = "most_conservative"
        approximated_first = True

    priority = _stop_priority_index(
        protection.stop_priority_order if protection is not None else None, logic_enabled
    )
    if resolution in ("priority_order", "record_all_execute_highest"):
        winner = min(triggered, key=lambda k: priority.get(k, len(priority)))
    else:  # most_conservative: tightest adverse move, canonical priority as tie-break
        winner = min(
            triggered,
            key=lambda k: (abs(entry - triggered[k]), priority.get(k, len(priority))),
        )

    return _StopOutcome(
        price=triggered[winner],
        executed_key=winner,
        triggered=tuple(sorted(triggered)),
        approximated_first=approximated_first,
    )


def _exit_proxy(position: _Position, bar: _Bar, window: deque[_Bar]) -> bool:
    """Opposite-breakout exit: a long exits on a new window low, a short on a new high."""
    if len(window) < _BREAKOUT_WINDOW:
        return False
    if position.direction == "long":
        return bar.close < min(b.low for b in window)
    return bar.close > max(b.high for b in window)


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
) -> EngineOutput:
    """Deterministically bar-replay one strategy over its pinned OHLCV bars.

    Entry/exit timing uses real built-in indicator signals when ``indicator_plan``
    resolves to at least one computable entry block; otherwise it falls back to the
    labelled deterministic breakout proxy (Slice B behaviour), so callers without a
    plan — and the pure unit tests — are unaffected.

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
    funding and is BYTE-IDENTICAL to the pre-F-11 engine."""
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
    long_ok, short_ok = _direction_flags(config.position_entry_logic.direction_mode)
    half_spread, slippage, commission = _cost_params(config)
    trail_pct = _trail_pct(config)
    # §5.9 Stop+Exit same-bar collision policy (read straight from the pinned config so it
    # applies in BOTH plan and breakout-proxy modes; default "stop_has_priority" = V18).
    stop_exit_conflict = str(config.conflict_position_handling.stop_exit_conflict)
    # F-08 stop-combination modes (read once; drive _resolve_stop + the ledger record).
    _protection = config.protection_stop_logic
    stop_trigger_requirement = (
        _protection.stop_trigger_requirement if _protection is not None else "any_active"
    )
    stop_conflict_resolution = (
        _protection.stop_conflict_resolution if _protection is not None else "most_conservative"
    )

    # F-09: an unmodelled / misconfigured sizing method opens NO position at all — the
    # engine is a fail-closed backstop to the Ready Check STRATEGY_SIZING_UNSUPPORTED
    # blocker, so a stale/bypassed readiness state reaching the worker still produces a
    # financially inert run (no phantom 0-size or all-in trades).
    sizing_ok = _sizing_is_honored(config)

    # F-07a: entry/exit execution timing. Immediate modes fill at the signal bar's
    # close; the next-candle modes defer the fill to the following bar (removing the
    # hardcoded current-candle-close assumption). An UNSUPPORTED timing (intrabar_touch /
    # a limit or stop-limit simulation) opens NO position — the fail-closed backstop to
    # the Ready Check STRATEGY_EXECUTION_TIMING_UNSUPPORTED blocker, never silently
    # downgraded to a close fill it did not request.
    timing_ok = execution_timing_is_modelled(config)
    entry_sched = _fill_schedule(config.data.execution.entry_timing)
    exit_sched = _fill_schedule(config.data.execution.exit_timing)

    plan_active = indicator_plan is not None and indicator_plan.has_entry
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
    logic_stop_triggers = 0

    equity = initial_capital
    peak = initial_capital
    trades: list[TradeRow] = []
    equity_points: list[EquityPoint] = [
        EquityPoint(0, "", initial_capital, _ZERO.quantize(_MONEY), _ZERO.quantize(_PCT))
    ]
    signal_events: list[SignalEventRow] = []
    window: deque[_Bar] = deque(maxlen=_BREAKOUT_WINDOW)
    position: _Position | None = None
    pending: _Pending | None = None  # a fill deferred to a future bar (F-07a timing)
    bars_seen = 0
    first_ts = ""
    last_bar: _Bar | None = None
    winners = 0
    stops_hit = 0
    stop_streak = 0
    max_stop_streak = 0
    suppressed_entries = 0
    stop_exit_collisions = 0
    deferred_entry_fills = 0
    deferred_exit_fills = 0
    gross_profit = _ZERO
    gross_loss = _ZERO
    # F-11: funding cost state. ``funding_records`` is the ascending, available-time-safe
    # series (empty when funding is off → the whole funding path is inert, byte-identical to
    # pre-F-11). ``funding_idx`` is the as-of cursor (a record fires at most once, in order);
    # ``funding_paid`` is the cumulative signed cost booked against equity.
    funding_records = funding.records if funding is not None else ()
    funding_idx = 0
    funding_charges = 0
    funding_paid = _ZERO
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
        """Append one immutable decision-trace event (F-10, doc 15 §9.3 step 8/§14).

        ``bar_seq`` (the 1-based replayed-bar index) + ``event_time`` bind the event to
        the exact bar; ``detail`` carries the position/order linkage and rule evidence.
        A signal/decision event is NEVER conflated with a real fill (doc 15 §16)."""
        signal_events.append(
            SignalEventRow(
                seq=len(signal_events),
                event_time=event_time,
                event_type=event_type,
                direction=direction,
                detail={"bar_seq": bar_seq, **detail},
            )
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
        """Why a wanted entry produced NO fill (F-10 restriction trace)."""
        if not sizing_ok:
            return "sizing_unsupported"
        if alloc_on:
            return "sleeve_zero_capacity"
        return "no_fill"

    def _close(
        exit_time: str,
        exit_price_raw: Decimal,
        reason: str,
        pos: _Position,
        *,
        bar_seq: int,
    ) -> None:
        nonlocal equity, peak, winners, stops_hit, stop_streak, max_stop_streak
        nonlocal gross_profit, gross_loss
        is_long = pos.direction == "long"
        exit_eff = _effective_fill(
            exit_price_raw, is_buy=not is_long, half_spread=half_spread, slip=slippage
        )
        sign = Decimal("1") if is_long else Decimal("-1")
        gross = (exit_eff - pos.entry_price) * pos.size * sign
        pnl = (gross - commission * 2).quantize(_MONEY)
        equity_before = equity
        equity = (equity + pnl).quantize(_MONEY)
        peak = max(peak, equity)
        drawdown = (peak - equity).quantize(_MONEY)
        exposure = (
            (pos.entry_notional / equity_before * _HUNDRED).quantize(_PCT)
            if equity_before > _ZERO
            else _ZERO.quantize(_PCT)
        )
        if pnl > _ZERO:
            winners += 1
            gross_profit += pnl
        else:
            gross_loss += -pnl
        if reason == "stop_loss":
            stops_hit += 1
            stop_streak += 1
            max_stop_streak = max(max_stop_streak, stop_streak)
        else:
            stop_streak = 0
        seq = len(trades) + 1
        trades.append(
            TradeRow(
                seq=seq,
                entry_time=pos.entry_time,
                exit_time=exit_time,
                direction=pos.direction,
                entry_price=pos.entry_price,
                exit_price=exit_eff,
                pnl=pnl,
                exit_reason=reason,
            )
        )
        equity_points.append(
            EquityPoint(
                seq=seq,
                timestamp=exit_time,
                equity=equity,
                drawdown=drawdown,
                exposure=exposure,
            )
        )
        # F-10: the position CLOSE decision — links the lifecycle to its immutable trade
        # row (``trade_seq``), the exit reason, the realized pnl and the holding span so a
        # reviewer reconstructs exactly why/when the position closed. Distinct from the
        # ``entry_fill`` event — a close is never conflated with the open (doc 15 §16).
        _emit(
            "position_close",
            event_time=exit_time,
            direction=pos.direction,
            bar_seq=bar_seq,
            detail={
                "position_seq": pos.position_seq,
                "trade_seq": seq,
                "exit_reason": reason,
                "exit_price": str(exit_eff),
                "pnl": str(pnl),
                "entry_bar_seq": pos.entry_bar_seq,
                "holding_bars": bar_seq - pos.entry_bar_seq,
            },
        )

    def _sleeve_capital(current_equity: Decimal) -> Decimal:
        """The replayed item's sleeve cap Ci(t) at this valuation point (doc 13 §8.3).

        Compound: A(t) = max(0, E(t) - R0); Ci(t) = A(t) * wi / 100, where E(t) is the
        portfolio equity (which starts at P0 and accrues this item's realized PnL in the
        single-item foundation). Fixed: Ci = A0 * wi / 100 (constant)."""
        allocatable = (
            max(_ZERO, current_equity - reserve_nominal) if alloc_compound else allocatable_initial
        )
        return allocatable * item_share / _HUNDRED

    def _open(direction: str, bar: _Bar, fill_raw: Decimal, *, bar_seq: int) -> _Position | None:
        """Open a position at the cost-adjusted fill of ``fill_raw``, or ``None`` for a
        no-fill.

        ``fill_raw`` is the raw (pre-cost) execution price chosen by the entry timing:
        the signal bar's close (immediate), or the next bar's open / close (deferred) —
        removing the hardcoded current-candle-close assumption (F-07a). Under allocation
        a 0-capacity sleeve (an unallocated item, or a compound pool busted below its
        reserve) yields no fill at all — ``None`` — rather than a phantom 0-size trade
        (doc 13 §8.4 step 5/6). Independent mode books even a bust-equity 0-size fill
        (preserving the risk-based no-phantom-profit invariant), but an UNMODELLED sizing
        method (F-09) opens nothing at all — no phantom trade for a strategy the user
        never validly configured."""
        if not sizing_ok:
            return None
        is_long = direction == "long"
        entry_eff = _effective_fill(
            fill_raw, is_buy=is_long, half_spread=half_spread, slip=slippage
        )
        if alloc_on:
            # Strategy Details sizing/risk constraints first (within the item's sleeve),
            # then the allocation remaining-sleeve outer cap (§8.4 step 5).
            sleeve = _sleeve_capital(equity)
            desired = _position_size(config, entry_eff, sleeve)
            size = _cap_to_sleeve(desired, sleeve, entry_eff)
            if size <= _ZERO:
                return None
        else:
            size = _position_size(config, entry_eff, equity)
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
        )

    def _do_open(
        direction: str, bar: _Bar, fill_raw: Decimal, *, bar_seq: int, deferred: bool
    ) -> _Position | None:
        """Open a position AND emit the F-10 fill/blocked decision-trace event.

        On a real fill: ``entry_fill`` (the execution — position_seq, price, size, timing).
        On a no-fill: ``entry_blocked`` with the concrete reason (sizing/sleeve), so a
        signalled-but-unfilled entry is never a silent gap in the trace."""
        pos = _open(direction, bar, fill_raw, bar_seq=bar_seq)
        if pos is not None:
            _emit(
                "entry_fill",
                event_time=bar.timestamp,
                direction=direction,
                bar_seq=bar_seq,
                detail={
                    "position_seq": pos.position_seq,
                    "fill_price": str(pos.entry_price),
                    "size": str(pos.size),
                    "entry_notional": str(pos.entry_notional),
                    "timing": config.data.execution.entry_timing,
                    "deferred": deferred,
                },
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

    def _plan_exit(pos: _Position, entry_signal: str | None, exit_hit: bool) -> bool:
        """Exit on an explicit exit signal or (opt-in) an opposite entry signal."""
        if exit_hit:
            return True
        opposite = entry_signal is not None and entry_signal != pos.direction
        return bool(opposite and indicator_plan is not None and indicator_plan.exit_on_opposite)

    def _emit_stop_resolution(outcome: _StopOutcome, event_time: str, direction: str) -> None:
        """Record the resolved stop (Master Ref §9.2: ledger carries priority + sources).

        Emits a ``stop_resolution`` decision-trace event whenever more than one rule fired,
        the executed rule was a Logic-Based Stop, or the OHLCV first-trigger approximation
        applied. The single-price-stop default path emits nothing extra (byte-identical to
        pre-F-08 output)."""
        nonlocal logic_stop_triggers
        if any(k.startswith("logic:") for k in outcome.triggered):
            logic_stop_triggers += 1
        if (
            len(outcome.triggered) > 1
            or outcome.approximated_first
            or outcome.executed_key.startswith("logic:")
        ):
            signal_events.append(
                SignalEventRow(
                    seq=len(signal_events),
                    event_time=event_time,
                    event_type="stop_resolution",
                    direction=direction,
                    detail={
                        "executed": outcome.executed_key,
                        "triggered": list(outcome.triggered),
                        "requirement": stop_trigger_requirement,
                        "resolution": stop_conflict_resolution,
                        "first_trigger_approximated": outcome.approximated_first,
                    },
                )
            )

    for batch in bar_batches:
        for raw in batch:
            bar = _normalize(raw)
            if bar is None:
                continue
            bars_seen += 1
            if not first_ts:
                first_ts = bar.timestamp
            last_bar = bar

            # Real indicator signals (when a plan resolved); evaluators see EVERY bar.
            entry_signal: str | None = None
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

            # (1) Resolve a fill deferred to THIS bar's OPEN (next_candle_open). Runs
            # before the intrabar stop path so the open fill precedes the bar's high/low.
            if pending is not None and pending.target_seq == bars_seen and pending.at_open:
                if pending.kind == "entry" and position is None:
                    deferred_entry_fills += 1
                    position = _do_open(
                        pending.direction, bar, bar.open, bar_seq=bars_seen, deferred=True
                    )
                elif pending.kind == "exit" and position is not None:
                    deferred_exit_fills += 1
                    _close(bar.timestamp, bar.open, pending.reason, position, bar_seq=bars_seen)
                    position = None
                pending = None

            if position is not None:
                # (2) protection / stop / exit against this bar (intrabar touch).
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
                )
                stop_touched = stop_outcome is not None
                # A fresh exit signal is evaluated only when no exit is already committed:
                # a deferred exit from a prior bar (``pending``) is pinned and cannot be
                # pre-empted by a new signal — only an intrabar stop below can cancel it.
                exit_wanted = pending is None and (
                    _plan_exit(position, entry_signal, exit_hit)
                    if plan_active
                    else _exit_proxy(position, bar, window)
                )
                if stop_touched and exit_wanted and exit_sched == "immediate":
                    # §5.9 same-bar Stop+Exit collision — only when the exit ALSO fills
                    # this bar (immediate timing). A deferred exit would fill strictly
                    # later, so an intrabar stop simply wins (handled by the elif below).
                    # Only "exit_has_priority" changes the OUTCOME (close at close as an
                    # exit); the other three execute the stop (the intrabar touch precedes
                    # the close-based exit), "record_both_reasons" logs both codes.
                    stop_exit_collisions += 1
                    executed_reason = (
                        "exit_signal" if stop_exit_conflict == "exit_has_priority" else "stop_loss"
                    )
                    # F-10: the CONFLICT decision is ALWAYS traced (was only under
                    # record_both_reasons) — which rule executed, which also triggered, and
                    # the governing policy — so a reviewer can reconstruct the tie-break.
                    _emit(
                        "stop_exit_collision",
                        event_time=bar.timestamp,
                        direction=position.direction,
                        bar_seq=bars_seen,
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
                        _close(bar.timestamp, bar.close, "exit_signal", position, bar_seq=bars_seen)
                    else:
                        assert stop_outcome is not None  # implied by stop_touched
                        _close(
                            bar.timestamp,
                            stop_outcome.price,
                            "stop_loss",
                            position,
                            bar_seq=bars_seen,
                        )
                        _emit_stop_resolution(stop_outcome, bar.timestamp, position.direction)
                    position = None
                elif stop_touched:
                    # An intrabar stop fires immediately and subsumes any deferred exit
                    # scheduled for later this bar (or a later bar) — the stop is hit first.
                    assert stop_outcome is not None  # implied by stop_touched
                    _close(
                        bar.timestamp, stop_outcome.price, "stop_loss", position, bar_seq=bars_seen
                    )
                    _emit_stop_resolution(stop_outcome, bar.timestamp, position.direction)
                    position = None
                    pending = None
                elif exit_wanted:
                    if exit_sched == "immediate":
                        _close(bar.timestamp, bar.close, "exit_signal", position, bar_seq=bars_seen)
                        position = None
                    else:
                        # Defer the exit to the next bar's open / close (F-07a); trace the
                        # scheduling decision so the two-phase timing is reconstructable.
                        _emit(
                            "exit_scheduled",
                            event_time=bar.timestamp,
                            direction=position.direction,
                            bar_seq=bars_seen,
                            detail={
                                "position_seq": position.position_seq,
                                "reason": "exit_signal",
                                "timing": config.data.execution.exit_timing,
                                "target_bar_seq": bars_seen + 1,
                            },
                        )
                        pending = _Pending(
                            "exit", exit_sched == "next_open", bars_seen + 1, "", "exit_signal"
                        )
            elif timing_ok and pending is None:
                # Flat and uncommitted: evaluate a fresh entry, then open now (immediate)
                # or schedule the fill for the next bar (deferred). ``timing_ok`` is the
                # fail-closed backstop — an unsupported timing opens nothing (F-07a).
                want: str | None = None
                if plan_active:
                    # (3a) real indicator entry, respecting the direction bias.
                    if entry_signal is not None:
                        if (entry_signal == "long" and not long_ok) or (
                            entry_signal == "short" and not short_ok
                        ):
                            suppressed_entries += 1
                            _emit(
                                "filtered_no_entry",
                                event_time=bar.timestamp,
                                direction=entry_signal,
                                bar_seq=bars_seen,
                                detail={
                                    "reason": "direction_restriction",
                                    "direction_mode": config.position_entry_logic.direction_mode,
                                },
                            )
                        else:
                            want = entry_signal
                elif len(window) == _BREAKOUT_WINDOW:
                    # (3b) breakout entry proxy, with a full look-back.
                    highest = max(b.high for b in window)
                    lowest = min(b.low for b in window)
                    want_long = bar.close > highest
                    want_short = bar.close < lowest
                    if (want_long and not long_ok) or (want_short and not short_ok):
                        suppressed_entries += 1
                        _emit(
                            "filtered_no_entry",
                            event_time=bar.timestamp,
                            direction="long" if want_long else "short",
                            bar_seq=bars_seen,
                            detail={
                                "reason": "direction_restriction",
                                "direction_mode": config.position_entry_logic.direction_mode,
                            },
                        )
                    elif want_long or want_short:
                        # long wins a same-bar tie (deterministic); sides are exclusive.
                        want = "long" if want_long else "short"
                if want is not None:
                    # F-10: the entry DECISION (signal fired + bias allowed), carrying the
                    # evaluated rule id(s) and each nested condition's pass/fail — distinct
                    # from the ``entry_fill`` execution event (doc 15 §16).
                    _emit(
                        "entry_signal",
                        event_time=bar.timestamp,
                        direction=want,
                        bar_seq=bars_seen,
                        detail={"rule": _entry_rule_snapshot(want)},
                    )
                    if entry_sched == "immediate":
                        position = _do_open(want, bar, bar.close, bar_seq=bars_seen, deferred=False)
                    else:
                        _emit(
                            "entry_scheduled",
                            event_time=bar.timestamp,
                            direction=want,
                            bar_seq=bars_seen,
                            detail={
                                "timing": config.data.execution.entry_timing,
                                "target_bar_seq": bars_seen + 1,
                            },
                        )
                        pending = _Pending(
                            "entry", entry_sched == "next_open", bars_seen + 1, want, ""
                        )

            # (4) Resolve a fill deferred to THIS bar's CLOSE (next_candle_close). Runs at
            # end-of-bar so an intrabar stop (above) pre-empts a scheduled close exit, and
            # so a pending set THIS bar (target bars_seen+1) is never resolved early.
            if pending is not None and pending.target_seq == bars_seen and not pending.at_open:
                if pending.kind == "entry" and position is None:
                    deferred_entry_fills += 1
                    position = _do_open(
                        pending.direction, bar, bar.close, bar_seq=bars_seen, deferred=True
                    )
                elif pending.kind == "exit" and position is not None:
                    deferred_exit_fills += 1
                    _close(bar.timestamp, bar.close, pending.reason, position, bar_seq=bars_seen)
                    position = None
                pending = None

            # (6) F-11 funding cost — a backward/as-of join over the available-time-safe
            # schedule (doc 12 §8.4 rule 3). Every funding record now AVAILABLE at this bar
            # (``available_at <= bar_time``) fires exactly once; while a position is held it
            # charges ``notional * rate`` (a long pays a positive rate, a short receives),
            # reducing equity mid-run so funding-on and funding-off produce a verifiably
            # different result. A record dated after the last replayed bar never fires — a
            # future value can never leak into the run. Records that become available while
            # flat are consumed without a charge: funding is paid only for the interval the
            # position is actually held (perp funding convention). An unparseable bar
            # timestamp fires nothing this bar rather than draining the schedule (no leak).
            if funding_records:
                bar_time = parse_utc(bar.timestamp)
                if bar_time is not None:
                    while (
                        funding_idx < len(funding_records)
                        and funding_records[funding_idx].available_at <= bar_time
                    ):
                        rec = funding_records[funding_idx]
                        funding_idx += 1
                        if position is None:
                            continue
                        fsign = _ONE if position.direction == "long" else -_ONE
                        charge = (position.entry_notional * rec.rate * fsign).quantize(_MONEY)
                        if charge != _ZERO:
                            equity = (equity - charge).quantize(_MONEY)
                            peak = max(peak, equity)
                            funding_paid += charge
                        funding_charges += 1
                        _emit(
                            "funding_charge",
                            event_time=bar.timestamp,
                            direction=position.direction,
                            bar_seq=bars_seen,
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

            window.append(bar)

    # End-of-data: close any open position at the last bar's close (never left dangling).
    if position is not None and last_bar is not None:
        _close(last_bar.timestamp, last_bar.close, "end_of_data", position, bar_seq=bars_seen)
        position = None

    total_trades = len(trades)
    net_profit = (equity - initial_capital).quantize(_MONEY)
    net_profit_pct = (
        (net_profit / initial_capital * _HUNDRED).quantize(_PCT)
        if initial_capital > _ZERO
        else None
    )
    max_drawdown = max((p.drawdown for p in equity_points), default=_ZERO)
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

    summary: dict[str, Any] = {
        "symbol": config.data.instrument_id,
        "timeframe": timeframe,
        # F-05: the ACTUAL first/last bar timestamps replayed (post-filter), never
        # the requested config.data.backtest_range bounds — proves the manifest
        # range matches the data actually processed (spec F-05 acceptance).
        "period_start": first_ts or None,
        "period_end": last_bar.timestamp if last_bar is not None else None,
        "initial_capital": initial_capital,
        "final_equity": equity,
        "net_profit": net_profit,
        "net_profit_pct": net_profit_pct,
        "max_drawdown": max_drawdown.quantize(_MONEY),
        "max_drawdown_pct": max_drawdown_pct,
        "romad": romad,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_trades": total_trades,
        "total_stops": stops_hit,
        "max_stop_streak": max_stop_streak,
        "total_winning_trades": winners,
        # F-11: cumulative signed funding cost booked against equity (positive = net paid).
        # Already reflected in ``final_equity`` / ``net_profit``; surfaced so the funding
        # contribution is auditable on its own.
        "funding_paid": funding_paid.quantize(_MONEY),
    }
    warnings: list[str] = []
    if not bars_seen:
        warnings.append("no_bars_in_source")
    if not sizing_ok:
        # formula sizing (and a risk_based request without its sub-config) is not
        # modelled; the run opened NO position (fail closed, F-09) rather than a
        # notional all-in. Surface the divergence rather than hide it (L4).
        # risk_based_sizing with a sub-config IS honored.
        warnings.append(f"position_sizing_method_unsupported:{config.position_sizing.method}")
    if not timing_ok:
        # An unsupported entry/exit execution timing (intrabar_touch / a limit or
        # stop-limit simulation) is not modelled over plain OHLCV; the run opened NO
        # position (fail closed, F-07a) rather than silently filling at the candle
        # close. Ready Check raises STRATEGY_EXECUTION_TIMING_UNSUPPORTED — this L4
        # warning is the engine backstop when a stale readiness state reaches the worker.
        execution = config.data.execution
        warnings.append(
            f"execution_timing_unsupported:{execution.entry_timing}/{execution.exit_timing}"
        )
    if indicator_plan is not None:
        # Blocks the native-trigger foundation could not compute (deferred sources,
        # timeframe overrides, non-directional keys) are surfaced, never hidden (L4).
        warnings.extend(indicator_plan.unresolved)
        if not plan_active:
            warnings.append("indicator_plan_empty_fallback_proxy")
    if alloc_on:
        # FX conversion across a mixed-currency pool is out of scope (GAP-16); the run
        # assumes a single-currency portfolio pool — surfaced, never hidden (L4).
        warnings.append("allocation_single_currency_pool_assumed")
        if item_share <= _ZERO:
            # Allocation is enabled but the replayed item has no active entry → a
            # 0-capital sleeve → no fills. Surface it rather than silently fall back to
            # the strategy's own independent capital (L4).
            warnings.append("allocation_item_not_in_active_plan")
    condition_count = (
        sum(len(spec.conditions) for spec in indicator_plan.entry_specs)
        + sum(len(spec.conditions) for spec in indicator_plan.exit_specs)
        if plan_active and indicator_plan is not None
        else 0
    )
    multi_timeframe_blocks = (
        sum(1 for spec in indicator_plan.entry_specs if spec.resample_seconds)
        + sum(1 for spec in indicator_plan.exit_specs if spec.resample_seconds)
        if plan_active and indicator_plan is not None
        else 0
    )
    # Conditions whose RHS reference indicator computes on a coarser per-condition
    # timeframe than its parent block (post-V1 (i)) — surfaced for reproducibility audits.
    per_condition_timeframe_conditions = (
        sum(
            1
            for spec in (*indicator_plan.entry_specs, *indicator_plan.exit_specs)
            for cond in spec.conditions
            if cond.reference_resample_seconds
        )
        if plan_active and indicator_plan is not None
        else 0
    )
    # Conditions whose RHS is an N-ary reference chain (>2 packages compared — post-V1 (ii)):
    # source vs a monotonic fan of separately-pinned indicators — surfaced for audits.
    nary_reference_conditions = (
        sum(
            1
            for spec in (*indicator_plan.entry_specs, *indicator_plan.exit_specs)
            for cond in spec.conditions
            if cond.extra_references
        )
        if plan_active and indicator_plan is not None
        else 0
    )
    # Blocks/reference legs computed as a volume-weighted price line (VWAP — post-V1 (d)):
    # the first directional key whose compute consumes the bars' volume — surfaced for audits.
    vwap_blocks = (
        sum(
            1
            for spec in (*indicator_plan.entry_specs, *indicator_plan.exit_specs)
            if spec.canonical_key in VOLUME_WEIGHTED_KEYS
        )
        + sum(
            1
            for spec in (*indicator_plan.entry_specs, *indicator_plan.exit_specs)
            for cond in spec.conditions
            if cond.reference_key in VOLUME_WEIGHTED_KEYS
            or any(leg.key in VOLUME_WEIGHTED_KEYS for leg in cond.extra_references)
        )
        if plan_active and indicator_plan is not None
        else 0
    )
    entry_model = BUILTIN_ENTRY_MODEL if plan_active else ENTRY_MODEL
    reproducibility_note = (
        "Deterministic bar-replay over the pinned market revision; real bars, "
        "protection stops and built-in indicator native triggers."
        if plan_active
        else "Deterministic bar-replay over the pinned market revision; real bars and "
        "protection stops, breakout entry proxy (indicator layer still stubbed)."
    )
    diagnostics = {
        "engine_kind": "v1_bar_replay",
        "entry_model": entry_model,
        "reproducibility_note": reproducibility_note,
        "bars_processed": bars_seen,
        "breakout_window": _BREAKOUT_WINDOW,
        "indicator_blocks": len(entry_evals),
        "condition_blocks": condition_count,
        "multi_timeframe_blocks": multi_timeframe_blocks,
        "per_condition_timeframe_conditions": per_condition_timeframe_conditions,
        "nary_reference_conditions": nary_reference_conditions,
        "vwap_blocks": vwap_blocks,
        "position_size_limits_active": config.position_sizing.position_size_limits is not None,
        "entry_timing": config.data.execution.entry_timing,
        "exit_timing": config.data.execution.exit_timing,
        "execution_timing_modelled": timing_ok,
        "deferred_entry_fills": deferred_entry_fills,
        "deferred_exit_fills": deferred_exit_fills,
        "stop_exit_conflict": stop_exit_conflict,
        "stop_exit_collisions": stop_exit_collisions,
        "logic_stop_blocks": len(stop_evals),
        "stop_trigger_requirement": stop_trigger_requirement,
        "stop_conflict_resolution": stop_conflict_resolution,
        "logic_stop_triggers": logic_stop_triggers,
        "allocation_enabled": alloc_on,
        "allocation_compounding": ("compound" if alloc_compound else "fixed") if alloc_on else None,
        "allocation_items_executed": 1 if (alloc_on and item_share > _ZERO) else 0,
        "allocation_sleeve_cap_active": alloc_on and item_share > _ZERO,
        # F-11: funding provenance + application counts (the used revision is pinned in the
        # manifest via the strategy config; surfaced here for the decision-trace audit).
        "funding_enabled": funding is not None,
        "funding_source_revision_id": funding.source_revision_id if funding is not None else None,
        "funding_records": len(funding_records),
        "funding_charges": funding_charges,
        "item_count": item_count,
        "decision_trace_count": len(signal_events),
        "decision_trace_schema": DECISION_TRACE_SCHEMA,
        "decision_trace_event_types": list(DECISION_TRACE_EVENT_TYPES),
        "unmodelled_decision_classes": list(UNMODELLED_DECISION_CLASSES),
        "suppressed_entries": suppressed_entries,
        "execution_key": execution_key,
        "warnings": warnings,
    }
    return EngineOutput(
        summary=summary,
        trades=trades,
        equity_points=equity_points,
        signal_events=signal_events,
        diagnostics=diagnostics,
    )


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
)

# Sequential composite curve is NOT a unified-clock portfolio valuation (each strategy
# still replays over its own bar axis, then its realized PnL is concatenated onto the
# portfolio equity in deterministic pin order). A genuine multi-item co-simulation over
# one clock across heterogeneous bar sources stays deferred — surfaced, never hidden (L4).
COMPOSITION_CURVE_WARNING = "portfolio_curve_sequential_not_unified_clock"


def combine_item_runs(
    runs: list[ItemRun],
    *,
    portfolio_initial_capital: Decimal,
    execution_key: str,
    item_count: int,
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
                    "net_profit": None,
                    "total_trades": 0,
                    "winning_trades": 0,
                    "trade_seq_range": None,
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
                "net_profit": run_net,
                "total_trades": len(out.trades),
                "winning_trades": run_winners,
                "trade_seq_range": [lo_seq, hi_seq] if out.trades else None,
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
    diagnostics = {
        "engine_kind": "v1_bar_replay_composition",
        "entry_model": next(iter(entry_models)) if len(entry_models) == 1 else "mixed",
        "reproducibility_note": (
            "Deterministic per-strategy bar-replay over each pinned market revision, "
            "composed in deterministic manifest pin order into one portfolio result."
        ),
        "item_count": item_count,
        "decision_trace_count": len(combined_events),
        "composition": {
            "strategy_count": len(executing),
            "participating_item_count": len(runs),
            "items": per_item,
        },
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


__all__ = [
    "COMPOSITION_CURVE_WARNING",
    "DECISION_TRACE_EVENT_TYPES",
    "DECISION_TRACE_SCHEMA",
    "ENTRY_MODEL",
    "UNMODELLED_DECISION_CLASSES",
    "AllocationExecution",
    "EngineOutput",
    "EquityPoint",
    "ItemRun",
    "SignalEventRow",
    "TradeRow",
    "combine_item_runs",
    "execution_timing_is_modelled",
    "resolve_allocation_execution",
    "run_engine",
    "sizing_is_modelled",
]
