"""Future Dev read models (Stage 7b, doc 22 §5, §7, §8).

Read-only registry projections: the capability list/detail every client uses
to refresh state, and the Graphic View placeholder overview. The overview is a
QUERY — it renders the static doc-22 §4.1 copy plus the server-side lifecycle
state; it never prepares chart data, starts a job or fakes progress (CR-09).

The operational OUTPUT history (View Dataset, Analysis Artifact) is an
owner-scoped, ACTIVE-only, newest-first keyset projection (doc 22 §7, §13): a
principal sees only the outputs it created, never a cross-owner row. An empty
page is the futureDevNoHistory.empty state — real absence, never a fake row."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.agent_lab.cursor import clamp_limit, decode_cursor, encode_cursor
from entropia.domain.capability.baseline import (
    GRAPHIC_VIEW_CARDS,
    GRAPHIC_VIEW_INTRO,
    STATE_MESSAGES,
)
from entropia.domain.capability.enums import GRAPHIC_VIEW, OPERATIONAL_STATES
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.models import (
    AnalysisArtifact,
    FutureCapability,
    ViewDataset,
)
from entropia.infrastructure.postgres.repositories import capability as capability_repo
from entropia.shared.errors import (
    AnalysisArtifactNotFoundError,
    CapabilityNotFoundError,
    ViewDatasetNotFoundError,
)

# Cursor namespaces are distinct per output kind so a View Dataset cursor can
# never be replayed against the Analysis Artifact list (CURSOR_INVALID).
_VIEW_DATASET_CURSOR_NS = "future_dev.view_datasets"
_ANALYSIS_ARTIFACT_CURSOR_NS = "future_dev.analysis_artifacts"


def _capability_view(capability: FutureCapability) -> dict[str, Any]:
    state = capability.lifecycle_state
    return {
        "capability_key": capability.capability_key,
        "title": capability.title,
        "menu_path": capability.menu_path,
        "lifecycle_state": state.value,
        "is_operational": state in OPERATIONAL_STATES,
        "ui_surface_version": capability.ui_surface_version,
        "domain_contract_version": capability.domain_contract_version,
        "registry_version": capability.registry_version,
        "enabled_at": capability.enabled_at.isoformat() if capability.enabled_at else None,
        "retirement_at": (
            capability.retirement_at.isoformat() if capability.retirement_at else None
        ),
        "status_message": STATE_MESSAGES[state],
    }


async def list_capabilities(session: AsyncSession, actor: Actor) -> dict[str, Any]:
    """GET /capabilities (doc 22 §8): the client may cache the display state,
    but the server re-checks before any command dispatch."""
    require_authenticated(actor)
    rows = await capability_repo.list_capabilities(session)
    return {"capabilities": [_capability_view(row) for row in rows], "count": len(rows)}


async def get_capability(
    session: AsyncSession, actor: Actor, *, capability_key: str
) -> dict[str, Any]:
    """GET /capabilities/{key} (doc 22 §8): detail incl. the dependency
    snapshot and the last transition provenance."""
    require_authenticated(actor)
    capability = await capability_repo.get_capability_by_key(session, capability_key)
    if capability is None:
        raise CapabilityNotFoundError()
    return {
        **_capability_view(capability),
        "dependency_snapshot": capability.dependency_snapshot or {},
        "changed_by_actor_id": capability.changed_by_actor_id,
        "change_reason": capability.change_reason,
    }


async def get_graphic_view_overview(session: AsyncSession, actor: Actor) -> dict[str, Any]:
    """GET /future-dev/graphic_view/overview (doc 22 §4.1, §8, FD-01/03): the
    static intro + six future cards + the server-side registry state. No chart
    request, no View Dataset job, no marker computation, no persistence."""
    require_authenticated(actor)
    capability = await capability_repo.get_capability_by_key(session, GRAPHIC_VIEW)
    if capability is None:
        raise CapabilityNotFoundError()
    state = capability.lifecycle_state
    return {
        "capability_key": capability.capability_key,
        "title": capability.title,
        "lifecycle_state": state.value,
        "is_operational": state in OPERATIONAL_STATES,
        "registry_version": capability.registry_version,
        "intro": GRAPHIC_VIEW_INTRO,
        "cards": [dict(card) for card in GRAPHIC_VIEW_CARDS],
        "status_message": STATE_MESSAGES[state],
    }


# --------------------------------------------------------------------------- #
# Operational output history (owner-scoped, ACTIVE-only — doc 22 §7, §13)       #
# --------------------------------------------------------------------------- #


def _view_dataset_row(dataset: ViewDataset) -> dict[str, Any]:
    return {
        "view_dataset_id": dataset.view_dataset_id,
        "capability_key": dataset.capability_key,
        "schema_version": dataset.schema_version,
        "source_manifest_refs": list(dataset.source_manifest_refs or []),
        "series_refs": list(dataset.series_refs or []),
        "marker_refs": list(dataset.marker_refs or []),
        "range_spec": dataset.range_spec,
        "deletion_state": str(dataset.deletion_state),
        "row_version": dataset.row_version,
        "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
    }


def _analysis_artifact_row(artifact: AnalysisArtifact) -> dict[str, Any]:
    return {
        "artifact_id": artifact.artifact_id,
        "artifact_type": artifact.artifact_type,
        "capability_key": artifact.capability_key,
        "input_manifest_refs": list(artifact.input_manifest_refs or []),
        "method_version": artifact.method_version,
        "output_ref": artifact.output_ref,
        "deletion_state": str(artifact.deletion_state),
        "row_version": artifact.row_version,
        "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
    }


def _decode_last_key(cursor: str | None, *, namespace: str) -> str | None:
    if cursor is None:
        return None
    return decode_cursor(cursor, namespace=namespace).last_key


async def list_view_datasets(
    session: AsyncSession,
    actor: Actor,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Owner-scoped View Dataset history (doc 22 §7): a newest-first keyset page
    of the caller's own ACTIVE datasets. An empty page is real absence, never a
    fabricated row (futureDevNoHistory.empty)."""
    require_authenticated(actor)
    page_limit = clamp_limit(limit)
    last_key = _decode_last_key(cursor, namespace=_VIEW_DATASET_CURSOR_NS)
    rows = await capability_repo.list_view_datasets(
        session,
        owner_principal_id=actor.principal_id or "",
        last_key=last_key,
        limit=page_limit + 1,
    )
    has_more = len(rows) > page_limit
    page = rows[:page_limit]
    next_cursor = (
        encode_cursor(_VIEW_DATASET_CURSOR_NS, last_key=page[-1].view_dataset_id)
        if has_more and page
        else None
    )
    return {
        "data": [_view_dataset_row(row) for row in page],
        "meta": {"cursor": next_cursor, "has_more": has_more, "limit": page_limit},
    }


async def get_view_dataset(
    session: AsyncSession, actor: Actor, *, view_dataset_id: str
) -> dict[str, Any]:
    """Owner-scoped View Dataset detail (doc 22 §7): a missing, soft-deleted or
    cross-owner id is reported as not-found so existence never leaks."""
    require_authenticated(actor)
    dataset = await capability_repo.get_view_dataset(session, view_dataset_id)
    if (
        dataset is None
        or dataset.owner_principal_id != actor.principal_id
        or dataset.deletion_state != DeletionState.ACTIVE
    ):
        raise ViewDatasetNotFoundError()
    return {
        **_view_dataset_row(dataset),
        "owner_principal_id": dataset.owner_principal_id,
        "created_by_principal_id": dataset.created_by_principal_id,
    }


async def list_analysis_artifacts(
    session: AsyncSession,
    actor: Actor,
    *,
    artifact_type: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Owner-scoped Analysis Artifact history (doc 22 §7), optionally narrowed
    to one ``artifact_type``. Newest-first keyset over the caller's ACTIVE
    rows; an empty page is real absence."""
    require_authenticated(actor)
    page_limit = clamp_limit(limit)
    last_key = _decode_last_key(cursor, namespace=_ANALYSIS_ARTIFACT_CURSOR_NS)
    normalized_type = (artifact_type or "").strip().lower() or None
    rows = await capability_repo.list_analysis_artifacts(
        session,
        owner_principal_id=actor.principal_id or "",
        artifact_type=normalized_type,
        last_key=last_key,
        limit=page_limit + 1,
    )
    has_more = len(rows) > page_limit
    page = rows[:page_limit]
    next_cursor = (
        encode_cursor(_ANALYSIS_ARTIFACT_CURSOR_NS, last_key=page[-1].artifact_id)
        if has_more and page
        else None
    )
    return {
        "data": [_analysis_artifact_row(row) for row in page],
        "meta": {
            "cursor": next_cursor,
            "has_more": has_more,
            "limit": page_limit,
            "artifact_type": normalized_type,
        },
    }


async def get_analysis_artifact(
    session: AsyncSession, actor: Actor, *, artifact_id: str
) -> dict[str, Any]:
    """Owner-scoped Analysis Artifact detail (doc 22 §7): a missing, soft-deleted
    or cross-owner id is reported as not-found so existence never leaks."""
    require_authenticated(actor)
    artifact = await capability_repo.get_analysis_artifact(session, artifact_id)
    if (
        artifact is None
        or artifact.owner_principal_id != actor.principal_id
        or artifact.deletion_state != DeletionState.ACTIVE
    ):
        raise AnalysisArtifactNotFoundError()
    return {
        **_analysis_artifact_row(artifact),
        "owner_principal_id": artifact.owner_principal_id,
        "created_by_principal_id": artifact.created_by_principal_id,
    }


__all__ = [
    "get_analysis_artifact",
    "get_capability",
    "get_graphic_view_overview",
    "get_view_dataset",
    "list_analysis_artifacts",
    "list_capabilities",
    "list_view_datasets",
]
