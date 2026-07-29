"""Unit tests for the Create-Package request display label (audit F-07 §4.4).

The Pre-Check request picker used to identify a row by its raw ``request_id``.
These lock the pure composition rule behind the projection's ``display_label``:
a human noun first, the creation instant as the discriminator, and the revision
attempt only when the request is past its original attempt.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from entropia.domain.create_package.labels import package_kind_label, request_display_label
from entropia.domain.lifecycle.enums import PackageKind

_CREATED = datetime(2026, 7, 29, 14, 3, 22, tzinfo=UTC)


def test_precheck_projection_label_names_the_kind_and_creation_instant() -> None:
    label = request_display_label(package_kind=PackageKind.INDICATOR, created_at=_CREATED)
    assert label == "Indicator Package · 2026-07-29 14:03:22 UTC"


def test_precheck_projection_label_never_contains_the_request_id() -> None:
    """The label is composed from request FACTS — it never echoes the opaque id."""
    label = request_display_label(
        package_kind=PackageKind.CONDITION, created_at=_CREATED, revision_attempt_no=1
    )
    assert "cpr_" not in label
    assert label == "Condition Package · 2026-07-29 14:03:22 UTC"


def test_precheck_projection_label_names_the_revision_attempt_past_the_original() -> None:
    original = request_display_label(
        package_kind=PackageKind.INDICATOR, created_at=_CREATED, revision_attempt_no=1
    )
    revised = request_display_label(
        package_kind=PackageKind.INDICATOR, created_at=_CREATED, revision_attempt_no=3
    )
    # Attempt 1 IS the original — naming it would be noise on every fresh request.
    assert "revision" not in original
    assert revised == "Indicator Package · 2026-07-29 14:03:22 UTC · revision 3"


def test_precheck_projection_label_discriminates_two_requests_of_one_kind() -> None:
    """Second precision: same kind, seconds apart, still two distinct labels."""
    first = request_display_label(package_kind=PackageKind.INDICATOR, created_at=_CREATED)
    second = request_display_label(
        package_kind=PackageKind.INDICATOR, created_at=_CREATED + timedelta(seconds=5)
    )
    assert first != second


def test_precheck_projection_label_renders_utc_regardless_of_source_offset() -> None:
    """A +03:00 instant is shown in UTC, not re-labelled with the local wall clock."""
    istanbul = _CREATED.astimezone(timezone(timedelta(hours=3)))
    assert request_display_label(
        package_kind=PackageKind.INDICATOR, created_at=istanbul
    ) == request_display_label(package_kind=PackageKind.INDICATOR, created_at=_CREATED)


def test_precheck_projection_label_reads_a_naive_timestamp_as_utc() -> None:
    naive = _CREATED.replace(tzinfo=None)
    assert (
        request_display_label(package_kind=PackageKind.INDICATOR, created_at=naive)
        == "Indicator Package · 2026-07-29 14:03:22 UTC"
    )


def test_precheck_projection_label_falls_back_to_the_kind_without_a_timestamp() -> None:
    """An honest degradation — never a fabricated date, never the raw id."""
    assert (
        request_display_label(package_kind=PackageKind.EMBEDDED_SYSTEM, created_at=None)
        == "Embedded System Package"
    )


def test_precheck_projection_label_title_cases_an_unmapped_kind() -> None:
    """A kind added to the enum later surfaces humanized, never as raw snake_case."""
    assert package_kind_label("some_new_kind") == "Some New Kind"
