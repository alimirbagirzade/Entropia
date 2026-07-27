"""Agent artifact (Analysis Lab output) soft delete -> Trash (doc 20 §10, §11).

K-06: ``hypothesis_artifact`` has always been a canonical Trash object type
(``domain/trash/page.py`` -> "Analysis Lab / Outputs"), but the only writer of
its ``deletion_state`` — the Agent's ``artifact.soft_delete`` tool — never wrote
a Trash Entry. The artifact left the active board and became invisible: the
Admin type filter returned nothing, and Restore/Purge had no entry to act on.

This module owns the ONE soft-delete path for an artifact so the Trash Entry is
written in the same transaction as the state flip. Per doc 20:

* §10 — the owner Agent (or a permitted human) may soft delete; source task,
  checkpoint and provenance links are RETAINED and the Agent main loop is never
  stopped by the delete.
* §11 — the Agent has NO Trash list/restore/purge capability; recovery and
  permanent deletion stay Admin-only through the Trash commands.

An artifact is not a registry root (like ``backtest_result``, CR-03): its
lifecycle lives on the row's own ``deletion_state``/``row_version``, so restore
and purge dispatch on ``entity_type`` in ``commands/deletion.py`` and
``jobs/purge.py``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.identity.policy import can_edit
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.trash.page import original_location_for
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import trash as trash_repo
from entropia.shared.errors import ArtifactOwnershipError

ARTIFACT_ENTITY_TYPE = "hypothesis_artifact"
ARTIFACT_SOFT_DELETE_EVENT = "agent.artifact.soft_deleted"

# ``trash_entries.display_name`` is String(200); an artifact title is String(256).
_MAX_DISPLAY_NAME = 200


async def soft_delete_hypothesis_artifact(
    session: AsyncSession,
    actor: Actor,
    *,
    artifact_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Soft-delete an Agent-owned artifact and record it in Trash (one tx, no commit).

    Owner-or-Admin: the Agent principal owns only what it created, so a foreign
    artifact is ``ARTIFACT_NOT_OWNED`` for it (AL-16) while an Admin keeps the
    "permitted human" path doc 20 §10 describes. A repeat delete is an idempotent
    no-op that returns the current state and never writes a second entry
    (doc 20 §14).
    """
    artifact = await al_repo.get_hypothesis(session, artifact_id)
    if artifact is None:
        raise ArtifactOwnershipError("The artifact to soft-delete was not found.")
    if not can_edit(actor, owner_principal_id=artifact.created_by_principal_id):
        raise ArtifactOwnershipError()

    await session.refresh(artifact, with_for_update=True)
    if artifact.deletion_state is not DeletionState.ACTIVE:
        return {"artifact_id": artifact_id, "deletion_state": str(artifact.deletion_state)}

    artifact.deletion_state = DeletionState.SOFT_DELETED
    artifact.row_version += 1

    # Provenance the Admin needs to judge a restore/purge — the source task and
    # checkpoint rows themselves are never touched (doc 20 §10).
    provenance = {
        "source_task_id": artifact.source_task_id,
        "checkpoint_id": artifact.checkpoint_id,
    }
    trash_repo.add_trash_entry(
        session,
        entity_id=artifact_id,
        entity_type=ARTIFACT_ENTITY_TYPE,
        deleted_by=actor.principal_id,
        reason=reason,
        owner_at_deletion=artifact.created_by_principal_id,
        dependency_snapshot=provenance,
        display_name=artifact.title[:_MAX_DISPLAY_NAME],
        original_location=original_location_for(ARTIFACT_ENTITY_TYPE),
        deletion_snapshot={
            **provenance,
            "title": artifact.title[:_MAX_DISPLAY_NAME],
            "artifact_status": str(artifact.status),
        },
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_audit_event(
        session,
        event_kind=ARTIFACT_SOFT_DELETE_EVENT,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=artifact_id,
        target_entity_type=ARTIFACT_ENTITY_TYPE,
        previous_state=str(DeletionState.ACTIVE),
        new_state=DeletionState.SOFT_DELETED.value,
        reason=reason,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type=ARTIFACT_SOFT_DELETE_EVENT,
        resource_type=ARTIFACT_ENTITY_TYPE,
        resource_id=artifact_id,
        payload={"artifact_id": artifact_id, "deletion_state": DeletionState.SOFT_DELETED.value},
        correlation_id=actor.correlation_id,
    )
    return {"artifact_id": artifact_id, "deletion_state": DeletionState.SOFT_DELETED.value}


__all__ = [
    "ARTIFACT_ENTITY_TYPE",
    "ARTIFACT_SOFT_DELETE_EVENT",
    "soft_delete_hypothesis_artifact",
]
