"""Direct, non-HTTP admission (bulk-execution plan §4, slice B1).

These cases pin the three properties that make the runner safe to point at thousands of
compositions: it cannot mint an actor, it inherits Ready Check's refusal, and it never
lets a worker see a job the transaction has not committed.
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.apps.runner.admit import admit_and_dispatch, admit_run
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import BacktestRun, HumanUser, Job, Principal
from entropia.shared.errors import ReadinessBlockedError, UnauthenticatedError
from tests.integration.test_backtest_persistence import (
    USER1,
    _count,
    _empty_composition,
    _ready_composition,
    _seed_principals,
)


async def _seed_resolvable_user(session) -> None:
    """A HumanUser row for ``user_1``, not merely a Principal.

    The rest of this suite hand-constructs its Actor, so it never exercises principal
    resolution and a bare Principal is enough for it. The runner does the opposite: it
    RESOLVES the actor from the database, so without this row ``user_1`` comes back
    ANONYMOUS. That is the fail-closed behaviour working, not a fixture nicety — it is
    why the unknown-principal case below has to name a genuinely different id to prove
    anything.
    """
    await _seed_principals(session)
    if await session.get(Principal, "user_1") is None:  # pragma: no cover - defensive
        session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
    if await session.get(HumanUser, "user_1") is None:
        session.add(
            HumanUser(
                user_id="user_1",
                username="runner_user",
                email="runner@example.com",
                display_name="Runner User",
                current_role=Role.USER,
                status="active",
            )
        )
    await session.flush()


pytestmark = pytest.mark.integration


async def test_a_ready_composition_is_admitted_without_any_http(session) -> None:
    await _seed_resolvable_user(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)

    result = await admit_run(
        session,
        principal_id="user_1",
        composition_id=composition_id,
        idempotency_key="b1-admit-1",
    )

    assert result.get("run_id")
    assert result.get("job_id")
    # The durable rows are what the worker will pick up; the dict alone would pass even
    # if admission had written nothing.
    assert await _count(session, BacktestRun) == 1
    assert await _count(session, Job) == 1


async def test_a_principal_the_database_does_not_know_cannot_admit(session) -> None:
    # The security property: role comes from the database, never from the caller. A CLI
    # flag naming an unknown principal resolves to ANONYMOUS, and admission refuses.
    await _seed_resolvable_user(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)

    with pytest.raises(UnauthenticatedError):
        await admit_run(
            session,
            principal_id="user_does_not_exist",
            composition_id=composition_id,
        )
    await session.rollback()
    assert await _count(session, BacktestRun) == 0
    assert await _count(session, Job) == 0


async def test_the_runner_inherits_ready_checks_refusal(session) -> None:
    # Not a new gate — the SAME one the route gets. An empty composition is blocked and
    # leaves nothing behind, so a bulk caller cannot produce a Result nobody can trust.
    await _seed_resolvable_user(session)
    composition_id = await _empty_composition(session, USER1)

    with pytest.raises(ReadinessBlockedError):
        await admit_run(session, principal_id="user_1", composition_id=composition_id)
    await session.rollback()
    assert await _count(session, BacktestRun) == 0
    assert await _count(session, Job) == 0


async def test_the_job_is_enqueued_only_after_the_transaction_commits(session) -> None:
    """Ordering, not merely "it enqueued".

    A dispatch inside the transaction would let the worker open the job before the
    commit — and a rollback would then erase a row the worker is already running. The
    observation is therefore WHEN send_job fired relative to the commit, which is why
    the fake records the commit rather than asserting a call count.
    """
    await _seed_resolvable_user(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    await session.commit()

    events: list[str] = []

    class _RecordingSession:
        """Delegates to the real session, but records the commit in order."""

        def __init__(self, inner: Any) -> None:
            self._inner = inner

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *_exc: Any) -> None:
            return None

        async def commit(self) -> None:
            events.append("commit")
            await self._inner.commit()

        def __getattr__(self, name: str) -> Any:
            return getattr(self._inner, name)

    sent: list[str] = []

    def _fake_send(_actor: Any, job_id: str) -> None:
        events.append("send_job")
        sent.append(job_id)

    import entropia.apps.runner.admit as admit_mod

    original = admit_mod.send_job
    admit_mod.send_job = _fake_send  # type: ignore[assignment]
    try:
        result = await admit_and_dispatch(
            principal_id="user_1",
            composition_id=composition_id,
            idempotency_key="b1-order-1",
            session_factory=lambda: _RecordingSession(session),
        )
    finally:
        admit_mod.send_job = original  # type: ignore[assignment]

    assert events == ["commit", "send_job"], events
    assert sent == [str(result["job_id"])]


async def test_no_dispatch_admits_the_run_and_enqueues_nothing(session) -> None:
    # The escape hatch must not silently enqueue: an operator staging thousands of runs
    # before starting workers depends on this being real absence, not a delayed send.
    await _seed_resolvable_user(session)
    composition_id, _root, _rev = await _ready_composition(session, USER1)
    await session.commit()

    sent: list[str] = []
    import entropia.apps.runner.admit as admit_mod

    original = admit_mod.send_job
    admit_mod.send_job = lambda _a, job_id: sent.append(job_id)  # type: ignore[assignment]
    try:
        result = await admit_and_dispatch(
            principal_id="user_1",
            composition_id=composition_id,
            idempotency_key="b1-nodispatch-1",
            dispatch=False,
            session_factory=lambda: _Passthrough(session),
        )
    finally:
        admit_mod.send_job = original  # type: ignore[assignment]

    assert result.get("job_id")
    assert sent == []


class _Passthrough:
    def __init__(self, inner: Any) -> None:
        self._inner = inner

    async def __aenter__(self) -> Any:
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
