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


class BlockEvaluator:
    """Stateful per-block native-trigger evaluator over the streamed bars.

    Feeds each bar's close into the indicator, detects the native trigger EVENT
    (MA cross, or RSI band cross), applies the block's ``direction`` filter, and
    holds the last fired signal active for its ``validity`` window. The engine reads
    ``current_signal`` (``"long"``/``"short"``/``None``) after ``update``."""

    __slots__ = (
        "_active_dir",
        "_active_left",
        "_is_rsi",
        "_ma",
        "_prev_close",
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

    def update(self, close: Decimal) -> None:
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
        fired = self._detect(close, value)
        if fired is not None:
            self._active_dir = fired
            self._active_left = _VALIDITY_BARS.get(self._spec.validity, 1)
        self._prev_value = value
        self._prev_close = close

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
    "DIRECTIONAL_KEYS",
    "NON_DIRECTIONAL_KEYS",
    "RECOGNIZED_KEYS",
    "BlockEvaluator",
    "IndicatorPlan",
    "IndicatorSpec",
    "SignalRule",
    "aggregate",
    "build_evaluators",
    "default_length",
]
