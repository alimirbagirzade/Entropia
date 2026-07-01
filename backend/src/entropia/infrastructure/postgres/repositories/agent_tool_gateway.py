"""Tool Gateway persistence access (Stage 6a-2, doc 18 §9.2).

Module-level async functions over ``agent_tool_call``. No commits — the Tool
Gateway (``application/jobs/agent_tools``) owns the transaction. The terminal
outcome is written back onto the row the dispatcher created (status +
response_ref + artifact_output_ref), so a redelivered call replays it (AL-14).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.agent_lab.tool_gateway import PolicyScope, ToolCallStatus, ToolName
from entropia.domain.lifecycle.enums import ActorKind
from entropia.infrastructure.postgres.models.agent_tool_gateway import AgentToolCall
from entropia.shared.ids import new_id


async def create_tool_call(
    session: AsyncSession,
    *,
    tool_name: ToolName,
    agent_id: str,
    actor_principal_id: str | None,
    actor_kind: ActorKind,
    policy_scope: PolicyScope,
    task_id: str | None = None,
    checkpoint_id: str | None = None,
    input_manifest_id: str | None = None,
    idempotency_key: str | None = None,
    request: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    status: ToolCallStatus = ToolCallStatus.RUNNING,
) -> AgentToolCall:
    """Insert the durable envelope for one tool call, RUNNING by default."""
    call = AgentToolCall(
        tool_call_id=new_id("agttool"),
        tool_name=tool_name.value,
        agent_id=agent_id,
        actor_principal_id=actor_principal_id,
        actor_kind=actor_kind,
        policy_scope=policy_scope,
        status=status,
        task_id=task_id,
        checkpoint_id=checkpoint_id,
        input_manifest_id=input_manifest_id,
        idempotency_key=idempotency_key,
        request=request or {},
        correlation_id=correlation_id,
    )
    session.add(call)
    await session.flush()
    return call


async def get_tool_call(session: AsyncSession, tool_call_id: str) -> AgentToolCall | None:
    return await session.get(AgentToolCall, tool_call_id)


async def get_by_idempotency_key(
    session: AsyncSession, idempotency_key: str
) -> AgentToolCall | None:
    """The prior tool call for this key, if any — the at-least-once guard (AL-14).

    This SELECT is a fast path; correctness under a concurrent redelivery rests on
    the DB-level ``uq_agent_tool_call_idem`` UNIQUE constraint. ``create_tool_call``
    flushes the row (with the key) BEFORE any handler side effect runs, so a losing
    concurrent transaction blocks on the unique index and never executes its
    handler — it rolls back and replays this recorded outcome (same guarantee as
    ``UNIQUE(backtest_result.run_id)`` in the backtest engine)."""
    stmt = select(AgentToolCall).where(AgentToolCall.idempotency_key == idempotency_key).limit(1)
    return (await session.execute(stmt)).scalars().first()


async def list_tool_calls(
    session: AsyncSession, *, task_id: str | None = None, limit: int = 50
) -> list[AgentToolCall]:
    stmt = select(AgentToolCall)
    if task_id is not None:
        stmt = stmt.where(AgentToolCall.task_id == task_id)
    stmt = stmt.order_by(AgentToolCall.tool_call_id.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


__all__ = [
    "create_tool_call",
    "get_by_idempotency_key",
    "get_tool_call",
    "list_tool_calls",
]
