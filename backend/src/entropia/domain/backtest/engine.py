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
from datetime import date
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
        RestrictionFilter,
        StopOrderDetails,
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
    "funding_charge",  # a funding rate applied to the open position (F-11, doc 12 §8.4)
)
# Honest V1 boundary: the bar-replay engine cannot model a partial FILL (OHLCV carries no
# volume-at-price / order book, so the filled fraction of a limit order is unknowable) —
# surfaced, never fabricated as a phantom event. ``partial_close`` IS modelled (F-07c
# ``close_percentage``) and ``same_direction_scaling`` IS modelled (F-07d price-distance
# layers), so both left this list.
UNMODELLED_DECISION_CLASSES = ("partial_fill",)


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
    within the validity window. ``expires_seq`` is the last ``bars_seen`` index the order is
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
    expires_seq: int | None  # last live bars_seen index (None = until_cancelled)
    # F-07g: the signal bar's strength multiplier — a limit fill (touch or convert-to-
    # market) inherits its SIGNAL bar's strength (the F-07e restriction-verdict
    # precedent), never re-priced at the fill bar. Inert 1x when no adjustment is active.
    strength: Decimal = _ONE


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


# §10.2 Exposure & leverage (post-V1 (f), Master Ref §10.2). 'No Leverage' normalizes to
# 1x regardless of the saved ``leverage`` value (spec: "No Leverage modunda 1x olarak
# normalize edilir"). 'Isolated' applies the saved positive multiplier directly to this
# position's computed size — the single-position bar-replay engine already isolates each
# position's risk to itself (nothing else is open concurrently to share margin with),
# which is exactly what isolated-margin semantics require. 'Cross' shares margin/risk
# across concurrently open positions via a portfolio-level risk model the engine does not
# implement (Master Ref §10.2: cross-margin logic depends on the Equity Allocation /
# portfolio risk model) — NOT modelled, fails closed rather than silently degrading to
# isolated semantics.
def leverage_is_modelled(config: StrategyConfig) -> bool:
    """Public predicate: is this strategy's leverage configuration modelled (F-07f)?

    The single shared source of truth for the readiness ``STRATEGY_LEVERAGE_UNSUPPORTED``
    blocker and the engine's fail-closed entry gate. 'No Leverage' is always modelled
    (normalizes to 1x); 'Isolated' is modelled when the saved ``leverage`` multiplier is
    a positive value (schema-enforced ``gt=0``, re-checked here defensively); 'Cross' is
    never modelled — blocked at Ready Check AND opens no position if a stale readiness
    state slips through to the worker (never a silently un-leveraged or mis-leveraged
    run)."""
    sizing = config.position_sizing
    if sizing.leverage_mode == "no_leverage":
        return True
    if sizing.leverage_mode == "cross":
        return False
    return sizing.leverage > _ZERO


def _leverage_multiplier(config: StrategyConfig) -> Decimal:
    """The resolved leverage multiplier (only called once ``leverage_is_modelled`` has
    gated position opening, so every branch here is safe/defined)."""
    sizing = config.position_sizing
    if sizing.leverage_mode == "no_leverage":
        return _ONE
    return Decimal(sizing.leverage)


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


# §2 Order type execution modelled by the deterministic OHLCV bar-replay (F-07b). The
# engine previously IGNORED ``order_config`` and always filled at market — a strategy
# configured for a Limit Order silently got a market fill. Now:
#   * ``market_order`` / ``simulation_only`` → a market fill at the timing-chosen price
#     (simulation_only is doc 02's "simplified virtual fill to test the entry logic" — a
#     backtest fill IS that virtual fill, so it is byte-identical to a market order).
#   * ``limit_order`` → a resting working order (``_WorkingLimit``) that fills only if a
#     later bar reaches the signal-derived limit within the validity window, then applies
#     the unfilled policy.
#   * ``stop_order`` → a resting stop trigger (``_WorkingStop``, F-07h): fires when a later
#     bar reaches the signal-derived trigger, then fills market-like at max(trigger, open)
#     (long; short mirror) — a gap through the trigger fills at the open.
#   * ``stop_limit_order`` → the same trigger, which on firing ARMS the F-07b limit machine:
#     the limit rests from the NEXT bar (same-bar stop-vs-limit ordering needs tick data —
#     never modelled over OHLCV) with validity/unfilled policy applied verbatim.
#   * a stop/stop-limit with NO ``stop`` subtree or an offset activation rule missing its
#     ``trigger_offset``, a ``limit_order``/stop-limit whose ``price_rule`` is
#     ``best_bid_ask`` (needs a bid/ask quote series, absent over OHLCV), and a
#     ``partial_fill_policy`` other than ``not_allowed`` all FAIL CLOSED (never a silent
#     full/market fill).
_MARKET_ORDER_TYPES = frozenset({"market_order", "simulation_only"})
_MODELLED_LIMIT_PRICE_RULES = frozenset(
    {"entry_signal_price", "signal_price_minus_offset", "signal_price_plus_offset"}
)
# F-07h: the stop activation rules the trigger model executes — the same signal-derived
# shapes as the limit price rules (the schema's ``StopOrderDetails.activation_rule``
# Literal). An offset rule without its ``trigger_offset`` is an invalid trigger → not
# modelled (fail closed), mirroring the schema's conditional requiredness.
_MODELLED_STOP_ACTIVATION_RULES = frozenset(
    {"entry_signal_price", "signal_price_minus_offset", "signal_price_plus_offset"}
)
_OFFSET_ACTIVATION_RULES = frozenset({"signal_price_minus_offset", "signal_price_plus_offset"})
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


def _stop_trigger_is_modelled(stop: StopOrderDetails | None) -> bool:
    """Is a stop trigger derivable from the saved ``stop`` subtree (F-07h)?

    Requires the subtree itself (a triggerless stop is unexecutable), a modelled
    activation rule, and — for the offset rules — a present ``trigger_offset``."""
    if stop is None or stop.activation_rule not in _MODELLED_STOP_ACTIVATION_RULES:
        return False
    return not (stop.activation_rule in _OFFSET_ACTIVATION_RULES and stop.trigger_offset is None)


def order_execution_is_modelled(config: StrategyConfig) -> bool:
    """Public predicate: is this strategy's order-type execution modelled (F-07b/F-07h)?

    The single shared source of truth imported by the readiness validator so Ready Check's
    ``STRATEGY_ORDER_TYPE_UNSUPPORTED`` blocker and the engine's fail-closed entry gate
    agree on exactly one definition. market / simulation → market fill; limit → the
    working-order model (a modelled price rule + a ``not_allowed`` partial-fill policy);
    stop → the resting-trigger model (a modelled activation rule with its offset);
    stop-limit → the trigger model AND the limit working-order model (both legs). A missing
    /invalid trigger, a ``best_bid_ask`` price rule, or a non-``not_allowed`` partial-fill
    policy → NOT modelled (blocked at Ready Check AND opens no position if a stale readiness
    state reaches the worker)."""
    order = config.data.order_config
    if order.type in _MARKET_ORDER_TYPES:
        return True
    if order.type == "limit_order":
        limit = order.limit
        return (
            limit is not None
            and limit.price_rule in _MODELLED_LIMIT_PRICE_RULES
            and limit.partial_fill_policy == "not_allowed"
        )
    if order.type == "stop_order":
        return _stop_trigger_is_modelled(order.stop)
    if order.type == "stop_limit_order":
        limit = order.limit
        return (
            _stop_trigger_is_modelled(order.stop)
            and limit is not None
            and limit.price_rule in _MODELLED_LIMIT_PRICE_RULES
            and limit.partial_fill_policy == "not_allowed"
        )
    return False


# §4 Partial-close aftermath modelled by the bar-replay (F-07c). ``close_percentage`` < 100
# closes only that fraction of the position on an EXIT SIGNAL and holds the remainder; the
# aftermath governs the remainder. ``move_stop_to_entry`` (breakeven the remainder's stop) and
# ``close_all`` (the signal closes 100% regardless) are deterministic over OHLCV. A
# ``move_stop_to_entry`` / ``lock_in_profit`` need no extra strategy config (they mutate the
# remainder's stop from data already on the open position). A full close (close_percentage
# == 100) never produces a remainder, so its aftermath is irrelevant and always modelled.
# ``trailing_stop`` is CONFIG-DEPENDENT (post-V1 (f)): the schema carries no separate
# trailing-distance/activation fields on ``PositionExitLogic`` itself, so the aftermath
# reuses ``protection_stop_logic.trailing_stop`` — modelled only when that rule is
# configured/enabled (checked in ``partial_close_is_modelled`` via ``_trail_pct``).
_MODELLED_PARTIAL_AFTERMATHS = frozenset({"move_stop_to_entry", "close_all", "lock_in_profit"})


def partial_close_is_modelled(config: StrategyConfig) -> bool:
    """Public predicate: is this strategy's partial-close behaviour modelled (F-07c/f)?

    The single shared source of truth for the readiness ``STRATEGY_PARTIAL_CLOSE_UNSUPPORTED``
    blocker and the engine's fail-closed entry gate. A full close (``close_percentage`` >= 100)
    is always modelled. A partial close is modelled when its aftermath is move-stop-to-entry,
    close-all or lock-in-profit (self-contained — no extra config needed), or trailing-stop
    WHEN the strategy's own ``protection_stop_logic.trailing_stop`` rule is configured and
    enabled (the aftermath has no trailing parameters of its own to reuse). A trailing-stop
    aftermath with no such rule configured fails closed (blocked at Ready Check AND opens no
    position if a stale readiness state slips through to the worker)."""
    exit_logic = config.position_exit_logic
    if exit_logic.close_percentage >= _HUNDRED:
        return True
    aftermath = exit_logic.partial_aftermath
    if aftermath in _MODELLED_PARTIAL_AFTERMATHS:
        return True
    if aftermath == "trailing_stop":
        return _trail_pct(config) is not None
    return False


# §7 Same-direction scaling modelled by the bar-replay (F-07d, Master Ref §11). The engine
# previously never scaled: a saved scaling config was silently ignored. Now PRICE-DISTANCE
# scaling on the strategy's own timeframe is executed as a deterministic ladder — each
# ``retracement_distance``% adverse close from the reference (initial entry, then the
# previous trigger close) creates ONE layer candidate; candidates pass the layer-count caps
# at CREATION (a capped ladder simply generates no candidate, §11.4 "yeni layer oluşturulmaz")
# and the exposure/size caps at ACCEPTANCE (an over-cap layer is REJECTED with a ledger
# reason, never auto-trimmed — §11.4 exposure binding). NOT modelled (fail closed):
#   * ``logic_based_scaling`` — needs separate scale-rule evaluators (a later slice);
#   * a scaling ``timeframe`` other than ``same_as_base_tf`` (increasing-by-layer / custom
#     TF sequence) — needs per-layer resampled evaluation;
#   * a missing / non-positive ``add_size_value`` (no layer size is derivable);
#   * a negative ``max_scaling_layers`` or a non-positive ``max_total_position_size``
#     (misconfigurations the schema does not reject — spec §11.4 requires int >= 0).
# ``enabled=false`` / an absent subtree is trivially modelled (nothing to scale — the
# disabled-section filter collapses it to None; byte-identical baseline).


def scaling_is_modelled(config: StrategyConfig) -> bool:
    """Public predicate: is this strategy's same-direction scaling modelled (F-07d)?

    The single shared source of truth for the readiness ``STRATEGY_SCALING_UNSUPPORTED``
    blocker and the engine's fail-closed entry gate. Disabled/absent scaling is always
    modelled; enabled scaling is modelled only as the price-distance ladder on the
    strategy's own timeframe with a derivable positive add size and sane caps — anything
    else is blocked at Ready Check AND opens no position if a stale readiness state slips
    through to the worker (never a silently un-scaled run the user did not configure)."""
    scaling = config.scaling_logic
    if scaling is None or not scaling.enabled:
        return True
    if scaling.timeframe != "same_as_base_tf":
        return False
    if scaling.method != "price_distance_scaling" or scaling.price_scaling is None:
        return False
    if scaling.add_size_value is None or scaling.add_size_value <= _ZERO:
        return False
    limits = scaling.scaling_limits
    if limits is not None:
        if limits.max_scaling_layers is not None and limits.max_scaling_layers < 0:
            return False
        if limits.max_total_position_size is not None and limits.max_total_position_size <= _ZERO:
            return False
    return True


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


def _limit_price(price_rule: str, reference: Decimal, offset: Decimal) -> Decimal:
    """Resolve a limit level from a price rule + reference price + offset (F-07b).

    ``entry_signal_price`` rests at the reference (the signal / re-price bar's close);
    ``signal_price_minus_offset`` / ``_plus_offset`` shift it by the configured magnitude."""
    if price_rule == "signal_price_minus_offset":
        return reference - offset
    if price_rule == "signal_price_plus_offset":
        return reference + offset
    return reference


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


def _position_size(
    config: StrategyConfig,
    entry_price: Decimal,
    equity: Decimal,
    strength: Decimal = _ONE,
) -> Decimal:
    """Deterministic sizing (see ``_raw_position_size``), scaled by the leverage
    multiplier (§10.2, post-V1 (f) — a leveraged strategy controls MORE notional per
    unit of computed capital, so the multiplier scales the SIZE itself, which scales
    every downstream notional/exposure/PnL figure with it) and by the signal-strength
    multiplier (§10.3, F-07g — the SIGNAL bar's strength scales every signal-driven
    entry size; 1x for non-signal callers), then clamped to the configured
    ``position_size_limits`` min/max caps (§6). All three apply uniformly to EVERY
    sizing method — base, risk-based, Kelly and the notional fallback — so a global
    cap, leverage and strength are honoured regardless of which sizing path produced
    the size, and the LIMITS remain the final word (a strength-boosted size is still
    capped). Only called once ``leverage_is_modelled`` / ``signal_strength_is_modelled``
    have gated position opening, so both multipliers are always well-defined here. A 1x
    multiplier and a missing limits subtree are both no-ops, so behaviour is
    byte-identical to the pre-wiring engine."""
    size = _raw_position_size(config, entry_price, equity)
    if size > _ZERO:
        size = size * _leverage_multiplier(config) * strength
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


def _trail_lock_in_pct(config: StrategyConfig) -> Decimal | None:
    """Trailing stop's profit-lock ACTIVATION threshold, as a fraction of entry price
    (Master Ref §9.2 "Activate After Profit %", post-V1 (f)). Mirrors ``_trail_pct``:
    ``None`` when trailing is not configured/enabled."""
    protection = config.protection_stop_logic
    if protection is None or protection.trailing_stop is None:
        return None
    trailing = protection.trailing_stop
    return trailing.lock_in_percentage / _HUNDRED if trailing.enabled else None


def _trailing_activated(position: _Position) -> bool:
    """Has the trailing stop's profit-lock activation threshold been reached?

    ``trail_anchor`` tracks the favourable extreme UNCONDITIONALLY from entry (a
    monotonic ratchet — see the bar loop), but the trailing rule contributes NO stop
    level until the position's profit reaches ``lock_in_percentage`` (post-V1 (f)):
    before activation there is simply no trailing protection, only whichever other
    stop rules are enabled. Deriving activation from ``trail_anchor`` (rather than a
    separate mutable flag) is what makes the lock "never retreat": once
    ``trail_anchor`` has crossed the threshold it can only move further favourably,
    so the derived trailing level can only tighten, never loosen or deactivate."""
    if position.trail_pct is None or position.trail_lock_in_pct is None:
        return False
    entry = position.entry_price
    if position.direction == "long":
        return position.trail_anchor >= entry * (_ONE + position.trail_lock_in_pct)
    return position.trail_anchor <= entry * (_ONE - position.trail_lock_in_pct)


def _trailing_level(position: _Position) -> Decimal | None:
    """Current trailing-stop level from the favourable extreme, or ``None`` when
    trailing is not configured OR its activation threshold has not yet been reached."""
    if position.trail_pct is None or not _trailing_activated(position):
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
    # F-07f: trailing stop profit-lock activation threshold (Master Ref §9.2 "Activate
    # After Profit %") — mirrors ``trail_pct``, threaded into every opened position.
    trail_lock_in_pct = _trail_lock_in_pct(config)
    trailing_lock_in_active = trail_lock_in_pct is not None
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
    if scaling_active and scaling_cfg is not None and scaling_cfg.price_scaling is not None:
        price_scaling = scaling_cfg.price_scaling
        scale_distance = price_scaling.retracement_distance
        # The method's planned ladder depth, further capped by the optional global limit
        # (§11.4 Max Additional Layers, int >= 0 — 0 legally disables the ladder).
        scale_max_layers = price_scaling.layers
        scale_limits = scaling_cfg.scaling_limits
        if scale_limits is not None and scale_limits.max_scaling_layers is not None:
            scale_max_layers = min(scale_max_layers, scale_limits.max_scaling_layers)
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
    restrictions_ok = restrictions_are_modelled(config)
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
    working_limit: _WorkingLimit | None = None  # a resting limit ENTRY order (F-07b)
    working_stop: _WorkingStop | None = None  # a resting stop ENTRY trigger (F-07h)
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
    limit_orders_placed = 0
    limit_orders_filled = 0
    limit_orders_cancelled = 0
    # F-07h: stop-trigger lifecycle counts (a stop-limit's armed limit leg then counts
    # through the limit_orders_* counters — the two machines compose, never double-count).
    stop_orders_placed = 0
    stop_orders_triggered = 0
    stop_orders_cancelled = 0
    partial_closes = 0
    # F-07f: count of partial-close aftermaths that locked in profit on the remainder
    # (``lock_in_profit`` moving the stop to the current price, or ``trailing_stop``
    # force-activating the trailing rule) — surfaced as a diagnostics count.
    lock_in_locks = 0
    # F-07g: count of signal-driven entry decisions whose computed strength multiplier
    # was NOT the neutral 1x (flat entries, deferred/limit entries at their signal bar,
    # and conflict-driven stack/replace entries) — surfaced as a diagnostics count.
    strength_adjustments = 0
    scale_layers_added = 0
    scale_layers_rejected = 0
    # F-07e: restriction-gate + conflict-policy counters and their realized-ledger state.
    # ``current_day`` / ``day_realized`` track the UTC calendar day's realized trade PnL
    # (max-daily-loss basis); ``loss_streak`` counts consecutive realized losing lots
    # (consecutive-loss basis); ``prev_entry_signal`` detects a NEW aggregated signal EDGE
    # (a held signal is one entry event, never a per-bar stack/replace/ignore storm).
    entries_blocked_by_restriction = 0
    stack_entries_added = 0
    stack_entries_rejected = 0
    positions_replaced = 0
    opposite_signal_closes = 0
    conflict_signals_ignored = 0
    current_day: date | None = None
    day_realized = _ZERO
    loss_streak = 0
    prev_entry_signal: str | None = None
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
        if not leverage_ok:
            return "leverage_unsupported"
        if not strength_ok:
            return "signal_strength_unsupported"
        if alloc_on:
            return "sleeve_zero_capacity"
        return "no_fill"

    def _signal_strength(bar: _Bar) -> Decimal:
        """The strength multiplier at THIS signal bar (F-07g, §10.3).

        Computed at DECISION time from the bars already replayed (``window`` holds the
        prior look-back; the signal bar itself is complete at its close) — look-back
        only, no look-ahead. Inert (exactly 1x, zero extra work) unless the
        ``volatility_adjusted`` mode is active, so every other mode stays
        byte-identical. A non-neutral multiplier is counted for diagnostics."""
        nonlocal strength_adjustments
        if not strength_active:
            return _ONE
        multiplier = _volatility_strength((*window, bar))
        if multiplier != _ONE:
            strength_adjustments += 1
        return multiplier

    def _close(
        exit_time: str,
        exit_price_raw: Decimal,
        reason: str,
        pos: _Position,
        *,
        bar_seq: int,
        fraction: Decimal = _ONE,
    ) -> bool:
        """Close ``fraction`` of the position; return True iff it is now FULLY closed.

        A partial close (fraction < 1, F-07c ``close_percentage``) realizes PnL on
        ``size * fraction`` as its own trade lot, reduces the position's size + notional in
        place, and leaves it OPEN — the caller must not null it and applies the aftermath.
        Commission is charged proportional to the fraction so N partial lots summing to the
        whole position pay exactly one round-trip. ``fraction >= 1`` is a full close, byte-
        identical to pre-F-07c (same event type + detail)."""
        nonlocal equity, peak, winners, stops_hit, stop_streak, max_stop_streak
        nonlocal gross_profit, gross_loss, partial_closes, day_realized, loss_streak
        is_full = fraction >= _ONE
        close_size = pos.size if is_full else pos.size * fraction
        is_long = pos.direction == "long"
        exit_eff = _effective_fill(
            exit_price_raw, is_buy=not is_long, half_spread=half_spread, slip=slippage
        )
        sign = Decimal("1") if is_long else Decimal("-1")
        gross = (exit_eff - pos.entry_price) * close_size * sign
        commission_lot = commission * 2 if is_full else commission * 2 * fraction
        pnl = (gross - commission_lot).quantize(_MONEY)
        equity_before = equity
        equity = (equity + pnl).quantize(_MONEY)
        peak = max(peak, equity)
        drawdown = (peak - equity).quantize(_MONEY)
        closed_notional = (pos.entry_price * close_size).quantize(_MONEY)
        exposure = (
            (closed_notional / equity_before * _HUNDRED).quantize(_PCT)
            if equity_before > _ZERO
            else _ZERO.quantize(_PCT)
        )
        if pnl > _ZERO:
            winners += 1
            gross_profit += pnl
        else:
            gross_loss += -pnl
        # F-07e: the restriction filters' realized ledger. Every realized lot (full or
        # partial) books into the UTC day's PnL; a strictly negative lot extends the
        # consecutive-loss streak, anything else (a 0-PnL lot is not a loss) resets it.
        day_realized += pnl
        if pnl < _ZERO:
            loss_streak += 1
        else:
            loss_streak = 0
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
                exit_reason=reason if is_full else "partial_exit",
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
        if not is_full:
            partial_closes += 1
            pos.size = pos.size - close_size
            pos.entry_notional = (pos.entry_price * pos.size).quantize(_MONEY)
        # F-10: the position CLOSE decision — links the lifecycle to its immutable trade row
        # (``trade_seq``), the exit reason, the realized pnl and the holding span so a reviewer
        # reconstructs exactly why/when the position closed. A partial close emits
        # ``position_partial_close`` with the closed fraction + remaining size; a FULL close's
        # event type + detail are byte-identical to pre-F-07c.
        partial_detail = (
            {} if is_full else {"closed_fraction": str(fraction), "remaining_size": str(pos.size)}
        )
        _emit(
            "position_close" if is_full else "position_partial_close",
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
                **partial_detail,
            },
        )
        return is_full

    def _apply_partial_aftermath(pos: _Position, exit_price_raw: Decimal) -> None:
        """Govern the remainder after a partial close (F-07c/f §4). ``move_stop_to_entry``
        breakevens the remainder's percentage stop (any dip back to the entry now stops it
        out). ``lock_in_profit`` moves the stop to the cost-adjusted price achieved AT this
        partial close — a one-time ratchet: a LATER partial close (long via ``max``, short
        via ``min``) can only tighten it further, never loosen it (never reaches here
        without a prior stop level, so the initial application always sets it verbatim).
        ``trailing_stop`` force-activates the remainder's already-configured protection
        trailing stop (``partial_close_is_modelled`` guarantees ``trail_pct`` /
        ``trail_lock_in_pct`` are set whenever this branch is reachable) immediately, even
        if the protection-level profit-lock threshold has not yet been reached — the
        partial exit itself is the activation event; ``trail_anchor`` only ever moves
        toward the threshold (``max``/``min``), never backward, so it cannot loosen an
        already-active trail. ``close_all`` never reaches here (it closes fully)."""
        nonlocal lock_in_locks
        is_long = pos.direction == "long"
        if partial_aftermath == "move_stop_to_entry":
            pos.pct_stop = pos.entry_price
        elif partial_aftermath == "lock_in_profit":
            exit_eff = _effective_fill(
                exit_price_raw, is_buy=not is_long, half_spread=half_spread, slip=slippage
            )
            if pos.pct_stop is None:
                pos.pct_stop = exit_eff
            elif is_long:
                pos.pct_stop = max(pos.pct_stop, exit_eff)
            else:
                pos.pct_stop = min(pos.pct_stop, exit_eff)
            lock_in_locks += 1
        elif (
            partial_aftermath == "trailing_stop"
            and pos.trail_pct is not None
            and pos.trail_lock_in_pct is not None
        ):
            threshold = (
                pos.entry_price * (_ONE + pos.trail_lock_in_pct)
                if is_long
                else pos.entry_price * (_ONE - pos.trail_lock_in_pct)
            )
            pos.trail_anchor = (
                max(pos.trail_anchor, threshold) if is_long else min(pos.trail_anchor, threshold)
            )
            lock_in_locks += 1

    def _sleeve_capital(current_equity: Decimal) -> Decimal:
        """The replayed item's sleeve cap Ci(t) at this valuation point (doc 13 §8.3).

        Compound: A(t) = max(0, E(t) - R0); Ci(t) = A(t) * wi / 100, where E(t) is the
        portfolio equity (which starts at P0 and accrues this item's realized PnL in the
        single-item foundation). Fixed: Ci = A0 * wi / 100 (constant)."""
        allocatable = (
            max(_ZERO, current_equity - reserve_nominal) if alloc_compound else allocatable_initial
        )
        return allocatable * item_share / _HUNDRED

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
                hit = day_realized <= -limit_amount
            else:  # consecutive_loss_filter
                assert spec.max_losses is not None  # guaranteed by _parse_restriction
                hit = loss_streak >= spec.max_losses
            if hit:
                active.append({"filter_id": spec.filter_id, "filter_type": spec.filter_type})
        return active

    def _restrictions_block(active: list[dict[str, str]]) -> bool:
        """Combine ACTIVE filters per the §12.1 rule: "any" = OR, "all" = AND."""
        if not restriction_specs:
            return False
        if restriction_rule == "all":
            return len(active) == len(restriction_specs)
        return bool(active)

    def _open(
        direction: str,
        bar: _Bar,
        fill_raw: Decimal,
        *,
        bar_seq: int,
        strength: Decimal = _ONE,
    ) -> _Position | None:
        """Open a position at the cost-adjusted fill of ``fill_raw``, or ``None`` for a
        no-fill.

        ``fill_raw`` is the raw (pre-cost) execution price chosen by the entry timing:
        the signal bar's close (immediate), or the next bar's open / close (deferred) —
        removing the hardcoded current-candle-close assumption (F-07a). ``strength`` is
        the SIGNAL bar's strength multiplier (F-07g, 1x unless volatility-adjusted
        sizing is active). Under allocation a 0-capacity sleeve (an unallocated item, or
        a compound pool busted below its reserve) yields no fill at all — ``None`` —
        rather than a phantom 0-size trade (doc 13 §8.4 step 5/6). Independent mode
        books even a bust-equity 0-size fill (preserving the risk-based
        no-phantom-profit invariant), but an UNMODELLED sizing method (F-09), leverage
        configuration (F-07f) or signal-strength mode (F-07g) opens nothing at all — no
        phantom trade for a strategy the user never validly configured."""
        if not sizing_ok or not leverage_ok or not strength_ok:
            return None
        is_long = direction == "long"
        entry_eff = _effective_fill(
            fill_raw, is_buy=is_long, half_spread=half_spread, slip=slippage
        )
        if alloc_on:
            # Strategy Details sizing/risk constraints first (within the item's sleeve),
            # then the allocation remaining-sleeve outer cap (§8.4 step 5).
            sleeve = _sleeve_capital(equity)
            desired = _position_size(config, entry_eff, sleeve, strength)
            size = _cap_to_sleeve(desired, sleeve, entry_eff)
            if size <= _ZERO:
                return None
        else:
            size = _position_size(config, entry_eff, equity, strength)
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
        )

    def _do_open(
        direction: str,
        bar: _Bar,
        fill_raw: Decimal,
        *,
        bar_seq: int,
        deferred: bool,
        strength: Decimal = _ONE,
    ) -> _Position | None:
        """Open a position AND emit the F-10 fill/blocked decision-trace event.

        On a real fill: ``entry_fill`` (the execution — position_seq, price, size, timing).
        On a no-fill: ``entry_blocked`` with the concrete reason (sizing/sleeve), so a
        signalled-but-unfilled entry is never a silent gap in the trace. ``strength`` is
        the SIGNAL bar's multiplier (F-07g), carried verbatim from the decision point."""
        pos = _open(direction, bar, fill_raw, bar_seq=bar_seq, strength=strength)
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
                    "order_type": order_cfg.type,
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
            # F-07d: an exit lot (full or partial) realized on THIS bar appends a trade row;
            # the scale ladder below never adds to a position a bar has already reduced.
            trades_before_bar = len(trades)

            # F-07e: the restriction filters' clock. The bar's UTC calendar date drives the
            # date-blackout windows and rolls the max-daily-loss accumulator at each new
            # day; an unparseable timestamp yields ``None`` (date-dependent filters then
            # fail closed) and never resets the day. Skipped entirely when no modelled
            # filter is enabled — the hot loop stays byte-identical.
            bar_date: date | None = None
            if restriction_specs:
                parsed_bar_time = parse_utc(bar.timestamp)
                bar_date = parsed_bar_time.date() if parsed_bar_time is not None else None
                if bar_date is not None and bar_date != current_day:
                    current_day = bar_date
                    day_realized = _ZERO

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
                        pending.direction,
                        bar,
                        bar.open,
                        bar_seq=bars_seen,
                        deferred=True,
                        strength=pending.strength,
                    )
                elif pending.kind == "exit" and position is not None:
                    deferred_exit_fills += 1
                    # F-07c: a deferred exit SIGNAL closes ``close_fraction`` and holds the
                    # remainder under the aftermath (a full close nulls the position).
                    if _close(
                        bar.timestamp,
                        bar.open,
                        pending.reason,
                        position,
                        bar_seq=bars_seen,
                        fraction=close_fraction,
                    ):
                        position = None
                    else:
                        _apply_partial_aftermath(position, bar.open)
                pending = None

            # (1b) Resolve a RESTING limit ENTRY order against THIS bar (F-07b). Resolves
            # before the position block (like a next_open fill), so a same-bar protective
            # stop can hit the just-filled position — consistent with the deferred-open path.
            # A touch fills at the limit; on the expiry bar an unfilled order applies its
            # policy (convert-to-market fills at the close, else cancel); otherwise a
            # re-price policy recomputes the limit from THIS bar's close for the next bar.
            if working_limit is not None and position is None:
                wl = working_limit
                touched = (
                    bar.low <= wl.limit_price
                    if wl.direction == "long"
                    else bar.high >= wl.limit_price
                )
                expired = wl.expires_seq is not None and bars_seen >= wl.expires_seq
                if touched:
                    limit_orders_filled += 1
                    position = _do_open(
                        wl.direction,
                        bar,
                        wl.limit_price,
                        bar_seq=bars_seen,
                        deferred=True,
                        strength=wl.strength,
                    )
                    working_limit = None
                elif expired:
                    if wl.unfilled_policy == "convert_to_market_order":
                        limit_orders_filled += 1
                        position = _do_open(
                            wl.direction,
                            bar,
                            bar.close,
                            bar_seq=bars_seen,
                            deferred=True,
                            strength=wl.strength,
                        )
                    else:
                        limit_orders_cancelled += 1
                        _emit(
                            "limit_order_cancelled",
                            event_time=bar.timestamp,
                            direction=wl.direction,
                            bar_seq=bars_seen,
                            detail={
                                "reason": "validity_expired",
                                "unfilled_policy": wl.unfilled_policy,
                                "limit_price": str(wl.limit_price),
                            },
                        )
                    working_limit = None
                elif wl.unfilled_policy == "re_price_next_candle":
                    wl.limit_price = _limit_price(wl.price_rule, bar.close, wl.offset)

            # (1c) Resolve a RESTING stop ENTRY trigger against THIS bar (F-07h). A long
            # buy-stop fires when the bar's high reaches the trigger (short mirror: low).
            # A plain stop then fills market-like at max(trigger, open) — a gap through
            # the trigger fills at the open (the trigger price no longer exists),
            # deterministic over OHLCV. A stop-limit instead ARMS the (1b) limit machine:
            # placed HERE (below the (1b) block), the armed limit is first examined on the
            # NEXT bar — the same-bar stop-then-limit sequence needs tick ordering, so a
            # same-bar limit touch never fills (doc 02 §5.2: the trigger may fire and the
            # position still never open). Validity counts from the trigger bar, and the
            # (1b) unfilled/re-price policies then apply verbatim.
            if working_stop is not None and position is None:
                ws = working_stop
                fired = (
                    bar.high >= ws.trigger_price
                    if ws.direction == "long"
                    else bar.low <= ws.trigger_price
                )
                if fired:
                    stop_orders_triggered += 1
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
                            bar_seq=bars_seen,
                            detail=trigger_detail,
                        )
                        position = _do_open(
                            ws.direction,
                            bar,
                            fill_price,
                            bar_seq=bars_seen,
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
                                None if ws.validity_bars is None else bars_seen + ws.validity_bars
                            ),
                            strength=ws.strength,
                        )
                        limit_orders_placed += 1
                        trigger_detail["limit_price"] = str(ws.limit_price)
                        _emit(
                            "stop_order_triggered",
                            event_time=bar.timestamp,
                            direction=ws.direction,
                            bar_seq=bars_seen,
                            detail=trigger_detail,
                        )
                        _emit(
                            "limit_order_placed",
                            event_time=bar.timestamp,
                            direction=ws.direction,
                            bar_seq=bars_seen,
                            detail={
                                "limit_price": str(ws.limit_price),
                                "price_rule": ws.limit_rule,
                                "unfilled_policy": ws.unfilled_policy,
                                "expires_bar_seq": working_limit.expires_seq,
                                "armed_by": "stop_order_triggered",
                            },
                        )
                    working_stop = None

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
                        # F-07c: an exit signal closes ``close_fraction`` and holds the
                        # remainder under the aftermath; a full close (fraction 1) nulls it.
                        if _close(
                            bar.timestamp,
                            bar.close,
                            "exit_signal",
                            position,
                            bar_seq=bars_seen,
                            fraction=close_fraction,
                        ):
                            position = None
                        else:
                            _apply_partial_aftermath(position, bar.close)
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
            elif (
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
                # Flat and uncommitted: evaluate a fresh entry, then open now (immediate),
                # schedule a deferred fill (timing), or rest a limit order. ``timing_ok``,
                # ``order_ok``, ``partial_close_ok``, ``scaling_ok``, ``restrictions_ok``
                # and ``conflict_ok`` are the fail-closed backstops — an unsupported timing /
                # order type / partial-close aftermath / scaling config / restriction filter /
                # hedge policy opens nothing (F-07a / F-07b / F-07c / F-07d / F-07e).
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
                if want is not None and restriction_specs:
                    # F-07e: the Restrictions/Filters ENTRY gate (Master Ref §12.1 "block
                    # entry"). Evaluated AFTER the signal + direction bias produced a wanted
                    # entry, so the trace shows a real signal the filters vetoed — never a
                    # phantom suppression. The gate runs at DECISION time (the signal bar);
                    # a deferred/limit fill inherits its signal bar's verdict (V1 boundary,
                    # engine-version-pinned).
                    active_filters = _active_restrictions(bar_date)
                    if _restrictions_block(active_filters):
                        entries_blocked_by_restriction += 1
                        _emit(
                            "filtered_no_entry",
                            event_time=bar.timestamp,
                            direction=want,
                            bar_seq=bars_seen,
                            detail={
                                "reason": "restriction_blocked",
                                "rule": restriction_rule,
                                "active_filters": active_filters,
                                "context": "flat_entry",
                            },
                        )
                        want = None
                if want is not None:
                    # F-07g: the SIGNAL bar's strength multiplier, computed once at the
                    # decision point (after the restriction gate — a vetoed signal never
                    # computes strength) and inherited verbatim by whichever fill path
                    # executes (immediate / deferred / limit) — never re-priced later.
                    strength = _signal_strength(bar)
                    entry_detail: dict[str, Any] = {"rule": _entry_rule_snapshot(want)}
                    if strength_active:
                        entry_detail["signal_strength"] = {
                            "mode": strength_mode,
                            "multiplier": str(strength),
                        }
                    # F-10: the entry DECISION (signal fired + bias allowed), carrying the
                    # evaluated rule id(s) and each nested condition's pass/fail — distinct
                    # from the ``entry_fill`` execution event (doc 15 §16).
                    _emit(
                        "entry_signal",
                        event_time=bar.timestamp,
                        direction=want,
                        bar_seq=bars_seen,
                        detail=entry_detail,
                    )
                    if order_is_limit:
                        # F-07b: rest a limit order at the signal-derived price; it fills
                        # only on a later touch within the validity window (resolved by the
                        # (1b) block on subsequent bars), never on this signal bar.
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
                            expires_seq=(
                                None if validity_bars is None else bars_seen + validity_bars
                            ),
                            strength=strength,
                        )
                        limit_orders_placed += 1
                        _emit(
                            "limit_order_placed",
                            event_time=bar.timestamp,
                            direction=want,
                            bar_seq=bars_seen,
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
                            stop_limit_level = _limit_price(
                                limit.price_rule, bar.close, limit_offset
                            )
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
                        stop_orders_placed += 1
                        _emit(
                            "stop_order_placed",
                            event_time=bar.timestamp,
                            direction=want,
                            bar_seq=bars_seen,
                            detail=place_detail,
                        )
                    elif entry_sched == "immediate":
                        position = _do_open(
                            want,
                            bar,
                            bar.close,
                            bar_seq=bars_seen,
                            deferred=False,
                            strength=strength,
                        )
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
                            "entry", entry_sched == "next_open", bars_seen + 1, want, "", strength
                        )

            # (4) Resolve a fill deferred to THIS bar's CLOSE (next_candle_close). Runs at
            # end-of-bar so an intrabar stop (above) pre-empts a scheduled close exit, and
            # so a pending set THIS bar (target bars_seen+1) is never resolved early.
            if pending is not None and pending.target_seq == bars_seen and not pending.at_open:
                if pending.kind == "entry" and position is None:
                    deferred_entry_fills += 1
                    position = _do_open(
                        pending.direction,
                        bar,
                        bar.close,
                        bar_seq=bars_seen,
                        deferred=True,
                        strength=pending.strength,
                    )
                elif pending.kind == "exit" and position is not None:
                    deferred_exit_fills += 1
                    # F-07c: a deferred exit SIGNAL at the close closes ``close_fraction`` and
                    # holds the remainder under the aftermath (a full close nulls the position).
                    if _close(
                        bar.timestamp,
                        bar.close,
                        pending.reason,
                        position,
                        bar_seq=bars_seen,
                        fraction=close_fraction,
                    ):
                        position = None
                    else:
                        _apply_partial_aftermath(position, bar.close)
                pending = None

            # (4b) F-07e conflict / position handling — a NEW aggregated entry-signal EDGE
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
                and position.entry_bar_seq != bars_seen
                and plan_active
                and pending is None
                and len(trades) == trades_before_bar
                and entry_signal is not None
                and entry_signal != prev_entry_signal
            ):
                if entry_signal == position.direction:
                    if stacking_policy == "ignore":
                        conflict_signals_ignored += 1
                        _emit(
                            "filtered_no_entry",
                            event_time=bar.timestamp,
                            direction=entry_signal,
                            bar_seq=bars_seen,
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
                        conflict_signals_ignored += 1
                        _emit(
                            "filtered_no_entry",
                            event_time=bar.timestamp,
                            direction=entry_signal,
                            bar_seq=bars_seen,
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
                        conflict_active = (
                            _active_restrictions(bar_date) if restriction_specs else []
                        )
                        if _restrictions_block(conflict_active):
                            entries_blocked_by_restriction += 1
                            _emit(
                                "filtered_no_entry",
                                event_time=bar.timestamp,
                                direction=entry_signal,
                                bar_seq=bars_seen,
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
                            positions_replaced += 1
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
                                bar_seq=bars_seen,
                                detail=replace_detail,
                            )
                            _close(
                                bar.timestamp,
                                bar.close,
                                "replaced_by_signal",
                                position,
                                bar_seq=bars_seen,
                            )
                            position = _do_open(
                                entry_signal,
                                bar,
                                bar.close,
                                bar_seq=bars_seen,
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
                                sleeve = _sleeve_capital(equity)
                                tranche = _cap_to_sleeve(
                                    _position_size(config, stack_eff, sleeve, stack_strength),
                                    sleeve,
                                    stack_eff,
                                )
                            else:
                                tranche = _position_size(config, stack_eff, equity, stack_strength)
                            stacked_size = position.size + tranche
                            size_limits = config.position_sizing.position_size_limits
                            stack_reject: str | None = None
                            stack_cap: str | None = None
                            if tranche <= _ZERO:
                                stack_reject = "stack_size_not_positive"
                            elif (
                                size_limits is not None
                                and size_limits.max_position_size is not None
                                and stacked_size > size_limits.max_position_size
                            ):
                                stack_reject = "position_size_limit"
                                stack_cap = str(size_limits.max_position_size)
                            elif alloc_on:
                                sleeve_remaining = _sleeve_capital(equity) - position.entry_notional
                                if (stack_eff * tranche) > sleeve_remaining:
                                    stack_reject = "sleeve_capacity"
                                    stack_cap = str(max(sleeve_remaining, _ZERO).quantize(_MONEY))
                            if stack_reject is not None:
                                stack_entries_rejected += 1
                                _emit(
                                    "stack_entry_rejected",
                                    event_time=bar.timestamp,
                                    direction=position.direction,
                                    bar_seq=bars_seen,
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
                                position.entry_notional = (new_basis * stacked_size).quantize(
                                    _MONEY
                                )
                                stack_entries_added += 1
                                if commission > _ZERO:
                                    equity = (equity - commission).quantize(_MONEY)
                                _emit(
                                    "stack_entry_added",
                                    event_time=bar.timestamp,
                                    direction=position.direction,
                                    bar_seq=bars_seen,
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
                    opposite_signal_closes += 1
                    _close(bar.timestamp, bar.close, "opposite_signal", position, bar_seq=bars_seen)
                    position = None
                elif hedge_policy == "ignore":
                    conflict_signals_ignored += 1
                    _emit(
                        "filtered_no_entry",
                        event_time=bar.timestamp,
                        direction=entry_signal,
                        bar_seq=bars_seen,
                        detail={
                            "reason": "hedge_ignored",
                            "policy": hedge_policy,
                            "position_seq": position.position_seq,
                        },
                    )

            # (5) F-07d same-direction scaling — the price-distance ladder over the OPEN
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
                and len(trades) == trades_before_bar
                and position.layers_filled < scale_max_layers
            ):
                scale_ref = position.scale_reference
                scale_long = position.direction == "long"
                scale_step = scale_ref * scale_distance / _HUNDRED
                scale_crossed = (
                    bar.close <= scale_ref - scale_step
                    if scale_long
                    else bar.close >= scale_ref + scale_step
                )
                if scale_crossed:
                    position.scale_reference = bar.close  # the ladder steps from this trigger
                    if scale_add_basis == "fixed_amount":
                        layer_size = scale_add_value.quantize(_QTY)
                    else:
                        layer_base = (
                            position.initial_size
                            if scale_add_basis == "percent_of_initial"
                            else position.size
                        )
                        layer_size = (layer_base * scale_add_value / _HUNDRED).quantize(_QTY)
                    layer_eff = _effective_fill(
                        bar.close, is_buy=scale_long, half_spread=half_spread, slip=slippage
                    )
                    scaled_size = position.size + layer_size
                    size_limits = config.position_sizing.position_size_limits
                    reject_reason: str | None = None
                    reject_cap: str | None = None
                    if layer_size <= _ZERO:
                        # A degenerate candidate (e.g. a percent basis quantized to 0) adds
                        # nothing — rejected, never a phantom 0-size layer.
                        reject_reason = "layer_size_not_positive"
                    elif scale_max_total is not None and scaled_size > scale_max_total:
                        reject_reason = "max_total_exposure"
                        reject_cap = str(scale_max_total)
                    elif (
                        size_limits is not None
                        and size_limits.max_position_size is not None
                        and scaled_size > size_limits.max_position_size
                    ):
                        reject_reason = "position_size_limit"
                        reject_cap = str(size_limits.max_position_size)
                    elif alloc_on:
                        sleeve_remaining = _sleeve_capital(equity) - position.entry_notional
                        if (layer_eff * layer_size) > sleeve_remaining:
                            reject_reason = "sleeve_capacity"
                            reject_cap = str(max(sleeve_remaining, _ZERO).quantize(_MONEY))
                    if reject_reason is not None:
                        scale_layers_rejected += 1
                        _emit(
                            "scale_layer_rejected",
                            event_time=bar.timestamp,
                            direction=position.direction,
                            bar_seq=bars_seen,
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
                        position.layers_filled += 1
                        scale_layers_added += 1
                        if commission > _ZERO:
                            # The layer's own entry fill pays its commission NOW; the close
                            # still books one round trip (initial entry + exit) — N layers
                            # pay exactly N extra fills, no double counting.
                            equity = (equity - commission).quantize(_MONEY)
                        _emit(
                            "scale_layer_added",
                            event_time=bar.timestamp,
                            direction=position.direction,
                            bar_seq=bars_seen,
                            detail={
                                "position_seq": position.position_seq,
                                "layer_seq": position.layers_filled,
                                "reference": str(scale_ref),
                                "fill_price": str(layer_eff),
                                "layer_size": str(layer_size),
                                "new_size": str(scaled_size),
                                "entry_basis": str(new_basis),
                                "exposure": str(position.entry_notional),
                                "method": "price_distance_scaling",
                            },
                        )

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

            # F-07e: the conflict EDGE detector's memory — this bar's aggregated signal is
            # the next bar's "previous" (None in proxy mode, so the detector stays inert).
            prev_entry_signal = entry_signal

            window.append(bar)

    # End-of-data: a limit order still resting past the last bar never filled → cancel it
    # (F-07b), so an unfilled limit is an auditable no-fill, never a silent gap.
    if working_limit is not None and last_bar is not None:
        limit_orders_cancelled += 1
        _emit(
            "limit_order_cancelled",
            event_time=last_bar.timestamp,
            direction=working_limit.direction,
            bar_seq=bars_seen,
            detail={
                "reason": "end_of_data",
                "unfilled_policy": working_limit.unfilled_policy,
                "limit_price": str(working_limit.limit_price),
            },
        )
        working_limit = None

    # End-of-data: a stop trigger still resting past the last bar never fired → cancel it
    # (F-07h), so an unfired stop is an auditable no-fill, never a silent gap.
    if working_stop is not None and last_bar is not None:
        stop_orders_cancelled += 1
        _emit(
            "stop_order_cancelled",
            event_time=last_bar.timestamp,
            direction=working_stop.direction,
            bar_seq=bars_seen,
            detail={
                "reason": "end_of_data",
                "trigger_price": str(working_stop.trigger_price),
                "order_type": order_cfg.type,
            },
        )
        working_stop = None

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
    if not leverage_ok:
        # Cross-margin (needs a portfolio risk model the engine does not implement) or a
        # non-positive saved multiplier is not modelled; the run opened NO position (fail
        # closed, F-07f). Ready Check raises STRATEGY_LEVERAGE_UNSUPPORTED — this L4
        # warning is the engine backstop when a stale readiness state reaches the worker.
        warnings.append(f"leverage_unsupported:{config.position_sizing.leverage_mode}")
    if not strength_ok:
        # A trend- / divergence-adjusted signal-strength mode is not modelled (the saved
        # schema carries no condition refs / multiplier / band config to execute it,
        # Master Ref §10.3); the run opened NO position (fail closed, F-07g) rather than
        # silently sizing un-adjusted. Ready Check raises
        # STRATEGY_SIGNAL_STRENGTH_UNSUPPORTED — this L4 warning is the engine backstop
        # when a stale readiness state reaches the worker.
        warnings.append(f"signal_strength_unsupported:{strength_mode}")
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
    if not order_ok:
        # An unsupported order variant (a stop / stop-limit with a missing or invalid
        # trigger, a best_bid_ask price rule — no quote series over OHLCV — or a
        # partial-fill policy other than not_allowed) is not modelled; the run opened NO
        # position (fail closed, F-07b/F-07h) rather than silently market-filling.
        # Ready Check raises STRATEGY_ORDER_TYPE_UNSUPPORTED — this L4 warning is the engine
        # backstop when a stale readiness state reaches the worker.
        warnings.append(f"order_type_unsupported:{order_cfg.type}")
    if not partial_close_ok:
        # A partial close (close_percentage < 100) with a trailing-stop aftermath but NO
        # protection-level trailing_stop configured/enabled is not modelled (post-V1 (f):
        # the aftermath has no trailing parameters of its own to reuse); the run opened NO
        # position (fail closed, F-07c/f) rather than silently ignoring the aftermath.
        # Ready Check raises STRATEGY_PARTIAL_CLOSE_UNSUPPORTED — this L4 warning is the
        # engine backstop. move_stop_to_entry / lock_in_profit / close_all are always
        # modelled and never reach here.
        warnings.append(f"partial_close_unsupported:{partial_aftermath}")
    if not scaling_ok:
        # An enabled scaling config the ladder cannot execute (logic-based scaling, a
        # per-layer timeframe override, a missing/non-positive add size, or a misconfigured
        # cap) is not modelled; the run opened NO position (fail closed, F-07d) rather than
        # silently running un-scaled. Ready Check raises STRATEGY_SCALING_UNSUPPORTED —
        # this L4 warning is the engine backstop.
        unsupported_method = (
            scaling_cfg.method
            if scaling_cfg is not None and scaling_cfg.method is not None
            else "unconfigured"
        )
        warnings.append(f"scaling_unsupported:{unsupported_method}")
    if not restrictions_ok:
        # An enabled restriction filter the replay cannot decide (volatility / spread /
        # volume / correlation, a non-block action, or an unparseable config) is not
        # modelled; the run opened NO position (fail closed, F-07e) rather than silently
        # trading through the filter. Ready Check raises STRATEGY_RESTRICTIONS_UNSUPPORTED —
        # this L4 warning is the engine backstop.
        unmodelled_types = sorted(
            {
                rf.filter_type
                for rf in restrictions_cfg.filters
                if rf.enabled and _parse_restriction(rf) is None
            }
        )
        warnings.append("restrictions_unsupported:" + ",".join(unmodelled_types))
    if not conflict_ok:
        # A true hedge (allow_hedge with exit-on-opposite off) needs two concurrent
        # opposite positions the single-position replay cannot honestly simulate; the run
        # opened NO position (fail closed, F-07e). Ready Check raises
        # STRATEGY_CONFLICT_HANDLING_UNSUPPORTED — this L4 warning is the engine backstop.
        warnings.append("conflict_handling_unsupported:allow_hedge_without_exit_on_opposite")
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
        # F-07f: leverage provenance (§10.2) — the resolved multiplier actually applied to
        # every computed position size (1x when unleveraged or 'no_leverage' normalized).
        "leverage_mode": config.position_sizing.leverage_mode,
        "leverage_modelled": leverage_ok,
        "leverage_multiplier": (str(_leverage_multiplier(config)) if leverage_ok else None),
        # F-07g: signal-strength provenance (§10.3) — the saved adjustment mode, whether
        # this engine version models it, and how many signal-driven entry decisions
        # computed a non-neutral (≠1x) multiplier.
        "signal_strength_mode": strength_mode,
        "signal_strength_modelled": strength_ok,
        "strength_adjustments": strength_adjustments,
        "entry_timing": config.data.execution.entry_timing,
        "exit_timing": config.data.execution.exit_timing,
        "execution_timing_modelled": timing_ok,
        "deferred_entry_fills": deferred_entry_fills,
        "deferred_exit_fills": deferred_exit_fills,
        # F-07b: order-type execution provenance + limit-order working-order counts.
        "order_type": order_cfg.type,
        "order_execution_modelled": order_ok,
        "limit_orders_placed": limit_orders_placed,
        "limit_orders_filled": limit_orders_filled,
        "limit_orders_cancelled": limit_orders_cancelled,
        "stop_orders_placed": stop_orders_placed,
        "stop_orders_triggered": stop_orders_triggered,
        "stop_orders_cancelled": stop_orders_cancelled,
        # F-07c: partial-close provenance + count (an exit signal closed part of a position).
        "close_percentage": str(exit_logic.close_percentage),
        "partial_aftermath": partial_aftermath,
        "partial_close_modelled": partial_close_ok,
        "partial_closes": partial_closes,
        # F-07f: trailing stop profit-lock provenance — whether the protection-level
        # activation threshold is configured at all, and how many lock events (a
        # lock_in_profit ratchet, or a trailing_stop aftermath force-activation) fired.
        "trailing_lock_in_active": trailing_lock_in_active,
        "lock_in_locks": lock_in_locks,
        # F-07d: same-direction scaling provenance + ladder counts.
        "scaling_enabled": scaling_enabled,
        "scaling_method": scaling_cfg.method if scaling_enabled and scaling_cfg else None,
        "scaling_modelled": scaling_ok,
        "scale_layers_added": scale_layers_added,
        "scale_layers_rejected": scale_layers_rejected,
        "max_total_exposure_active": scale_max_total is not None,
        # F-07e: restrictions & filters provenance + entry-gate counts.
        "restrictions_rule": restriction_rule,
        "restrictions_modelled": restrictions_ok,
        "active_filter_types": sorted(
            {rf.filter_type for rf in restrictions_cfg.filters if rf.enabled}
        ),
        "entries_blocked_by_restriction": entries_blocked_by_restriction,
        # F-07e: conflict / position handling provenance + policy-outcome counts.
        "conflict_handling_modelled": conflict_ok,
        "overlapping_signal_policy": overlap_policy,
        "same_direction_stacking": stacking_policy,
        "opposite_direction_hedge": hedge_policy,
        "exit_on_opposite_signal": bool(conflict_cfg.exit_on_opposite_signal),
        "stack_entries_added": stack_entries_added,
        "stack_entries_rejected": stack_entries_rejected,
        "positions_replaced": positions_replaced,
        "opposite_signal_closes": opposite_signal_closes,
        "conflict_signals_ignored": conflict_signals_ignored,
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
    "conflict_handling_is_modelled",
    "execution_timing_is_modelled",
    "order_execution_is_modelled",
    "partial_close_is_modelled",
    "resolve_allocation_execution",
    "restrictions_are_modelled",
    "run_engine",
    "scaling_is_modelled",
    "sizing_is_modelled",
]
