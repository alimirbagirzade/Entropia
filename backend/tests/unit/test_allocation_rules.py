"""Stage 4a — Portfolio / Equity Allocation domain rules (doc 13 §8.3, §10.1, §14).

Infra-free: exercises the pure validator + capital formulas + config hash. The
capital numbers pin acceptance §14#10 (10,000 / 10% reserve / 40-35-15 shares).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from entropia.domain.allocation.config import PortfolioAllocationConfigV1
from entropia.domain.allocation.enums import AllocationIssueCode as Code
from entropia.domain.allocation.enums import AllocationIssueSeverity as Sev
from entropia.domain.allocation.rules import (
    AllocationItemRef,
    compute_config_hash,
    has_blockers,
    validate_allocation,
)
from entropia.domain.mainboard.enums import MainboardItemKind


def _entry(cid: str, share: str | None, *, active: bool = True) -> dict:
    return {"composition_item_id": cid, "active": active, "equity_share_percent": share}


def _config(**overrides) -> PortfolioAllocationConfigV1:
    base = {
        "enabled": True,
        "initial_capital": {"amount": "10000", "currency": "USDT"},
        "compounding_mode": "COMPOUND_PORTFOLIO_EQUITY",
        "reserve_cash_percent": "10",
        "entries": [],
    }
    base.update(overrides)
    return PortfolioAllocationConfigV1.model_validate(base)


def _refs(*cids: str, available: bool = True) -> dict[str, AllocationItemRef]:
    return {
        cid: AllocationItemRef(kind=MainboardItemKind.STRATEGY, available=available) for cid in cids
    }


def _codes(issues) -> set[str]:
    return {str(i.code) for i in issues}


def test_independent_mode_is_engine_clear() -> None:
    issues, derived = validate_allocation(_config(enabled=False), item_refs={})
    assert issues == []
    assert derived is None


def test_valid_shared_derives_canonical_amounts() -> None:
    config = _config(
        entries=[_entry("a", "40"), _entry("b", "35"), _entry("c", "15")],
    )
    issues, derived = validate_allocation(config, item_refs=_refs("a", "b", "c"))

    assert not has_blockers(issues)
    assert derived is not None
    assert Decimal(derived.portfolio_initial_capital) == Decimal("10000")
    assert Decimal(derived.reserved_cash) == Decimal("1000")
    assert Decimal(derived.capital_available) == Decimal("9000")
    assert Decimal(derived.total_allocated) == Decimal("8100")
    assert Decimal(derived.unallocated) == Decimal("900")
    sleeves = {s.composition_item_id: Decimal(s.initial_sleeve_capital) for s in derived.sleeves}
    assert sleeves == {"a": Decimal("3600"), "b": Decimal("3150"), "c": Decimal("1350")}
    # 90% < 100% => warning, no auto-borrow (§14#5).
    assert Code.TOTAL_ALLOCATION_UNDER_100 in _codes(issues)


def test_full_100_has_no_unallocated_warning() -> None:
    config = _config(entries=[_entry("a", "40"), _entry("b", "35"), _entry("c", "25")])
    issues, derived = validate_allocation(config, item_refs=_refs("a", "b", "c"))
    assert derived is not None
    assert Decimal(derived.unallocated) == Decimal("0")
    assert Code.TOTAL_ALLOCATION_UNDER_100 not in _codes(issues)
    assert Code.TOTAL_ALLOCATION_EXCEEDS_100 not in _codes(issues)


def test_initial_capital_must_be_positive() -> None:
    config = _config(
        initial_capital={"amount": "0", "currency": "USDT"}, entries=[_entry("a", "50")]
    )
    issues, _ = validate_allocation(config, item_refs=_refs("a"))
    assert Code.INITIAL_CAPITAL_INVALID in _codes(issues)
    assert has_blockers(issues)


def test_reserve_out_of_range_blocks() -> None:
    issues, _ = validate_allocation(
        _config(reserve_cash_percent="100", entries=[_entry("a", "50")]), item_refs=_refs("a")
    )
    assert Code.RESERVE_OUT_OF_RANGE in _codes(issues)


def test_missing_compounding_mode_blocks() -> None:
    issues, _ = validate_allocation(
        _config(compounding_mode=None, entries=[_entry("a", "50")]), item_refs=_refs("a")
    )
    assert Code.COMPOUNDING_MODE_INVALID in _codes(issues)


def test_no_active_entry_blocks() -> None:
    issues, _ = validate_allocation(_config(entries=[]), item_refs={})
    assert Code.NO_ACTIVE_ENTRY in _codes(issues)


def test_active_entry_needs_positive_share() -> None:
    issues, _ = validate_allocation(_config(entries=[_entry("a", "0")]), item_refs=_refs("a"))
    assert Code.ENTRY_SHARE_INVALID in _codes(issues)


def test_total_share_over_100_blocks() -> None:
    issues, _ = validate_allocation(
        _config(entries=[_entry("a", "70"), _entry("b", "45")]), item_refs=_refs("a", "b")
    )
    assert Code.TOTAL_ALLOCATION_EXCEEDS_100 in _codes(issues)
    assert has_blockers(issues)


def test_duplicate_active_item_blocks() -> None:
    issues, _ = validate_allocation(
        _config(entries=[_entry("a", "40"), _entry("a", "40")]), item_refs=_refs("a")
    )
    assert Code.DUPLICATE_ACTIVE_ENTRY in _codes(issues)


def test_unavailable_item_blocks() -> None:
    issues, _ = validate_allocation(
        _config(entries=[_entry("gone", "50")]), item_refs=_refs("gone", available=False)
    )
    assert Code.ITEM_UNAVAILABLE in _codes(issues)


def test_single_active_sleeve_warns_but_is_valid() -> None:
    issues, derived = validate_allocation(
        _config(entries=[_entry("a", "100")]), item_refs=_refs("a")
    )
    codes = _codes(issues)
    assert Code.ONE_ACTIVE_SLEEVE in codes
    assert not has_blockers(issues)
    warning_severities = {str(i.severity) for i in issues}
    assert str(Sev.WARNING) in warning_severities
    assert derived is not None


def test_config_hash_is_deterministic_and_sensitive() -> None:
    a = _config(entries=[_entry("a", "40"), _entry("b", "60")])
    b = _config(entries=[_entry("a", "40"), _entry("b", "60")])
    c = _config(entries=[_entry("a", "50"), _entry("b", "50")])
    assert compute_config_hash(a) == compute_config_hash(b)
    assert compute_config_hash(a) != compute_config_hash(c)
    assert len(compute_config_hash(a)) == 64


def test_money_must_not_be_float() -> None:
    with pytest.raises(ValidationError):
        PortfolioAllocationConfigV1.model_validate(
            {"enabled": True, "initial_capital": {"amount": 10000.5, "currency": "USDT"}}
        )
