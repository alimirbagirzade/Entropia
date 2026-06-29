"""Optimistic concurrency helpers (DOMAIN_MODEL §10).

Every mutation carries an expected token (`expected_row_version` or
`expected_head_revision_id`), mirrored by HTTP `If-Match`/`ETag`. A mismatch is a
409 STALE_REVISION — never last-write-wins.
"""

from __future__ import annotations

from entropia.shared.errors import StaleRevisionError


def check_row_version(actual: int, expected: int | None) -> None:
    if expected is not None and actual != expected:
        raise StaleRevisionError(f"Expected row_version {expected} but current is {actual}.")


def check_head_revision(actual: str | None, expected: str | None) -> None:
    if expected is not None and actual != expected:
        raise StaleRevisionError("The resource head revision changed. Refresh and retry.")


def etag_for_row_version(row_version: int) -> str:
    """Strong ETag derived from a root's row_version."""
    return f'"rv-{row_version}"'


def row_version_from_if_match(if_match: str | None) -> int | None:
    """Parse an If-Match header produced by etag_for_row_version()."""
    if not if_match:
        return None
    value = if_match.strip().strip('"')
    if value.startswith("rv-"):
        value = value[3:]
    try:
        return int(value)
    except ValueError:
        return None
