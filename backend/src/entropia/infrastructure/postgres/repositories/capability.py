"""Capability Registry data access (Stage 7b, doc 22 §9, §13).

No commit here — the caller's transaction owns atomicity. Every ``create_*``
follows the 7a L1 lesson: without ``relationship()`` SQLAlchemy does NOT
FK-order cross-table inserts, so the parent row is flushed BEFORE any child
references it (``create_capability`` -> ``add_activation_event``).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.capability.baseline import (
    BASELINE_CAPABILITIES,
    UI_SURFACE_VERSION_V18,
)
from entropia.domain.capability.enums import CapabilityState
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.models import (
    AnalysisArtifact,
    CapabilityActivationEvent,
    FutureCapability,
    ViewDataset,
)
from entropia.shared.ids import new_id

# --------------------------------------------------------------------------- #
# Lookups                                                                      #
# --------------------------------------------------------------------------- #


async def get_capability(session: AsyncSession, capability_id: str) -> FutureCapability | None:
    return await session.get(FutureCapability, capability_id)


async def get_capability_by_key(
    session: AsyncSession, capability_key: str
) -> FutureCapability | None:
    stmt = select(FutureCapability).where(FutureCapability.capability_key == capability_key)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_capabilities(session: AsyncSession) -> list[FutureCapability]:
    stmt = select(FutureCapability).order_by(FutureCapability.capability_key.asc())
    return list((await session.execute(stmt)).scalars())


async def operational_capability_keys(session: AsyncSession) -> frozenset[str]:
    """Keys currently Limited/Active — the CR-08 tool-exposure input."""
    stmt = select(FutureCapability.capability_key).where(
        FutureCapability.lifecycle_state.in_([CapabilityState.LIMITED, CapabilityState.ACTIVE])
    )
    return frozenset((await session.execute(stmt)).scalars())


async def list_activation_events(
    session: AsyncSession, capability_id: str
) -> list[CapabilityActivationEvent]:
    stmt = (
        select(CapabilityActivationEvent)
        .where(CapabilityActivationEvent.capability_id == capability_id)
        .order_by(CapabilityActivationEvent.resulting_registry_version.asc())
    )
    return list((await session.execute(stmt)).scalars())


# --------------------------------------------------------------------------- #
# Operational output history (read-only, owner-scoped — doc 22 §7, §13)        #
# --------------------------------------------------------------------------- #


async def get_view_dataset(session: AsyncSession, view_dataset_id: str) -> ViewDataset | None:
    return await session.get(ViewDataset, view_dataset_id)


async def list_view_datasets(
    session: AsyncSession,
    *,
    owner_principal_id: str,
    last_key: str | None,
    limit: int,
) -> list[ViewDataset]:
    """Owner-scoped, ACTIVE-only View Dataset history, newest-first. The
    ``view_dataset_id`` is ULID-sortable, so a descending id keyset orders by
    creation time and ``id < last_key`` pages forward without an offset."""
    stmt = (
        select(ViewDataset)
        .where(
            ViewDataset.owner_principal_id == owner_principal_id,
            ViewDataset.deletion_state == DeletionState.ACTIVE,
        )
        .order_by(ViewDataset.view_dataset_id.desc())
        .limit(limit)
    )
    if last_key is not None:
        stmt = stmt.where(ViewDataset.view_dataset_id < last_key)
    return list((await session.execute(stmt)).scalars())


async def get_analysis_artifact(session: AsyncSession, artifact_id: str) -> AnalysisArtifact | None:
    return await session.get(AnalysisArtifact, artifact_id)


async def list_analysis_artifacts(
    session: AsyncSession,
    *,
    owner_principal_id: str,
    artifact_type: str | None,
    last_key: str | None,
    limit: int,
) -> list[AnalysisArtifact]:
    """Owner-scoped, ACTIVE-only Analysis Artifact history, newest-first,
    optionally narrowed to one ``artifact_type``. The ``artifact_id`` is
    ULID-sortable — the descending id keyset orders by creation time."""
    stmt = (
        select(AnalysisArtifact)
        .where(
            AnalysisArtifact.owner_principal_id == owner_principal_id,
            AnalysisArtifact.deletion_state == DeletionState.ACTIVE,
        )
        .order_by(AnalysisArtifact.artifact_id.desc())
        .limit(limit)
    )
    if artifact_type is not None:
        stmt = stmt.where(AnalysisArtifact.artifact_type == artifact_type)
    if last_key is not None:
        stmt = stmt.where(AnalysisArtifact.artifact_id < last_key)
    return list((await session.execute(stmt)).scalars())


# --------------------------------------------------------------------------- #
# Inserts (no commit — the caller's transaction owns atomicity)                #
# --------------------------------------------------------------------------- #


async def create_capability(
    session: AsyncSession,
    *,
    capability_id: str | None = None,
    capability_key: str,
    title: str,
    menu_path: str,
    lifecycle_state: CapabilityState = CapabilityState.PLACEHOLDER,
    ui_surface_version: str = UI_SURFACE_VERSION_V18,
    domain_contract_version: str | None = None,
    dependency_snapshot: dict[str, Any],
) -> FutureCapability:
    capability = FutureCapability(
        capability_id=capability_id or new_id("fcap"),
        capability_key=capability_key,
        title=title,
        menu_path=menu_path,
        lifecycle_state=lifecycle_state,
        ui_surface_version=ui_surface_version,
        domain_contract_version=domain_contract_version,
        dependency_snapshot=dependency_snapshot,
        registry_version=1,
    )
    session.add(capability)
    await session.flush()  # L1: registry row exists before events reference it
    return capability


async def add_activation_event(
    session: AsyncSession,
    *,
    capability_id: str,
    capability_key: str,
    from_state: CapabilityState,
    to_state: CapabilityState,
    actor_principal_id: str | None,
    reason: str,
    dependency_snapshot: dict[str, Any],
    snapshot_checksum: str,
    prior_registry_version: int,
    resulting_registry_version: int,
    correlation_id: str | None = None,
) -> CapabilityActivationEvent:
    event = CapabilityActivationEvent(
        event_id=new_id("caev"),
        capability_id=capability_id,
        capability_key=capability_key,
        from_state=from_state,
        to_state=to_state,
        actor_principal_id=actor_principal_id,
        reason=reason,
        dependency_snapshot=dependency_snapshot,
        snapshot_checksum=snapshot_checksum,
        prior_registry_version=prior_registry_version,
        resulting_registry_version=resulting_registry_version,
        correlation_id=correlation_id,
    )
    session.add(event)
    await session.flush()
    return event


async def create_view_dataset(
    session: AsyncSession,
    *,
    capability_key: str,
    source_manifest_refs: list[str],
    series_refs: list[str],
    marker_refs: list[str],
    range_spec: dict[str, Any] | None,
    schema_version: str,
    owner_principal_id: str | None,
    created_by_principal_id: str | None,
) -> ViewDataset:
    dataset = ViewDataset(
        view_dataset_id=new_id("vds"),
        capability_key=capability_key,
        source_manifest_refs=source_manifest_refs,
        series_refs=series_refs,
        marker_refs=marker_refs,
        range_spec=range_spec,
        schema_version=schema_version,
        owner_principal_id=owner_principal_id,
        created_by_principal_id=created_by_principal_id,
        row_version=1,
    )
    session.add(dataset)
    await session.flush()
    return dataset


async def create_analysis_artifact(
    session: AsyncSession,
    *,
    artifact_type: str,
    capability_key: str,
    input_manifest_refs: list[str],
    method_version: str,
    output_ref: str | None,
    owner_principal_id: str | None,
    created_by_principal_id: str | None,
) -> AnalysisArtifact:
    artifact = AnalysisArtifact(
        artifact_id=new_id("aart"),
        artifact_type=artifact_type,
        capability_key=capability_key,
        input_manifest_refs=input_manifest_refs,
        method_version=method_version,
        output_ref=output_ref,
        owner_principal_id=owner_principal_id,
        created_by_principal_id=created_by_principal_id,
        row_version=1,
    )
    session.add(artifact)
    await session.flush()
    return artifact


# --------------------------------------------------------------------------- #
# Baseline seed (shared by migration 0020 and tests)                           #
# --------------------------------------------------------------------------- #


async def seed_baseline_capabilities(session: AsyncSession) -> list[FutureCapability]:
    """Idempotently insert the seven fixed V18 capability slots as PLACEHOLDER
    registry rows (doc 22 §4, §9 'baseline future keys Placeholder')."""
    rows: list[FutureCapability] = []
    for seed in BASELINE_CAPABILITIES:
        existing = await get_capability_by_key(session, seed.capability_key)
        if existing is not None:
            rows.append(existing)
            continue
        rows.append(
            await create_capability(
                session,
                capability_id=seed.capability_id,
                capability_key=seed.capability_key,
                title=seed.title,
                menu_path=seed.menu_path,
                dependency_snapshot=seed.dependency_snapshot,
            )
        )
    return rows
