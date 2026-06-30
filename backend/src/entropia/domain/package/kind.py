"""Package-kind guard (doc 09 §14, CR-01).

The canonical package type enum is ``strategy``, ``indicator``, ``condition``,
``embedded_system`` only. Legacy client types (``trading_signal`` / ``trade_log``)
are external Mainboard working objects and must never become a PackageRoot. This
guard normalizes/validates a client-supplied kind and rejects legacy values with
the typed ``ClientLegacyTypeRejected`` error.
"""

from __future__ import annotations

from entropia.domain.lifecycle.enums import PackageKind
from entropia.shared.errors import ClientLegacyTypeRejected

# Legacy client package types that are explicitly excluded from the package model
# (doc 09 §12 "Canonical types", §14). They remain Mainboard external objects.
LEGACY_PACKAGE_TYPES: frozenset[str] = frozenset({"trading_signal", "trade_log"})


def ensure_package_kind(value: str | PackageKind) -> PackageKind:
    """Coerce a client-supplied package kind to a canonical ``PackageKind``.

    Raises ``ClientLegacyTypeRejected`` for ``trading_signal`` / ``trade_log``
    and for any value outside the canonical enum.
    """
    if isinstance(value, PackageKind):
        return value
    raw = value.strip().lower()
    if raw in LEGACY_PACKAGE_TYPES:
        raise ClientLegacyTypeRejected(
            f"Package type '{raw}' is a legacy client type and cannot be modeled as a package."
        )
    try:
        return PackageKind(raw)
    except ValueError as exc:
        raise ClientLegacyTypeRejected(f"'{raw}' is not a valid package type.") from exc
