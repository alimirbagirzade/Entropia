"""Immutable Backtest Run Manifest builder (Stage 5a, doc 15 §9.2, §15).

Pure: no DB, no clock, no randomness. The caller passes ``created_at_iso`` so the
manifest is deterministic for a given input. The manifest PINS exact revision ids
(never 'latest'); the worker consumes only this record (doc 15 §1, §9.1).

Two hashes are produced:

* ``execution_key`` — sha256 over the REPRODUCIBILITY content only (pinned items +
  capital + engine/metric versions), EXCLUDING run identity. Identical
  compositions therefore share an execution key, so the deterministic engine
  reproduces identical results (doc 15 §17 async reproducibility).
* ``manifest_hash`` — sha256 over the WHOLE manifest INCLUDING ``run_id`` +
  ``created_at`` + ``correlation_id``, so every run (and every retry of a failed
  run) gets a unique manifest hash (doc 15 §7, §8.4 "retry -> new manifest hash").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from entropia.shared.manifest import manifest_hash

ENGINE_VERSION = "backtest-engine-v2-allocation-execution"
METRIC_SET_VERSION = "metric-set-v1"
OUTPUT_ARTIFACT_PROFILE = "standard-v1"


@dataclass(frozen=True, slots=True)
class ManifestBuildResult:
    """The canonical manifest dict + its two content hashes."""

    manifest: dict[str, Any]
    manifest_hash: str
    execution_key: str


def _pinned_items(item_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Project the snapshot's item manifest into pinned (root, revision) tuples.

    Sorted by ``(root_id, selected_revision_id)`` so the pin set is order-stable
    (mirrors the composition fingerprint's sort — doc 01 §5.2)."""
    raw = item_manifest.get("items", []) if isinstance(item_manifest, dict) else []
    items = [
        {
            "item_id": entry.get("item_id"),
            "item_kind": entry.get("kind"),
            "root_id": entry.get("root_id"),
            "selected_revision_id": entry.get("revision_id"),
            "position": entry.get("position"),
            "enabled": entry.get("enabled"),
        }
        for entry in raw
    ]
    return sorted(items, key=lambda m: (str(m["root_id"]), str(m["selected_revision_id"])))


def build_run_manifest(
    *,
    run_id: str,
    composition_id: str,
    composition_snapshot_id: str,
    composition_fingerprint: str,
    item_manifest: dict[str, Any],
    capital_mode: dict[str, Any] | None,
    requested_by_principal_id: str | None,
    preflight: dict[str, Any],
    correlation_id: str | None,
    created_at_iso: str,
    engine_version: str = ENGINE_VERSION,
    metric_set_version: str = METRIC_SET_VERSION,
    output_artifact_profile: str = OUTPUT_ARTIFACT_PROFILE,
) -> ManifestBuildResult:
    """Assemble the immutable manifest (doc 15 §9.2 minimum content)."""
    items = _pinned_items(item_manifest)
    artifact_context = {
        "metric_set_version": metric_set_version,
        "output_artifact_profile": output_artifact_profile,
    }
    execution_content = {
        "composition_fingerprint": composition_fingerprint,
        "mainboard_items": items,
        "capital_execution": capital_mode,
        "result_artifact_context": artifact_context,
        "engine_version": engine_version,
    }
    execution_key = manifest_hash(execution_content)
    manifest = {
        "identity": {
            "run_id": run_id,
            "composition_id": composition_id,
            "composition_snapshot_id": composition_snapshot_id,
            "composition_fingerprint": composition_fingerprint,
            "requested_by_principal_id": requested_by_principal_id,
            "created_at": created_at_iso,
            "engine_version": engine_version,
            "correlation_id": correlation_id,
        },
        "mainboard_items": items,
        "capital_execution": capital_mode,
        "result_artifact_context": artifact_context,
        "preflight": preflight,
        "execution_key": execution_key,
    }
    return ManifestBuildResult(
        manifest=manifest,
        manifest_hash=manifest_hash(manifest),
        execution_key=execution_key,
    )


__all__ = [
    "ENGINE_VERSION",
    "METRIC_SET_VERSION",
    "OUTPUT_ARTIFACT_PROFILE",
    "ManifestBuildResult",
    "build_run_manifest",
]
