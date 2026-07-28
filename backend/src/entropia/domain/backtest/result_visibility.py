"""Backtest Result read-visibility policy (doc 16 §2, §9.3; finding O-14).

A ``backtest_result`` row carries NO visibility column of its own. Doc 16 §1
defines the Result as the immutable evidence artifact OF a composition, so the
composition (Mainboard workspace) registry root is the authority for who may read
it. This module is the single pure predicate every Results History surface (list,
detail, compare) evaluates; the DB-bound grantee/scope resolution lives in
``application/queries/result_access.py``.

Doc 16 §2 grants read access to:

* **Admin** — every accessible result (already ``identity.can_view``).
* **User** — doc 16 §2 "own + explicitly shared + published": own results, plus results
  whose composition carries an ACTIVE grant to that principal in the SAME generic
  ``resource_share`` table Package sharing already uses (GAP-17). There is no
  second sharing mechanism; the grantee set is resolved by the caller and fed to
  ``identity.can_view`` verbatim, which fails CLOSED when it is ``None``.
* **Supervisor** — doc 16 §2 "results within the accessible/shared work scope;
  someone else's result is read-only": everything a User sees, PLUS the Agent research scope the
  Analysis Lab already opens to exactly (Admin, Supervisor) regardless of
  ownership (``queries/agent_workspace.py::_LAB_ROLES``, doc 18 §2). That lab
  scope is the only "accessible work scope" this system actually models — no team
  or project grouping exists, so nothing wider is invented here. "Salt-okunur" is
  not a second rule: ``identity.can_edit`` already denies every non-owner write,
  so a Supervisor reading someone else's result gets ``soft_delete=False``.

Honest boundary (V1): a **published** result cannot exist. ``mainboard_workspace``
has no ``visibility_scope`` column, so no composition is ever published/system —
the doc 16 §2 "published" branch is unreachable rather than faked with a default.
"""

from __future__ import annotations

from collections.abc import Collection

from entropia.domain.identity import policy as identity_policy
from entropia.domain.identity.actor import Actor
from entropia.domain.lifecycle.enums import Role, VisibilityScope
from entropia.domain.mainboard.enums import WorkspaceKind

# The roles the Analysis Lab opens the Agent research scope to (doc 18 §2). Kept
# identical to ``queries/agent_workspace.py::_LAB_ROLES`` on purpose: a result
# produced inside an Agent research workspace must not be readable by a role that
# cannot already read that workspace's tasks, hypotheses and messages.
LAB_SCOPE_ROLES: frozenset[Role] = frozenset({Role.ADMIN, Role.SUPERVISOR})


def is_lab_scope_readable(actor: Actor, *, workspace_kind: str | None) -> bool:
    """True iff this is an Agent research composition and the actor oversees it.

    Ownership is deliberately NOT consulted here — the lab scope is a role scope
    (Admin/Supervisor), exactly as the Analysis Lab read models already enforce.
    An unauthenticated caller has no role and is rejected before this point.
    """
    if workspace_kind is None or not actor.is_authenticated:
        return False
    return workspace_kind == WorkspaceKind.AGENT_RESEARCH and actor.role in LAB_SCOPE_ROLES


def can_view_result_composition(
    actor: Actor,
    *,
    owner_principal_id: str | None,
    workspace_kind: str | None = None,
    shared_principal_ids: Collection[str] | None = None,
) -> bool:
    """Read access to every Result of one composition (doc 16 §2).

    Delegates owner/Admin/explicit-share resolution to the shared identity policy
    with ``EXPLICITLY_SHARED`` visibility — that is what makes ``resource_share``
    grants count. Passing ``shared_principal_ids=None`` keeps the fail-closed
    default: no resolved grant means owner + Admin only.
    """
    if identity_policy.can_view(
        actor,
        owner_principal_id=owner_principal_id,
        visibility=str(VisibilityScope.EXPLICITLY_SHARED),
        shared_principal_ids=shared_principal_ids,
    ):
        return True
    return is_lab_scope_readable(actor, workspace_kind=workspace_kind)


def ensure_can_view_result_composition(
    actor: Actor,
    *,
    owner_principal_id: str | None,
    workspace_kind: str | None = None,
    shared_principal_ids: Collection[str] | None = None,
) -> None:
    """Raise ``AccessDeniedError`` unless the actor may read this composition."""
    if not can_view_result_composition(
        actor,
        owner_principal_id=owner_principal_id,
        workspace_kind=workspace_kind,
        shared_principal_ids=shared_principal_ids,
    ):
        identity_policy.ensure_can_view(
            actor,
            owner_principal_id=owner_principal_id,
            visibility=str(VisibilityScope.EXPLICITLY_SHARED),
            shared_principal_ids=shared_principal_ids,
        )


__all__ = [
    "LAB_SCOPE_ROLES",
    "can_view_result_composition",
    "ensure_can_view_result_composition",
    "is_lab_scope_readable",
]
