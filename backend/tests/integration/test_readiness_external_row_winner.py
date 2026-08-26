"""G15 / Karar 4 = Seçenek B — which external-import row Ready Check leg 3 reads.

``work_object_revision_id`` is **not** UNIQUE on either leg-3 table (measured on the
live ``0043`` schema: ``indisunique = f``, and no ``contype IN ('u','p')`` beyond the
PKs). Before the signature both readers were an ``ORDER BY``-less ``.first()``, which
made the answer **non-deterministic in production**: the closure brief measured the same
input returning two different rows across three calls, and the two rows produced
OPPOSITE Ready Check evidence (2 accepted records vs 0).

Karar 4 signed **Seçenek B**: the winner is the NEWEST row, under a **total** order —
``created_at DESC, <pk> DESC``. This module pins three claims that a single assertion
cannot cover, because each fails to a different defect:

1. **the winner** — the newest row wins, not merely "some row";
2. **the order is TOTAL** — a ``created_at`` tie is broken by the pk, so the winner is
   still single-valued. ``created_at`` alone is NOT total, and this is not a hypothetical:
   ``server_default=func.now()`` is the *transaction* timestamp, so two batches written in
   one transaction tie EXACTLY. Drop the pk tie-break and the old non-determinism returns;
3. **the two read forms AGREE** — ``DISTINCT ON`` returns exactly the row the per-item
   ``LIMIT 1`` returns. This is the claim that makes batching leg 3 safe, and it is the
   only reason ``query_budgets.json`` could lower ``per_item`` from 1 to 0.

Claims 1 and 3 are asserted for BOTH kinds. Asserting only the Trade Log half would leave
the Trading Signal reader's order entirely unpinned — they are separate tables, separate
statements, and a defect in one is invisible to the other.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from entropia.domain.trade_log.enums import RecordBatchStatus
from entropia.domain.trading_signal.enums import NormalizedRevisionStatus
from entropia.infrastructure.postgres.models import (
    CanonicalTradeRecordBatch,
    NormalizedSignalEventRevision,
    SourceAsset,
)
from entropia.infrastructure.postgres.repositories import readiness as readiness_repo
from entropia.shared.ids import new_id

pytestmark = pytest.mark.asyncio

_PIN = "wobjrev_g15_shared_pin"
_OLDER = datetime(2026, 1, 1, tzinfo=UTC)
_NEWER = datetime(2026, 6, 1, tzinfo=UTC)


async def _source_asset(session) -> str:
    asset_id = new_id("srcasset")
    session.add(
        SourceAsset(
            source_asset_id=asset_id,
            object_key=f"s3://bucket/{asset_id}",
            raw_asset_hash="0" * 64,
            size_bytes=1,
        )
    )
    await session.flush()
    return asset_id


async def _batch(
    session, asset_id: str, *, batch_id: str, created_at: datetime, accepted: int, ok: bool
) -> str:
    session.add(
        CanonicalTradeRecordBatch(
            record_batch_id=batch_id,
            source_asset_id=asset_id,
            status=RecordBatchStatus.SUCCEEDED if ok else RecordBatchStatus.FAILED,
            accepted_count=accepted,
            skipped_count=0,
            records=[],
            skipped_rows=[],
            content_hash=batch_id[-8:].rjust(64, "0"),
            work_object_revision_id=_PIN,
            created_at=created_at,
        )
    )
    await session.flush()
    return batch_id


async def _signal(
    session, asset_id: str, *, revision_id: str, created_at: datetime, accepted: int, ok: bool
) -> str:
    session.add(
        NormalizedSignalEventRevision(
            normalized_revision_id=revision_id,
            source_asset_id=asset_id,
            status=(NormalizedRevisionStatus.SUCCEEDED if ok else NormalizedRevisionStatus.FAILED),
            accepted_count=accepted,
            skipped_count=0,
            events=[],
            skipped_rows=[],
            content_hash=revision_id[-8:].rjust(64, "0"),
            work_object_revision_id=_PIN,
            created_at=created_at,
        )
    )
    await session.flush()
    return revision_id


# --------------------------------------------------------------- Trade Log half


async def test_trade_log_newest_batch_wins_and_survives_planner_variation(session) -> None:
    """The newest batch wins, in BOTH read forms, under EVERY plan.

    The two seeded rows carry OPPOSITE evidence on purpose — SUCCEEDED/2 vs FAILED/0 —
    so a wrong winner is not a cosmetic difference: it flips the Ready Check verdict for
    that item. This is the exact pair the closure brief measured flipping.

    The ``enable_seqscan`` sweep is the brief's own method (§Ölçüm 1), and it is the
    **vacuity proof** for this test: under the old order-less read the winner changed
    with the plan. If the order is ever dropped, this loop is what notices — a single
    default-plan call could return the right row by luck.
    """
    asset_id = await _source_asset(session)
    # Seeded OLDEST-first so insertion order and the correct answer disagree; a reader
    # that simply takes the physically-first row fails here instead of passing by luck.
    older = await _batch(
        session, asset_id, batch_id="btch_older", created_at=_OLDER, accepted=2, ok=True
    )
    newer = await _batch(
        session, asset_id, batch_id="btch_newer", created_at=_NEWER, accepted=0, ok=False
    )
    await session.commit()
    session.expire_all()

    # Vacuity guard: both rows really are there and really do share the pin. Without
    # this, every assertion below would also pass on a single-row table — and on one row
    # `.first()` is deterministic even with no ORDER BY, so the test would prove nothing.
    shared = (
        await session.execute(
            text(
                "SELECT count(*) FROM canonical_trade_record_batch "
                "WHERE work_object_revision_id = :pin"
            ),
            {"pin": _PIN},
        )
    ).scalar_one()
    assert shared == 2, "fixture must actually contain the duplication under test"

    for seqscan in ("off", "on"):
        await session.execute(text(f"SET enable_seqscan = {seqscan}"))
        session.expire_all()

        per_item = await readiness_repo.resolve_trade_log_batch(session, _PIN)
        assert per_item is not None
        assert per_item.record_batch_id == newer, (
            f"per-item reader picked {per_item.record_batch_id} under seqscan={seqscan}; "
            f"Seçenek B says the newest ({newer}) wins"
        )
        # The evidence, not just the id: a wrong winner reverses the item's verdict.
        assert (per_item.accepted_count, str(per_item.status)) == (0, "failed")

        batched = await readiness_repo.resolve_trade_log_batches(session, [_PIN])
        assert batched[_PIN].record_batch_id == newer, (
            f"batch reader picked {batched[_PIN].record_batch_id} under seqscan={seqscan}"
        )
        # The load-bearing claim: DISTINCT ON == the per-item LIMIT 1. Asserted as an
        # identity between the two forms, not against a literal, so a future change to
        # the winner rule can only pass here if it is applied to BOTH readers.
        assert batched[_PIN].record_batch_id == per_item.record_batch_id

    await session.execute(text("SET enable_seqscan = on"))
    assert older != newer


async def test_trade_log_created_at_tie_is_broken_by_pk_in_both_forms(session) -> None:
    """A ``created_at`` tie still has ONE winner: the higher pk.

    Not a corner case. ``created_at`` defaults to ``func.now()``, which is the
    TRANSACTION timestamp — two batches written in one transaction carry byte-identical
    timestamps. If the order were ``created_at DESC`` alone it would not be total, and on
    a tie Postgres would be free to return either row: precisely the non-determinism
    Seçenek B was signed to remove.
    """
    asset_id = await _source_asset(session)
    same = datetime(2026, 3, 3, tzinfo=UTC)
    await _batch(session, asset_id, batch_id="btch_aaa", created_at=same, accepted=1, ok=True)
    await _batch(session, asset_id, batch_id="btch_zzz", created_at=same, accepted=9, ok=True)
    await session.commit()
    session.expire_all()

    for seqscan in ("off", "on"):
        await session.execute(text(f"SET enable_seqscan = {seqscan}"))
        session.expire_all()
        per_item = await readiness_repo.resolve_trade_log_batch(session, _PIN)
        batched = await readiness_repo.resolve_trade_log_batches(session, [_PIN])
        assert per_item is not None
        assert per_item.record_batch_id == "btch_zzz", (
            f"tie broken to {per_item.record_batch_id} under seqscan={seqscan}; "
            "the pk DESC tie-break is what makes the order total"
        )
        assert batched[_PIN].record_batch_id == "btch_zzz"
        assert batched[_PIN].record_batch_id == per_item.record_batch_id
    await session.execute(text("SET enable_seqscan = on"))


# ---------------------------------------------------------- Trading Signal half


async def test_signal_newest_revision_wins_and_survives_planner_variation(session) -> None:
    """The Trading Signal half of the same rule — a separate table and statement.

    Kept as its own test rather than parametrised with the Trade Log case: the two
    readers share a rule but not a line of SQL, so a defect in one is invisible to the
    other. Dropping this test would leave ``resolve_signal_revision``'s order unpinned.
    """
    asset_id = await _source_asset(session)
    await _signal(
        session, asset_id, revision_id="nsrev_older", created_at=_OLDER, accepted=5, ok=True
    )
    await _signal(
        session, asset_id, revision_id="nsrev_newer", created_at=_NEWER, accepted=0, ok=False
    )
    await session.commit()
    session.expire_all()

    shared = (
        await session.execute(
            text(
                "SELECT count(*) FROM normalized_signal_event_revision "
                "WHERE work_object_revision_id = :pin"
            ),
            {"pin": _PIN},
        )
    ).scalar_one()
    assert shared == 2, "fixture must actually contain the duplication under test"

    for seqscan in ("off", "on"):
        await session.execute(text(f"SET enable_seqscan = {seqscan}"))
        session.expire_all()
        per_item = await readiness_repo.resolve_signal_revision(session, _PIN)
        assert per_item is not None
        assert per_item.normalized_revision_id == "nsrev_newer", (
            f"per-item reader picked {per_item.normalized_revision_id} under seqscan={seqscan}"
        )
        assert (per_item.accepted_count, str(per_item.status)) == (0, "failed")
        batched = await readiness_repo.resolve_signal_revisions(session, [_PIN])
        assert batched[_PIN].normalized_revision_id == "nsrev_newer"
        assert batched[_PIN].normalized_revision_id == per_item.normalized_revision_id
    await session.execute(text("SET enable_seqscan = on"))


async def test_signal_created_at_tie_is_broken_by_pk_in_both_forms(session) -> None:
    """The Trading Signal half of the totality claim."""
    asset_id = await _source_asset(session)
    same = datetime(2026, 4, 4, tzinfo=UTC)
    await _signal(session, asset_id, revision_id="nsrev_aaa", created_at=same, accepted=1, ok=True)
    await _signal(session, asset_id, revision_id="nsrev_zzz", created_at=same, accepted=9, ok=True)
    await session.commit()
    session.expire_all()

    per_item = await readiness_repo.resolve_signal_revision(session, _PIN)
    batched = await readiness_repo.resolve_signal_revisions(session, [_PIN])
    assert per_item is not None
    assert per_item.normalized_revision_id == "nsrev_zzz"
    assert batched[_PIN].normalized_revision_id == per_item.normalized_revision_id


# ------------------------------------------------------------ absence semantics


async def test_absent_pin_is_absent_from_the_batch_maps(session) -> None:
    """A pin with no row is ABSENT from the map — the same ``None`` the per-item read gave.

    This is what keeps ``_resolve_external``'s ``found=False`` branch reachable on exactly
    the inputs it was reachable on before batching. If the batch readers ever returned a
    placeholder instead of omitting the key, an unresolvable pin would silently become a
    resolved one and the fail-closed branch would go dead.

    The empty-input short-circuit is asserted beside it: it must return ``{}`` rather than
    fall through to a query with an empty ``IN ()``.
    """
    asset_id = await _source_asset(session)
    await _batch(session, asset_id, batch_id="btch_only", created_at=_NEWER, accepted=1, ok=True)
    await session.commit()
    session.expire_all()

    batched = await readiness_repo.resolve_trade_log_batches(session, [_PIN, "wobjrev_missing"])
    assert set(batched) == {_PIN}
    assert await readiness_repo.resolve_trade_log_batch(session, "wobjrev_missing") is None

    signals = await readiness_repo.resolve_signal_revisions(session, ["wobjrev_missing"])
    assert signals == {}
    assert await readiness_repo.resolve_signal_revision(session, "wobjrev_missing") is None

    assert await readiness_repo.resolve_trade_log_batches(session, []) == {}
    assert await readiness_repo.resolve_signal_revisions(session, []) == {}
