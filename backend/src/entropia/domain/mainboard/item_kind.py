"""Client-supplied item-kind guard (doc 03 §11 taxonomy, acceptance AOS-03 §14).

The Add Outsource Signal chooser offers exactly two external work object kinds:
``trading_signal`` and ``trade_log``. The V18 legacy prototype labelled those same
two choices ``signal_package`` / ``trade_log_package`` — doc 03 §0.1 marks that
vocabulary as "V18 legacy prototype label; Production domain/API type değildir".
AOS-03 requires that a client still speaking it be told so **by name**: the server
returns ``INVALID_ITEM_KIND`` and creates no PackageKind expansion, root, revision
or item.

This guard is the OPPOSITE direction of ``domain/package/kind.py``'s
``LEGACY_PACKAGE_TYPES``: that one keeps the two external kinds OUT of
``PackageKind`` (TS-01 / TL-01); this one keeps the two package-flavoured aliases
OUT of ``MainboardItemKind``. Both guards are required and neither replaces the
other.

Kept distinct from ``MainboardItemKindMismatchError`` on purpose — that code
answers "your kind disagrees with the root's kind" (CR-01), while this one answers
"that is not a kind this system has".
"""

from __future__ import annotations

from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.shared.errors import InvalidItemKindError, MainboardItemKindMismatchError

# Legacy V18 prototype labels mapped to the canonical kind they meant. Recognized
# ONLY so they can be rejected by name — never coerced to the canonical value, or
# the "no root/revision/item is created" half of AOS-03 would be violated.
LEGACY_ITEM_KIND_ALIASES: dict[str, MainboardItemKind] = {
    "signal_package": MainboardItemKind.TRADING_SIGNAL,
    "trade_log_package": MainboardItemKind.TRADE_LOG,
}


def ensure_mainboard_item_kind(
    value: str | MainboardItemKind,
    *,
    field: str = "object_kind",
) -> MainboardItemKind:
    """Coerce a client-supplied kind to a canonical ``MainboardItemKind``.

    Raises ``InvalidItemKindError`` (422 ``INVALID_ITEM_KIND``) for a legacy
    package-flavoured alias and ``MainboardItemKindMismatchError`` for any other
    value outside the enum.
    """
    if isinstance(value, MainboardItemKind):
        return value
    canonical = LEGACY_ITEM_KIND_ALIASES.get(value.strip().lower())
    if canonical is not None:
        raise InvalidItemKindError(
            f"{value!r} is a legacy item kind and is not a supported work object type.",
            details=[{"field": field, "actual": value, "expected": canonical.value}],
            field_path=field,
        )
    try:
        return MainboardItemKind(value)
    except ValueError as exc:
        raise MainboardItemKindMismatchError(
            f"Unknown work object kind {value!r}.",
            details=[{"field": field, "actual": value}],
        ) from exc
