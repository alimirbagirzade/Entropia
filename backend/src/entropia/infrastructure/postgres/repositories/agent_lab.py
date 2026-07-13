"""Analysis Lab persistence access (Stage 6a, doc 18 §9).

Module-level async functions. No commits — the command layer owns the
transaction. L1 (parent-before-child): ``create_task`` flushes before a
checkpoint/directive/artifact references it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.agent_lab.enums import (
    AgentTaskPriority,
    AgentTaskStatus,
    DirectiveStatus,
    HypothesisStatus,
    LabMessageType,
)
from entropia.domain.lifecycle.enums import ActorKind, DeletionState
from entropia.infrastructure.postgres.models.agent_lab import (
    AgentCheckpoint,
    AgentEvent,
    AgentRuntime,
    AgentTask,
    ArtifactLink,
    HypothesisArtifact,
    LabMessage,
    TaskDirective,
)
from entropia.shared.ids import new_id

# ---------- Runtime ----------


async def get_runtime(session: AsyncSession, agent_id: str) -> AgentRuntime | None:
    return await session.get(AgentRuntime, agent_id)


async def create_runtime(
    session: AsyncSession, *, agent_id: str, mode: Any, status: Any
) -> AgentRuntime:
    runtime = AgentRuntime(agent_id=agent_id, mode=mode, status=status, row_version=1)
    session.add(runtime)
    await session.flush()
    return runtime


# ---------- Tasks ----------


async def create_task(
    session: AsyncSession,
    *,
    agent_id: str,
    task_type: str,
    title: str,
    source: str,
    priority: AgentTaskPriority,
    status: AgentTaskStatus,
    stage: str | None = None,
    context_manifest_id: str | None = None,
    parent_task_id: str | None = None,
) -> AgentTask:
    task = AgentTask(
        task_id=new_id("agttask"),
        agent_id=agent_id,
        task_type=task_type,
        title=title,
        source=source,
        priority=priority,
        status=status,
        stage=stage,
        progress=0,
        context_manifest_id=context_manifest_id,
        parent_task_id=parent_task_id,
    )
    session.add(task)
    await session.flush()
    return task


async def get_task(session: AsyncSession, task_id: str) -> AgentTask | None:
    return await session.get(AgentTask, task_id)


async def page_tasks(
    session: AsyncSession,
    *,
    agent_id: str | None = None,
    status: AgentTaskStatus | None = None,
    last_key: str | None = None,
    limit: int,
) -> list[AgentTask]:
    """One keyset page ordered by ``task_id`` DESC (sortable id => recency)."""
    stmt = select(AgentTask)
    if agent_id is not None:
        stmt = stmt.where(AgentTask.agent_id == agent_id)
    if status is not None:
        stmt = stmt.where(AgentTask.status == status)
    if last_key is not None:
        stmt = stmt.where(AgentTask.task_id < last_key)
    stmt = stmt.order_by(AgentTask.task_id.desc()).limit(limit + 1)
    return list((await session.execute(stmt)).scalars().all())


async def recent_tasks(session: AsyncSession, agent_id: str, limit: int) -> list[AgentTask]:
    stmt = (
        select(AgentTask)
        .where(AgentTask.agent_id == agent_id)
        .order_by(AgentTask.task_id.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def queue_counts(session: AsyncSession, agent_id: str) -> dict[str, int]:
    stmt = (
        select(AgentTask.status, func.count())
        .where(AgentTask.agent_id == agent_id)
        .group_by(AgentTask.status)
    )
    rows = (await session.execute(stmt)).all()
    return {str(status): int(count) for status, count in rows}


# ---------- Directives ----------


async def create_directive(
    session: AsyncSession,
    *,
    author_principal_id: str,
    target_agent_id: str,
    related_task_id: str | None,
    text: str,
    priority: AgentTaskPriority,
    correlation_id: str | None,
) -> TaskDirective:
    directive = TaskDirective(
        directive_id=new_id("agtdir"),
        author_principal_id=author_principal_id,
        target_agent_id=target_agent_id,
        related_task_id=related_task_id,
        text=text,
        priority=priority,
        status=DirectiveStatus.QUEUED,
        delivery_policy="next_safe_checkpoint",
        correlation_id=correlation_id,
    )
    session.add(directive)
    await session.flush()
    return directive


async def get_directive(session: AsyncSession, directive_id: str) -> TaskDirective | None:
    return await session.get(TaskDirective, directive_id)


async def next_queued_directive(session: AsyncSession, agent_id: str) -> TaskDirective | None:
    """The next eligible directive: HIGH before NORMAL, then oldest first."""
    priority_rank = case((TaskDirective.priority == AgentTaskPriority.HIGH, 0), else_=1)
    stmt = (
        select(TaskDirective)
        .where(
            TaskDirective.target_agent_id == agent_id,
            TaskDirective.status == DirectiveStatus.QUEUED,
        )
        .order_by(priority_rank, TaskDirective.created_at.asc(), TaskDirective.directive_id.asc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


async def list_directives_for_task(session: AsyncSession, task_id: str) -> list[TaskDirective]:
    stmt = (
        select(TaskDirective)
        .where(TaskDirective.related_task_id == task_id)
        .order_by(TaskDirective.created_at.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


# ---------- Checkpoints ----------


async def max_checkpoint_no(session: AsyncSession, task_id: str) -> int:
    stmt = select(func.max(AgentCheckpoint.checkpoint_no)).where(AgentCheckpoint.task_id == task_id)
    current = (await session.execute(stmt)).scalar_one_or_none()
    return int(current) if current is not None else 0


async def create_checkpoint(
    session: AsyncSession,
    *,
    task_id: str,
    checkpoint_no: int,
    stage: str,
    state_ref: str | None = None,
    context_manifest_id: str | None = None,
    plan_revision: int = 1,
    directive_cursor: str | None = None,
    artifact_ids: list[str] | None = None,
) -> AgentCheckpoint:
    checkpoint = AgentCheckpoint(
        checkpoint_id=new_id("agtckpt"),
        task_id=task_id,
        checkpoint_no=checkpoint_no,
        stage=stage,
        state_ref=state_ref,
        context_manifest_id=context_manifest_id,
        plan_revision=plan_revision,
        directive_cursor=directive_cursor,
        artifact_ids=artifact_ids or [],
    )
    session.add(checkpoint)
    await session.flush()
    return checkpoint


async def get_latest_checkpoint(session: AsyncSession, task_id: str) -> AgentCheckpoint | None:
    stmt = (
        select(AgentCheckpoint)
        .where(AgentCheckpoint.task_id == task_id)
        .order_by(AgentCheckpoint.checkpoint_no.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


async def list_checkpoints(session: AsyncSession, task_id: str) -> list[AgentCheckpoint]:
    stmt = (
        select(AgentCheckpoint)
        .where(AgentCheckpoint.task_id == task_id)
        .order_by(AgentCheckpoint.checkpoint_no.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


# ---------- Lab messages ----------


async def create_message(
    session: AsyncSession,
    *,
    message_type: LabMessageType,
    author_principal_id: str | None,
    text: str,
    task_id: str | None,
    correlation_id: str | None,
) -> LabMessage:
    message = LabMessage(
        message_id=new_id("labmsg"),
        type=message_type,
        author_principal_id=author_principal_id,
        text=text,
        task_id=task_id,
        correlation_id=correlation_id,
    )
    session.add(message)
    await session.flush()
    return message


async def page_messages(
    session: AsyncSession,
    *,
    task_id: str | None = None,
    last_key: str | None = None,
    limit: int,
) -> list[LabMessage]:
    """One keyset page of the append-only conversation log, newest-first.

    ``message_id`` is a sortable id, so it doubles as the recency key (mirrors
    ``page_tasks`` / ``page_hypotheses``). ``task_id`` scopes to a single task's
    thread; ``None`` returns the whole conversation.
    """
    stmt = select(LabMessage)
    if task_id is not None:
        stmt = stmt.where(LabMessage.task_id == task_id)
    if last_key is not None:
        stmt = stmt.where(LabMessage.message_id < last_key)
    stmt = stmt.order_by(LabMessage.message_id.desc()).limit(limit + 1)
    return list((await session.execute(stmt)).scalars().all())


# ---------- Hypotheses / artifacts ----------


async def create_hypothesis(
    session: AsyncSession,
    *,
    status: HypothesisStatus,
    title: str,
    mechanism: str,
    data_context: str | None = None,
    evidence_refs: list[Any] | None = None,
    next_action: str | None = None,
    source_task_id: str | None = None,
    checkpoint_id: str | None = None,
    created_by_principal_id: str | None = None,
    correlation_id: str | None = None,
) -> HypothesisArtifact:
    artifact = HypothesisArtifact(
        artifact_id=new_id("hypart"),
        status=status,
        title=title,
        mechanism=mechanism,
        data_context=data_context,
        evidence_refs=evidence_refs or [],
        next_action=next_action,
        source_task_id=source_task_id,
        checkpoint_id=checkpoint_id,
        deletion_state=DeletionState.ACTIVE,
        created_by_principal_id=created_by_principal_id,
        correlation_id=correlation_id,
        row_version=1,
    )
    session.add(artifact)
    await session.flush()
    return artifact


async def get_hypothesis(session: AsyncSession, artifact_id: str) -> HypothesisArtifact | None:
    return await session.get(HypothesisArtifact, artifact_id)


async def page_hypotheses(
    session: AsyncSession,
    *,
    status: HypothesisStatus | None = None,
    last_key: str | None = None,
    limit: int,
) -> list[HypothesisArtifact]:
    """One keyset page of ACTIVE (non-soft-deleted) artifacts, id DESC."""
    stmt = select(HypothesisArtifact).where(
        HypothesisArtifact.deletion_state == DeletionState.ACTIVE
    )
    if status is not None:
        stmt = stmt.where(HypothesisArtifact.status == status)
    if last_key is not None:
        stmt = stmt.where(HypothesisArtifact.artifact_id < last_key)
    stmt = stmt.order_by(HypothesisArtifact.artifact_id.desc()).limit(limit + 1)
    return list((await session.execute(stmt)).scalars().all())


async def create_artifact_link(
    session: AsyncSession,
    *,
    source_artifact_id: str,
    target_type: str,
    target_id: str,
    relation_type: str,
) -> ArtifactLink:
    link = ArtifactLink(
        link_id=new_id("artlink"),
        source_artifact_id=source_artifact_id,
        target_type=target_type,
        target_id=target_id,
        relation_type=relation_type,
    )
    session.add(link)
    await session.flush()
    return link


async def list_artifact_links(session: AsyncSession, source_artifact_id: str) -> list[ArtifactLink]:
    stmt = (
        select(ArtifactLink)
        .where(ArtifactLink.source_artifact_id == source_artifact_id)
        .order_by(ArtifactLink.created_at.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


# ---------- Events ----------


async def append_event(
    session: AsyncSession,
    *,
    event_type: str,
    actor_principal_id: str | None,
    actor_kind: ActorKind,
    task_id: str | None = None,
    directive_id: str | None = None,
    payload: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> AgentEvent:
    event = AgentEvent(
        event_id=new_id("agtevt"),
        type=event_type,
        actor_principal_id=actor_principal_id,
        actor_kind=actor_kind,
        task_id=task_id,
        directive_id=directive_id,
        payload=payload or {},
        correlation_id=correlation_id,
    )
    session.add(event)
    await session.flush()
    return event


async def events_after(session: AsyncSession, *, after_seq: int, limit: int) -> list[AgentEvent]:
    stmt = (
        select(AgentEvent)
        .where(AgentEvent.seq > after_seq)
        .order_by(AgentEvent.seq.asc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def latest_event_seq(session: AsyncSession) -> int:
    current = (await session.execute(select(func.max(AgentEvent.seq)))).scalar_one_or_none()
    return int(current) if current is not None else 0


__all__ = [
    "append_event",
    "create_artifact_link",
    "create_checkpoint",
    "create_directive",
    "create_hypothesis",
    "create_message",
    "create_runtime",
    "create_task",
    "events_after",
    "get_directive",
    "get_hypothesis",
    "get_latest_checkpoint",
    "get_runtime",
    "get_task",
    "latest_event_seq",
    "list_artifact_links",
    "list_checkpoints",
    "list_directives_for_task",
    "max_checkpoint_no",
    "next_queued_directive",
    "page_hypotheses",
    "page_messages",
    "page_tasks",
    "queue_counts",
    "recent_tasks",
]
