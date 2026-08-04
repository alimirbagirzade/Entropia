"""Order matching, intrabar prints and protection-stop resolution (K-09 slice a).

Extracted VERBATIM from ``domain.backtest.engine``: everything that answers "did this
order fill, at what level, and which stop won this bar" — the modelled-execution
predicates, the limit level resolver, the tick/print stream (``_Tick`` ->
``_TickCursor`` -> touch/trigger search) and the F-08 stop combination engine
(``_resolve_stop``).

Also here, and NEW as extracted functions rather than closures: ``limit_touch_evidence``
and ``decide_partial_fill``. Both were nested inside ``run_engine``, but neither
actually needed the loop's mutable state — they only read it. Lifting them out makes
the F-07i partial-fill policy table directly testable, which matters because it is the
subtlest branch in the engine: whether a resting order fills whole, fills partially, or
is rejected below its minimum decides how much size a run ever holds.

The never-fabricate rules they carry are unchanged. A print-less bar keeps the coarse
bar-touch — data sparsity is never proof of no fill. Size-less print evidence degrades
to the full-fill model rather than inventing a fraction. And a tick-backed entry timing
makes the print path authoritative, so a bar extreme the prints never confirm does not
fill.

Imports point DOWNWARD only (``execution.constants`` / ``execution.state``), never back
at ``engine``, which calls into this module from inside ``run_engine``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from entropia.domain.backtest.execution.constants import _HUNDRED, _ONE, _ZERO
from entropia.domain.backtest.execution.state import _Bar, _dec, _Position
from entropia.domain.backtest.funding import parse_utc

if TYPE_CHECKING:
    from entropia.domain.strategy.config import StopOrderDetails, StrategyConfig


def execution_timing_is_modelled(config: StrategyConfig) -> bool:
    """Public predicate: are BOTH entry and exit execution timings modelled (F-07a/F-07i C)?

    The single shared source of truth for "modelled timing", imported by the readiness
    validator so Ready Check's ``STRATEGY_EXECUTION_TIMING_UNSUPPORTED`` blocker and the
    engine's fail-closed entry gate agree on exactly one definition. The base bar-replay
    modes are always modelled. The tick-dependent modes (``intrabar_touch``,
    ``limit_fill_simulation``, ``stop_limit_priority_simulation``) are modelled ONLY when
    the strategy demands tick data (``tick_data_required`` — 'Use Tick Data' = Yes), which
    chains Ready Check availability -> manifest pin -> worker tick stream, so the mode
    runs over the real print path; ``limit_fill_simulation`` additionally needs a
    limit-backed order type (there is no limit order to simulate otherwise). Anything
    else is blocked at Ready Check AND opens no position if a stale readiness state
    slips through to the worker — never silently downgraded to a fill model it did not
    request."""
    execution = config.data.execution
    entry, exit_ = execution.entry_timing, execution.exit_timing
    tick_backed = tick_data_required(config)
    entry_ok = entry in _ENTRY_TIMING_MODELLED or (
        entry in _TICK_ENTRY_TIMINGS
        and tick_backed
        and (
            entry != "limit_fill_simulation"
            or config.data.order_config.type in _LIMIT_BACKED_ORDER_TYPES
        )
    )
    exit_ok = exit_ in _EXIT_TIMING_MODELLED or (exit_ in _TICK_EXIT_TIMINGS and tick_backed)
    return entry_ok and exit_ok


def _fill_schedule(timing: str) -> str:
    """Map a timing enum to a fill schedule: ``immediate`` / ``next_open`` / ``next_close``
    / ``touch``.

    ``intrabar_touch`` (F-07i C) rests the fill as a TOUCH order at the signal price and
    fills on a later print-touch of that level. ``limit_fill_simulation`` maps to
    ``immediate`` (the configured limit order machinery governs the fill, not the
    schedule); ``stop_limit_priority_simulation`` maps to ``immediate`` (exit fills at
    the signal close — its substance is the same-bar stop-then-limit print sequence in
    the (1c) block). Immediate / market-fill (and any unmodelled value) map to
    ``immediate`` — the unmodelled case is inert because the entry gate blocks trading
    unless ``execution_timing_is_modelled`` holds (fail-closed backstop to Ready Check)."""
    if timing == "next_candle_open":
        return "next_open"
    if timing == "next_candle_close":
        return "next_close"
    if timing == "intrabar_touch":
        return "touch"
    return "immediate"


def _stop_trigger_is_modelled(stop: StopOrderDetails | None) -> bool:
    """Is a stop trigger derivable from the saved ``stop`` subtree (F-07h)?

    Requires the subtree itself (a triggerless stop is unexecutable), a modelled
    activation rule, and — for the offset rules — a present ``trigger_offset``."""
    if stop is None or stop.activation_rule not in _MODELLED_STOP_ACTIVATION_RULES:
        return False
    return not (stop.activation_rule in _OFFSET_ACTIVATION_RULES and stop.trigger_offset is None)


def order_execution_is_modelled(config: StrategyConfig) -> bool:
    """Public predicate: is this strategy's order-type execution modelled (F-07b/h/i C)?

    The single shared source of truth imported by the readiness validator so Ready Check's
    ``STRATEGY_ORDER_TYPE_UNSUPPORTED`` blocker and the engine's fail-closed entry gate
    agree on exactly one definition. market / simulation → market fill; limit → the
    working-order model (a modelled price rule + a modelled partial-fill policy);
    stop → the resting-trigger model (a modelled activation rule with its offset);
    stop-limit → the trigger model AND the limit working-order model (both legs).

    Partial-fill policies other than ``not_allowed`` are modelled ONLY when the strategy
    demands tick data (F-07i C — the filled fraction is computed from the print path's
    trade sizes; without prints it is unknowable and stays fail-closed, never a fabricated
    fraction). A ``best_bid_ask`` price rule stays NOT modelled regardless: it needs an
    observed bid/ask QUOTE series (Master Ref §2.3 Spread/Execution dataset), which the
    tick/trade print path does not carry. A missing/invalid trigger or an unmodelled rule
    → blocked at Ready Check AND opens no position if a stale readiness state reaches the
    worker."""
    order = config.data.order_config
    if order.type in _MARKET_ORDER_TYPES:
        return True
    tick_backed = tick_data_required(config)
    if order.type == "limit_order":
        limit = order.limit
        return (
            limit is not None
            and limit.price_rule in _MODELLED_LIMIT_PRICE_RULES
            and (limit.partial_fill_policy == "not_allowed" or tick_backed)
        )
    if order.type == "stop_order":
        return _stop_trigger_is_modelled(order.stop)
    if order.type == "stop_limit_order":
        limit = order.limit
        return (
            _stop_trigger_is_modelled(order.stop)
            and limit is not None
            and limit.price_rule in _MODELLED_LIMIT_PRICE_RULES
            and (limit.partial_fill_policy == "not_allowed" or tick_backed)
        )
    return False


def tick_data_required(config: StrategyConfig) -> bool:
    """Public predicate: does this strategy DEMAND an intrabar tick path (F-07i-A)?

    'Use Tick Data = Yes' saves ``intrabar_policy.tick_policy = 'require'`` (doc 02
    Data & Execution row; Master Ref §6.4). 'None' / 'No' (``inherit`` / ``disable``)
    never demand tick data — ``inherit`` falls back to the conservative OHLCV
    resolution and ``disable`` forces it even when tick data exists. The single shared
    source of truth imported by the readiness command so Ready Check's
    ``TICK_DATA_UNAVAILABLE`` blocker has exactly one definition of "requires tick".

    NOTE (F-07i): sub-slice A wired the REQUIREMENT to Ready Check (Master Ref §11.2
    / line ~3558: an unmet requirement blocks RUN rather than silently resolving over
    OHLCV); sub-slice B pins the approved tick revision into the RUN manifest at
    admission and replays its real intrabar print path (true ``first_trigger_wins``
    stop order — see ``_TickCursor`` / ``_first_tick_touch``); sub-slice C executes
    the tick-dependent EXECUTION settings over that path (``intrabar_touch`` /
    ``limit_fill_simulation`` / ``stop_limit_priority_simulation`` timings +
    partial-fill policies) — each modelled ONLY when this predicate holds, so the
    demand->availability->pin->stream chain is what unlocks them
    (``execution_timing_is_modelled`` / ``order_execution_is_modelled``). A
    ``best_bid_ask`` price rule stays fail-closed regardless: it needs an observed
    bid/ask QUOTE series, which the tick/trade print path does not carry."""
    return config.data.intrabar_policy.tick_policy == "require"


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
# F-07i (C): the tick-dependent timing modes. Modelled ONLY when the strategy itself
# DEMANDS tick data ('Use Tick Data' = Yes -> ``tick_data_required``): only then is the
# intrabar print path guaranteed present at run time (Ready Check blocks RUN when no
# approved tick revision exists — (i)a; admission pins it; the worker streams it — (i)B),
# so the mode is executed over the REAL print path, never imitated (doc 02 / Master Ref
# ~3558). Without the demand the modes stay a Ready Check blocker + an inert engine run.
_TICK_ENTRY_TIMINGS = frozenset({"intrabar_touch", "limit_fill_simulation"})
_TICK_EXIT_TIMINGS = frozenset({"intrabar_touch", "stop_limit_priority_simulation"})
# ``limit_fill_simulation`` simulates the CONFIGURED limit order's fill over the print
# path — with a market-like order type there is no limit order to simulate (fail closed).
_LIMIT_BACKED_ORDER_TYPES = frozenset({"limit_order", "stop_limit_order"})


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


# Canonical §9.2 stop precedence AFTER any logic blocks (which come first, in display
# order): percentage, then trailing, then absolute. Used for priority_order resolution
# when no explicit stop_priority_order is configured, and as the deterministic tie-break
# for most_conservative.
_CANONICAL_PRICE_STOP_ORDER = ("percentage", "trailing", "absolute")


def _limit_price(price_rule: str, reference: Decimal, offset: Decimal) -> Decimal:
    """Resolve a limit level from a price rule + reference price + offset (F-07b).

    ``entry_signal_price`` rests at the reference (the signal / re-price bar's close);
    ``signal_price_minus_offset`` / ``_plus_offset`` shift it by the configured magnitude."""
    if price_rule == "signal_price_minus_offset":
        return reference - offset
    if price_rule == "signal_price_plus_offset":
        return reference + offset
    return reference


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


@dataclass(frozen=True, slots=True)
class _Tick:
    """One normalized intrabar tick/trade print (canonical tick fields, doc 11).

    ``size`` is the print's traded quantity (the canonical optional ``size`` column,
    F-07i C) — ``None`` when the revision does not carry it. Partial-fill fractions are
    computable only from prints WITH sizes; a size-less path degrades to the coarse
    full-fill model (surfaced, never guessed). Size units are assumed to be the same
    base units the position size uses (documented L4 boundary — a quote-denominated
    size column would skew the fraction)."""

    epoch_ms: int
    price: Decimal
    size: Decimal | None = None


def _tick_epoch_ms(timestamp: str) -> int | None:
    """Parse a tick timestamp (ISO-8601 or bare epoch) to UTC epoch MILLISECONDS.

    Millisecond resolution (not the bar path's whole seconds) because in-bar print
    ORDER is the whole point of the tick path. ``None`` on anything unparseable —
    the print is dropped fail-closed, never guessed into a bar window."""
    text = timestamp.strip()
    if not text:
        return None
    if text.isdigit():
        value = int(text)
        return value if len(text) >= 13 else value * 1000
    # source_zone=None (K-01): tick data is UTC-normalized at ingest; a naive print
    # is dropped fail-closed rather than guessed into a bar window at the wrong hour.
    parsed = parse_utc(text, source_zone=None)
    if parsed is None:
        return None
    # round(), not int(): float epoch*1000 can land at x.9998 for sub-second ISO
    # fractions, and truncation would shift the print 1ms early.
    return round(parsed.timestamp() * 1000)


def _normalize_tick(raw: dict[str, Any]) -> _Tick | None:
    """Project a raw tick/trade row to a typed print; drop rows missing time or price.

    Fail-closed: a row whose ``timestamp`` cannot be parsed or whose ``price`` is not
    a positive decimal can never be proven to belong to a bar's intrabar window (doc
    02: unavailable detail is never imitated), so it is dropped rather than guessed."""
    epoch = _tick_epoch_ms(str(raw.get("timestamp", "")))
    if epoch is None:
        return None
    try:
        price = _dec(raw["price"])
    except (KeyError, TypeError, ArithmeticError, ValueError):
        return None
    if price <= _ZERO:
        return None
    # F-07i (C): the print's traded quantity (canonical optional ``size`` column). A
    # missing/unparseable/non-positive size degrades to None — the print still orders
    # the price path; only the partial-fill fraction computation skips it.
    size: Decimal | None = None
    raw_size = raw.get("size")
    if raw_size is not None:
        try:
            parsed_size = _dec(raw_size)
        except (TypeError, ArithmeticError, ValueError):
            parsed_size = None
        if parsed_size is not None and parsed_size > _ZERO:
            size = parsed_size
    return _Tick(epoch_ms=epoch, price=price, size=size)


class _TickCursor:
    """Forward-only cursor aligning a global tick stream to per-bar intrabar windows.

    A bar timestamped ``T`` with base span ``S`` owns the prints in ``[T, T+S)``.
    Ordering contract: the processed tick asset is globally time-ordered (the same
    normalization contract the processed bar stream carries); the cursor stops pulling
    at the first print at/after the window end and buffers it for the next bar, so a
    print arriving BEHIND the already-consumed window is dropped fail-closed — it can
    no longer be attributed to its true bar and is never applied to a later one.
    Prints inside one window are stably sorted by epoch so equal-millisecond prints
    keep their source order — deterministic for a given asset. Bounded memory: at most
    one bar window of prints is resident."""

    __slots__ = ("_exhausted", "_pending", "_rows", "_span_ms")

    def __init__(self, batches: Iterator[list[dict[str, Any]]], span_seconds: int) -> None:
        self._rows = (row for batch in batches for row in batch)
        self._span_ms = span_seconds * 1000
        self._pending: _Tick | None = None
        self._exhausted = False

    def for_bar(self, bar_timestamp: str) -> tuple[_Tick, ...]:
        """The bar's intrabar prints in true time order (empty when none/unalignable)."""
        start = _tick_epoch_ms(bar_timestamp)
        if start is None:
            return ()
        end = start + self._span_ms
        collected: list[_Tick] = []
        if self._pending is not None:
            if self._pending.epoch_ms >= end:
                return ()  # the buffered print belongs to a later bar
            if self._pending.epoch_ms >= start:
                collected.append(self._pending)
            self._pending = None  # behind the window -> dropped fail-closed
        while not self._exhausted:
            row = next(self._rows, None)
            if row is None:
                self._exhausted = True
                break
            tick = _normalize_tick(row)
            if tick is None:
                continue
            if tick.epoch_ms >= end:
                self._pending = tick
                break
            if tick.epoch_ms >= start:
                collected.append(tick)
            # else: behind the window — dropped fail-closed (pre-range / out-of-order)
        collected.sort(key=lambda t: t.epoch_ms)  # stable: equal-ms keep source order
        return tuple(collected)


def _first_tick_touch(
    levels: dict[str, Decimal],
    ticks: tuple[_Tick, ...],
    *,
    is_long: bool,
    priority: dict[str, int],
) -> str | None:
    """The FIRST price-stop level the bar's tick path touches, in true time order.

    Walks the intrabar prints chronologically; the first print that reaches any level
    resolves the winner. A single print reaching several levels at once (a gap trade
    through the stack) resolves to the level a continuous path would have touched
    first — the one closest to the pre-gap price (long: highest; short: lowest) —
    with the priority index as the deterministic equal-level tie-break. ``None`` when
    no print reaches any level (the tick path contradicts the bar's OHLC extremes —
    the caller falls back to the conservative model, never a guessed order)."""
    for tick in ticks:
        touched = [
            key
            for key, level in levels.items()
            if (tick.price <= level if is_long else tick.price >= level)
        ]
        if not touched:
            continue
        if is_long:
            return max(touched, key=lambda k: (levels[k], -priority.get(k, len(priority))))
        return min(touched, key=lambda k: (levels[k], priority.get(k, len(priority))))
    return None


def _touching_ticks(ticks: tuple[_Tick, ...], level: Decimal, *, is_buy: bool) -> tuple[_Tick, ...]:
    """The prints that would fill an order resting at ``level`` (F-07i C).

    A BUY resting at ``level`` fills against prints trading at/below it; a SELL against
    prints at/above it (standard touch/limit semantics). Order is preserved — the first
    element is the true first touch."""
    if is_buy:
        return tuple(t for t in ticks if t.price <= level)
    return tuple(t for t in ticks if t.price >= level)


def _first_trigger_index(
    ticks: tuple[_Tick, ...], trigger: Decimal, *, is_long: bool
) -> int | None:
    """Index of the first print that fires a stop ENTRY trigger (long buy-stop: at/above;
    short sell-stop: at/below), or ``None`` when the print path never reaches it."""
    for idx, tick in enumerate(ticks):
        if tick.price >= trigger if is_long else tick.price <= trigger:
            return idx
    return None


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
    """Resolved protection-stop firing for one bar (F-08 combination engine).

    ``trigger_price`` and ``price`` are two DIFFERENT facts, deliberately kept apart
    (Master Ref §9.2 has the ledger carry a ``trigger_price`` and never equates it to the
    fill): the first is the level whose breach fired the rule — the evidence for WHY this
    stop won — and the second is the price the exit could actually have executed at. They
    differ only when the bar gapped past the level (see ``_attainable_stop_fill``);
    collapsing them into one field loses whichever question the reader is asking."""

    price: Decimal  # executable exit price (gap-adjusted for a price stop)
    trigger_price: Decimal  # the winning rule's own level — trace evidence, not the fill
    executed_key: str  # winning stop key (e.g. "percentage" / "logic:<block_id>")
    triggered: tuple[str, ...]  # every stop key that fired this bar (sorted)
    approximated_first: bool  # first_trigger_wins resolved to conservative over OHLCV
    tick_resolved: bool = False  # first_trigger_wins resolved by the REAL tick order (F-07i B)

    @property
    def gap_adjusted(self) -> bool:
        """Did the bar gap past the winning level, so the fill is worse than the trigger?"""
        return self.price != self.trigger_price


def _attainable_stop_fill(level: Decimal, bar: _Bar, *, is_long: bool) -> Decimal:
    """The first price a triggered PRICE stop could actually have executed at.

    A level inside the bar's range executes at the level. When the bar OPENS already
    beyond it, the level never existed at any point in that bar, so the first attainable
    price is the open: long (a sell) ``min(level, open)``, short (a buy)
    ``max(level, open)``.

    This is not an intrabar-path assumption — the open is a boundary FACT carried by
    OHLCV, not the ordering guess Master Ref §9.3 forbids. It is also the exact mirror of
    the rule this engine already applies to a gapped stop ENTRY (``max(trigger, open)``
    long, ``min`` short — see ``_WorkingStop``): one rule, two signs. Booking the
    untouchable level instead understates the loss on every gapped stop-out, always in the
    run's favour.

    Logic-Based stops never come here: they fill at ``bar.close``, which is inside the bar
    by construction, and clamping that against the open would move a price that was always
    attainable."""
    return min(level, bar.open) if is_long else max(level, bar.open)


def _resolve_stop(
    config: StrategyConfig,
    position: _Position,
    bar: _Bar,
    *,
    logic_enabled: list[str],
    logic_triggered: list[str],
    ticks: tuple[_Tick, ...] = (),
) -> _StopOutcome | None:
    """Combine every enabled protection stop rule for THIS bar (Master Ref §9.1/§9.3).

    Enabled rules = each enabled price stop (percentage / absolute / trailing) plus each
    enabled Logic-Based Stop Block (``logic_enabled``). A price stop TRIGGERS when the
    bar's adverse extreme touches its level (long: ``low <= level``; short:
    ``high >= level``) and executes at that level — or, when the bar OPENED already past
    it, at the open, which is the first price that actually existed
    (``_attainable_stop_fill``). A logic block triggers when it emits a
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
    priority = _stop_priority_index(
        protection.stop_priority_order if protection is not None else None, logic_enabled
    )
    approximated_first = False
    if resolution == "first_trigger_wins":
        # F-07i (B): a real intrabar tick path resolves the TRUE first touch among the
        # bar-triggered PRICE stops — a logic stop confirms only at the bar close, so
        # any intrabar price touch precedes it by construction. Without ticks — or when
        # the tick path never reaches a bar-triggered level (incomplete/contradictory
        # coverage) — the order stays unknowable over OHLCV: resolve to the
        # conservative model and flag it (Master Ref §9.3), never faked.
        price_triggered = {key: triggered[key] for key in triggered if key in price_levels}
        winner = (
            _first_tick_touch(price_triggered, ticks, is_long=is_long, priority=priority)
            if ticks and price_triggered
            else None
        )
        if winner is not None:
            return _StopOutcome(
                price=_attainable_stop_fill(triggered[winner], bar, is_long=is_long),
                trigger_price=triggered[winner],
                executed_key=winner,
                triggered=tuple(sorted(triggered)),
                approximated_first=False,
                tick_resolved=True,
            )
        resolution = "most_conservative"
        approximated_first = True

    if resolution in ("priority_order", "record_all_execute_highest"):
        winner = min(triggered, key=lambda k: priority.get(k, len(priority)))
    else:  # most_conservative: tightest adverse move, canonical priority as tie-break
        winner = min(
            triggered,
            key=lambda k: (abs(entry - triggered[k]), priority.get(k, len(priority))),
        )

    # The gap clamp is applied AFTER the winner is chosen, never before: the selection
    # comparators above read each rule's own LEVEL, so clamping first would collapse every
    # gapped-through level onto the same open price and silently change which rule is
    # reported as executed. A logic stop keeps its bar-close fill (always attainable).
    level = triggered[winner]
    return _StopOutcome(
        price=_attainable_stop_fill(level, bar, is_long=is_long)
        if winner in price_levels
        else level,
        trigger_price=level,
        executed_key=winner,
        triggered=tuple(sorted(triggered)),
        approximated_first=approximated_first,
    )


@dataclass(frozen=True, slots=True)
class PartialFillDecision:
    """How a TOUCHED resting entry order resolves against its print-size evidence.

    ``outcome`` is one of:

    * ``"full"`` — the F-07b model verbatim: the whole planned size books at the level.
      Reached when partial fills are off, when there is no usable print-size evidence,
      or when the evidence covers the whole planned size.
    * ``"rejected_below_minimum"`` — a ``minimum_50_percent`` order whose evidence
      covers less than half the plan. Nothing books; the order keeps resting whole.
    * ``"partial"`` — ``filled_size`` books at the level and ``remainder`` is disposed
      per policy (cancelled / market-filled / left resting).

    ``evidence_missing`` marks the degraded case: partial fills are active and the bar
    HAS prints, but none carry a size. The fill falls back to the coarse full-fill model
    and the run is flagged L4 — a fraction is never fabricated from size-less evidence.
    """

    outcome: str
    filled_size: Decimal
    remainder: Decimal
    evidence_missing: bool


def limit_touch_evidence(
    limit_price: Decimal,
    direction: str,
    bar: _Bar,
    ticks: tuple[_Tick, ...],
    *,
    tick_entry_authority: bool,
) -> tuple[bool, tuple[_Tick, ...]]:
    """(touched, touching_prints) for a resting order against THIS bar (F-07i C).

    Bar-touch (low/high reaches the level) is the base F-07b model. Under a tick-backed
    ENTRY timing a bar WITH prints makes the print path AUTHORITATIVE: the order fills
    only if a print actually reaches the level — a bar extreme the prints never confirm
    does not fill (that is what the simulation modes promise). A print-less bar keeps
    the coarse bar-touch: data sparsity is never treated as proof of no fill. The
    touching prints double as the partial-fill size evidence."""
    is_buy = direction == "long"
    bar_touched = bar.low <= limit_price if is_buy else bar.high >= limit_price
    if not ticks:
        return bar_touched, ()
    prints = _touching_ticks(ticks, limit_price, is_buy=is_buy)
    if tick_entry_authority:
        return bool(prints), prints
    return bar_touched, prints


def decide_partial_fill(
    *,
    planned: Decimal,
    prints: tuple[_Tick, ...],
    partial_active: bool,
    partial_policy: str,
) -> PartialFillDecision:
    """Apply the configured partial-fill policy to a touched order's print evidence.

    Pure: it reads the plan and the prints and returns what should happen. Booking the
    fill, emitting the trace events and disposing of the remainder stay in the bar loop,
    where the position and counters live."""
    sized = [t for t in prints if t.size is not None]
    available = sum((t.size for t in sized if t.size is not None), _ZERO)
    evidence_missing = bool(partial_active and planned > _ZERO and prints and not sized)
    if not partial_active or planned <= _ZERO or not sized or available >= planned:
        return PartialFillDecision(
            outcome="full",
            filled_size=planned,
            remainder=_ZERO,
            evidence_missing=evidence_missing,
        )
    if partial_policy == "minimum_50_percent" and available * 2 < planned:
        return PartialFillDecision(
            outcome="rejected_below_minimum",
            filled_size=available,
            remainder=planned - available,
            evidence_missing=evidence_missing,
        )
    return PartialFillDecision(
        outcome="partial",
        filled_size=available,
        remainder=planned - available,
        evidence_missing=evidence_missing,
    )
