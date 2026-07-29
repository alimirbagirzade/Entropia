"""F-07 §4.4 — display labels ride the run manifest WITHOUT entering execution_key.

The Result's per-item breakdown must be able to name its rows, and doc 16 §4 forbids
re-resolving that name from the live Mainboard: the label therefore has to travel in
the immutable manifest.

The danger is that ``mainboard_items`` — the obvious place to put it — is hashed into
``execution_key``. Putting a DISPLAY string there would fork a run's reproducibility
identity on a rename: the same composition, replayed identically, would stop matching
its own prior execution key (INF-04/INF-05). These tests pin the separation.
"""

from __future__ import annotations

from typing import Any

from entropia.domain.backtest.manifest import (
    ENGINE_VERSION,
    build_run_manifest,
    pinned_item_labels,
)

# The version this slice replaced — the namespace a labelled result must LEAVE.
_PRIOR_ENGINE_VERSION = "backtest-engine-v18-min-n-filtered-events-artifact"


def _item_manifest(*, labelled: bool) -> dict[str, Any]:
    return {
        "snapshot_id": "mbsnap_1",
        "workspace_id": "mbws_1",
        "composition_hash": "fp_1",
        "items": [
            {
                "item_id": "mbi_1",
                "kind": "strategy",
                "root_id": "strat_1",
                "revision_id": "worev_1",
                "enabled": True,
                "position": 0,
                **({"label": "Momentum A"} if labelled else {}),
            },
            {
                "item_id": "mbi_2",
                "kind": "trade_log",
                "root_id": "tl_1",
                "revision_id": "worev_2",
                "enabled": True,
                "position": 1,
                "label": None,
            },
        ],
    }


def _build(item_manifest: dict[str, Any]):
    return build_run_manifest(
        run_id="btrun_1",
        composition_id="mbws_1",
        composition_snapshot_id="mbsnap_1",
        composition_fingerprint="fp_1",
        item_manifest=item_manifest,
        capital_mode={"enabled": False},
        requested_by_principal_id="user_1",
        preflight={"ready_report_id": "rcrpt_1", "state": "ready", "warning_count": 0},
        correlation_id="corr_1",
        created_at_iso="2024-03-01T00:00:00Z",
    )


def test_labels_do_not_change_the_execution_key() -> None:
    """THE invariant: renaming a composition item must not fork reproducibility.

    Two manifests differing ONLY in the display label must share an execution_key, so
    a renamed-but-otherwise-identical composition still reproduces (and idempotently
    reuses) the same execution.
    """
    unlabelled = _build(_item_manifest(labelled=False))
    labelled = _build(_item_manifest(labelled=True))

    assert labelled.execution_key == unlabelled.execution_key


def test_labels_are_absent_from_the_hashed_pin_set() -> None:
    """Belt-and-braces for the test above: the pin set itself carries no label.

    Equality of execution_key could in principle hold for the wrong reason; this
    asserts the structural fact that produces it.
    """
    built = _build(_item_manifest(labelled=True))

    assert all("label" not in item for item in built.manifest["mainboard_items"])


def test_manifest_publishes_the_pinned_labels_separately() -> None:
    built = _build(_item_manifest(labelled=True))

    assert built.manifest["mainboard_item_labels"] == {"mbi_1": "Momentum A"}


def test_unlabelled_items_yield_no_entry_rather_than_a_fabricated_name() -> None:
    """A null/absent label must NOT become a name derived from the id (F-07)."""
    labels = pinned_item_labels(_item_manifest(labelled=False))

    assert labels == {}
    assert "mbi_2" not in pinned_item_labels(_item_manifest(labelled=True))


def test_pre_f07_snapshot_degrades_to_an_empty_label_map() -> None:
    """Snapshots written before the manifest carried ``label`` must still build."""
    legacy = {
        "items": [{"item_id": "mbi_1", "kind": "strategy", "root_id": "s", "revision_id": "r"}]
    }

    assert pinned_item_labels(legacy) == {}
    assert _build(legacy).manifest["mainboard_item_labels"] == {}


def test_the_artifact_change_shifted_the_execution_key_namespace() -> None:
    """The per-item breakdown gained ``item_label``, so the artifact SHAPE changed.

    Engine behaviour did not — every strategy-replay golden scenario is byte-identical
    and only the four ``portfolio.combine*`` composite ones moved. But an additive
    artifact change still needs the bump (the same reasoning v17 recorded for the
    per-item breakdown itself): without it a stale pre-label result would be idempotently
    REUSED for a re-RUN of the same composition and its rows would stay id-only forever,
    so the fix would never reach an existing composition.

    This is a ONE-TIME namespace shift and does not contradict
    ``test_labels_do_not_change_the_execution_key`` above: that one holds the version
    fixed and varies the label VALUE.
    """
    assert ENGINE_VERSION == "backtest-engine-v18-min-n-filtered-events-per-item-labels"

    item_manifest = _item_manifest(labelled=True)

    def _with(version: str) -> str:
        return build_run_manifest(
            run_id="btrun_1",
            composition_id="mbws_1",
            composition_snapshot_id="mbsnap_1",
            composition_fingerprint="fp_1",
            item_manifest=item_manifest,
            capital_mode={"enabled": False},
            requested_by_principal_id="user_1",
            preflight={"ready_report_id": "rcrpt_1", "state": "ready", "warning_count": 0},
            correlation_id="corr_1",
            created_at_iso="2024-03-01T00:00:00Z",
            engine_version=version,
        ).execution_key

    assert _with(ENGINE_VERSION) != _with(_PRIOR_ENGINE_VERSION)
    # ...while the same pin under the same engine still reproduces the same key.
    assert _with(ENGINE_VERSION) == _with(ENGINE_VERSION)
