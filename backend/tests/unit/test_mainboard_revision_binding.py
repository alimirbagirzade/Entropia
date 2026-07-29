"""AOS-12 (doc 03 §14 "Type/payload mismatch"): a revision id whose work object is
of another kind is rejected by its spec name, ``KIND_REVISION_MISMATCH``.

Before this slice the string ``KIND_REVISION_MISMATCH`` did not exist anywhere in
``src/`` — doc 03 §11 named it in the "Revision/attachment" validation class and
nothing implemented it, so a Trading Signal attach carrying a Trade Log revision id
came back as a bare ``VALIDATION_ERROR`` ("The pinned revision does not belong to
this work object"), which describes the wrong defect.

This module pins the pure domain gate. The two-surface wiring and the "no partial
item creation" half of AOS-12 are proven against a real database in
``integration/test_mainboard_kind_revision_mismatch.py``.

The three-code family is asserted to stay distinct here: AOS-12 must not be
answered with AOS-03's ``INVALID_ITEM_KIND`` nor with CR-01's
``MAINBOARD_ITEM_KIND_MISMATCH`` — each names a different failure.
"""

from __future__ import annotations

import pytest

from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.mainboard.revision_binding import assert_revision_kind_matches
from entropia.shared.errors import (
    ErrorCategory,
    InvalidItemKindError,
    KindRevisionMismatchError,
    MainboardItemKindMismatchError,
)

_SIGNAL = MainboardItemKind.TRADING_SIGNAL
_TRADE_LOG = MainboardItemKind.TRADE_LOG
_STRATEGY = MainboardItemKind.STRATEGY


@pytest.mark.parametrize("kind", [_SIGNAL, _TRADE_LOG, _STRATEGY])
def test_matching_kinds_pass_through(kind: MainboardItemKind) -> None:
    assert (
        assert_revision_kind_matches(revision_id="wrev_1", revision_kind=kind, expected_kind=kind)
        is None
    )


def test_aos_12_signal_bound_to_a_trade_log_revision_is_named_by_its_own_code() -> None:
    """The spec's literal example: a Trading Signal attach carrying a Trade Log revision id."""
    with pytest.raises(KindRevisionMismatchError) as exc:
        assert_revision_kind_matches(
            revision_id="wrev_tradelog_7",
            revision_kind=_TRADE_LOG,
            expected_kind=_SIGNAL,
        )

    assert exc.value.code == "KIND_REVISION_MISMATCH"
    assert exc.value.http_status == 422


def test_aos_12_envelope_carries_the_recovery_contract() -> None:
    """O-02: the envelope must classify the failure, not just name it."""
    with pytest.raises(KindRevisionMismatchError) as exc:
        assert_revision_kind_matches(
            revision_id="wrev_tradelog_7",
            revision_kind=_TRADE_LOG,
            expected_kind=_SIGNAL,
        )

    err = exc.value
    assert err.category is ErrorCategory.VALIDATION
    # An immutable revision is never re-kinded, so resending the same pair fails
    # identically forever — advertising a retry would be a lie.
    assert err.retryable is False
    assert err.suggested_action == "choose_matching_revision"
    assert err.remediation
    assert err.scope_type == "work_object_revision"
    assert err.scope_id == "wrev_tradelog_7"
    assert err.field_path == "revision_id"


def test_aos_12_details_echo_both_kinds_without_coercing_either() -> None:
    with pytest.raises(KindRevisionMismatchError) as exc:
        assert_revision_kind_matches(
            revision_id="wrev_9", revision_kind=_TRADE_LOG, expected_kind=_SIGNAL
        )

    assert exc.value.details == [
        {
            "field": "revision_id",
            "actual": "wrev_9",
            "actual_kind": "trade_log",
            "expected_kind": "trading_signal",
        }
    ]


def test_aos_12_is_symmetric_across_the_two_external_kinds() -> None:
    """The reverse direction (Trade Log attach, Signal revision) is the same defect."""
    with pytest.raises(KindRevisionMismatchError):
        assert_revision_kind_matches(
            revision_id="wrev_2", revision_kind=_SIGNAL, expected_kind=_TRADE_LOG
        )


def test_aos_12_field_path_follows_the_request_field() -> None:
    with pytest.raises(KindRevisionMismatchError) as exc:
        assert_revision_kind_matches(
            revision_id="wrev_3",
            revision_kind=_STRATEGY,
            expected_kind=_SIGNAL,
            field="pinned_revision_id",
        )

    assert exc.value.field_path == "pinned_revision_id"
    assert exc.value.details[0]["field"] == "pinned_revision_id"


def test_aos_12_does_not_reuse_either_neighbouring_kind_code() -> None:
    """AOS-03 and CR-01 answer different questions; neither may stand in for AOS-12."""
    with pytest.raises(KindRevisionMismatchError) as exc:
        assert_revision_kind_matches(
            revision_id="wrev_4", revision_kind=_TRADE_LOG, expected_kind=_SIGNAL
        )

    assert not isinstance(exc.value, InvalidItemKindError | MainboardItemKindMismatchError)
    assert exc.value.code not in {"INVALID_ITEM_KIND", "MAINBOARD_ITEM_KIND_MISMATCH"}
