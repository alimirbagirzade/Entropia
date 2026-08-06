"""ADIM 23 — production must not boot on the credentials published in this repo.

`.env.example` ships `OBJECT_STORAGE_SECRET_KEY=entropia-secret`,
`OBJECT_STORAGE_ACCESS_KEY=entropia` and a `entropia:entropia@` database URL, and
`docker-compose.yml` repeats every one of them as a `${VAR:-default}` fallback.
A production deployment that never set those variables therefore does not fail —
it comes up GREEN, with an artifact store and a database whose credentials are
readable by anyone who can read this repository. There is no signal anywhere,
because from the stack's point of view nothing is wrong.

These tests pin the startup refusal and, just as importantly, pin the CONSTANTS
to `.env.example` itself: if someone rotates the example values without updating
the check, the gate would quietly start passing on the new published defaults.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from entropia.config.settings import (
    _SHIPPED_DB_CREDENTIALS,
    _SHIPPED_OBJECT_ACCESS_KEY,
    _SHIPPED_OBJECT_SECRET_KEY,
    Settings,
)

_ENV_EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"

# A production Settings needs session auth (F-22) and explicit CORS origins
# (I-14); those validators are not what these tests are about, so every case
# starts from a base that satisfies them and varies only the credentials.
_PRODUCTION_BASE = {
    "ENTROPIA_ENV": "production",
    "AUTH_MODE": "session",
    "API_CORS_ORIGINS": "https://app.example.com",
    "OBJECT_STORAGE_ACCESS_KEY": "rotated-access-key",
    "OBJECT_STORAGE_SECRET_KEY": "rotated-secret-key",
    "DATABASE_URL": "postgresql+asyncpg://appuser:s3cr3t@db.internal:5432/entropia",
}


def _settings(**overrides: str) -> Settings:
    return Settings(**{**_PRODUCTION_BASE, **overrides})  # type: ignore[arg-type]


def _env_example_value(key: str) -> str:
    match = re.search(rf"^{re.escape(key)}=(.*)$", _ENV_EXAMPLE.read_text("utf-8"), re.MULTILINE)
    assert match, f"{key} not found in .env.example"
    return match.group(1).strip()


def test_rotated_credentials_start_normally() -> None:
    assert _settings().is_production is True


@pytest.mark.parametrize(
    ("override", "expected_name"),
    [
        ({"OBJECT_STORAGE_ACCESS_KEY": _SHIPPED_OBJECT_ACCESS_KEY}, "OBJECT_STORAGE_ACCESS_KEY"),
        ({"OBJECT_STORAGE_SECRET_KEY": _SHIPPED_OBJECT_SECRET_KEY}, "OBJECT_STORAGE_SECRET_KEY"),
        (
            {"DATABASE_URL": "postgresql+asyncpg://entropia:entropia@db.internal:5432/entropia"},
            "DATABASE_URL",
        ),
    ],
    ids=["object-access-key", "object-secret-key", "database-url"],
)
def test_each_shipped_default_fails_closed_in_production(
    override: dict[str, str], expected_name: str
) -> None:
    with pytest.raises(ValidationError) as excinfo:
        _settings(**override)
    assert expected_name in str(excinfo.value)


def test_the_error_names_every_offender_at_once() -> None:
    """One restart per secret is a bad way to learn you left three behind."""
    with pytest.raises(ValidationError) as excinfo:
        _settings(
            OBJECT_STORAGE_ACCESS_KEY=_SHIPPED_OBJECT_ACCESS_KEY,
            OBJECT_STORAGE_SECRET_KEY=_SHIPPED_OBJECT_SECRET_KEY,
            DATABASE_URL="postgresql+asyncpg://entropia:entropia@db.internal:5432/entropia",
        )
    message = str(excinfo.value)
    for name in ("OBJECT_STORAGE_ACCESS_KEY", "OBJECT_STORAGE_SECRET_KEY", "DATABASE_URL"):
        assert name in message


def test_a_changed_host_does_not_launder_the_published_password() -> None:
    """The DB check is a substring on the credential pair, not URL equality: an
    operator who pointed the URL at a real host while keeping `entropia:entropia`
    changed nothing that matters."""
    with pytest.raises(ValidationError):
        _settings(
            DATABASE_URL="postgresql+asyncpg://entropia:entropia@prod-db.eu-west-1:6543/entropia_prod"
        )


@pytest.mark.parametrize("environment", ["local", "staging"])
def test_defaults_remain_usable_outside_production(environment: str) -> None:
    """`make up` and the E2E stacks run on exactly these values on purpose.
    A gate that broke them would only teach people to unset ENTROPIA_ENV."""
    settings = Settings(  # type: ignore[call-arg]
        ENTROPIA_ENV=environment,
        AUTH_MODE="session",
        OBJECT_STORAGE_ACCESS_KEY=_SHIPPED_OBJECT_ACCESS_KEY,
        OBJECT_STORAGE_SECRET_KEY=_SHIPPED_OBJECT_SECRET_KEY,
        DATABASE_URL="postgresql+asyncpg://entropia:entropia@localhost:5432/entropia",
    )
    assert settings.is_production is False


def test_constants_match_env_example() -> None:
    """Rotating the example values without updating the check would leave the
    gate passing on whatever is newly published."""
    assert _env_example_value("OBJECT_STORAGE_ACCESS_KEY") == _SHIPPED_OBJECT_ACCESS_KEY
    assert _env_example_value("OBJECT_STORAGE_SECRET_KEY") == _SHIPPED_OBJECT_SECRET_KEY
    assert _SHIPPED_DB_CREDENTIALS in _env_example_value("DATABASE_URL")
