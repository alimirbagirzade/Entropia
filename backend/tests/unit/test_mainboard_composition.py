"""Unit tests for the Mainboard composition fingerprint + CR-01 guard (doc 01 §5.2,
§9.3-9.4) and the work-object anti-lookahead rule (no DB).

Covers the Non-Canonical Gap Resolution byte-semantics of ``composition_hash``:
determinism, order-independence, enabled-only membership, and which mutations move
the fingerprint (add / soft-delete / enable-toggle / pin-change) versus which leave
it untouched (reorder / label-only). Also pins the kind-guard matrix and the
``available_time`` lookahead validation used by ``create_work_object``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from entropia.application.commands.mainboard import _validate_available_time
from entropia.domain.mainboard.composition import (
    CompositionMember,
    assert_item_kind_matches,
    composition_hash,
)
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.shared.errors import MainboardItemKindMismatchError, ValidationError


def _member(
    root: str, revision: str, kind: MainboardItemKind = MainboardItemKind.STRATEGY
) -> CompositionMember:
    return CompositionMember(kind=kind, root_id=root, revision_id=revision)


# --------------------------------------------------------------------------- #
# composition_hash                                                            #
# --------------------------------------------------------------------------- #


def test_hash_is_deterministic_for_same_input() -> None:
    members = [_member("wo_a", "worev_1"), _member("wo_b", "worev_2")]
    assert composition_hash(members) == composition_hash(list(members))


def test_hash_is_order_independent() -> None:
    a = _member("wo_a", "worev_1")
    b = _member("wo_b", "worev_2")
    c = _member("wo_c", "worev_3")
    assert composition_hash([a, b, c]) == composition_hash([c, a, b])
    assert composition_hash([a, b, c]) == composition_hash([b, c, a])


def test_empty_set_is_deterministic_and_nonempty() -> None:
    first = composition_hash([])
    second = composition_hash([])
    assert first == second
    assert isinstance(first, str)
    assert first  # non-null, persistable


def test_empty_differs_from_populated() -> None:
    assert composition_hash([]) != composition_hash([_member("wo_a", "worev_1")])


def test_adding_a_member_changes_the_hash() -> None:
    one = [_member("wo_a", "worev_1")]
    two = [_member("wo_a", "worev_1"), _member("wo_b", "worev_2")]
    assert composition_hash(one) != composition_hash(two)


def test_removing_a_member_changes_the_hash() -> None:
    # soft-delete / detach => the member drops from the enabled set => hash moves.
    full = [_member("wo_a", "worev_1"), _member("wo_b", "worev_2")]
    reduced = [_member("wo_a", "worev_1")]
    assert composition_hash(full) != composition_hash(reduced)


def test_disabling_a_member_changes_the_hash() -> None:
    # enable-toggle is modeled as inclusion/exclusion from the enabled iterable.
    enabled_both = [_member("wo_a", "worev_1"), _member("wo_b", "worev_2")]
    enabled_one = [_member("wo_a", "worev_1")]
    assert composition_hash(enabled_both) != composition_hash(enabled_one)


def test_pin_change_changes_the_hash() -> None:
    before = [_member("wo_a", "worev_1")]
    after = [_member("wo_a", "worev_2")]  # same root, new pinned revision
    assert composition_hash(before) != composition_hash(after)


def test_reorder_does_not_change_the_hash() -> None:
    # position_index is not part of the fingerprint; reorder is presentation-only.
    a = _member("wo_a", "worev_1")
    b = _member("wo_b", "worev_2")
    assert composition_hash([a, b]) == composition_hash([b, a])


def test_label_only_does_not_change_the_hash() -> None:
    # display_label_override is not represented in CompositionMember at all, so a
    # label-only edit cannot move the fingerprint.
    same = [_member("wo_a", "worev_1")]
    assert composition_hash(same) == composition_hash([_member("wo_a", "worev_1")])


def test_kind_does_not_collapse_distinct_revisions() -> None:
    strat = _member("wo_a", "worev_1", MainboardItemKind.STRATEGY)
    signal = _member("wo_a", "worev_1", MainboardItemKind.TRADING_SIGNAL)
    # Same root+revision but different kind => different fingerprint (kind is in tuple).
    assert composition_hash([strat]) != composition_hash([signal])


# --------------------------------------------------------------------------- #
# assert_item_kind_matches (CR-01)                                           #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "kind",
    [
        MainboardItemKind.STRATEGY,
        MainboardItemKind.TRADING_SIGNAL,
        MainboardItemKind.TRADE_LOG,
    ],
)
def test_matching_kinds_pass(kind: MainboardItemKind) -> None:
    assert_item_kind_matches(kind, kind)  # no raise


def test_matching_kinds_pass_with_string_values() -> None:
    assert_item_kind_matches("strategy", MainboardItemKind.STRATEGY)
    assert_item_kind_matches(MainboardItemKind.TRADE_LOG, "trade_log")


@pytest.mark.parametrize(
    ("item_kind", "object_kind"),
    [
        (MainboardItemKind.STRATEGY, MainboardItemKind.TRADING_SIGNAL),
        (MainboardItemKind.TRADING_SIGNAL, MainboardItemKind.TRADE_LOG),
        (MainboardItemKind.TRADE_LOG, MainboardItemKind.STRATEGY),
    ],
)
def test_mismatched_kinds_raise(
    item_kind: MainboardItemKind, object_kind: MainboardItemKind
) -> None:
    with pytest.raises(MainboardItemKindMismatchError) as exc:
        assert_item_kind_matches(item_kind, object_kind)
    assert exc.value.code == "MAINBOARD_ITEM_KIND_MISMATCH"
    assert exc.value.http_status == 422


# --------------------------------------------------------------------------- #
# available_time anti-lookahead (create_work_object validation)              #
# --------------------------------------------------------------------------- #


def test_strategy_allows_null_available_time() -> None:
    _validate_available_time(MainboardItemKind.STRATEGY, None)  # no raise


def test_external_kind_requires_available_time() -> None:
    with pytest.raises(ValidationError):
        _validate_available_time(MainboardItemKind.TRADING_SIGNAL, None)


def test_external_kind_rejects_naive_available_time() -> None:
    naive = datetime(2026, 1, 1, 12, 0, 0)  # intentionally naive (no tzinfo)
    with pytest.raises(ValidationError):
        _validate_available_time(MainboardItemKind.TRADE_LOG, naive)


def test_external_kind_rejects_future_available_time() -> None:
    future = datetime.now(UTC) + timedelta(days=1)
    with pytest.raises(ValidationError):
        _validate_available_time(MainboardItemKind.TRADING_SIGNAL, future)


def test_external_kind_accepts_past_utc_available_time() -> None:
    past = datetime.now(UTC) - timedelta(days=1)
    _validate_available_time(MainboardItemKind.TRADE_LOG, past)  # no raise
