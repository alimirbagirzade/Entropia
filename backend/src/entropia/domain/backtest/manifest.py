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

# F-07i (C): the tick-dependent execution SETTINGS (intrabar_touch /
# limit_fill_simulation / stop_limit_priority_simulation timings + partial-fill
# policies) are now executed over the pinned print path — the version bump shifts the
# execution_key namespace so a pre-(C) result is never reused for a config whose
# settings now genuinely execute (INF-04/INF-05).
# v17: a multi-item composition Result now persists a PER-ITEM breakdown (each executing
# strategy's own equity curve + PnL/drawdown/trade-count) in ``diagnostics.composition.items``.
# Additive to the artifact, but the version bump shifts the execution_key namespace so a
# stale pre-v17 composite result (which lacks the per-item breakdown) is NOT idempotently
# reused for a re-RUN of the same composition (INF-04/INF-05) — a re-RUN produces the
# richer artifact instead of returning the older one.
# v18: PORTFOLIO-LEVEL rules now EXECUTE (doc 13 §8.4 cross-item): a composition-wide
# Max Total Exposure cap + the opposing same-instrument conflict policy gate entries /
# stack tranches / scale layers against the earlier-pinned items' held windows
# (sequential pin-order precedence, fail-closed, L4-disclosed; NET executes as
# BLOCK_OPPOSITE). The bump shifts the execution_key namespace so a pre-v18 result is
# never reused for a plan whose rules now genuinely execute (INF-04/INF-05).
# v18-capability-matrix (F-05): the machine-readable capability matrix
# (domain/backtest/capabilities.py) is now a fail-closed engine gate, so every option the
# matrix marks ``future_dev`` opens NO position. This CHANGES executed behaviour for one
# previously-ungated option: ``data.costs.slippage_mode = 'historical_slippage_if_available'``
# used to run as a silent ZERO-slippage backtest (``_cost_params`` never branched on the mode
# and the schema makes ``slippage_value`` optional under it). The bump shifts the
# execution_key namespace so such a result — produced under an over-optimistic fill model — is
# never idempotently reused for a re-RUN now that the config is correctly refused
# (INF-04/INF-05).
# v18-available-time-gate (K-02): every research-feed access in the engine is now gated by
# the canonical ``research_data.time_policy.is_eligible_for_decision`` predicate (doc 12 §8.4
# rule 2), and the run FAILS CLOSED wherever eligibility cannot be proven — an unresolvable
# bar timestamp while funding is active, an incoherent available-time policy/delay pair, and
# a funding source with no valid instrument mapping now raise instead of silently booking a
# ZERO funding cost. A result produced under those previously-silent, over-optimistic paths
# must never be idempotently reused for a re-RUN (INF-04/INF-05), so the bump shifts the
# execution_key namespace.
# v18-full-pinning (K-04): the manifest now carries ALL SEVEN doc 15 §9.2 field groups.
# The three that only exist behind a dereference — strategy/package context (the real
# strategy revision + every transitive indicator/condition/reference package revision and
# its resolver/ESP refs), external object context (the TS/TL import revision + its
# mapping/timezone/availability/price-source policy) and data/time context (the market
# dataset revision + coverage + execution resolution + the research feed's available-time
# policy, join/instrument mapping and definition versions) — were previously re-derived by
# the WORKER at run time, so a Result carried no proof of which revisions produced it and a
# post-admission change to a package/dataset/import pin could go unnoticed. Those pins are
# now part of the REPRODUCIBILITY content and are re-resolved fail-closed before replay, so
# a result produced under a different (or since-removed) dependency set is never
# idempotently reused for a re-RUN (INF-04/INF-05) — the bump shifts the execution_key
# namespace accordingly.
# v18-funding-step-order (K-03): funding/fee/carry is now applied at the TOP of each bar
# (doc 15 §9.3 step 2) instead of at the end of the bar loop. Because ``equity`` sizes every
# entry (``_position_size``) and bounds the allocation sleeve / exposure caps
# (``_sleeve_capital``), the old end-of-bar placement sized entries and scale layers off
# equity that had not yet paid its carry — a one-directional CUMULATIVE bias toward larger
# positions and a late-binding ``max_total_exposure`` under perp funding. It also silently
# DROPPED a charge whose record became available on the bar that closed the position. Every
# funding-enabled result therefore changes numerically: a result produced under the old order
# stays valid under its own pinned engine_version but is NOT comparable with a new one, and
# the bump shifts the execution_key namespace so it is never idempotently reused for a
# re-RUN (INF-04/INF-05).
# v18-restriction-min-n (I-15a): the Restrictions/Filters combination gained the spec's
# third option (doc 02 §5.8) — ``rule="min_n_of_m"`` + ``min_true_count``. The entry gate
# ``_restrictions_block`` now has a third branch, so a strategy saved under the new rule
# opens a DIFFERENT set of positions than the same filter set would have under the old
# any/all-only engine (which could not even parse the value). ``any``/``all`` are
# untouched and reproduce their prior results exactly; the bump exists because the saved
# config space widened, and it shifts the execution_key namespace so a result produced by
# an engine that could not evaluate Minimum-N is never idempotently reused for a re-RUN
# (INF-04/INF-05).
# v18-filtered-events-artifact (I-02): the FILTER vetoes (``filtered_no_entry``) leave the
# ``signal_events`` journal and become their own ``filtered_events`` output journal +
# persisted artifact (doc 15 §3.2 "View Filtered Events", §16). No trade, fill, price or
# metric changes — but the artifact SHAPE does: ``signal_events`` loses those rows and every
# surviving row's ``seq`` is renumbered, and ``diagnostics.decision_trace_count`` now counts
# the signal journal alone. Those rows are persisted into the immutable Result and read by
# users, so a pre-I-02 Result is NOT artifact-comparable with a new one; the bump shifts the
# execution_key namespace so it is never idempotently reused for a re-RUN (INF-04/INF-05).
# v18-min-n-filtered-events-artifact (I-02 merged onto I-15a): this branch carries BOTH
# engine changes, so the version names both. It is NOT a third behavioural change — the
# single string exists because the namespace must shift relative to EACH predecessor: a
# Result produced by the min-n-only engine (no filtered_events artifact) and one produced
# by the filtered-events-only engine (no Minimum-N gate) are both incomparable with what
# this engine emits, and neither may be idempotently reused for a re-RUN.
# v18-scaling-tf-sequence (S5c): Logic-Based Scaling stopped being a future_dev selection —
# logic-scaling blocks now resolve through the same resolver as entry/exit/stop and propose
# a same-direction layer on the signal's EDGE, gated on the closed candle of the scaling
# timeframe sequence's Nth entry (doc 02 §5.7). A strategy carrying a logic scaling block
# therefore opens a DIFFERENT ladder than the same config did under the engine that
# reported it unsupported, so the bump shifts the execution_key namespace and a pre-S5c
# Result is never idempotently reused for a re-RUN (INF-04/INF-05).
# v18-scaling-tf-sequence-per-item-labels (F-07): immutable composite Result diagnostics
# now persist the snapshot-owned label beside each per-item and leave-one-out row. The
# labels stay outside execution_content so renames do not fork reproducibility, but the
# artifact shape changed; this namespace shift prevents stale label-less Results from
# being idempotently reused.
ENGINE_VERSION = "backtest-engine-v18-same-candle-entry-exit"
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


def pinned_item_labels(item_manifest: dict[str, Any]) -> dict[str, str]:
    """Project the snapshot's per-item human labels (F-07 §4.4).

    DELIBERATELY separate from ``_pinned_items``: that projection is hashed into
    ``execution_key``, and a DISPLAY label must never change a run's reproducibility
    identity — renaming a composition item would otherwise make an identical replay
    look like a different execution. These labels therefore ride in the manifest only,
    outside ``execution_content``.

    They exist so the Result's per-item breakdown can name its rows from the PINNED
    composition instead of the live one: the result is immutable, and an item renamed
    or swapped after the run must not re-label a finished result.

    Snapshots written before the manifest carried ``label`` simply yield no entries —
    the reader then falls back to the raw item id rather than inventing a name.
    """
    raw = item_manifest.get("items", []) if isinstance(item_manifest, dict) else []
    labels: dict[str, str] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("item_id")
        label = entry.get("label")
        if isinstance(item_id, str) and isinstance(label, str) and label:
            labels[item_id] = label
    return labels


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
    tick_data: dict[str, Any] | None = None,
    strategy_package_context: list[dict[str, Any]] | None = None,
    external_object_context: list[dict[str, Any]] | None = None,
    data_time_context: list[dict[str, Any]] | None = None,
) -> ManifestBuildResult:
    """Assemble the immutable manifest (doc 15 §9.2 minimum content).

    ``tick_data`` (F-07i B) pins the approved tick/trade revision per tick-demanding
    Strategy item (``{item_id: {"tick_revision_id", "instrument_id"}}``) — resolved
    at ADMISSION so the worker never falls back to 'newest approved' (doc 15 §15).
    It is part of the REPRODUCIBILITY content: two runs replaying different tick
    paths must never share an ``execution_key`` (INF-04/INF-05).

    ``strategy_package_context`` / ``external_object_context`` / ``data_time_context``
    (K-04) are the three doc 15 §9.2 groups that only exist behind a dereference,
    resolved at ADMISSION by ``commands.backtest_run_context`` over the SAME paths the
    worker walks. They are reproducibility content too: two runs whose transitive
    package / dataset / import revisions differ replay different inputs and must never
    share an ``execution_key``. ``None`` (no resolver supplied) keeps the pre-K-04
    manifest shape with explicit nulls rather than a fabricated empty pin set."""
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
        "tick_data": tick_data,
        "strategy_package_context": strategy_package_context,
        "external_object_context": external_object_context,
        "data_time_context": data_time_context,
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
        # F-07 §4.4 — display labels for the pinned items, NOT part of
        # ``execution_content`` above and therefore NOT part of ``execution_key``: a
        # rename must never fork a run's reproducibility identity. The worker copies
        # these onto each ``ItemRun`` so the immutable Result can name its per-item and
        # leave-one-out rows without ever joining the live composition.
        "mainboard_item_labels": pinned_item_labels(item_manifest),
        "strategy_package_context": strategy_package_context,
        "external_object_context": external_object_context,
        "data_time_context": data_time_context,
        "capital_execution": capital_mode,
        "result_artifact_context": artifact_context,
        "tick_data": tick_data,
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
    "pinned_item_labels",
]
