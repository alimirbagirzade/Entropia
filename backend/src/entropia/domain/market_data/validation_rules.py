"""Pure per-type market-data validation rules (doc 11 §, AT #7-#9).

Each rule takes a single typed row and returns a ``ValidationStatus``. No I/O.
Numeric inputs are ``Decimal`` (or decimal-parseable ``str``) — never ``float``
(project DB rule D6). Side values for ticks are preserved, never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from entropia.domain.lifecycle.enums import ValidationStatus
from entropia.domain.market_data.enums import TradeSide

DecimalLike = Decimal | str | int


def _as_decimal(value: DecimalLike) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"'{value}' is not a valid decimal.") from exc


@dataclass(frozen=True, slots=True)
class OhlcvRow:
    open: DecimalLike
    high: DecimalLike
    low: DecimalLike
    close: DecimalLike
    volume: DecimalLike | None = None


@dataclass(frozen=True, slots=True)
class TickRow:
    price: DecimalLike
    side: TradeSide = TradeSide.UNKNOWN


@dataclass(frozen=True, slots=True)
class SpreadRow:
    bid: DecimalLike
    ask: DecimalLike


def validate_ohlcv_row(row: OhlcvRow) -> ValidationStatus:
    """OHLC must be positive; ``high >= max(open, close)``; ``low <= min(open, close)``.
    Negative volume is a blocking failure; zero volume is a contextual warning."""
    o, h, low, c = (
        _as_decimal(row.open),
        _as_decimal(row.high),
        _as_decimal(row.low),
        _as_decimal(row.close),
    )
    if any(v <= 0 for v in (o, h, low, c)):
        return ValidationStatus.BLOCKING_FAIL
    if h < max(o, c) or low > min(o, c):
        return ValidationStatus.BLOCKING_FAIL
    if row.volume is not None:
        vol = _as_decimal(row.volume)
        if vol < 0:
            return ValidationStatus.BLOCKING_FAIL
        if vol == 0:
            return ValidationStatus.WARNING
    return ValidationStatus.PASS


def validate_tick_row(row: TickRow) -> ValidationStatus:
    """Price must be positive. ``UNKNOWN`` side is preserved (not rejected) and
    surfaces as a downstream warning rather than a blocking failure."""
    if _as_decimal(row.price) <= 0:
        return ValidationStatus.BLOCKING_FAIL
    if row.side == TradeSide.UNKNOWN:
        return ValidationStatus.WARNING
    return ValidationStatus.PASS


def validate_spread_row(row: SpreadRow) -> ValidationStatus:
    """``ask < bid`` is a blocking failure; non-positive quotes also block."""
    bid, ask = _as_decimal(row.bid), _as_decimal(row.ask)
    if bid <= 0 or ask <= 0:
        return ValidationStatus.BLOCKING_FAIL
    if ask < bid:
        return ValidationStatus.BLOCKING_FAIL
    return ValidationStatus.PASS
