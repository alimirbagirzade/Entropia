"""Mainboard composition-plane enums (doc 01; DOMAIN_MODEL §2.2).

Lowercase snake_case ``StrEnum`` values, stored via ``enum_column`` (portable
VARCHAR + CHECK). ``MainboardItemKind`` is the single canonical kind facet for
BOTH a work object's ``object_kind`` and a working item's ``item_kind`` — the
CR-01 kind guard is exact enum equality between the two.
"""

from __future__ import annotations

from enum import StrEnum


class MainboardItemKind(StrEnum):
    """The kind of work object that can sit on the Mainboard.

    Strategy is the internal, package-backed object; Trading Signal and Trade Log
    are EXTERNAL work objects (never a ``PackageKind``).
    """

    STRATEGY = "strategy"
    TRADING_SIGNAL = "trading_signal"
    TRADE_LOG = "trade_log"


class WorkspaceKind(StrEnum):
    """The provenance/role of a Mainboard workspace."""

    HUMAN_DEFAULT = "human_default"
    AGENT_RESEARCH = "agent_research"
    SYSTEM = "system"
