"""Package-kind guard (doc 09 §14, CR-01).

Acceptance: TS-01 (doc 04 — a client sending ``package_kind=trading_signal`` is
rejected; the kind stays valid only as an external work object / Mainboard item)
and TL-01 (doc 05 — the same boundary for ``trade_log``).

AOS-03 (doc 03 — a client sending a legacy ``item_kind`` creates no PackageKind
expansion, root, revision or item) is satisfied by this same guard. The spec names
the code ``INVALID_ITEM_KIND``; the SHIPPED code is ``CLIENT_LEGACY_TYPE_REJECTED``
(same defect, shipped name wins — see the O-03 adjudication convention).
"""

from __future__ import annotations

import pytest

from entropia.domain.lifecycle.enums import PackageKind
from entropia.domain.package.kind import ensure_package_kind
from entropia.shared.errors import ClientLegacyTypeRejected


def test_canonical_kinds_pass_through() -> None:
    assert ensure_package_kind("embedded_system") == PackageKind.EMBEDDED_SYSTEM
    assert ensure_package_kind("strategy") == PackageKind.STRATEGY
    assert ensure_package_kind("indicator") == PackageKind.INDICATOR
    assert ensure_package_kind("condition") == PackageKind.CONDITION


def test_enum_value_is_returned_directly() -> None:
    assert ensure_package_kind(PackageKind.EMBEDDED_SYSTEM) == PackageKind.EMBEDDED_SYSTEM


@pytest.mark.parametrize("legacy", ["trading_signal", "trade_log", "TRADING_SIGNAL"])
def test_legacy_types_are_rejected(legacy: str) -> None:
    with pytest.raises(ClientLegacyTypeRejected) as exc:
        ensure_package_kind(legacy)
    assert exc.value.code == "CLIENT_LEGACY_TYPE_REJECTED"


def test_unknown_type_is_rejected() -> None:
    with pytest.raises(ClientLegacyTypeRejected):
        ensure_package_kind("nonsense")
