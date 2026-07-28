"""O-12: the dual-token OCC conflict rule over HTTP.

Seventeen mutating endpoints accept the concurrency token in TWO places — the body
(`expected_*`, the domain identity) and `If-Match` (the HTTP transport of that
identity). Every page spec says they are two spellings of one value and must not
be treated as interchangeable fields (doc 15 §11, doc 20 §14, doc 21 §7), but the
behaviour when they DISAGREED was undefined: each route silently preferred the
body and dropped the header, applying a mutation under a version the caller never
sanctioned.

The rule is now one line in `reconcile_occ_tokens`: disagreement -> 409
OCC_TOKEN_CONFLICT. These tests pin it at the HTTP edge across all four token
shapes actually in use, because the reconcile runs in the route before any DB
access — a dummy session is enough.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role


class _DummySession:
    """Stand-in: the conflict is raised in the route, before any DB access."""


ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)


def _override(app: Any, actor: Actor) -> Iterator[None]:
    app.dependency_overrides[request_context] = lambda: RequestContext(
        session=_DummySession(),  # type: ignore[arg-type]
        actor=actor,
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


def _client(app: Any, *, raise_app_exceptions: bool = True) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions),
        base_url="http://t",
    )


# (label, method, path, body, If-Match) — one row per OCC token SHAPE in use.
_CONFLICTS = [
    # int row_version, transported as the "rv-N" ETag
    (
        "strategy-draft-patch",
        "PATCH",
        "/api/v1/strategy-drafts/sd_1",
        {"expected_draft_row_version": 5},
        '"rv-6"',
    ),
    (
        "strategy-draft-save",
        "POST",
        "/api/v1/strategy-drafts/sd_1/save",
        {"expected_draft_row_version": 5},
        '"rv-6"',
    ),
    (
        "strategy-draft-clear",
        "POST",
        "/api/v1/strategy-drafts/sd_1/clear",
        {"expected_draft_row_version": 5},
        '"rv-6"',
    ),
    (
        "mainboard-item-patch",
        "PATCH",
        "/api/v1/mainboard-items/mbi_1",
        {"intent": "toggle_enabled", "expected_row_version": 5},
        '"rv-6"',
    ),
    (
        "allocation-draft-put",
        "PUT",
        "/api/v1/mainboard-compositions/mc_1/portfolio-allocation-draft",
        {"expected_row_version": 5},
        '"rv-6"',
    ),
    (
        "allocation-revision",
        "POST",
        "/api/v1/mainboard-compositions/mc_1/portfolio-allocation/revisions",
        {"expected_row_version": 5},
        '"rv-6"',
    ),
    (
        "backtest-result-delete",
        "POST",
        "/api/v1/backtest-results/br_1/delete",
        {"expected_row_version": 5},
        '"rv-6"',
    ),
    (
        "backtest-run-cancel",
        "POST",
        "/api/v1/backtest-runs/btrun_1/cancel",
        {"expected_row_version": 5},
        '"rv-6"',
    ),
    # str fingerprint
    (
        "readiness-check",
        "POST",
        "/api/v1/mainboard-compositions/mc_1/readiness-checks",
        {"expected_fingerprint": "fp-alpha"},
        '"fp-beta"',
    ),
    (
        "backtest-run",
        "POST",
        "/api/v1/mainboard-compositions/mc_1/backtest-runs",
        {"expected_fingerprint": "fp-alpha"},
        '"fp-beta"',
    ),
    # str revision id
    (
        "metric-profile-revision",
        "POST",
        "/api/v1/metric-profiles/mp_1/revisions",
        {"selected_metric_codes": ["net_profit"], "expected_profile_revision_id": "rev_a"},
        '"rev_b"',
    ),
    (
        "manual-revision",
        "POST",
        "/api/v1/admin/manual/documents/doc_1/revisions",
        {"content": "x", "expected_head_revision_id": "rev_a"},
        '"rev_b"',
    ),
    # int head revision (Trash lifecycle) + the O-18 generic soft delete
    (
        "trash-restore",
        "POST",
        "/api/v1/trash-entries/te_1/restore",
        {"expected_head_revision_id": 5},
        '"rv-6"',
    ),
    (
        "admin-role-assign",
        "PATCH",
        "/api/v1/admin/users/usr_1/role",
        {"target_role": "admin", "expected_head_revision_id": 5},
        '"6"',
    ),
    (
        "entity-soft-delete",
        "DELETE",
        "/api/v1/entities/ent_1",
        {"expected_row_version": 5},
        '"rv-6"',
    ),
]


@pytest.mark.contract
@pytest.mark.parametrize(
    ("label", "method", "path", "body", "if_match"),
    _CONFLICTS,
    ids=[row[0] for row in _CONFLICTS],
)
async def test_disagreeing_occ_tokens_are_409(
    app, label: str, method: str, path: str, body: dict[str, Any], if_match: str
) -> None:
    gen = _override(app, ADMIN)
    next(gen)
    try:
        async with _client(app) as c:
            resp = await c.request(method, path, json=body, headers={"If-Match": if_match})
    finally:
        next(gen, None)

    assert resp.status_code == 409, f"{label}: expected 409, got {resp.status_code}"
    error = resp.json()["error"]
    assert error["code"] == "OCC_TOKEN_CONFLICT", label
    # The recovery contract (O-02) must be complete on the new code, and it must
    # NOT advertise a blind retry: resending the same contradiction always fails.
    assert error["category"] == "concurrency_or_preflight", label
    assert error["retryable"] is False, label
    assert error["suggested_action"] == "resend_with_a_single_occ_token", label
    assert error["remediation"], label
    # Both values are echoed so the caller can see WHICH pair contradicted.
    assert error["details"], label
    assert error["field_path"], label


@pytest.mark.contract
@pytest.mark.parametrize(
    ("label", "method", "path", "body", "if_match"),
    _CONFLICTS,
    ids=[row[0] for row in _CONFLICTS],
)
async def test_agreeing_occ_tokens_pass_the_gate(
    app, label: str, method: str, path: str, body: dict[str, Any], if_match: str
) -> None:
    """Agreement is NOT a conflict: the request proceeds past the reconcile gate.

    The dummy session makes the downstream command fail, which is fine — the point
    is that the failure is never OCC_TOKEN_CONFLICT. This is what keeps the rule
    from breaking the callers that legitimately mirror the body token into If-Match.
    """
    # Re-spell the header so it carries the SAME value the body carries.
    body_token = next(v for k, v in body.items() if k.startswith("expected_"))
    agreeing = f'"rv-{body_token}"' if if_match.startswith('"rv-') else f'"{body_token}"'

    gen = _override(app, ADMIN)
    next(gen)
    try:
        async with _client(app, raise_app_exceptions=False) as c:
            resp = await c.request(method, path, json=body, headers={"If-Match": agreeing})
    finally:
        next(gen, None)

    if resp.status_code == 409:
        assert resp.json()["error"]["code"] != "OCC_TOKEN_CONFLICT", label


@pytest.mark.contract
async def test_single_token_callers_are_untouched(app) -> None:
    """A caller sending only ONE token never sees the new error — the rule adds a
    failure mode for contradictions only, it does not make If-Match mandatory."""
    gen = _override(app, ADMIN)
    next(gen)
    try:
        async with _client(app, raise_app_exceptions=False) as c:
            body_only = await c.patch(
                "/api/v1/strategy-drafts/sd_1", json={"expected_draft_row_version": 5}
            )
            header_only = await c.patch(
                "/api/v1/strategy-drafts/sd_1", json={}, headers={"If-Match": '"rv-5"'}
            )
    finally:
        next(gen, None)

    for resp in (body_only, header_only):
        if resp.status_code == 409:
            assert resp.json()["error"]["code"] != "OCC_TOKEN_CONFLICT"
