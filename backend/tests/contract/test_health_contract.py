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
    body = resp.json()
    # A framework-raised 404 is the canonical envelope, never Starlette's bare
    # {"detail": ...} shape the frontend cannot parse into an ApiError.
    assert "detail" not in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"]
    assert body["error"]["details"] == []
    # Correlation identifiers are echoed into the envelope, not just the headers.
    assert body["error"]["request_id"] == resp.headers["X-Request-Id"]
    assert body["error"]["correlation_id"] == resp.headers["X-Correlation-Id"]


@pytest.mark.contract
async def test_method_not_allowed_uses_error_envelope(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        # /api/v1/meta is GET-only; POST triggers a framework 405.
        resp = await client.post("/api/v1/meta")
    assert resp.status_code == 405
    body = resp.json()
    assert "detail" not in body
    assert body["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert body["error"]["message"]
    # The Allow header the framework attaches is preserved through the envelope.
    assert "GET" in resp.headers.get("Allow", "")
