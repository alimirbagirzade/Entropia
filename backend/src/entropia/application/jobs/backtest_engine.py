"""Backtest engine worker body (Stage 5a, doc 15 §8.3, §9.3, §15).

Runs on the ``backtest`` queue. The durable ``jobs`` row + the ``backtest_run`` row
are the source of truth — the request that admitted the run has long since returned
(CR-09); browser close / logout never cancels it (doc 15 §8.2). Steps:

    load job + run + immutable manifest -> mark RUNNING ->
    RE-RESOLVE every pinned revision from the manifest (NO 'latest' fallback;
        any unresolved pin => terminal FAILED, doc 15 §11, §15) ->
    run the deterministic engine (``domain.backtest.engine``) ->
    ONLY on success: materialize the immutable Result + summary + metrics +
        artifacts (CR-03), back-fill run.result_id, run -> SUCCEEDED ->
    audit + outbox.

A FAILED run is a normal recorded terminal outcome (diagnostics only, no Result,
no history row), NOT a job exception — so the worker does not retry a permanent
manifest-resolution failure. Only an unexpected/missing-row condition raises.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.backtest.engine import run_engine
from entropia.domain.backtest.enums import (
    RUN_TERMINAL_STATES,
    BacktestRunState,
    RunFailureCode,
)
from entropia.domain.backtest.metrics import derive_metric_values
from entropia.domain.lifecycle.enums import ActorKind, JobStatus
from entropia.infrastructure.postgres.models import Job
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo

_DEFAULT_CAPITAL = Decimal("10000")
_RUN_TARGET = "backtest_run"
_RESULT_TARGET = "backtest_result"


async def run_backtest(session: AsyncSession, job_id: str) -> dict[str, Any]:
    """Execute the durable backtest job. Does not commit (the worker scope commits)."""
    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError(f"Job '{job_id}' not found.")
    run_id = str((job.payload or {}).get("run_id"))
    run = await bt_repo.get_run(session, run_id)
    if run is None:
        raise ValueError(f"Backtest run '{run_id}' not found for job '{job_id}'.")
    manifest = await bt_repo.get_manifest_by_run(session, run_id)
    if manifest is None:
        raise ValueError(f"Backtest manifest for run '{run_id}' not found.")

    # At-least-once delivery guard: a redelivered message for an already-terminal
    # run must NOT re-run the engine (a second create_result would violate
    # UNIQUE(backtest_result.run_id)). Return the durable outcome unchanged.
    if run.state in RUN_TERMINAL_STATES:
        return _terminal_ref(run)

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    run.state = BacktestRunState.PROVISIONING
    run.started_at = datetime.now(UTC)

    # Re-resolve pins while still PROVISIONING; advance to RUNNING only when the
    # manifest fully resolves, so the fail path never transits through RUNNING.
    missing = await _unresolved_pins(session, manifest.manifest)
    if missing:
        return _fail_run(
            session,
            job,
            run,
            code=RunFailureCode.MANIFEST_RESOLUTION,
            message=f"Pinned revisions could not be resolved (no 'latest' fallback): {missing}",
        )
    run.state = BacktestRunState.RUNNING

    initial_capital = _initial_capital(manifest.manifest.get("capital_execution"))
    item_count = len(manifest.manifest.get("mainboard_items", []))
    output = run_engine(
        manifest.execution_key, initial_capital=initial_capital, item_count=item_count
    )
    metric_values = derive_metric_values(output.summary)

    result = await bt_repo.create_result(
        session,
        run=run,
        manifest=manifest,
        engine_output=output,
        metric_values=metric_values,
    )
    run.result_id = result.result_id
    run.state = BacktestRunState.SUCCEEDED
    run.finished_at = datetime.now(UTC)

    _emit_success_audit(session, run=run, result_id=result.result_id)
    job.status = JobStatus.SUCCEEDED
    job.finished_at = datetime.now(UTC)
    result_ref = {
        "run_id": run_id,
        "state": BacktestRunState.SUCCEEDED.value,
        "result_id": result.result_id,
        "manifest_hash": run.manifest_hash,
    }
    job.result_ref = result_ref
    return result_ref


async def _unresolved_pins(session: AsyncSession, manifest: dict[str, Any]) -> list[str]:
    """Every pinned revision that no longer resolves (soft-deleted / missing).

    The worker reads ONLY the manifest; it never falls back to the current
    Mainboard or a 'latest' revision (doc 15 §15)."""
    missing: list[str] = []
    for item in manifest.get("mainboard_items", []):
        revision_id = item.get("selected_revision_id")
        if revision_id is None:
            missing.append(str(item.get("item_id")))
            continue
        revision = await mb_repo.get_work_object_revision(session, str(revision_id))
        if revision is None:
            missing.append(str(revision_id))
    return missing


def _initial_capital(capital_mode: Any) -> Decimal:
    if isinstance(capital_mode, dict) and capital_mode.get("enabled"):
        config = capital_mode.get("config")
        initial = config.get("initial_capital") if isinstance(config, dict) else None
        amount = initial.get("amount") if isinstance(initial, dict) else None
        if amount is not None:
            try:
                return Decimal(str(amount))
            except (InvalidOperation, ValueError):
                return _DEFAULT_CAPITAL
    return _DEFAULT_CAPITAL


def _fail_run(
    session: AsyncSession,
    job: Job,
    run: Any,
    *,
    code: RunFailureCode,
    message: str,
) -> dict[str, Any]:
    run.state = BacktestRunState.FAILED
    run.failure_code = code.value
    run.failure_message = message
    run.finished_at = datetime.now(UTC)
    _emit_failure_audit(session, run=run, code=code)
    # The job itself completed (it produced a terminal run); a permanent manifest
    # failure is not retried by re-running the same job (doc 15 §11 — retry is a
    # new run via RetryBacktestRun).
    job.status = JobStatus.SUCCEEDED
    job.finished_at = datetime.now(UTC)
    result_ref = {
        "run_id": run.run_id,
        "state": BacktestRunState.FAILED.value,
        "failure_code": code.value,
        "result_id": None,
    }
    job.result_ref = result_ref
    return result_ref


def _terminal_ref(run: Any) -> dict[str, Any]:
    """Durable outcome for an already-terminal run (redelivery-safe; no re-run)."""
    return {
        "run_id": run.run_id,
        "state": str(run.state),
        "result_id": run.result_id,
        "failure_code": run.failure_code,
    }


def _emit_success_audit(session: AsyncSession, *, run: Any, result_id: str) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind="backtest.run_succeeded",
        actor_principal_id=run.requested_by_principal_id,
        actor_kind=ActorKind.SYSTEM_SERVICE,
        target_entity_id=run.run_id,
        target_entity_type=_RUN_TARGET,
        new_state=str(run.state),
        correlation_id=run.correlation_id,
        metadata={"manifest_hash": run.manifest_hash, "result_id": result_id},
    )
    audit_repo.add_audit_event(
        session,
        event_kind="backtest.result_materialized",
        actor_principal_id=run.requested_by_principal_id,
        actor_kind=ActorKind.SYSTEM_SERVICE,
        target_entity_id=result_id,
        target_entity_type=_RESULT_TARGET,
        new_state=result_id,
        correlation_id=run.correlation_id,
        metadata={"manifest_hash": run.manifest_hash, "run_id": run.run_id},
    )
    audit_repo.add_outbox_event(
        session,
        event_type="backtest.result_materialized",
        resource_type=_RESULT_TARGET,
        resource_id=result_id,
        payload={
            "result_id": result_id,
            "run_id": run.run_id,
            "manifest_hash": run.manifest_hash,
            "composition_fingerprint": run.composition_fingerprint,
        },
        correlation_id=run.correlation_id,
    )


def _emit_failure_audit(session: AsyncSession, *, run: Any, code: RunFailureCode) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind="backtest.run_failed",
        actor_principal_id=run.requested_by_principal_id,
        actor_kind=ActorKind.SYSTEM_SERVICE,
        target_entity_id=run.run_id,
        target_entity_type=_RUN_TARGET,
        new_state=run.state,
        correlation_id=run.correlation_id,
        metadata={"failure_code": code.value},
    )
    audit_repo.add_outbox_event(
        session,
        event_type="backtest.run_failed",
        resource_type=_RUN_TARGET,
        resource_id=run.run_id,
        payload={"run_id": run.run_id, "state": run.state, "failure_code": code.value},
        correlation_id=run.correlation_id,
    )


__all__ = ["run_backtest"]
