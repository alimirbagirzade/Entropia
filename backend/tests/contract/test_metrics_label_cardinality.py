"""Metric labels stay bounded no matter what the caller sends (ADIM 25).

Label cardinality is the failure mode that kills a Prometheus server rather than
merely misinforming it: one unbounded label turns a handful of series into one
per request, and the blast radius is the whole monitoring stack — including the
alerts for the incident that caused it.

``apps/api/hardening.py`` already labels the registry with the RESOLVED route
template and collapses unmatched paths to the literal ``"unmatched"``. This test
attacks that guarantee from the caller's side rather than asserting the
implementation: it drives real parametrized routes with distinct UUIDs and a
hostile 404 path, then proves the identifiers never reach a label.
"""

from __future__ import annotations

import re
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.infrastructure.observability import metrics as metrics_registry

#: Parametrized GET route suffixes, taken from docs/openapi.json (where the path
#: parameters are named `{run_id}`, `{result_id}`, `{task_id}`, `{artifact_id}` —
#: the placeholder below is this test's own, since the value is what matters).
#: Each is exercised with an id that exists nowhere, so the request fails early on
#: auth and the test needs no database: the label is written in the middleware's
#: `finally` regardless of how the request ended.
#:
#: The prefix comes from settings, not a literal. Hard-coding "/api/v1" made every
#: route 404 to "unmatched" under a non-default API_BASE_PATH, which would have
#: turned the cardinality proof into a test of nothing.
PARAMETRIZED_ROUTES = (
    "/backtest-runs/{id}",
    "/backtest-results/{id}",
    "/agent-tasks/{id}",
    "/analysis-artifacts/{id}",
)


def _base() -> str:
    from entropia.config import get_settings

    return get_settings().api_base_path


LABEL_VALUE = re.compile(r'path="([^"]*)"')
UUID_SHAPED = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


async def _drive(app, paths: list[str]) -> str:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        for path in paths:
            await client.get(path)
    return metrics_registry.render_process_metrics()


@pytest.mark.contract
async def test_resource_ids_never_reach_a_metric_label(app) -> None:
    metrics_registry.reset()
    ids = [str(uuid.uuid4()) for _ in PARAMETRIZED_ROUTES]
    paths = [
        f"{_base()}{route.format(id=value)}"
        for route, value in zip(PARAMETRIZED_ROUTES, ids, strict=True)
    ]

    body = await _drive(app, paths)

    for value in ids:
        assert value not in body, f"the id {value} leaked into the exposition"
    leaked = UUID_SHAPED.findall(body)
    assert not leaked, f"UUID-shaped label values present: {leaked}"


@pytest.mark.contract
async def test_many_ids_on_one_route_collapse_to_one_series(app) -> None:
    """The actual cardinality proof: N distinct ids must produce ONE path label."""
    metrics_registry.reset()
    route = PARAMETRIZED_ROUTES[0]

    body = await _drive(app, [f"{_base()}{route.format(id=str(uuid.uuid4()))}" for _ in range(25)])

    values = set(LABEL_VALUE.findall(body))
    assert len(values) == 1, f"25 ids produced {len(values)} path labels: {sorted(values)}"
    assert "{" in next(iter(values)), "the surviving label is not a route template"


@pytest.mark.contract
async def test_attacker_controlled_paths_all_collapse_to_unmatched(app) -> None:
    """A scanner walking a wordlist must add exactly one series, not one per probe."""
    metrics_registry.reset()
    probes = [f"/wp-admin/{uuid.uuid4()}" for _ in range(20)] + [
        "/../../etc/passwd",
        "/.env",
        f"{_base()}/nope",
    ]

    body = await _drive(app, probes)

    values = set(LABEL_VALUE.findall(body))
    assert values == {"unmatched"}, f"unmatched probes produced extra labels: {sorted(values)}"


METHOD_VALUE = re.compile(r'method="([^"]*)"')


@pytest.mark.contract
async def test_invented_http_methods_collapse_to_one_label(app) -> None:
    """The OTHER unbounded axis. `request.method` is an arbitrary wire token.

    h11 accepts any HTTP token as a method, so before this was clamped a scanner
    sending PROPFIND, EVIL0, EVIL1 ... minted one series per request — the exact
    hole the `path` guard was written to close, on the axis nobody was watching.
    Reproduced against the real app before the fix: six invented methods produced
    six `method="..."` label values.
    """
    metrics_registry.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        for index in range(10):
            await client.request(f"EVILMETHOD{index}", f"{_base()}/meta")
        await client.request("PROPFIND", f"{_base()}/meta")

    values = set(METHOD_VALUE.findall(metrics_registry.render_process_metrics()))
    assert values == {"other"}, f"invented methods leaked into labels: {sorted(values)}"


@pytest.mark.contract
async def test_real_methods_keep_their_own_label(app) -> None:
    """Clamping must not flatten the methods the API actually serves."""
    metrics_registry.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        await client.get(f"{_base()}/meta")
        await client.request("PROPFIND", f"{_base()}/meta")

    values = set(METHOD_VALUE.findall(metrics_registry.render_process_metrics()))
    assert values == {"GET", "other"}
