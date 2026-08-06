"""Finding O-22 — the metrics exposition is credentialed, not public.

Infra-free (httpx ASGI). ``GET /metrics`` publishes operational intelligence
(per-queue job depth, outbox lag, oldest RUNNING lease age), so an unauthenticated
scrape must be refused BEFORE any database work. Covered here: 401 without a
credential, 403 with the wrong one, 200 with the right one, the deliberate
local-profile opening when no token is configured, the production fail-closed when
it is missing, and the preserved rate-limit exemption.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.apps.api import hardening
from entropia.config import get_settings
from tests.production_profile import rotate_production_credentials

METRICS_PATH = "/api/v1/metrics"
TOKEN = "prom-scraper-secret"
GAUGE_MARKERS = ("entropia_jobs_depth", "entropia_outbox_lag_seconds", "entropia_http_requests")


@pytest.fixture(autouse=True)
def _isolated_settings():
    """Settings are a process-wide lru_cache: rebuild from the env for every test
    and drop the mutated instance afterwards (this fixture tears down LAST, after
    monkeypatch has restored the environment)."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def gated(monkeypatch):
    """Configure a metrics scraper token for the current test."""
    monkeypatch.setenv("ENTROPIA_METRICS_TOKEN", TOKEN)
    get_settings.cache_clear()
    assert get_settings().metrics_token == TOKEN


async def _scrape(app, headers: dict[str, str] | None = None):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.get(METRICS_PATH, headers=headers or {})


def _assert_no_exposition(body: str) -> None:
    for marker in GAUGE_MARKERS:
        assert marker not in body, f"refused scrape leaked {marker!r}"


@pytest.mark.contract
async def test_scrape_without_credential_is_401(app, gated) -> None:
    resp = await _scrape(app)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "METRICS_SCRAPE_UNAUTHORIZED"
    _assert_no_exposition(resp.text)


@pytest.mark.contract
async def test_scrape_with_wrong_credential_is_403(app, gated) -> None:
    """A presented-but-invalid credential is an authorization failure (403);
    an absent one is an authentication failure (401)."""
    resp = await _scrape(app, {"Authorization": "Bearer wrong-token"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "METRICS_SCRAPE_FORBIDDEN"
    _assert_no_exposition(resp.text)


@pytest.mark.contract
async def test_near_miss_credential_is_403(app, gated) -> None:
    """A token sharing the configured prefix is still refused (no prefix match)."""
    resp = await _scrape(app, {"Authorization": f"Bearer {TOKEN}x"})
    assert resp.status_code == 403
    _assert_no_exposition(resp.text)


@pytest.mark.contract
async def test_non_bearer_scheme_is_401(app, gated) -> None:
    """A non-Bearer Authorization header yields no credential at all -> 401."""
    resp = await _scrape(app, {"Authorization": f"Basic {TOKEN}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "METRICS_SCRAPE_UNAUTHORIZED"
    _assert_no_exposition(resp.text)


@pytest.mark.contract
async def test_scrape_with_configured_token_succeeds(app, gated) -> None:
    resp = await _scrape(app, {"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "# TYPE entropia_http_requests_total counter" in resp.text


@pytest.mark.contract
async def test_unconfigured_token_stays_open_in_local_profile(app) -> None:
    """Documented boundary: the default LOCAL profile keeps ``curl /metrics``
    working; the fail-closed line is production (next test)."""
    assert get_settings().metrics_token == ""
    resp = await _scrape(app)
    assert resp.status_code == 200
    assert "# TYPE entropia_http_requests_total counter" in resp.text


@pytest.mark.contract
async def test_unconfigured_token_is_fail_closed_in_production(app, monkeypatch) -> None:
    """A production deployment that forgot the credential publishes NOTHING."""
    monkeypatch.setenv("ENTROPIA_ENV", "production")
    monkeypatch.setenv("AUTH_MODE", "session")  # F-22: non-local forbids dev auth
    rotate_production_credentials(monkeypatch)  # ADIM 23: no shipped defaults
    monkeypatch.delenv("ENTROPIA_METRICS_TOKEN", raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.is_production and settings.metrics_token == ""

    resp = await _scrape(app)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "METRICS_SCRAPE_FORBIDDEN"
    _assert_no_exposition(resp.text)


@pytest.mark.contract
def test_metrics_keeps_its_rate_limit_exemption() -> None:
    """The gate must not be paid for by shedding monitoring under load: a
    rate-limited scrape would blind the operator exactly when it matters."""
    assert "/metrics" in hardening._EXEMPT_SUFFIXES
    assert "/health/live" in hardening._EXEMPT_SUFFIXES
    assert "/health/ready" in hardening._EXEMPT_SUFFIXES
