"""Sharing facet enums (GAP-17; Master Reference §6, §6.4)."""

from __future__ import annotations

from enum import StrEnum


class ShareResourceType(StrEnum):
    """The resource classes that support an explicit share grant.

    V1 shares Package Library heads only (the sole surface where the
    ``explicitly_shared`` visibility state is a real, readable scope). The
    ``resource_share`` table is generic so later resources reuse it verbatim.
    """

    PACKAGE = "package"
