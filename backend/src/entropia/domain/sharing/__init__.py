"""Explicit resource-sharing domain (GAP-17; Master Reference §6, §6.4)."""

from entropia.domain.sharing.enums import ShareResourceType
from entropia.domain.sharing.policy import (
    SHAREABLE_VISIBILITIES,
    ensure_can_manage_shares,
    ensure_distinct_grantee,
    ensure_shareable_visibility,
)

__all__ = [
    "SHAREABLE_VISIBILITIES",
    "ShareResourceType",
    "ensure_can_manage_shares",
    "ensure_distinct_grantee",
    "ensure_shareable_visibility",
]
