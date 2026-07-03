"""Backtest engine worker body (Stage 5a → post-V1 Slice B, doc 15 §8.3, §9.3, §15).

Runs on the ``backtest`` queue. The durable ``jobs`` row + the ``backtest_run`` row
are the source of truth — the request that admitted the run has long since returned
(CR-09); browser close / logout never cancels it (doc 15 §8.2). Steps:

    load job + run + immutable manifest -> mark RUNNING ->
    RE-RESOLVE every pinned revision from the manifest (NO 'latest' fallback;
        any unresolved pin => terminal FAILED, doc 15 §11, §15) ->
    resolve the primary Strategy's pinned config + its pinned market revision's
        processed bar source (INF-12); a missing asset => terminal FAILED ->
    bar-replay the deterministic engine (``domain.backtest.engine``) over the
        streamed OHLCV batches (bounded memory) ->
    ONLY on success: materialize the immutable Result + summary + metrics +
        artifacts (CR-03), back-fill run.result_id, run -> SUCCEEDED ->
    audit + outbox.

A FAILED run is a normal recorded terminal outcome (diagnostics only, no Result,
no history row), NOT a job exception — so the worker does not retry a permanent
manifest/asset/engine failure. Only an unexpected/missing-row condition raises.

Bars are injected via ``stream_bars`` (default: the real S3-backed
``iter_bar_batches``) so integration tests exercise the full resolve → replay →
materialize chain without object storage.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.queries.market_bars import (
    BarSourceRef,
    iter_bar_batches,
    resolve_bar_source,
)
from entropia.domain.backtest.engine import run_engine
from entropia.domain.backtest.enums import (
    RUN_TERMINAL_STATES,
    BacktestRunState,
    RunFailureCode,
)
from entropia.domain.backtest.metrics import derive_metric_values
from entropia.domain.lifecycle.enums import ActorKind, JobStatus
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.strategy.config import StrategyConfig
from entropia.infrastructure.postgres.models import Job
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import strategy as strat_repo
from entropia.shared.errors import NotFoundError

_RUN_TARGET = "backtest_run"
_RESULT_TARGET = "backtest_result"

# The worker owns the bar-source I/O boundary; the engine itself never touches S3.
BarBatchStreamer = Callable[[BarSourceRef], Iterator[list[dict[str, Any]]]]


async def run_backtest(
    session: AsyncSession,
    job_id: str,
    *,
    stream_bars: BarBatchStreamer = iter_bar_batches,
) -> dict[str, Any]:
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
    # manifest fully resolves AND the bar source is available, so the fail path
    # never transits through RUNNING.
    missing = await _unresolved_pins(session, manifest.manifest)
    if missing:
        return _fail_run(
            session,
            job,
            run,
            code=RunFailureCode.MANIFEST_RESOLUTION,
            message=f"Pinned revisions could not be resolved (no 'latest' fallback): {missing}",
        )

    strategy_config = await _resolve_primary_strategy(session, manifest.manifest)
    if strategy_config is None:
        return _fail_run(
            session,
            job,
            run,
            code=RunFailureCode.ASSET_UNAVAILABLE,
            message="No enabled Strategy item with a resolvable pinned config in the composition.",
        )
    market_revision_id = strategy_config.data.market_dataset_revision_id
    try:
        source = await resolve_bar_source(session, market_revision_id=market_revision_id)
    except NotFoundError:
        return _fail_run(
            session,
            job,
            run,
            code=RunFailureCode.ASSET_UNAVAILABLE,
            message=f"Pinned market revision '{market_revision_id}' has no processed bar asset.",
        )

    run.state = BacktestRunState.RUNNING

    item_count = len(manifest.manifest.get("mainboard_items", []))
    try:
        output = run_engine(
            strategy_config=strategy_config,
            bar_batches=stream_bars(source),
            execution_key=manifest.execution_key,
            item_count=item_count,
        )
    except Exception as exc:
        return _fail_run(
            session,
            job,
            run,
            code=RunFailureCode.ENGINE_ERROR,
            message=f"Engine error during bar-replay: {exc}",
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


async def _resolve_primary_strategy(
    session: AsyncSession, manifest: dict[str, Any]
) -> StrategyConfig | None:
    """Resolve the first enabled Strategy item's pinned, typed StrategyConfig.

    Foundation scope: a single-strategy bar-replay. Items are already pin-ordered
    (doc 01 §5.2); the first enabled Strategy whose pinned revision parses to a
    valid config drives the simulation. Reads ONLY pinned revisions."""
    for item in manifest.get("mainboard_items", []):
        if item.get("item_kind") != MainboardItemKind.STRATEGY:
            continue
        if item.get("enabled") is False:
            continue
        revision_id = item.get("selected_revision_id")
        if revision_id is None:
            continue
        revision = await mb_repo.get_work_object_revision(session, str(revision_id))
        if revision is None:
            continue
        payload = await _resolve_strategy_payload(session, dict(revision.payload))
        try:
            return StrategyConfig.model_validate(payload)
        except ValidationError:
            continue
    return None


async def _resolve_strategy_payload(
    session: AsyncSession, payload: dict[str, Any]
) -> dict[str, Any]:
    """Dereference a Strategy-editor MIRROR pin to its typed canonical config.

    Twin of ``readiness_check._resolve_strategy_payload`` (doc 02 §7.1): a strategy
    Mainboard item pins either a direct StrategyConfig or the mirror work-object
    revision (``{"strategy_revision_id", ...}``). The engine must replay the REAL
    immutable configuration, so the mirror is dereferenced here; an unresolvable
    mirror falls through unchanged and fails config parse visibly."""
    mirror_ref = payload.get("strategy_revision_id")
    if not mirror_ref:
        return payload
    revision = await strat_repo.get_strategy_revision(session, str(mirror_ref))
    if revision is None:
        return payload
    return dict(revision.payload)


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


__all__ = ["BarBatchStreamer", "run_backtest"]
