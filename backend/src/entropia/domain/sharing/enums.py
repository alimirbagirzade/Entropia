"""Sharing facet enums (GAP-17; Master Reference §6, §6.4)."""

from __future__ import annotations

from enum import StrEnum


class ShareResourceType(StrEnum):
    """The resource classes that support an explicit share grant.

    The ``resource_share`` table is generic, so each value is simply the sharable
    resource's ``entity_registry.entity_type`` — a grant row therefore needs no
    per-resource table and no second sharing mechanism.

    ``PACKAGE`` is the only kind with a *managed* grant surface (grant/revoke
    commands + the ``explicitly_shared`` visibility state on ``package_root``).
    ``COMPOSITION`` is a READ scope: Results History resolves a Mainboard
    workspace's active grants to decide who may read the immutable Results
    produced in it (doc 16 §2, finding O-14). A Mainboard workspace carries no
    ``visibility_scope`` column, so a composition is never published — it is
    readable by its owner, its active grantees, Admin, and (for Agent research
    workspaces) the Analysis Lab roles.
    """

    PACKAGE = "package"
    COMPOSITION = "mainboard_workspace"
