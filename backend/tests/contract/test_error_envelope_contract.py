"""O-02 — the structured error envelope contract (doc 01 §11.2, doc 04 §11.1).

Both page specs pin a machine-readable recovery envelope that the shipped
``ErrorBody`` did not carry: ``category``, ``retryable``, ``suggested_action`` /
``remediation``, ``scope_type``, ``scope_id`` and ``field_path``. These tests assert
the wire shape end to end through the app's real exception handlers, including the
two worked examples the specs write out verbatim.

Adjudication under test (see ``shared/errors.py``): doc 01's ``field_issues`` is the
shipped ``details`` list, and ``suggested_action`` (machine token) and ``remediation``
(human prose) stay two distinct fields.

Probe routes are mounted on a throwaway app per assertion — the session-scoped ``app``
fixture is shared and is only read here, never mutated.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from entropia.apps.api.main import create_app
from entropia.shared.errors import (
    AppError,
    ErrorCategory,
    ReadyReportStaleError,
    SignalEventMappingRequiredError,
    ValidationError,
)

# The full envelope key set. A client reads every key unconditionally, so absent
# optional values must be explicit nulls rather than missing keys.
ENVELOPE_KEYS = {
    "code",
    "message",
    "details",
    "request_id",
    "correlation_id",
    "category",
    "retryable",
    "suggested_action",
    "remediation",
    "scope_type",
    "scope_id",
    "field_path",
}

# The pre-O-02 Module 19 contract. These names must never move.
LEGACY_KEYS = {"code", "message", "details", "request_id", "correlation_id"}

PROBE_PATH = "/__envelope_probe"


class _Body(BaseModel):
    quantity: int


async def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _raise_through_app(exc: AppError) -> dict[str, Any]:
    """Raise ``exc`` from a real route and return the rendered ``error`` object."""
    probe = create_app()

    async def _boom() -> None:
        raise exc

    probe.add_api_route(PROBE_PATH, _boom, methods=["GET"], include_in_schema=False)
    async with await _client(probe) as c:
        resp = await c.get(PROBE_PATH)
    assert resp.status_code == exc.http_status
    return dict(resp.json()["error"])


@pytest.mark.contract
async def test_envelope_exposes_every_recovery_field_and_keeps_the_legacy_names() -> None:
    error = await _raise_through_app(ValidationError("Nope."))
    assert set(error.keys()) == ENVELOPE_KEYS
    # Backward compatibility: the original five keys survive with their meanings.
    assert set(error.keys()) >= LEGACY_KEYS
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Nope."
    assert error["details"] == []


@pytest.mark.contract
async def test_ready_report_stale_reproduces_the_doc_01_worked_example() -> None:
    # doc 01 §11.2 writes this envelope out verbatim for READY_REPORT_STALE.
    error = await _raise_through_app(ReadyReportStaleError())
    assert error["code"] == "READY_REPORT_STALE"
    assert error["category"] == ErrorCategory.CONCURRENCY_OR_PREFLIGHT.value
    assert error["retryable"] is True
    assert error["suggested_action"] == "rerun_ready_check"
    # doc 01 calls the per-field list ``field_issues``; it ships as ``details``.
    assert error["details"] == []


@pytest.mark.contract
async def test_signal_event_mapping_reproduces_the_doc_04_worked_example() -> None:
    # doc 04 §11.1 writes this envelope out verbatim for SIGNAL_EVENT_MAPPING_REQUIRED.
    error = await _raise_through_app(SignalEventMappingRequiredError())
    assert error["code"] == "SIGNAL_EVENT_MAPPING_REQUIRED"
    assert error["category"] == ErrorCategory.DEPENDENCY_VALIDATION.value
    assert error["retryable"] is False
    assert error["scope_type"] == "TradingSignal"
    assert error["field_path"] == "import_binding.mapping.available_time"
    assert error["remediation"] is not None
    assert "rerun import validation" in error["remediation"]


@pytest.mark.contract
async def test_a_raise_site_can_pin_the_scope_and_field_it_failed_on() -> None:
    # A generic class still reports the concrete object/field (doc 04 §11.1).
    error = await _raise_through_app(
        ValidationError(
            "Map an available time for every accepted signal event.",
            scope_type="TradingSignal",
            scope_id="ts_root_42",
            field_path="import_binding.mapping.available_time",
            remediation="Add the source column, then rerun import validation.",
        )
    )
    assert error["scope_type"] == "TradingSignal"
    assert error["scope_id"] == "ts_root_42"
    assert error["field_path"] == "import_binding.mapping.available_time"
    assert error["remediation"].endswith("rerun import validation.")
    # The class-level category still applies; pinning scope does not reclassify.
    assert error["category"] == ErrorCategory.VALIDATION.value


@pytest.mark.contract
async def test_an_unclassified_failure_is_never_advertised_as_retryable() -> None:
    error = await _raise_through_app(AppError())
    assert error["category"] == ErrorCategory.INTERNAL.value
    assert error["retryable"] is False
    assert error["suggested_action"] is None


@pytest.mark.contract
async def test_framework_raised_responses_are_classified_from_the_status(app) -> None:
    # An unmatched route is produced by Starlette, not by domain code — it must
    # still carry the envelope rather than a bare {"detail": ...}.
    async with await _client(app) as c:
        resp = await c.get("/api/v1/definitely-not-a-route")
    assert resp.status_code == 404
    error = resp.json()["error"]
    assert set(error.keys()) == ENVELOPE_KEYS
    assert error["category"] == ErrorCategory.NOT_FOUND.value
    assert error["retryable"] is False


@pytest.mark.contract
async def test_schema_rejection_names_the_single_offending_field() -> None:
    probe = create_app()

    async def _echo(body: _Body) -> dict[str, int]:
        return {"quantity": body.quantity}

    probe.add_api_route(PROBE_PATH, _echo, methods=["POST"], include_in_schema=False)
    async with await _client(probe) as c:
        resp = await c.post(PROBE_PATH, json={"quantity": "not-a-number"})
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["category"] == ErrorCategory.VALIDATION.value
    assert error["field_path"] == "body.quantity"
    assert error["details"][0]["field"] == "body.quantity"


@pytest.mark.contract
async def test_the_envelope_is_published_in_the_openapi_schema(app) -> None:
    # Error responses come from exception handlers, so no route declares the model;
    # it is registered explicitly so the drift guard reviews changes to it.
    schemas = app.openapi()["components"]["schemas"]
    assert "ErrorResponse" in schemas
    assert set(schemas["ErrorBody"]["properties"]) == ENVELOPE_KEYS
