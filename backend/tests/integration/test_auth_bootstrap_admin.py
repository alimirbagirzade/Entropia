"""post-V1 — first-Admin bootstrap provisioning (TIER 2; closes the PR #38
honest boundary "signup always gets the baseline role").

Auto-skips without PostgreSQL (session fixture). Proves:
- env unset (bootstrap_admin_email=None) -> baseline User role, no new events
  (zero behavior change);
- matching email + no active Admin -> Admin, with a dedicated
  ``user.admin_bootstrapped`` audit event and ``admin_bootstrapped`` outbox
  event in the SAME transaction;
- matching email while an active Admin exists -> baseline User (fail-closed),
  no bootstrap events;
- non-matching email / signup without email -> baseline User;
- case + whitespace normalization on the match;
- the route wiring reads ENTROPIA_BOOTSTRAP_ADMIN_EMAIL from settings.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import auth as auth_cmd
from entropia.config import get_settings
from entropia.domain.lifecycle.enums import Role
from entropia.infrastructure.postgres.models import AuditEvent, OutboxEvent

pytestmark = pytest.mark.integration

PASSWORD = "correct-horse-battery"
BOOTSTRAP_EMAIL = "founder@example.com"


async def _bootstrap_events(session: AsyncSession) -> tuple[list[AuditEvent], list[OutboxEvent]]:
    audits = (
        (
            await session.execute(
                select(AuditEvent).where(AuditEvent.event_kind == "user.admin_bootstrapped")
            )
        )
        .scalars()
        .all()
    )
    outbox = (
        (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "admin_bootstrapped")
            )
        )
        .scalars()
        .all()
    )
    return list(audits), list(outbox)


async def test_env_unset_keeps_baseline_role(session: AsyncSession) -> None:
    result = await auth_cmd.sign_up(
        session,
        username="alice",
        password=PASSWORD,
        email=BOOTSTRAP_EMAIL,
        bootstrap_admin_email=None,
    )
    assert result["role"] == str(Role.USER)
    audits, outbox = await _bootstrap_events(session)
    assert audits == [] and outbox == []


async def test_matching_email_with_no_admin_provisions_admin(session: AsyncSession) -> None:
    result = await auth_cmd.sign_up(
        session,
        username="alice",
        password=PASSWORD,
        email=BOOTSTRAP_EMAIL,
        bootstrap_admin_email=BOOTSTRAP_EMAIL,
    )
    assert result["role"] == str(Role.ADMIN)

    audits, outbox = await _bootstrap_events(session)
    assert len(audits) == 1
    assert audits[0].target_entity_id == result["user_id"]
    assert audits[0].new_state == str(Role.ADMIN)
    assert len(outbox) == 1
    assert outbox[0].resource_id == result["user_id"]
    assert outbox[0].payload["audit_event_id"] == audits[0].event_id


async def test_existing_admin_fails_closed_to_baseline(session: AsyncSession) -> None:
    first = await auth_cmd.sign_up(
        session,
        username="root",
        password=PASSWORD,
        email=BOOTSTRAP_EMAIL,
        bootstrap_admin_email=BOOTSTRAP_EMAIL,
    )
    assert first["role"] == str(Role.ADMIN)

    # A later signup matching the (hypothetically re-used) bootstrap email must
    # NOT mint a second Admin while one is active.
    second = await auth_cmd.sign_up(
        session,
        username="latecomer",
        password=PASSWORD,
        email="other@example.com",
        bootstrap_admin_email="other@example.com",
    )
    assert second["role"] == str(Role.USER)

    audits, outbox = await _bootstrap_events(session)
    assert len(audits) == 1 and len(outbox) == 1  # only the first provisioning


async def test_non_matching_or_missing_email_keeps_baseline(session: AsyncSession) -> None:
    no_match = await auth_cmd.sign_up(
        session,
        username="bob",
        password=PASSWORD,
        email="bob@example.com",
        bootstrap_admin_email=BOOTSTRAP_EMAIL,
    )
    assert no_match["role"] == str(Role.USER)

    no_email = await auth_cmd.sign_up(
        session,
        username="carol",
        password=PASSWORD,
        email=None,
        bootstrap_admin_email=BOOTSTRAP_EMAIL,
    )
    assert no_email["role"] == str(Role.USER)

    audits, outbox = await _bootstrap_events(session)
    assert audits == [] and outbox == []


async def test_match_is_case_and_whitespace_normalized(session: AsyncSession) -> None:
    result = await auth_cmd.sign_up(
        session,
        username="alice",
        password=PASSWORD,
        email="  Founder@Example.COM ",
        bootstrap_admin_email=BOOTSTRAP_EMAIL,
    )
    assert result["role"] == str(Role.ADMIN)


async def test_settings_reads_bootstrap_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTROPIA_BOOTSTRAP_ADMIN_EMAIL", BOOTSTRAP_EMAIL)
    get_settings.cache_clear()
    try:
        assert get_settings().bootstrap_admin_email == BOOTSTRAP_EMAIL
    finally:
        get_settings.cache_clear()


async def test_route_passes_setting_through(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENTROPIA_BOOTSTRAP_ADMIN_EMAIL", BOOTSTRAP_EMAIL)
    get_settings.cache_clear()
    try:
        from starlette.requests import Request

        from entropia.apps.api.routes import auth as auth_routes

        request = Request(
            {"type": "http", "method": "POST", "path": "/api/v1/auth/signup", "headers": []}
        )
        body = auth_routes.SignUpRequest(
            username="founder", password=PASSWORD, email=BOOTSTRAP_EMAIL
        )
        response = await auth_routes.sign_up(body, request, session)
        assert response.role == str(Role.ADMIN)
    finally:
        get_settings.cache_clear()
