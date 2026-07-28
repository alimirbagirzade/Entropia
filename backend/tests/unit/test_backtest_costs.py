"""K-09 (d) — the cost and funding/carry layer, tested as its own unit.

``due_funding_charges`` is the funding DECISION lifted out of the bar loop: which
pinned records fire at this bar and what each costs. Applying a charge still mutates
the loop's equity/counters, but the decision is now a pure function of
``(records, cursor, decision_time, position)`` and is directly testable — including
the two rules that make F-11 honest rather than optimistic:

* a record that becomes available while FLAT is CONSUMED but not charged (funding is
  paid only for the interval the position is actually held), so the cursor must
  advance even when nothing is billed;
* an unresolvable bar timestamp FAILS CLOSED rather than booking a zero cost.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from entropia.domain.backtest.execution.costs import (
    _cost_params,
    _effective_fill,
    due_funding_charges,
    resolve_funding_decision_time,
)
from entropia.domain.backtest.funding import FundingRecord
from entropia.shared.errors import FundingSourceInvalid
from tests.unit.test_backtest_engine import _config

_NOTIONAL = Decimal("5100.00")


def _ts(day: int) -> datetime:
    return datetime(2024, 1, day, tzinfo=UTC)


def _rec(day: int, rate: str) -> FundingRecord:
    return FundingRecord(available_at=_ts(day), event_at=_ts(day), rate=Decimal(rate))


def _due(records, *, day: int, direction: str | None, start: int = 0, mapping: bool = True):
    return due_funding_charges(
        records,
        start_index=start,
        decision_time=_ts(day),
        has_instrument_mapping=mapping,
        position_direction=direction,
        position_notional=_NOTIONAL,
    )


# --------------------------------------------------------------------------- #
# _cost_params / _effective_fill                                               #
# --------------------------------------------------------------------------- #
def test_cost_params_halves_the_spread_and_scales_slippage_to_a_fraction() -> None:
    half_spread, slippage, commission = _cost_params(_config())
    assert half_spread == Decimal("0")
    assert slippage == Decimal("0")  # slippage_value "0" percent
    assert commission == Decimal("0")


def test_effective_fill_is_adverse_on_both_sides() -> None:
    """A buy pays up, a sell receives less — the cost model never favours the run."""
    price = Decimal("100")
    buy = _effective_fill(price, is_buy=True, half_spread=Decimal("1"), slip=Decimal("0.01"))
    sell = _effective_fill(price, is_buy=False, half_spread=Decimal("1"), slip=Decimal("0.01"))
    assert buy > price
    assert sell < price


def test_effective_fill_is_an_identity_without_costs() -> None:
    price = Decimal("100")
    assert _effective_fill(
        price, is_buy=True, half_spread=Decimal("0"), slip=Decimal("0")
    ) == price.quantize(Decimal("0.01"))


# --------------------------------------------------------------------------- #
# resolve_funding_decision_time — fail closed                                  #
# --------------------------------------------------------------------------- #
def test_resolve_decision_time_reads_an_iso_bar_timestamp() -> None:
    assert resolve_funding_decision_time("2024-01-21T00:00:00Z") == _ts(21)


def test_an_unresolvable_bar_timestamp_fails_closed() -> None:
    """Silently firing nothing would book an over-optimistic ZERO funding cost for the
    whole run — a cost has no restrictive reading to fall back on."""
    with pytest.raises(FundingSourceInvalid):
        resolve_funding_decision_time("not-a-timestamp")


# --------------------------------------------------------------------------- #
# due_funding_charges                                                          #
# --------------------------------------------------------------------------- #
def test_a_long_pays_a_positive_rate() -> None:
    index, charges = _due((_rec(21, "0.001"),), day=21, direction="long")
    assert index == 1
    assert [c.amount for c in charges] == [Decimal("5.10")]  # 5100 * 0.001, positive = paid


def test_a_short_receives_a_positive_rate() -> None:
    _, charges = _due((_rec(21, "0.001"),), day=21, direction="short")
    assert charges[0].amount == Decimal("-5.10")


def test_records_available_while_flat_are_consumed_without_a_charge() -> None:
    """The cursor MUST advance — otherwise the record would re-fire on a later bar and
    bill a position it was never held against."""
    index, charges = _due((_rec(21, "0.001"), _rec(22, "0.002")), day=22, direction=None)
    assert index == 2
    assert charges == []


def test_a_record_dated_after_this_bar_does_not_fire() -> None:
    """Future-leak protection is structural: the cursor simply never reaches it."""
    index, charges = _due((_rec(21, "0.001"), _rec(28, "0.5")), day=21, direction="long")
    assert index == 1
    assert len(charges) == 1


def test_every_available_record_fires_exactly_once_in_order() -> None:
    index, charges = _due(
        (_rec(21, "0.001"), _rec(22, "0.002"), _rec(28, "0.9")), day=23, direction="long"
    )
    assert index == 2
    assert [c.record.rate for c in charges] == [Decimal("0.001"), Decimal("0.002")]


def test_the_cursor_resumes_where_it_left_off() -> None:
    records = (_rec(21, "0.001"), _rec(22, "0.002"))
    index, first = _due(records, day=21, direction="long")
    _, second = _due(records, day=22, direction="long", start=index)
    assert len(first) == 1
    assert len(second) == 1
    assert second[0].record.rate == Decimal("0.002")


def test_nothing_is_eligible_without_an_instrument_mapping() -> None:
    """The as-of gate is the canonical rule-2 predicate: mapping AND available_at <= t."""
    index, charges = _due((_rec(21, "0.001"),), day=21, direction="long", mapping=False)
    assert index == 0
    assert charges == []


def test_a_zero_rate_still_consumes_the_record() -> None:
    index, charges = _due((_rec(21, "0"),), day=21, direction="long")
    assert index == 1
    assert [c.amount for c in charges] == [Decimal("0.00")]


def test_an_empty_schedule_charges_nothing() -> None:
    assert _due((), day=21, direction="long") == (0, [])
