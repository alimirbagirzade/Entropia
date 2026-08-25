"""Karar 1's K1 rider — the commission DISTRIBUTION is declared in the manifest.

Master Ref Modul 6 §8 requires the commission distribution to be explicit in the engine
manifest. Before this it was not: the cost config lived inside the pinned strategy
revision as a hash, and a hash does not say what the engine did with it.

The rider as signed asked for the field INSIDE ``execution_key``. That was adjudicated
down on a measurement, and both halves of the adjudication are pinned here — the field
is published, and it did NOT move the reproduction identity.
"""

from __future__ import annotations

from typing import Any

from entropia.domain.backtest.manifest import COMMISSION_MODEL, build_run_manifest


def _item_manifest(revision_id: str = "worev_1") -> dict[str, Any]:
    return {
        "snapshot_id": "mbsnap_1",
        "workspace_id": "mbws_1",
        "composition_hash": "fp_1",
        "items": [
            {
                "item_id": "mbi_1",
                "kind": "strategy",
                "root_id": "strat_1",
                "revision_id": revision_id,
                "enabled": True,
                "position": 0,
            }
        ],
    }


def _build(item_manifest: dict[str, Any]) -> Any:
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


def test_the_manifest_declares_the_commission_distribution() -> None:
    """K1: the distribution is NAMED, not left to be inferred from a config hash.

    The literal is asserted, not just the key's presence: a field that silently became
    `None` or `""` would satisfy "is published" while declaring nothing.
    """
    manifest = _build(_item_manifest()).manifest

    assert manifest["commission_model"] == "per_fill"
    assert COMMISSION_MODEL == "per_fill"


def test_the_commission_model_stays_out_of_the_execution_key() -> None:
    """The adjudication, pinned: declaring the model must not fork reproducibility.

    ``execution_content`` is what ``execution_key`` hashes. Adding a run-invariant
    constant to it would shift EVERY key with no numeric change and no ``ENGINE_VERSION``
    bump behind it — an undeclared namespace shift. The field therefore rides beside
    ``mainboard_item_labels``, outside that dict, and this asserts the placement by its
    consequence rather than by reading the source.
    """
    manifest = _build(_item_manifest()).manifest

    # It is IN the manifest...
    assert "commission_model" in manifest
    # ...and NOT in the hashed reproducibility content.
    assert "commission_model" not in manifest.get("execution_content", {})


def test_the_basis_reaches_the_execution_key_through_the_pinned_revision() -> None:
    """Why the rider's own justification did not hold, measured rather than argued.

    The rider reasoned that without the field, two runs priced by different fee models
    would share a reproduction identity. They do not: `commission_basis` lives in the
    strategy config, revisions are immutable, so changing it mints a NEW revision id —
    and ``_pinned_items`` hashes ``selected_revision_id``. The discrimination the rider
    wanted already exists one level down.
    """
    flat_world = _build(_item_manifest("worev_flat")).execution_key
    bps_world = _build(_item_manifest("worev_bps")).execution_key

    assert flat_world != bps_world
