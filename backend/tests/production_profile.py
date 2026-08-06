"""Building a *production* Settings in a test, without every test having to know
what production requires.

`Settings` refuses to construct under `ENTROPIA_ENV=production` unless three
separate things are right: `AUTH_MODE=session` (F-22), an explicit non-wildcard
`API_CORS_ORIGINS` (I-14), and — since ADIM 23 — credentials that are not the
ones published in `.env.example`
(`config/settings.py::_reject_shipped_default_credentials_in_production`).

Each of those gates is worth having. Together they create a trap: a test that
wants a production profile for a reason having NOTHING to do with credentials —
metrics scraping, header impersonation, CORS parsing — must still supply them,
and discovers this only when a validator it never heard of fails. Three tests
broke that way when the credential gate landed.

So the knowledge lives here once. A test that needs a realistic production
profile takes it from this module and stays about its own subject.
"""

from __future__ import annotations

import pytest

# Deliberately nothing like the `.env.example` values — that is the whole point.
PRODUCTION_CREDENTIALS: dict[str, str] = {
    "OBJECT_STORAGE_ACCESS_KEY": "rotated-access-key",
    "OBJECT_STORAGE_SECRET_KEY": "rotated-secret-key",
    "DATABASE_URL": "postgresql+asyncpg://appuser:rotated-password@db.internal:5432/entropia",
}


def rotate_production_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the credential env vars at non-published values.

    For tests that reach production via `monkeypatch.setenv("ENTROPIA_ENV", ...)`
    plus `get_settings.cache_clear()`. Tests that construct `Settings(...)`
    directly should splat `**PRODUCTION_CREDENTIALS` into the call instead.
    """
    for key, value in PRODUCTION_CREDENTIALS.items():
        monkeypatch.setenv(key, value)
