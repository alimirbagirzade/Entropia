"""post-V1 — read-only first-Admin bootstrap status (TIER 2 provisioning
dashboard backend). Anonymous booleans-only signal driving the Provisioning
page: is the mechanism configured, and is the bootstrap window still open
(no active Admin yet) or already closed.

Auto-skips without PostgreSQL (session fixture). Proves:
- fresh DB, mechanism off -> {configured: False, active_admin_exists: False};
- fresh DB, mechanism on  -> {configured: True,  active_admin_exists: False}
  (the window is OPEN);
- after a bootstrap signup mints the first Admin -> active_admin_exists True
  (the window is CLOSED), independent of the configured flag;
- the route handler reads ENTROPIA_BOOTSTRAP_ADMIN_EMAIL from settings and
  returns booleans only.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import auth as auth_cmd
from entropia.config import get_settings

pytestmark = pytest.mark.integration

PASSWORD = "correct-horse-battery"
BOOTSTRAP_EMAIL = "founder@example.com"


async def test_unconfigured_fresh_db_reports_closed_and_off(session: AsyncSession) -> None:
    status = await auth_cmd.bootstrap_status(session, bootstrap_admin_email=None)
    assert status == {"bootstrap_configured": False, "active_admin_exists": False}


async def test_configured_fresh_db_window_open(session: AsyncSession) -> None:
    status = await auth_cmd.bootstrap_status(session, bootstrap_admin_email=BOOTSTRAP_EMAIL)
    assert status["bootstrap_configured"] is True
    assert status["active_admin_exists"] is False


async def test_window_closes_once_an_admin_exists(session: AsyncSession) -> None:
    # A bootstrap signup mints the first Admin (see test_auth_bootstrap_admin).
    provisioned = await auth_cmd.sign_up(
        session,
        username="founder",
        password=PASSWORD,
        email=BOOTSTRAP_EMAIL,
        bootstrap_admin_email=BOOTSTRAP_EMAIL,
    )
    assert provisioned["role"].lower().endswith("admin")

    # The configured flag is independent of the window: even with the env still
    # set, the window is now CLOSED because an active Admin exists.
    status = await auth_cmd.bootstrap_status(session, bootstrap_admin_email=BOOTSTRAP_EMAIL)
    assert status["bootstrap_configured"] is True
    assert status["active_admin_exists"] is True

    # And with the mechanism turned off the window is still CLOSED.
    off = await auth_cmd.bootstrap_status(session, bootstrap_admin_email=None)
    assert off == {"bootstrap_configured": False, "active_admin_exists": True}


async def test_route_reads_setting_and_returns_booleans(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ENTROPIA_BOOTSTRAP_ADMIN_EMAIL", BOOTSTRAP_EMAIL)
    get_settings.cache_clear()
    try:
        from entropia.apps.api.routes import auth as auth_routes

        response = await auth_routes.bootstrap_status(session)
        assert response.bootstrap_configured is True
        assert response.active_admin_exists is False
    finally:
        get_settings.cache_clear()
