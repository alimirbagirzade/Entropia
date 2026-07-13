"""Research-data analysis job + bundle compilers (doc 12 §8, §9, decision DR7/DR8).

Three pieces, all importable without a live broker / MinIO (heavy imports are
local to the functions that need them):

* ``run_analysis`` — the durable ``data``-queue job: load raw asset -> parse the
  native schema (Polars) -> validate time policy + usage scope + field meaning ->
  write a native asset + a validation run/issues -> advance the revision state.
* ``compile_agent_data_bundle`` — immutable Agent research bundle pinning exact
  research + market revision ids + content hashes, enforcing usage scope.
* ``compile_backtest_evidence_bundle`` — immutable Backtest evidence bundle; only
  ACTIVE+APPROVED, usage-scope-eligible, time-policy-valid revisions; pins exact
  ids + hashes (no "latest").
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import policy as identity_policy
from entropia.domain.identity.actor import Actor
from entropia.domain.lifecycle.enums import DeletionState, JobStatus, ValidationStatus
from entropia.domain.research_data import policy as rd_policy
from entropia.domain.research_data.enums import ResearchRevisionState
from entropia.domain.research_data.quality_rules import (
    SEVERITY_RANK,
    QualityIssue,
    evaluate_quality,
)
from entropia.domain.research_data.state_machine import next_research_revision_state
from entropia.domain.research_data.time_policy import time_policy_is_valid
from entropia.domain.research_data.usage_scope import ensure_allows_evidence_bundle
from entropia.infrastructure.postgres.models import (
    EntityRegistry,
    Job,
    ResearchDatasetRevision,
)
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import research_data as rd_repo
from entropia.shared.errors import NotFoundError, TimePolicyInvalid
from entropia.shared.manifest import manifest_hash

# Lifecycle states a research revision can no longer be consumed from.
_NON_CONSUMABLE_STATES = frozenset(
    {ResearchRevisionState.DEPRECATED, ResearchRevisionState.APPROVAL_REVOKED}
)

_BUNDLE_COMPILER_VERSION = "research-bundle-v1"


# --------------------------------------------------------------------------- #
# Analysis job
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class AnalysisOutcome:
    """Aggregate result of validating a research revision (pure)."""

    status: ValidationStatus
    rows_checked: int
    next_state: ResearchRevisionState
    issues: list[dict[str, Any]]


@dataclass(slots=True)
class ParsedResearch:
    """Parsed native-schema product, ready for validation."""

    columns: list[str]
    rows: list[dict[str, Any]]


# Injection seams (mirror the market-data job): the S3/Polars steps are swappable so
# ``run_analysis`` is exercisable end-to-end against a real DB without MinIO.
# Production callers pass neither and get the real helpers below.
_LoadAndParse = Callable[[AsyncSession, str], Awaitable[ParsedResearch]]
_WriteNative = Callable[[AsyncSession, str, str, ParsedResearch], Awaitable[str]]


def evaluate_research(parsed: ParsedResearch, revision: ResearchDatasetRevision) -> AnalysisOutcome:
    """Decide the validation outcome for a parsed research revision (pure).

    Structural blockers (any -> needs_review, never auto-verified):
      * the time policy must be structurally valid (DR4);
      * at least one native field/column must exist (schema integrity).

    Then the deeper semantic quality report (doc 12 §10 / backlog R9) adds the
    coverage / duplicates / null-density / type-consistency / numeric-range /
    instrument-mapping families. Per the §10.1 decision tree, only a ``BLOCKING_FAIL``
    forces ``NEEDS_REVIEW``; ``WARNING`` findings are recorded but still verify (a
    verified-with-warnings revision remains Admin-approvable). The run status is the
    worst severity across every finding so warnings surface in the quality report.
    """
    issues: list[dict[str, Any]] = []

    delay = (
        None
        if revision.available_delay_seconds is None
        else timedelta(seconds=revision.available_delay_seconds)
    )
    if revision.available_time_policy is None or not time_policy_is_valid(
        policy=revision.available_time_policy, delay=delay
    ):
        issues.append(
            {
                "check_id": "TIME_POLICY",
                "severity": ValidationStatus.BLOCKING_FAIL.value,
                "message": "Event/available time policy is missing or invalid.",
                "remediation": "Set a valid event time + available-time rule, then re-analyze.",
            }
        )
    if not parsed.columns:
        issues.append(
            {
                "check_id": "NATIVE_SCHEMA",
                "severity": ValidationStatus.BLOCKING_FAIL.value,
                "message": "No native fields were parsed from the raw source.",
                "remediation": "Upload a non-empty source whose columns can be parsed.",
            }
        )

    quality = evaluate_quality(
        parsed.columns,
        parsed.rows,
        linked_market_dataset_revision_id=revision.linked_market_dataset_revision_id,
        instrument_mapping_ref=revision.instrument_mapping_ref,
    )
    issues.extend(_quality_issue_dict(issue) for issue in quality.issues)

    worst = ValidationStatus.PASS
    for issue in issues:
        severity = ValidationStatus(issue["severity"])
        if SEVERITY_RANK[severity] > SEVERITY_RANK[worst]:
            worst = severity
    has_blocker = worst == ValidationStatus.BLOCKING_FAIL
    next_state = (
        ResearchRevisionState.NEEDS_REVIEW if has_blocker else ResearchRevisionState.VERIFIED
    )
    return AnalysisOutcome(
        status=worst,
        rows_checked=len(parsed.rows),
        next_state=next_state,
        issues=issues,
    )


def _quality_issue_dict(issue: QualityIssue) -> dict[str, Any]:
    """Flatten a pure ``QualityIssue`` into the job's persist-ready issue dict."""
    return {
        "check_id": issue.check_id,
        "severity": issue.severity.value,
        "message": issue.message,
        "remediation": issue.remediation,
        "occurrences": issue.occurrences,
        "evidence": issue.evidence,
    }


def _issues_by_severity(issues: list[dict[str, Any]]) -> dict[str, int]:
    """Count findings per severity for the validation-run summary (JSON-safe)."""
    counts = {status.value: 0 for status in ValidationStatus}
    for issue in issues:
        counts[str(issue["severity"])] += 1
    return counts


def _parse_raw_bytes(data: bytes) -> ParsedResearch:
    """Parse CSV/TXT bytes into native rows via Polars (DR7). Imported locally so
    the module stays import-clean without Polars at load time."""
    import io

    import polars as pl

    frame = pl.read_csv(io.BytesIO(data))
    columns = list(frame.columns)
    rows = list(frame.iter_rows(named=True))
    return ParsedResearch(columns=columns, rows=rows)


def _to_parquet_bytes(parsed: ParsedResearch) -> bytes:
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
    write_native: _WriteNative | None = None,
) -> dict[str, Any]:
    """Execute the durable research-analysis job. The ``jobs`` row is the source
    of truth. Does not commit (the worker's session scope commits). ``load_and_parse``
    / ``write_native`` default to the real S3/Polars helpers; tests inject fakes."""
    load = load_and_parse or _load_and_parse
    write = write_native or _write_native

    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError(f"Job '{job_id}' not found.")
    payload = job.payload or {}
    entity_id = str(payload.get("entity_id"))
    revision_id = str(payload.get("revision_id"))

    revision = await rd_repo.get_revision(session, revision_id)
    if revision is None:
        raise ValueError(f"Revision '{revision_id}' not found for analysis.")

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)

    parsed = await load(session, entity_id)
    outcome = evaluate_research(parsed, revision)

    native_digest = await write(session, entity_id, revision_id, parsed)

    run = rd_repo.add_validation_run(
        session,
        entity_id=entity_id,
        status=outcome.status,
        revision_id=revision_id,
        job_id=job_id,
        rows_checked=outcome.rows_checked,
        summary={
            "native_digest": native_digest,
            "issue_count": len(outcome.issues),
            "issues_by_severity": _issues_by_severity(outcome.issues),
        },
    )
    # The run must be INSERTed before its issues: there is no ORM relationship
    # between run and issue, so the unit-of-work cannot derive the parent-before-
    # child order from the bare run_id FK (mirrors the market-data job + registry
    # create-order note).
    await session.flush()
    for issue in outcome.issues:
        rd_repo.add_validation_issue(
            session,
            run_id=run.run_id,
            severity=ValidationStatus(issue["severity"]),
            check_id=issue["check_id"],
            message=issue["message"],
            occurrences=int(issue.get("occurrences", 1)),
            remediation=issue.get("remediation"),
            evidence=issue.get("evidence"),
        )

    _advance_revision(revision, outcome, parsed, native_digest)

    audit_repo.add_audit_event(
        session,
        event_kind="research.analysis.completed",
        actor_principal_id=job.actor_principal_id,
        actor_kind=_system_actor_kind(),
        target_entity_id=entity_id,
        target_entity_type=rd_repo.ENTITY_TYPE,
        target_revision_id=revision_id,
        new_state=str(revision.revision_state),
        correlation_id=job.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="resource.changed",
        resource_type=rd_repo.ENTITY_TYPE,
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


def _advance_revision(
    revision: ResearchDatasetRevision,
    outcome: AnalysisOutcome,
    parsed: ParsedResearch,
    native_digest: str,
) -> None:
    revision.validation_status = outcome.status
    revision.native_schema_descriptor = {"columns": parsed.columns}
    if revision.revision_state == ResearchRevisionState.ANALYZING:
        revision.revision_state = next_research_revision_state(
            ResearchRevisionState.ANALYZING, outcome.next_state
        )
    revision.manifest_hash = manifest_hash(
        {
            "revision_id": revision.revision_id,
            "validation_status": str(outcome.status),
            "rows_checked": outcome.rows_checked,
            "native_digest": native_digest,
        }
    )


def _system_actor_kind() -> Any:
    from entropia.domain.lifecycle.enums import ActorKind

    return ActorKind.SYSTEM_SERVICE


async def _load_and_parse(session: AsyncSession, entity_id: str) -> ParsedResearch:
    """Load the latest raw asset bytes and parse them. Isolated for testing."""
    from sqlalchemy import select

    from entropia.infrastructure.postgres.models import ResearchRawAsset
    from entropia.infrastructure.s3.datasets import get_raw_bytes

    stmt = (
        select(ResearchRawAsset)
        .where(ResearchRawAsset.entity_id == entity_id)
        .order_by(ResearchRawAsset.created_at.desc())
        .limit(1)
    )
    asset = (await session.execute(stmt)).scalars().first()
    if asset is None:
        raise ValueError(f"No raw asset found for research dataset '{entity_id}'.")
    data = get_raw_bytes(asset.object_key)
    return _parse_raw_bytes(data)


async def _write_native(
    session: AsyncSession,
    entity_id: str,
    revision_id: str,
    parsed: ParsedResearch,
) -> str:
    """Write parsed native rows to a Parquet asset. Returns the digest."""
    from entropia.infrastructure.s3.datasets import put_processed_parquet

    parquet_bytes = _to_parquet_bytes(parsed)
    object_key, digest = put_processed_parquet(entity_id, parquet_bytes)
    rd_repo.add_native_asset(
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


# --------------------------------------------------------------------------- #
# Bundle compilers (DR7)
# --------------------------------------------------------------------------- #


async def compile_agent_data_bundle(
    session: AsyncSession,
    actor: Actor,
    *,
    research_revision_ids: Sequence[str],
    task_id: str | None = None,
) -> dict[str, Any]:
    """Compile an immutable Agent research bundle (doc 12 §9.1).

    Requires Research Data page access (Admin/Supervisor/Agent); each member is
    re-checked for view permission and must be in a consumable lifecycle state
    (not deprecated/approval_revoked/soft-deleted). Every usage scope allows
    Agent research. The bundle pins exact research revision ids + content hashes
    AND the linked market revision id + content hash. No "latest" resolution.
    """
    rd_policy.ensure_can_access_page(actor)
    members: list[dict[str, Any]] = []
    for revision_id in research_revision_ids:
        revision = await _require_revision(session, revision_id)
        await _require_viewable_root(session, actor, revision, consumable_only=True)
        link = await rd_repo.get_market_link(session, revision_id)
        members.append(
            {
                "research_revision_id": revision.revision_id,
                "research_content_hash": revision.content_hash,
                "usage_scope": str(revision.usage_scope) if revision.usage_scope else None,
                "market_dataset_revision_id": revision.linked_market_dataset_revision_id,
                "market_content_hash": link.market_content_hash if link else None,
            }
        )
    return _seal_bundle("agent_data_bundle", members, extra={"task_id": task_id})


async def compile_backtest_evidence_bundle(
    session: AsyncSession,
    actor: Actor,
    *,
    research_revision_ids: Sequence[str],
    run_request_id: str | None = None,
) -> dict[str, Any]:
    """Compile an immutable Backtest evidence bundle (doc 12 §9.2, §9.3).

    Requires Research Data page access (Admin/Supervisor/Agent) and per-revision
    view permission. Each revision must be ACTIVE+APPROVED, have a usage scope
    that allows evidence bundles (Feature-Input-Only requires an approved feature
    definition), and a valid time policy. Pins exact ids + hashes. Raises
    ``UsageScopeForbidden`` / ``FieldMeaningInsufficient`` / ``TimePolicyInvalid``.
    """
    rd_policy.ensure_can_access_page(actor)
    members: list[dict[str, Any]] = []
    for revision_id in research_revision_ids:
        revision = await _require_revision(session, revision_id)
        await _require_viewable_root(session, actor, revision)
        if revision.revision_state != ResearchRevisionState.APPROVED:
            raise NotFoundError(
                f"Research revision '{revision_id}' is not ACTIVE+APPROVED for a bundle."
            )
        has_feature = await _has_approved_feature_definition(session, revision.entity_id)
        if revision.usage_scope is not None:
            ensure_allows_evidence_bundle(
                revision.usage_scope, has_approved_feature_definition=has_feature
            )
        _ensure_time_policy_valid(revision)
        link = await rd_repo.get_market_link(session, revision_id)
        members.append(
            {
                "research_revision_id": revision.revision_id,
                "research_content_hash": revision.content_hash,
                "usage_scope": str(revision.usage_scope) if revision.usage_scope else None,
                "market_dataset_revision_id": revision.linked_market_dataset_revision_id,
                "market_content_hash": link.market_content_hash if link else None,
            }
        )
    return _seal_bundle(
        "backtest_evidence_bundle", members, extra={"run_request_id": run_request_id}
    )


def _seal_bundle(
    bundle_kind: str, members: list[dict[str, Any]], *, extra: dict[str, Any]
) -> dict[str, Any]:
    """Hash the pinned members into an immutable, content-addressed bundle."""
    body = {
        "bundle_kind": bundle_kind,
        "members": members,
        "compiler_version": _BUNDLE_COMPILER_VERSION,
        **{k: v for k, v in extra.items() if v is not None},
    }
    bundle_hash = manifest_hash(body)
    return {**body, "resolved_at": datetime.now(UTC).isoformat(), "bundle_hash": bundle_hash}


async def _require_revision(session: AsyncSession, revision_id: str) -> ResearchDatasetRevision:
    revision = await rd_repo.get_revision(session, revision_id)
    if revision is None:
        raise NotFoundError(f"Research revision '{revision_id}' not found.")
    return revision


async def _require_viewable_root(
    session: AsyncSession,
    actor: Actor,
    revision: ResearchDatasetRevision,
    *,
    consumable_only: bool = False,
) -> EntityRegistry:
    """Load the revision's root and ensure it is active and viewable by the actor
    (and, when ``consumable_only``, that the revision is not deprecated/revoked).
    Stops a bundle from leaking or pinning an unauthorized or non-consumable
    revision."""
    root = await rd_repo.get_dataset_root(session, revision.entity_id)
    if root is None or root.deletion_state != DeletionState.ACTIVE:
        raise NotFoundError(f"Research revision '{revision.revision_id}' is not available.")
    visibility = "published" if root.lifecycle_state == "active" else "private"
    identity_policy.ensure_can_view(
        actor, owner_principal_id=root.owner_principal_id, visibility=visibility
    )
    if consumable_only and revision.revision_state in _NON_CONSUMABLE_STATES:
        raise NotFoundError(
            f"Research revision '{revision.revision_id}' is not in a consumable state."
        )
    return root


async def _has_approved_feature_definition(session: AsyncSession, entity_id: str) -> bool:
    from sqlalchemy import select

    from entropia.infrastructure.postgres.models import ResearchFeatureDefinition

    stmt = (
        select(ResearchFeatureDefinition)
        .where(
            ResearchFeatureDefinition.entity_id == entity_id,
            ResearchFeatureDefinition.approval_state == "approved",
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first() is not None


def _ensure_time_policy_valid(revision: ResearchDatasetRevision) -> None:
    delay = (
        None
        if revision.available_delay_seconds is None
        else timedelta(seconds=revision.available_delay_seconds)
    )
    if revision.available_time_policy is None or not time_policy_is_valid(
        policy=revision.available_time_policy, delay=delay
    ):
        raise TimePolicyInvalid(
            f"Research revision '{revision.revision_id}' has an invalid time policy."
        )
