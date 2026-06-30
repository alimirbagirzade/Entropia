"""ESP (Embedded System Package) per-domain enums (doc 09 §11.2, CR-04).

All values are lowercase snake_case and are returned over REST/SSE verbatim.
The registry trust projection (``ResolverTrustState``) is a SEPARATE facet from
the package revision validation/approval/visibility facets and from the root
lifecycle; Pre-Check uses only ``trusted_active`` resolvers (doc 09 §4.3 step 5,
§11.2 "Registry trust projection").
"""

from __future__ import annotations

from enum import StrEnum


class ResolverTrustState(StrEnum):
    """Registry trust selection state for a resolver (doc 09 §11.2).

    ``candidate``: proposed/under review, not selectable by Pre-Check.
    ``trusted_active``: the exact revision selectable for new conversions.
    ``deprecated``: removed from default new selection; historical pins still read.
    ``unavailable``: not resolvable (e.g. soft-deleted / withdrawn registry entry).
    """

    CANDIDATE = "candidate"
    TRUSTED_ACTIVE = "trusted_active"
    DEPRECATED = "deprecated"
    UNAVAILABLE = "unavailable"


class RuntimeAdapter(StrEnum):
    """Target runtime adapters an ESP revision may be executed under (doc 09
    §4.1 RuntimeAdapterRef, §4.2 "Runtime adapter"). The public semantic
    contract is separate from the implementation adapter; an incompatible
    adapter is never silently substituted."""

    PINE_V5 = "pine_v5"
    PYTHON = "python"
