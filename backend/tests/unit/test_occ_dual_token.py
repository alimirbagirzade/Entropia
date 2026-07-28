"""The single dual-token OCC rule (O-12) at the unit level.

Body ``expected_*`` and the ``If-Match`` header are two spellings of ONE value —
doc 15 §11, doc 20 §14, doc 21 §7. ``reconcile_occ_tokens`` is the one place that
rule lives, so every dual-token route inherits it and it cannot drift.
"""

from __future__ import annotations

import pytest

from entropia.shared.concurrency import reconcile_occ_tokens
from entropia.shared.errors import ErrorCategory, OccTokenConflictError


def test_body_only_wins() -> None:
    assert reconcile_occ_tokens(7, None, field="expected_row_version") == 7


def test_header_only_wins() -> None:
    assert reconcile_occ_tokens(None, 7, field="expected_row_version") == 7


def test_neither_supplied_is_none() -> None:
    """No token at all stays ``None`` — the caller decides if one is mandatory."""
    assert reconcile_occ_tokens(None, None, field="expected_row_version") is None


def test_agreeing_tokens_collapse_to_the_shared_value() -> None:
    assert reconcile_occ_tokens(7, 7, field="expected_row_version") == 7


def test_agreeing_string_tokens_collapse() -> None:
    assert reconcile_occ_tokens("rev_9", "rev_9", field="expected_head_revision_id") == "rev_9"


def test_disagreeing_tokens_are_a_conflict() -> None:
    with pytest.raises(OccTokenConflictError) as exc:
        reconcile_occ_tokens(7, 8, field="expected_row_version")
    assert exc.value.code == "OCC_TOKEN_CONFLICT"
    assert exc.value.http_status == 409


def test_disagreeing_string_tokens_are_a_conflict() -> None:
    with pytest.raises(OccTokenConflictError):
        reconcile_occ_tokens("rev_9", "rev_10", field="expected_head_revision_id")


def test_conflict_reports_both_values_and_the_field() -> None:
    """The envelope must name the field and BOTH values — the caller cannot fix a
    contradiction it cannot see."""
    with pytest.raises(OccTokenConflictError) as exc:
        reconcile_occ_tokens(3, 4, field="expected_draft_row_version")
    err = exc.value
    assert err.field_path == "expected_draft_row_version"
    assert err.details == [
        {
            "field": "expected_draft_row_version",
            "body_value": "3",
            "if_match_value": "4",
        }
    ]


def test_conflict_is_a_concurrency_failure_that_is_not_blindly_retryable() -> None:
    """A blind retry of the identical request always fails again: the caller must
    resend ONE token. Advertising retryable=True would loop the client forever."""
    err = OccTokenConflictError()
    assert err.category == ErrorCategory.CONCURRENCY_OR_PREFLIGHT
    assert err.retryable is False
    assert err.suggested_action == "resend_with_a_single_occ_token"
    assert err.remediation


def test_zero_is_a_real_token_not_an_absent_one() -> None:
    """``0`` is falsy but is still a supplied token — a ``not value`` check here
    would silently drop it and reopen the last-write-wins hole."""
    assert reconcile_occ_tokens(0, None, field="expected_row_version") == 0
    with pytest.raises(OccTokenConflictError):
        reconcile_occ_tokens(0, 1, field="expected_row_version")
