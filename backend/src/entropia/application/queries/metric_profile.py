"""Arrange Metrics read models (Stage 5c, doc 17 §7, §8, §9.1).

Read-only projections. The metric registry + resolved profile drive PRESENTATION
only: ``get_result_metrics`` hydrates the immutable ``metric_value`` rows a Result
already carries, FILTERED + ORDERED by the caller's resolved profile — it never
recomputes a formula and never fabricates a value. A selected metric with no
persisted value is surfaced as ``not_computed`` (never 0, L4 — doc 17 §6, §11, §14).
A caller with no personal profile resolves to the in-memory System Default (the
nine selectable codes in registry order — doc 17 §4, §8.1).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.backtest.enums import MetricAvailability
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_view, require_authenticated
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.metric_profile.registry import DEFAULT_SELECTED_METRIC_CODES, REGISTRY_VERSION
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import metric_profile as mp_repo
from entropia.shared.errors import BacktestResultNotFoundError, CompositionNotFoundError

_ACTIVE = "active"
_SYSTEM_DEFAULT_PROFILE_ID = "system_default"


# --------------------------------------------------------------------------- #
# Metric definition registry                                                  #
# --------------------------------------------------------------------------- #


async def list_metric_definitions(
    session: AsyncSession,
    actor: Actor,
    *,
    availability: str | None = None,
) -> dict[str, Any]:
    """The metric registry (optionally availability-filtered), display-ordered.

    ``availability`` is a comma-separated status list (selectable/future/experimental);
    ``None`` returns the whole registry (doc 17 §3, §7)."""
    require_authenticated(actor)
    wanted = _parse_availability(availability)
    rows = await mp_repo.list_definitions(session, availability=wanted)
    return {
        "registry_version": REGISTRY_VERSION,
        "metric_definitions": [_definition_dto(row) for row in rows],
    }


# --------------------------------------------------------------------------- #
# Resolved profile                                                            #
# --------------------------------------------------------------------------- #


async def get_resolved_metric_profile(session: AsyncSession, actor: Actor) -> dict[str, Any]:
    """The caller's effective profile (personal, else System Default — doc 17 §8.1)."""
    require_authenticated(actor)
    resolved = await _resolve_profile(session, actor)
    return {
        "profile_id": resolved["profile_id"],
        "scope": resolved["scope"],
        "is_personal": resolved["is_personal"],
        "current_revision_id": resolved["current_revision_id"],
        "selected_metric_codes": resolved["selected_metric_codes"],
        "display_order": resolved["display_order"],
        "is_locked": resolved["is_locked"],
        "registry_version": REGISTRY_VERSION,
        "selected_metric_count": len(resolved["selected_metric_codes"]),
        # The id the client POSTs a revision to (first Apply forks a personal root).
        "editable_profile_id": resolved["profile_id"],
    }


# --------------------------------------------------------------------------- #
# Result metrics (hydrated by resolved profile)                               #
# --------------------------------------------------------------------------- #


async def get_result_metrics(
    session: AsyncSession, actor: Actor, *, result_id: str
) -> dict[str, Any]:
    """Immutable Result metrics filtered/ordered by the resolved profile (doc 17 §9.1).

    Presentation-only: values come straight from the persisted ``metric_value`` rows;
    a selected-but-absent metric is ``not_computed`` (never 0, L4). No mutation, no
    recompute, no new Backtest Run.
    """
    require_authenticated(actor)
    result = await bt_repo.get_result(session, result_id)
    if result is None or result.deletion_state != _ACTIVE:
        raise BacktestResultNotFoundError()
    await _ensure_can_view_workspace(session, actor, result.workspace_entity_id)

    resolved = await _resolve_profile(session, actor)
    metric_rows = await bt_repo.list_metric_values(session, result_id)
    by_key = {row.metric_key: row for row in metric_rows}
    definitions = {d.metric_code: d for d in await mp_repo.list_definitions(session)}

    cards: list[dict[str, Any]] = []
    for code in resolved["display_order"]:
        row = by_key.get(code)
        if row is not None:
            cards.append(_metric_card_from_row(row))
        else:
            cards.append(_metric_card_not_computed(code, definitions.get(code)))

    return {
        "result_id": result_id,
        "profile": {
            "profile_id": resolved["profile_id"],
            "scope": resolved["scope"],
            "is_personal": resolved["is_personal"],
            "is_locked": resolved["is_locked"],
            "registry_version": REGISTRY_VERSION,
        },
        "metrics": cards,
    }


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


async def _resolve_profile(session: AsyncSession, actor: Actor) -> dict[str, Any]:
    """Personal profile if present, else the in-memory System Default (doc 17 §8.1)."""
    personal = await mp_repo.get_personal_profile(session, actor.principal_id or "")
    if personal is not None and personal.current_revision_id is not None:
        revision = await mp_repo.get_revision(session, personal.current_revision_id)
        if revision is not None:
            return {
                "profile_id": personal.profile_id,
                "scope": "user",
                "is_personal": True,
                "current_revision_id": personal.current_revision_id,
                "selected_metric_codes": list(revision.selected_metric_codes),
                "display_order": list(revision.display_order),
                "is_locked": revision.is_locked,
            }
    default = list(DEFAULT_SELECTED_METRIC_CODES)
    return {
        "profile_id": _SYSTEM_DEFAULT_PROFILE_ID,
        "scope": "system_default",
        "is_personal": False,
        "current_revision_id": None,
        "selected_metric_codes": default,
        "display_order": default,
        "is_locked": False,
    }


async def _ensure_can_view_workspace(
    session: AsyncSession, actor: Actor, workspace_entity_id: str
) -> None:
    workspace = await mb_repo.get_workspace(session, workspace_entity_id)
    if workspace is None or workspace.deletion_state != DeletionState.ACTIVE:
        raise CompositionNotFoundError()
    ensure_can_view(actor, owner_principal_id=workspace.owner_principal_id, visibility="private")


def _parse_availability(availability: str | None) -> list[str] | None:
    if availability is None:
        return None
    values = [part.strip() for part in availability.split(",") if part.strip()]
    return values or None


def _definition_dto(row: Any) -> dict[str, Any]:
    return {
        "metric_code": row.metric_code,
        "label": row.label,
        "unit": row.unit,
        "value_format": row.value_format,
        "availability_status": str(row.availability_status),
        "display_order": row.display_order,
        "formula_version": row.formula_version,
        "description": row.description,
        "selectable": str(row.availability_status) == "selectable",
    }


def _metric_card_from_row(row: Any) -> dict[str, Any]:
    return {
        "key": row.metric_key,
        "label": row.label,
        "unit": row.unit,
        "value_format": row.value_format,
        "value": None if row.value is None else str(row.value),
        "availability": str(row.availability),
    }


def _metric_card_not_computed(code: str, definition: Any) -> dict[str, Any]:
    return {
        "key": code,
        "label": definition.label if definition is not None else code,
        "unit": definition.unit if definition is not None else None,
        "value_format": definition.value_format if definition is not None else None,
        "value": None,
        "availability": str(MetricAvailability.NOT_COMPUTED),
    }


__all__ = [
    "get_resolved_metric_profile",
    "get_result_metrics",
    "list_metric_definitions",
]
