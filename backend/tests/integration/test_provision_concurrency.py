"""Provisioning is idempotent under REPEAT and under CONCURRENCY (ADIM 22).

``python -m entropia.apps.seed`` is not a developer convenience: docker-compose's
``provision`` one-shot runs it, and every plane gates on it via
``service_completed_successfully`` (docker-compose.yml ``x-needs-provision``). So
a provisioning run that exits non-zero because a second one was racing it does
not "just retry" — it stops the API, all four worker planes, the coordinator and
the scheduler from starting.

Before ``lock_provisioning``, that is exactly what happened. Every guard in the
seed is SELECT-then-INSERT and the whole seed commits once at the end, so under
READ COMMITTED the second run cannot see the first one's uncommitted rows: both
pass "does it already exist?", and the loser dies on ``principals_pkey``,
rolling back its entire transaction. Reproduced at the process level by
``scripts/migration-acceptance.sh`` step [8]; pinned here at the session level.

These tests drive the REAL body (``seed.provision``) on their own connections —
the same second-connection idiom as ``test_worker_delivery_recovery.py`` — because
concurrency cannot be observed inside a single session.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select

from entropia.apps import seed as seed_mod
from entropia.apps.seed import DEFAULT_AGENT_ID
from entropia.domain.agent_lab.enums import ALPHA_AGENT_ID
from entropia.infrastructure.postgres.models import (
    Agent,
    HumanUser,
    Principal,
    RationaleFamilyRevision,
    RationaleFamilyRoot,
)
from entropia.infrastructure.postgres.models.agent_lab import AgentRuntime

pytestmark = pytest.mark.asyncio


class _NullLog:
    def info(self, *args: object, **kwargs: object) -> None: ...
    def warning(self, *args: object, **kwargs: object) -> None: ...


async def _own_engine():
    """A private engine + session factory on the isolated integration database."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from .conftest import DATABASE_URL

    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    return engine, async_sessionmaker(bind=engine, expire_on_commit=False)


async def _provision_once() -> None:
    """One full provisioning run in its own transaction — what the one-shot does."""
    engine, factory = await _own_engine()
    try:
        async with factory() as s:
            await seed_mod.provision(s, _NullLog())
            await s.commit()
    finally:
        await engine.dispose()


async def _identity_counts(session) -> dict[str, int]:
    return {
        "principals": (
            await session.execute(select(func.count()).select_from(Principal))
        ).scalar_one(),
        "human_users": (
            await session.execute(select(func.count()).select_from(HumanUser))
        ).scalar_one(),
        "agents": (await session.execute(select(func.count()).select_from(Agent))).scalar_one(),
    }


async def test_concurrent_provisioning_runs_all_succeed(session) -> None:
    """Three simultaneous provisioning runs: none may fail.

    An exception here is the compose ``provision`` gate failing, which is the
    whole stack failing to start — not a retryable blip.
    """
    results = await asyncio.gather(
        _provision_once(), _provision_once(), _provision_once(), return_exceptions=True
    )
    failures = [r for r in results if isinstance(r, BaseException)]
    assert not failures, f"{len(failures)}/3 concurrent provisioning runs failed: {failures!r}"


async def test_concurrent_provisioning_leaves_exactly_the_sequential_state(session) -> None:
    """Concurrency must not duplicate rows, and must not reset existing ones.

    The assertion is equality with the SEQUENTIAL outcome, not merely "no
    exception": a run that raced, rolled back and left the database half
    provisioned would still raise nothing in the winner.
    """
    await _provision_once()
    sequential = await _identity_counts(session)
    assert sequential["principals"] >= 2  # the admin + the agent principal

    await asyncio.gather(_provision_once(), _provision_once(), _provision_once())
    after_concurrent = await _identity_counts(session)
    assert after_concurrent == sequential

    # And a later sequential run still finds nothing to repair.
    await _provision_once()
    assert await _identity_counts(session) == sequential


async def test_repeat_provisioning_is_a_no_op(session) -> None:
    """The documented `make up` behaviour: the one-shot re-runs on every boot."""
    await _provision_once()
    first = await _identity_counts(session)
    await _provision_once()
    assert await _identity_counts(session) == first


async def test_the_agent_principal_is_not_the_agent_runtime(session) -> None:
    """`agent_alpha` (principal) and `alpha-agent` (runtime singleton) are two
    different identities provisioned by two different mechanisms.

    The principal is a seed concern; the ``agent_runtime`` singleton is inserted
    by migration ``0016_analysis_lab`` and has no FK to ``principals``. Seeding
    must therefore create the principal side and MUST NOT write a runtime row —
    a second provisioning path for the same singleton is how duplicates start.

    Honest boundary: this suite builds its schema with ``Base.metadata.create_all``
    (tests/integration/conftest.py), which does not replay migration inserts, so
    ``agent_runtime`` is empty here. That the REAL install path does create
    exactly one ``alpha-agent`` row is asserted against a migrated database by
    ``scripts/migration-acceptance.sh`` step [4].
    """
    assert DEFAULT_AGENT_ID != ALPHA_AGENT_ID  # "agent_alpha" vs "alpha-agent"

    await _provision_once()

    agent_principal = await session.get(Principal, DEFAULT_AGENT_ID)
    assert agent_principal is not None, "the seed owns the Agent PRINCIPAL"
    assert await session.get(Agent, DEFAULT_AGENT_ID) is not None

    runtime_rows = (
        await session.execute(select(func.count()).select_from(AgentRuntime))
    ).scalar_one()
    assert runtime_rows == 0, (
        "the seed must not provision agent_runtime — migration 0016_analysis_lab does"
    )
    assert await session.get(AgentRuntime, DEFAULT_AGENT_ID) is None


async def test_provisioning_never_resets_operator_edits(session) -> None:
    """Existing state is not reset: a re-provision leaves an edited row alone.

    The edited row is the system Agent, which BOTH auth modes provision. The
    credentialless `user_admin` HumanUser would have been the more obvious
    subject, but session mode deliberately does not create it (PROV-05), so a
    test keyed on it would silently `skip` itself the day CI pins
    `AUTH_MODE=session` — the profile `.env.example` actually ships.
    """
    await _provision_once()
    agent = await session.get(Agent, DEFAULT_AGENT_ID)
    assert agent is not None
    agent.name = "Renamed By Operator"
    agent.enabled = False
    await session.commit()

    await _provision_once()
    session.expire_all()
    again = await session.get(Agent, DEFAULT_AGENT_ID)
    assert again is not None
    assert again.name == "Renamed By Operator"
    assert again.enabled is False


async def test_concurrency_does_not_duplicate_an_unguarded_seed_block(session, monkeypatch) -> None:
    """The silent-duplicate class, not just the loud-crash one.

    `principals`, `agents` and `human_users` are PK/unique-protected, so a lost
    race there fails LOUDLY. The dangerous blocks are the ones with no unique
    constraint behind their existence guard: `rationale_family_revision`
    .normalized_name is `index=True` only, so two runs can both pass "does this
    family already exist?" and both COMMIT — leaving two ACTIVE families per
    canonical name, and no error anywhere.

    The SEED_* flags are module-level constants read at import time, so a
    default test run never reaches this branch; it is enabled explicitly here.
    """
    # Prime the identities with the flag still OFF, so the concurrent wave races
    # on the rationale families themselves rather than on `principals_pkey` —
    # and so the families do not already exist when the wave starts. (Priming
    # with the flag on makes this test vacuous: it then passes even with
    # `lock_provisioning` removed, because there is nothing left to create.)
    await _provision_once()
    assert (
        await session.execute(select(func.count()).select_from(RationaleFamilyRoot))
    ).scalar_one() == 0

    monkeypatch.setattr(seed_mod, "SEED_RATIONALE", True)
    expected = len(seed_mod._RATIONALE_FAMILIES)

    await asyncio.gather(_provision_once(), _provision_once(), _provision_once())

    roots = (
        await session.execute(select(func.count()).select_from(RationaleFamilyRoot))
    ).scalar_one()
    revisions = (
        await session.execute(select(func.count()).select_from(RationaleFamilyRevision))
    ).scalar_one()
    assert roots == expected, f"concurrency duplicated rationale families: {roots} != {expected}"
    assert revisions == expected
