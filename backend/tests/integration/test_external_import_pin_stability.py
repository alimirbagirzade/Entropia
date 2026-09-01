"""The import pin is SET-ONCE: reusing a batch keeps the first pin (GH #854).

Auto-skips without PostgreSQL (see tests/integration/conftest.py).

PINS THE SIGNED FIX. Karar 1 = (b) SET-ONCE was signed 2026-09-01
(``docs/decisions/closure_i854_external_import_pin_stability_2026-08-28.md``), and
``link_batch_to_revision`` / ``link_normalized_to_revision`` now write only while
``work_object_revision_id`` is None. This file previously CHARACTERIZED the defect
(the pin moved to N+1 and BLOCKED the untouched item); its own docstring demanded
that a fix rewrite it deliberately rather than let a silent green carry the old
behaviour forward — this rewrite is that act (ADIM 155).

What doc 05 requires. K3 (Pinned Revision) fixes the rule: *"Yeni revision
olustugunda otomatik gecmez; acik pin gerekir."* The pin is the USER's decision and
never a side effect of a write path. Under set-once that now holds for the batch
column too: saving a new revision that names the SAME canonical batch leaves the
batch pinned to the FIRST revision, the Mainboard item (also pinned to the first
revision, per K3) still resolves, and a READY composition STAYS ready when the user
only edits a display name.

The signed cost is pinned here too, not hidden: the column is single-valued, so the
NEW revision has no backing row. A user who explicitly repins the item to N+1 (K3's
own act) moves the breakage there — ``§Ölçüm 6``'s "the breakage moves, it does not
vanish". The assertion that no row backs N+1 is that cost, stated as a fact.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select

from entropia.application.commands import readiness_check as readiness_cmd
from entropia.application.commands import trade_log as tl_cmd
from entropia.application.commands import trading_signal as ts_cmd
from entropia.domain.identity import Actor
from entropia.domain.trading_signal.enums import NormalizedRevisionStatus
from entropia.infrastructure.postgres.models import (
    CanonicalTradeRecordBatch,
    NormalizedSignalEventRevision,
)
from entropia.infrastructure.postgres.repositories import trading_signal as ts_repo
from entropia.infrastructure.s3 import datasets
from entropia.shared.ids import new_id
from tests.integration.test_backtest_manifest_pinning import _signal_payload
from tests.integration.test_backtest_persistence import USER1, _ready_composition, _seed_principals
from tests.integration.test_external_object_run_provenance import (
    _attach_trade_log,
    _trade_log_payload,
)

pytestmark = pytest.mark.integration

_UNRESOLVED = "EXTERNAL_IMPORT_UNRESOLVED"


@pytest.fixture
def fake_object_store(monkeypatch) -> dict[str, bytes]:
    """In-process object storage so upload + the import worker run without MinIO.

    Declared locally rather than imported: ten integration modules each carry their
    own copy of this fixture and there is no shared one, so this follows the suite's
    existing shape instead of introducing a cross-module fixture import.
    """
    store: dict[str, bytes] = {}

    def _put(source_asset_id: str, data: bytes, *, content_type: str | None = None):
        digest = hashlib.sha256(data).hexdigest()
        key = f"signals/source/{source_asset_id}/{digest}"
        store[key] = data
        return key, digest

    monkeypatch.setattr(datasets, "put_source_asset_bytes", _put)
    monkeypatch.setattr(datasets, "get_raw_bytes", lambda object_key: store[object_key])
    return store


def _codes(result: dict[str, Any]) -> set[str]:
    return {issue["code"] for issue in result["issues"]}


async def test_reusing_the_same_batch_keeps_the_pin_and_the_item_stays_ready(
    session, fake_object_store
) -> None:
    """GH #854 FIXED: editing a display name no longer re-points the batch.

    The composition is proved READY first. Without that guard the closing
    "still no blocker" assertion would be vacuous — a composition that never
    resolved would satisfy it just as well.
    """
    await _seed_principals(session)
    workspace_id = (await _ready_composition(session, USER1))[0]
    first = await _attach_trade_log(session, USER1, workspace_id)
    batch_id = first["record_batch_revision_id"]

    # VACUITY GUARD -- the item resolves and the composition carries no import blocker.
    before = await readiness_cmd.run_readiness_check(session, USER1, composition_id=workspace_id)
    assert _UNRESOLVED not in _codes(before)

    batch = await session.get(CanonicalTradeRecordBatch, batch_id)
    assert batch is not None
    assert batch.work_object_revision_id == first["revision_id"]
    accepted_before = batch.accepted_count
    status_before = batch.status

    # The ONLY change is a display name. The import binding is byte-identical: same
    # source asset, same canonical batch. Nothing is re-imported.
    revised = await tl_cmd.create_trade_log_revision(
        session,
        USER1,
        root_id=first["root_id"],
        payload=_trade_log_payload(
            first["source_asset_id"],
            batch_id,
            identity={"display_name": "Binance BTCUSDT trade history v2"},
        ),
    )
    await session.commit()
    assert revised["revision_id"] != first["revision_id"]

    # Re-READ from the database rather than trusting the identity map.
    session.expire_all()
    batch = await session.get(CanonicalTradeRecordBatch, batch_id)
    assert batch is not None

    # The import itself is intact.
    assert batch.status == status_before
    assert batch.accepted_count == accepted_before

    # SET-ONCE: the pin STAYS on revision N. This is the line NC-1 turns red.
    assert batch.work_object_revision_id == first["revision_id"]
    assert batch.work_object_revision_id != revised["revision_id"]

    # The signed cost, stated as a fact: the NEW revision has no backing row, so an
    # explicit user repin to N+1 would move the breakage there (Karar 1(b)'s price).
    stranded = (
        await session.execute(
            select(CanonicalTradeRecordBatch).where(
                CanonicalTradeRecordBatch.work_object_revision_id == revised["revision_id"]
            )
        )
    ).scalar_one_or_none()
    assert stranded is None

    # And the user-visible consequence of the fix: the item (pinned to N, K3) still
    # resolves — the READY composition STAYS ready after a display-name edit.
    after = await readiness_cmd.run_readiness_check(session, USER1, composition_id=workspace_id)
    assert _UNRESOLVED not in _codes(after)
    assert after["state"] == before["state"]


async def _seed_signal_import(session, actor: Actor) -> dict[str, str]:
    """An accepted normalized Signal revision, written through the import worker's own
    repositories. ``earliest_available_time`` is a PAST instant on purpose: the real
    save command derives the work object's ``available_time`` from this row, and doc 01
    anti-lookahead would otherwise hold the composition out of Ready.
    """
    asset = await ts_repo.create_source_asset(
        session,
        source_asset_id=new_id("srcast"),
        owner_principal_id=actor.principal_id,
        draft_id=None,
        object_key="signal/raw/i854/seed.csv",
        raw_asset_hash="9" * 64,
        size_bytes=128,
        content_type="text/csv",
        original_filename="signals.csv",
        uploaded_by_principal_id=actor.principal_id,
    )
    await session.flush()
    normalized = await ts_repo.create_normalized_revision(
        session,
        source_asset_id=asset.source_asset_id,
        job_id=None,
        status=NormalizedRevisionStatus.SUCCEEDED,
        instrument_id="BTCUSDT",
        accepted_count=2,
        skipped_count=0,
        events=[],
        skipped_rows=[],
        validation_summary={"source_timezone": "Europe/Istanbul", "mapping_hash": "7" * 64},
        earliest_available_time=datetime(2020, 1, 1, tzinfo=UTC),
        content_hash="8" * 64,
        created_by_principal_id=actor.principal_id,
    )
    await session.flush()
    return {
        "source_asset_id": asset.source_asset_id,
        "normalized_revision_id": normalized.normalized_revision_id,
    }


async def test_the_trading_signal_twin_keeps_its_pin_the_same_way(session) -> None:
    """The sibling surface named in GH #854, driven through the REAL save commands.

    ``repositories/trading_signal.py::link_normalized_to_revision`` is the exact twin
    of the Trade Log writer — both went set-once in the same change because the
    defect was one class, not two bugs. Pinning only the Trade Log half would let a
    regression repair one surface and silently leave the other; NC-2 proves the two
    cases discriminate (reverting only this writer reddens only this test).

    Note this case does NOT reuse ``_attach_trading_signal``: that helper hand-writes
    the pin with ``ts_repo.link_normalized_to_revision`` after ``create_work_object``,
    so it would prove the test harness rather than the shipped command. The real
    ``create_trading_signal_and_attach`` -> ``create_trading_signal_revision`` pair is
    driven instead.
    """
    await _seed_principals(session)
    workspace_id = (await _ready_composition(session, USER1))[0]
    seeded = await _seed_signal_import(session, USER1)
    normalized_id = seeded["normalized_revision_id"]

    first = await ts_cmd.create_trading_signal_and_attach(
        session,
        USER1,
        payload=_signal_payload(seeded["source_asset_id"], normalized_id),
        workspace_id=workspace_id,
    )
    await session.commit()
    assert first["attached"] is True

    # VACUITY GUARD -- the signal resolves before the second save.
    before = await readiness_cmd.run_readiness_check(session, USER1, composition_id=workspace_id)
    assert _UNRESOLVED not in _codes(before)

    row = await session.get(NormalizedSignalEventRevision, normalized_id)
    assert row is not None
    assert row.work_object_revision_id == first["revision_id"]

    revised = await ts_cmd.create_trading_signal_revision(
        session,
        USER1,
        root_id=first["root_id"],
        payload=_signal_payload(
            seeded["source_asset_id"],
            normalized_id,
        )
        | {"identity": {"display_name": "K-04 signal source v2"}},
    )
    await session.commit()
    assert revised["revision_id"] != first["revision_id"]

    session.expire_all()
    row = await session.get(NormalizedSignalEventRevision, normalized_id)
    assert row is not None

    # SET-ONCE, identical shape to the Trade Log half. NC-2's red line.
    assert row.work_object_revision_id == first["revision_id"]
    assert row.work_object_revision_id != revised["revision_id"]

    # The signed cost on this surface too: nothing backs the new revision.
    stranded = (
        await session.execute(
            select(NormalizedSignalEventRevision).where(
                NormalizedSignalEventRevision.work_object_revision_id == revised["revision_id"]
            )
        )
    ).scalar_one_or_none()
    assert stranded is None

    after = await readiness_cmd.run_readiness_check(session, USER1, composition_id=workspace_id)
    assert _UNRESOLVED not in _codes(after)
    assert after["state"] == before["state"]
