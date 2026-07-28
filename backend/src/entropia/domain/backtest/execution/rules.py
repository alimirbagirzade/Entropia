"""Cross-item portfolio rule evaluation (K-10c).

The four helpers the bar loop used to answer "what were the EARLIER-pinned items doing
at this moment": does a held window cover this instant, what is the total notional they
held, and does one of them hold the opposite direction on the same instrument.

Extracted from ``run_engine``'s closures with their bodies unchanged. They read the
pinned rules and WRITE only the two L4 gate flags, which now live on the ledger — so
the pair ``(led, rules)`` is the whole contract.

Every fail-closed reading is preserved verbatim, and they all point the same way: an
unplaceable moment is treated as covered by every prior window, and an unknown
instrument identity on either side counts as a conflict. An unplaceable or unnameable
thing can never RULE OUT a rule; it can only over-cover.
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.execution.constants import _ZERO
from entropia.domain.backtest.execution.state import (
    PortfolioRules,
    PriorItemInterval,
    _Ledger,
)
from entropia.domain.backtest.funding import parse_utc


def interval_covers(iv: PriorItemInterval, t_ms: int | None) -> bool:
    if t_ms is None:
        return True
    if iv.start_ms is not None and t_ms < iv.start_ms:
        return False
    return not (iv.end_ms is not None and t_ms > iv.end_ms)


def bar_epoch_ms(ts: str) -> int | None:
    """UTC epoch ms of a bar timestamp, ``None`` when unplaceable (fail closed:
    the portfolio gates treat an unplaceable moment as covered by every prior
    window — the date-blackout precedent, never trading through a rule).

    ``source_zone=None`` (K-01): bars are UTC-normalized at ingest."""
    parsed = parse_utc(ts, source_zone=None)
    return int(parsed.timestamp() * 1000) if parsed is not None else None


def prior_exposure_at(led: _Ledger, rules: PortfolioRules, t_ms: int | None) -> Decimal:
    """Total notional the earlier-pinned items hold at this moment (peak-notional
    basis — conservative; an unplaceable moment counts EVERY window, fail closed)."""
    total = _ZERO
    for iv in rules.prior_intervals:
        if interval_covers(iv, t_ms):
            total += iv.notional
    if t_ms is None and rules.prior_intervals:
        led.portfolio_time_unparseable_gate = True
    return total


def conflicts_with_prior(
    led: _Ledger, rules: PortfolioRules, direction: str, t_ms: int | None
) -> bool:
    """Does an earlier-pinned item hold the OPPOSITE direction on the same
    instrument at this moment? Unknown instrument identity on either side
    cannot RULE OUT a same-instrument conflict — fail closed (counts as
    conflicting) and surfaced via a dedicated L4 warning."""
    own = (rules.own_symbol or "").strip()
    for iv in rules.prior_intervals:
        if iv.direction == direction:
            continue
        other = (iv.symbol or "").strip()
        if own and other and own != other:
            continue
        if not interval_covers(iv, t_ms):
            continue
        if not (own and other):
            led.portfolio_symbol_unknown_gate = True
        if t_ms is None:
            led.portfolio_time_unparseable_gate = True
        return True
    return False
