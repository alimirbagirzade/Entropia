import pytest
from pydantic import ValidationError

from entropia.config import Settings


def test_cors_origins_parsed_to_list() -> None:
    s = Settings(API_CORS_ORIGINS="http://a.test, http://b.test")
    assert s.cors_origin_list == ["http://a.test", "http://b.test"]


def test_sync_database_url_strips_async_driver() -> None:
    s = Settings(DATABASE_URL="postgresql+asyncpg://u:p@h:5432/db")
    assert "asyncpg" not in s.sync_database_url
    assert s.sync_database_url.startswith("postgresql")


# ---- F-22: AUTH_MODE=dev restricted to the local dev profile ----


def test_local_dev_profile_allows_dev_auth_mode() -> None:
    s = Settings(ENTROPIA_ENV="local", AUTH_MODE="dev")
    assert s.environment == "local"
    assert s.auth_mode == "dev"


@pytest.mark.parametrize("env", ["local", "staging", "production"])
def test_session_auth_mode_allowed_in_every_environment(env: str) -> None:
    s = Settings(ENTROPIA_ENV=env, AUTH_MODE="session")
    assert s.auth_mode == "session"


@pytest.mark.parametrize("env", ["staging", "production"])
def test_dev_auth_mode_rejected_outside_local_fails_closed(env: str) -> None:
    """The non-local profiles MUST NOT be able to trust a client-supplied
    X-Actor-Id header for actor impersonation — the app refuses to even
    construct its settings (fail-closed at startup, not at request time)."""
    with pytest.raises(ValidationError, match="AUTH_MODE=dev is restricted to ENTROPIA_ENV=local"):
        Settings(ENTROPIA_ENV=env, AUTH_MODE="dev")
