"""ADR 0002 §13.1 OD-1(a) / OD-6(a) — the shared-mode admission predicates.

These are the plan-level refusals `C6` owes: a composition the unified loop cannot
model, refused before a run exists. The wiring proof (a real admission actually
refusing and leaving nothing behind) is
``tests/integration/test_shared_mode_admission.py``; this file pins the DECISIONS.

Every refusal case below is paired with a negative control in the same block — a
config that differs only in the offending fact and must come back clean. Without
that pairing a predicate that simply returned everything would pass the refusal
half of this file.
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.domain.allocation.rules import ALLOCATABLE_ITEM_KINDS
from entropia.domain.allocation.shared_mode_admission import (
    EXECUTING_ITEM_KINDS,
    declared_record_time_bases,
    mixed_record_time_bases,
    non_executing_sleeve_holders,
)
from entropia.domain.mainboard.enums import MainboardItemKind


def _snapshot(*entries: dict[str, Any]) -> dict[str, Any]:
    """An immutable capital snapshot in the shape ``_resolve_allocation`` writes."""
    return {
        "enabled": True,
        "plan_id": "allocplan_1",
        "plan_revision_id": "allocrev_1",
        "config_hash": "deadbeef",
        "config": {"enabled": True, "entries": list(entries)},
    }


def _entry(
    item_id: str,
    item_type: str | None,
    *,
    active: bool = True,
    share: str | None = "50",
) -> dict[str, Any]:
    return {
        "composition_item_id": item_id,
        "item_type": item_type,
        "active": active,
        "equity_share_percent": share,
    }


def _data_time(*bases: str | None) -> list[dict[str, Any]]:
    """One ``data_time`` row per basis; ``None`` means the revision declares none."""
    return [
        {
            "item_id": f"mbitem_{index}",
            "market_dataset": None if basis is None else {"record_time_basis": basis},
        }
        for index, basis in enumerate(bases)
    ]


# --------------------------------------------------------------------------- #
# The executing set — stated positively so a widened enum fails CLOSED         #
# --------------------------------------------------------------------------- #


def test_only_strategy_executes_and_the_complement_is_the_allocatable_rest() -> None:
    """Strategy is the only kind the worker simulates (``output=None`` for the rest)."""
    assert EXECUTING_ITEM_KINDS == frozenset({MainboardItemKind.STRATEGY})
    assert ALLOCATABLE_ITEM_KINDS - EXECUTING_ITEM_KINDS == {
        MainboardItemKind.TRADING_SIGNAL,
        MainboardItemKind.TRADE_LOG,
    }


def test_an_unknown_future_kind_is_treated_as_non_executing() -> None:
    """The fail-closed direction, and the reason the set is written positively.

    A kind this build has never heard of cannot be known to execute, so it must be
    refused a sleeve rather than silently earning one. Had the module listed the
    NON-executing kinds instead, this row would sail through.
    """
    holders = non_executing_sleeve_holders(_snapshot(_entry("mbitem_x", "quantum_oracle")))
    assert holders == ("mbitem_x",)


# --------------------------------------------------------------------------- #
# OD-6(a) — a non-executing kind holding a sleeve                              #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("kind", ["trading_signal", "trade_log"])
def test_a_non_executing_kind_holding_a_positive_share_is_an_offender(kind: str) -> None:
    snapshot = _snapshot(
        _entry("mbitem_strategy", "strategy", share="60"),
        _entry("mbitem_external", kind, share="40"),
    )
    assert non_executing_sleeve_holders(snapshot) == ("mbitem_external",)


def test_a_strategy_only_plan_is_clean() -> None:
    """NEGATIVE CONTROL: the legal shape must produce no finding."""
    snapshot = _snapshot(
        _entry("mbitem_a", "strategy", share="60"),
        _entry("mbitem_b", "strategy", share="40"),
    )
    assert non_executing_sleeve_holders(snapshot) == ()


def test_an_inactive_external_entry_is_not_an_offender() -> None:
    """ADR names ACTIVE entries; a deactivated row claims nothing from the pool."""
    snapshot = _snapshot(
        _entry("mbitem_strategy", "strategy", share="100"),
        _entry("mbitem_external", "trade_log", active=False, share="40"),
    )
    assert non_executing_sleeve_holders(snapshot) == ()


@pytest.mark.parametrize("share", [None, "0", "0.00"])
def test_an_external_entry_claiming_no_capital_is_not_an_offender(share: str | None) -> None:
    """OD-6's harm is a positive share that silently does nothing.

    A null or zero share withholds nothing from the items that can trade, and is
    already ``validate_allocation``'s finding rather than this one.
    """
    snapshot = _snapshot(_entry("mbitem_external", "trade_log", share=share))
    assert non_executing_sleeve_holders(snapshot) == ()


def test_an_unparseable_share_fails_closed() -> None:
    """A malformed row is refused, not waved through on a parse error."""
    snapshot = _snapshot(_entry("mbitem_external", "trade_log", share="not-a-number"))
    assert non_executing_sleeve_holders(snapshot) == ("mbitem_external",)


def test_an_entry_with_no_recorded_kind_yields_nothing() -> None:
    """An unrecorded kind is not evidence of a non-executing one (already UNAVAILABLE)."""
    assert non_executing_sleeve_holders(_snapshot(_entry("mbitem_x", None))) == ()


def test_every_offender_is_reported_in_snapshot_order() -> None:
    """The envelope promotes ONE leader, so ``details`` must carry the rest (O-02)."""
    snapshot = _snapshot(
        _entry("mbitem_signal", "trading_signal", share="30"),
        _entry("mbitem_strategy", "strategy", share="40"),
        _entry("mbitem_log", "trade_log", share="30"),
    )
    assert non_executing_sleeve_holders(snapshot) == ("mbitem_signal", "mbitem_log")


@pytest.mark.parametrize(
    "capital",
    [None, {}, {"enabled": True}, {"config": None}, {"config": {"entries": "nope"}}, "string"],
)
def test_an_unreadable_capital_snapshot_yields_no_offenders(capital: Any) -> None:
    """A snapshot that cannot be read is not evidence of a violation.

    The caller has already established that shared capital was REQUESTED; inventing
    an offender out of a shape mismatch would refuse runs for the wrong reason.
    """
    assert non_executing_sleeve_holders(capital) == ()


# --------------------------------------------------------------------------- #
# OD-1(a) — pinned revisions declaring different record time bases             #
# --------------------------------------------------------------------------- #


def test_two_different_bases_are_reported_sorted() -> None:
    assert mixed_record_time_bases(_data_time("bar_open", "bar_close")) == (
        "bar_close",
        "bar_open",
    )


def test_three_different_bases_are_all_reported() -> None:
    bases = mixed_record_time_bases(_data_time("event_time", "bar_open", "bar_close"))
    assert bases == ("bar_close", "bar_open", "event_time")


def test_one_basis_pinned_twice_is_clean() -> None:
    """NEGATIVE CONTROL: agreeing revisions are the legal shape."""
    assert mixed_record_time_bases(_data_time("bar_close", "bar_close")) == ()


def test_a_single_item_is_clean() -> None:
    assert mixed_record_time_bases(_data_time("bar_close")) == ()


def test_no_strategy_items_is_clean() -> None:
    assert mixed_record_time_bases([]) == ()


def test_an_absent_declaration_is_not_a_second_convention() -> None:
    """A revision that declares nothing must not COUNT as a rival basis.

    Bucketing ``None`` would block a composition for a provenance GAP instead of for
    a conflict — a different defect, with a different remedy.
    """
    assert declared_record_time_bases(_data_time("bar_close", None)) == ("bar_close",)
    assert mixed_record_time_bases(_data_time("bar_close", None)) == ()
    assert mixed_record_time_bases(_data_time(None, None)) == ()


def test_a_malformed_data_time_row_is_ignored() -> None:
    rows: list[Any] = ["not-a-dict", {"market_dataset": "not-a-dict"}, {}]
    assert declared_record_time_bases(rows) == ()
