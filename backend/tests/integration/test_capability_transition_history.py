"""Stage 7b follow-up — Future Dev capability lifecycle-transition HISTORY read
surface (doc 22 §9, §13). Auto-skips without PostgreSQL.

The immutable, append-only activation-event timeline for one capability: an
Admin transition appends exactly one event, and ``get_capability_transitions``
replays them oldest-first by resulting registry version. Any authenticated
principal may read registry provenance (the write path stays Admin-only); a
never-transitioned capability returns a real empty timeline; an unknown key is a
canonical not-found.
"""

from __future__ import annotations

import pytest

from entropia.application.commands.capability import transition_capability
from entropia.application.queries.capability import get_capability_transitions
from entropia.domain.capability.baseline import initial_dependency_snapshot
from entropia.domain.capability.enums import GRAPHIC_VIEW, LIVE_TRADE, ActivationGate
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import Principal
from entropia.infrastructure.postgres.repositories import capability as capability_repo
from entropia.shared.errors import CapabilityNotFoundError

pytestmark = pytest.mark.integration

ADMIN = Actor(
    principal_id="user_admin",
    principal_type=PrincipalType.HUMAN,
    role=Role.ADMIN,
    correlation_id="corr_adm",
)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

# Limited needs every gate complete except UI; Active needs all seven (§9.2).
GATES_WITHOUT_UI = {"gates": {gate.value: gate is not ActivationGate.UI for gate in ActivationGate}}
GATES_ALL = {"gates": {gate.value: True for gate in ActivationGate}}


async def _seed(session) -> None:
    for actor in (ADMIN, USER):
        session.add(Principal(principal_id=actor.principal_id, principal_type=actor.principal_type))
    await capability_repo.seed_baseline_capabilities(session)
    await session.commit()


async def _walk_to_limited(session, key: str) -> None:
    """placeholder -> designed -> internal -> shadow -> limited (legal chain)."""
    steps = (
        ("designed", 1, initial_dependency_snapshot()),
        ("internal", 2, None),
        ("shadow", 3, None),
        ("limited", 4, GATES_WITHOUT_UI),
    )
    for to_state, expected, snapshot in steps:
        await transition_capability(
            session,
            ADMIN,
            capability_key=key,
            to_state=to_state,
            reason=f"activate {key} to {to_state}",
            expected_registry_version=expected,
            dependency_snapshot=snapshot,
            idempotency_key=f"{key}-{to_state}",
        )
    await session.commit()


async def test_transition_timeline_oldest_first_with_full_provenance(session) -> None:
    await _seed(session)
    await _walk_to_limited(session, GRAPHIC_VIEW)

    # Any authenticated principal (here a plain USER) reads registry provenance.
    result = await get_capability_transitions(session, USER, capability_key=GRAPHIC_VIEW)
    assert result["capability_key"] == GRAPHIC_VIEW
    assert result["count"] == 4

    transitions = result["transitions"]
    # Oldest-first by resulting registry version — the transition chain replayed.
    assert [(t["from_state"], t["to_state"]) for t in transitions] == [
        ("placeholder", "designed"),
        ("designed", "internal"),
        ("internal", "shadow"),
        ("shadow", "limited"),
    ]
    assert [t["resulting_registry_version"] for t in transitions] == [2, 3, 4, 5]
    assert [t["prior_registry_version"] for t in transitions] == [1, 2, 3, 4]
    # Every event carries the Admin actor, a reason, a snapshot checksum and a
    # timestamp — immutable audit provenance (doc 22 §13).
    assert all(t["actor_principal_id"] == ADMIN.principal_id for t in transitions)
    assert transitions[-1]["reason"] == f"activate {GRAPHIC_VIEW} to limited"
    assert all(t["snapshot_checksum"] for t in transitions)
    assert all(t["occurred_at"] is not None for t in transitions)


async def test_transition_timeline_tracks_a_newly_appended_transition(session) -> None:
    await _seed(session)
    await _walk_to_limited(session, GRAPHIC_VIEW)
    # One more legal transition (limited -> active needs every gate complete).
    await transition_capability(
        session,
        ADMIN,
        capability_key=GRAPHIC_VIEW,
        to_state="active",
        reason="promote to active",
        expected_registry_version=5,
        dependency_snapshot=GATES_ALL,
        idempotency_key="gv-active",
    )
    await session.commit()

    result = await get_capability_transitions(session, USER, capability_key=GRAPHIC_VIEW)
    assert result["count"] == 5
    newest = result["transitions"][-1]
    assert (newest["from_state"], newest["to_state"]) == ("limited", "active")
    assert newest["resulting_registry_version"] == 6


async def test_transition_timeline_empty_for_never_transitioned_capability(session) -> None:
    """A freshly-seeded placeholder has appended no activation event yet — a real
    empty timeline, never a fabricated row."""
    await _seed(session)
    result = await get_capability_transitions(session, USER, capability_key=LIVE_TRADE)
    assert result["capability_key"] == LIVE_TRADE
    assert result["transitions"] == []
    assert result["count"] == 0


async def test_transition_timeline_unknown_key_is_not_found(session) -> None:
    await _seed(session)
    with pytest.raises(CapabilityNotFoundError):
        await get_capability_transitions(session, USER, capability_key="not_a_capability")
