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
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

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
    direction: str  # "long" | "short"
    entry_time: str
    entry_price: Decimal  # cost-adjusted effective fill
    size: Decimal
    static_stop: Decimal | None
    trail_pct: Decimal | None
    trail_anchor: Decimal  # best price seen since entry (favourable extreme)
    entry_notional: Decimal


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
    modelled and fall back to notional sizing (surfaced as a diagnostics warning,
    never hidden — L4)."""
    sizing = config.position_sizing
    if sizing.method == "base_position_size" and sizing.base_position_size is not None:
        return True
    if sizing.method == "risk_based_sizing" and sizing.risk_based is not None:
        return True
    return _kelly_capital_fraction(sizing) is not None


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
    """Deterministic sizing: explicit base size, risk-based, Kelly, else all-in notional.

    ``base_position_size`` returns the explicit size. ``risk_based_sizing`` risks a
    fixed % of (non-negative) equity across the configured stop distance —
    ``size = equity * risk% / 100 / stop_loss_point`` — and is therefore independent
    of the entry price. ``formula_based_sizing`` with a valid ``kelly_criterion`` config
    allocates a fractional-Kelly slice of (non-negative) equity —
    ``size = equity * f* / entry_price`` — and is therefore entry-price DEPENDENT
    (Kelly sizes a fraction of CAPITAL; converting that to units divides by price),
    unlike risk-based. An unmodelled formula (``custom_formula`` / bad params) and any
    request missing its sub-config fall back to an all-in notional (surfaced as a
    diagnostics warning, L4). Every branch clamps to NON-NEGATIVE equity: a bust
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
    if entry_price > _ZERO:
        return (usable_equity / entry_price).quantize(_QTY)
    return _ZERO


def _position_size(config: StrategyConfig, entry_price: Decimal, equity: Decimal) -> Decimal:
    """Deterministic sizing (see ``_raw_position_size``) clamped to the configured
    ``position_size_limits`` min/max caps (§6). The clamp applies uniformly to EVERY
    sizing method — base, risk-based, Kelly and the notional fallback — so a global cap
    is honoured regardless of which sizing path produced the size. A missing limits
    subtree is a no-op, so behaviour is byte-identical to the pre-wiring engine."""
    size = _raw_position_size(config, entry_price, equity)
    return _clamp_to_limits(size, config.position_sizing.position_size_limits)


def _initial_static_stop(
    config: StrategyConfig, *, is_long: bool, entry_price: Decimal
) -> Decimal | None:
    """Tightest enabled percentage/absolute stop (trailing handled dynamically)."""
    protection = config.protection_stop_logic
    if protection is None:
        return None
    candidates: list[Decimal] = []
    pct = protection.percentage_stop
    if pct is not None and pct.enabled:
        distance = entry_price * (pct.loss_percentage / _HUNDRED)
        candidates.append(entry_price - distance if is_long else entry_price + distance)
    absolute = protection.absolute_stop
    if absolute is not None and absolute.enabled and absolute.absolute_price is not None:
        candidates.append(Decimal(absolute.absolute_price))
    if not candidates:
        return None
    # Tightest = closest to entry on the adverse side (highest for long, lowest for short).
    return max(candidates) if is_long else min(candidates)


def _trail_pct(config: StrategyConfig) -> Decimal | None:
    protection = config.protection_stop_logic
    if protection is None or protection.trailing_stop is None:
        return None
    trailing = protection.trailing_stop
    return trailing.trail_percentage / _HUNDRED if trailing.enabled else None


def _effective_stop(position: _Position) -> Decimal | None:
    """Combine the static stop with the trailing stop; return the tightest."""
    trailing: Decimal | None = None
    if position.trail_pct is not None:
        if position.direction == "long":
            trailing = position.trail_anchor * (Decimal("1") - position.trail_pct)
        else:
            trailing = position.trail_anchor * (Decimal("1") + position.trail_pct)
    stops = [s for s in (position.static_stop, trailing) if s is not None]
    if not stops:
        return None
    return max(stops) if position.direction == "long" else min(stops)


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
) -> EngineOutput:
    """Deterministically bar-replay one strategy over its pinned OHLCV bars.

    Entry/exit timing uses real built-in indicator signals when ``indicator_plan``
    resolves to at least one computable entry block; otherwise it falls back to the
    labelled deterministic breakout proxy (Slice B behaviour), so callers without a
    plan — and the pure unit tests — are unaffected."""
    config = strategy_config
    initial_capital = Decimal(config.data.initial_capital).quantize(_MONEY)
    long_ok, short_ok = _direction_flags(config.position_entry_logic.direction_mode)
    half_spread, slippage, commission = _cost_params(config)
    trail_pct = _trail_pct(config)

    plan_active = indicator_plan is not None and indicator_plan.has_entry
    entry_evals: list[BlockEvaluator] = (
        build_evaluators(indicator_plan.entry_specs) if plan_active and indicator_plan else []
    )
    exit_evals: list[BlockEvaluator] = (
        build_evaluators(indicator_plan.exit_specs) if plan_active and indicator_plan else []
    )

    equity = initial_capital
    peak = initial_capital
    trades: list[TradeRow] = []
    equity_points: list[EquityPoint] = [
        EquityPoint(0, "", initial_capital, _ZERO.quantize(_MONEY), _ZERO.quantize(_PCT))
    ]
    signal_events: list[SignalEventRow] = []
    window: deque[_Bar] = deque(maxlen=_BREAKOUT_WINDOW)
    position: _Position | None = None
    bars_seen = 0
    first_ts = ""
    last_bar: _Bar | None = None
    winners = 0
    stops_hit = 0
    stop_streak = 0
    max_stop_streak = 0
    suppressed_entries = 0
    gross_profit = _ZERO
    gross_loss = _ZERO

    def _close(exit_time: str, exit_price_raw: Decimal, reason: str, pos: _Position) -> None:
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
        signal_events.append(
            SignalEventRow(
                seq=len(signal_events),
                event_time=pos.entry_time,
                event_type="entry_signal",
                direction=pos.direction,
                detail={"trade_seq": seq},
            )
        )

    def _open(direction: str, bar: _Bar) -> _Position:
        """Open a position in ``direction`` at this bar's cost-adjusted fill."""
        is_long = direction == "long"
        entry_eff = _effective_fill(
            bar.close, is_buy=is_long, half_spread=half_spread, slip=slippage
        )
        size = _position_size(config, entry_eff, equity)
        return _Position(
            direction=direction,
            entry_time=bar.timestamp,
            entry_price=entry_eff,
            size=size,
            static_stop=_initial_static_stop(config, is_long=is_long, entry_price=entry_eff),
            trail_pct=trail_pct,
            trail_anchor=bar.close,
            entry_notional=(entry_eff * size).quantize(_MONEY),
        )

    def _plan_exit(pos: _Position, entry_signal: str | None, exit_hit: bool) -> bool:
        """Exit on an explicit exit signal or (opt-in) an opposite entry signal."""
        if exit_hit:
            return True
        opposite = entry_signal is not None and entry_signal != pos.direction
        return bool(opposite and indicator_plan is not None and indicator_plan.exit_on_opposite)

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

            if position is not None:
                # (2) protection / stop / exit against this bar (intrabar touch).
                if position.direction == "long":
                    position.trail_anchor = max(position.trail_anchor, bar.high)
                else:
                    position.trail_anchor = min(position.trail_anchor, bar.low)
                stop = _effective_stop(position)
                exited = False
                if stop is not None and (
                    (position.direction == "long" and bar.low <= stop)
                    or (position.direction == "short" and bar.high >= stop)
                ):
                    _close(bar.timestamp, stop, "stop_loss", position)
                    position, exited = None, True
                if not exited and position is not None:
                    if plan_active:
                        if _plan_exit(position, entry_signal, exit_hit):
                            _close(bar.timestamp, bar.close, "exit_signal", position)
                            position = None
                    elif _exit_proxy(position, bar, window):
                        _close(bar.timestamp, bar.close, "exit_signal", position)
                        position = None
            elif plan_active:
                # (3a) real indicator entry (only when flat, respecting the direction bias).
                if entry_signal is not None:
                    if (entry_signal == "long" and not long_ok) or (
                        entry_signal == "short" and not short_ok
                    ):
                        suppressed_entries += 1
                    else:
                        position = _open(entry_signal, bar)
            elif len(window) == _BREAKOUT_WINDOW:
                # (3b) breakout entry proxy (only when flat, with a full look-back).
                highest = max(b.high for b in window)
                lowest = min(b.low for b in window)
                want_long = bar.close > highest
                want_short = bar.close < lowest
                if (want_long and not long_ok) or (want_short and not short_ok):
                    suppressed_entries += 1
                elif want_long or want_short:
                    # long wins a same-bar tie (deterministic); breakout sides are exclusive.
                    position = _open("long" if want_long else "short", bar)

            window.append(bar)

    # End-of-data: close any open position at the last bar's close (never left dangling).
    if position is not None and last_bar is not None:
        _close(last_bar.timestamp, last_bar.close, "end_of_data", position)
        position = None

    if suppressed_entries:
        signal_events.append(
            SignalEventRow(
                seq=len(signal_events),
                event_time=first_ts,
                event_type="filtered_no_entry",
                direction=None,
                detail={"reason": "direction_restriction", "count": suppressed_entries},
            )
        )

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
        "timeframe": None,
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
    }
    warnings: list[str] = []
    if not bars_seen:
        warnings.append("no_bars_in_source")
    if not _sizing_is_honored(config):
        # formula sizing (and a risk_based request without its sub-config) is not
        # modelled; the run used notional sizing instead. Surface the divergence
        # rather than hide it (L4). risk_based_sizing with a sub-config IS honored.
        warnings.append(f"position_sizing_method_unsupported:{config.position_sizing.method}")
    if indicator_plan is not None:
        # Blocks the native-trigger foundation could not compute (deferred sources,
        # timeframe overrides, non-directional keys) are surfaced, never hidden (L4).
        warnings.extend(indicator_plan.unresolved)
        if not plan_active:
            warnings.append("indicator_plan_empty_fallback_proxy")
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
        "item_count": item_count,
        "decision_trace_count": len(signal_events),
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


__all__ = [
    "ENTRY_MODEL",
    "EngineOutput",
    "EquityPoint",
    "SignalEventRow",
    "TradeRow",
    "run_engine",
]
