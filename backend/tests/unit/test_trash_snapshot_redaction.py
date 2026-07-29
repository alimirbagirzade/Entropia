"""I-09 — Trash snapshot redaction + size bound (doc 20 §12).

Doc 20 §12: *"Snapshot contains redacted/size-bounded data only"* / *"Never
render credentials, secrets, tokens or unnecessary raw artifacts in Trash
detail"*. These are the pure-function proofs; the endpoint-level proof lives in
``tests/integration/test_trash_snapshot_redaction.py``.

The load-bearing case is ``test_unknown_key_value_never_survives``: before I-09
the detail query returned the stored JSONB verbatim, so the whole contract
rested on writers happening to store safe keys. The allowlist inverts that — a
key nobody reviewed leaks its NAME at most, never its value.
"""

from __future__ import annotations

import json

import pytest

from entropia.domain.trash.redaction import (
    MAX_VALUE_CHARS,
    REDACTED,
    SNAPSHOT_ALLOWED_KEYS,
    TRUNCATED_KEY,
    redact_snapshot,
)


def test_allowlisted_scalars_pass_through_unchanged() -> None:
    snapshot = {
        "current_revision_id": "rev-1",
        "domain_lifecycle_state": "active",
        "stream_position": 7,
        "title": "Demo document",
    }
    assert redact_snapshot(snapshot) == snapshot


def test_unknown_key_value_never_survives() -> None:
    """The injected-credential case from the I-09 report."""
    rendered = redact_snapshot({"api_key": "sk-xxx", "current_revision_id": "rev-1"})

    assert "sk-xxx" not in json.dumps(rendered)
    assert rendered["api_key"] == REDACTED
    # The KEY stays as evidence that a field exists — only the value is withheld.
    assert rendered["current_revision_id"] == "rev-1"


@pytest.mark.parametrize(
    "value",
    [
        {"nested": "sk-xxx"},
        ["sk-xxx"],
        [{"token": "sk-xxx"}],
    ],
)
def test_nested_value_under_allowlisted_key_is_redacted_whole(value: object) -> None:
    """Reviewing a key is not reviewing an arbitrary tree hung under it."""
    rendered = redact_snapshot({"title": value})

    assert rendered["title"] == REDACTED
    assert "sk-xxx" not in json.dumps(rendered)


def test_oversized_string_is_cut_and_flagged() -> None:
    rendered = redact_snapshot({"title": "x" * 10_000})

    assert len(rendered["title"]) == MAX_VALUE_CHARS
    assert rendered[TRUNCATED_KEY] is True


def test_ten_megabyte_snapshot_is_bounded_and_flagged() -> None:
    """A 10 MB stored snapshot must not become a 10 MB API response."""
    snapshot = {f"blob_{i}": "y" * 100_000 for i in range(100)}
    snapshot["title"] = "z" * 100_000
    assert len(json.dumps(snapshot).encode()) > 10 * 1000 * 1000  # >10 MB stored

    rendered = redact_snapshot(snapshot)
    encoded = json.dumps(rendered).encode()

    assert len(encoded) <= 16_384
    assert rendered[TRUNCATED_KEY] is True
    assert b"y" * 1000 not in encoded


def test_size_bound_is_respected_for_allowlisted_values_too() -> None:
    """Redaction alone cannot save us: allowlisted keys are bounded as well."""
    snapshot = dict.fromkeys(SNAPSHOT_ALLOWED_KEYS, "q" * MAX_VALUE_CHARS)

    rendered = redact_snapshot(snapshot, max_bytes=256)

    assert len(json.dumps(rendered).encode()) <= 256
    assert rendered[TRUNCATED_KEY] is True


def test_untruncated_result_carries_no_marker() -> None:
    """A bound that fires when nothing was cut would read as data loss."""
    assert TRUNCATED_KEY not in redact_snapshot({"current_revision_id": "rev-1"})


def test_stored_truncation_marker_cannot_be_forged_away() -> None:
    """A writer must not be able to stamp (or clear) our honesty marker."""
    rendered = redact_snapshot({TRUNCATED_KEY: False, "current_revision_id": "rev-1"})

    assert rendered[TRUNCATED_KEY] is True


@pytest.mark.parametrize("snapshot", [None, [], "raw", 7])
def test_non_object_snapshot_yields_empty_dict(snapshot: object) -> None:
    """The column is nullable JSONB — ``None`` is a normal input, not an error."""
    assert redact_snapshot(snapshot) == {}


def test_non_positive_max_bytes_is_rejected() -> None:
    with pytest.raises(ValueError):
        redact_snapshot({"title": "t"}, max_bytes=0)
