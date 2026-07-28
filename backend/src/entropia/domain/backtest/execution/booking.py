"""Trade booking and the decision-trace journal (K-10b).

The three things ``run_engine`` did that WROTE to the run's accumulating state:
appending a decision event, closing (or part-closing) a position, and topping an open
position up with a partial-fill remainder.

They were closures because they mutated the loop's ``nonlocal`` tallies. K-10a moved
those tallies onto :class:`_Ledger`, which is what lets these move out here with their
bodies unchanged — the ledger is now passed in rather than captured.

``run_engine`` keeps three thin binders of the same names, so all ~40 existing call
sites are untouched; only the bodies moved. That is deliberate: rewriting call sites
is where a refactor of this shape silently changes behaviour.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from entropia.domain.backtest.execution.constants import _HUNDRED, _MONEY, _ONE, _PCT, _ZERO
from entropia.domain.backtest.execution.costs import FillCosts, _effective_fill
from entropia.domain.backtest.execution.state import (
    EquityPoint,
    SignalEventRow,
    TradeRow,
    _Bar,
    _Ledger,
    _Position,
)


def emit_event(
    led: _Ledger,
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
    led.signal_events.append(
        SignalEventRow(
            seq=len(led.signal_events),
            event_time=event_time,
            event_type=event_type,
            direction=direction,
            detail={"bar_seq": bar_seq, **detail},
        )
    )


def close_position(
    led: _Ledger,
    pos: _Position,
    costs: FillCosts,
    *,
    exit_time: str,
    exit_price_raw: Decimal,
    reason: str,
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
    is_full = fraction >= _ONE
    close_size = pos.size if is_full else pos.size * fraction
    is_long = pos.direction == "long"
    exit_eff = _effective_fill(
        exit_price_raw, is_buy=not is_long, half_spread=costs.half_spread, slip=costs.slippage
    )
    sign = Decimal("1") if is_long else Decimal("-1")
    gross = (exit_eff - pos.entry_price) * close_size * sign
    commission_lot = costs.commission * 2 if is_full else costs.commission * 2 * fraction
    pnl = (gross - commission_lot).quantize(_MONEY)
    equity_before = led.equity
    led.equity = (led.equity + pnl).quantize(_MONEY)
    led.peak = max(led.peak, led.equity)
    drawdown = (led.peak - led.equity).quantize(_MONEY)
    closed_notional = (pos.entry_price * close_size).quantize(_MONEY)
    exposure = (
        (closed_notional / equity_before * _HUNDRED).quantize(_PCT)
        if equity_before > _ZERO
        else _ZERO.quantize(_PCT)
    )
    if pnl > _ZERO:
        led.winners += 1
        led.gross_profit += pnl
    else:
        led.gross_loss += -pnl
    # F-07e: the restriction filters' realized ledger. Every realized lot (full or
    # partial) books into the UTC day's PnL; a strictly negative lot extends the
    # consecutive-loss streak, anything else (a 0-PnL lot is not a loss) resets it.
    led.day_realized += pnl
    if pnl < _ZERO:
        led.loss_streak += 1
    else:
        led.loss_streak = 0
    if reason == "stop_loss":
        led.stops_hit += 1
        led.stop_streak += 1
        led.max_stop_streak = max(led.max_stop_streak, led.stop_streak)
    else:
        led.stop_streak = 0
    seq = len(led.trades) + 1
    led.trades.append(
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
    led.equity_points.append(
        EquityPoint(
            seq=seq,
            timestamp=exit_time,
            equity=led.equity,
            drawdown=drawdown,
            exposure=exposure,
        )
    )
    if is_full:
        # Portfolio-rules slice: record the position's held window (entry->exit,
        # PEAK notional over its life) — the constraint input a LATER-pinned item
        # replays against. Always captured (cheap, additive); consumed only when
        # portfolio rules are configured.
        led.position_intervals.append(
            {
                "entry_time": pos.entry_time,
                "exit_time": exit_time,
                "direction": pos.direction,
                "peak_notional": max(pos.peak_notional, pos.entry_notional),
            }
        )
    if not is_full:
        led.partial_closes += 1
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
    emit_event(
        led,
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


def absorb_remainder(
    led: _Ledger,
    pos: _Position,
    costs: FillCosts,
    *,
    bar: _Bar,
    price_raw: Decimal,
    add_size: Decimal,
    action: str,
    bar_seq: int,
    partial_policy: str,
) -> None:
    """Top an open position up with a partial-fill remainder lot (F-07i C).

    Mirrors the F-07d scale-layer mutation: size-weighted average basis, notional
    refresh, one commission per extra fill. Stop LEVELS stay as installed at the
    initial entry (the documented fixed-for-life invariant). The lot is the SAME
    order's remainder — already sized/capped at intent time — so no re-capping."""
    fill_eff = _effective_fill(
        price_raw,
        is_buy=pos.direction == "long",
        half_spread=costs.half_spread,
        slip=costs.slippage,
    )
    new_size = pos.size + add_size
    new_basis = ((pos.entry_price * pos.size + fill_eff * add_size) / new_size).quantize(_MONEY)
    pos.entry_price = new_basis
    pos.size = new_size
    pos.entry_notional = (new_basis * new_size).quantize(_MONEY)
    pos.peak_notional = max(pos.peak_notional, pos.entry_notional)
    if costs.commission > _ZERO:
        led.equity = (led.equity - costs.commission).quantize(_MONEY)
    led.partial_fills += 1
    emit_event(
        led,
        "partial_fill",
        event_time=bar.timestamp,
        direction=pos.direction,
        bar_seq=bar_seq,
        detail={
            "position_seq": pos.position_seq,
            "policy": partial_policy,
            "action": action,
            "fill_price": str(fill_eff),
            "fill_size": str(add_size),
            "new_size": str(new_size),
            "entry_basis": str(new_basis),
        },
    )
