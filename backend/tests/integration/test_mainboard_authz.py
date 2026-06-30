"""Stage 3a Mainboard authorization gates — exercised against a real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).

These tests pin the cross-principal authorization boundary of the composition
plane (doc 01 §5, §7; DOMAIN_MODEL §4, §5):

* A foreign, non-admin principal MUST NOT attach (and thereby read the pinned
  revision payload of) another principal's PRIVATE work object — a private root
  is one whose ``lifecycle_state`` is not ``"active"`` / not published. Attach
  visibility is derived from the root's actual state (mirroring
  ``application/jobs/research_data.py`` ``_require_viewable_root``); it must never
  be a hardcoded ``"explicitly_shared"`` (which ``policy.can_view`` treats as
  readable by ANY authenticated actor — the original vulnerability).
* A PUBLISHED (``lifecycle_state == "active"``) foreign root remains attachable —
  the fix narrows access to private roots, it does not blanket-block foreigners.
* An Agent principal cannot mutate (attach / revise / soft-delete) a human-owned
  work object it does not own.
* Admin override still works: an Admin may attach a foreign private root.
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


async def _create_work_object(
    session, *, owner_id: str, lifecycle_state: str, name: str = "secret"
) -> tuple[str, str]:
    """Create an ACTIVE (not deleted) work object owned by ``owner_id`` with the
    given domain ``lifecycle_state``. Returns (root_id, revision_id).

    ``lifecycle_state="active"`` is the published state; anything else (e.g.
    ``"draft"``) is private — readable only by the owner or an Admin.
    """
    root, _detail, revision = await mb_repo.create_work_object(
        session,
        owner_principal_id=owner_id,
        created_by_principal_id=owner_id,
        object_kind=MainboardItemKind.STRATEGY,
        payload={"name": name},
        lifecycle_state=lifecycle_state,
    )
    await session.flush()
    return root.entity_id, revision.revision_id


# --------------------------------------------------------------------------- #
# Attach — cross-principal view gate (the vulnerability)                      #
# --------------------------------------------------------------------------- #


async def test_attach_foreign_private_work_object_is_denied(session) -> None:
    """A foreign, non-admin user attaching another user's PRIVATE root onto their
    own workspace must be denied (403). Before the fix, attach hardcoded
    ``visibility="explicitly_shared"`` and this attach SUCCEEDED — leaking the
    pinned revision payload of someone else's private work object."""
    await _seed_principals(session)
    root_id, revision_id = await _create_work_object(
        session, owner_id="owner_h", lifecycle_state="draft"
    )
    # FOREIGN attaches to FOREIGN's *own* workspace; the breach is pinning a
    # foreign private root, not touching a foreign workspace.
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


async def test_attach_foreign_published_work_object_is_allowed(session) -> None:
    """A PUBLISHED (``lifecycle_state == "active"``) foreign root stays attachable:
    the fix derives visibility from state and must not blanket-block foreigners."""
    await _seed_principals(session)
    root_id, revision_id = await _create_work_object(
        session, owner_id="owner_h", lifecycle_state="active", name="published"
    )
    board = await mb_query.get_default_mainboard(session, FOREIGN)
    await session.flush()

    attached = await mb_cmd.attach_mainboard_item(
        session,
        FOREIGN,
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


async def test_agent_cannot_attach_human_private_work_object(session) -> None:
    """An Agent attaching a human's PRIVATE root onto the agent's own research
    workspace must be denied (403) — same view-gate breach as a foreign human."""
    await _seed_principals(session)
    root_id, revision_id = await _create_work_object(
        session, owner_id="owner_h", lifecycle_state="draft"
    )
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
    root_id, _revision_id = await _create_work_object(
        session, owner_id="owner_h", lifecycle_state="draft"
    )

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
    root_id, _revision_id = await _create_work_object(
        session, owner_id="owner_h", lifecycle_state="draft"
    )

    with pytest.raises(AccessDeniedError):
        await mb_cmd.soft_delete_work_object(session, AGENT, root_id=root_id)


# --------------------------------------------------------------------------- #
# Admin override                                                              #
# --------------------------------------------------------------------------- #


async def test_admin_can_attach_foreign_private_work_object(session) -> None:
    """An Admin may attach a foreign PRIVATE root (admin bypasses the view gate).
    Guards that the fix does not regress the legitimate Admin override."""
    await _seed_principals(session)
    root_id, revision_id = await _create_work_object(
        session, owner_id="owner_h", lifecycle_state="draft"
    )
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
