"""Deterministic V1 backtest engine STUB (Stage 5a, doc 15 §9.3, §15).

Production V1 has no real market-data simulation engine yet, mirroring the honest
V1 stubs already shipped (2e candidate generation + dependency scan). This module
produces a DETERMINISTIC, reproducible result from the manifest's ``execution_key``
alone: the same pinned composition always yields byte-identical output (doc 15 §17
async reproducibility). It never reads live market data, the current Mainboard or
any 'latest' source, and it is pure — no DB, clock, network or real randomness.

When a real engine lands, only this module + ``metrics.py`` change; the RUN
admission, manifest, run lifecycle and result-materialization contracts stay put.
The synthetic timestamps/prices are labelled stub output and are NOT presented as
real market data (symbol/timeframe are left unresolved — never fabricated, L4).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

_MONEY = Decimal("0.01")
_PCT = Decimal("0.0001")
_RATIO = Decimal("0.01")
_HUNDRED = Decimal("100")


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


def _stream(key: str) -> Iterator[float]:
    """A deterministic [0, 1) pseudo-random stream seeded from ``key`` (stub only)."""
    counter = 0
    while True:
        digest = hashlib.sha256(f"{key}:{counter}".encode()).digest()
        counter += 1
        for offset in range(0, len(digest), 4):
            yield int.from_bytes(digest[offset : offset + 4], "big") / 4294967296.0


def _iso_day(index: int) -> str:
    """A deterministic synthetic UTC day from a fixed epoch (stub output only)."""
    month = 1 + (index // 28) % 12
    day = 1 + index % 28
    return f"2024-{month:02d}-{day:02d}T00:00:00Z"


def run_engine(
    execution_key: str,
    *,
    initial_capital: Decimal,
    item_count: int,
) -> EngineOutput:
    """Deterministically simulate a backtest from the manifest execution key."""
    draws = _stream(execution_key)
    trade_count = 8 + int(next(draws) * 8)
    equity = initial_capital
    peak = initial_capital
    trades: list[TradeRow] = []
    equity_points: list[EquityPoint] = [
        EquityPoint(
            seq=0,
            timestamp=_iso_day(0),
            equity=equity.quantize(_MONEY),
            drawdown=Decimal("0").quantize(_MONEY),
            exposure=Decimal("0").quantize(_PCT),
        )
    ]
    gross_profit = Decimal("0")
    gross_loss = Decimal("0")
    winners = 0
    stops = 0
    streak = 0
    max_stop_streak = 0

    for seq in range(1, trade_count + 1):
        direction = "long" if next(draws) < Decimal("0.55") else "short"
        entry_price = (Decimal("100") + Decimal(str(round(next(draws) * 50, 2)))).quantize(_MONEY)
        pnl_pct = Decimal(str(round((next(draws) - 0.42) * 6, 4)))
        reason_roll = next(draws)
        exposure = Decimal(str(round(next(draws), 4)))
        pnl = (equity * pnl_pct / _HUNDRED).quantize(_MONEY)
        if pnl_pct < 0:
            exit_reason = "stop_loss" if reason_roll < 0.6 else "exit_signal"
        else:
            exit_reason = "take_profit" if reason_roll < 0.6 else "exit_signal"
        exit_price = (entry_price * (Decimal("1") + pnl_pct / _HUNDRED)).quantize(_MONEY)
        equity = (equity + pnl).quantize(_MONEY)
        peak = max(peak, equity)
        drawdown = (peak - equity).quantize(_MONEY)
        if pnl > 0:
            winners += 1
            gross_profit += pnl
        else:
            gross_loss += -pnl
        if exit_reason == "stop_loss":
            stops += 1
            streak += 1
            max_stop_streak = max(max_stop_streak, streak)
        else:
            streak = 0
        trades.append(
            TradeRow(
                seq=seq,
                entry_time=_iso_day(seq * 2 - 1),
                exit_time=_iso_day(seq * 2),
                direction=direction,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl=pnl,
                exit_reason=exit_reason,
            )
        )
        equity_points.append(
            EquityPoint(
                seq=seq,
                timestamp=_iso_day(seq * 2),
                equity=equity,
                drawdown=drawdown,
                exposure=exposure,
            )
        )

    net_profit = (equity - initial_capital).quantize(_MONEY)
    net_profit_pct = (
        (net_profit / initial_capital * _HUNDRED).quantize(_PCT) if initial_capital > 0 else None
    )
    max_drawdown = max((point.drawdown for point in equity_points), default=Decimal("0"))
    max_drawdown_pct = (max_drawdown / peak * _HUNDRED).quantize(_PCT) if peak > 0 else Decimal("0")
    win_rate = (
        (Decimal(winners) / Decimal(trade_count) * _HUNDRED).quantize(_PCT) if trade_count else None
    )
    profit_factor = (gross_profit / gross_loss).quantize(_RATIO) if gross_loss > 0 else None
    romad = (
        (net_profit_pct / max_drawdown_pct).quantize(_RATIO)
        if net_profit_pct is not None and max_drawdown_pct > 0
        else None
    )

    summary: dict[str, Any] = {
        "symbol": None,
        "timeframe": None,
        "initial_capital": initial_capital.quantize(_MONEY),
        "final_equity": equity,
        "net_profit": net_profit,
        "net_profit_pct": net_profit_pct,
        "max_drawdown": max_drawdown.quantize(_MONEY),
        "max_drawdown_pct": max_drawdown_pct,
        "romad": romad,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_trades": trade_count,
        "total_stops": stops,
        "max_stop_streak": max_stop_streak,
        "total_winning_trades": winners,
    }
    signal_events = _signal_events(execution_key, trades)
    diagnostics = {
        "engine_kind": "v1_stub",
        "reproducibility_note": "Deterministic from manifest execution_key; not real market data.",
        "item_count": item_count,
        "decision_trace_count": len(signal_events),
        "warnings": [],
    }
    return EngineOutput(
        summary=summary,
        trades=trades,
        equity_points=equity_points,
        signal_events=signal_events,
        diagnostics=diagnostics,
    )


def _signal_events(execution_key: str, trades: list[TradeRow]) -> list[SignalEventRow]:
    """Decision-trace events — entry signals plus a filtered/no-entry marker.

    A signal event is NOT a fill (doc 15 §14): filtered/no-entry decisions are
    surfaced distinctly so the ledger is never double-counted from them.
    """
    events: list[SignalEventRow] = []
    for trade in trades:
        events.append(
            SignalEventRow(
                seq=len(events),
                event_time=trade.entry_time,
                event_type="entry_signal",
                direction=trade.direction,
                detail={"trade_seq": trade.seq},
            )
        )
    events.append(
        SignalEventRow(
            seq=len(events),
            event_time=_iso_day(1),
            event_type="filtered_no_entry",
            direction=None,
            detail={"reason": "restriction_filter"},
        )
    )
    return events


__all__ = [
    "EngineOutput",
    "EquityPoint",
    "SignalEventRow",
    "TradeRow",
    "run_engine",
]
