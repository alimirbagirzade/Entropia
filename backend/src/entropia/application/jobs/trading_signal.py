"""Trading Signal import job body (Stage 3c, doc 04 §7, §9.3, §9.4).

Runs on the ``data`` queue. Steps:

    load job + source asset -> read raw bytes (object storage) -> parse CSV/TXT ->
    normalize + time-safe validate (pure ``domain.trading_signal.events``) ->
    write an immutable ``normalized_signal_event_revision`` (accepted events +
    skipped-row report + evidence + content hash) -> advance the durable job.

The pure decision logic lives in ``domain.trading_signal.events``; this module only
wires object storage + persistence around it, so it is importable without a live
broker or MinIO (the S3 read is a local import). The ``jobs`` row is the source of
truth — the request that enqueued it has long since returned (CR-09).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import ActorKind, JobStatus
from entropia.domain.trading_signal.events import (
    ImportOutcome,
    events_content_hash,
    normalize_signal_rows,
    parse_delimited,
)
from entropia.infrastructure.postgres.models import Job
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import trading_signal as ts_repo

_TARGET_TYPE = "source_asset"


async def run_import(session: AsyncSession, job_id: str) -> dict[str, Any]:
    """Execute the durable signal-import job. The ``jobs`` row is the source of truth.

    Returns a JSON-safe result reference. Does not commit (the worker session scope
    commits). A source asset that cannot be read is a hard error (the worker retries
    per Dramatiq policy); a parse that runs but accepts no events writes a FAILED
    normalized revision with the skipped-row evidence (not an exception).
    """
    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError(f"Job '{job_id}' not found.")
    payload = job.payload or {}
    source_asset_id = str(payload.get("source_asset_id"))
    instrument_id = str(payload.get("instrument_id"))
    source_timezone = str(payload.get("source_timezone") or "UTC")
    import_mapping = _coerce_mapping(payload.get("import_mapping"))

    asset = await ts_repo.get_source_asset(session, source_asset_id)
    if asset is None:
        raise ValueError(f"Source asset '{source_asset_id}' not found for import.")

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)

    data = _read_bytes(asset.object_key)
    columns, rows = parse_delimited(data)
    outcome = normalize_signal_rows(
        columns,
        rows,
        source_timezone=source_timezone,
        instrument_id=instrument_id,
        import_mapping=import_mapping,
    )

    content_hash = events_content_hash(outcome.accepted)
    normalized = await ts_repo.create_normalized_revision(
        session,
        source_asset_id=source_asset_id,
        job_id=job_id,
        status=outcome.status,
        instrument_id=instrument_id,
        accepted_count=outcome.accepted_count,
        skipped_count=outcome.skipped_count,
        events=[asdict(event) for event in outcome.accepted],
        skipped_rows=[asdict(skipped) for skipped in outcome.skipped],
        validation_summary=_summary(outcome, source_timezone),
        earliest_available_time=outcome.earliest_available_time,
        content_hash=content_hash,
        created_by_principal_id=job.actor_principal_id,
    )

    audit_repo.add_audit_event(
        session,
        event_kind="trading_signal.import_completed",
        actor_principal_id=job.actor_principal_id,
        actor_kind=ActorKind.SYSTEM_SERVICE,
        target_entity_id=source_asset_id,
        target_entity_type=_TARGET_TYPE,
        new_state=str(outcome.status),
        correlation_id=job.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="trading_signal.import_completed",
        resource_type=_TARGET_TYPE,
        resource_id=source_asset_id,
        payload={
            "normalized_event_revision_id": normalized.normalized_revision_id,
            "status": str(outcome.status),
            "accepted_count": outcome.accepted_count,
            "skipped_count": outcome.skipped_count,
        },
        correlation_id=job.correlation_id,
    )

    job.status = JobStatus.SUCCEEDED
    job.finished_at = datetime.now(UTC)
    result = {
        "source_asset_id": source_asset_id,
        "normalized_event_revision_id": normalized.normalized_revision_id,
        "status": str(outcome.status),
        "accepted_count": outcome.accepted_count,
        "skipped_count": outcome.skipped_count,
        "blocker_code": outcome.blocker_code,
        "mapping_hash": outcome.mapping_hash,
    }
    job.result_ref = result
    return result


def _coerce_mapping(raw: Any) -> dict[str, str] | None:
    """Read a ``{canonical_field: source_header}`` mapping from the durable payload.

    The job payload is JSON, so an absent/malformed mapping degrades to ``None``
    (no mapping) rather than raising — the parser then relies on exact/aliased
    headers exactly as before.
    """
    if not isinstance(raw, dict):
        return None
    mapping = {str(k): str(v) for k, v in raw.items() if v is not None and str(v).strip()}
    return mapping or None


def _summary(outcome: ImportOutcome, source_timezone: str) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "source_timezone": source_timezone,
        "instrument_id": outcome.instrument_id,
        "accepted_count": outcome.accepted_count,
        "skipped_count": outcome.skipped_count,
        "blocker_code": outcome.blocker_code,
        "earliest_available_time": (
            outcome.earliest_available_time.isoformat()
            if outcome.earliest_available_time is not None
            else None
        ),
    }
    if outcome.mapping_hash is not None:
        summary["mapping_hash"] = outcome.mapping_hash
        summary["resolved_mapping"] = outcome.resolved_mapping
    return summary


def _read_bytes(object_key: str) -> bytes:
    """Read raw source bytes from object storage (isolated for monkeypatching)."""
    from entropia.infrastructure.s3.datasets import get_raw_bytes

    return get_raw_bytes(object_key)
