"""End-to-end proof that typing the ESP / Library / Gateway bodies drops NO field.

``tests/contract/test_typed_contract_no_field_drop.py`` pins each model against the pure
serializer that feeds it. This module closes the other half — the command envelopes, which
only exist inside a transaction — without ever hand-writing the expectation:

    body   = await client.post(url, headers={"Idempotency-Key": "k"})   # AFTER the model
    stored = idempotency_keys[k].response_ref                           # BEFORE the model

``run_idempotent`` persists the command's return value VERBATIM, so the stored envelope is
literally the dict the route handed to FastAPI. ``body == stored`` therefore proves both
directions at once: the model drops no key and invents none. It also settles the replay
question by construction — a replay returns that same stored dict through that same DTO —
and the replay is additionally driven end-to-end where the command's pre-body guards allow
a second call (a ``deprecate`` cannot be replayed over HTTP at all: its lifecycle guard sits
OUTSIDE ``run_idempotent``, so the second call is a 409 before idempotency is consulted).

Reads have no stored envelope, so they compare the HTTP body against the query function's
own unfiltered return.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.application.commands import esp as esp_cmd
from entropia.application.jobs import agent_tools
from entropia.application.queries import agent_tool_gateway as tg_query
from entropia.application.queries import esp as esp_query
from entropia.application.queries import library as library_query
from entropia.apps.api.deps import RequestContext, request_context
from entropia.apps.api.routes import library as library_routes
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskPriority,
    AgentTaskStatus,
    RuntimeMode,
    RuntimeStatus,
)
from entropia.domain.esp.enums import RuntimeAdapter
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.package.catalog import parse_catalog_filters
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import AgentRuntime, IdempotencyKey, Principal
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.pagination import PageParams
from tests.integration.test_library_validation_run import _library_head
from tests.integration.test_validation_evidence import OWNER as CP_OWNER

pytestmark = pytest.mark.integration

_API = "/api/v1"

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
AGENT = Actor(principal_id="agent_alpha", principal_type=PrincipalType.AGENT, role=None)

_SMA_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}
_EVIDENCE = {
    "test_vectors": [
        {
            "name": "sma_len3",
            "length": 3,
            "close": [1, 2, 3, 4, 5],
            "expected": [None, None, 2, 3, 4],
        }
    ]
}


def _override(app, session, actor: Actor = OWNER) -> Iterator[None]:
    app.dependency_overrides[request_context] = lambda: RequestContext(session=session, actor=actor)
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


def _client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _stored_envelope(session, key: str) -> dict[str, Any]:
    """The command's return value as ``run_idempotent`` persisted it — i.e. the exact dict
    the route returned BEFORE ``response_model`` filtered it."""
    row = await session.get(IdempotencyKey, key)
    assert row is not None, f"no idempotency record for {key!r}"
    assert row.response_ref is not None
    return dict(row.response_ref)


async def _seed_principals(session) -> None:
    for pid, kind in (
        ("user_admin", PrincipalType.HUMAN),
        ("user_1", PrincipalType.HUMAN),
        ("agent_alpha", PrincipalType.AGENT),
    ):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=kind))
    await session.flush()


async def _create_esp(session, *, key: str = "ta.sma") -> dict[str, Any]:
    return await esp_cmd.create_esp_package(
        session,
        OWNER,
        canonical_key=key,
        signature=_SMA_SIG,
        runtime_adapter=RuntimeAdapter.PINE_V5,
        input_contract={"resolver_key": key},
        output_contract={"return": "series"},
        evidence=_EVIDENCE,
        visibility_scope=VisibilityScope.PRIVATE,
    )


async def _make_package(session, *, name: str = "Momentum") -> Any:
    root, _detail, _revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        package_kind=PackageKind.INDICATOR,
        input_contract={"name": name, "market": "btcusdt", "timeframe": "15m"},
        output_contract={"output_kinds": ["directional_signal"]},
        dependency_snapshot={"resolved": []},
        # A pinned family snapshot is what makes `rationale_family` non-null on BOTH
        # projections; without it the nested family models are never applied and their
        # coverage would be vacuous. The family root does not exist, which exercises the
        # `family_active: False` branch of `_live_family` — same key set, either branch.
        rationale_family_snapshot={"rationale_family_id": "rf_x", "display_name": "Momentum"},
        visibility_scope=VisibilityScope.PRIVATE,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.DRAFT,
    )
    await session.flush()
    return root


# ---------------------------------------------------------------------------
# ESP — commands (first call direct, HTTP replays it)
# ---------------------------------------------------------------------------


async def test_esp_create_body_matches_the_stored_envelope_and_replays(app, session) -> None:
    await _seed_principals(session)
    await session.commit()
    payload = {
        "canonical_key": "ta.ema",
        "signature": _SMA_SIG,
        "runtime_adapter": "pine_v5",
        "input_contract": {"resolver_key": "ta.ema"},
        "output_contract": {"return": "series"},
        "evidence": _EVIDENCE,
        "visibility_scope": "private",
    }

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            first = await client.post(
                f"{_API}/embedded-system-packages",
                json=payload,
                headers={"Idempotency-Key": "esp-create-1"},
            )
            await session.commit()
            replay = await client.post(
                f"{_API}/embedded-system-packages",
                json=payload,
                headers={"Idempotency-Key": "esp-create-1"},
            )
    finally:
        next(gen, None)

    assert first.status_code == 201
    assert first.json() == await _stored_envelope(session, "esp-create-1")
    assert replay.status_code == 201
    assert replay.json() == first.json()


async def test_esp_validation_run_body_matches_the_stored_envelope_and_replays(
    app, session
) -> None:
    await _seed_principals(session)
    created = await _create_esp(session)
    await session.commit()

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            first = await client.post(
                f"{_API}/embedded-system-packages/{created['entity_id']}/validate",
                json={"revision_id": created["revision_id"]},
                headers={"Idempotency-Key": "esp-validate-1"},
            )
            await session.commit()
            replay = await client.post(
                f"{_API}/embedded-system-packages/{created['entity_id']}/validate",
                json={"revision_id": created["revision_id"]},
                headers={"Idempotency-Key": "esp-validate-1"},
            )
    finally:
        next(gen, None)

    assert first.status_code == 200
    stored = await _stored_envelope(session, "esp-validate-1")
    assert first.json() == stored
    assert replay.json() == first.json()
    # The per-check LIST survives verbatim — it is not the stored dict envelope that the
    # DETAIL read exposes under the same name.
    assert [c["name"] for c in first.json()["checks"]] == [
        "contract_schema",
        "test_vectors",
        "timing_integrity",
    ]


async def test_esp_activate_and_deprecate_bodies_match_their_stored_envelopes(app, session) -> None:
    await _seed_principals(session)
    created = await _create_esp(session)
    await esp_cmd.run_resolver_validation(
        session, OWNER, entity_id=created["entity_id"], revision_id=created["revision_id"]
    )
    await session.commit()

    gen = _override(app, session, actor=ADMIN)
    next(gen)
    try:
        async with _client(app) as client:
            act = await client.post(
                f"{_API}/embedded-system-packages/{created['entity_id']}/activate",
                json={
                    "revision_id": created["revision_id"],
                    "canonical_key": created["canonical_key"],
                },
                headers={"Idempotency-Key": "esp-activate-1"},
            )
            await session.commit()
            dep = await client.post(
                f"{_API}/embedded-system-packages/{created['entity_id']}/deprecate",
                json={"canonical_key": created["canonical_key"], "reason": "superseded"},
                headers={"Idempotency-Key": "esp-deprecate-1"},
            )
            await session.commit()
    finally:
        next(gen, None)

    assert act.status_code == 200
    assert act.json() == await _stored_envelope(session, "esp-activate-1")
    assert dep.status_code == 200
    assert dep.json() == await _stored_envelope(session, "esp-deprecate-1")
    # Deprecate carries `replacement_revision_id` and NO `revision_id`; activate is the
    # mirror image. Keeping the two models separate is what preserves that asymmetry.
    assert "revision_id" not in dep.json()
    assert dep.json()["replacement_revision_id"] is None
    assert "replacement_revision_id" not in act.json()
    assert act.json()["trust_state"] == "trusted_active"
    assert dep.json()["trust_state"] == "deprecated"


# ---------------------------------------------------------------------------
# ESP — reads
# ---------------------------------------------------------------------------


async def _activated_esp(session) -> dict[str, Any]:
    created = await _create_esp(session)
    await esp_cmd.run_resolver_validation(
        session, OWNER, entity_id=created["entity_id"], revision_id=created["revision_id"]
    )
    await esp_cmd.activate_resolver(
        session,
        ADMIN,
        entity_id=created["entity_id"],
        revision_id=created["revision_id"],
        canonical_key=created["canonical_key"],
    )
    await session.flush()
    return created


async def test_esp_detail_and_listing_serve_the_unfiltered_projection(app, session) -> None:
    await _seed_principals(session)
    created = await _activated_esp(session)
    await session.commit()

    raw_detail = await esp_query.get_esp_detail(session, OWNER, entity_id=created["entity_id"])
    raw_page = await esp_query.list_embedded_system_packages(
        session, OWNER, PageParams(cursor=None, limit=20)
    )

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            detail = await client.get(f"{_API}/embedded-system-packages/{created['entity_id']}")
            page = await client.get(f"{_API}/embedded-system-packages")
    finally:
        next(gen, None)

    assert detail.status_code == 200
    assert detail.json() == raw_detail
    # The nested registry block is the FULL row — it carries the OCC token the lifecycle
    # actions need, so a truncated nested model would break activate/deprecate.
    assert (
        detail.json()["registry"]["registry_version"] == raw_detail["registry"]["registry_version"]
    )
    assert detail.json()["registry"]["visibility_scope"] is None
    assert detail.json()["contract"]["signature"] == _SMA_SIG
    assert (
        detail.json()["latest_validation_run"]["checks"]
        == raw_detail["latest_validation_run"]["checks"]
    )
    assert detail.headers["ETag"] == f'"rv-{raw_detail["row_version"]}"'

    assert page.status_code == 200
    assert page.json() == raw_page
    assert page.json()["data"][0]["visibility_scope"] is not None


async def test_esp_resolve_serves_the_unfiltered_projection(app, session) -> None:
    await _seed_principals(session)
    created = await _activated_esp(session)
    await session.commit()
    parsed_call = {"key": created["canonical_key"], "signature": _SMA_SIG}
    raw = await esp_query.resolve_embedded_dependency(
        session, parsed_call=parsed_call, target_runtime=RuntimeAdapter.PINE_V5
    )

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            resp = await client.post(
                f"{_API}/embedded-system-packages/resolve",
                json={"parsed_call": parsed_call, "target_runtime": "pine_v5"},
            )
    finally:
        next(gen, None)

    assert resp.status_code == 200
    assert resp.json() == raw
    assert resp.json()["resolved"] is True
    assert resp.json()["signature"] == _SMA_SIG


async def test_a_resolve_failure_still_returns_the_untouched_error_envelope(app, session) -> None:
    """Typing the SUCCESS body must not reroute the error path: a non-resolvable call
    still renders ``shared/responses.py::ErrorBody``, not a validation error about the
    response model."""
    await _seed_principals(session)
    await session.commit()

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            resp = await client.post(
                f"{_API}/embedded-system-packages/resolve",
                json={"parsed_call": {"key": "ta.nope"}, "target_runtime": "pine_v5"},
            )
    finally:
        next(gen, None)

    assert resp.status_code == 404
    body = resp.json()["error"]
    assert body["code"] == "RESOLVER_NOT_RESOLVED"
    assert {"code", "message", "details", "request_id", "correlation_id"} <= set(body)
    assert {"category", "retryable", "suggested_action", "remediation"} <= set(body)


# ---------------------------------------------------------------------------
# Library — commands and reads
# ---------------------------------------------------------------------------


async def test_library_derive_and_revision_bodies_match_their_stored_envelopes(
    app, session
) -> None:
    await _seed_principals(session)
    root = await _make_package(session)
    head = root.current_revision_id
    await session.commit()

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            derived = await client.post(
                f"{_API}/library/{root.entity_id}/derive",
                json={"source_revision_id": head, "name": "Momentum copy"},
                headers={"Idempotency-Key": "lib-derive-1"},
            )
            await session.commit()
            replay = await client.post(
                f"{_API}/library/{root.entity_id}/derive",
                json={"source_revision_id": head, "name": "Momentum copy"},
                headers={"Idempotency-Key": "lib-derive-1"},
            )
            revised = await client.post(
                f"{_API}/library/{root.entity_id}/revisions",
                json={"expected_head_revision_id": head, "change_note": "tweak"},
                headers={"Idempotency-Key": "lib-revision-1"},
            )
            await session.commit()
    finally:
        next(gen, None)

    assert derived.status_code == 201
    assert derived.json() == await _stored_envelope(session, "lib-derive-1")
    assert replay.status_code == 201
    assert replay.json() == derived.json()
    # The derive envelope names BOTH roots — the new one and the source.
    assert derived.json()["source_entity_id"] == root.entity_id
    assert derived.json()["entity_id"] != root.entity_id

    assert revised.status_code == 201
    assert revised.json() == await _stored_envelope(session, "lib-revision-1")
    assert revised.json()["base_revision_id"] == head
    assert revised.json()["current_revision_id"] == revised.json()["revision_id"]


async def test_library_approval_flow_bodies_match_their_stored_envelopes(app, session) -> None:
    await _seed_principals(session)
    root = await _make_package(session)
    head = root.current_revision_id
    await session.commit()

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            req = await client.post(
                f"{_API}/library/{root.entity_id}/request-approval",
                json={"revision_id": head, "expected_head_revision_id": head},
                headers={"Idempotency-Key": "lib-req-approval-1"},
            )
            await session.commit()
    finally:
        next(gen, None)
    assert req.status_code == 200, req.text
    assert req.json() == await _stored_envelope(session, "lib-req-approval-1")
    assert req.json()["approval_state"] == "approval_requested"

    gen = _override(app, session, actor=ADMIN)
    next(gen)
    try:
        async with _client(app) as client:
            approved = await client.post(
                f"{_API}/library/{root.entity_id}/approve",
                json={"revision_id": head, "expected_head_revision_id": head},
                headers={"Idempotency-Key": "lib-approve-1"},
            )
            await session.commit()
            replay = await client.post(
                f"{_API}/library/{root.entity_id}/approve",
                json={"revision_id": head, "expected_head_revision_id": head},
                headers={"Idempotency-Key": "lib-approve-1"},
            )
    finally:
        next(gen, None)
    assert approved.status_code == 200, approved.text
    assert approved.json() == await _stored_envelope(session, "lib-approve-1")
    assert approved.json()["visibility_scope"] == "published"
    assert replay.json() == approved.json()


async def test_library_deprecate_body_matches_its_stored_envelope(app, session) -> None:
    await _seed_principals(session)
    root = await _make_package(session)
    await session.commit()

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            resp = await client.post(
                f"{_API}/library/{root.entity_id}/deprecate",
                json={"note": "eol"},
                headers={"Idempotency-Key": "lib-deprecate-1"},
            )
            await session.commit()
    finally:
        next(gen, None)

    assert resp.status_code == 200
    assert resp.json() == await _stored_envelope(session, "lib-deprecate-1")
    assert resp.json()["lifecycle_state"] == "deprecated"


async def test_library_export_body_matches_its_stored_envelope_and_replays(app, session) -> None:
    await _seed_principals(session)
    root = await _make_package(session)
    head = root.current_revision_id
    await session.commit()

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            first = await client.post(
                f"{_API}/library/{root.entity_id}/export",
                json={"revision_id": head},
                headers={"Idempotency-Key": "lib-export-1"},
            )
            await session.commit()
            replay = await client.post(
                f"{_API}/library/{root.entity_id}/export",
                json={"revision_id": head},
                headers={"Idempotency-Key": "lib-export-1"},
            )
    finally:
        next(gen, None)

    assert first.status_code == 200, first.text
    stored = await _stored_envelope(session, "lib-export-1")
    # The manifest is an OPEN artifact round-tripped into POST /package-imports — every one
    # of its keys must survive the envelope model byte-for-byte.
    assert first.json() == stored
    assert first.json()["manifest"] == stored["manifest"]
    assert first.json()["export_schema_version"] == 2
    assert replay.json() == first.json()


async def test_a_pre_g02_export_record_still_replays_under_the_strict_model(app, session) -> None:
    """Old fixture compatibility: a v1 idempotency record stores only four keys.

    ``_with_export_envelope_defaults`` back-fills ``export_schema_version`` and
    ``registry_observation`` before the envelope is returned; without it the now-strict
    ``PackageExportResponse`` would turn a legacy replay into a 500.
    """
    await _seed_principals(session)
    root = await _make_package(session)
    head = root.current_revision_id
    await session.commit()

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            fresh = await client.post(
                f"{_API}/library/{root.entity_id}/export",
                json={"revision_id": head},
                headers={"Idempotency-Key": "lib-export-legacy"},
            )
            await session.commit()

            # Rewrite the stored envelope back to its pre-G-02 (schema v1) shape.
            row = await session.get(IdempotencyKey, "lib-export-legacy")
            assert row is not None
            legacy = {
                k: fresh.json()[k]
                for k in ("entity_id", "revision_id", "manifest_hash", "manifest")
            }
            row.response_ref = legacy
            await session.commit()

            resp = await client.post(
                f"{_API}/library/{root.entity_id}/export",
                json={"revision_id": head},
                headers={"Idempotency-Key": "lib-export-legacy"},
            )
    finally:
        next(gen, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["export_schema_version"] == 1
    assert body["registry_observation"] is None
    assert body["manifest"] == legacy["manifest"]
    assert body["manifest_hash"] == legacy["manifest_hash"]


async def test_library_detail_and_listing_serve_the_unfiltered_projection(app, session) -> None:
    await _seed_principals(session)
    root = await _make_package(session)
    await session.commit()

    raw_detail = await library_query.get_package_detail(session, OWNER, entity_id=root.entity_id)
    raw_page = await library_query.list_packages(
        session, OWNER, PageParams(cursor=None, limit=20), filters=parse_catalog_filters()
    )

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as client:
            detail = await client.get(f"{_API}/library/{root.entity_id}")
            page = await client.get(f"{_API}/library")
    finally:
        next(gen, None)

    assert detail.status_code == 200
    assert detail.json() == raw_detail
    # All eleven permission flags and all six performance metrics reach the client: the UI
    # early-returns on each flag, so a dropped one silently hides an action.
    assert detail.json()["permissions"] == raw_detail["permissions"]
    assert detail.json()["performance"] == raw_detail["performance"]
    assert detail.json()["input_contract"] == raw_detail["input_contract"]
    assert detail.headers["ETag"] == f'"rv-{raw_detail["row_version"]}"'
    # The family reference is the one field whose shape DIFFERS between the two
    # projections, so both nested models have to be exercised, not just declared.
    assert detail.json()["rationale_family"] == {
        "id": "rf_x",
        "name": "Momentum",
        "pinned_name": "Momentum",
        "family_active": False,
    }

    assert page.status_code == 200
    assert page.json() == raw_page
    assert page.json()["data"][0]["rationale_family"] == {"id": "rf_x", "name": "Momentum"}


# ---------------------------------------------------------------------------
# Agent Tool Gateway — history reads
# ---------------------------------------------------------------------------


async def _seed_agent(session) -> Any:
    session.add(
        AgentRuntime(
            agent_id=ALPHA_AGENT_ID,
            mode=RuntimeMode.CONTINUOUS,
            status=RuntimeStatus.ACTIVE,
            row_version=1,
        )
    )
    await session.flush()
    return await al_repo.create_task(
        session,
        agent_id=ALPHA_AGENT_ID,
        task_type="research",
        title="Active research",
        source="autonomous",
        priority=AgentTaskPriority.AUTONOMOUS,
        status=AgentTaskStatus.RUNNING,
    )


async def test_tool_call_history_serves_the_unfiltered_projection(app, session) -> None:
    await _seed_principals(session)
    task = await _seed_agent(session)
    dispatched = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="artifact.create",
        policy_scope="research",
        task_id=task.task_id,
        checkpoint_id="ckpt_x",
        input_manifest_id="man_x",
        idempotency_key="tool-1",
        request={"title": "Funding edge", "mechanism": "carry"},
    )
    await session.commit()
    call_id = dispatched["tool_call_id"]

    raw_page = await tg_query.list_task_tool_calls(session, ADMIN, task_id=task.task_id)
    raw_detail = await tg_query.get_tool_call(session, ADMIN, tool_call_id=call_id)

    gen = _override(app, session, actor=ADMIN)
    next(gen)
    try:
        async with _client(app) as client:
            page = await client.get(f"{_API}/agent-tasks/{task.task_id}/tool-calls")
            detail = await client.get(f"{_API}/agent-tool-calls/{call_id}")
    finally:
        next(gen, None)

    assert page.status_code == 200
    assert page.json() == raw_page
    assert detail.status_code == 200
    assert detail.json() == raw_detail
    # The per-tool payloads pass through untouched — the gateway envelope is typed, the
    # tool's own result is not.
    assert detail.json()["request"] == {"title": "Funding edge", "mechanism": "carry"}
    assert detail.json()["response_ref"] == raw_detail["response_ref"]


async def test_a_rejected_tool_call_survives_the_typed_detail_model(app, session) -> None:
    """A governance denial writes a gateway-authored ``response_ref``
    (``{status, reason_code, reason}``) and a ``failure_code`` / ``failure_message``.
    The typed detail must render that shape as faithfully as a success payload — the
    open ``response_ref`` is exactly what makes both fit one model."""
    await _seed_principals(session)
    task = await _seed_agent(session)
    rejected = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="artifact.create",
        # `artifact.create` declares the RESEARCH scope only. The scope gate runs inside
        # the gateway's try-block, so the denial is RECORDED as a terminal rejection with
        # a gateway-authored `response_ref` rather than escaping uncaptured.
        policy_scope="observation",
        task_id=task.task_id,
        idempotency_key="tool-rejected",
        request={"title": "Blocked"},
    )
    await session.commit()
    assert rejected["status"] == "rejected"

    raw = await tg_query.get_tool_call(session, ADMIN, tool_call_id=rejected["tool_call_id"])

    gen = _override(app, session, actor=ADMIN)
    next(gen)
    try:
        async with _client(app) as client:
            detail = await client.get(f"{_API}/agent-tool-calls/{rejected['tool_call_id']}")
    finally:
        next(gen, None)

    assert detail.status_code == 200
    assert detail.json() == raw
    body = detail.json()
    assert body["status"] == "rejected"
    assert body["failure_code"] == raw["failure_code"]
    assert body["response_ref"]["reason_code"] == raw["response_ref"]["reason_code"]
    assert "reason" in body["response_ref"]


# ---------------------------------------------------------------------------
# The two surfaces whose envelope is NOT stored by run_idempotent
# ---------------------------------------------------------------------------


@pytest.fixture
def _no_broker(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record the durable hand-off instead of performing it (no broker in CI)."""
    dispatched: list[str] = []
    monkeypatch.setattr(library_routes, "dispatch_create_package_job", dispatched.append)
    return dispatched


async def test_the_queued_validation_envelope_is_not_filtered_by_its_model(
    app, session, monkeypatch: pytest.MonkeyPatch, _no_broker: list[str]
) -> None:
    """`request_package_validation` is NOT wrapped in ``run_idempotent`` — the outer
    envelope is re-projected on every call, so there is no stored copy to compare against.

    Spying on the command is what makes the comparison real: ``captured`` is the dict the
    handler returned, ``resp.json()`` is what survived ``response_model``. Pinning the body
    against a hand-written key set instead (as the pre-existing route test does) would agree
    with the model by construction and stay green if the command grew a ninth key.
    """
    entity_id, revision_id = await _library_head(session)
    captured: list[dict[str, Any]] = []
    original = library_routes.pkg_cmd.request_package_validation

    async def _spy(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = await original(*args, **kwargs)
        captured.append(dict(result))
        return result

    monkeypatch.setattr(library_routes.pkg_cmd, "request_package_validation", _spy)

    gen = _override(app, session, actor=CP_OWNER)
    next(gen)
    try:
        async with _client(app) as client:
            resp = await client.post(
                f"{_API}/library/{entity_id}/validation-runs",
                json={"revision_id": revision_id, "expected_head_revision_id": revision_id},
                headers={"Idempotency-Key": "typed-val-1"},
            )
    finally:
        next(gen, None)
    await session.commit()

    assert resp.status_code == 201, resp.text
    assert len(captured) == 1
    assert resp.json() == captured[0]
    # The two planes stay distinct on the wire.
    assert resp.json()["status"] == "queued"
    assert resp.json()["state"] == "validation_running"
    # The broker hand-off still runs BEFORE serialization, off the raw dict.
    assert _no_broker == [captured[0]["job_id"]]


async def test_the_detail_provenance_block_survives_its_nested_models(app, session) -> None:
    """A package built through the CreatePackage plane carries a non-null ``provenance``.

    The plain ``_make_package`` fixture has no originating request, so ``provenance`` is
    ``null`` there and ``PackageProvenance`` / ``PackageProvenanceScan`` are never applied —
    declared but unexercised. This drives the populated branch.
    """
    entity_id, _revision_id = await _library_head(session)
    raw = await library_query.get_package_detail(session, CP_OWNER, entity_id=entity_id)
    assert raw["provenance"] is not None, "fixture no longer produces a provenance block"

    gen = _override(app, session, actor=CP_OWNER)
    next(gen)
    try:
        async with _client(app) as client:
            detail = await client.get(f"{_API}/library/{entity_id}")
    finally:
        next(gen, None)

    assert detail.status_code == 200, detail.text
    assert detail.json() == raw
    provenance = detail.json()["provenance"]
    assert set(provenance) == set(raw["provenance"])
    if provenance["scan"] is not None:
        assert set(provenance["scan"]) == set(raw["provenance"]["scan"])
        # The three per-call lists are Pre-Check-plane rows and stay open.
        assert isinstance(provenance["scan"]["resolved_refs"], list)
    assert detail.json()["revisions"] == raw["revisions"]
