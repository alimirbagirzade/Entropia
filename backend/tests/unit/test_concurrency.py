import pytest

from entropia.shared.concurrency import (
    check_head_revision,
    check_row_version,
    etag_for_row_version,
    row_version_from_if_match,
)
from entropia.shared.errors import StaleRevisionError


def test_row_version_match_passes() -> None:
    check_row_version(3, 3)  # no raise
    check_row_version(3, None)  # unconditional


def test_row_version_mismatch_raises() -> None:
    with pytest.raises(StaleRevisionError):
        check_row_version(3, 2)


def test_head_revision_mismatch_raises() -> None:
    with pytest.raises(StaleRevisionError):
        check_head_revision("rev_b", "rev_a")


def test_etag_roundtrip() -> None:
    etag = etag_for_row_version(5)
    assert row_version_from_if_match(etag) == 5
    assert row_version_from_if_match(None) is None
    assert row_version_from_if_match('"rv-9"') == 9
