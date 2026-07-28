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

    # The run's four output journals. Append-only — they are never rebound, so they
    # needed no ``nonlocal``; they live here so an extracted booking function can take
    # ONE accumulator instead of four separate list parameters.
    signal_events: list[SignalEventRow] = field(default_factory=list)
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
