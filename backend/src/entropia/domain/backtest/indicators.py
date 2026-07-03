"""Built-in technical-indicator compute for the bar-replay engine (post-V1 Slice C).

Slice B replaced the deterministic stub with a real bar-replay, but entry/exit
timing still used a breakout PROXY because the indicator layer was stubbed. This
module lands the first REAL indicator compute: a small, deterministic, *incremental*
(streaming, bounded-memory) library for the canonical TA calls the ESP registry
seeds (``ta.sma``/``ta.ema``/``ta.rma``/``ta.wma``/``ta.rsi``), plus the
native-trigger rules that turn an indicator into a directional entry/exit signal.

Honest V1 boundary (kept explicit, never hidden):

* Package bodies are still NOT executed. A strategy pins an indicator package by
  revision; the engine reads that revision's ``dependency_snapshot`` to learn WHICH
  canonical TA call the package resolves to — it does not run the package source.
* The concrete indicator *parameter values* (e.g. RSI length 14) live in the
  un-parsed source body, so they are NOT recoverable from the pin. Compute uses the
  strategy's ``parameter_overrides`` when present, else a documented engine-version
  DEFAULT (part of the reproducibility contract, like ``_BREAKOUT_WINDOW`` was).
* Only whitelisted directional keys produce a native trigger. ``ta.atr`` (volatility)
  and ``ta.vwap`` (needs volume + a session anchor) are recognized but non-directional
  → the block is left unresolved (surfaced as a diagnostics warning, L4). Nested
  condition blocks / multi-timeframe overrides / non-native trigger sources are a
  later slice and likewise surface a warning rather than silently mis-computing.

The compute is a PURE function of the bars: same pinned strategy + same pinned
market revision => byte-identical signals. All arithmetic is ``Decimal``.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal

_ZERO = Decimal("0")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")

# Diagnostics label emitted when a real indicator plan (not the proxy) drove the run.
BUILTIN_ENTRY_MODEL = "builtin_indicator_native_trigger_v1"

# Canonical keys with a defined native directional trigger (price/MA cross or RSI
# band cross). Aligned to the ESP registry seed (apps/seed.py ``_ESP_TA_RESOLVERS``).
_MA_KEYS: frozenset[str] = frozenset({"ta.sma", "ta.ema", "ta.rma", "ta.wma"})
DIRECTIONAL_KEYS: frozenset[str] = _MA_KEYS | frozenset({"ta.rsi"})
# Recognized-but-non-directional in this slice (no native trigger yet).
NON_DIRECTIONAL_KEYS: frozenset[str] = frozenset({"ta.atr", "ta.vwap"})
RECOGNIZED_KEYS: frozenset[str] = DIRECTIONAL_KEYS | NON_DIRECTIONAL_KEYS

# Condition primitives (post-V1 (b) — condition blocks; extended in (b2)). A nested
# condition either GATES an indicator block's native trigger (``*_native_trigger_plus_
# condition``: the trigger only fires on a bar where the block's conditions hold) or
# DRIVES a condition-only directional signal (``indicator_output_plus_condition``: no
# native trigger — a cross primitive's edge IS the entry). Comparators:
#   * ``cond.above`` / ``cond.below`` — LEVEL: source strictly over/under the RHS.
#   * ``cond.crosses_above`` / ``cond.crosses_below`` — EDGE: source crosses the RHS
#     this bar (prev on/under -> now strictly over, and vice versa). Directional.
#   * ``cond.between`` — RANGE: source strictly within (lower, upper). Non-directional.
# The RHS is (in precedence order): a second separately-pinned INDICATOR package's output
# series (``reference_key`` — the two-package indicator-vs-indicator form, e.g. fast-MA vs
# slow-MA), else a bounded ``reference`` series (a bar price field or the parent block's
# ``indicator_output``), else a strategy-supplied constant ``threshold``. Aligned to the
# ESP seed (apps/seed.py ``_ESP_COND_RESOLVERS``).
_COND_ABOVE = "cond.above"
_COND_BELOW = "cond.below"
_COND_CROSSES_ABOVE = "cond.crosses_above"
_COND_CROSSES_BELOW = "cond.crosses_below"
_COND_BETWEEN = "cond.between"
CONDITION_KEYS: frozenset[str] = frozenset(
    {_COND_ABOVE, _COND_BELOW, _COND_CROSSES_ABOVE, _COND_CROSSES_BELOW, _COND_BETWEEN}
)
# Cross primitives carry a directional edge: usable as the driver of a condition-only
# signal (``crosses_above`` -> long, ``crosses_below`` -> short).
CROSS_CONDITION_KEYS: frozenset[str] = frozenset({_COND_CROSSES_ABOVE, _COND_CROSSES_BELOW})
# The range primitive needs two bounds and is non-directional (gate/supporting only).
RANGE_CONDITION_KEYS: frozenset[str] = frozenset({_COND_BETWEEN})
# Sources a condition may read (for its ``source`` AND its ``reference`` RHS). Price
# fields come from the bar; the special ``indicator_output`` reads the PARENT block's
# current indicator value (e.g. RSI 72).
_COND_PRICE_SOURCES: frozenset[str] = frozenset({"close", "open", "high", "low"})
CONDITION_SOURCES: frozenset[str] = _COND_PRICE_SOURCES | frozenset({"indicator_output"})
# Engine-version reproducibility constant: the source used when none is configured.
DEFAULT_CONDITION_SOURCE = "close"


def condition_direction(canonical_key: str) -> str | None:
    """Long/short polarity of a directional (cross) condition; ``None`` if non-directional.

    Condition-only signals take their direction from a cross edge: ``crosses_above`` is
    a bullish edge (long), ``crosses_below`` a bearish edge (short). Level/range
    comparators carry no inherent direction (a level is ambiguous — over/oversold)."""
    if canonical_key == _COND_CROSSES_ABOVE:
        return "long"
    if canonical_key == _COND_CROSSES_BELOW:
        return "short"
    return None


# Engine-version default parameters (reproducibility constants — a change here is a
# new ``engine_version``). Used only when the strategy carries no override.
_DEFAULT_MA_LENGTH = 20
_DEFAULT_RSI_LENGTH = 14
_DEFAULT_RSI_LOWER = Decimal("30")
_DEFAULT_RSI_UPPER = Decimal("70")


def default_length(canonical_key: str) -> int:
    """Documented default look-back for a canonical key (no strategy override)."""
    return _DEFAULT_RSI_LENGTH if canonical_key == "ta.rsi" else _DEFAULT_MA_LENGTH


@dataclass(frozen=True, slots=True)
class ConditionSpec:
    """A resolved, computable condition nested under an indicator block.

    Pure data (no DB, no package body). ``canonical_key`` is a ``cond.*`` comparator,
    ``source`` names the series compared (a bar price field or the parent block's
    ``indicator_output``). The right-hand side is (in precedence order) a second pinned
    indicator's series (``reference_key`` — two-package indicator-vs-indicator), else a
    bounded ``reference`` series, else the constant ``threshold``. ``cond.between`` ignores
    the RHS and uses the ``lower``/``upper`` bounds instead."""

    condition_block_id: str
    canonical_key: str  # one of CONDITION_KEYS
    source: str  # "close" | "open" | "high" | "low" | "indicator_output"
    threshold: Decimal | None  # constant RHS; None for cond.between or a reference RHS
    requirement: str  # "required" | "supporting"
    validity: str
    lower: Decimal | None = None  # cond.between lower bound (exclusive)
    upper: Decimal | None = None  # cond.between upper bound (exclusive)
    reference: str | None = None  # bounded series RHS (price field / parent indicator_output)
    # Two-package indicator-vs-indicator: a separately-pinned INDICATOR package computed
    # inline as the RHS series (its canonical key + look-back). Takes precedence over
    # ``reference`` and ``threshold``; ``None`` for the single-package forms.
    reference_key: str | None = None  # 2nd-package RHS indicator (a DIRECTIONAL_KEYS key)
    reference_length: int | None = None


@dataclass(frozen=True, slots=True)
class IndicatorSpec:
    """A resolved, computable indicator block (pure data — no DB, no package body)."""

    block_id: str
    canonical_key: str
    length: int
    direction: str  # "long" | "short" | "long_and_short"
    requirement: str  # "required" | "supporting"
    validity: str
    rsi_lower: Decimal = _DEFAULT_RSI_LOWER
    rsi_upper: Decimal = _DEFAULT_RSI_UPPER
    # Nested conditions (post-V1 (b)/(b2)). In native-gated mode they GATE this block's
    # native trigger; in ``condition_only`` mode there is no native trigger and the
    # conditions DRIVE the signal (direction from the required cross primitive). Empty
    # for a plain ``indicator_native_trigger`` block (Slice C behaviour intact).
    conditions: tuple[ConditionSpec, ...] = ()
    condition_rule: str | None = None  # ``condition_block_rule`` (None => all-required)
    min_condition_support: int | None = None
    # True for ``indicator_output_plus_condition``: the conditions ARE the signal.
    condition_only: bool = False


@dataclass(frozen=True, slots=True)
class SignalRule:
    """A signal-block aggregation rule (entry or exit)."""

    rule: str
    min_supporting_count: int | None = None


@dataclass(frozen=True, slots=True)
class IndicatorPlan:
    """The fully-resolved, deterministic indicator plan handed to the engine.

    Produced by the DB-touching query layer (``resolve_indicator_plan``) and consumed
    by the pure engine. ``unresolved`` carries human-readable warnings for blocks the
    slice could not compute (surfaced in diagnostics, never silently dropped)."""

    entry_rule: SignalRule
    entry_specs: tuple[IndicatorSpec, ...]
    exit_rule: SignalRule | None = None
    exit_specs: tuple[IndicatorSpec, ...] = ()
    exit_on_opposite: bool = True
    unresolved: tuple[str, ...] = ()

    @property
    def has_entry(self) -> bool:
        """True when at least one entry block resolved to a computable indicator."""
        return bool(self.entry_specs)


# Validity window (in bars) a fired native trigger stays active. ``None`` means
# "until an opposite signal" (an open-ended window cleared by the opposite event).
_VALIDITY_BARS: dict[str, int | None] = {
    "current_candle_only": 1,
    "1_candle": 1,
    "2_candles": 2,
    "3_candles": 3,
    "4_candles": 4,
    "until_opposite_signal": None,
}


def _mean(window: deque[Decimal]) -> Decimal:
    total = _ZERO
    for value in window:
        total += value
    return total / Decimal(len(window))


def _wma(window: deque[Decimal]) -> Decimal:
    """Linearly weighted MA: the most recent close carries the highest weight."""
    total = _ZERO
    weight_sum = _ZERO
    for index, value in enumerate(window, start=1):
        weight = Decimal(index)
        total += value * weight
        weight_sum += weight
    return total / weight_sum


@dataclass(slots=True)
class _MovingAverage:
    """Incremental MA value for one of ``ta.sma``/``ta.ema``/``ta.rma``/``ta.wma``.

    All variants warm up over ``length`` closes (value is ``None`` until then), so a
    cross is only evaluated once the average is established — no seed-noise crosses.
    EMA/RMA seed from the SMA of the first full window, then smooth."""

    key: str
    length: int
    _window: deque[Decimal] = field(init=False)
    _running: Decimal | None = field(init=False, default=None)
    value: Decimal | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self._window = deque(maxlen=self.length)

    def update(self, close: Decimal) -> Decimal | None:
        self._window.append(close)
        if len(self._window) < self.length:
            self.value = None
            return None
        if self.key == "ta.sma":
            self.value = _mean(self._window)
        elif self.key == "ta.wma":
            self.value = _wma(self._window)
        elif self.key == "ta.ema":
            if self._running is None:
                self._running = _mean(self._window)
            else:
                alpha = Decimal(2) / Decimal(self.length + 1)
                self._running = self._running + alpha * (close - self._running)
            self.value = self._running
        else:  # ta.rma (Wilder smoothing)
            if self._running is None:
                self._running = _mean(self._window)
            else:
                n = Decimal(self.length)
                self._running = (self._running * (n - _ONE) + close) / n
            self.value = self._running
        return self.value


@dataclass(slots=True)
class _Rsi:
    """Incremental Wilder RSI. Value is ``None`` until ``length`` price changes seen."""

    length: int
    _prev_close: Decimal | None = field(init=False, default=None)
    _avg_gain: Decimal | None = field(init=False, default=None)
    _avg_loss: Decimal | None = field(init=False, default=None)
    _seed_gains: Decimal = field(init=False, default=_ZERO)
    _seed_losses: Decimal = field(init=False, default=_ZERO)
    _changes_seen: int = field(init=False, default=0)
    value: Decimal | None = field(init=False, default=None)

    def update(self, close: Decimal) -> Decimal | None:
        if self._prev_close is None:
            self._prev_close = close
            return None
        change = close - self._prev_close
        self._prev_close = close
        gain = change if change > _ZERO else _ZERO
        loss = -change if change < _ZERO else _ZERO
        self._changes_seen += 1
        if self._avg_gain is None or self._avg_loss is None:
            self._seed_gains += gain
            self._seed_losses += loss
            if self._changes_seen < self.length:
                self.value = None
                return None
            self._avg_gain = self._seed_gains / Decimal(self.length)
            self._avg_loss = self._seed_losses / Decimal(self.length)
        else:
            n = Decimal(self.length)
            self._avg_gain = (self._avg_gain * (n - _ONE) + gain) / n
            self._avg_loss = (self._avg_loss * (n - _ONE) + loss) / n
        if self._avg_loss == _ZERO:
            self.value = _HUNDRED
        else:
            rs = self._avg_gain / self._avg_loss
            self.value = _HUNDRED - (_HUNDRED / (_ONE + rs))
        return self.value


def _build_reference_indicator(key: str, length: int) -> _MovingAverage | _Rsi:
    """A second computed series (a separately-pinned indicator package) used as a
    condition's RHS — the two-package indicator-vs-indicator form. Mirrors the
    ``BlockEvaluator`` compute choice: Wilder RSI for ``ta.rsi``, else a moving average."""
    if key == "ta.rsi":
        return _Rsi(length)
    return _MovingAverage(key, length)


class ConditionEvaluator:
    """Stateful per-condition comparator over the streamed bars.

    Each bar it reads the condition's SOURCE series and its RHS — the constant
    ``threshold`` or, when configured, a ``reference`` series — then evaluates the
    ``cond.*`` comparator: a LEVEL check (above/below), an EDGE cross (crosses_above/
    crosses_below, which needs the previous bar's pair) or a RANGE (between, over the
    ``lower``/``upper`` bounds). A satisfied check stays active for the condition's
    validity window; ``until_opposite_signal`` is open-ended and clears the moment the
    check fails. The parent ``BlockEvaluator`` reads ``satisfied``."""

    __slots__ = ("_active", "_active_left", "_prev_rhs", "_prev_source", "_ref_indicator", "_spec")

    def __init__(self, spec: ConditionSpec) -> None:
        self._spec = spec
        self._active = False
        self._active_left: int | None = None  # bars remaining (None = until it fails)
        self._prev_source: Decimal | None = None  # last bar's source (for cross edges)
        self._prev_rhs: Decimal | None = None  # last bar's RHS (constant or reference)
        # A second, separately-pinned indicator computed inline as the RHS series (the
        # two-package indicator-vs-indicator form). It warms up over its own length; a
        # ``None`` value fails the check closed just like any missing series.
        self._ref_indicator: _MovingAverage | _Rsi | None = (
            _build_reference_indicator(
                spec.reference_key, spec.reference_length or default_length(spec.reference_key)
            )
            if spec.reference_key is not None
            else None
        )

    def update(
        self,
        *,
        close: Decimal,
        high: Decimal,
        low: Decimal,
        open_price: Decimal,
        indicator_value: Decimal | None,
    ) -> None:
        window = _VALIDITY_BARS.get(self._spec.validity, 1)
        # Age a finite window BEFORE this bar's fresh check can refresh it.
        if self._active_left is not None and self._active:
            self._active_left -= 1
            if self._active_left <= 0:
                self._active = False
                self._active_left = None
        # Advance the reference indicator (if any) so its RHS value is as-of this bar.
        if self._ref_indicator is not None:
            self._ref_indicator.update(close)
        source = self._series_value(
            self._spec.source, close, high, low, open_price, indicator_value
        )
        rhs = self._rhs_value(close, high, low, open_price, indicator_value)
        if self._raw_check(source, rhs):
            self._active = True
            self._active_left = window  # None => open-ended (until the check fails)
        elif window is None:
            # until_opposite_signal: an open-ended gate clears when the check fails.
            # (A momentary cross therefore stays active for exactly its firing bar.)
            self._active = False
            self._active_left = None
        self._prev_source = source
        self._prev_rhs = rhs

    def _series_value(
        self,
        name: str,
        close: Decimal,
        high: Decimal,
        low: Decimal,
        open_price: Decimal,
        indicator_value: Decimal | None,
    ) -> Decimal | None:
        if name == "indicator_output":
            return indicator_value  # None while the parent indicator is still warming up
        if name == "high":
            return high
        if name == "low":
            return low
        if name == "open":
            return open_price
        return close

    def _rhs_value(
        self,
        close: Decimal,
        high: Decimal,
        low: Decimal,
        open_price: Decimal,
        indicator_value: Decimal | None,
    ) -> Decimal | None:
        """The comparator's right-hand side, in precedence order: a second pinned
        indicator's series (two-package), else a bounded ``reference`` series, else the
        constant ``threshold``. A warming-up reference indicator returns ``None`` and
        fails the check closed."""
        if self._ref_indicator is not None:
            return self._ref_indicator.value
        reference = self._spec.reference
        if reference is not None:
            return self._series_value(reference, close, high, low, open_price, indicator_value)
        return self._spec.threshold

    def _raw_check(self, source: Decimal | None, rhs: Decimal | None) -> bool:
        key = self._spec.canonical_key
        if key == _COND_BETWEEN:
            lower, upper = self._spec.lower, self._spec.upper
            if source is None or lower is None or upper is None:
                return False
            return lower < source < upper
        if source is None or rhs is None:
            return False  # a missing series (warm-up) fails closed
        if key == _COND_ABOVE:
            return source > rhs
        if key == _COND_BELOW:
            return source < rhs
        # Cross edges need the previous bar's (source, rhs) pair.
        prev_source, prev_rhs = self._prev_source, self._prev_rhs
        if prev_source is None or prev_rhs is None:
            return False
        if key == _COND_CROSSES_ABOVE:
            return prev_source <= prev_rhs and source > rhs
        if key == _COND_CROSSES_BELOW:
            return prev_source >= prev_rhs and source < rhs
        return False

    @property
    def satisfied(self) -> bool:
        return self._active

    @property
    def requirement(self) -> str:
        return self._spec.requirement


class BlockEvaluator:
    """Stateful per-block native-trigger evaluator over the streamed bars.

    Feeds each bar's close into the indicator, detects the native trigger EVENT
    (MA cross, or RSI band cross), applies the block's ``direction`` filter, and
    holds the last fired signal active for its ``validity`` window. The engine reads
    ``current_signal`` (``"long"``/``"short"``/``None``) after ``update``."""

    __slots__ = (
        "_active_dir",
        "_active_left",
        "_cond_evals",
        "_condition_dir",
        "_condition_only",
        "_is_rsi",
        "_ma",
        "_prev_close",
        "_prev_gate",
        "_prev_value",
        "_rsi",
        "_spec",
    )

    def __init__(self, spec: IndicatorSpec) -> None:
        self._spec = spec
        self._is_rsi = spec.canonical_key == "ta.rsi"
        self._ma = None if self._is_rsi else _MovingAverage(spec.canonical_key, spec.length)
        self._rsi = _Rsi(spec.length) if self._is_rsi else None
        self._prev_value: Decimal | None = None
        self._prev_close: Decimal | None = None
        self._active_dir: str | None = None
        self._active_left: int | None = None  # validity bars remaining (None = until opposite)
        self._cond_evals = [ConditionEvaluator(cond) for cond in spec.conditions]
        # Condition-only mode: the conditions DRIVE the signal (no native trigger). The
        # block direction is the required cross primitives' shared polarity; the signal
        # fires on the RISING EDGE of the aggregate gate and is held for the validity
        # window. ``_condition_dir`` is None for a native-gated block (native trigger).
        self._condition_only = spec.condition_only
        self._condition_dir = _condition_only_direction(spec) if spec.condition_only else None
        self._prev_gate = False  # last bar's aggregate condition-gate state (edge detect)

    def update(
        self,
        close: Decimal,
        high: Decimal | None = None,
        low: Decimal | None = None,
        open_price: Decimal | None = None,
    ) -> None:
        # OHLC is optional so callers/tests with close-only series keep working; a
        # missing field degrades to the close (only price-source conditions read them).
        high = close if high is None else high
        low = close if low is None else low
        open_price = close if open_price is None else open_price
        # Age any active window BEFORE this bar's fresh event can refresh it.
        if self._active_left is not None and self._active_dir is not None:
            self._active_left -= 1
            if self._active_left <= 0:
                self._active_dir = None
                self._active_left = None
        if self._rsi is not None:
            value = self._rsi.update(close)
        else:
            assert self._ma is not None
            value = self._ma.update(close)
        # Native trigger (MA/RSI cross) — skipped in condition-only mode, where the
        # conditions themselves drive the signal.
        if not self._condition_only:
            fired = self._detect(close, value)
            if fired is not None:
                self._active_dir = fired
                self._active_left = _VALIDITY_BARS.get(self._spec.validity, 1)
        self._prev_value = value
        self._prev_close = close
        # Feed the nested conditions THIS bar's prices + the parent's fresh indicator
        # value, so the gate is evaluated as-of the same bar as the trigger.
        for cond in self._cond_evals:
            cond.update(
                close=close,
                high=high,
                low=low,
                open_price=open_price,
                indicator_value=value,
            )
        # Condition-only signal: fire on the RISING EDGE of the aggregate condition gate
        # (a directionless false->true transition), in the block's condition direction.
        if self._condition_only:
            gate = _conditions_satisfied(
                self._spec.condition_rule, self._cond_evals, self._spec.min_condition_support
            )
            if gate and not self._prev_gate and self._condition_dir is not None:
                fired = self._filter(self._condition_dir)
                if fired is not None:
                    self._active_dir = fired
                    self._active_left = _VALIDITY_BARS.get(self._spec.validity, 1)
            self._prev_gate = gate

    def _detect(self, close: Decimal, value: Decimal | None) -> str | None:
        prev = self._prev_value
        if value is None or prev is None:
            return None
        if self._is_rsi:
            if prev <= self._spec.rsi_lower and value > self._spec.rsi_lower:
                return self._filter("long")
            if prev >= self._spec.rsi_upper and value < self._spec.rsi_upper:
                return self._filter("short")
            return None
        # MA family: a price/MA cross using the previous close vs the previous MA.
        if self._prev_close is None:
            return None
        if self._prev_close <= prev and close > value:
            return self._filter("long")
        if self._prev_close >= prev and close < value:
            return self._filter("short")
        return None

    def _filter(self, direction: str) -> str | None:
        allowed = self._spec.direction
        return direction if allowed in ("long_and_short", direction) else None

    @property
    def current_signal(self) -> str | None:
        """The active signal direction for this block.

        A block with no conditions behaves exactly as in Slice C. In native-gated mode
        an otherwise-active trigger is suppressed on any bar where the conditions are
        not satisfied per the block's ``condition_block_rule`` (directionless gate). In
        condition-only mode the direction was already gated at the firing edge and is
        simply held for the validity window (no re-gating)."""
        if self._active_dir is None:
            return None
        if (
            not self._condition_only
            and self._cond_evals
            and not _conditions_satisfied(
                self._spec.condition_rule, self._cond_evals, self._spec.min_condition_support
            )
        ):
            return None
        return self._active_dir

    @property
    def requirement(self) -> str:
        return self._spec.requirement


def build_evaluators(specs: tuple[IndicatorSpec, ...]) -> list[BlockEvaluator]:
    return [BlockEvaluator(spec) for spec in specs]


def _viable_direction(rule: SignalRule, evaluators: list[BlockEvaluator], direction: str) -> bool:
    required = [ev for ev in evaluators if ev.requirement == "required"]
    supporting = [ev for ev in evaluators if ev.requirement == "supporting"]
    # With no explicitly-required block, aggregation degenerates to "every block must
    # agree" so a plan is never trivially satisfiable.
    if not required:
        required, supporting = evaluators, []
    if not all(ev.current_signal == direction for ev in required):
        return False
    supporting_hits = sum(1 for ev in supporting if ev.current_signal == direction)
    if rule.rule == "required_indicator_blocks_only":
        return True
    if rule.rule == "required_plus_any_supporting":
        return supporting_hits >= 1
    if rule.rule == "required_plus_min_supporting":
        return supporting_hits >= (rule.min_supporting_count or 1)
    if rule.rule == "required_plus_all_confirmations":
        return supporting_hits == len(supporting)
    return False


def _conditions_satisfied(
    rule: str | None, conditions: list[ConditionEvaluator], min_support: int | None
) -> bool:
    """Whether an indicator block's nested threshold conditions gate its trigger.

    Mirrors the signal-block aggregation shape but over booleans: every REQUIRED
    condition must hold, then the SUPPORTING conditions are combined per the
    ``condition_block_rule``. With no explicitly-required condition the set
    degenerates to 'every condition must hold', so a gate is never vacuously true."""
    required = [c for c in conditions if c.requirement == "required"]
    supporting = [c for c in conditions if c.requirement == "supporting"]
    if not required:
        required, supporting = conditions, []
    if not all(c.satisfied for c in required):
        return False
    hits = sum(1 for c in supporting if c.satisfied)
    if rule is None or rule == "required_condition_blocks_only":
        return True
    if rule == "required_plus_any_supporting":
        return hits >= 1
    if rule == "required_plus_min_supporting":
        return hits >= (min_support or 1)
    if rule == "required_plus_all_supporting":
        return hits == len(supporting)
    return False


def _condition_only_direction(spec: IndicatorSpec) -> str | None:
    """The single directional edge a condition-only block signals, or ``None``.

    Direction comes from the block's REQUIRED cross primitives (``crosses_above`` ->
    long, ``crosses_below`` -> short). With no explicitly-required condition the whole
    set is considered (mirrors ``_conditions_satisfied``). Non-directional level/range
    conditions contribute no direction; a mixed or absent polarity yields ``None`` (the
    plan layer surfaces this as an unresolved block, so it should not reach here)."""
    required = [c for c in spec.conditions if c.requirement == "required"]
    pool = required or list(spec.conditions)
    directions = {condition_direction(c.canonical_key) for c in pool}
    directions.discard(None)
    if len(directions) == 1:
        return directions.pop()
    return None


def aggregate(rule: SignalRule, evaluators: list[BlockEvaluator]) -> str | None:
    """Combine block signals into one directional decision (long wins a tie)."""
    if not evaluators:
        return None
    if _viable_direction(rule, evaluators, "long"):
        return "long"
    if _viable_direction(rule, evaluators, "short"):
        return "short"
    return None


__all__ = [
    "BUILTIN_ENTRY_MODEL",
    "CONDITION_KEYS",
    "CONDITION_SOURCES",
    "CROSS_CONDITION_KEYS",
    "DEFAULT_CONDITION_SOURCE",
    "DIRECTIONAL_KEYS",
    "NON_DIRECTIONAL_KEYS",
    "RANGE_CONDITION_KEYS",
    "RECOGNIZED_KEYS",
    "BlockEvaluator",
    "ConditionEvaluator",
    "ConditionSpec",
    "IndicatorPlan",
    "IndicatorSpec",
    "SignalRule",
    "aggregate",
    "build_evaluators",
    "condition_direction",
    "default_length",
]
