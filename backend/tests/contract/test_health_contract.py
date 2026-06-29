import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.contract
async def test_liveness_ok(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert "X-Request-Id" in resp.headers
    assert "X-Correlation-Id" in resp.headers


@pytest.mark.contract
async def test_meta_reports_version(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/api/v1/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Entropia V18"
    assert "version" in body


@pytest.mark.contract
async def test_unknown_route_uses_error_envelope(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
