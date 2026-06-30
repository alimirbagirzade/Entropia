"""Package Library catalog filters + ordering (doc 08 §3.2, §5, §13, CR-01).

Pure parsing/validation for the read-only catalog query. The catalog lists only
the four canonical package kinds (CR-01); the V18 ``Status`` dropdown is split
into the orthogonal facets it always was — lifecycle / validation / approval /
visibility — and never collapsed into one column (doc 08 §13). Invalid facet
values raise ``CatalogFilterInvalid`` (422) so the API never silently coerces a
bad filter; a legacy client type (``trading_signal`` / ``trade_log``) is rejected
by the canonical package-kind guard (CR-01) rather than treated as unknown.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from entropia.domain.lifecycle.enums import ApprovalState, PackageKind, VisibilityScope
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.package.kind import ensure_package_kind
from entropia.shared.errors import CatalogFilterInvalid

# The catalog discovers only the four canonical package kinds (CR-01); external
# Mainboard objects (trading_signal / trade_log) are never packages.
CATALOG_PACKAGE_KINDS: tuple[PackageKind, ...] = (
    PackageKind.STRATEGY,
    PackageKind.INDICATOR,
    PackageKind.CONDITION,
    PackageKind.EMBEDDED_SYSTEM,
)

# Root lifecycle states that remain discoverable in the catalog. ``deprecated`` is
# still listed (shown as deprecated, not offered for new work by default, doc 08
# §4.4); ``soft_deleted`` is excluded by the deletion overlay (Admin/Trash only).
CATALOG_LIFECYCLE_STATES: frozenset[str] = frozenset({"active", "deprecated"})

# Sentinel rationale-family filter value: packages with no pinned family.
UNASSIGNED = "unassigned"

# Catalog free-text search is capped server-side (doc 08 §5).
MAX_QUERY_LENGTH = 200

_EnumT = TypeVar("_EnumT", bound=StrEnum)


@dataclass(frozen=True, slots=True)
class CatalogFilters:
    """Validated catalog filter set. ``None`` means "no constraint on this facet"."""

    package_kind: PackageKind | None
    lifecycle_state: str | None
    validation_state: PackageValidationState | None
    approval_state: ApprovalState | None
    visibility_scope: VisibilityScope | None
    rationale_family_id: str | None
    query: str | None


def _coerce_enum(enum_cls: type[_EnumT], value: str, field: str) -> _EnumT:
    try:
        return enum_cls(value.strip().lower())
    except ValueError as exc:
        raise CatalogFilterInvalid(f"'{value}' is not a valid {field}.") from exc


def parse_catalog_filters(
    *,
    package_type: str | None = None,
    lifecycle_state: str | None = None,
    validation_state: str | None = None,
    approval_state: str | None = None,
    visibility_scope: str | None = None,
    rationale_family_id: str | None = None,
    query: str | None = None,
) -> CatalogFilters:
    """Validate raw catalog query params into a typed ``CatalogFilters``.

    Every facet is optional (no ``*`` required filters, doc 08 §5). Bad enum
    values raise ``CatalogFilterInvalid``; a legacy/unknown package type raises
    ``ClientLegacyTypeRejected`` via the canonical guard (CR-01).
    """
    kind = ensure_package_kind(package_type) if package_type else None

    lifecycle: str | None = None
    if lifecycle_state:
        lifecycle = lifecycle_state.strip().lower()
        if lifecycle not in CATALOG_LIFECYCLE_STATES:
            raise CatalogFilterInvalid(
                f"'{lifecycle_state}' is not a catalog lifecycle state "
                "(use 'active' or 'deprecated')."
            )

    validation = (
        _coerce_enum(PackageValidationState, validation_state, "validation_state")
        if validation_state
        else None
    )
    approval = (
        _coerce_enum(ApprovalState, approval_state, "approval_state") if approval_state else None
    )
    visibility = (
        _coerce_enum(VisibilityScope, visibility_scope, "visibility_scope")
        if visibility_scope
        else None
    )

    family = rationale_family_id.strip() if rationale_family_id else None
    text = query.strip()[:MAX_QUERY_LENGTH] if query and query.strip() else None

    return CatalogFilters(
        package_kind=kind,
        lifecycle_state=lifecycle,
        validation_state=validation,
        approval_state=approval,
        visibility_scope=visibility,
        rationale_family_id=family,
        query=text,
    )


__all__ = [
    "CATALOG_LIFECYCLE_STATES",
    "CATALOG_PACKAGE_KINDS",
    "MAX_QUERY_LENGTH",
    "UNASSIGNED",
    "CatalogFilters",
    "parse_catalog_filters",
]
