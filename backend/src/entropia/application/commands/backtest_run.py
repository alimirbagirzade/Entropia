"""Backtest RUN admission + cancel + retry + result soft-delete (doc 15 §7-§9, §15).

RUN is NOT a browser 'calculate' button (doc 15 §1, §15): the endpoint re-runs the
MANDATORY server-side preflight from the CURRENT persisted composition — the client
``ready`` flag, item list and modal text are never trusted. The preflight is the 4b
``run_readiness_check`` called nested (``idempotency_key=None`` pass-through), which
also builds the immutable snapshot + report the manifest then pins.

One transaction (supplied by the request dependency, never committed here):

    require_authenticated + ensure_can_view (OUTSIDE the idempotent body) ->
    run_idempotent op {
        run_readiness_check (fresh snapshot+report; 409 COMPOSITION_STALE on
            expected_fingerprint mismatch) ->
        optional ready_report_id currentness guard (409 READY_REPORT_STALE) ->
        blocker_count > 0 => 422 READINESS_BLOCKED (no run/manifest/job) ->
        build immutable manifest (hash-pinned, no 'latest') ->
        create QUEUED backtest_run + backtest_run_manifest ->
        enqueue durable 'backtest' job (row = source of truth, CR-09) + audit/outbox
    }

Only a succeeded worker run materializes a Result (CR-03); the worker lives in
``application/jobs/backtest_engine``. Cancel (O-06, doc 15 §8.4) is controlled, never
a kill: a QUEUED run is terminated here under a row lock, while a run the worker
already owns only gets a recorded INTENT that the worker honors at one of its O-05
stage boundaries. Retry never resets the original run — it
re-admits the CURRENT composition with a new run_id + manifest + ``retry_of_run_id``
(doc 15 §7, §8.4). Result soft-delete flips a local flag under owner/Admin policy +
``expected_row_version`` (409 on stale); Admin Trash restore/purge is Stage 6.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands.backtest_run_context import resolve_run_manifest_context
from entropia.application.commands.readiness_check import (
    _resolve_strategy_payload,
    record_readiness_access_denied,
    run_readiness_check,
)
from entropia.application.durable_audit import AuditSessionFactory, record_durable_audit
from entropia.application.idempotency import run_idempotent
from entropia.domain.backtest.engine import tick_data_required
from entropia.domain.backtest.enums import (
    RUN_RETRYABLE_STATES,
    RUN_TERMINAL_STATES,
    BacktestRunState,
    RunEventType,
)
from entropia.domain.backtest.manifest import build_run_manifest
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_edit, ensure_can_view, require_authenticated
from entropia.domain.lifecycle.enums import JOB_TERMINAL_STATES, DeletionState, JobStatus
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.readiness.enums import (
    ReadinessIssueCode,
    ReadinessScope,
    ReadinessSeverity,
)
from entropia.domain.strategy.config import StrategyConfig
from entropia.domain.trash.page import original_location_for
from entropia.infrastructure.postgres.models import Job, MainboardCompositionSnapshot
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import market_data as market_repo
from entropia.infrastructure.postgres.repositories import readiness as readiness_repo
from entropia.infrastructure.postgres.repositories import trash as trash_repo
from entropia.infrastructure.queues.enqueue import enqueue_job
from entropia.shared.errors import (
    AccessDeniedError,
    AppError,
    BacktestResultNotFoundError,
    BacktestRunNotFoundError,
    CompositionNotFoundError,
    ReadinessBlockedError,
    ReadyReportStaleError,
    RowVersionConflictError,
    RunNotCancellableError,
    RunNotRetryableError,
)
from entropia.shared.ids import new_id

_RUN_TARGET = "backtest_run"
_RESULT_TARGET = "backtest_result"
_WORKSPACE_TARGET = "mainboard_workspace"
_BACKTEST_QUEUE = "backtest"
_ACTIVE = "active"
_SOFT_DELETED = "soft_deleted"
_ADMISSION_REJECTED_EVENT = "backtest.run_admission_rejected"
_ADMISSION_ACCEPTED_EVENT = "backtest.run_admission_accepted"
_CANCEL_REQUESTED_EVENT = "backtest.run_cancellation_requested"
_CANCELLED_EVENT = "backtest.run_cancelled"
# Doc 15 §12: an authorized cancel runs under the durable queue/lifecycle and
# safe-checkpoint rules — the same delivery contract Analysis Lab's stop_run publishes.
_CANCEL_DELIVERY_POLICY = "cancellation_safe_boundary"
_ISSUE_SUMMARY_LIMIT = 10


# --------------------------------------------------------------------------- #
# RUN admission                                                               #
# --------------------------------------------------------------------------- #


async def request_backtest_run(
    session: AsyncSession,
    actor: Actor,
    *,
    composition_id: str,
    expected_fingerprint: str | None = None,
    ready_report_id: str | None = None,
    idempotency_key: str | None = None,
    parent_agent_task_id: str | None = None,
    audit_session_factory: AuditSessionFactory | None = None,
) -> dict[str, Any]:
    """Admit a backtest run for the current composition (doc 15 §7, §8.2).

    Both admission outcomes are audited (doc 14 §12.2): an accepted run emits
    ``backtest.run_admission_accepted`` in the SAME transaction as the run row, a
    rejected one emits ``backtest.run_admission_rejected`` DURABLY — the rejection
    is a raise, and the request tx is rolled back on the 4xx, so an in-transaction
    row could never survive (O-04)."""
    require_authenticated(actor)
    await _load_workspace(
        session,
        actor,
        composition_id,
        operation="request_backtest_run",
        audit_session_factory=audit_session_factory,
    )

    async def _op() -> dict[str, Any]:
        return await _admit_run(
            session,
            actor,
            composition_id=composition_id,
            expected_fingerprint=expected_fingerprint,
            ready_report_id=ready_report_id,
            retry_of_run_id=None,
            idempotency_key=idempotency_key,
            parent_agent_task_id=parent_agent_task_id,
            audit_session_factory=audit_session_factory,
        )

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "request_backtest_run",
            "composition_id": composition_id,
            "expected_fingerprint": expected_fingerprint,
        },
        operation=_op,
    )


async def retry_backtest_run(
    session: AsyncSession,
    actor: Actor,
    *,
    run_id: str,
    idempotency_key: str | None = None,
    parent_agent_task_id: str | None = None,
    audit_session_factory: AuditSessionFactory | None = None,
) -> dict[str, Any]:
    """Retry a terminal FAILED/CANCELLED run against the CURRENT composition.

    Never mutates the original run (immutable, historical); creates a new run_id +
    manifest hash + ``retry_of_run_id`` link (doc 15 §7, §8.4)."""
    require_authenticated(actor)
    original = await bt_repo.get_run(session, run_id)
    if original is None:
        raise BacktestRunNotFoundError()
    composition_id = original.workspace_entity_id
    await _load_workspace(
        session,
        actor,
        composition_id,
        operation="retry_backtest_run",
        audit_session_factory=audit_session_factory,
    )

    async def _op() -> dict[str, Any]:
        if original.state not in RUN_RETRYABLE_STATES:
            # A non-retryable state is an admission rejection like any other, so it
            # carries the same durable audit rather than vanishing with the 409 tx.
            rejection = RunNotRetryableError()
            await _record_admission_rejected(
                actor,
                composition_id=composition_id,
                expected_fingerprint=None,
                current_fingerprint=None,
                report_id=None,
                rejection=rejection,
                retry_of_run_id=original.run_id,
                audit_session_factory=audit_session_factory,
            )
            raise rejection
        return await _admit_run(
            session,
            actor,
            composition_id=composition_id,
            expected_fingerprint=None,
            ready_report_id=None,
            retry_of_run_id=original.run_id,
            idempotency_key=idempotency_key,
            parent_agent_task_id=parent_agent_task_id,
            audit_session_factory=audit_session_factory,
        )

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "retry_backtest_run", "run_id": run_id},
        operation=_op,
    )


async def cancel_backtest_run(
    session: AsyncSession,
    actor: Actor,
    *,
    run_id: str,
    expected_row_version: int | None = None,
    idempotency_key: str | None = None,
    audit_session_factory: AuditSessionFactory | None = None,
) -> dict[str, Any]:
    """Cancel a non-terminal run under owner/Admin policy (doc 15 §8.4, §16).

    Controlled cancellation, never a kill. Two paths, decided under a row lock:

    * **QUEUED** — no worker owns the run yet, so the cancel IS the terminal
      transition: ``cancelled`` + ``RUN_CANCELLED`` event + audit, written here.
      The worker's at-least-once terminal guard turns a later delivery of the
      same message into a no-op, so the engine never starts.
    * **PROVISIONING / RUNNING** — the worker owns the run and is mid-flight.
      Only the INTENT is recorded (``cancel_requested_at``); the worker observes
      it at its next O-05 stage boundary and writes the terminal state itself.
      Delivery is therefore ``cancellation_safe_boundary`` (the same policy
      ``agent_control.stop_run`` publishes): a run that reaches its final
      checkpoint before the request lands completes normally, and the response
      says ``requested``, never ``cancelled``.

    The lock is what makes the split honest: the worker takes the SAME row lock
    before it moves QUEUED -> PROVISIONING, so this either wins the race outright
    or blocks and then observes the stage the worker actually reached — it can
    never terminate a run out from under a worker that is already replaying.

    NO Backtest Result is ever materialized for a cancelled run (CR-03, doc 15
    §16), so a cancelled run also never reaches Results History.
    """
    require_authenticated(actor)
    run = await bt_repo.get_run(session, run_id)
    if run is None:
        raise BacktestRunNotFoundError()
    await _load_workspace(
        session,
        actor,
        run.workspace_entity_id,
        operation="cancel_backtest_run",
        audit_session_factory=audit_session_factory,
    )
    # Cancelling mutates someone's run, so it needs edit rights on the RUN itself
    # (its requester), not merely view rights on the composition — owner or Admin,
    # exactly like the Result soft delete below.
    ensure_can_edit(actor, owner_principal_id=run.requested_by_principal_id)

    async def _op() -> dict[str, Any]:
        await session.refresh(run, with_for_update=True)
        if run.state in RUN_TERMINAL_STATES:
            raise RunNotCancellableError()
        if expected_row_version is not None and expected_row_version != run.row_version:
            raise RowVersionConflictError()
        run.cancel_requested_at = datetime.now(UTC)
        run.cancel_requested_by_principal_id = actor.principal_id
        run.row_version += 1
        if run.state == BacktestRunState.QUEUED:
            return await _cancel_queued_run(session, actor, run=run)
        return _request_worker_cancellation(session, actor, run=run)

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "cancel_backtest_run",
            "run_id": run_id,
            "expected_row_version": expected_row_version,
        },
        operation=_op,
    )


async def _cancel_queued_run(session: AsyncSession, actor: Actor, *, run: Any) -> dict[str, Any]:
    """Terminal-cancel a run the worker has not started (still QUEUED).

    Writes the same terminal shape the worker writes at a stage boundary — state,
    ``cancellation_reason``, the ``RUN_CANCELLED`` stream event and the audit — so
    a consumer cannot tell the two paths apart except by the reason text. The
    durable job row is finalized too: nothing will ever execute it, and leaving it
    non-terminal would strand it in the queue projection forever.
    """
    reason = "Cancelled by an authorized actor before the worker started (queued)."
    run.state = BacktestRunState.CANCELLED
    run.cancellation_reason = reason
    run.finished_at = datetime.now(UTC)
    await bt_repo.record_run_event(
        session,
        run_id=run.run_id,
        event_type=RunEventType.RUN_CANCELLED,
        previous_state=BacktestRunState.QUEUED,
        state=BacktestRunState.CANCELLED,
        correlation_id=actor.correlation_id,
        detail={
            "cancellation_reason": reason,
            "cancelled_at_stage": BacktestRunState.QUEUED.value,
            "requested_by_principal_id": actor.principal_id,
            "result_id": None,
        },
    )
    if run.job_id is not None:
        job = await session.get(Job, run.job_id)
        if job is not None and job.status not in JOB_TERMINAL_STATES:
            job.status = JobStatus.CANCELLED
            job.finished_at = datetime.now(UTC)
            job.result_ref = {
                "run_id": run.run_id,
                "state": BacktestRunState.CANCELLED.value,
                "result_id": None,
            }
    _emit_cancellation_audit(
        session,
        actor,
        run=run,
        event_kind=_CANCELLED_EVENT,
        new_state=BacktestRunState.CANCELLED.value,
        metadata={
            "cancellation_reason": reason,
            "cancelled_at_stage": BacktestRunState.QUEUED.value,
        },
    )
    return {
        "run_id": run.run_id,
        "state": BacktestRunState.CANCELLED.value,
        "cancellation": "cancelled",
        "cancellation_reason": reason,
        "result_id": None,
        "row_version": run.row_version,
    }


def _request_worker_cancellation(
    session: AsyncSession, actor: Actor, *, run: Any
) -> dict[str, Any]:
    """Record a cancel INTENT for a run the worker is actively executing.

    No state transition happens here on purpose: writing ``cancelled`` while the
    worker replays would be exactly the abrupt kill doc 15 §8.4/§12 forbids — the
    worker would keep going and could still materialize a Result. The worker
    honors this flag at its next safe checkpoint and owns the terminal write
    (including the durable job row)."""
    _emit_cancellation_audit(
        session,
        actor,
        run=run,
        event_kind=_CANCEL_REQUESTED_EVENT,
        new_state=str(run.state),
        metadata={
            "requested_at_stage": str(run.state),
            "delivery_policy": _CANCEL_DELIVERY_POLICY,
        },
    )
    return {
        "run_id": run.run_id,
        "state": str(run.state),
        "cancellation": "requested",
        "delivery_policy": _CANCEL_DELIVERY_POLICY,
        "result_id": None,
        "row_version": run.row_version,
    }


def _emit_cancellation_audit(
    session: AsyncSession,
    actor: Actor,
    *,
    run: Any,
    event_kind: str,
    new_state: str,
    metadata: dict[str, Any],
) -> None:
    """The doc 15 §16 cancellation audit event + its SSE outbox twin.

    Attributed to the ACTOR (a human asked for this), unlike the worker's stage
    audits which are attributed to the system service."""
    payload = {
        "run_id": run.run_id,
        "manifest_hash": run.manifest_hash,
        "requested_by_principal_id": run.cancel_requested_by_principal_id,
        **metadata,
    }
    audit_repo.add_audit_event(
        session,
        event_kind=event_kind,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=run.run_id,
        target_entity_type=_RUN_TARGET,
        new_state=new_state,
        correlation_id=actor.correlation_id,
        metadata=payload,
    )
    audit_repo.add_outbox_event(
        session,
        event_type=event_kind,
        resource_type=_RUN_TARGET,
        resource_id=run.run_id,
        payload={"state": new_state, **payload},
        correlation_id=actor.correlation_id,
    )


async def _admit_run(
    session: AsyncSession,
    actor: Actor,
    *,
    composition_id: str,
    expected_fingerprint: str | None,
    ready_report_id: str | None,
    retry_of_run_id: str | None,
    idempotency_key: str | None = None,
    parent_agent_task_id: str | None = None,
    audit_session_factory: AuditSessionFactory | None = None,
) -> dict[str, Any]:
    """Run the admission decision; audit BOTH outcomes (doc 14 §12.2).

    Every typed failure raised inside the body IS the rejection decision, and the
    request tx is rolled back on the resulting 409/422 — so the
    ``run_admission_rejected`` row is written on its own committed connection
    before the error propagates (O-04). ``trace`` carries the facts the body had
    already resolved and that OUTLIVE the rollback — the current fingerprint the
    preflight computed — so the rejection audit can report them even though the
    rejection unwound the body.
    """
    trace: dict[str, Any] = {"report_id": ready_report_id, "current_fingerprint": None}
    try:
        return await _admit_run_body(
            session,
            actor,
            trace,
            composition_id=composition_id,
            expected_fingerprint=expected_fingerprint,
            ready_report_id=ready_report_id,
            retry_of_run_id=retry_of_run_id,
            idempotency_key=idempotency_key,
            parent_agent_task_id=parent_agent_task_id,
        )
    except AppError as rejection:
        await _record_admission_rejected(
            actor,
            composition_id=composition_id,
            expected_fingerprint=expected_fingerprint,
            current_fingerprint=trace["current_fingerprint"],
            report_id=trace["report_id"],
            rejection=rejection,
            retry_of_run_id=retry_of_run_id,
            audit_session_factory=audit_session_factory,
        )
        raise


async def _admit_run_body(
    session: AsyncSession,
    actor: Actor,
    trace: dict[str, Any],
    *,
    composition_id: str,
    expected_fingerprint: str | None,
    ready_report_id: str | None,
    retry_of_run_id: str | None,
    idempotency_key: str | None,
    parent_agent_task_id: str | None,
) -> dict[str, Any]:
    # 1. Mandatory server preflight — nested (key=None pass-through). Raises
    #    CompositionStaleError (409) on an expected_fingerprint mismatch, and
    #    builds the immutable snapshot + report the manifest pins (doc 15 §15).
    preflight = await run_readiness_check(
        session,
        actor,
        composition_id=composition_id,
        expected_fingerprint=expected_fingerprint,
        idempotency_key=None,
        parent_agent_task_id=parent_agent_task_id,
    )
    fingerprint = preflight["composition_fingerprint"]
    # Only the fingerprint is published to the rejection trace. The preflight's OWN
    # report was written in THIS transaction, so a rejection rolls it back — naming
    # its id in a durable audit would leave a dangling reference to a report that
    # never existed. ``trace["report_id"]`` therefore keeps the client-supplied
    # ``ready_report_id``, which came from an earlier COMMITTED check.
    trace["current_fingerprint"] = fingerprint
    if ready_report_id is not None and ready_report_id != preflight["report_id"]:
        await _assert_ready_report_current(session, ready_report_id, composition_id, fingerprint)

    # 2. Any blocker => 422 READINESS_BLOCKED; the whole tx rolls back so no run,
    #    manifest, report or job is left behind (doc 15 §11).
    if preflight["summary"]["blocker_count"] > 0:
        raise _readiness_blocked(preflight["issues"])

    snapshot = await session.get(MainboardCompositionSnapshot, preflight["snapshot_id"])
    if snapshot is None:  # pragma: no cover - snapshot was just written in this tx
        raise CompositionNotFoundError()

    # F-07i (B): pin the approved tick/trade revision for every tick-demanding Strategy
    # NOW, into the immutable manifest — the worker must never resolve 'newest approved'
    # itself (doc 15 §15), and two runs replaying different tick paths must never share
    # an execution_key (INF-04/INF-05).
    tick_data = await _resolve_tick_pins(session, snapshot.item_manifest)

    # K-04: resolve the three doc 15 §9.2 field groups that only exist behind a
    # dereference (strategy/package, external object, data/time) NOW, so the immutable
    # manifest proves WHICH transitive package / dataset / import revisions the run
    # replays. The worker re-resolves these pins fail-closed and never falls back to the
    # current Mainboard, Package Library or a 'latest' dataset row (doc 15 §15).
    context = await resolve_run_manifest_context(session, snapshot.item_manifest)

    run_id = new_id("btrun")
    manifest_id = new_id("btman")
    built = build_run_manifest(
        run_id=run_id,
        composition_id=composition_id,
        composition_snapshot_id=snapshot.snapshot_id,
        composition_fingerprint=fingerprint,
        item_manifest=snapshot.item_manifest,
        capital_mode=snapshot.capital_mode_snapshot,
        requested_by_principal_id=actor.principal_id,
        preflight={
            "ready_report_id": preflight["report_id"],
            "state": preflight["state"],
            "warning_count": preflight["summary"]["warning_count"],
        },
        correlation_id=actor.correlation_id,
        created_at_iso=datetime.now(UTC).isoformat(),
        tick_data=tick_data,
        strategy_package_context=context.strategy_package,
        external_object_context=context.external_objects,
        data_time_context=context.data_time,
    )
    run = await bt_repo.create_run(
        session,
        run_id=run_id,
        workspace_entity_id=composition_id,
        composition_snapshot_id=snapshot.snapshot_id,
        composition_fingerprint=fingerprint,
        manifest_id=manifest_id,
        manifest_hash=built.manifest_hash,
        state=BacktestRunState.QUEUED.value,
        requested_by_principal_id=actor.principal_id,
        ready_report_id=preflight["report_id"],
        retry_of_run_id=retry_of_run_id,
        correlation_id=actor.correlation_id,
    )
    await bt_repo.create_manifest(
        session,
        manifest_id=manifest_id,
        run_id=run_id,
        manifest_hash=built.manifest_hash,
        execution_key=built.execution_key,
        composition_snapshot_id=snapshot.snapshot_id,
        composition_fingerprint=fingerprint,
        engine_version=built.manifest["identity"]["engine_version"],
        manifest=built.manifest,
    )
    job = enqueue_job(
        session,
        queue=_BACKTEST_QUEUE,
        payload={"run_id": run_id},
        actor_principal_id=actor.principal_id,
        correlation_id=actor.correlation_id,
    )
    run.job_id = job.job_id

    _emit_run_audit(
        session,
        actor,
        run=run,
        fingerprint=fingerprint,
        retry_of=retry_of_run_id,
        idempotency_key=idempotency_key,
        parent_agent_task_id=parent_agent_task_id,
    )
    return {
        "run_id": run_id,
        "state": BacktestRunState.QUEUED.value,
        "manifest_hash": built.manifest_hash,
        "composition_fingerprint": fingerprint,
        "ready_report_id": preflight["report_id"],
        "retry_of_run_id": retry_of_run_id,
        "warning_count": preflight["summary"]["warning_count"],
        "job_id": job.job_id,
    }


# --------------------------------------------------------------------------- #
# Result soft delete                                                          #
# --------------------------------------------------------------------------- #


async def soft_delete_backtest_result(
    session: AsyncSession,
    actor: Actor,
    *,
    result_id: str,
    expected_row_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Soft-delete a Result under owner/Admin policy (doc 15 §7, §12).

    Removes it from the active projection; the immutable run manifest + provenance
    are preserved. Admin-only Trash restore/purge is Stage 6."""
    require_authenticated(actor)
    result = await bt_repo.get_result(session, result_id)
    if result is None or result.deletion_state != _ACTIVE:
        raise BacktestResultNotFoundError()
    ensure_can_edit(actor, owner_principal_id=result.created_by_principal_id)

    async def _op() -> dict[str, Any]:
        await session.refresh(result, with_for_update=True)
        if result.deletion_state != _ACTIVE:
            return {"result_id": result_id, "deletion_state": result.deletion_state}
        if expected_row_version is not None and expected_row_version != result.row_version:
            raise RowVersionConflictError()
        result.deletion_state = _SOFT_DELETED
        result.row_version += 1
        # Stage 6c (doc 20 §3.3): the deleted Result becomes an Admin Trash row;
        # the parent Run manifest stays immutable and readable.
        trash_repo.add_trash_entry(
            session,
            entity_id=result_id,
            entity_type=_RESULT_TARGET,
            deleted_by=actor.principal_id,
            reason=None,
            owner_at_deletion=result.created_by_principal_id,
            dependency_snapshot={"run_id": result.run_id, "manifest_hash": result.manifest_hash},
            display_name=result_id,
            original_location=original_location_for(_RESULT_TARGET),
            deletion_snapshot={
                "run_id": result.run_id,
                "manifest_hash": result.manifest_hash,
                "workspace_entity_id": result.workspace_entity_id,
            },
            correlation_id=actor.correlation_id,
        )
        _emit_delete_audit(session, actor, result_id=result_id)
        return {"result_id": result_id, "deletion_state": _SOFT_DELETED}

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "soft_delete_backtest_result",
            "result_id": result_id,
            "expected_row_version": expected_row_version,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


async def _load_workspace(
    session: AsyncSession,
    actor: Actor,
    composition_id: str,
    *,
    operation: str = "request_backtest_run",
    audit_session_factory: AuditSessionFactory | None = None,
) -> Any:
    workspace = await mb_repo.get_workspace(session, composition_id)
    if workspace is None or workspace.deletion_state != DeletionState.ACTIVE:
        raise CompositionNotFoundError()
    try:
        ensure_can_view(
            actor, owner_principal_id=workspace.owner_principal_id, visibility="private"
        )
    except AccessDeniedError as denial:
        # Same event kind the Ready Check surface writes (doc 14 §12.2
        # ``readiness_access_denied``), distinguished by ``operation`` — the RUN
        # surface is the other door onto the same composition.
        await record_readiness_access_denied(
            actor,
            composition_id=composition_id,
            operation=operation,
            denial_code=denial.code,
            audit_session_factory=audit_session_factory,
        )
        raise
    return workspace


async def _record_admission_rejected(
    actor: Actor,
    *,
    composition_id: str,
    expected_fingerprint: str | None,
    current_fingerprint: str | None,
    report_id: str | None,
    rejection: AppError,
    retry_of_run_id: str | None,
    audit_session_factory: AuditSessionFactory | None,
) -> None:
    """Persist the doc 14 §12.2 ``run_admission_rejected`` audit DURABLY (O-04).

    Carries the full §12.2 field set: actor (via the durable writer), composition
    id, expected/current fingerprint, nullable report id, response code and issue
    summary, correlation id. The summary is capped so a composition with hundreds
    of blockers cannot bloat one audit row; the authoritative per-issue detail
    already lives on the report the preflight wrote (when it got that far).
    """
    details = rejection.details[:_ISSUE_SUMMARY_LIMIT]
    await record_durable_audit(
        actor,
        event_kind=_ADMISSION_REJECTED_EVENT,
        target_entity_id=composition_id,
        target_entity_type=_WORKSPACE_TARGET,
        new_state=rejection.code,
        reason=rejection.code.lower(),
        metadata={
            "response_code": rejection.code,
            "http_status": rejection.http_status,
            "expected_fingerprint": expected_fingerprint,
            "current_fingerprint": current_fingerprint,
            "ready_report_id": report_id,
            "retry_of_run_id": retry_of_run_id,
            "issue_summary": [
                {"code": item.get("code"), "scope_id": item.get("scope_id")} for item in details
            ],
            "issue_count": len(rejection.details),
        },
        audit_session_factory=audit_session_factory,
    )


def _idempotency_key_hash(idempotency_key: str | None) -> str | None:
    """Hash the client's Idempotency-Key for the admission audit (doc 14 §12.2).

    The key is client-chosen and can carry meaning (an order ref, a user id); the
    audit only needs to CORRELATE two admissions, so the digest is stored and the
    raw value never is — the same discipline as ``auth._username_hint``.
    """
    if idempotency_key is None:
        return None
    return f"sha256:{hashlib.sha256(idempotency_key.encode('utf-8')).hexdigest()}"


async def _assert_ready_report_current(
    session: AsyncSession,
    ready_report_id: str,
    composition_id: str,
    current_fingerprint: str,
) -> None:
    report = await readiness_repo.get_report(session, ready_report_id)
    if (
        report is None
        or report.workspace_entity_id != composition_id
        or report.composition_fingerprint != current_fingerprint
    ):
        raise ReadyReportStaleError()


async def _resolve_tick_pins(
    session: AsyncSession, item_manifest: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Pin the approved tick/trade revision for every tick-demanding Strategy (F-07i B).

    The manifest must carry EVERY input the worker replays: resolving 'newest approved'
    at worker time would be a 'latest' leak (doc 15 §15) and would let two runs sharing
    an ``execution_key`` replay different tick paths (INF-04/INF-05). Ready Check —
    same tx, just passed with zero blockers — already proved availability via the same
    ``find_approved_tick_revision_for_instrument`` probe; a requirement that STILL
    fails to resolve here (a racing approval revocation) is a hard 422 admission
    reject, never a silently tickless run. ``None`` when no enabled Strategy demands
    tick data — the manifest then carries an explicit ``tick_data: null``."""
    pins: dict[str, Any] = {}
    raw = item_manifest.get("items", []) if isinstance(item_manifest, dict) else []
    for entry in raw:
        if entry.get("kind") != MainboardItemKind.STRATEGY or entry.get("enabled") is False:
            continue
        revision_id = entry.get("revision_id")
        if revision_id is None:
            continue
        revision = await mb_repo.get_work_object_revision(session, str(revision_id))
        if revision is None:
            continue
        payload = await _resolve_strategy_payload(session, dict(revision.payload))
        try:
            config = StrategyConfig.model_validate(payload)
        except PydanticValidationError:
            continue  # readiness STRATEGY_CONFIG_INVALID already gates this upstream
        if not tick_data_required(config):
            continue
        tick_revision = await market_repo.find_approved_tick_revision_for_instrument(
            session, config.data.instrument_id
        )
        if tick_revision is None:
            raise _readiness_blocked(
                [
                    {
                        "code": ReadinessIssueCode.TICK_DATA_UNAVAILABLE.value,
                        "severity": ReadinessSeverity.BLOCKER.value,
                        "scope": ReadinessScope.MARKET_DATA.value,
                        "field_path": "data.intrabar_policy.tick_policy",
                        "scope_id": str(entry.get("item_id")),
                        "message": (
                            "The strategy requires tick data but no approved tick/trade "
                            "dataset could be pinned for its instrument at admission."
                        ),
                        "remediation": (
                            "Import and approve a tick/trade dataset for the strategy's "
                            "instrument, or switch the intrabar policy off tick data."
                        ),
                    }
                ]
            )
        pins[str(entry.get("item_id"))] = {
            "tick_revision_id": tick_revision.revision_id,
            "instrument_id": config.data.instrument_id,
        }
    return pins or None


def _issue_detail(issue: dict[str, Any]) -> dict[str, Any]:
    # ``remediation`` is the actionable half of a readiness finding (doc 14 §3.2);
    # dropping it here used to strand it inside the report while the HTTP caller
    # only saw the symptom (O-02).
    return {
        "code": issue.get("code"),
        "severity": issue.get("severity"),
        "scope": issue.get("scope"),
        "field": issue.get("field_path"),
        "scope_id": issue.get("scope_id"),
        "message": issue.get("message"),
        "remediation": issue.get("remediation"),
    }


def _readiness_blocked(issues: list[dict[str, Any]]) -> ReadinessBlockedError:
    """Build the 422 from a preflight result, lifting the first blocker's scope and
    remediation onto the envelope itself (doc 01 §11.2, doc 04 §11.1).

    ``details`` still carries every issue; the promoted fields let a client act on
    the leading blocker without parsing the list.
    """
    blockers = [i for i in issues if i.get("severity") == ReadinessSeverity.BLOCKER.value]
    lead = blockers[0] if blockers else None
    return ReadinessBlockedError(
        details=[_issue_detail(issue) for issue in issues],
        remediation=lead.get("remediation") if lead else None,
        scope_type=str(lead["scope"]) if lead and lead.get("scope") else None,
        scope_id=str(lead["scope_id"]) if lead and lead.get("scope_id") else None,
        field_path=str(lead["field_path"]) if lead and lead.get("field_path") else None,
    )


def _emit_run_audit(
    session: AsyncSession,
    actor: Actor,
    *,
    run: Any,
    fingerprint: str,
    retry_of: str | None,
    idempotency_key: str | None = None,
    parent_agent_task_id: str | None = None,
) -> None:
    """Audit the ACCEPTED admission + the queue fan-out (doc 14 §12.2, doc 15 §7).

    ``run_admission_accepted`` is the doc 14 §12.2 event and carries the fields
    only admission knows: the idempotency-key DIGEST (never the raw key), the
    parent Agent task id, and the queue/outbox outcome that proves the run was
    actually handed to the durable job row rather than merely written. The
    existing ``run_requested`` / ``run_queued`` pair is untouched in taxonomy and
    simply shares the same enriched metadata.
    """
    metadata = {
        "manifest_hash": run.manifest_hash,
        "composition_fingerprint": fingerprint,
        "ready_report_id": run.ready_report_id,
        "retry_of_run_id": retry_of,
        "job_id": run.job_id,
        "idempotency_key_hash": _idempotency_key_hash(idempotency_key),
        "parent_agent_task_id": parent_agent_task_id,
        "queue_outcome": {"queue": _BACKTEST_QUEUE, "job_id": run.job_id},
        "outbox_outcome": "backtest.run_queued",
    }
    for event_kind in (_ADMISSION_ACCEPTED_EVENT, "backtest.run_requested", "backtest.run_queued"):
        audit_repo.add_audit_event(
            session,
            event_kind=event_kind,
            actor_principal_id=actor.principal_id,
            actor_kind=actor.actor_kind,
            target_entity_id=run.run_id,
            target_entity_type=_RUN_TARGET,
            new_state=run.state,
            correlation_id=actor.correlation_id,
            metadata=metadata,
        )
    audit_repo.add_outbox_event(
        session,
        event_type="backtest.run_queued",
        resource_type=_RUN_TARGET,
        resource_id=run.run_id,
        payload={
            "run_id": run.run_id,
            "state": run.state,
            "manifest_hash": run.manifest_hash,
            "composition_fingerprint": fingerprint,
            "job_id": run.job_id,
            "retry_of_run_id": retry_of,
        },
        correlation_id=actor.correlation_id,
    )


def _emit_delete_audit(session: AsyncSession, actor: Actor, *, result_id: str) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind="backtest.result_soft_deleted",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=result_id,
        target_entity_type=_RESULT_TARGET,
        new_state=_SOFT_DELETED,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="backtest.result_soft_deleted",
        resource_type=_RESULT_TARGET,
        resource_id=result_id,
        payload={"result_id": result_id, "deletion_state": _SOFT_DELETED},
        correlation_id=actor.correlation_id,
    )


__all__ = [
    "cancel_backtest_run",
    "request_backtest_run",
    "retry_backtest_run",
    "soft_delete_backtest_result",
]
