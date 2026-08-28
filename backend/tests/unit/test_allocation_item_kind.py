"""I-03 — the allocation item-kind allowlist (doc 13 §5.2, §14#7-8).

``AllocationItemRef.kind`` was set by the command layer but never read by
``validate_allocation``: the only reason a non-allocatable kind could not slip
through was structural (``MainboardItemKind`` happens to hold exactly the three
allocatable kinds, ``item_type`` is server-derived, unknown ids are already
DEPENDENCY_BLOCKED). These tests pin the now-EXPLICIT guard, and prove the
regression by standing in a synthetic fourth kind — the shape a future enum
widening would take.
"""

from __future__ import annotations

from enum import StrEnum
from typing import cast

import pytest

from entropia.domain.allocation.config import PortfolioAllocationConfigV1
from entropia.domain.allocation.enums import AllocationIssueCode as Code
from entropia.domain.allocation.enums import AllocationIssueSeverity as Sev
from entropia.domain.allocation.rules import (
    ALLOCATABLE_ITEM_KINDS,
    AllocationItemRef,
    has_blockers,
    validate_allocation,
)
from entropia.domain.mainboard.enums import MainboardItemKind


class _FutureItemKind(StrEnum):
    """Stand-in for a kind a later slice might add to ``MainboardItemKind``.

    Declared test-only on purpose: widening the production enum just to prove a
    guard would ship a kind nothing else can handle.
    """

    RESEARCH_NOTE = "research_note"


_NOT_ALLOCATABLE = cast(MainboardItemKind, _FutureItemKind.RESEARCH_NOTE)


def _config(*entries: dict) -> PortfolioAllocationConfigV1:
    return PortfolioAllocationConfigV1.model_validate(
        {
            "enabled": True,
            "initial_capital": {"amount": "10000", "currency": "USDT"},
            "compounding_mode": "COMPOUND_PORTFOLIO_EQUITY",
            "reserve_cash_percent": "10",
            "entries": list(entries),
        }
    )


def _entry(cid: str, share: str, *, active: bool = True) -> dict:
    return {"composition_item_id": cid, "active": active, "equity_share_percent": share}


def _ref(kind: MainboardItemKind, *, available: bool = True) -> AllocationItemRef:
    return AllocationItemRef(kind=kind, available=available)


def _codes(issues) -> set[str]:
    return {str(i.code) for i in issues}


def _kind_issues(issues) -> list:
    return [i for i in issues if str(i.code) == str(Code.ITEM_KIND_NOT_ALLOCATABLE)]


@pytest.mark.parametrize("kind", sorted(MainboardItemKind, key=str))
def test_every_shipped_kind_is_allocatable(kind: MainboardItemKind) -> None:
    """Strategy / Trading Signal / Trade Log all pass the gate (doc 13 §14#8)."""
    issues, derived = validate_allocation(_config(_entry("a", "100")), item_refs={"a": _ref(kind)})

    assert _kind_issues(issues) == []
    # ADIM 3's containment made an ENABLED plan always lead with SHARED_MODE_NOT_IN_BUILD;
    # ADIM 20 (`C9`) lifted it, so the expected set is now EMPTY. The assertion's meaning is
    # unchanged — this test is about the ITEM KIND gate and says no OTHER blocker fires.
    assert {str(i.code) for i in issues if str(i.severity) == "blocker"} == set()
    assert derived is not None


def test_non_allocatable_kind_blocks_the_plan() -> None:
    """A kind outside the allowlist is a BLOCKER, not a silently funded sleeve."""
    issues, _derived = validate_allocation(
        _config(_entry("a", "100")), item_refs={"a": _ref(_NOT_ALLOCATABLE)}
    )

    blockers = _kind_issues(issues)
    assert len(blockers) == 1
    assert str(blockers[0].severity) == str(Sev.BLOCKER)
    assert blockers[0].composition_item_id == "a"
    assert "research_note" in blockers[0].message
    assert has_blockers(issues)


def test_kind_gate_is_independent_of_availability() -> None:
    """An item present in the composition is still rejected on kind alone.

    Guards against the check being folded into the ITEM_UNAVAILABLE branch, which
    would make it dead whenever the item resolves cleanly.
    """
    present, _ = validate_allocation(
        _config(_entry("a", "100")),
        item_refs={"a": _ref(_NOT_ALLOCATABLE, available=True)},
    )
    assert str(Code.ITEM_UNAVAILABLE) not in _codes(present)
    assert str(Code.ITEM_KIND_NOT_ALLOCATABLE) in _codes(present)

    absent, _ = validate_allocation(
        _config(_entry("a", "100")),
        item_refs={"a": _ref(_NOT_ALLOCATABLE, available=False)},
    )
    assert {str(Code.ITEM_UNAVAILABLE), str(Code.ITEM_KIND_NOT_ALLOCATABLE)} <= _codes(absent)


def test_only_active_entries_are_kind_checked() -> None:
    """An inactive row funds nothing, so its kind is not judged (doc 13 §5.2)."""
    issues, _derived = validate_allocation(
        _config(_entry("a", "100"), _entry("b", "0", active=False)),
        item_refs={
            "a": _ref(MainboardItemKind.STRATEGY),
            "b": _ref(_NOT_ALLOCATABLE),
        },
    )

    assert _kind_issues(issues) == []


def test_mixed_composition_blocks_only_the_offending_row() -> None:
    issues, _derived = validate_allocation(
        _config(_entry("ok", "60"), _entry("bad", "40")),
        item_refs={
            "ok": _ref(MainboardItemKind.TRADING_SIGNAL),
            "bad": _ref(_NOT_ALLOCATABLE),
        },
    )

    assert [i.composition_item_id for i in _kind_issues(issues)] == ["bad"]


def test_allowlist_covers_the_whole_shipped_enum() -> None:
    """Ratchet: widening ``MainboardItemKind`` must be an explicit decision.

    If a later slice adds a kind, this fails and forces the author to either add
    it to ``ALLOCATABLE_ITEM_KINDS`` or record that it is deliberately excluded —
    instead of the allowlist silently drifting out of date.
    """
    assert set(MainboardItemKind) == ALLOCATABLE_ITEM_KINDS
