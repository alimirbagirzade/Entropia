"""Legacy session-mode upgrade over a credentialless ``user_admin`` (audit §9.5 /
TEST-07).

The golden E2E fixture (``SEED_E2E_GOLDEN``) deliberately skips ``seed_identities``
so a *clean* install can bootstrap its first Admin — it can never be evidence for
the UPGRADE path it intentionally avoids. This suite is that missing evidence: an
existing installation whose database already holds the legacy credentialless
``user_admin`` role row (an ACTIVE Admin nobody can log in as) plus real
owned/audited data, upgraded to session mode WITHOUT resetting the volume.

It proves the full §9.5 flow end to end on one real Postgres schema:

1. old state: credentialless ``user_admin`` (role Admin, no credential) + a
   representative owned domain record and an audit row;
2. mode-aware provisioning run twice is idempotent and never mints a
   session-blocking credentialless Admin;
3. a real first Admin bootstraps OVER the legacy row (fail-open only because the
   legacy Admin cannot log in), recorded as a PII-free legacy-upgrade note;
4. the real Admin can log in;
5. every prior id, ownership, audit row and the legacy row itself are byte-for-
   byte unchanged — a pure add, never a delete/demote/rename/credential graft;
6. the real Admin is protected as the last *login-capable* Admin — the
   credentialless legacy row does not pad the count and let it be demoted.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import auth as auth_cmd
from entropia.application.commands.role_assignment import assign_user_role
from entropia.apps import seed as seed_mod
from entropia.config import get_settings
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import ActorKind, DeletionState, PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    EntityRegistry,
    HumanCredential,
    HumanUser,
    Principal,
)
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import identity as identity_repo
from entropia.shared.errors import LastAdminProtectedError

pytestmark = pytest.mark.integration

LEGACY_ADMIN_ID = "user_admin"
OWNED_ENTITY_ID = "ent_legacy_0001"
PASSWORD = "correct-horse-battery"
BOOTSTRAP_EMAIL = "founder@example.com"


@pytest.fixture
def session_mode(monkeypatch: pytest.MonkeyPatch):
    """The real session profile: provisioning that skips the credentialless Admin."""
    monkeypatch.setenv("AUTH_MODE", "session")
    monkeypatch.setenv("ENTROPIA_SERVICE_TOKEN", "svc-secret-token")
    monkeypatch.delenv("SEED_DEV_ADMIN", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _seed_legacy_install(session: AsyncSession) -> AuditEvent:
    """The pre-upgrade database: a credentialless Admin + owned + audited data."""
    session.add(Principal(principal_id=LEGACY_ADMIN_ID, principal_type=PrincipalType.HUMAN))
    await session.flush()
    session.add(
        HumanUser(
            user_id=LEGACY_ADMIN_ID,
            username="legacy_admin",
            display_name="Legacy Admin",
            current_role=Role.ADMIN,
            status="active",
            version=1,
        )
    )
    # A representative owned domain record — its ownership must survive the upgrade.
    session.add(
        EntityRegistry(
            entity_id=OWNED_ENTITY_ID,
            entity_type="market_dataset",
            owner_principal_id=LEGACY_ADMIN_ID,
            created_by_principal_id=LEGACY_ADMIN_ID,
            deletion_state=DeletionState.ACTIVE,
            row_version=1,
        )
    )
    event = audit_repo.add_audit_event(
        session,
        event_kind="market_data.uploaded",
        actor_principal_id=LEGACY_ADMIN_ID,
        actor_kind=ActorKind.HUMAN,
        target_entity_id=OWNED_ENTITY_ID,
        target_entity_type="market_dataset",
    )
    await session.flush()
    # No HumanCredential row — this is precisely the "cannot log in" legacy Admin.
    assert await session.get(HumanCredential, LEGACY_ADMIN_ID) is None
    await session.commit()
    return event


async def test_session_upgrade_over_credentialless_admin_preserves_and_bootstraps(
    session: AsyncSession, session_mode: None
) -> None:
    legacy_event = await _seed_legacy_install(session)
    legacy_event_id = legacy_event.event_id

    # (2) Mode-aware provisioning run TWICE is idempotent and never adds a
    #     session-blocking credentialless Admin nor touches the legacy row.
    for _ in range(2):
        await seed_mod.seed_identities(session)
        await session.commit()
    assert await session.get(HumanCredential, LEGACY_ADMIN_ID) is None
    # Still exactly one Admin ROLE ROW (the legacy one), still zero LOGIN-capable.
    assert await identity_repo.count_active_admins(session) == 1
    assert await identity_repo.count_login_capable_admins(session) == 0

    # (3) The real first Admin bootstraps OVER the legacy row — allowed only because
    #     no login-capable Admin exists — recorded as a PII-free legacy-upgrade note.
    founder = await auth_cmd.sign_up(
        session,
        username="founder",
        password=PASSWORD,
        email=BOOTSTRAP_EMAIL,
        bootstrap_admin_email=BOOTSTRAP_EMAIL,
        auth_mode="session",
    )
    assert founder["role"] == str(Role.ADMIN)

    bootstrap_rows = (
        (
            await session.execute(
                select(AuditEvent).where(AuditEvent.event_kind == "user.admin_bootstrapped")
            )
        )
        .scalars()
        .all()
    )
    assert len(bootstrap_rows) == 1
    assert bootstrap_rows[0].event_metadata == {
        "legacy_credentialless_admin_not_login_capable": True
    }

    # (4) The real Admin can actually log in.
    login = await auth_cmd.login(session, username="founder", password=PASSWORD, ttl_minutes=60)
    assert login["user"]["role"] == str(Role.ADMIN)
    assert await identity_repo.count_login_capable_admins(session) == 1

    # (5) Nothing prior was deleted, demoted, renamed, or given a credential — the
    #     legacy Admin, its ownership, and its audit row are byte-for-byte intact.
    legacy = await session.get(HumanUser, LEGACY_ADMIN_ID)
    assert legacy is not None
    assert legacy.username == "legacy_admin"
    assert legacy.current_role == Role.ADMIN
    assert legacy.status == "active"
    assert legacy.version == 1
    assert await session.get(HumanCredential, LEGACY_ADMIN_ID) is None  # never grafted

    owned = await session.get(EntityRegistry, OWNED_ENTITY_ID)
    assert owned is not None
    assert owned.owner_principal_id == LEGACY_ADMIN_ID  # ownership unchanged
    assert owned.created_by_principal_id == LEGACY_ADMIN_ID
    assert owned.deletion_state == DeletionState.ACTIVE

    preserved_event = await session.get(AuditEvent, legacy_event_id)
    assert preserved_event is not None  # prior audit history intact
    assert preserved_event.actor_principal_id == LEGACY_ADMIN_ID

    # (6) The real Admin is the last LOGIN-capable Admin — the credentialless legacy
    #     row must not pad the count and let it be demoted into a locked install.
    founder_actor = Actor(
        principal_id=founder["user_id"],
        principal_type=PrincipalType.HUMAN,
        role=Role.ADMIN,
        correlation_id="corr_upgrade",
    )
    with pytest.raises(LastAdminProtectedError):
        await assign_user_role(
            session,
            founder_actor,
            target_user_id=founder["user_id"],
            target_role=Role.USER,
            expected_head_revision_id=1,
            auth_mode="session",
        )
