"""Admit a Backtest run for one composition, without going through HTTP.

Why this exists
---------------
The engine, the durable queue, the worker and multi-strategy independent runs are all
shipped; what was missing was a way to say "run this" from anywhere other than the
browser. This module is that entry point and deliberately nothing more: the thin caller
the bulk-execution plan (§4, slice B1) describes, not a second engine and not a second
admission path.

The one boundary it does NOT cross
----------------------------------
Skipping **HTTP** is supported — ``commands.backtest_run.request_backtest_run`` is a
plain async command and the route is one caller of it, never its owner. Skipping
**Ready Check** is not, and this module cannot: admission refuses on
``blocker_count > 0`` (422 ``READINESS_BLOCKED``) and the caller rolls back, so no run,
no manifest and no job survive a blocked composition.

That refusal is the only thing between an unresolved indicator and a Result row that
silently computed nothing — and a wrong Result is indistinguishable from a good one
once written. The rule for every future caller is therefore the same as for this one:
go through ``request_backtest_run``. Reaching past it into ``run_backtest`` or
``run_engine`` would buy nothing and forfeit that guarantee.

Who the actor is
----------------
Resolved from the database by ``application.identity.resolve_actor``, never asserted by
the caller. A ``--principal-id`` that is unknown, disabled or soft-deleted resolves to
ANONYMOUS and admission then raises on ``require_authenticated`` — a CLI flag cannot
mint an Admin. This mirrors DOMAIN_MODEL §4: client-supplied role is never
authoritative.

Shape
-----
:func:`admit_run` follows the repo's command pattern — module-level async, one
transaction, **no commit** — so it composes with any caller's session (a fan-out in
slice B2, a test fixture, a future scheduler). :func:`admit_and_dispatch` owns the
session, commits, and only THEN enqueues, exactly as
``apps/api/routes/backtest.py::_dispatch`` does. Dispatching inside the transaction
would let the worker observe a ``jobs`` row that a later rollback erases.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.identity import resolve_actor
from entropia.infrastructure.observability import configure_logging, get_logger
from entropia.infrastructure.postgres.engine import get_session_factory
from entropia.infrastructure.queues.enqueue import send_job

log = get_logger("runner.admit")

#: Opens a session. Defaulted from the app factory; a caller may inject its own so the
#: dispatch-after-commit ordering can be driven without a live broker.
SessionFactory = Callable[[], Any]


async def admit_run(
    session: AsyncSession,
    *,
    principal_id: str,
    composition_id: str,
    idempotency_key: str | None = None,
    expected_fingerprint: str | None = None,
    ready_report_id: str | None = None,
) -> dict[str, Any]:
    """Admit one run in the caller's transaction. Does not commit and does not enqueue.

    Raises whatever admission raises — a readiness blocker is a
    ``ReadinessBlockedError``, never a silent skip. A fan-out (slice B2) is expected to
    CATCH it and report it as data; it must not suppress it, because "this composition
    was refused, and why" is the most useful thing a bulk run can tell its operator.
    """
    actor = await resolve_actor(session, principal_id=principal_id)
    return await backtest_cmd.request_backtest_run(
        session,
        actor,
        composition_id=composition_id,
        expected_fingerprint=expected_fingerprint,
        ready_report_id=ready_report_id,
        idempotency_key=idempotency_key,
    )


async def admit_and_dispatch(
    *,
    principal_id: str,
    composition_id: str,
    idempotency_key: str | None = None,
    expected_fingerprint: str | None = None,
    ready_report_id: str | None = None,
    dispatch: bool = True,
    session_factory: SessionFactory | None = None,
) -> dict[str, Any]:
    """Own a session, admit, commit, and only then enqueue the worker job."""
    factory = session_factory or get_session_factory()
    async with factory() as session:
        try:
            result = await admit_run(
                session,
                principal_id=principal_id,
                composition_id=composition_id,
                idempotency_key=idempotency_key,
                expected_fingerprint=expected_fingerprint,
                ready_report_id=ready_report_id,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    # After the commit, never before (see the module docstring).
    job_id = result.get("job_id")
    if dispatch and job_id:
        from entropia.apps.worker.actors import run_backtest_engine

        send_job(run_backtest_engine, str(job_id))
        log.info("runner.admit.dispatched", job_id=str(job_id))
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="entropia-admit-run",
        description="Admit a Backtest run for one composition without HTTP.",
    )
    parser.add_argument("--principal-id", required=True)
    parser.add_argument("--composition-id", required=True)
    # Optional, but a fan-out without it has no replay protection: a retried batch
    # admits duplicate runs. B2 supplies one per composition.
    parser.add_argument("--idempotency-key", default=None)
    parser.add_argument("--expected-fingerprint", default=None)
    parser.add_argument("--ready-report-id", default=None)
    parser.add_argument(
        "--no-dispatch",
        action="store_true",
        help="Admit only; do not enqueue the worker job (the run stays QUEUED).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = _parse_args(argv)
    result = asyncio.run(
        admit_and_dispatch(
            principal_id=args.principal_id,
            composition_id=args.composition_id,
            idempotency_key=args.idempotency_key,
            expected_fingerprint=args.expected_fingerprint,
            ready_report_id=args.ready_report_id,
            dispatch=not args.no_dispatch,
        )
    )
    log.info(
        "runner.admit.done",
        run_id=str(result.get("run_id")),
        job_id=str(result.get("job_id")),
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())


__all__ = ["admit_and_dispatch", "admit_run", "main"]
