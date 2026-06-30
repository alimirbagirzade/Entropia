"""Research Data persistence (doc 12, decision D1).

The Root is the shared ``entity_registry`` (entity_type="research_dataset"); these
helpers create/append ``research_dataset_revision`` rows and the supporting raw/
native asset, field/feature definition, time policy, market link, and validation
rows. Sync mutators mirror ``repositories/market_data.py`` (no commit); async
readers return ORM rows for the queries layer.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import DeletionState, ValidationStatus
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    EventTimeSemantics,
    ResearchRevisionState,
    ResearchTimezoneMode,
    UsageScope,
)
from entropia.domain.revision.hashing import content_hash
from entropia.domain.revision.head import next_revision_no
from entropia.infrastructure.postgres.models import (
    EntityRegistry,
    ResearchDatasetRevision,
    ResearchFeatureDefinition,
    ResearchFieldDefinition,
    ResearchMarketLink,
    ResearchNativeAsset,
    ResearchRawAsset,
    ResearchTimePolicy,
    ResearchValidationIssue,
    ResearchValidationRun,
)
from entropia.shared.ids import new_id

ENTITY_TYPE = "research_dataset"


async def create_research_dataset(
    session: AsyncSession,
    *,
    owner_principal_id: str | None,
    created_by_principal_id: str | None,
    payload: dict[str, Any],
    display_name: str | None = None,
    category_key: str | None = None,
    custom_category: str | None = None,
    provider_name: str | None = None,
    usage_scope: UsageScope | None = None,
    linked_market_dataset_revision_id: str | None = None,
    revision_state: ResearchRevisionState = ResearchRevisionState.DRAFT,
    lifecycle_state: str | None = "active",
) -> tuple[EntityRegistry, ResearchDatasetRevision]:
    """Create the registry Root + first research revision; point head at it.

    The root is flushed BEFORE the revision is added so the revision's
    ``entity_id`` FK target exists at flush time: SQLAlchemy's unit-of-work does
    not derive parent-before-child INSERT order from a bare ``ForeignKey`` without
    a ``relationship()`` (same fix as market data).
    """
    entity_id = new_id("rds")
    root = EntityRegistry(
        entity_id=entity_id,
        entity_type=ENTITY_TYPE,
        owner_principal_id=owner_principal_id,
        created_by_principal_id=created_by_principal_id,
        lifecycle_state=lifecycle_state,
        deletion_state=DeletionState.ACTIVE,
        current_revision_id=None,
        row_version=1,
    )
    session.add(root)
    await session.flush()
    revision = ResearchDatasetRevision(
        revision_id=new_id("rrev"),
        entity_id=entity_id,
        revision_no=next_revision_no(None),
        parent_revision_id=None,
        base_revision_id=None,
        supersedes_revision_id=None,
        revision_state=revision_state,
        display_name=display_name,
        category_key=category_key,
        custom_category=custom_category,
        provider_name=provider_name,
        usage_scope=usage_scope,
        linked_market_dataset_revision_id=linked_market_dataset_revision_id,
        payload=payload,
        content_hash=content_hash(payload),
        created_by_principal_id=created_by_principal_id,
    )
    session.add(revision)
    root.current_revision_id = revision.revision_id
    return root, revision


async def append_research_dataset_revision(
    session: AsyncSession,
    root: EntityRegistry,
    *,
    payload: dict[str, Any],
    created_by_principal_id: str | None,
    revision_state: ResearchRevisionState = ResearchRevisionState.DRAFT,
    base_revision_id: str | None = None,
    supersedes_revision_id: str | None = None,
    display_name: str | None = None,
    category_key: str | None = None,
    custom_category: str | None = None,
    provider_name: str | None = None,
    usage_scope: UsageScope | None = None,
    linked_market_dataset_revision_id: str | None = None,
) -> ResearchDatasetRevision:
    """Insert revision N+1, advance the head pointer + row_version."""
    prior_no = await _max_revision_no(session, root.entity_id)
    revision = ResearchDatasetRevision(
        revision_id=new_id("rrev"),
        entity_id=root.entity_id,
        revision_no=next_revision_no(prior_no),
        parent_revision_id=root.current_revision_id,
        base_revision_id=base_revision_id or root.current_revision_id,
        supersedes_revision_id=supersedes_revision_id or root.current_revision_id,
        revision_state=revision_state,
        display_name=display_name,
        category_key=category_key,
        custom_category=custom_category,
        provider_name=provider_name,
        usage_scope=usage_scope,
        linked_market_dataset_revision_id=linked_market_dataset_revision_id,
        payload=payload,
        content_hash=content_hash(payload),
        created_by_principal_id=created_by_principal_id,
    )
    session.add(revision)
    root.current_revision_id = revision.revision_id
    root.row_version += 1
    return revision


def add_raw_asset(
    session: AsyncSession,
    *,
    entity_id: str,
    object_key: str,
    content_digest: str,
    size_bytes: int,
    revision_id: str | None = None,
    content_type: str | None = None,
    original_filename: str | None = None,
    uploaded_by_principal_id: str | None = None,
) -> ResearchRawAsset:
    asset = ResearchRawAsset(
        asset_id=new_id("rraw"),
        entity_id=entity_id,
        revision_id=revision_id,
        object_key=object_key,
        content_digest=content_digest,
        size_bytes=size_bytes,
        content_type=content_type,
        original_filename=original_filename,
        uploaded_by_principal_id=uploaded_by_principal_id,
    )
    session.add(asset)
    return asset


def add_native_asset(
    session: AsyncSession,
    *,
    entity_id: str,
    object_key: str,
    content_digest: str,
    size_bytes: int,
    revision_id: str | None = None,
    raw_asset_id: str | None = None,
    row_count: int | None = None,
    schema_descriptor: dict[str, Any] | None = None,
) -> ResearchNativeAsset:
    asset = ResearchNativeAsset(
        asset_id=new_id("rnat"),
        entity_id=entity_id,
        revision_id=revision_id,
        raw_asset_id=raw_asset_id,
        object_key=object_key,
        content_digest=content_digest,
        size_bytes=size_bytes,
        row_count=row_count,
        schema_descriptor=schema_descriptor,
    )
    session.add(asset)
    return asset


def add_field_definition(
    session: AsyncSession,
    *,
    entity_id: str,
    field_name: str,
    semantic_type: str,
    revision_id: str | None = None,
    definition_version: int = 1,
    unit_or_scale: str | None = None,
    measurement_method: str | None = None,
    null_semantics: str | None = None,
    event_time_source: str | None = None,
    availability_rule: str | None = None,
    allowed_usage: str | None = None,
) -> ResearchFieldDefinition:
    field = ResearchFieldDefinition(
        field_definition_id=new_id("rfld"),
        entity_id=entity_id,
        revision_id=revision_id,
        definition_version=definition_version,
        field_name=field_name,
        semantic_type=semantic_type,
        unit_or_scale=unit_or_scale,
        measurement_method=measurement_method,
        null_semantics=null_semantics,
        event_time_source=event_time_source,
        availability_rule=availability_rule,
        allowed_usage=allowed_usage,
    )
    session.add(field)
    return field


def add_feature_definition(
    session: AsyncSession,
    *,
    entity_id: str,
    feature_name: str,
    definition: dict[str, Any],
    revision_id: str | None = None,
    feature_version: int = 1,
    approval_state: str | None = None,
) -> ResearchFeatureDefinition:
    feature = ResearchFeatureDefinition(
        feature_definition_id=new_id("rfea"),
        entity_id=entity_id,
        revision_id=revision_id,
        feature_version=feature_version,
        feature_name=feature_name,
        definition=definition,
        approval_state=approval_state,
        content_hash=content_hash(definition),
    )
    session.add(feature)
    return feature


def set_time_policy(
    session: AsyncSession,
    *,
    entity_id: str,
    event_time_semantics: EventTimeSemantics,
    available_time_policy: AvailableTimePolicy,
    source_timezone_mode: ResearchTimezoneMode,
    revision_id: str | None = None,
    time_policy_version: int = 1,
    delay_seconds: int | None = None,
    source_timezone_iana: str | None = None,
) -> ResearchTimePolicy:
    """Insert a new time-policy row (versioned, never mutated in place)."""
    policy = ResearchTimePolicy(
        time_policy_id=new_id("rtp"),
        entity_id=entity_id,
        revision_id=revision_id,
        time_policy_version=time_policy_version,
        event_time_semantics=event_time_semantics,
        available_time_policy=available_time_policy,
        delay_seconds=delay_seconds,
        source_timezone_mode=source_timezone_mode,
        source_timezone_iana=source_timezone_iana,
    )
    session.add(policy)
    return policy


def add_market_link(
    session: AsyncSession,
    *,
    entity_id: str,
    market_dataset_revision_id: str,
    revision_id: str | None = None,
    market_content_hash: str | None = None,
) -> ResearchMarketLink:
    """Pin an exact ACTIVE+APPROVED market revision by ID (+ content hash)."""
    link = ResearchMarketLink(
        link_id=new_id("rmlk"),
        entity_id=entity_id,
        revision_id=revision_id,
        market_dataset_revision_id=market_dataset_revision_id,
        market_content_hash=market_content_hash,
    )
    session.add(link)
    return link


def add_validation_run(
    session: AsyncSession,
    *,
    entity_id: str,
    status: ValidationStatus,
    revision_id: str | None = None,
    job_id: str | None = None,
    rows_checked: int | None = None,
    summary: dict[str, Any] | None = None,
) -> ResearchValidationRun:
    run = ResearchValidationRun(
        run_id=new_id("rval"),
        entity_id=entity_id,
        revision_id=revision_id,
        job_id=job_id,
        status=status,
        rows_checked=rows_checked,
        summary=summary,
    )
    session.add(run)
    return run


def add_validation_issue(
    session: AsyncSession,
    *,
    run_id: str,
    severity: ValidationStatus,
    check_id: str,
    message: str,
    occurrences: int = 1,
    remediation: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> ResearchValidationIssue:
    issue = ResearchValidationIssue(
        issue_id=new_id("riss"),
        run_id=run_id,
        severity=severity,
        check_id=check_id,
        message=message,
        remediation=remediation,
        occurrences=occurrences,
        evidence=evidence,
    )
    session.add(issue)
    return issue


async def get_dataset_root(session: AsyncSession, entity_id: str) -> EntityRegistry | None:
    """Return the registry Root iff it is a research dataset."""
    root = await session.get(EntityRegistry, entity_id)
    if root is None or root.entity_type != ENTITY_TYPE:
        return None
    return root


async def get_revision(session: AsyncSession, revision_id: str) -> ResearchDatasetRevision | None:
    return await session.get(ResearchDatasetRevision, revision_id)


async def list_revisions(
    session: AsyncSession, entity_id: str, *, limit: int = 50
) -> Sequence[ResearchDatasetRevision]:
    stmt = (
        select(ResearchDatasetRevision)
        .where(ResearchDatasetRevision.entity_id == entity_id)
        .order_by(ResearchDatasetRevision.revision_no.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_market_link(session: AsyncSession, revision_id: str) -> ResearchMarketLink | None:
    """Return the most recent market link pinned for a research revision."""
    stmt = (
        select(ResearchMarketLink)
        .where(ResearchMarketLink.revision_id == revision_id)
        .order_by(ResearchMarketLink.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


async def query_revisions_for_owner(
    session: AsyncSession,
    *,
    owner_principal_id: str,
    limit: int = 50,
) -> Sequence[ResearchDatasetRevision]:
    """Latest revision rows for datasets owned by the given principal (active)."""
    stmt = (
        select(ResearchDatasetRevision)
        .join(EntityRegistry, EntityRegistry.entity_id == ResearchDatasetRevision.entity_id)
        .where(
            EntityRegistry.entity_type == ENTITY_TYPE,
            EntityRegistry.owner_principal_id == owner_principal_id,
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
            ResearchDatasetRevision.revision_id == EntityRegistry.current_revision_id,
        )
        .order_by(ResearchDatasetRevision.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def _max_revision_no(session: AsyncSession, entity_id: str) -> int | None:
    stmt = select(func.max(ResearchDatasetRevision.revision_no)).where(
        ResearchDatasetRevision.entity_id == entity_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


__all__ = [
    "ENTITY_TYPE",
    "add_feature_definition",
    "add_field_definition",
    "add_market_link",
    "add_native_asset",
    "add_raw_asset",
    "add_validation_issue",
    "add_validation_run",
    "append_research_dataset_revision",
    "create_research_dataset",
    "get_dataset_root",
    "get_market_link",
    "get_revision",
    "list_revisions",
    "query_revisions_for_owner",
    "set_time_policy",
]
