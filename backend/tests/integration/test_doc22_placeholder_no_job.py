"""Doc 22 audit control step — a PLACEHOLDER capability starts NOTHING (CR-09).

The command-level proof already lives in ``test_future_dev.py``. This file adds
the missing HTTP-level one: the real route surface (FastAPI route -> application
command -> repository) is exercised for BOTH operational POSTs while every
baseline capability is Placeholder, and the ``jobs`` table row count is compared
before and after. The response must be the doc 22 §7 CAPABILITY_NOT_ACTIVE
envelope and the count must not move (FD-02, FD-03, FD-12).

Auto-skips without PostgreSQL, like every integration test here.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.capability.enums import GRAPHIC_VIEW, CapabilityState
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AnalysisArtifact,
    Job,
    OutboxEvent,
    ViewDataset,
)
from entropia.infrastructure.postgres.repositories import capability as capability_repo

USER = Actor(
    principal_id="user_doc22",
    principal_type=PrincipalType.HUMAN,
    role=Role.USER,
    correlation_id="corr_doc22",
)


def _override(app, session) -> Iterator[None]:
    app.dependency_overrides[request_context] = lambda: RequestContext(session=session, actor=USER)
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


@pytest.fixture
def api(app, session):
    yield from _override(app, session)


async def test_placeholder_capability_starts_no_job_over_http(app, session, api) -> None:
    """FD-02/FD-03: the seeded baseline is Placeholder; both operational POSTs
    are refused with CAPABILITY_NOT_ACTIVE and the jobs table never grows."""
    await capability_repo.seed_baseline_capabilities(session)
    await session.commit()

    graphic_view = await capability_repo.get_capability_by_key(session, GRAPHIC_VIEW)
    assert graphic_view is not None
    assert graphic_view.lifecycle_state is CapabilityState.PLACEHOLDER

    jobs_before = await _count(session, Job)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        dataset_response = await client.post(
            "/api/v1/view-datasets/query",
            json={"source_manifest_refs": ["result_abc123"], "schema_version": "v1"},
            headers={"Idempotency-Key": "doc22-audit-dataset"},
        )
        artifact_response = await client.post(
            "/api/v1/analysis-artifacts",
            json={
                "artifact_type": "backtest_review",
                "input_manifest_refs": ["result_abc123"],
                "method_version": "review-v1",
            },
            headers={"Idempotency-Key": "doc22-audit-artifact"},
        )

    for response in (dataset_response, artifact_response):
        assert response.status_code == 403
        body = response.json()["error"]
        assert body["code"] == "CAPABILITY_NOT_ACTIVE"
        # doc 22 §7: the caller is told explicitly that nothing started.
        assert body["message"] == (
            "This feature is not active in the current environment. No operation was started."
        )
        assert body["retryable"] is False

    await session.rollback()
    assert await _count(session, Job) == jobs_before  # no job, not even a queued one
    assert await _count(session, ViewDataset) == 0
    assert await _count(session, AnalysisArtifact) == 0
    assert await _count(session, OutboxEvent) == 0


async def test_placeholder_graphic_view_overview_is_static_and_creates_nothing(
    app, session, api
) -> None:
    """FD-01/FD-03: the placeholder overview renders the six static doc 22 §4.1
    cards and the §7 placeholder copy — no dataset, no job, no fake progress."""
    await capability_repo.seed_baseline_capabilities(session)
    await session.commit()
    jobs_before = await _count(session, Job)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/api/v1/future-dev/graphic-view/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["lifecycle_state"] == "placeholder"
    assert body["is_operational"] is False
    assert len(body["cards"]) == 6
    # Every card is future-tense placeholder copy — never a rendered value.
    assert all(card["text"].startswith("Future:") for card in body["cards"])
    assert body["status_message"].startswith(
        "This capability is currently a controlled Future Dev placeholder."
    )

    await session.rollback()
    assert await _count(session, Job) == jobs_before
    assert await _count(session, ViewDataset) == 0
