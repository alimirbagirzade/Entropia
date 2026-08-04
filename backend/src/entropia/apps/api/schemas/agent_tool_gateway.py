"""Agent Tool Gateway call-history response contracts (doc 18 §7, §9.2, §14).

These two reads are the ONLY HTTP surface of the gateway. Dispatch and enqueue
(``application/jobs/agent_tools.py::dispatch_tool_call`` / ``enqueue_tool_call``) are
worker-plane functions with no route, so there is no request contract to publish here —
what a human can reach over HTTP is the durable record the Coordinator already wrote.

The envelope/payload split is deliberate. Every field the GATEWAY owns — identity,
provenance, policy, terminal status, failure pointers, timestamps — is typed and published.
The two per-tool payloads (``request``, ``response_ref``) stay OPEN objects: ``response_ref``
is discriminated by ``tool_name`` across 33 registered tools and is the backing command's
return stored VERBATIM, so a closed union here would have to be re-cut on every tool added
to the registry and would drop fields from any tool it did not yet know about.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AgentToolCallCard(BaseModel):
    """Summary row (``queries/agent_tool_gateway.py::_tool_call_card``).

    Payload bodies are omitted from the listing by design — the per-call detail carries them.
    ``failure_code`` is a free-form ``AppError.code`` (UPPER_SNAKE_CASE), unlike ``status`` /
    ``actor_kind`` / ``policy_scope`` which are lowercase ``StrEnum`` wire values; it is not
    a closed set, so it is declared ``str`` rather than an enum."""

    tool_call_id: str
    tool_name: str
    task_id: str | None
    checkpoint_id: str | None
    actor_kind: str
    policy_scope: str
    status: str
    artifact_output_ref: str | None
    failure_code: str | None
    failure_message: str | None
    correlation_id: str | None
    created_at: str | None
    updated_at: str | None


class AgentToolCallListResponse(BaseModel):
    """``GET /agent-tasks/{task_id}/tool-calls`` — newest-first, bounded, NOT cursor-paged.

    The envelope carries no cursor on purpose: the listing is a bounded recent-activity
    view (``clamp_limit``), not a pageable history, so it must not advertise a ``meta``
    block the server never advances."""

    tool_calls: list[AgentToolCallCard]


class AgentToolCallDetailResponse(AgentToolCallCard):
    """``GET /agent-tool-calls/{tool_call_id}`` — the card plus the verbatim payloads.

    Inherits the card so the detail can never fall out of superset with the listing.

    ``response_ref`` is a THREE-WAY union kept open: on ``succeeded`` it is the tool's own
    payload (Strategy draft/revision results, Trading Signal upload/import/create results,
    …) with no ``status`` key at all — read the sibling ``status`` column instead; on
    ``rejected`` it is ``{status, reason_code, reason}``; on ``failed`` it is
    ``{status, failure_code, failure_reason, details}``. It is ``null`` while the call is
    still ``running``."""

    agent_id: str
    actor_principal_id: str | None
    input_manifest_id: str | None
    idempotency_key: str | None
    request: dict[str, Any]
    response_ref: dict[str, Any] | None


__all__ = [
    "AgentToolCallCard",
    "AgentToolCallDetailResponse",
    "AgentToolCallListResponse",
]
