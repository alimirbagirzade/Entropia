"""TEST-05 / PROV-02/03 — legacy credentialless-Admin upgrade on the REAL database
shape an older release left behind.

A fresh schema is NOT representative of an upgraded install: the blocking record
(an ACTIVE ``user_admin`` Admin HumanUser with NO credential) was created by an
earlier seed. This fixture reconstructs that exact state — legacy admin +
principal, representative owned domain rows, audit/outbox history, the required
Agent identity — then runs the session-mode provisioning/upgrade path twice and
proves:

* a bootstrap-email signup becomes a credentialed Admin even though a legacy
  credentialless Admin role row exists (PROV-02, §6.5.3);
* the bootstrap audit carries the PII-free legacy-upgrade note;
* a second matching signup does NOT mint a second Admin (fail-closed, §6.5.6);
* every legacy row and the owner id are byte-for-byte unchanged (audit §12);
* last-operational-Admin protection counts login-capable Admins, so the only
  real Admin cannot be demoted even though two Admin role rows exist (PROV-03).

Auto-skips without PostgreSQL (session fixture).
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import auth as auth_cmd
from entropia.application.commands.roles import change_user_role
from entropia.config import get_settings
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import ActorKind, PrincipalType, Role
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.infrastructure.postgres.models import (
    Agent,
    AuditEvent,
    HumanCredential,
    HumanUser,
    Principal,
)
from entropia.infrastructure.postgres.models.registry import EntityRegistry
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import identity as identity_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.shared.errors import LastAdminProtectedError

pytestmark = pytest.mark.integration

LEGACY_ADMIN_ID = "user_admin"
LEGACY_AGENT_ID = "agent_alpha"
BOOTSTRAP_EMAIL = "founder@example.com"
PASSWORD = "correct-horse-battery"


async def _seed_legacy_installation(session: AsyncSession) -> str:
    """Reproduce the DB an old ``AUTH_MODE=dev`` seed left behind. Returns the
    entity_id of a domain row owned/created by the legacy admin principal."""
    # Legacy credentialless Admin + its principal (NO HumanCredential).
    session.add(Principal(principal_id=LEGACY_ADMIN_ID, principal_type=PrincipalType.HUMAN))
    await session.flush()
    session.add(
        HumanUser(
            user_id=LEGACY_ADMIN_ID,
            username="admin",
            display_name="Default Admin",
            current_role=Role.ADMIN,
            status="active",
        )
    )
    await session.flush()

    # Required Agent/system identity.
    session.add(Principal(principal_id=LEGACY_AGENT_ID, principal_type=PrincipalType.AGENT))
    await session.flush()
    session.add(Agent(agent_id=LEGACY_AGENT_ID, name="Alpha Agent", enabled=True))
    await session.flush()

    # Representative domain rows owned/created by the legacy principal.
    root, _revision = await md_repo.create_market_dataset(
        session,
        owner_principal_id=LEGACY_ADMIN_ID,
        created_by_principal_id=LEGACY_ADMIN_ID,
        market_data_type=MarketDataType.OHLCV,
        payload={"instrument": "LEGACY", "resolution": "1D"},
        title="Legacy OHLCV",
        instrument_id="LEGACY",
        revision_state=MarketRevisionState.APPROVED,
        lifecycle_state="active",
    )

    # Audit/outbox history attributed to the legacy principal.
    audit_repo.add_audit_event(
        session,
        event_kind="user.signed_up",
        actor_principal_id=LEGACY_ADMIN_ID,
        actor_kind=ActorKind.HUMAN,
        target_entity_id=LEGACY_ADMIN_ID,
        target_entity_type="human_user",
        new_state="active",
    )
    audit_repo.add_outbox_event(
        session,
        event_type="user_created",
        resource_type="human_user",
        resource_id=LEGACY_ADMIN_ID,
        payload={"action": "user_created"},
    )
    await session.commit()
    return root.entity_id


async def _admin_snapshot(session: AsyncSession) -> dict[str, object]:
    """A field-by-field snapshot of the legacy admin's principal + user rows."""
    principal = await session.get(Principal, LEGACY_ADMIN_ID)
    user = await session.get(HumanUser, LEGACY_ADMIN_ID)
    assert principal is not None and user is not None
    return {
        "principal_type": principal.principal_type,
        "username": user.username,
        "display_name": user.display_name,
        "current_role": user.current_role,
        "status": user.status,
        "deletion_state": user.deletion_state,
        "version": user.version,
        "role_changed_by": user.role_changed_by,
        "email": user.email,
    }


def _admin_actor(principal_id: str) -> Actor:
    return Actor(principal_id=principal_id, principal_type=PrincipalType.HUMAN, role=Role.ADMIN)


async def test_legacy_credentialless_admin_upgrade_twice_and_protection(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUTH_MODE", "session")
    get_settings.cache_clear()
    try:
        entity_id = await _seed_legacy_installation(session)

        legacy_before = await _admin_snapshot(session)
        registry_before = await session.get(EntityRegistry, entity_id)
        assert registry_before is not None
        assert registry_before.owner_principal_id == LEGACY_ADMIN_ID

        # The legacy Admin is a role row but not login-capable: window is OPEN.
        assert await identity_repo.count_active_admins(session) == 1
        assert await identity_repo.count_login_capable_admins(session) == 0

        # Provisioning/upgrade path run TWICE — idempotent, session mode never
        # re-creates the credentialless admin and never duplicates a principal.
        await seed_identities_twice(session)

        assert await identity_repo.count_active_admins(session) == 1
        assert await identity_repo.count_login_capable_admins(session) == 0

        # First bootstrap-email signup provisions the first REAL credentialed Admin.
        first = await auth_cmd.sign_up(
            session,
            username="founder",
            password=PASSWORD,
            email=BOOTSTRAP_EMAIL,
            bootstrap_admin_email=BOOTSTRAP_EMAIL,
            auth_mode="session",
        )
        await session.commit()
        assert first["role"] == str(Role.ADMIN)
        assert await session.get(HumanCredential, first["user_id"]) is not None

        # The bootstrap audit carries the PII-free legacy-upgrade note.
        boot_events = (
            (
                await session.execute(
                    select(AuditEvent).where(AuditEvent.event_kind == "user.admin_bootstrapped")
                )
            )
            .scalars()
            .all()
        )
        assert len(boot_events) == 1
        assert boot_events[0].event_metadata == {
            "legacy_credentialless_admin_not_login_capable": True
        }

        # Second matching signup must NOT mint another Admin (fail-closed).
        second = await auth_cmd.sign_up(
            session,
            username="second",
            password=PASSWORD,
            email="second@example.com",
            bootstrap_admin_email="second@example.com",
            auth_mode="session",
        )
        await session.commit()
        assert second["role"] == str(Role.USER)
        assert await identity_repo.count_login_capable_admins(session) == 1
        # Still exactly one bootstrap event — the second attempt emitted none.
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_kind == "user.admin_bootstrapped")
            )
            == 1
        )

        # Every legacy row + owner id is byte-for-byte unchanged (audit §12).
        assert await _admin_snapshot(session) == legacy_before
        registry_after = await session.get(EntityRegistry, entity_id)
        assert registry_after is not None
        assert registry_after.owner_principal_id == LEGACY_ADMIN_ID
        assert await session.get(HumanCredential, LEGACY_ADMIN_ID) is None

        # PROV-03: two Admin ROLE ROWS exist (legacy + founder) but only ONE is
        # login-capable, so demoting the only real Admin must be blocked. A
        # role-row count would wrongly allow it and lock the installation.
        assert await identity_repo.count_active_admins(session) == 2
        assert await identity_repo.count_login_capable_admins(session) == 1
        with pytest.raises(LastAdminProtectedError):
            await change_user_role(
                session,
                _admin_actor(str(first["user_id"])),
                target_user_id=str(first["user_id"]),
                new_role=Role.USER,
                auth_mode="session",
            )
    finally:
        get_settings.cache_clear()


async def seed_identities_twice(session: AsyncSession) -> None:
    """Run the identity provisioning path twice under session mode (idempotent)."""
    from entropia.apps.seed import seed_identities

    await seed_identities(session)
    await session.commit()
    await seed_identities(session)
    await session.commit()
