"""Stage 8b — API hardening contract: security headers, metrics, rate limiting.

Infra-free (httpx ASGI). The default app ships security headers and the
per-process metrics endpoint; rate limiting is deployment-opt-in
(RATE_LIMIT_ENABLED) and is exercised here on a dedicated app instance with a
tiny window and a frozen clock (no minute-boundary flake).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.config import get_settings
from entropia.infrastructure.observability import metrics as metrics_registry


@pytest.mark.contract
async def test_security_headers_ride_every_response(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["Content-Security-Policy"] == "default-src 'none'"
    # HSTS is production-only (TLS terminates in front of the process).
    assert "Strict-Transport-Security" not in resp.headers


@pytest.mark.contract
async def test_metrics_exposition_reports_golden_signals(app) -> None:
    metrics_registry.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        await client.get("/api/v1/meta")
        await client.get("/wp-admin/definitely-not-a-route")  # 404 scan
        resp = await client.get("/api/v1/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    body = resp.text
    assert "# TYPE entropia_http_requests_total counter" in body
    import re

    # The path label is the resolved route template (low cardinality); the
    # framework reports it without the include-time prefix.
    assert re.search(
        r'entropia_http_requests_total\{method="GET",path="[^"]*meta",status="200"\} 1', body
    )
    assert "# TYPE entropia_http_request_duration_seconds histogram" in body
    assert "entropia_http_requests_in_flight" in body
    # Unmatched paths never label the registry (cardinality stays bounded).
    assert 'path="unmatched",status="404"' in body
    assert "wp-admin" not in body
    # Operational gauges degrade gracefully: either real gauges or the
    # unavailable marker — the scrape itself never fails.
    assert ("entropia_jobs_depth" in body) or ("operational gauges unavailable" in body)


def _rate_limited_app(monkeypatch: pytest.MonkeyPatch):
    """A dedicated app instance with rate limiting ON, tiny budgets, frozen clock."""
    import time as real_time

    import entropia.apps.api.hardening as hardening

    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_ANON_PER_MINUTE", "2")
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "3")
    monkeypatch.setenv("RATE_LIMIT_WRITE_PER_MINUTE", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(
        hardening,
        "time",
        SimpleNamespace(time=lambda: 1_000_000_000, perf_counter=real_time.perf_counter),
    )
    from entropia.apps.api.main import create_app

    return create_app()


@pytest.mark.contract
async def test_rate_limit_sheds_load_with_headers_and_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limited_app = _rate_limited_app(monkeypatch)
    try:
        transport = ASGITransport(app=limited_app)
        async with AsyncClient(transport=transport, base_url="http://t") as client:
            first = await client.get("/api/v1/meta")
            second = await client.get("/api/v1/meta")
            third = await client.get("/api/v1/meta")

            assert first.status_code == 200
            assert first.headers["X-RateLimit-Limit"] == "2"
            assert first.headers["X-RateLimit-Remaining"] == "1"
            assert second.status_code == 200
            assert second.headers["X-RateLimit-Remaining"] == "0"

            assert third.status_code == 429
            assert "Retry-After" in third.headers
            body = third.json()
            assert body["error"]["code"] == "RATE_LIMITED"

            # An authenticated principal has its own (larger) budget.
            authed = await client.get("/api/v1/meta", headers={"X-Actor-Id": "user_1"})
            assert authed.status_code == 200
            assert authed.headers["X-RateLimit-Limit"] == "3"

            # Probes are exempt: never shed health traffic.
            for _ in range(5):
                probe = await client.get("/api/v1/health/live")
                assert probe.status_code == 200
                assert "X-RateLimit-Limit" not in probe.headers
    finally:
        get_settings.cache_clear()


@pytest.mark.contract
async def test_default_app_has_rate_limiting_off(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/api/v1/meta")
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" not in resp.headers
