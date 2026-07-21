"""Retire the credentialless dev Admin so a session-mode install can bootstrap.

    python -m entropia.apps.retire_dev_admin

Older local databases were seeded (under ``AUTH_MODE=dev``) with an ACTIVE
``user_admin`` HumanUser that has NO login credential. First-Admin bootstrap is
fail-closed — it promotes a matching signup ONLY while no active Admin exists —
so that row permanently blocks a real session-mode installation from ever
provisioning its first Admin, while itself being unreachable (nobody can log in
as it; it only answers to ``X-Actor-Id``, which session mode ignores).

This transition marks that ONE row ``status='disabled'``. It is deliberately the
narrowest possible change:

* nothing is deleted — the Principal row, every ownership FK, all audit history
  and all domain data stay exactly as they are; only the login/admin-count
  status flag moves,
* it is idempotent — a second run is a no-op,
* it is fail-closed — it refuses unless every precondition holds (see below),
  and it never touches any principal other than ``SEED_ADMIN_ID``,
* it is auditable — a ``user.dev_admin_retired`` audit event records it.

Refuses (exit code 2, no write) when:

* the row carries a real password credential — that is somebody's live account,
  not the seed fixture,
* another active Admin already exists — the install already has an Admin, so
  retiring this one would only reduce administrative access,
* the row is not an Admin — out of scope for this transition.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.apps.seed import DEFAULT_ADMIN_ID
from entropia.domain.lifecycle.enums import ActorKind, DeletionState, Role
from entropia.infrastructure.observability import configure_logging, get_logger
from entropia.infrastructure.postgres.engine import get_session_factory
from entropia.infrastructure.postgres.models import HumanUser
from entropia.infrastructure.postgres.models.auth import HumanCredential
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import identity as identity_repo

_TARGET_TYPE = "human_user"

EXIT_OK = 0
EXIT_REFUSED = 2


class RetireRefused(Exception):
    """A precondition failed — nothing was written."""


async def retire_dev_admin(session: AsyncSession, *, admin_id: str = DEFAULT_ADMIN_ID) -> str:
    """Disable the credentialless seed Admin. Returns a human-readable outcome.

    Raises ``RetireRefused`` (leaving the transaction untouched) when a
    precondition fails. The caller owns the commit.
    """
    user = await session.get(HumanUser, admin_id)
    if user is None:
        return f"no-op: {admin_id} does not exist (already a clean session-mode database)"
    if user.status != "active" or user.deletion_state != DeletionState.ACTIVE:
        return f"no-op: {admin_id} is already retired (status={user.status})"
    if user.current_role != Role.ADMIN:
        raise RetireRefused(f"{admin_id} is not an Admin (role={user.current_role}) — out of scope")

    credential = await session.scalar(
        select(HumanCredential).where(HumanCredential.user_id == admin_id)
    )
    if credential is not None:
        raise RetireRefused(
            f"{admin_id} has a password credential — this is a real account, not the "
            "credentialless dev seed. Demote or disable it through the normal admin flow."
        )

    # Serialize against concurrent demotions/bootstraps exactly like the demote
    # path, then re-count: another active Admin means the install needs no
    # bootstrap window and this row is not what is blocking anything.
    await identity_repo.lock_admin_count(session)
    active_admins = await identity_repo.count_active_admins(session)
    if active_admins > 1:
        raise RetireRefused(
            f"{active_admins} active Admins exist — {admin_id} is not blocking bootstrap. "
            "Refusing to reduce administrative access."
        )

    user.status = "disabled"
    audit_repo.add_audit_event(
        session,
        event_kind="user.dev_admin_retired",
        actor_principal_id=None,  # operator-run CLI, not an authenticated principal
        actor_kind=ActorKind.SYSTEM_SERVICE,
        target_entity_id=admin_id,
        target_entity_type=_TARGET_TYPE,
        previous_state="active",
        new_state="disabled",
        reason="credentialless_dev_admin_blocks_session_mode_bootstrap",
        severity="warning",
    )
    await session.flush()
    return (
        f"retired: {admin_id} is now status=disabled. First-Admin bootstrap is open — "
        "sign up with ENTROPIA_BOOTSTRAP_ADMIN_EMAIL to provision a real Admin."
    )


async def _run() -> int:
    log = get_logger("retire_dev_admin")
    factory = get_session_factory()
    async with factory() as session:
        try:
            outcome = await retire_dev_admin(session)
        except RetireRefused as exc:
            await session.rollback()
            log.warning("retire_dev_admin.refused", reason=str(exc))
            print(f"REFUSED: {exc}", file=sys.stderr)
            return EXIT_REFUSED
        await session.commit()
    log.info("retire_dev_admin.done", outcome=outcome)
    print(outcome)
    return EXIT_OK


def run() -> None:
    configure_logging()
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    run()
