"""Per-command idempotency helper (decision D3, Module 20 §6.2).

Wraps the ``idempotency_keys`` table + ``repositories/idempotency`` so a command
runs at most once for a given key:

* No key supplied -> the command always runs (caller chose no idempotency).
* Key present + same request fingerprint -> return the stored ``response_ref``
  (the command body is NOT re-run; no second revision/run/job is created).
* Key present + a *different* fingerprint -> ``IdempotencyConflictError`` (409).
* Key absent -> record an ``in_progress`` row, run the command, then complete it
  with the response reference, all inside the caller's transaction (no commit).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.infrastructure.postgres.repositories import idempotency as idem_repo
from entropia.shared.errors import IdempotencyConflictError
from entropia.shared.idempotency import request_fingerprint


async def run_idempotent(
    session: AsyncSession,
    *,
    key: str | None,
    actor_principal_id: str | None,
    request_payload: object,
    operation: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    """Execute ``operation`` at most once per ``key`` for the same payload.

    Returns the operation's JSON-safe ``response_ref`` (stored verbatim for
    replays). ``operation`` itself must add rows to ``session`` and not commit.
    """
    if key is None:
        return await operation()

    fingerprint = request_fingerprint(request_payload)
    existing = await idem_repo.get_key(session, key)
    if existing is not None:
        # Idempotency keys are isolated per principal: never hand a caller another
        # actor's stored result (the key namespace is otherwise client-controlled).
        if existing.actor_principal_id is not None and (
            existing.actor_principal_id != actor_principal_id
        ):
            raise IdempotencyConflictError()
        if existing.request_hash != fingerprint:
            raise IdempotencyConflictError()
        if existing.status == "completed" and existing.response_ref is not None:
            return existing.response_ref
        # An in-progress row with a matching fingerprint: a prior attempt did not
        # complete. Re-running within this transaction is safe; fall through.

    row = existing or idem_repo.add_key(
        session,
        key=key,
        actor_principal_id=actor_principal_id,
        request_hash=fingerprint,
    )
    result = await operation()
    idem_repo.complete_key(row, response_ref=result)
    return result
