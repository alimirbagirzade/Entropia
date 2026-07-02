"""User Manual commands (Stage 7a, doc 21 §7, §8.2-§8.4, §10, §11).

Each command is ONE transaction (no commit here): canonical-block parse +
root/revision/stream-entry/search-chunk rows + publication event + audit +
outbox move together, so a failed parse/validation publishes NOTHING and the
prior reader stream survives untouched (doc 21 §10 recovery principle).

Every stream mutation takes the global advisory stream lock first, giving
concurrent Admin appends deterministic unique positions (UM-13). Write policy
is Admin-only at route AND service (``require_manual_admin``); soft delete
integrates the landed Trash core by writing a page-contract Trash entry under
``MANUAL_ENTITY_TYPE`` (restore runs through Admin Trash, doc 21 §8.4).
The search projection is built in the same transaction — publication is
atomic; index freshness may still be surfaced as eventually consistent to
clients (doc 21 §7).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_manual_admin, require_trash_admin
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.manual.blocks import (
    MAX_TITLE_LENGTH,
    build_search_chunks,
    has_visible_text,
    normalized_checksum,
    parse_source,
)
from entropia.domain.manual.enums import (
    MANUAL_ENTITY_TYPE,
    SOURCE_TYPE_BY_EXTENSION,
    ManualSourceType,
    PublicationState,
)
from entropia.domain.manual.enums import StreamEntryState as EntryState
from entropia.domain.manual.stream import section_anchor
from entropia.domain.trash.page import original_location_for
from entropia.infrastructure.postgres.models import ManualDocument
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import manual as manual_repo
from entropia.infrastructure.postgres.repositories import trash as trash_repo
from entropia.shared.errors import (
    BaselineManualImmutableError,
    EntityNotSoftDeletedError,
    LifecycleBlocked,
    ManualContentRequiredError,
    ManualDocumentNotFoundError,
    ManualDuplicateContentError,
    ManualFileTypeUnsupportedError,
    ManualRevisionConflictError,
    ManualSourceEncodingInvalidError,
    ManualStreamConflictError,
    ManualTitleRequiredError,
    ObjectAlreadyPurgedError,
    PurgeInProgressError,
    ValidationError,
)

MAX_SOURCE_CHARS = 1_000_000


# --------------------------------------------------------------------------- #
# Validation helpers                                                           #
# --------------------------------------------------------------------------- #


def _normalize_title(raw: str | None) -> str:
    title = " ".join((raw or "").split())
    if not title:
        raise ManualTitleRequiredError()
    if len(title) > MAX_TITLE_LENGTH:
        raise ValidationError(f"The document title exceeds {MAX_TITLE_LENGTH} characters.")
    return title


def _ensure_utf8_text(content: str) -> str:
    if len(content) > MAX_SOURCE_CHARS:
        raise ValidationError("The document exceeds the maximum accepted size.")
    if "\x00" in content:
        raise ManualSourceEncodingInvalidError()
    try:
        content.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ManualSourceEncodingInvalidError() from exc
    return content


def _source_type_for_upload(source_filename: str) -> ManualSourceType:
    suffix = PurePosixPath(source_filename.strip().lower()).suffix
    source_type = SOURCE_TYPE_BY_EXTENSION.get(suffix)
    if source_type is None:
        raise ManualFileTypeUnsupportedError()
    return source_type


async def _assert_stream_version(session: AsyncSession, expected: int | None) -> int:
    current = await manual_repo.current_stream_version(session)
    if expected is not None and expected != current:
        raise ManualStreamConflictError()
    return current


async def _require_document(session: AsyncSession, document_id: str) -> ManualDocument:
    document = await manual_repo.get_document(session, document_id)
    if document is None:
        raise ManualDocumentNotFoundError()
    return document


def _audit_and_outbox(
    session: AsyncSession,
    actor: Actor,
    *,
    event_kind: str,
    document_id: str,
    revision_id: str | None,
    previous_state: str | None,
    new_state: str | None,
    payload: dict[str, Any],
    reason: str | None = None,
) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind=event_kind,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=document_id,
        target_entity_type=MANUAL_ENTITY_TYPE,
        target_revision_id=revision_id,
        previous_state=previous_state,
        new_state=new_state,
        reason=reason,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type=event_kind,
        resource_type=MANUAL_ENTITY_TYPE,
        resource_id=document_id,
        payload=payload,
        correlation_id=actor.correlation_id,
    )


# --------------------------------------------------------------------------- #
# Publish (Add/Paste + Upload share one pipeline — doc 21 §14)                  #
# --------------------------------------------------------------------------- #


async def _publish_new_document(
    session: AsyncSession,
    actor: Actor,
    *,
    title: str,
    content: str,
    source_type: ManualSourceType,
    source_filename: str | None,
    allow_duplicate: bool,
    expected_stream_version: int | None,
) -> dict[str, Any]:
    await manual_repo.lock_stream(session)
    prior_version = await _assert_stream_version(session, expected_stream_version)

    blocks = parse_source(source_type, content)
    if not has_visible_text(blocks):
        raise ManualContentRequiredError()
    checksum = normalized_checksum(blocks)
    if not allow_duplicate:
        duplicate_of = await manual_repo.find_active_duplicate(session, checksum=checksum)
        if duplicate_of is not None:
            raise ManualDuplicateContentError()

    document = await manual_repo.create_document(
        session,
        owner_principal_id=actor.principal_id,
        created_by_principal_id=actor.principal_id,
    )
    revision = await manual_repo.create_revision(
        session,
        document_id=document.document_id,
        revision_no=1,
        title=title,
        source_type=source_type,
        source_filename=source_filename,
        content_checksum=checksum,
        created_by_principal_id=actor.principal_id,
        blocks=blocks,
    )
    document.current_revision_id = revision.revision_id
    position = await manual_repo.next_stream_position(session)
    entry = await manual_repo.create_stream_entry(
        session,
        document_id=document.document_id,
        stream_position=position,
        visible_revision_id=revision.revision_id,
    )
    anchor = section_anchor(document.document_id)
    manual_repo.add_search_chunks(
        session,
        document_id=document.document_id,
        revision_id=revision.revision_id,
        chunks=build_search_chunks(title, anchor, blocks),
    )
    stream_version = prior_version + 1
    manual_repo.add_publication_event(
        session,
        event_type="manual_document_published",
        document_id=document.document_id,
        revision_id=revision.revision_id,
        stream_entry_id=entry.stream_entry_id,
        actor_principal_id=actor.principal_id,
        prior_stream_version=prior_version,
        resulting_stream_version=stream_version,
        source_type=source_type.value,
        source_filename=source_filename,
        checksum=checksum,
        correlation_id=actor.correlation_id,
    )
    _audit_and_outbox(
        session,
        actor,
        event_kind="manual.document_published",
        document_id=document.document_id,
        revision_id=revision.revision_id,
        previous_state=None,
        new_state=PublicationState.PUBLISHED.value,
        payload={
            "document_id": document.document_id,
            "revision_id": revision.revision_id,
            "anchor": anchor,
            "stream_version": stream_version,
        },
    )
    return {
        "document_id": document.document_id,
        "revision_id": revision.revision_id,
        "revision_no": revision.revision_no,
        "stream_entry_id": entry.stream_entry_id,
        "stream_position": position,
        "anchor": anchor,
        "title": title,
        "checksum": checksum,
        "stream_version": stream_version,
        "correlation_id": actor.correlation_id,
    }


async def create_manual_document(
    session: AsyncSession,
    actor: Actor,
    *,
    title: str,
    content: str,
    allow_duplicate: bool = False,
    expected_stream_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Admin Add/Paste append (doc 21 §8.2, UM-04): atomic root + Published
    revision + stream entry + chunks + publication event + audit/outbox."""
    require_manual_admin(actor)
    final_title = _normalize_title(title)
    _ensure_utf8_text(content)

    async def _op() -> dict[str, Any]:
        return await _publish_new_document(
            session,
            actor,
            title=final_title,
            content=content,
            source_type=ManualSourceType.ADDED_TEXT,
            source_filename=None,
            allow_duplicate=allow_duplicate,
            expected_stream_version=expected_stream_version,
        )

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "manual.document.create",
            "title": final_title,
            "content": content,
            "allow_duplicate": allow_duplicate,
            "expected_stream_version": expected_stream_version,
        },
        operation=_op,
    )


async def upload_manual_document(
    session: AsyncSession,
    actor: Actor,
    *,
    source_filename: str,
    content: str,
    title: str | None = None,
    allow_duplicate: bool = False,
    expected_stream_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Admin upload (doc 21 §8.3, UM-05/06): TXT/MD/HTML only; the title is
    filename-derived but must be non-empty at commit; same atomic pipeline."""
    require_manual_admin(actor)
    source_type = _source_type_for_upload(source_filename)
    derived = title if title is not None else PurePosixPath(source_filename).stem
    final_title = _normalize_title(derived)
    _ensure_utf8_text(content)

    async def _op() -> dict[str, Any]:
        return await _publish_new_document(
            session,
            actor,
            title=final_title,
            content=content,
            source_type=source_type,
            source_filename=source_filename,
            allow_duplicate=allow_duplicate,
            expected_stream_version=expected_stream_version,
        )

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "manual.document.upload",
            "source_filename": source_filename,
            "title": final_title,
            "content": content,
            "allow_duplicate": allow_duplicate,
            "expected_stream_version": expected_stream_version,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Replace revision (backend capability; V18 UI not exposed — doc 21 §7)         #
# --------------------------------------------------------------------------- #


async def replace_manual_revision(
    session: AsyncSession,
    actor: Actor,
    *,
    document_id: str,
    content: str,
    title: str | None = None,
    expected_head_revision_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Publish revision N+1 at the SAME stream position (doc 21 §7, UM-11):
    the old revision becomes Superseded; the position never moves."""
    require_manual_admin(actor)
    _ensure_utf8_text(content)

    async def _op() -> dict[str, Any]:
        document = await _require_document(session, document_id)
        if document.is_baseline:
            raise BaselineManualImmutableError()
        await manual_repo.lock_stream(session)
        await session.refresh(document, with_for_update=True)
        if document.deletion_state != DeletionState.ACTIVE:
            raise LifecycleBlocked()
        if (
            expected_head_revision_id is not None
            and expected_head_revision_id != document.current_revision_id
        ):
            raise ManualRevisionConflictError()
        head_id = document.current_revision_id
        head = await manual_repo.get_revision(session, head_id) if head_id else None
        if head is None:
            raise ManualRevisionConflictError()
        entry = await manual_repo.get_stream_entry(session, document_id)
        if entry is None or entry.state != EntryState.ACTIVE:
            raise LifecycleBlocked()

        final_title = _normalize_title(title if title is not None else head.title)
        blocks = parse_source(ManualSourceType.ADDED_TEXT, content)
        if not has_visible_text(blocks):
            raise ManualContentRequiredError()
        checksum = normalized_checksum(blocks)

        revision = await manual_repo.create_revision(
            session,
            document_id=document_id,
            revision_no=head.revision_no + 1,
            title=final_title,
            source_type=ManualSourceType.ADDED_TEXT,
            source_filename=None,
            content_checksum=checksum,
            created_by_principal_id=actor.principal_id,
            blocks=blocks,
        )
        head.publication_state = PublicationState.SUPERSEDED
        document.current_revision_id = revision.revision_id
        document.row_version += 1
        entry.visible_revision_id = revision.revision_id
        entry.row_version += 1
        anchor = section_anchor(document_id)
        manual_repo.add_search_chunks(
            session,
            document_id=document_id,
            revision_id=revision.revision_id,
            chunks=build_search_chunks(final_title, anchor, blocks),
        )
        prior_version = await manual_repo.current_stream_version(session)
        stream_version = prior_version + 1
        manual_repo.add_publication_event(
            session,
            event_type="manual_document_revised",
            document_id=document_id,
            revision_id=revision.revision_id,
            stream_entry_id=entry.stream_entry_id,
            actor_principal_id=actor.principal_id,
            prior_stream_version=prior_version,
            resulting_stream_version=stream_version,
            source_type=ManualSourceType.ADDED_TEXT.value,
            checksum=checksum,
            correlation_id=actor.correlation_id,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="manual.document_revised",
            document_id=document_id,
            revision_id=revision.revision_id,
            previous_state=head.revision_id,
            new_state=revision.revision_id,
            payload={
                "document_id": document_id,
                "revision_id": revision.revision_id,
                "superseded_revision_id": head.revision_id,
                "stream_version": stream_version,
            },
        )
        return {
            "document_id": document_id,
            "revision_id": revision.revision_id,
            "revision_no": revision.revision_no,
            "superseded_revision_id": head.revision_id,
            "stream_position": entry.stream_position,
            "anchor": anchor,
            "stream_version": stream_version,
            "correlation_id": actor.correlation_id,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "manual.document.revise",
            "document_id": document_id,
            "title": title,
            "content": content,
            "expected_head_revision_id": expected_head_revision_id,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Soft delete -> Trash (doc 21 §8.4, UM-08)                                     #
# --------------------------------------------------------------------------- #


async def soft_delete_manual_document(
    session: AsyncSession,
    actor: Actor,
    *,
    document_id: str,
    reason: str | None = None,
    expected_stream_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Admin-only soft delete of a non-baseline document: the root goes
    ``soft_deleted``, the stream entry leaves the reader/search projection but
    KEEPS its unique position (deterministic restore), and a page-contract
    Trash entry is written (doc 21 §8.4, §11)."""
    require_manual_admin(actor)

    async def _op() -> dict[str, Any]:
        document = await _require_document(session, document_id)
        if document.is_baseline:
            raise BaselineManualImmutableError()
        await manual_repo.lock_stream(session)
        await session.refresh(document, with_for_update=True)

        previous = document.deletion_state
        if previous == DeletionState.SOFT_DELETED:
            entry_row = await trash_repo.get_recoverable_entry_for_entity(session, document_id)
            return {
                "document_id": document_id,
                "deletion_state": DeletionState.SOFT_DELETED.value,
                "trash_entry_id": entry_row.id if entry_row is not None else None,
                "stream_version": await manual_repo.current_stream_version(session),
                "idempotent_repeat": True,
                "correlation_id": actor.correlation_id,
            }
        if previous == DeletionState.PURGE_PENDING:
            raise PurgeInProgressError()
        if previous == DeletionState.PURGED:
            raise ObjectAlreadyPurgedError()

        prior_version = await _assert_stream_version(session, expected_stream_version)
        stream_entry = await manual_repo.get_stream_entry(session, document_id)
        head = (
            await manual_repo.get_revision(session, document.current_revision_id)
            if document.current_revision_id
            else None
        )
        title = head.title if head is not None else document_id

        document.deletion_state = DeletionState.SOFT_DELETED
        document.deleted_at = datetime.now(UTC)
        document.deleted_by = actor.principal_id
        document.delete_reason = reason
        document.row_version += 1
        if stream_entry is not None:
            stream_entry.state = EntryState.REMOVED
            stream_entry.row_version += 1

        trash_entry = trash_repo.add_trash_entry(
            session,
            entity_id=document_id,
            entity_type=MANUAL_ENTITY_TYPE,
            deleted_by=actor.principal_id,
            reason=reason,
            owner_at_deletion=document.owner_principal_id,
            dependency_snapshot={"current_revision_id": document.current_revision_id},
            display_name=title,
            original_location=original_location_for(MANUAL_ENTITY_TYPE),
            deletion_snapshot={
                "current_revision_id": document.current_revision_id,
                "stream_position": (
                    stream_entry.stream_position if stream_entry is not None else None
                ),
                "title": title,
            },
            correlation_id=actor.correlation_id,
        )
        stream_version = prior_version + 1
        manual_repo.add_publication_event(
            session,
            event_type="manual_document_soft_deleted",
            document_id=document_id,
            revision_id=document.current_revision_id,
            stream_entry_id=stream_entry.stream_entry_id if stream_entry is not None else None,
            actor_principal_id=actor.principal_id,
            prior_stream_version=prior_version,
            resulting_stream_version=stream_version,
            correlation_id=actor.correlation_id,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="manual.document_soft_deleted",
            document_id=document_id,
            revision_id=document.current_revision_id,
            previous_state=str(previous),
            new_state=DeletionState.SOFT_DELETED.value,
            payload={
                "document_id": document_id,
                "trash_entry_id": trash_entry.id,
                "stream_version": stream_version,
            },
            reason=reason,
        )
        return {
            "document_id": document_id,
            "deletion_state": DeletionState.SOFT_DELETED.value,
            "trash_entry_id": trash_entry.id,
            "display_name": title,
            "stream_version": stream_version,
            "correlation_id": actor.correlation_id,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "manual.document.soft_delete",
            "document_id": document_id,
            "expected_stream_version": expected_stream_version,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Restore (thin wrapper over the landed Trash core — doc 21 §8.4, UM-09)        #
# --------------------------------------------------------------------------- #


async def restore_manual_document(
    session: AsyncSession,
    actor: Actor,
    *,
    document_id: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """POST :restore addressed by document id: resolves the recoverable Trash
    entry and delegates to the landed Admin Trash restore (same root/revision
    chain, deterministic original position — doc 21 §8.4)."""
    require_trash_admin(actor)
    entry = await trash_repo.get_recoverable_entry_for_entity(session, document_id)
    if entry is None:
        raise EntityNotSoftDeletedError()

    from entropia.application.commands.deletion import restore_trash_entry

    return await restore_trash_entry(
        session, actor, trash_entry_id=entry.id, idempotency_key=idempotency_key
    )


__all__ = [
    "create_manual_document",
    "replace_manual_revision",
    "restore_manual_document",
    "soft_delete_manual_document",
    "upload_manual_document",
]
