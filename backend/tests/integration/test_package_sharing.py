"""GAP-17 explicit package sharing — exercised against a real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Covers: share grants view + flips PRIVATE->EXPLICITLY_SHARED (+1 audit & +1
outbox, row_version bumped), the grantee gains catalog + detail + shared-with-me
access, the over-share hole is closed (a non-grantee never sees an
explicitly_shared package), owner/Admin-only grant listing, revoke removes access
and reverts to PRIVATE, self/unknown/foreign/public-scope share rejections,
optimistic-concurrency + idempotent-replay, and the ``can_share`` detail flag.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import sharing as sharing_cmd
from entropia.application.queries import library as library_query
from entropia.application.queries import sharing as sharing_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PackageKind, PrincipalType, Role, VisibilityScope
from entropia.domain.package.catalog import parse_catalog_filters
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    HumanUser,
    OutboxEvent,
    Principal,
    ResourceShare,
)
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import (
    AccessDeniedError,
    ShareGranteeNotFoundError,
    ShareGrantNotFoundError,
    ShareManagementForbiddenError,
    ShareNotAllowedForVisibilityError,
    ShareWithSelfError,
    StaleRevisionError,
)
from entropia.shared.pagination import PageParams

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
GRANTEE = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)
OTHER = Actor(principal_id="user_3", principal_type=PrincipalType.HUMAN, role=Role.USER)

GRANTEE_EMAIL = "grantee@example.com"
OTHER_EMAIL = "other@example.com"

_USERS = {
    "user_admin": ("admin", None, Role.ADMIN),
    "user_1": ("owner", None, Role.USER),
    "user_2": ("grantee", GRANTEE_EMAIL, Role.USER),
    "user_3": ("other", OTHER_EMAIL, Role.USER),
}


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_identities(session) -> None:
    for pid in _USERS:
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()
    for pid, (username, email, role) in _USERS.items():
        if await session.get(HumanUser, pid) is None:
            session.add(
                HumanUser(
                    user_id=pid,
                    username=username,
                    email=email,
                    display_name=username.title(),
                    current_role=role,
                    status="active",
                )
            )
    await session.flush()


async def _create_pkg(
    session, *, owner: str = "user_1", visibility: VisibilityScope = VisibilityScope.PRIVATE
) -> str:
    root, _detail, _revision = await pkg_repo.create_package(
        session,
        owner_principal_id=owner,
        created_by_principal_id=owner,
        package_kind=PackageKind.INDICATOR,
        input_contract={"name": "Shared Indicator"},
        output_contract={"output_kinds": ["signal"]},
        dependency_snapshot={},
        visibility_scope=visibility,
    )
    return root.entity_id


async def _list_ids(session, actor) -> set[str]:
    page = await library_query.list_packages(
        session, actor, PageParams(limit=50), filters=parse_catalog_filters()
    )
    return {row["entity_id"] for row in page["data"]}


async def test_share_grants_view_and_flips_visibility(session) -> None:
    await _seed_identities(session)
    pkg = await _create_pkg(session)
    before_audit = await _count(session, AuditEvent)
    before_outbox = await _count(session, OutboxEvent)

    result = await sharing_cmd.share_package(
        session, OWNER, entity_id=pkg, grantee_email=GRANTEE_EMAIL
    )
    await session.commit()

    assert result["visibility_scope"] == str(VisibilityScope.EXPLICITLY_SHARED)
    assert result["grantee_principal_id"] == "user_2"
    assert result["active_share_count"] == 1
    assert result["row_version"] == 2  # bumped from the create's row_version 1
    assert await _count(session, AuditEvent) == before_audit + 1
    assert await _count(session, OutboxEvent) == before_outbox + 1
    assert await _count(session, ResourceShare) == 1

    # The grantee now sees it in the catalog, in detail, and in shared-with-me.
    assert pkg in await _list_ids(session, GRANTEE)
    detail = await library_query.get_package_detail(session, GRANTEE, entity_id=pkg)
    assert detail["entity_id"] == pkg
    inbox = await library_query.list_shared_with_me(session, GRANTEE, PageParams(limit=50))
    assert {r["entity_id"] for r in inbox["data"]} == {pkg}


async def test_over_share_hole_is_closed_for_non_grantees(session) -> None:
    await _seed_identities(session)
    pkg = await _create_pkg(session)
    await sharing_cmd.share_package(session, OWNER, entity_id=pkg, grantee_email=GRANTEE_EMAIL)
    await session.commit()

    # A third user with NO grant cannot see the explicitly_shared package at all.
    assert pkg not in await _list_ids(session, OTHER)
    with pytest.raises(AccessDeniedError):
        await library_query.get_package_detail(session, OTHER, entity_id=pkg)
    inbox = await library_query.list_shared_with_me(session, OTHER, PageParams(limit=50))
    assert inbox["data"] == []


async def test_list_package_shares_is_owner_or_admin_only(session) -> None:
    await _seed_identities(session)
    pkg = await _create_pkg(session)
    await sharing_cmd.share_package(session, OWNER, entity_id=pkg, grantee_email=GRANTEE_EMAIL)
    await session.commit()

    listing = await sharing_query.list_package_shares(session, OWNER, entity_id=pkg)
    assert [s["grantee_email"] for s in listing["shares"]] == [GRANTEE_EMAIL]
    assert listing["row_version"] == 2
    # Admin may also inspect; a foreign user (even the grantee) may not.
    await sharing_query.list_package_shares(session, ADMIN, entity_id=pkg)
    with pytest.raises(ShareManagementForbiddenError):
        await sharing_query.list_package_shares(session, OTHER, entity_id=pkg)
    with pytest.raises(ShareManagementForbiddenError):
        await sharing_query.list_package_shares(session, GRANTEE, entity_id=pkg)


async def test_revoke_removes_access_and_reverts_to_private(session) -> None:
    await _seed_identities(session)
    pkg = await _create_pkg(session)
    shared = await sharing_cmd.share_package(
        session, OWNER, entity_id=pkg, grantee_email=GRANTEE_EMAIL
    )
    await session.commit()

    revoked = await sharing_cmd.revoke_package_share(
        session, OWNER, entity_id=pkg, share_id=shared["share_id"]
    )
    await session.commit()

    assert revoked["revoked"] is True
    assert revoked["active_share_count"] == 0
    assert revoked["visibility_scope"] == str(VisibilityScope.PRIVATE)
    # The former grantee has lost access everywhere.
    assert pkg not in await _list_ids(session, GRANTEE)
    with pytest.raises(AccessDeniedError):
        await library_query.get_package_detail(session, GRANTEE, entity_id=pkg)


async def test_share_validation_and_authorization_errors(session) -> None:
    await _seed_identities(session)
    private_pkg = await _create_pkg(session)
    published_pkg = await _create_pkg(session, visibility=VisibilityScope.PUBLISHED)

    # Self-share: an owner sharing with their own email is rejected. Principal is
    # flushed before its human_users child (the FK insert-order requirement).
    session.add(Principal(principal_id="user_self", principal_type=PrincipalType.HUMAN))
    await session.flush()
    session.add(
        HumanUser(
            user_id="user_self",
            username="self",
            email="self@example.com",
            display_name="Self",
            current_role=Role.USER,
            status="active",
        )
    )
    await session.flush()
    self_actor = Actor(principal_id="user_self", principal_type=PrincipalType.HUMAN, role=Role.USER)
    self_pkg = await _create_pkg(session, owner="user_self")
    with pytest.raises(ShareWithSelfError):
        await sharing_cmd.share_package(
            session, self_actor, entity_id=self_pkg, grantee_email="self@example.com"
        )

    with pytest.raises(ShareGranteeNotFoundError):
        await sharing_cmd.share_package(
            session, OWNER, entity_id=private_pkg, grantee_email="ghost@example.com"
        )
    with pytest.raises(ShareManagementForbiddenError):
        await sharing_cmd.share_package(
            session, OTHER, entity_id=private_pkg, grantee_email=GRANTEE_EMAIL
        )
    with pytest.raises(ShareNotAllowedForVisibilityError):
        await sharing_cmd.share_package(
            session, OWNER, entity_id=published_pkg, grantee_email=GRANTEE_EMAIL
        )
    # No grant row was created by any rejected attempt.
    assert await _count(session, ResourceShare) == 0


async def test_optimistic_concurrency_and_idempotency(session) -> None:
    await _seed_identities(session)
    pkg = await _create_pkg(session)

    # A stale expected_row_version (0/1 vs the current 1) is fine on the first
    # share (row_version 1); after it, the token is 2, so a stale 1 conflicts.
    first = await sharing_cmd.share_package(
        session, OWNER, entity_id=pkg, grantee_email=GRANTEE_EMAIL, expected_row_version=1
    )
    assert first["row_version"] == 2
    with pytest.raises(StaleRevisionError):
        await sharing_cmd.share_package(
            session, OWNER, entity_id=pkg, grantee_email=OTHER_EMAIL, expected_row_version=1
        )

    # Re-sharing the SAME grantee is a no-op (no second grant, no new audit).
    audit_before = await _count(session, AuditEvent)
    repeat = await sharing_cmd.share_package(
        session, OWNER, entity_id=pkg, grantee_email=GRANTEE_EMAIL
    )
    assert repeat["active_share_count"] == 1
    assert await _count(session, ResourceShare) == 1
    assert await _count(session, AuditEvent) == audit_before

    # An Idempotency-Key replay returns the cached result without re-running.
    keyed = await sharing_cmd.share_package(
        session, OWNER, entity_id=pkg, grantee_email=OTHER_EMAIL, idempotency_key="k-share-1"
    )
    audit_after_keyed = await _count(session, AuditEvent)
    replay = await sharing_cmd.share_package(
        session, OWNER, entity_id=pkg, grantee_email=OTHER_EMAIL, idempotency_key="k-share-1"
    )
    assert replay["share_id"] == keyed["share_id"]
    assert await _count(session, AuditEvent) == audit_after_keyed


async def test_revoke_errors_and_idempotency(session) -> None:
    await _seed_identities(session)
    pkg = await _create_pkg(session)
    other_pkg = await _create_pkg(session)
    shared = await sharing_cmd.share_package(
        session, OWNER, entity_id=pkg, grantee_email=GRANTEE_EMAIL
    )
    await session.flush()

    with pytest.raises(ShareGrantNotFoundError):
        await sharing_cmd.revoke_package_share(session, OWNER, entity_id=pkg, share_id="shr_ghost")
    # A grant that belongs to a DIFFERENT package cannot be revoked via this one.
    with pytest.raises(ShareGrantNotFoundError):
        await sharing_cmd.revoke_package_share(
            session, OWNER, entity_id=other_pkg, share_id=shared["share_id"]
        )

    revoked = await sharing_cmd.revoke_package_share(
        session, OWNER, entity_id=pkg, share_id=shared["share_id"]
    )
    assert revoked["active_share_count"] == 0
    # Revoking again is an idempotent no-op.
    again = await sharing_cmd.revoke_package_share(
        session, OWNER, entity_id=pkg, share_id=shared["share_id"]
    )
    assert again["revoked"] is True
    assert again["active_share_count"] == 0


async def test_detail_can_share_flag_is_owner_only(session) -> None:
    await _seed_identities(session)
    pkg = await _create_pkg(session)
    await sharing_cmd.share_package(session, OWNER, entity_id=pkg, grantee_email=GRANTEE_EMAIL)
    await session.commit()

    owner_detail = await library_query.get_package_detail(session, OWNER, entity_id=pkg)
    assert owner_detail["permissions"]["can_share"] is True
    grantee_detail = await library_query.get_package_detail(session, GRANTEE, entity_id=pkg)
    assert grantee_detail["permissions"]["can_share"] is False
