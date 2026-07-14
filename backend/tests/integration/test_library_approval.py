"""R2 (GAP-06 epic slice R2b) Package Library approval sub-flow: Request Approval +
Approve & Publish.

Exercised against a real database (auto-skips when no PostgreSQL is reachable, see
tests/integration/conftest.py). Covers the approval mutations the catalog advertised
via ``PackagePermissions`` (``can_request_approval`` / ``can_approve_publish``) but
never dispatched — and the LATENT BUG that ``can_approve_publish`` could never be true
because no command set ``APPROVAL_REQUESTED`` (doc 08 §7, §14 "Admin publish"):

* Request Approval moves a validation-PASSED head ``DRAFT -> APPROVAL_REQUESTED``
  (owner/Admin); a not-passed head -> 409 VALIDATION_REQUIRED; a foreign root -> 403;
  a stale head -> 409 PACKAGE_REVISION_CONFLICT; a repeat is idempotent. This is the
  transition that OPENS the Admin approve gate (``can_approve_publish`` flips true).
* Approve & Publish (Admin-only) transitions the requested + passed head to APPROVED +
  root PUBLISHED with an approval_decision proof; a non-Admin -> 403
  APPROVAL_REQUIRES_ADMIN; an unrequested/non-passed head -> 409; a repeat is idempotent.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import package_lifecycle as pkg_cmd
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.package.permissions import package_permissions
from entropia.infrastructure.postgres.models import (
    ApprovalDecision,
    AuditEvent,
    EntityRegistry,
    Principal,
)
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import (
    AccessDeniedError,
    ApprovalRequiresAdmin,
    LifecycleBlocked,
    PackageRevisionConflict,
    ValidationRequired,
)

pytestmark = pytest.mark.integration

OWNER = Actor(principal_id="user_owner", principal_type=PrincipalType.HUMAN, role=Role.USER)
OTHER = Actor(principal_id="user_other", principal_type=PrincipalType.HUMAN, role=Role.USER)
ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)


async def _seed_principals(session) -> None:
    for pid in ("user_owner", "user_other", "user_admin"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _make_pkg(
    session,
    *,
    owner: str = "user_owner",
    validation: PackageValidationState = PackageValidationState.PASSED,
    approval: ApprovalState = ApprovalState.DRAFT,
    visibility: VisibilityScope = VisibilityScope.PRIVATE,
    name: str = "Approvable RSI",
) -> EntityRegistry:
    root, _detail, _revision = await pkg_repo.create_package(
        session,
        owner_principal_id=owner,
        created_by_principal_id=owner,
        package_kind=PackageKind.INDICATOR,
        input_contract={"name": name},
        output_contract={"output_kinds": ["directional_signal"]},
        dependency_snapshot={},
        visibility_scope=visibility,
        validation_state=validation,
        approval_state=approval,
    )
    await session.flush()
    return root


async def _count(session, model, **filters) -> int:
    stmt = select(func.count()).select_from(model)
    for column, value in filters.items():
        stmt = stmt.where(getattr(model, column) == value)
    return int((await session.execute(stmt)).scalar_one())


def _admin_can_approve(root: EntityRegistry, revision) -> bool:
    return package_permissions(
        ADMIN,
        owner_principal_id=root.owner_principal_id,
        visibility_scope="private",
        lifecycle_state=root.lifecycle_state,
        validation_state=revision.validation_state,
        approval_state=revision.approval_state,
    ).can_approve_publish


# --------------------------------------------------------------------------- #
# Request Approval                                                             #
# --------------------------------------------------------------------------- #


async def test_request_approval_opens_the_latent_admin_gate(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")
    head = root.current_revision_id

    # Before the request, no command ever set APPROVAL_REQUESTED -> the Admin gate is
    # closed (the latent bug the catalog advertised but could never satisfy).
    base = await pkg_repo.get_revision(session, head or "")
    assert base is not None and not _admin_can_approve(root, base)

    result = await pkg_cmd.request_package_approval(
        session, OWNER, entity_id=root.entity_id, revision_id=head or ""
    )
    await session.flush()

    assert result["approval_state"] == str(ApprovalState.APPROVAL_REQUESTED)
    requested = await pkg_repo.get_revision(session, head or "")
    assert requested is not None
    assert requested.approval_state == ApprovalState.APPROVAL_REQUESTED
    # The gate is now OPEN — request_approval is exactly the missing transition.
    assert _admin_can_approve(root, requested)
    assert await _count(session, AuditEvent, event_kind="package.approval_requested") == 1


async def test_request_approval_requires_passed_validation(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner", validation=PackageValidationState.PENDING)

    with pytest.raises(ValidationRequired):
        await pkg_cmd.request_package_approval(
            session, OWNER, entity_id=root.entity_id, revision_id=root.current_revision_id or ""
        )


async def test_request_approval_foreign_root_is_forbidden(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")

    with pytest.raises(AccessDeniedError):
        await pkg_cmd.request_package_approval(
            session, OTHER, entity_id=root.entity_id, revision_id=root.current_revision_id or ""
        )


async def test_request_approval_stale_head_conflicts(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")

    with pytest.raises(PackageRevisionConflict):
        await pkg_cmd.request_package_approval(
            session,
            OWNER,
            entity_id=root.entity_id,
            revision_id=root.current_revision_id or "",
            expected_head_revision_id="pkgrev_stale",
        )


async def test_request_approval_repeat_is_idempotent(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")
    head = root.current_revision_id or ""

    await pkg_cmd.request_package_approval(
        session, OWNER, entity_id=root.entity_id, revision_id=head
    )
    await session.flush()
    result = await pkg_cmd.request_package_approval(
        session, OWNER, entity_id=root.entity_id, revision_id=head
    )
    await session.flush()

    assert result["approval_state"] == str(ApprovalState.APPROVAL_REQUESTED)
    # A second request while already requested does not double-audit.
    assert await _count(session, AuditEvent, event_kind="package.approval_requested") == 1


# --------------------------------------------------------------------------- #
# Approve & Publish                                                            #
# --------------------------------------------------------------------------- #


async def test_admin_approve_publishes_requested_passed_head(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner", visibility=VisibilityScope.PRIVATE)
    head = root.current_revision_id or ""
    await pkg_cmd.request_package_approval(
        session, OWNER, entity_id=root.entity_id, revision_id=head
    )
    await session.flush()

    result = await pkg_cmd.approve_and_publish_package(
        session, ADMIN, entity_id=root.entity_id, revision_id=head, note="ship it"
    )
    await session.flush()

    assert result["approval_state"] == str(ApprovalState.APPROVED)
    assert result["visibility_scope"] == str(VisibilityScope.PUBLISHED)
    revision = await pkg_repo.get_revision(session, head)
    detail = await pkg_repo.get_package_detail(session, root.entity_id)
    assert revision is not None and revision.approval_state == ApprovalState.APPROVED
    assert detail is not None and detail.visibility_scope == VisibilityScope.PUBLISHED
    # The Admin decision proof + the published audit are both written.
    assert await _count(session, ApprovalDecision, target_entity_id=root.entity_id) == 1
    assert await _count(session, AuditEvent, event_kind="package.approved_published") == 1


async def test_approve_by_non_admin_is_forbidden(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")
    head = root.current_revision_id or ""
    await pkg_cmd.request_package_approval(
        session, OWNER, entity_id=root.entity_id, revision_id=head
    )
    await session.flush()

    # The OWNER requested approval but cannot approve their own package (CR-02).
    with pytest.raises(ApprovalRequiresAdmin):
        await pkg_cmd.approve_and_publish_package(
            session, OWNER, entity_id=root.entity_id, revision_id=head
        )
    revision = await pkg_repo.get_revision(session, head)
    assert revision is not None and revision.approval_state == ApprovalState.APPROVAL_REQUESTED


async def test_approve_unrequested_head_is_blocked(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")  # DRAFT, never requested

    with pytest.raises(LifecycleBlocked):
        await pkg_cmd.approve_and_publish_package(
            session, ADMIN, entity_id=root.entity_id, revision_id=root.current_revision_id or ""
        )


async def test_approve_requires_passed_validation(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner", validation=PackageValidationState.FAILED)
    head = root.current_revision_id or ""
    # Force APPROVAL_REQUESTED past the request guard so we isolate the approve-side
    # validation check (a FAILED head can never be published).
    revision = await pkg_repo.get_revision(session, head)
    assert revision is not None
    revision.approval_state = ApprovalState.APPROVAL_REQUESTED
    await session.flush()

    with pytest.raises(ValidationRequired):
        await pkg_cmd.approve_and_publish_package(
            session, ADMIN, entity_id=root.entity_id, revision_id=head
        )


async def test_approve_stale_head_conflicts(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")
    head = root.current_revision_id or ""
    await pkg_cmd.request_package_approval(
        session, OWNER, entity_id=root.entity_id, revision_id=head
    )
    await session.flush()

    with pytest.raises(PackageRevisionConflict):
        await pkg_cmd.approve_and_publish_package(
            session,
            ADMIN,
            entity_id=root.entity_id,
            revision_id=head,
            expected_head_revision_id="pkgrev_stale",
        )


async def test_approve_repeat_is_idempotent(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")
    head = root.current_revision_id or ""
    await pkg_cmd.request_package_approval(
        session, OWNER, entity_id=root.entity_id, revision_id=head
    )
    await session.flush()

    await pkg_cmd.approve_and_publish_package(
        session, ADMIN, entity_id=root.entity_id, revision_id=head
    )
    await session.flush()
    result = await pkg_cmd.approve_and_publish_package(
        session, ADMIN, entity_id=root.entity_id, revision_id=head
    )
    await session.flush()

    assert result["approval_state"] == str(ApprovalState.APPROVED)
    # The second approve short-circuits (already APPROVED) — no duplicate decision/audit.
    assert await _count(session, ApprovalDecision, target_entity_id=root.entity_id) == 1
    assert await _count(session, AuditEvent, event_kind="package.approved_published") == 1
