"""Market-data analysis job body (decision D4/D5/D6, doc 11 analysis flow).

Runs on the ``data`` queue. Steps:

    load job + raw asset -> parse (Polars) -> deterministic schema map ->
    normalize -> validate (domain rules) -> write processed Parquet ->
    write validation run + issues -> advance revision_state -> manifest hash.

The pure decision logic (``evaluate_rows``, ``decide_outcome``) takes already
parsed/normalized rows and is unit-testable with no infra. The orchestrator
(``run_analysis``) wires the S3/Polars helpers behind it and is importable
without a live broker or MinIO (heavy imports are local to the functions that
need them).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.jobs.delivery import claim_job_for_delivery
from entropia.domain.lifecycle.enums import JobStatus, ValidationStatus
from entropia.domain.market_data.enums import (
    MarketDataType,
    MarketRevisionState,
    TimezoneMode,
    TradeSide,
)
from entropia.domain.market_data.schema_mapping import propose_schema_mapping
from entropia.domain.market_data.state_machine import next_market_revision_state
from entropia.domain.market_data.validation_rules import (
    OhlcvRow,
    SpreadRow,
    TickRow,
    evaluate_cross_row,
    resolve_timestamp,
    validate_ohlcv_row,
    validate_spread_row,
    validate_tick_row,
)
from entropia.infrastructure.postgres.models import MarketDatasetRevision
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.shared.manifest import manifest_hash

# Severity ordering for aggregation; the worst row severity decides the outcome.
_SEVERITY_RANK: dict[ValidationStatus, int] = {
    ValidationStatus.PASS: 0,
    ValidationStatus.WARNING: 1,
    ValidationStatus.BLOCKING_FAIL: 2,
}

# The canonical normalized-row field holding the record time (schema_mapping target).
_TIMESTAMP_FIELD = "timestamp"


@dataclass(frozen=True, slots=True)
class AnalysisOutcome:
    """Aggregate result of validating a revision's rows."""

    status: ValidationStatus
    rows_checked: int
    counts: dict[str, int]
    next_state: MarketRevisionState


@dataclass(slots=True)
class ParsedDataset:
    """Normalized rows extracted from a raw asset, ready for validation."""

    market_data_type: MarketDataType
    columns: list[str]
    rows: list[dict[str, Any]]
    coverage: list[dict[str, Any]] = field(default_factory=list)


# Injection seams (mirror the backtest engine's ``stream_bars``): the S3/Polars
# steps are swappable so ``run_analysis`` is exercisable end-to-end against a real
# DB without MinIO. Production callers pass neither and get the real helpers.
_LoadAndParse = Callable[[AsyncSession, str, "MarketDatasetRevision"], Awaitable[ParsedDataset]]
_WriteProcessed = Callable[[AsyncSession, str, str, ParsedDataset], Awaitable[str]]


def _validate_one(market_data_type: MarketDataType, row: dict[str, Any]) -> ValidationStatus:
    if market_data_type == MarketDataType.OHLCV:
        return validate_ohlcv_row(
            OhlcvRow(
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row.get("volume"),
            )
        )
    if market_data_type == MarketDataType.TICK_TRADES:
        side = row.get("side")
        tick = (
            TickRow(price=row["price"], side=TradeSide(side))
            if side is not None
            else TickRow(price=row["price"])
        )
        return validate_tick_row(tick)
    return validate_spread_row(SpreadRow(bid=row["bid"], ask=row["ask"]))


def evaluate_rows(parsed: ParsedDataset) -> AnalysisOutcome:
    """Validate each row and aggregate into a single outcome (pure)."""
    counts = {s.value: 0 for s in ValidationStatus}
    worst = ValidationStatus.PASS
    for row in parsed.rows:
        status = _validate_one(parsed.market_data_type, row)
        counts[status.value] += 1
        if _SEVERITY_RANK[status] > _SEVERITY_RANK[worst]:
            worst = status
    return AnalysisOutcome(
        status=worst,
        rows_checked=len(parsed.rows),
        counts=counts,
        next_state=decide_outcome(worst),
    )


def decide_outcome(worst: ValidationStatus) -> MarketRevisionState:
    """Map the worst row severity to the next revision state (pure).

    blocking_fail -> needs_review (human must inspect; never auto-verified)
    warning       -> needs_review (contextual issues require review)
    pass          -> verified     (clean data is auto-verified, not approved)
    """
    if worst == ValidationStatus.PASS:
        return MarketRevisionState.VERIFIED
    return MarketRevisionState.NEEDS_REVIEW


def revision_source_zone(revision: MarketDatasetRevision) -> ZoneInfo | None:
    """The zone a NAIVE source timestamp is localized in, or ``None`` (K-01).

    The persistence -> domain adapter for the declared timezone: ``utc`` resolves to
    UTC, ``custom`` to its stored IANA identifier, and ``exchange`` to ``None`` (it
    carries no identifier to resolve). ``None`` is FAIL-CLOSED — the parse path then
    refuses naive timestamps instead of assuming UTC (doc 11 §9.1).

    Never raises: a stored identifier that no longer exists in the IANA database
    degrades to ``None`` (an unresolved revision, reported) rather than crashing a
    durable worker job mid-run.
    """
    if revision.timezone_mode == TimezoneMode.UTC:
        return ZoneInfo("UTC")
    if revision.timezone_mode == TimezoneMode.CUSTOM and revision.timezone_iana:
        try:
            return ZoneInfo(revision.timezone_iana)
        except (ZoneInfoNotFoundError, ValueError):
            return None
    return None


def normalize_source_timestamps(
    parsed: ParsedDataset, *, source_zone: ZoneInfo | None
) -> ParsedDataset:
    """Rewrite each row's ``timestamp`` to its canonical UTC instant (K-01, doc 11 §7.3).

    This is the step that makes the DECLARED timezone actually do something: a naive
    source cell is read in ``source_zone`` and stored as an ISO-8601 string carrying
    ``+00:00``, so the processed Parquet — and every engine that later replays it —
    sees the true instant rather than the wall-clock digits.

    A cell that does NOT resolve is left VERBATIM: the normalizer never invents a
    value. The cross-row pass that follows reports it (``MARKET_DATA_TIMEZONE_
    UNRESOLVED`` for a naive cell with no resolvable zone, ``TIMESTAMP_UNRESOLVABLE``
    for a garbage cell) as BLOCKING_FAIL, so the revision lands in NEEDS_REVIEW and
    can never auto-verify into the money-sizing engine.
    """
    rows: list[dict[str, Any]] = []
    for row in parsed.rows:
        if _TIMESTAMP_FIELD not in row:
            rows.append(row)
            continue
        moment = resolve_timestamp(row[_TIMESTAMP_FIELD], source_zone=source_zone).moment
        rows.append(row if moment is None else {**row, _TIMESTAMP_FIELD: moment.isoformat()})
    return ParsedDataset(
        market_data_type=parsed.market_data_type,
        columns=parsed.columns,
        rows=rows,
        coverage=parsed.coverage,
    )


def _parse_raw_bytes(market_data_type: MarketDataType, data: bytes) -> ParsedDataset:
    """Parse CSV/TXT bytes into normalized rows via Polars (D5).

    Imported locally so this module stays import-clean without Polars at module
    load. Columns are mapped deterministically (D7) to canonical field names.
    """
    import io

    import polars as pl

    frame = pl.read_csv(io.BytesIO(data))
    source_columns = list(frame.columns)
    proposal = propose_schema_mapping(market_data_type, source_columns)
    mapping = {k: v for k, v in proposal.proposed.items() if v is not None}

    rows: list[dict[str, Any]] = []
    for record in frame.iter_rows(named=True):
        normalized = {field: record[col] for field, col in mapping.items()}
        rows.append(normalized)
    return ParsedDataset(market_data_type=market_data_type, columns=source_columns, rows=rows)


def _to_parquet_bytes(parsed: ParsedDataset) -> bytes:
    import io

    import polars as pl

    buffer = io.BytesIO()
    pl.DataFrame(parsed.rows).write_parquet(buffer)
    return buffer.getvalue()


async def run_analysis(
    session: AsyncSession,
    job_id: str,
    *,
    load_and_parse: _LoadAndParse | None = None,
    write_processed: _WriteProcessed | None = None,
) -> dict[str, Any]:
    """Execute the durable analysis job. The ``jobs`` row is the source of truth.

    Returns a JSON-safe result reference. Does not commit (the worker's session
    scope commits). ``load_and_parse``/``write_processed`` default to the real
    S3/Polars helpers; tests inject in-memory fakes.

    The delivery claim is the at-least-once guard: the validation run and its
    issues are append-only with freshly generated ids, so a redelivered message
    would insert a SECOND run for the same revision and re-advance the revision
    state. See ``jobs/delivery.py``.
    """
    job, replay = await claim_job_for_delivery(session, job_id)
    if replay is not None:
        return replay
    payload = job.payload or {}
    entity_id = str(payload.get("entity_id"))
    revision_id = str(payload.get("revision_id"))

    revision = await md_repo.get_revision(session, revision_id)
    if revision is None:
        raise ValueError(f"Revision '{revision_id}' not found for analysis.")

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)

    # K-01: the declared timezone is applied HERE, between load and validate, so
    # every load path (the real S3/Polars helper and an injected fake alike) yields
    # canonical UTC instants before anything validates, stores or replays them.
    source_zone = revision_source_zone(revision)
    loaded = await (load_and_parse or _load_and_parse)(session, entity_id, revision)
    parsed = normalize_source_timestamps(loaded, source_zone=source_zone)

    per_row = evaluate_rows(parsed)
    cross = evaluate_cross_row(
        parsed.market_data_type,
        parsed.rows,
        source_zone=source_zone,
        resolution_kind=revision.resolution_kind,
        resolution_value=revision.resolution_value,
        spread_unit=(revision.payload or {}).get("spread_unit"),
    )
    # The final severity is the worse of per-row and cross-row; a blocking finding
    # from either drives the revision to NEEDS_REVIEW (decide_outcome), so a
    # non-monotonic or duplicated series can never auto-verify into the money engine.
    worst = (
        per_row.status
        if _SEVERITY_RANK[per_row.status] >= _SEVERITY_RANK[cross.worst]
        else cross.worst
    )
    outcome = AnalysisOutcome(
        status=worst,
        rows_checked=per_row.rows_checked,
        counts=per_row.counts,
        next_state=decide_outcome(worst),
    )

    processed_digest = await (write_processed or _write_processed)(
        session, entity_id, revision_id, parsed
    )

    run = md_repo.add_validation_run(
        session,
        entity_id=entity_id,
        status=outcome.status,
        revision_id=revision_id,
        job_id=job_id,
        rows_checked=outcome.rows_checked,
        summary={
            "counts": outcome.counts,
            "processed_digest": processed_digest,
            "cross_row": {issue.rule_code: issue.occurrences for issue in cross.issues},
            "coverage_slices": len(cross.coverage),
        },
    )
    # The run must be INSERTed before its issues: there is no ORM relationship
    # between run and issue, so the unit-of-work cannot derive the parent-before-
    # child order from the bare run_id FK (mirrors the registry create-order note).
    await session.flush()
    if outcome.counts.get(ValidationStatus.BLOCKING_FAIL.value, 0) > 0:
        md_repo.add_validation_issue(
            session,
            run_id=run.run_id,
            severity=ValidationStatus.BLOCKING_FAIL,
            rule_code="ROW_RULE_BLOCKING_FAIL",
            message="One or more rows failed blocking validation.",
            occurrences=outcome.counts[ValidationStatus.BLOCKING_FAIL.value],
        )
    for issue in cross.issues:
        md_repo.add_validation_issue(
            session,
            run_id=run.run_id,
            severity=issue.severity,
            rule_code=issue.rule_code,
            message=issue.message,
            occurrences=issue.occurrences,
            sample=issue.sample,
        )
    for segment in cross.coverage:
        md_repo.add_coverage_slice(
            session,
            entity_id=entity_id,
            revision_id=revision_id,
            start_at=segment.start_at,
            end_at=segment.end_at,
            row_count=segment.row_count,
            gap_seconds=segment.gap_seconds,
        )

    _advance_revision(revision, outcome)

    audit_repo.add_audit_event(
        session,
        event_kind="market.analysis.completed",
        actor_principal_id=job.actor_principal_id,
        actor_kind=_system_actor_kind(),
        target_entity_id=entity_id,
        target_entity_type=md_repo.ENTITY_TYPE,
        target_revision_id=revision_id,
        new_state=str(revision.revision_state),
        correlation_id=job.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="resource.changed",
        resource_type=md_repo.ENTITY_TYPE,
        resource_id=entity_id,
        payload={"action": "analyzed", "revision_id": revision_id},
        correlation_id=job.correlation_id,
    )

    job.status = JobStatus.SUCCEEDED
    job.finished_at = datetime.now(UTC)
    result = {
        "entity_id": entity_id,
        "revision_id": revision_id,
        "validation_status": str(outcome.status),
        "rows_checked": outcome.rows_checked,
        "revision_state": str(revision.revision_state),
    }
    job.result_ref = result
    return result


def _advance_revision(revision: MarketDatasetRevision, outcome: AnalysisOutcome) -> None:
    revision.validation_status = outcome.status
    if revision.revision_state == MarketRevisionState.ANALYZING:
        revision.revision_state = next_market_revision_state(
            MarketRevisionState.ANALYZING, outcome.next_state
        )
    revision.manifest_hash = manifest_hash(
        {
            "revision_id": revision.revision_id,
            "validation_status": str(outcome.status),
            "rows_checked": outcome.rows_checked,
        }
    )


def _system_actor_kind() -> Any:
    from entropia.domain.lifecycle.enums import ActorKind

    return ActorKind.SYSTEM_SERVICE


async def _load_and_parse(
    session: AsyncSession, entity_id: str, revision: MarketDatasetRevision
) -> ParsedDataset:
    """Load the latest raw asset bytes and parse them. Isolated for testing."""
    from sqlalchemy import select

    from entropia.infrastructure.postgres.models import MarketRawAsset
    from entropia.infrastructure.s3.datasets import get_raw_bytes

    stmt = (
        select(MarketRawAsset)
        .where(MarketRawAsset.entity_id == entity_id)
        .order_by(MarketRawAsset.created_at.desc())
        .limit(1)
    )
    asset = (await session.execute(stmt)).scalars().first()
    if asset is None:
        raise ValueError(f"No raw asset found for dataset '{entity_id}'.")
    data = get_raw_bytes(asset.object_key)
    return _parse_raw_bytes(revision.market_data_type, data)


async def _write_processed(
    session: AsyncSession,
    entity_id: str,
    revision_id: str,
    parsed: ParsedDataset,
) -> str:
    """Write normalized rows to a processed Parquet asset. Returns the digest."""
    from entropia.infrastructure.s3.datasets import put_processed_parquet

    parquet_bytes = _to_parquet_bytes(parsed)
    object_key, digest = put_processed_parquet(entity_id, parquet_bytes)
    md_repo.add_processed_asset(
        session,
        entity_id=entity_id,
        object_key=object_key,
        content_digest=digest,
        size_bytes=len(parquet_bytes),
        revision_id=revision_id,
        row_count=len(parsed.rows),
        schema_descriptor={"columns": parsed.columns},
    )
    return digest
