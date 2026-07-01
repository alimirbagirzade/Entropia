"""Canonical Role Scope Matrix projection (doc 19 §3.3, §4.1, §6.1).

The V18 prototype hard-codes role-scope prose in the client; Production makes the
matrix a *read model of server truth*. The Management screen renders this; it is
never editable from the UI (doc 19 §13). Agent is shown as a non-login system
actor row — present for transparency, never an assignable human role.
"""

from __future__ import annotations

from typing import Any

from entropia.domain.lifecycle.enums import Role

# Bumped whenever the canonical scope semantics change; lets the client cache-bust
# and lets audit reason about which policy revision a decision was made under.
ROLE_MATRIX_REVISION = "2026-06-role-matrix-v1"

# Columns mirror the V18 matrix: View/Use, Edit, Delete, Trash, Role Assignment.
# Values are canonical scope words resolved from DOMAIN_MODEL §4/§5 policy — not
# free text the client may reinterpret.
_ROWS: tuple[dict[str, Any], ...] = (
    {
        "role": str(Role.ADMIN),
        "is_system_actor": False,
        "assignable": True,
        "view_use": "all",
        "edit": "all",
        "delete": "all",
        "trash": "manage",
        "role_assignment": "manage",
    },
    {
        "role": str(Role.SUPERVISOR),
        "is_system_actor": False,
        "assignable": True,
        "view_use": "shared_and_published",
        "edit": "own",
        "delete": "own",
        "trash": "none",
        "role_assignment": "none",
    },
    {
        "role": str(Role.USER),
        "is_system_actor": False,
        "assignable": True,
        "view_use": "own_and_published",
        "edit": "own",
        "delete": "own",
        "trash": "none",
        "role_assignment": "none",
    },
    {
        "role": "agent",
        "is_system_actor": True,
        "assignable": False,
        "view_use": "own_system_outputs",
        "edit": "own_output",
        "delete": "none",
        "trash": "none",
        "role_assignment": "none",
    },
)


def build_role_matrix() -> dict[str, Any]:
    """Return the canonical, read-only role-scope matrix projection."""
    return {
        "policy_revision": ROLE_MATRIX_REVISION,
        "columns": ["view_use", "edit", "delete", "trash", "role_assignment"],
        "rows": [dict(row) for row in _ROWS],
    }


__all__ = ["ROLE_MATRIX_REVISION", "build_role_matrix"]
