"""R4 — Admin Logs "Resource type" filter hydrates from the real distinct
``target_entity_type`` set, not a hand-curated list that silently drifts.

The Logs filter matches ``target_entity_type`` EXACTLY (``log_projection._apply_filters``);
a curated option that no emitter ever produces returns an empty page with no error. This
suite pins the distinct-set query: every returned option is a real emitted target, the set
is admin-gated, NULL targets are excluded, and the six previously-broken frontend options
(``user``, ``package_revision``, ``dataset_revision``, ``artifact``, ``allocation_plan``,
``system``) can never appear because no emitter produces them.
"""

from __future__ import annotations

import pytest

from entropia.application.queries.log_projection import list_resource_types
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import ActorKind, PrincipalType, Role
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.shared.errors import AdminPanelAccessRequiredError

pytestmark = pytest.mark.integration

ADMIN = Actor(
    principal_id="user_admin",
    principal_type=PrincipalType.HUMAN,
    role=Role.ADMIN,
    correlation_id="corr_admin",
)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

# A representative slice of REAL emitted target_entity_type values (verified by an AST
# scan of every ``target_entity_type=`` emit site under application/) — the exact values
# the six broken frontend options should have mapped to.
_REAL_TARGETS = [
    "human_user",  # roles.py / role_assignment.py — was mis-listed as "user"
    "package",  # pkg_repo.ENTITY_TYPE — was mis-listed as "package_revision"
    "market_dataset",  # md_repo.ENTITY_TYPE — was mis-listed under "dataset_revision"
    "research_dataset",  # rd_repo.ENTITY_TYPE
    "analysis_artifact",  # capability.py — was collapsed into "artifact"
    "portfolio_allocation_plan",  # allocation_plan.py — was mis-listed as "allocation_plan"
    "strategy",  # a working option, still emitted
    "backtest_run",
]
# The six curated options that matched no emitter → silent empty page (the bug).
_BROKEN_OPTIONS = {
    "user",
    "package_revision",
    "dataset_revision",
    "artifact",
    "allocation_plan",
    "system",
}


def _seed(session, target_type: str | None) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind="test.event",
        actor_principal_id="user_admin",
        actor_kind=ActorKind.HUMAN,
        target_entity_id="ent_x" if target_type else None,
        target_entity_type=target_type,
    )


async def test_empty_log_yields_no_resource_types(session) -> None:
    # No dead options on a fresh deployment: an option can only exist once a real
    # event has carried that type.
    assert await list_resource_types(session, ADMIN) == {"resource_types": []}


async def test_returns_sorted_distinct_non_null_real_targets(session) -> None:
    for target in _REAL_TARGETS:
        _seed(session, target)
        _seed(session, target)  # duplicate → still one option
    _seed(session, None)  # NULL target (e.g. a system event) → excluded
    await session.flush()

    result = await list_resource_types(session, ADMIN)
    options = result["resource_types"]

    # Sorted, de-duplicated, NULL excluded.
    assert options == sorted(set(_REAL_TARGETS))
    # Every returned option is a real emitted target (the R4 invariant).
    assert set(options) == set(_REAL_TARGETS)
    # None of the six previously-broken curated options can appear — no emitter
    # produces them, so hydrating from the DB structurally cannot resurrect the drift.
    assert _BROKEN_OPTIONS.isdisjoint(options)


async def test_non_admin_is_rejected(session) -> None:
    _seed(session, "strategy")
    await session.flush()
    with pytest.raises(AdminPanelAccessRequiredError):
        await list_resource_types(session, USER)
