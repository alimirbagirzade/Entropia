"""I-08 slice 1 — the registry-owner and strategy head/family edges are DB-enforced.

Before I-08 these three columns were plain VARCHARs: the code promised the target
existed, and a bug or a hand-written UPDATE could point a strategy at a revision
that was never written. These tests fail if the FK is dropped again — each one
writes a reference to an id that does not exist and demands the DATABASE reject it,
which is a claim no application-level check can satisfy.

The last test is the other half of the pair: the constraints must not break the
LEGAL path. A strategy root is still created with a NULL head and repointed after
the first Save, so no circular INSERT appears.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from entropia.application.commands import rationale as rationale_cmd
from entropia.application.commands import strategy_draft as strat_cmd
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role
from entropia.infrastructure.postgres.models import EntityRegistry, Principal, StrategyRoot
from entropia.shared.ids import new_id

pytestmark = pytest.mark.integration

USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_GHOST = "ghost_0000000000"


async def _seed_principal(session) -> None:
    if await session.get(Principal, USER.principal_id) is None:
        session.add(Principal(principal_id=USER.principal_id, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _strategy_root(session) -> StrategyRoot:
    await _seed_principal(session)
    created = await strat_cmd.create_strategy_draft(
        session, USER, display_name="STRATEGY 1", rationale_family_id=None
    )
    await session.flush()
    root = await session.get(StrategyRoot, created["strategy_root_id"])
    assert root is not None
    return root


async def test_fk_integrity_entity_registry_owner_rejects_unknown_principal(session) -> None:
    session.add(
        EntityRegistry(
            entity_id=new_id("ent"),
            entity_type="work_object",
            owner_principal_id=_GHOST,
            deletion_state=DeletionState.ACTIVE,
            row_version=1,
        )
    )
    # match= pins WHICH constraint fired: without it the test would still pass if
    # some unrelated NOT NULL rejected the row, and the FK could be dropped unseen.
    with pytest.raises(IntegrityError, match="entity_registry_owner_principal_id_fkey"):
        await session.flush()


async def test_fk_integrity_strategy_head_rejects_unknown_revision(session) -> None:
    root = await _strategy_root(session)

    root.current_revision_id = _GHOST
    with pytest.raises(IntegrityError, match="strategy_root_current_revision_id_fkey"):
        await session.flush()


async def test_fk_integrity_strategy_family_rejects_unknown_family(session) -> None:
    root = await _strategy_root(session)

    root.rationale_family_id = _GHOST
    with pytest.raises(IntegrityError, match="strategy_root_rationale_family_id_fkey"):
        await session.flush()


async def test_fk_integrity_leaves_the_legal_strategy_path_intact(session) -> None:
    """Root -> NULL head -> family set -> first Save repoints the head (no cycle)."""
    from tests.integration.test_strategy_integration import _valid_payload

    await _seed_principal(session)
    family = await rationale_cmd.create_family(session, USER, display_name="Momentum")
    payload = _valid_payload()
    payload["rationale_family_id"] = family["entity_id"]
    created = await strat_cmd.create_strategy_draft(
        session,
        USER,
        display_name="STRATEGY 1",
        rationale_family_id=None,
        initial_payload=payload,
    )
    await session.flush()
    root = await session.get(StrategyRoot, created["strategy_root_id"])
    assert root is not None
    assert root.current_revision_id is None  # created head-less, so no circular INSERT

    await strat_cmd.set_strategy_rationale_family(
        session,
        USER,
        strategy_root_id=root.entity_id,
        rationale_family_id=family["entity_id"],
    )
    await session.flush()
    await session.refresh(root)

    assert root.rationale_family_id == family["entity_id"]
    saved = await strat_cmd.save_strategy_revision(
        session,
        USER,
        draft_id=created["draft_id"],
        expected_draft_row_version=0,
    )
    await session.flush()
    await session.refresh(root)

    assert root.current_revision_id == saved["strategy_revision_id"]
