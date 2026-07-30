"""I-09 — the Trash detail endpoint redacts + bounds the stored snapshot (doc 20 §12).

The unit proofs for ``redact_snapshot`` live in
``tests/unit/test_trash_snapshot_redaction.py``. This file proves the WIRING:
a credential written into ``trash_entries.deletion_snapshot`` (the way a future
writer might, silently) never reaches ``get_trash_entry_detail``'s response,
and an oversized stored snapshot comes back bounded and flagged.

The stored column is deliberately left intact — restore preflight reads the raw
``dependency_snapshot`` head pointer as integrity evidence, so redaction must be
presentation-only or restore would start comparing against ``"<redacted>"``.
"""

from __future__ import annotations

import json

import pytest

from entropia.application.commands.deletion import soft_delete_entity
from entropia.application.commands.entities import create_entity
from entropia.application.queries.trash import get_restore_preflight, get_trash_entry_detail
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.trash.redaction import REDACTED, TRUNCATED_KEY
from entropia.infrastructure.postgres.models import Principal
from entropia.infrastructure.postgres.repositories import trash as trash_repo

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _entry_with_snapshot(session, snapshot: dict):
    """Soft-delete a root, then write ``snapshot`` onto its entry — simulating a
    writer that stores a field nobody vetted."""
    if await session.get(Principal, USER.principal_id) is None:
        session.add(Principal(principal_id=USER.principal_id, principal_type=PrincipalType.HUMAN))
        await session.flush()
    root = await create_entity(session, USER, entity_type="demo_entity", payload={"v": 1})
    await session.commit()
    await soft_delete_entity(session, USER, entity_id=root.entity_id, reason="cleanup")
    await session.commit()

    entry = await trash_repo.get_recoverable_entry_for_entity(session, root.entity_id)
    assert entry is not None
    entry.deletion_snapshot = {**(entry.deletion_snapshot or {}), **snapshot}
    await session.commit()
    return entry


async def test_detail_never_renders_an_injected_credential(session) -> None:
    entry = await _entry_with_snapshot(session, {"api_key": "sk-xxx"})

    detail = await get_trash_entry_detail(session, ADMIN, trash_entry_id=entry.id)

    assert "sk-xxx" not in json.dumps(detail)
    assert detail["deletion_snapshot"]["api_key"] == REDACTED
    # The reviewed keys still render — redaction is a filter, not a blackout.
    assert detail["deletion_snapshot"]["current_revision_id"] is not None


async def test_detail_bounds_a_ten_megabyte_snapshot(session) -> None:
    entry = await _entry_with_snapshot(
        session, {"title": "z" * 100_000, **{f"blob_{i}": "y" * 100_000 for i in range(100)}}
    )

    detail = await get_trash_entry_detail(session, ADMIN, trash_entry_id=entry.id)
    encoded = json.dumps(detail["deletion_snapshot"]).encode()

    assert len(encoded) <= 16_384
    assert detail["deletion_snapshot"][TRUNCATED_KEY] is True


async def test_redaction_does_not_disturb_restore_preflight(session) -> None:
    """Presentation-only: the raw stored head pointer still drives preflight."""
    entry = await _entry_with_snapshot(session, {"api_key": "sk-xxx"})

    preflight = await get_restore_preflight(session, ADMIN, trash_entry_id=entry.id)

    assert preflight["outcome"] == "allow"
    assert entry.deletion_snapshot["api_key"] == "sk-xxx"  # column untouched
