"""S-L2 — the two doc 15 §3.2 export types the enum was missing.

§3.2 lists five Data Export entries (Trade Log CSV, Signal Events CSV, Equity Curve
CSV, **PineScript Signal Marker**, Result JSON) plus a Research Data / Agent Data row
whose action is **Export Agent Dataset**. Only five types shipped, so
`pinescript_signal_marker` and `agent_dataset` returned EXPORT_TYPE_INVALID.

The agent dataset carries a condition the other six do not: "Agent dataset yalniz
approved/scope-authorized artifactsden olusturulur; UI local stateinden turetilmez."
Both halves are pinned here.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

import pytest

from entropia.application.commands import result_export as export_cmd
from entropia.infrastructure.postgres.models import ResultManifestSnapshot
from entropia.infrastructure.postgres.repositories import export as export_repo
from entropia.shared.errors import AgentDatasetSourceNotApprovedError
from tests.integration.test_arrange_metrics import (
    USER1,
    _seed_principals,
    _seed_registry,
    _seed_result,
    _workspace,
)

pytestmark = pytest.mark.integration


async def _result(session, result_id: str, *, ledger_rows: int = 3) -> str:
    await _seed_registry(session)
    await _seed_principals(session)
    ws = await _workspace(session, USER1)
    await _seed_result(
        session, workspace_id=ws, result_id=result_id, owner="user_1", ledger_rows=ledger_rows
    )
    return result_id


async def _pin_package(session, result_id: str, *, approval_state: str) -> None:
    """Rewrite the Result's manifest snapshot to pin one package revision."""
    snapshot = await session.get(ResultManifestSnapshot, f"snap_{result_id}")
    assert snapshot is not None
    snapshot.manifest = {
        **snapshot.manifest,
        "strategy_package_context": [
            {
                "item_id": "mbwi_1",
                "package_revisions": [
                    {
                        "role": "entry",
                        "package_revision_id": "pkgrev_1",
                        "revision": {
                            "package_kind": "indicator",
                            "approval_state": approval_state,
                        },
                    }
                ],
            }
        ],
    }
    await session.flush()


async def test_pinescript_signal_marker_is_accepted_and_derives_from_signal_events(
    session,
) -> None:
    """The marker is a RENDERING of the signal-event artifact, not a second source.

    Pointing it anywhere else would let a marker export disagree with the
    signal-events export of the same immutable Result.
    """
    result_id = await _result(session, "btres_pine")

    marker = await export_cmd.request_result_export(
        session,
        USER1,
        result_id=result_id,
        export_type="pinescript_signal_marker",
        export_format="json",
    )
    signals = await export_cmd.request_result_export(
        session,
        USER1,
        result_id=result_id,
        export_type="signal_events",
        export_format="json",
    )

    assert marker["export_type"] == "pinescript_signal_marker"
    assert marker["row_count"] == signals["row_count"] == 1
    # The object key carries the full 24-char type — proof the widened column holds it.
    assert "/pinescript_signal_marker/" in marker["object_key"]
    # Different type -> different checksum namespace, same underlying rows.
    assert marker["checksum"] != signals["checksum"]
    assert marker["source_manifest_hash"] == signals["source_manifest_hash"]


async def test_agent_dataset_composes_every_persisted_artifact(session) -> None:
    """Composed from persisted artifacts only — never from UI local state."""
    result_id = await _result(session, "btres_agent", ledger_rows=3)

    out = await export_cmd.request_result_export(
        session,
        USER1,
        result_id=result_id,
        export_type="agent_dataset",
        export_format="json",
    )
    assert out["export_type"] == "agent_dataset"

    rows = await export_repo.load_source_rows(
        session, result_id=result_id, export_type=export_cmd.ExportType.AGENT_DATASET
    )
    assert out["row_count"] == len(rows)
    kinds = [row["artifact_type"] for row in rows]
    # Every row is tagged, and every artifact the fixture seeds is represented. The
    # fixture writes no ResultSummary, and the composite correctly omits it rather
    # than fabricating an empty summary row.
    assert set(kinds) == {"trade_ledger", "signal_events", "diagnostics"}
    assert kinds.count("trade_ledger") == 3
    # Fixed artifact order -> a reproducible composite checksum.
    assert kinds == sorted(
        kinds,
        key=lambda k: [
            "trade_ledger",
            "signal_events",
            "equity_curve",
            "diagnostics",
            "summary",
        ].index(k),
    )


async def test_agent_dataset_is_deterministic(session) -> None:
    """Same result + type + format -> same checksum (doc 15 §14)."""
    result_id = await _result(session, "btres_det", ledger_rows=2)
    first = await export_cmd.request_result_export(
        session, USER1, result_id=result_id, export_type="agent_dataset", export_format="json"
    )
    second = await export_cmd.request_result_export(
        session, USER1, result_id=result_id, export_type="agent_dataset", export_format="json"
    )
    assert first["export_id"] != second["export_id"]  # no idempotency key supplied
    assert first["checksum"] == second["checksum"]


async def test_agent_dataset_refused_when_a_pinned_package_is_not_approved(session) -> None:
    """The §3.2 'approved' half, checked against the manifest's own pins."""
    result_id = await _result(session, "btres_unapproved")
    await _pin_package(session, result_id, approval_state="draft")

    with pytest.raises(AgentDatasetSourceNotApprovedError) as excinfo:
        await export_cmd.request_result_export(
            session, USER1, result_id=result_id, export_type="agent_dataset", export_format="json"
        )
    await session.rollback()

    assert excinfo.value.code == "AGENT_DATASET_SOURCE_NOT_APPROVED"
    assert excinfo.value.retryable is False
    assert excinfo.value.details == [
        {"package_revision_id": "pkgrev_1", "role": "entry", "approval_state": "draft"}
    ]


async def test_an_unapproved_pin_never_blocks_the_other_export_types(session) -> None:
    """The gate is deliberately narrow — §3.2 restricts only the agent dataset.

    Refusing a trade-ledger export here would hide data the spec never restricted.
    """
    result_id = await _result(session, "btres_narrow", ledger_rows=2)
    await _pin_package(session, result_id, approval_state="draft")

    out = await export_cmd.request_result_export(
        session, USER1, result_id=result_id, export_type="trade_ledger", export_format="csv"
    )
    assert out["row_count"] == 2


async def test_an_approved_pin_lets_the_agent_dataset_through(session) -> None:
    result_id = await _result(session, "btres_approved")
    await _pin_package(session, result_id, approval_state="approved")

    out = await export_cmd.request_result_export(
        session, USER1, result_id=result_id, export_type="agent_dataset", export_format="json"
    )
    assert out["export_type"] == "agent_dataset"
