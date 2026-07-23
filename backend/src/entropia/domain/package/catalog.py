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

# Market / Timeframe catalog facets (doc 08 §3.2, finding P-06). A package's scope is
# DERIVED, never fabricated: an ESP is fixed to the SYSTEM sentinel ("System / Not
# applicable"); every other kind reads a declared scope from its revision
# ``input_contract`` (forward-compatible with a create flow that sets it), defaulting to
# UNSPECIFIED. The projection (``derive_catalog_scope``) and the SQL filter in
# ``application/queries/library.py`` apply the SAME rule so a server filter is exact.
MARKET_SCOPE_KEY = "market_scope"
TIMEFRAME_SCOPE_KEY = "timeframe_scope"
SYSTEM_SCOPE = "system"
UNSPECIFIED_SCOPE = "unspecified"

# Market is an OPEN instrument/market scope (values come from the catalog projection,
# doc 08 §3.2): a filter value is normalized + length-capped, never enum-checked, so an
# unmatched value yields an empty page rather than a 422 ("unsupported values not
# silently hidden").
MARKET_FILTER_MAX_LENGTH = 64

# Timeframe is a CLOSED capability vocabulary (doc 08 §3.2 "explicit / multi /
# same-as-base capability and System for ESP"), plus the UNSPECIFIED default; a bad
# timeframe filter is a 422 like the other closed facets.
TIMEFRAME_SCOPES: frozenset[str] = frozenset(
    {"explicit", "multi", "same_as_base", SYSTEM_SCOPE, UNSPECIFIED_SCOPE}
)

_EnumT = TypeVar("_EnumT", bound=StrEnum)


def derive_catalog_scope(package_kind: PackageKind, input_contract: object, key: str) -> str:
    """Derive a package's Market/Timeframe catalog scope (doc 08 §3.2, finding P-06).

    ESP packages are SYSTEM (Not applicable for a market/timeframe); every other kind
    reads its declared scope from ``input_contract[key]`` (absent in V1 until a create
    flow declares it), defaulting to UNSPECIFIED. The value is normalized (trim + lower)
    so it matches the SQL ``CASE`` expression in ``application/queries/library.py``
    exactly — the projection and the server filter never diverge.
    """
    if package_kind == PackageKind.EMBEDDED_SYSTEM:
        return SYSTEM_SCOPE
    raw = input_contract.get(key) if isinstance(input_contract, dict) else None
    if raw is None:
        return UNSPECIFIED_SCOPE
    return str(raw).strip().lower() or UNSPECIFIED_SCOPE


@dataclass(frozen=True, slots=True)
class CatalogFilters:
    """Validated catalog filter set. ``None`` means "no constraint on this facet"."""

    package_kind: PackageKind | None
    lifecycle_state: str | None
    validation_state: PackageValidationState | None
    approval_state: ApprovalState | None
    visibility_scope: VisibilityScope | None
    rationale_family_id: str | None
    market_scope: str | None
    timeframe_scope: str | None
    query: str | None


def _coerce_enum(enum_cls: type[_EnumT], value: str, field: str) -> _EnumT:
    try:
        return enum_cls(value.strip().lower())
    except ValueError as exc:
        raise CatalogFilterInvalid(f"'{value}' is not a valid {field}.") from exc


def _parse_market_filter(value: str | None) -> str | None:
    """Open market/instrument scope: normalize + length-cap, never enum-check."""
    if value is None or not value.strip():
        return None
    return value.strip().lower()[:MARKET_FILTER_MAX_LENGTH]


def _parse_timeframe_filter(value: str | None) -> str | None:
    """Closed timeframe capability vocabulary; a bad value is a 422 like other facets."""
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized not in TIMEFRAME_SCOPES:
        raise CatalogFilterInvalid(
            f"'{value}' is not a valid timeframe scope "
            "(use explicit, multi, same_as_base, system or unspecified)."
        )
    return normalized


def parse_catalog_filters(
    *,
    package_type: str | None = None,
    lifecycle_state: str | None = None,
    validation_state: str | None = None,
    approval_state: str | None = None,
    visibility_scope: str | None = None,
    rationale_family_id: str | None = None,
    market: str | None = None,
    timeframe: str | None = None,
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
        market_scope=_parse_market_filter(market),
        timeframe_scope=_parse_timeframe_filter(timeframe),
        query=text,
    )


__all__ = [
    "CATALOG_LIFECYCLE_STATES",
    "CATALOG_PACKAGE_KINDS",
    "MARKET_FILTER_MAX_LENGTH",
    "MARKET_SCOPE_KEY",
    "MAX_QUERY_LENGTH",
    "SYSTEM_SCOPE",
    "TIMEFRAME_SCOPES",
    "TIMEFRAME_SCOPE_KEY",
    "UNASSIGNED",
    "UNSPECIFIED_SCOPE",
    "CatalogFilters",
    "derive_catalog_scope",
    "parse_catalog_filters",
]
