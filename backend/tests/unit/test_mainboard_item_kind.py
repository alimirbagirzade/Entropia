"""AOS-03 (doc 03): a legacy V18 item-kind label is rejected by its spec name.

The chooser has exactly two external kinds. A client that still sends the V18
prototype labels ``signal_package`` / ``trade_log_package`` must get
``INVALID_ITEM_KIND`` — not a generic pydantic ``VALIDATION_ERROR`` and not the
CR-01 ``MAINBOARD_ITEM_KIND_MISMATCH`` (which answers a different question: "your
kind disagrees with the root's"). Before O-27 the string ``INVALID_ITEM_KIND`` did
not exist anywhere in ``src/``.

The opposite-direction guard (``domain/package/kind.py::LEGACY_PACKAGE_TYPES``,
which keeps ``trading_signal``/``trade_log`` OUT of ``PackageKind`` for TS-01 /
TL-01) is asserted here to still stand: the two guards face different ways and both
are required.
"""

from __future__ import annotations

import pytest

from entropia.domain.lifecycle.enums import PackageKind
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.mainboard.item_kind import (
    LEGACY_ITEM_KIND_ALIASES,
    ensure_mainboard_item_kind,
)
from entropia.domain.package.kind import LEGACY_PACKAGE_TYPES, ensure_package_kind
from entropia.shared.errors import (
    ClientLegacyTypeRejected,
    InvalidItemKindError,
    MainboardItemKindMismatchError,
)


def test_canonical_item_kinds_pass_through() -> None:
    assert ensure_mainboard_item_kind("strategy") == MainboardItemKind.STRATEGY
    assert ensure_mainboard_item_kind("trading_signal") == MainboardItemKind.TRADING_SIGNAL
    assert ensure_mainboard_item_kind("trade_log") == MainboardItemKind.TRADE_LOG


def test_enum_value_is_returned_directly() -> None:
    assert ensure_mainboard_item_kind(MainboardItemKind.TRADE_LOG) == MainboardItemKind.TRADE_LOG


@pytest.mark.parametrize(
    ("legacy", "meant"),
    [
        ("signal_package", "trading_signal"),
        ("trade_log_package", "trade_log"),
        ("  SIGNAL_PACKAGE  ", "trading_signal"),
    ],
)
def test_aos_03_legacy_labels_raise_invalid_item_kind(legacy: str, meant: str) -> None:
    with pytest.raises(InvalidItemKindError) as exc:
        ensure_mainboard_item_kind(legacy)

    assert exc.value.code == "INVALID_ITEM_KIND"
    assert exc.value.http_status == 422
    # The envelope names the offending field and echoes what the client sent; the
    # canonical kind is reported as `expected` but is NEVER substituted for it.
    assert exc.value.field_path == "object_kind"
    assert exc.value.details == [{"field": "object_kind", "actual": legacy, "expected": meant}]


def test_aos_03_field_path_follows_the_request_field() -> None:
    with pytest.raises(InvalidItemKindError) as exc:
        ensure_mainboard_item_kind("signal_package", field="item_kind")

    assert exc.value.field_path == "item_kind"
    assert exc.value.details[0]["field"] == "item_kind"


def test_legacy_label_is_never_coerced_to_the_kind_it_meant() -> None:
    """AOS-03's second half: no expansion/root/revision/item may follow."""
    for alias in LEGACY_ITEM_KIND_ALIASES:
        with pytest.raises(InvalidItemKindError):
            ensure_mainboard_item_kind(alias)


def test_unknown_kind_keeps_the_cr01_mismatch_code() -> None:
    """Only the two named legacy labels change code; everything else is untouched."""
    with pytest.raises(MainboardItemKindMismatchError) as exc:
        ensure_mainboard_item_kind("nonsense")
    assert exc.value.code == "MAINBOARD_ITEM_KIND_MISMATCH"


def test_package_guard_still_faces_the_other_way() -> None:
    """The pre-existing TS-01 / TL-01 guard is NOT replaced by the AOS-03 one."""
    assert frozenset({"trading_signal", "trade_log"}) == LEGACY_PACKAGE_TYPES
    for legacy in LEGACY_PACKAGE_TYPES:
        with pytest.raises(ClientLegacyTypeRejected):
            ensure_package_kind(legacy)
    # ...and the two vocabularies do not overlap: neither guard shadows the other.
    assert not (LEGACY_PACKAGE_TYPES & set(LEGACY_ITEM_KIND_ALIASES))
    assert ensure_package_kind("strategy") == PackageKind.STRATEGY
