"""Stage 3a Mainboard authorization gates — exercised against a real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).

These tests pin the cross-principal authorization boundary of the composition
plane (doc 01 §5, §7; DOMAIN_MODEL §4, §5):

* Work objects have NO visibility/sharing facet and NO publish path in Stage 3a
  (``create_work_object`` always produces an ``active`` root; ``active`` is a
  deletion/lifecycle facet, NOT a publication facet — CR-04). Cross-owner reuse
  is exposed via the Package catalog (Add Package → derived Strategy Draft), not
  by attaching another principal's raw work object. Therefore ANY foreign
  principal (human or Agent) attaching another principal's work object — whatever
  its ``lifecycle_state`` — MUST be denied (403). Only the owner or an Admin may
  attach. The original bug hardcoded ``visibility="explicitly_shared"``, which
  ``policy.can_view`` treats as readable by ANY authenticated actor; the fix gates
  the attach as owner/Admin-only (a foreign root resolves to private), so deriving
  ``published`` from ``lifecycle_state == "active"`` (which every work object has)
  would re-open the exact leak and is deliberately NOT done.
* The owner may attach their own work object; an Admin may attach a foreign one.
* An Agent cannot mutate (attach / revise / soft-delete) a human-owned work object
  it does not own.
"""

from __future__ import annotations

import pytest

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.queries import mainboard as mb_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.infrastructure.postgres.models import Principal
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.shared.errors import AccessDeniedError

pytestmark = pytest.mark.integration

OWNER = Actor(principal_id="owner_h", principal_type=PrincipalType.HUMAN, role=Role.USER)
FOREIGN = Actor(principal_id="foreign_h", principal_type=PrincipalType.HUMAN, role=Role.USER)
ADMIN = Actor(principal_id="admin_h", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
AGENT = Actor(principal_id="agent_sys", principal_type=PrincipalType.AGENT, role=None)

_PRINCIPALS: dict[str, PrincipalType] = {
    "owner_h": PrincipalType.HUMAN,
    "foreign_h": PrincipalType.HUMAN,
    "admin_h": PrincipalType.HUMAN,
    "agent_sys": PrincipalType.AGENT,
}


async def _seed_principals(session) -> None:
    for pid, ptype in _PRINCIPALS.items():
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=ptype))
    await session.flush()


async def _create_work_object(session, *, owner_id: str, name: str = "secret") -> tuple[str, str]:
    """Create a work object owned by ``owner_id`` with the real-world default
    ``lifecycle_state="active"``. Returns (root_id, revision_id).

    In Stage 3a there is no draft/published distinction and no sharing facet for
    work objects, so the same root is used for every cross-principal authz case —
    authorization does not depend on ``lifecycle_state``.
    """
    root, _detail, revision = await mb_repo.create_work_object(
        session,
        owner_principal_id=owner_id,
        created_by_principal_id=owner_id,
        object_kind=MainboardItemKind.STRATEGY,
        payload={"name": name},
    )
    await session.flush()
    return root.entity_id, revision.revision_id


# --------------------------------------------------------------------------- #
# Attach — cross-principal view gate (the vulnerability)                      #
# --------------------------------------------------------------------------- #


async def test_attach_foreign_work_object_is_denied(session) -> None:
    """A foreign, non-admin user attaching another user's work object onto their
    own workspace must be denied (403). Before the fix, attach hardcoded
    ``visibility="explicitly_shared"`` and this SUCCEEDED — leaking the pinned
    revision payload of someone else's work object. The root is created with the
    real default ``lifecycle_state="active"``, proving the gate does NOT treat
    ``active`` as a permissive "published" state (which would re-open the leak)."""
    await _seed_principals(session)
    root_id, revision_id = await _create_work_object(session, owner_id="owner_h")
    # FOREIGN attaches to FOREIGN's *own* workspace; the breach is pinning a
    # foreign root, not touching a foreign workspace.
    board = await mb_query.get_default_mainboard(session, FOREIGN)
    await session.flush()

    with pytest.raises(AccessDeniedError):
        await mb_cmd.attach_mainboard_item(
            session,
            FOREIGN,
            workspace_id=board["workspace_id"],
            root_id=root_id,
            revision_id=revision_id,
        )


async def test_attach_own_work_object_is_allowed(session) -> None:
    """The owner attaching their OWN work object succeeds — the fix narrows access
    to owner/Admin, it does not block legitimate self-composition."""
    await _seed_principals(session)
    root_id, revision_id = await _create_work_object(session, owner_id="owner_h")
    board = await mb_query.get_default_mainboard(session, OWNER)
    await session.flush()

    attached = await mb_cmd.attach_mainboard_item(
        session,
        OWNER,
        workspace_id=board["workspace_id"],
        root_id=root_id,
        revision_id=revision_id,
    )
    await session.commit()

    assert attached["item_id"].startswith("mbi_")
    assert attached["work_object_root_id"] == root_id
    assert attached["pinned_revision_id"] == revision_id


# --------------------------------------------------------------------------- #
# Agent cannot mutate a human-owned work object                               #
# --------------------------------------------------------------------------- #


async def test_agent_cannot_attach_human_work_object(session) -> None:
    """An Agent attaching a human's root onto the agent's own research workspace
    must be denied (403) — same view-gate boundary as a foreign human."""
    await _seed_principals(session)
    root_id, revision_id = await _create_work_object(session, owner_id="owner_h")
    board = await mb_query.get_default_mainboard(session, AGENT)
    await session.flush()

    with pytest.raises(AccessDeniedError):
        await mb_cmd.attach_mainboard_item(
            session,
            AGENT,
            workspace_id=board["workspace_id"],
            root_id=root_id,
            revision_id=revision_id,
        )


async def test_agent_cannot_revise_human_work_object(session) -> None:
    """An Agent appending a revision to a human-owned work object must be denied
    (403) — edit access requires ownership (or Admin)."""
    await _seed_principals(session)
    root_id, _revision_id = await _create_work_object(session, owner_id="owner_h")

    with pytest.raises(AccessDeniedError):
        await mb_cmd.create_work_object_revision(
            session,
            AGENT,
            root_id=root_id,
            payload={"name": "agent-edit"},
        )


async def test_agent_cannot_soft_delete_human_work_object(session) -> None:
    """An Agent soft-deleting a human-owned work object must be denied (403)."""
    await _seed_principals(session)
    root_id, _revision_id = await _create_work_object(session, owner_id="owner_h")

    with pytest.raises(AccessDeniedError):
        await mb_cmd.soft_delete_work_object(session, AGENT, root_id=root_id)


# --------------------------------------------------------------------------- #
# Admin override                                                              #
# --------------------------------------------------------------------------- #


async def test_admin_can_attach_foreign_work_object(session) -> None:
    """An Admin may attach a foreign root (admin bypasses the view gate). Guards
    that the fix does not regress the legitimate Admin override."""
    await _seed_principals(session)
    root_id, revision_id = await _create_work_object(session, owner_id="owner_h")
    board = await mb_query.get_default_mainboard(session, ADMIN)
    await session.flush()

    attached = await mb_cmd.attach_mainboard_item(
        session,
        ADMIN,
        workspace_id=board["workspace_id"],
        root_id=root_id,
        revision_id=revision_id,
    )
    await session.commit()

    assert attached["item_id"].startswith("mbi_")
    assert attached["work_object_root_id"] == root_id
    assert attached["pinned_revision_id"] == revision_id
