"""The import pin is NOT stable when a revision reuses its batch (GH #854).

Auto-skips without PostgreSQL (see tests/integration/conftest.py).

CHARACTERIZATION of a SHIPPED DEFECT. Every assertion below states what the build
does TODAY, not what it ought to do. Nothing here blesses the behaviour.

What doc 05 requires. K3 (Pinned Revision) fixes the rule: *"Yeni revision
olustugunda otomatik gecmez; acik pin gerekir."* The pin is the USER's decision and
never a side effect of a write path. G15 SS"Olcum 4" measured that this is violated.

The mechanism. ``repositories/trade_log.py::link_batch_to_revision`` is an
UNCONDITIONAL assignment, and ``commands/trade_log.py::_require_ready_import`` gates
only status / accepted_count / time zone -- it never asks whether the batch is
ALREADY pinned. So saving a new revision that names the SAME canonical batch
repoints that batch's ``work_object_revision_id`` at N+1 and leaves N with no
backing row at all. ``commands/readiness_check.py::_resolve_external`` resolves in
the REVERSE direction (pinned revision id -> the batch carrying it), so exactly one
revision can ever resolve: the column is single-valued.

Why the suite never caught it (measured, not argued). Every existing second-revision
case in ``test_external_object_run_provenance.py`` re-imports ``_SECOND_CSV`` -- a
DIFFERENT batch -- so same-batch reuse is exercised nowhere in the tree. The models
carry a ``# Set once at Save time`` comment on the very column that moves; a comment
is an intent, and nothing enforces it.

The consequence pinned here is the one that matters, and it is not a column value:
the Mainboard item is still pinned to N because K3 forbids auto-repin, so a
composition that was READY becomes BLOCKED with ``EXTERNAL_IMPORT_UNRESOLVED``
although no import changed and the user only edited a display name.

A FIX WILL TURN THIS TEST RED, and that is the point. The single-valued column
cannot let both revisions resolve, so every candidate repair is either incomplete
(set-once merely moves the breakage onto N+1) or a product decision (refusing the
save, a link table, or resolving forward from the payload -- the last of which would
moot the SIGNED G15/Karar 4). Whoever lands the fix must rewrite this test
deliberately rather than let a silent green carry the old behaviour forward.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import pytest

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


async def test_reusing_the_same_batch_moves_the_pin_and_blocks_the_untouched_item(
    session, fake_object_store
) -> None:
    """GH #854: editing a display name re-points the batch and BLOCKS revision N.

    The composition is proved READY first. Without that guard the closing assertion
    is vacuous: a blocker that was already present before the second save would
    satisfy it just as well.
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

    # The import itself is intact -- this is a pin defect, not a data defect.
    assert batch.status == status_before
    assert batch.accepted_count == accepted_before

    # SHIPPED DEFECT: the pin MOVED off revision N.
    assert batch.work_object_revision_id == revised["revision_id"]
    assert batch.work_object_revision_id != first["revision_id"]

    # And the user-visible consequence: the item was never repinned (K3), so the
    # composition that was READY above now carries a BLOCKER.
    after = await readiness_cmd.run_readiness_check(session, USER1, composition_id=workspace_id)
    assert _UNRESOLVED in _codes(after)
    assert after["state"] == "not_ready"


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


async def test_the_trading_signal_twin_moves_its_pin_the_same_way(session) -> None:
    """The sibling surface named in GH #854, driven through the REAL save commands.

    ``repositories/trading_signal.py::link_normalized_to_revision`` is the exact twin
    of the Trade Log writer -- an unconditional assignment reached from two call sites
    in ``commands/trading_signal.py`` -- so the defect is one class, not two bugs.
    Pinning only the Trade Log half would let a fix repair one surface and silently
    leave the other.

    Note this case does NOT reuse ``_attach_trading_signal``: that helper hand-writes
    the pin with ``ts_repo.link_normalized_to_revision`` after ``create_work_object``,
    so it would prove the test harness rather than the shipped command. The real
    ``create_trading_signal_and_attach`` -> ``create_trading_signal_revision`` pair is
    driven instead -- the same pair whose own docstring states K3 ("the Mainboard item
    is NEVER auto-repinned"), which is precisely why the stranded revision matters.
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

    # SHIPPED DEFECT, identical shape to the Trade Log half.
    assert row.work_object_revision_id == revised["revision_id"]
    assert row.work_object_revision_id != first["revision_id"]

    after = await readiness_cmd.run_readiness_check(session, USER1, composition_id=workspace_id)
    assert _UNRESOLVED in _codes(after)
    assert after["state"] == "not_ready"
