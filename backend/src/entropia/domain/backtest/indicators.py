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
* Only whitelisted directional keys produce a native trigger: the MA family and RSI,
  plus ``ta.vwap`` — a rolling volume-weighted price line whose price/VWAP cross is
  directional (post-V1 (d)); its compute reads the bars' volume (a windowed VWAP over
  ``length`` candles, not a session anchor, to match the ``length``-parameterized family
  and stay bounded-memory). ``ta.atr`` (volatility band width) stays recognized-but-non-
  directional → that block is left unresolved (surfaced as a diagnostics warning, L4).
  Non-native trigger sources likewise surface a warning rather than silently mis-computing.
* An indicator block MAY compute on a higher timeframe than the base bars (post-V1 (c)):
  the base bars are aggregated into the block's coarser candle and the trigger only
  advances on a completed candle (no look-ahead). A nested condition's RHS reference
  indicator MAY also compute on a coarser timeframe than its parent block (post-V1 (i)):
  the fast source is compared against the slower reference series, which only advances on a
  completed reference candle (no look-ahead). Only the ``reference_package_ref`` RHS is
  resampled; a bounded ``reference``/``threshold`` RHS stays on the block's timeframe.

The compute is a PURE function of the bars: same pinned strategy + same pinned
market revision => byte-identical signals. All arithmetic is ``Decimal``.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

_ZERO = Decimal("0")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")

# Diagnostics label emitted when a real indicator plan (not the proxy) drove the run.
BUILTIN_ENTRY_MODEL = "builtin_indicator_native_trigger_v1"

# Canonical keys with a defined native directional trigger (price/MA cross, RSI band
# cross, or a price/VWAP cross). Aligned to the ESP registry seed (apps/seed.py
# ``_ESP_TA_RESOLVERS``).
_MA_KEYS: frozenset[str] = frozenset({"ta.sma", "ta.ema", "ta.rma", "ta.wma"})
# ``ta.vwap`` is a volume-weighted price line (post-V1 (d)): its compute needs the bars'
# volume, so it is grouped here to keep the volume-dependent compute path explicit.
_VWAP_KEY = "ta.vwap"
VOLUME_WEIGHTED_KEYS: frozenset[str] = frozenset({_VWAP_KEY})
DIRECTIONAL_KEYS: frozenset[str] = _MA_KEYS | frozenset({"ta.rsi"}) | VOLUME_WEIGHTED_KEYS
# Recognized-but-non-directional: ``ta.atr`` is a volatility measure (a band width, not a
# directional line), so it yields no native cross — left unresolved (surfaced as a
# diagnostics warning, L4) rather than silently mis-computed.
NON_DIRECTIONAL_KEYS: frozenset[str] = frozenset({"ta.atr"})
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


# Multi-timeframe resampling (post-V1 Slice C follow-up (c)). A higher-timeframe
# indicator block aggregates the base bars into its own coarser candles and advances
# the indicator only when a candle CLOSES — never on a still-forming one (no look-ahead
# / no repaint). The override vocabulary is a fixed set of fixed-duration timeframes (a
# reproducibility constant, matching ``IndicatorBlock.timeframe``); each maps to the
# second span used to floor a bar's timestamp into a higher-TF bucket.
_TF_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "1D": 86400,
}


def timeframe_seconds(timeframe: str) -> int | None:
    """Span in seconds of a supported timeframe, or ``None`` if it is not recognized."""
    return _TF_SECONDS.get(timeframe)


def _epoch_seconds(timestamp: str) -> int | None:
    """Parse an ISO-8601 (or bare epoch) bar timestamp to integer UTC epoch seconds.

    Deterministic and clock-free — it only parses the given string, never reads the
    wall clock. ISO strings (with or without a trailing ``Z``) go through ``datetime``;
    an all-digit string is read as epoch milliseconds (>=13 digits) else seconds.
    ``None`` on anything unparseable, so a higher-TF block fails closed (holds its last
    completed-candle signal) rather than silently mis-bucketing."""
    if not timestamp:
        return None
    text = timestamp.strip()
    if text.isdigit():
        value = int(text)
        return value // 1000 if len(text) >= 13 else value
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp())


def _htf_bucket(timestamp: str, span_seconds: int) -> int | None:
    """Higher-TF bucket index a bar falls in — ``floor(epoch / span)`` — or ``None`` if
    the timestamp is unparseable. Consecutive base bars sharing a bucket aggregate into
    one candle; a change of bucket means the prior higher-TF candle has closed."""
    epoch = _epoch_seconds(timestamp)
    if epoch is None:
        return None
    return epoch // span_seconds


@dataclass(frozen=True, slots=True)
class ReferenceSeriesSpec:
    """One resolved leg of an N-ary reference chain (post-V1 (ii)).

    A separately-pinned indicator package computed inline as part of a condition's RHS
    comparison chain. ``key`` is a ``DIRECTIONAL_KEYS`` MA/RSI key, ``length`` its look-back,
    and ``resample_seconds`` an optional per-leg coarser reference timeframe (``None`` keeps
    the leg on the block's timeframe)."""

    key: str
    length: int
    resample_seconds: int | None = None


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
    # Per-condition multi-timeframe reference (post-V1 (i)). When set, the RHS reference
    # indicator (``reference_key``) is computed on a timeframe COARSER than the parent
    # block: base bars are aggregated into that reference candle and the RHS only advances
    # when a candle CLOSES (the fast ``source`` is compared against the slower, held RHS —
    # no look-ahead). ``None`` computes the RHS on the block's own timeframe (Slice C /
    # (#53) behaviour). Only meaningful when ``reference_key`` is set.
    reference_resample_seconds: int | None = None
    # N-ary reference chain (post-V1 (ii)): reference legs BEYOND the primary ``reference_key``.
    # The comparison becomes a monotonic chain ``source [cmp] primary [cmp] extra[0] [cmp]
    # extra[1] ...`` (e.g. fast-MA > slow-MA > slowest-MA). Empty for the single-reference forms
    # (#53/#56), where the check is byte-identical. Only meaningful with ``reference_key`` set.
    extra_references: tuple[ReferenceSeriesSpec, ...] = ()


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
    # Higher-timeframe resampling span in seconds (post-V1 (c)). ``None`` computes on the
    # base bars (Slice C behaviour); a positive span aggregates the base bars into that
    # coarser candle and advances the indicator only when the candle closes.
    resample_seconds: int | None = None


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


@dataclass(slots=True)
class _Vwap:
    """Incremental rolling volume-weighted average price over ``length`` candles (post-V1 (d)).

    Each candle contributes its typical price ``(high + low + close) / 3`` weighted by its
    volume; the value is the window's volume-weighted mean. Warms up over ``length`` candles
    (value ``None`` until then), so a price/VWAP cross is only evaluated once the line is
    established — mirroring the MA warm-up. A windowed VWAP (not a session-anchored one) keeps
    it ``length``-parameterized and bounded-memory like the rest of the family; ``length`` is
    the same look-back the plan layer resolves for any directional key. When the window carries
    ZERO total volume the line is undefined — value ``None`` (fails closed, never divides by
    zero), so a volume-less market yields no phantom crosses."""

    length: int
    _pv: deque[Decimal] = field(init=False)  # typical_price * volume per candle slot
    _vol: deque[Decimal] = field(init=False)  # volume per candle slot
    value: Decimal | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self._pv = deque(maxlen=self.length)
        self._vol = deque(maxlen=self.length)

    def update(
        self, close: Decimal, high: Decimal, low: Decimal, volume: Decimal
    ) -> Decimal | None:
        typical = (high + low + close) / Decimal(3)
        self._pv.append(typical * volume)
        self._vol.append(volume)
        if len(self._vol) < self.length:
            self.value = None
            return None
        total_pv = _ZERO
        total_vol = _ZERO
        for pv, vol in zip(self._pv, self._vol, strict=True):
            total_pv += pv
            total_vol += vol
        if total_vol <= _ZERO:
            self.value = None  # no volume in the window: VWAP undefined, fail closed
            return None
        self.value = total_pv / total_vol
        return self.value


def _build_reference_indicator(key: str, length: int) -> _MovingAverage | _Rsi | _Vwap:
    """A second computed series (a separately-pinned indicator package) used as a
    condition's RHS — the two-package indicator-vs-indicator form. Mirrors the
    ``BlockEvaluator`` compute choice: Wilder RSI for ``ta.rsi``, a rolling VWAP for
    ``ta.vwap`` (post-V1 (d)), else a moving average."""
    if key == "ta.rsi":
        return _Rsi(length)
    if key == _VWAP_KEY:
        return _Vwap(length)
    return _MovingAverage(key, length)


# Directional keys whose incremental compute an ESP validation-run can execute against
# stored test-vectors (doc 09 §11.1 "Test vectors", post-V1 R8). ``ta.atr`` / ``cond.*``
# have no directional series compute here, so a validation-run over them cannot PASS
# (fail-closed, doc 09 §7 "a successful one-off sample is not sufficient evidence").
VALIDATABLE_RESOLVER_KEYS: frozenset[str] = DIRECTIONAL_KEYS


def compute_resolver_series(
    key: str,
    length: int,
    closes: Sequence[Decimal],
    *,
    highs: Sequence[Decimal] | None = None,
    lows: Sequence[Decimal] | None = None,
    volumes: Sequence[Decimal] | None = None,
) -> list[Decimal | None]:
    """Run a directional resolver's incremental compute over a bar series (post-V1 R8).

    Returns the per-bar output value (``None`` during warm-up / when undefined). Reuses the
    exact ``_build_reference_indicator`` compute the engine's conditions use, so an ESP
    validation-run certifies the SAME math the backtest engine runs — never a divergent
    second implementation. ``ta.vwap`` reads ``highs``/``lows``/``volumes`` (a zero-volume
    window is undefined -> ``None``, fail-closed); the MA family and ``ta.rsi`` read only
    ``closes``. Callers must pre-check ``key in VALIDATABLE_RESOLVER_KEYS``.
    """
    indicator = _build_reference_indicator(key, length)
    out: list[Decimal | None] = []
    for i, close in enumerate(closes):
        if isinstance(indicator, _Vwap):
            high = highs[i] if highs is not None and i < len(highs) else close
            low = lows[i] if lows is not None and i < len(lows) else close
            volume = volumes[i] if volumes is not None and i < len(volumes) else _ZERO
            out.append(indicator.update(close, high, low, volume))
        else:
            out.append(indicator.update(close))
    return out


def _feed_indicator(
    indicator: _MovingAverage | _Rsi | _Vwap,
    close: Decimal,
    high: Decimal,
    low: Decimal,
    volume: Decimal,
) -> Decimal | None:
    """Advance an inline reference/block indicator by one candle, routing the extra
    volume-weighted inputs only to a ``_Vwap`` (the MA/RSI computes read the close alone —
    their behaviour is byte-identical to before (d))."""
    if isinstance(indicator, _Vwap):
        return indicator.update(close, high, low, volume)
    return indicator.update(close)


@dataclass(slots=True)
class _ReferenceSeries:
    """One reference leg's computed series, with its own per-leg resampling state.

    Wraps one inline reference indicator (``_MovingAverage``/``_Rsi``/``_Vwap``) plus the
    optional coarser-timeframe aggregation (post-V1 (i)/(ii)/(d)). On the block's own
    timeframe (``resample_seconds is None``) it advances every bar — byte-identical to the
    (#53) two-package form for MA/RSI. On a coarser reference timeframe it aggregates the
    base candles (high=max, low=min, close=last, volume=sum) and advances the indicator only
    when a reference candle CLOSES (the first base bar of the next bucket), so the RHS never
    repaints from a still-forming candle (no look-ahead). The high/low/volume aggregation is
    inert for MA/RSI legs (they read the close alone) and feeds a ``_Vwap`` leg its candle."""

    indicator: _MovingAverage | _Rsi | _Vwap
    resample_seconds: int | None
    _bucket: int | None = field(init=False, default=None)
    _form_high: Decimal = field(init=False, default=_ZERO)
    _form_low: Decimal = field(init=False, default=_ZERO)
    _form_close: Decimal = field(init=False, default=_ZERO)
    _form_volume: Decimal = field(init=False, default=_ZERO)

    def advance(
        self,
        close: Decimal,
        high: Decimal,
        low: Decimal,
        volume: Decimal,
        timestamp: str | None,
    ) -> None:
        if self.resample_seconds is None:
            _feed_indicator(self.indicator, close, high, low, volume)
            return
        bucket = _htf_bucket(timestamp, self.resample_seconds) if timestamp else None
        if bucket is None:
            return  # unparseable/absent timestamp: hold the last completed reference candle
        if self._bucket is None:
            self._begin(bucket, high, low, close, volume)
            return
        if bucket == self._bucket:
            self._form_high = max(self._form_high, high)
            self._form_low = min(self._form_low, low)
            self._form_close = close
            self._form_volume += volume  # volume sums across the reference candle (for VWAP)
            return
        # A new reference bucket started: the previous reference candle is complete — advance
        # the RHS with its aggregated candle, then open the next forming reference candle.
        _feed_indicator(
            self.indicator, self._form_close, self._form_high, self._form_low, self._form_volume
        )
        self._begin(bucket, high, low, close, volume)

    def _begin(
        self, bucket: int, high: Decimal, low: Decimal, close: Decimal, volume: Decimal
    ) -> None:
        """Open a fresh forming reference candle from this base bar."""
        self._bucket = bucket
        self._form_high = high
        self._form_low = low
        self._form_close = close
        self._form_volume = volume

    @property
    def value(self) -> Decimal | None:
        return self.indicator.value


def _build_reference_chain(spec: ConditionSpec) -> list[_ReferenceSeries]:
    """The RHS reference legs of a condition — primary first, then the N-ary extras.

    Empty when the condition has no reference package (its RHS is a bounded ``reference``
    series or a constant ``threshold``). The ``extra_references`` (post-V1 (ii)) are only
    meaningful with a primary ``reference_key`` and are ignored without one (the plan layer
    forbids that configuration)."""
    if spec.reference_key is None:
        return []
    chain = [
        _ReferenceSeries(
            _build_reference_indicator(
                spec.reference_key, spec.reference_length or default_length(spec.reference_key)
            ),
            spec.reference_resample_seconds,
        )
    ]
    for extra in spec.extra_references:
        chain.append(
            _ReferenceSeries(
                _build_reference_indicator(extra.key, extra.length or default_length(extra.key)),
                extra.resample_seconds,
            )
        )
    return chain


def _chain_ordered(head: Decimal, rest: list[Decimal | None], descending: bool) -> bool:
    """Whether ``head`` and ``rest`` form a strictly monotonic chain.

    ``descending`` requires ``head > rest[0] > rest[1] > ...`` (the source is the largest —
    an ``above`` fan); otherwise strictly ascending (a ``below`` fan). Any ``None`` breaks the
    chain (fails closed). A single-element ``rest`` reduces to exactly one comparison, so the
    two-package (#53/#56) check is preserved byte-for-byte."""
    prev = head
    for value in rest:
        if value is None:
            return False
        if descending:
            if not prev > value:
                return False
        elif not prev < value:
            return False
        prev = value
    return True


class ConditionEvaluator:
    """Stateful per-condition comparator over the streamed bars.

    Each bar it reads the condition's SOURCE series and its RHS — the constant
    ``threshold`` or, when configured, a ``reference`` series — then evaluates the
    ``cond.*`` comparator: a LEVEL check (above/below), an EDGE cross (crosses_above/
    crosses_below, which needs the previous bar's pair) or a RANGE (between, over the
    ``lower``/``upper`` bounds). A satisfied check stays active for the condition's
    validity window; ``until_opposite_signal`` is open-ended and clears the moment the
    check fails. The parent ``BlockEvaluator`` reads ``satisfied``."""

    __slots__ = (
        "_active",
        "_active_left",
        "_prev_ref_values",
        "_prev_source",
        "_ref_series",
        "_spec",
    )

    def __init__(self, spec: ConditionSpec) -> None:
        self._spec = spec
        self._active = False
        self._active_left: int | None = None  # bars remaining (None = until it fails)
        self._prev_source: Decimal | None = None  # last bar's source (for cross edges)
        # RHS reference chain (post-V1 #53/(i)/(ii)): the primary ``reference_key`` leg plus
        # any ``extra_references``, each a separately-pinned indicator computed inline (its own
        # look-back + optional coarser timeframe). Empty for the bounded-reference/threshold
        # forms; a warming-up leg contributes ``None`` and fails the check closed.
        self._ref_series: list[_ReferenceSeries] = _build_reference_chain(spec)
        # Previous bar's RHS chain values (for cross edges), parallel to ``_ref_series``.
        self._prev_ref_values: list[Decimal | None] | None = None

    def update(
        self,
        *,
        close: Decimal,
        high: Decimal,
        low: Decimal,
        open_price: Decimal,
        indicator_value: Decimal | None,
        volume: Decimal | None = None,
        timestamp: str | None = None,
    ) -> None:
        window = _VALIDITY_BARS.get(self._spec.validity, 1)
        # Age a finite window BEFORE this bar's fresh check can refresh it.
        if self._active_left is not None and self._active:
            self._active_left -= 1
            if self._active_left <= 0:
                self._active = False
                self._active_left = None
        # Advance each RHS reference leg so its value is as-of this bar; a leg on a coarser
        # reference timeframe only advances when its own reference candle closes. Volume is
        # consumed only by a VWAP reference leg (post-V1 (d)); an absent volume defaults to 0.
        vol = _ZERO if volume is None else volume
        for ref in self._ref_series:
            ref.advance(close, high, low, vol, timestamp)
        source = self._series_value(
            self._spec.source, close, high, low, open_price, indicator_value
        )
        rhs_values = self._rhs_values(close, high, low, open_price, indicator_value)
        if self._raw_check(source, rhs_values):
            self._active = True
            self._active_left = window  # None => open-ended (until the check fails)
        elif window is None:
            # until_opposite_signal: an open-ended gate clears when the check fails.
            # (A momentary cross therefore stays active for exactly its firing bar.)
            self._active = False
            self._active_left = None
        self._prev_source = source
        self._prev_ref_values = rhs_values

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

    def _rhs_values(
        self,
        close: Decimal,
        high: Decimal,
        low: Decimal,
        open_price: Decimal,
        indicator_value: Decimal | None,
    ) -> list[Decimal | None]:
        """The comparator's right-hand side series, in precedence order: the reference chain
        (one or more separately-pinned indicators — two-package / N-ary), else a single-
        element bounded ``reference`` series, else the constant ``threshold``. A warming-up
        reference leg contributes ``None`` and fails the check closed."""
        if self._ref_series:
            return [ref.value for ref in self._ref_series]
        reference = self._spec.reference
        if reference is not None:
            return [self._series_value(reference, close, high, low, open_price, indicator_value)]
        return [self._spec.threshold]

    def _raw_check(self, source: Decimal | None, rhs_values: list[Decimal | None]) -> bool:
        """Evaluate the comparator over the source and its RHS chain.

        ``cond.between`` ignores the RHS (uses the ``lower``/``upper`` bounds). LEVEL/CROSS
        treat the RHS as a monotonic chain: ``cond.above``/``crosses_above`` require
        ``source > rhs[0] > rhs[1] > ...`` (source largest); ``cond.below``/``crosses_below``
        the reverse. A single-leg chain reduces EXACTLY to the (#53/#56) two-package check.
        Any missing value (warm-up) fails closed. Cross primitives additionally require the
        previous bar's chain to NOT already hold (the alignment is achieved THIS bar)."""
        key = self._spec.canonical_key
        if key == _COND_BETWEEN:
            lower, upper = self._spec.lower, self._spec.upper
            if source is None or lower is None or upper is None:
                return False
            return lower < source < upper
        if source is None or any(value is None for value in rhs_values):
            return False  # a missing series (warm-up) fails closed
        descending = key in (_COND_ABOVE, _COND_CROSSES_ABOVE)
        chain_now = _chain_ordered(source, rhs_values, descending)
        if key in (_COND_ABOVE, _COND_BELOW):
            return chain_now
        # Cross edges need the previous bar's (source, chain) to be fully established.
        prev_source, prev_refs = self._prev_source, self._prev_ref_values
        if prev_source is None or prev_refs is None or any(v is None for v in prev_refs):
            return False
        chain_prev = _chain_ordered(prev_source, prev_refs, descending)
        return chain_now and not chain_prev

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
        "_cur_bucket",
        "_form_close",
        "_form_high",
        "_form_low",
        "_form_open",
        "_form_ts",
        "_form_volume",
        "_is_rsi",
        "_is_vwap",
        "_ma",
        "_prev_close",
        "_prev_gate",
        "_prev_value",
        "_resample_seconds",
        "_rsi",
        "_spec",
        "_vwap",
    )

    def __init__(self, spec: IndicatorSpec) -> None:
        self._spec = spec
        self._is_rsi = spec.canonical_key == "ta.rsi"
        self._is_vwap = spec.canonical_key == _VWAP_KEY
        self._vwap = _Vwap(spec.length) if self._is_vwap else None
        self._ma = (
            None
            if self._is_rsi or self._is_vwap
            else _MovingAverage(spec.canonical_key, spec.length)
        )
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
        # Higher-timeframe resampling (post-V1 (c)): when set, base bars are aggregated
        # into the current forming higher-TF candle and the inner compute only advances on
        # a candle CLOSE (the first bar of the next bucket). ``None`` => base-TF compute.
        self._resample_seconds = spec.resample_seconds
        self._cur_bucket: int | None = None
        self._form_open: Decimal = _ZERO
        self._form_high: Decimal = _ZERO
        self._form_low: Decimal = _ZERO
        self._form_close: Decimal = _ZERO
        # Volume summed across the forming higher-TF candle (post-V1 (d)); fed to a VWAP
        # block's compute on candle close (inert for MA/RSI blocks, which read the close).
        self._form_volume: Decimal = _ZERO
        # Timestamp of the forming higher-TF candle's latest base bar (its close time). On a
        # candle close it is handed to ``_advance`` so nested per-condition reference
        # resampling (post-V1 (i)) buckets against the candle the trigger sees, not the raw
        # base bars. On the base-TF path each bar's own timestamp is passed straight through.
        self._form_ts: str | None = None

    def update(
        self,
        close: Decimal,
        high: Decimal | None = None,
        low: Decimal | None = None,
        open_price: Decimal | None = None,
        volume: Decimal | None = None,
        timestamp: str | None = None,
    ) -> None:
        # OHLC is optional so callers/tests with close-only series keep working; a
        # missing field degrades to the close (only price-source conditions read them).
        # Volume is consumed only by a VWAP block/leg (post-V1 (d)); absent volume = 0.
        high = close if high is None else high
        low = close if low is None else low
        open_price = close if open_price is None else open_price
        vol = _ZERO if volume is None else volume
        if self._resample_seconds is None:
            # Base-timeframe block: advance on every bar (Slice C behaviour). The bar's own
            # timestamp flows to the nested conditions for per-condition reference resampling.
            self._advance(close, high, low, open_price, vol, timestamp)
            return
        # Higher-timeframe block: aggregate the base bars into a coarser candle and
        # advance the inner compute only when that candle CLOSES — detected as the first
        # base bar of the NEXT bucket — so a signal is never read from a still-forming
        # candle (no look-ahead). The trailing partial candle is never finalized.
        bucket = _htf_bucket(timestamp, self._resample_seconds) if timestamp else None
        if bucket is None:
            return  # unparseable/absent timestamp: hold the last completed-candle signal
        if self._cur_bucket is None:
            self._begin_htf_candle(bucket, open_price, high, low, close, vol, timestamp)
            return
        if bucket == self._cur_bucket:
            self._form_high = max(self._form_high, high)
            self._form_low = min(self._form_low, low)
            self._form_close = close
            self._form_volume += vol  # volume sums across the higher-TF candle (for VWAP)
            self._form_ts = timestamp  # candle close time advances with each base bar
            return
        # A new bucket started: the previous higher-TF candle is complete — advance the
        # inner compute with its aggregated OHLCV (stamped at the candle's close time so a
        # coarser per-condition reference buckets against the candle, not the base bars),
        # then open the next forming candle.
        self._advance(
            self._form_close,
            self._form_high,
            self._form_low,
            self._form_open,
            self._form_volume,
            self._form_ts,
        )
        self._begin_htf_candle(bucket, open_price, high, low, close, vol, timestamp)

    def _begin_htf_candle(
        self,
        bucket: int,
        open_price: Decimal,
        high: Decimal,
        low: Decimal,
        close: Decimal,
        volume: Decimal,
        timestamp: str | None,
    ) -> None:
        """Start aggregating a fresh higher-TF candle from this base bar."""
        self._cur_bucket = bucket
        self._form_open = open_price
        self._form_high = high
        self._form_low = low
        self._form_close = close
        self._form_volume = volume
        self._form_ts = timestamp

    def _advance(
        self,
        close: Decimal,
        high: Decimal,
        low: Decimal,
        open_price: Decimal,
        volume: Decimal,
        timestamp: str | None = None,
    ) -> None:
        """Run one indicator/condition step over one (base or aggregated) candle."""
        # Age any active window BEFORE this bar's fresh event can refresh it.
        if self._active_left is not None and self._active_dir is not None:
            self._active_left -= 1
            if self._active_left <= 0:
                self._active_dir = None
                self._active_left = None
        if self._rsi is not None:
            value = self._rsi.update(close)
        elif self._vwap is not None:
            # VWAP is a volume-weighted price line; its price/VWAP cross is detected by the
            # MA-family branch of ``_detect`` (close vs the line), same shape as an MA cross.
            value = self._vwap.update(close, high, low, volume)
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
        # Feed the nested conditions THIS candle's prices + the parent's fresh indicator
        # value, so the gate is evaluated as-of the same candle as the trigger.
        for cond in self._cond_evals:
            cond.update(
                close=close,
                high=high,
                low=low,
                open_price=open_price,
                indicator_value=value,
                volume=volume,
                timestamp=timestamp,
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
    "VALIDATABLE_RESOLVER_KEYS",
    "VOLUME_WEIGHTED_KEYS",
    "BlockEvaluator",
    "ConditionEvaluator",
    "ConditionSpec",
    "IndicatorPlan",
    "IndicatorSpec",
    "ReferenceSeriesSpec",
    "SignalRule",
    "aggregate",
    "build_evaluators",
    "compute_resolver_series",
    "condition_direction",
    "default_length",
    "timeframe_seconds",
]
