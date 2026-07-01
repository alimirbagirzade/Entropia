"""Backtest RUN admission + retry + result soft-delete (Stage 5a, doc 15 §7-§9, §15).

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
``application/jobs/backtest_engine``. Retry never resets the original run — it
re-admits the CURRENT composition with a new run_id + manifest + ``retry_of_run_id``
(doc 15 §7, §8.4). Result soft-delete flips a local flag under owner/Admin policy +
``expected_row_version`` (409 on stale); Admin Trash restore/purge is Stage 6.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands.readiness_check import run_readiness_check
from entropia.application.idempotency import run_idempotent
from entropia.domain.backtest.enums import RUN_RETRYABLE_STATES, BacktestRunState
from entropia.domain.backtest.manifest import build_run_manifest
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_edit, ensure_can_view, require_authenticated
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.models import MainboardCompositionSnapshot
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import readiness as readiness_repo
from entropia.infrastructure.queues.enqueue import enqueue_job
from entropia.shared.errors import (
    BacktestResultNotFoundError,
    BacktestRunNotFoundError,
    CompositionNotFoundError,
    ReadinessBlockedError,
    ReadyReportStaleError,
    RowVersionConflictError,
    RunNotRetryableError,
)
from entropia.shared.ids import new_id

_RUN_TARGET = "backtest_run"
_RESULT_TARGET = "backtest_result"
_BACKTEST_QUEUE = "backtest"
_ACTIVE = "active"
_SOFT_DELETED = "soft_deleted"


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
) -> dict[str, Any]:
    """Admit a backtest run for the current composition (doc 15 §7, §8.2)."""
    require_authenticated(actor)
    await _load_workspace(session, actor, composition_id)

    async def _op() -> dict[str, Any]:
        return await _admit_run(
            session,
            actor,
            composition_id=composition_id,
            expected_fingerprint=expected_fingerprint,
            ready_report_id=ready_report_id,
            retry_of_run_id=None,
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
) -> dict[str, Any]:
    """Retry a terminal FAILED/CANCELLED run against the CURRENT composition.

    Never mutates the original run (immutable, historical); creates a new run_id +
    manifest hash + ``retry_of_run_id`` link (doc 15 §7, §8.4)."""
    require_authenticated(actor)
    original = await bt_repo.get_run(session, run_id)
    if original is None:
        raise BacktestRunNotFoundError()
    composition_id = original.workspace_entity_id
    await _load_workspace(session, actor, composition_id)

    async def _op() -> dict[str, Any]:
        if original.state not in RUN_RETRYABLE_STATES:
            raise RunNotRetryableError()
        return await _admit_run(
            session,
            actor,
            composition_id=composition_id,
            expected_fingerprint=None,
            ready_report_id=None,
            retry_of_run_id=original.run_id,
        )

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "retry_backtest_run", "run_id": run_id},
        operation=_op,
    )


async def _admit_run(
    session: AsyncSession,
    actor: Actor,
    *,
    composition_id: str,
    expected_fingerprint: str | None,
    ready_report_id: str | None,
    retry_of_run_id: str | None,
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
    )
    fingerprint = preflight["composition_fingerprint"]
    if ready_report_id is not None and ready_report_id != preflight["report_id"]:
        await _assert_ready_report_current(session, ready_report_id, composition_id, fingerprint)

    # 2. Any blocker => 422 READINESS_BLOCKED; the whole tx rolls back so no run,
    #    manifest, report or job is left behind (doc 15 §11).
    if preflight["summary"]["blocker_count"] > 0:
        raise ReadinessBlockedError(details=[_issue_detail(issue) for issue in preflight["issues"]])

    snapshot = await session.get(MainboardCompositionSnapshot, preflight["snapshot_id"])
    if snapshot is None:  # pragma: no cover - snapshot was just written in this tx
        raise CompositionNotFoundError()

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

    _emit_run_audit(session, actor, run=run, fingerprint=fingerprint, retry_of=retry_of_run_id)
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


async def _load_workspace(session: AsyncSession, actor: Actor, composition_id: str) -> Any:
    workspace = await mb_repo.get_workspace(session, composition_id)
    if workspace is None or workspace.deletion_state != DeletionState.ACTIVE:
        raise CompositionNotFoundError()
    ensure_can_view(actor, owner_principal_id=workspace.owner_principal_id, visibility="private")
    return workspace


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


def _issue_detail(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": issue.get("code"),
        "severity": issue.get("severity"),
        "scope": issue.get("scope"),
        "field": issue.get("field_path"),
        "scope_id": issue.get("scope_id"),
        "message": issue.get("message"),
    }


def _emit_run_audit(
    session: AsyncSession,
    actor: Actor,
    *,
    run: Any,
    fingerprint: str,
    retry_of: str | None,
) -> None:
    metadata = {
        "manifest_hash": run.manifest_hash,
        "composition_fingerprint": fingerprint,
        "ready_report_id": run.ready_report_id,
        "retry_of_run_id": retry_of,
        "job_id": run.job_id,
    }
    for event_kind in ("backtest.run_requested", "backtest.run_queued"):
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
    "request_backtest_run",
    "retry_backtest_run",
    "soft_delete_backtest_result",
]
