"""O-02 — a readiness blocker's remediation reaches the HTTP error envelope.

``ReadinessIssue`` has always carried ``remediation``/``field_path``/``scope_id``
(doc 14 §3.2), but the RUN-admission 422 dropped them: the caller saw the symptom
and never the fix. This exercises the real path against a real database — seed a
composition whose pinned indicator does not resolve, let RUN admission re-run the
mandatory server preflight, then render the resulting error through the app's own
registered exception handler and assert the recovery fields survive the trip.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from starlette.requests import Request

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.apps.api.main import create_app
from entropia.domain.backtest.indicators import ENGINE_COMPUTABLE_KEYS
from entropia.shared.errors import AppError, ErrorCategory, ReadinessBlockedError

# Reuse the Stage 5a seeding helpers rather than re-deriving a ready composition.
from tests.integration.test_backtest_persistence import (
    USER1,
    _ready_composition,
    _seed_principals,
)

pytestmark = pytest.mark.integration


async def _render(exc: AppError) -> dict[str, Any]:
    """Render ``exc`` through the app's registered AppError handler."""
    handler = create_app().exception_handlers[AppError]
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
    response = await handler(request, exc)
    assert response.status_code == exc.http_status
    return dict(json.loads(bytes(response.body))["error"])


async def test_readiness_blocker_remediation_reaches_the_http_envelope(session) -> None:
    await _seed_principals(session)
    composition_id, _root, _rev = await _ready_composition(
        session, USER1, resolvable_indicator=False
    )

    with pytest.raises(ReadinessBlockedError) as excinfo:
        await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)

    error = await _render(excinfo.value)

    assert error["code"] == "READINESS_BLOCKED"
    assert error["category"] == ErrorCategory.COMPOSITION_VALIDATION.value
    assert error["retryable"] is False
    assert error["suggested_action"] == "resolve_blockers_and_recheck"

    # The leading blocker is promoted onto the envelope itself, so a client can act
    # without parsing ``details``. These values come from the ReadinessIssue that
    # commands/readiness_check.py emitted — not from a string re-invented here.
    assert error["scope_type"] == "strategy"
    assert error["scope_id"] is not None
    assert error["field_path"] == "position_entry_logic.indicator_blocks"
    assert error["remediation"] is not None
    assert "re-run the check" in error["remediation"]
    # The remedy must name what this engine can actually execute. Telling the author to
    # "pin a package whose dependencies resolve" without saying WHICH keys resolve leaves
    # them guessing at the one gate that refused them. Derived from the engine's own set,
    # so a newly supported resolver cannot leave this text behind.
    for key in ENGINE_COMPUTABLE_KEYS:
        assert key in error["remediation"], key
    # ta.atr is recognized but computes no directional series: naming it here would send
    # the author to a pin that fails this very check again.
    assert "ta.atr" not in error["remediation"]

    # ``details`` still carries every issue, and each one now keeps its remediation
    # instead of having it stripped on the way out.
    blocker = next(d for d in error["details"] if d["code"] == "STRATEGY_INDICATOR_UNRESOLVED")
    assert blocker["remediation"] == error["remediation"]
    assert blocker["field"] == "position_entry_logic.indicator_blocks"
    assert blocker["scope_id"] == error["scope_id"]
