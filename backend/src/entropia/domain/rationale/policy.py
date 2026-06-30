"""Rationale Families authorization policy — the global shared-editing exception
(doc 10 §2, DOMAIN_MODEL §6).

This page is a deliberate, resource-type-scoped exception to owner-only editing:
every authenticated actor (Admin / Supervisor / User / Agent) may create, edit,
rename, soft-delete ANY family and edit ANY assignment regardless of
``created_by`` (provenance only). The generic ``can_edit(owner)`` policy is NOT
used here. Guests are rejected before any registry/assignment data is returned.

Restore and permanent delete are explicitly NOT part of this exception — they stay
Admin-only and are enforced by the generic deletion/Trash commands, not here.
"""

from __future__ import annotations

from entropia.domain.identity.actor import Actor
from entropia.domain.identity.policy import require_authenticated


def ensure_can_manage_families(actor: Actor) -> None:
    """``can_manage_rationale_families(actor)`` — create/edit/rename/soft-delete.

    True for any authenticated Admin/Supervisor/User/Agent; Guest -> 401
    (doc 10 §2 canonical rule). Ownership is irrelevant (shared exception).
    """
    require_authenticated(actor)


def ensure_can_edit_assignments(actor: Actor) -> None:
    """``can_edit_rationale_assignments(actor)`` — stage + save the shared table.

    Same shared-editing exception as family management. The semantic assignment
    scope never widens to package code / parameters / approval / publication
    (doc 10 §2 policy boundary); those stay owner/Admin-gated in their own domains.
    """
    require_authenticated(actor)
