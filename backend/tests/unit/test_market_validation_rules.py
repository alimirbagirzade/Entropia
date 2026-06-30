"""Market validation-rule unit tests (doc 11, AT #7-#9)."""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.lifecycle.enums import ValidationStatus
from entropia.domain.market_data.enums import TradeSide
from entropia.domain.market_data.validation_rules import (
    OhlcvRow,
    SpreadRow,
    TickRow,
    validate_ohlcv_row,
    validate_spread_row,
    validate_tick_row,
)


def test_ohlcv_valid_row_passes() -> None:
    row = OhlcvRow(open="10", high="12", low="9", close="11", volume="100")
    assert validate_ohlcv_row(row) == ValidationStatus.PASS


def test_ohlcv_high_below_close_blocks() -> None:
    row = OhlcvRow(open="10", high="10", low="9", close="11")
    assert validate_ohlcv_row(row) == ValidationStatus.BLOCKING_FAIL


def test_ohlcv_negative_volume_blocks() -> None:
    row = OhlcvRow(open="10", high="12", low="9", close="11", volume="-1")
    assert validate_ohlcv_row(row) == ValidationStatus.BLOCKING_FAIL


def test_ohlcv_zero_volume_warns() -> None:
    row = OhlcvRow(open="10", high="12", low="9", close="11", volume="0")
    assert validate_ohlcv_row(row) == ValidationStatus.WARNING


def test_ohlcv_non_positive_price_blocks() -> None:
    row = OhlcvRow(open="0", high="12", low="9", close="11")
    assert validate_ohlcv_row(row) == ValidationStatus.BLOCKING_FAIL


def test_tick_unknown_side_preserved_as_warning() -> None:
    # UNKNOWN side is preserved, never guessed; surfaces as a warning not a block.
    assert validate_tick_row(TickRow(price="5", side=TradeSide.UNKNOWN)) == (
        ValidationStatus.WARNING
    )


def test_tick_known_side_passes() -> None:
    assert validate_tick_row(TickRow(price=Decimal("5"), side=TradeSide.BUY)) == (
        ValidationStatus.PASS
    )


def test_tick_non_positive_price_blocks() -> None:
    assert validate_tick_row(TickRow(price="-1")) == ValidationStatus.BLOCKING_FAIL


def test_spread_ask_below_bid_blocks() -> None:
    assert validate_spread_row(SpreadRow(bid="10", ask="9")) == (ValidationStatus.BLOCKING_FAIL)


def test_spread_valid_passes() -> None:
    assert validate_spread_row(SpreadRow(bid="9", ask="10")) == ValidationStatus.PASS


def test_spread_non_positive_blocks() -> None:
    assert validate_spread_row(SpreadRow(bid="0", ask="10")) == (ValidationStatus.BLOCKING_FAIL)
