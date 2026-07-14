"""Package Library approval policy (doc 08 §2, §4.3; CR-02).

Approve & Publish is Admin-only, mirroring ``market_data`` / ``research_data`` /
``esp`` — a non-Admin caller receives ``ApprovalRequiresAdmin`` (403). Request
Approval follows the shared owner/Admin edit policy (``ensure_can_edit``), so it
needs no dedicated gate here. UI hide/disable is never a substitute for these
checks; the command layer re-validates on every dispatch (doc 08 §2).
"""

from __future__ import annotations

from entropia.domain.identity.actor import Actor
from entropia.shared.errors import ApprovalRequiresAdmin


def ensure_can_approve(actor: Actor) -> None:
    """Approve & Publish is Admin-only (CR-02, doc 08 §4.3)."""
    if not actor.is_admin:
        raise ApprovalRequiresAdmin()


__all__ = ["ensure_can_approve"]
