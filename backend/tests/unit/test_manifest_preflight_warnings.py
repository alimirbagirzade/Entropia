"""S-L4 — RC-03: readiness WARNINGS are retained in the manifest, not just counted.

Doc 14 RC-03 requires a warning be "retained in report AND later manifest". The
manifest previously carried ``warning_count`` alone, which cannot say WHICH item or
field was flagged — so an archived manifest could not tell a later reader what the
run was knowingly admitted despite.

These are the pure-function guarantees. The end-to-end proof (a real allocation
warning surviving admission into the stored manifest row) lives in
``tests/integration/test_backtest_manifest_warnings.py``.
"""

from __future__ import annotations

from entropia.application.commands.backtest_run import _manifest_warning_rows
from entropia.domain.backtest.manifest import build_run_manifest

_ITEM_MANIFEST = {
    "items": [
        {
            "item_id": "mbwi_1",
            "kind": "strategy",
            "root_id": "root_1",
            "revision_id": "rev_1",
            "position": 1,
            "enabled": True,
        }
    ]
}

_WARNING = {
    "code": "ALLOCATION_UNALLOCATED_CASH",
    "severity": "warning",
    "scope": "allocation",
    "scope_id": "cmbi_1",
    "field_path": "allocation.entries",
    "message": "80% active share defined; the remaining 20% stays unallocated.",
    "remediation": "Allocate the remaining share or accept the idle cash.",
}
_BLOCKER = {
    "code": "COMPOSITION_EMPTY",
    "severity": "blocker",
    "scope": "composition",
    "scope_id": None,
    "field_path": None,
    "message": "No enabled item.",
    "remediation": "Add one.",
}


def _build(preflight: dict) -> object:
    return build_run_manifest(
        run_id="btrun_1",
        composition_id="mbws_1",
        composition_snapshot_id="mbsnap_1",
        composition_fingerprint="fp_1",
        item_manifest=_ITEM_MANIFEST,
        capital_mode={"enabled": False},
        requested_by_principal_id="user_1",
        preflight=preflight,
        correlation_id="corr_1",
        created_at_iso="2024-03-01T00:00:00Z",
    )


def test_warning_rows_carry_code_scope_path_and_message() -> None:
    rows = _manifest_warning_rows([_WARNING])
    assert rows == [
        {
            "code": "ALLOCATION_UNALLOCATED_CASH",
            "scope": "allocation",
            "scope_id": "cmbi_1",
            "field_path": "allocation.entries",
            "message": "80% active share defined; the remaining 20% stays unallocated.",
        }
    ]


def test_blockers_never_reach_the_manifest() -> None:
    """A blocker means no run was admitted at all, so a manifest cannot carry one."""
    assert _manifest_warning_rows([_BLOCKER]) == []
    assert _manifest_warning_rows([_BLOCKER, _WARNING])[0]["code"] == "ALLOCATION_UNALLOCATED_CASH"


def test_rows_are_order_stable() -> None:
    """Same preflight -> same manifest bytes, whatever order the evaluator emitted."""
    second = {**_WARNING, "code": "MARKET_DATA_LIMITED_COVERAGE", "scope_id": "cmbi_2"}
    assert _manifest_warning_rows([_WARNING, second]) == _manifest_warning_rows([second, _WARNING])


def test_manifest_retains_the_rows_next_to_the_count() -> None:
    built = _build(
        {
            "ready_report_id": "rcrpt_1",
            "state": "ready_with_warnings",
            "warning_count": 1,
            "warnings": _manifest_warning_rows([_WARNING]),
        }
    )
    preflight = built.manifest["preflight"]
    assert preflight["warning_count"] == 1
    assert [w["code"] for w in preflight["warnings"]] == ["ALLOCATION_UNALLOCATED_CASH"]
    assert preflight["warnings"][0]["field_path"] == "allocation.entries"


def test_warnings_change_the_manifest_hash_but_not_the_execution_key() -> None:
    """The rows are EVIDENCE, not execution inputs.

    ``preflight`` is outside ``execution_content``, so enriching it must not shift the
    execution_key namespace — otherwise every prior Result would stop being
    idempotently reusable for a re-RUN (INF-04/INF-05) and ENGINE_VERSION would have
    to be bumped. It is not, and this test is what pins that.
    """
    bare = _build(
        {"ready_report_id": "rcrpt_1", "state": "ready_with_warnings", "warning_count": 1}
    )
    rich = _build(
        {
            "ready_report_id": "rcrpt_1",
            "state": "ready_with_warnings",
            "warning_count": 1,
            "warnings": _manifest_warning_rows([_WARNING]),
        }
    )
    assert rich.execution_key == bare.execution_key
    assert rich.manifest_hash != bare.manifest_hash
