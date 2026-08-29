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
# v18-gap-adjusted-stop-fill (#549): a triggered PRICE stop now executes at the bar's OPEN
# when the bar opened already past the level, instead of at the level itself. The level was
# unattainable for the whole bar in that case, so the old reading understated the loss on
# every gapped stop-out — always in the run's favour. This is the exact mirror of the
# ``max(trigger, open)`` rule the engine already applied to a gapped stop ENTRY, so it
# completes a shipped rule rather than inventing one where canon is silent. Every gapped
# stop-out returns a different PnL, so the namespace must shift: a pre-fix Result can never
# be idempotently reused for a re-RUN (INF-04/INF-05).
# v18-percent-sizing-per-fill-commission (#550, #551, #552): three financial-logic fixes
# land together because each of them alone moves PnL, and a single namespace shift covers
# all three. (#550) ``base_position_size`` and the ``position_size_limits`` min/max caps are
# PERCENTAGES of resolved capital, not unit counts — a strategy that stored 10 now opens 10%
# of the account rather than 10 units, which is what the shipped UI's ``%`` suffix, doc 02's
# worked example and Master Ref §10.1 have always said. The scaling ladder and the
# same-direction stacking check convert the same cap the same way, so one config field has
# one meaning everywhere it binds. (#551) a size that resolves to zero opens NOTHING in
# independent mode too — the guard used to be reachable only under allocation, so a 0-size
# phantom position was booked, counted in ``total_trades`` and written to
# ``position_intervals`` where it could block another item's genuine entry. (#552) commission
# is charged PER FILL, entry included, instead of billing a whole round trip at the exit —
# which made cost scale with the number of partial CLOSES rather than fills, so a three-step
# scale-out paid 1.7 round trips for four fills. Every one of the three returns a different
# PnL for configs that were previously legal, so a pre-fix Result is never artifact-comparable
# and must never be idempotently reused for a re-RUN (INF-04/INF-05). Ready Check refuses to
# run a revision saved before the sizing cutover until a human re-confirms the magnitude
# (``STRATEGY_SIZING_SEMANTICS_UNCONFIRMED``); nothing is converted automatically, because
# the stored number does not say which reading its author meant.
# v18-a16-manifest-policy-provenance (`C7`, ADR 0002 §10.1/§10.3 + §14 A16/A15): the run
# manifest now carries the allocation PROVENANCE the canon requires — the resolved sleeve
# amounts and the per-entry settlement-currency refs (both were already computed at
# admission and discarded), plus the four policy versions below. Doc 13 §13 and Modül 11
# §10 have always required them; until now `grep -rn "allocation_policy" backend/` returned
# nothing, so a Result carried no record of WHICH clock / arbitration / mark-staleness
# policy produced it.
#
# THIS BUMP IS DIFFERENT FROM EVERY BUMP ABOVE IT, AND THE DIFFERENCE IS WRITTEN DOWN
# RATHER THAN GLOSSED. Each earlier entry names an executed-behaviour change and shifts the
# namespace so a Result priced under the old behaviour is never idempotently reused. This
# one changes NO executed behaviour: 49 of the 50 golden scenarios stay byte-identical, and
# the one that moves (`contract.execution_key`) moves only because it hashes the version
# string itself. What it shifts the namespace for is a RECORD change — a pre-`C7` Result
# cannot state its policy provenance, so it is not audit-comparable with one that can.
#
# The cost is real and is named here so `C9` cannot inherit it unknowingly: the namespace
# shift is a one-shot resource, and spending it here does NOT discharge A15. A15 exists so
# that a CONTAINED-era Result can never be idempotently reused for a UNIFIED-CLOCK re-RUN,
# and only a bump in the commit that lifts `SHARED_ALLOCATION_STATUS` can do that. `C9`
# MUST BUMP AGAIN. That obligation is not left to this comment: it is enforced by
# ``tests/unit/oracles/test_oracle_portfolio_containment_gate.py::
# test_lifting_containment_requires_a_second_engine_version_bump``. That guard is written
# as a PREDICATE exercised on all four (flag, version) corners rather than as an ``if``
# that is vacuously green until the day it matters, so a lift that reuses this string is a
# red build rather than a silent namespace collision.
#
# GH #532 bumps it again, and the reason is NOT that a number moved — none did. The
# decision-trace taxonomy gained ``entry_exit_collision``, an event PR #513 had emitted
# since the day it landed while the published list denied it existed. Measured: the
# taxonomy is absent from ``execution_content``, so the ``contract.execution_key`` payload
# is byte-identical without a bump, and each of the 45 golden payloads that moved differs
# by exactly the added member and nothing else. The bump is required anyway, for the
# reason the golden module states: ``execution_key`` keys the ARTIFACT's bytes, and
# without a shift two runs sharing a key would publish different diagnostics blocks — the
# stored pre-#532 Result would stop being byte-reproducible under its own key. This bump
# is NOT the `C9` lift bump (that one landed with the flag flip) and, unlike it, it moves
# non-``portfolio.*`` digests; A13's partition test pins group sizes, not values, so it
# stays green — a reader comparing this regeneration against A13's "only portfolio.* may
# move" sentence should read that sentence as scoped to the lift it was written for.
#
# GH #534 bumps it again, for the same reason and by the same measurement -- the axis is
# NOT "is this only diagnostics" but "do the artifact's bytes move". The provenance block
# published every conflict policy except two: ``same_candle_entry_exit`` (observable only
# inside an ``entry_exit_collision`` event, so a run with no collision recorded the policy
# nowhere) and the stop precedence order (invisible whenever the config left it null).
# Both are now published. Measured BEFORE the bump, member by member rather than by
# digest: 45 of the 50 golden payloads move, each by EXACTLY the two added members and
# nothing else; the 5 that do not move are exactly the 5 that carry no conflict block; the
# ``contract.execution_key`` payload is byte-identical without the bump, so the post-bump
# delta is 46 = 45 + ``execution_key``. No financial number moved -- every difference is
# an added key. That is precisely why the bump is still required: ``execution_key`` keys
# the ARTIFACT's bytes, so without a shift a stored pre-#534 Result and a new one would
# share a key while publishing different diagnostics blocks. This is the same class the
# ADIM 135 signature ruled the OTHER way, and the two do not conflict: OD-2's diagnostics
# addition moved zero golden digests, so its key stayed faithful without a bump.
ENGINE_VERSION = "backtest-engine-v18-conflict-provenance-completed"

# K1 (Master Ref Modul 6 §8: "komisyon dagilimi engine manifestinde acik olmalidir"),
# satisfied by Karar 1's mandatory rider (GH #552, signed 2026-08-25). Until now the
# manifest said NOTHING about commission: the cost config lived inside the pinned
# strategy revision as a hash, and a hash is not an explanation.
#
# This names the DISTRIBUTION — how a fee is split across a position's fills — which is
# what §8 asks for and which is engine-wide: `booking.close_position` charges one fee per
# fill unconditionally, with no config switch. It deliberately does NOT name the BASIS
# (`commission_basis`, flat|bps). The basis is PER-ITEM config, so one scalar here would
# misstate a composition whose items carry different bases, and it is already pinned
# transitively — a config change mints a new strategy revision and `_pinned_items` hashes
# `selected_revision_id` into `execution_key` (measured 2026-08-25).
#
# Update this string only in the commit that changes what `booking` actually does; the
# shipped distribution is pinned behaviourally by
# `test_oracle_position_lifecycle.py::test_every_fill_pays_one_commission_entry_included`.
COMMISSION_MODEL = "per_fill"

METRIC_SET_VERSION = "metric-set-v1"
OUTPUT_ARTIFACT_PROFILE = "standard-v1"

# ---------------------------------------------------------------------------
# A16 — the four policy versions (ADR 0002 §10.1, §10.3, §14 A16).
#
# WHY THESE ARE LITERALS AND NOT IMPORTS. Each value is also defined by the module that
# OWNS the policy, under `execution/` — the contained phase loop. This module sits outside
# that directory, and the containment gate scans production source as TEXT for the dotted
# `execution.<module> import` spelling; the per-module allowlists it holds are signed
# (`docs/decisions/closure_participant_importer_allowlist_2026-08-18.md`) and name exactly
# two modules. Importing the constants here would widen a signed allowlist by an unsigned
# third module to fetch four inert strings. So the values are restated, following the
# `portfolio_mode.py::UNIFIED_MANIFEST_KEY` precedent, which solved this same problem the
# same way — and, like that module, the comments here deliberately spell the owning modules
# as PATHS (`execution/clock.py`), because the dotted form would trip the very scan being
# described.
#
# TWO SPELLINGS DRIFT — SO THE SECOND ONE IS DERIVED, NOT TRUSTED. Restating a value is
# exactly how a repo grows two answers to one question. The drift is closed on the TEST
# side, where importing the contained layer is free: `tests/unit/test_a16_manifest_policy_
# parity.py` imports both this module and each owning module and asserts equality, so a
# change to either spelling that is not made to both is a red build. That is the shape
# ADIM 125 settled on when a single shared symbol was impossible.
ENGINE_ALLOCATION_POLICY_VERSION = "portfolio-allocation-v1"  # execution/provenance.py
CLOCK_POLICY_VERSION = "clock-policy-v1"  # execution/clock.py
ARBITRATION_POLICY_VERSION = "arbitration-policy-v1"  # execution/arbitration.py

# NOT a version of nothing any more — a real DISCLOSURE. ADR 0002 §13 OD-2 (how an open
# position is marked at a tick with no fresh bar of its own) was decided (a) on 2026-08-05 and
# BUILT at ADIM 20 (containment-lift precondition 17): carry the last closed bar's close
# forward under a declared `stale_after` bound with a diagnostic counter. The implementation
# and the bound live in `execution/portfolio_ledger.py` (`MarkPrice.is_usable`,
# `MARK_STALE_AFTER_MS`); this module cannot import them — the signed importer allowlist names
# two modules and `manifest.py` is not one of them (ADIM 118/126) — so the literal is
# RE-WRITTEN here and `test_a16_manifest_policy_parity.py` closes the drift.
#
# The flip moved the `execution_key` namespace, which is the correct coupling and was spent
# deliberately in the lift commit: a run marked under a real staleness bound is not comparable
# with one marked under none. Changing `MARK_STALE_AFTER_MS` later REQUIRES a new version here.
MARK_STALENESS_POLICY = "carry_forward_bounded_v1"


#: The block as it appears in the manifest, built once so the two placements below cannot
#: disagree.
def _portfolio_policy() -> dict[str, Any]:
    return {
        "engine_allocation_policy_version": ENGINE_ALLOCATION_POLICY_VERSION,
        "clock_policy_version": CLOCK_POLICY_VERSION,
        "arbitration_policy_version": ARBITRATION_POLICY_VERSION,
        "mark_staleness_policy": MARK_STALENESS_POLICY,
    }


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
        # A16. INSIDE ``execution_content``, unlike ``commission_model`` below — and the
        # test that separates them is the one that adjudication itself used (2026-08-25):
        # does the field buy DISCRIMINATION nothing else already provides? For the
        # commission model the answer was no; it is a function of the pinned strategy
        # revisions, which ``_pinned_items`` already hashes, so including it would have
        # shifted every key while distinguishing nothing. For these four the answer is
        # yes: no pinned revision, fingerprint or context group encodes the clock,
        # arbitration or mark-staleness policy, so without them two runs replayed under
        # DIFFERENT policies would share an ``execution_key`` and the older Result would
        # be idempotently reused for the newer question (INF-04/INF-05).
        #
        # These are engine-wide, so an independent single-Strategy run carries them too.
        # That is deliberate and fail-closed: over-shifting costs a re-run, under-shifting
        # returns a stale Result, and only one of those two is silent.
        "portfolio_policy": _portfolio_policy(),
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
        # Karar 1's K1 rider. Placed HERE — in the manifest, outside ``execution_content``
        # — on the ``mainboard_item_labels`` precedent directly above.
        #
        # The rider as signed asked for it INSIDE ``execution_key``, reasoning that two runs
        # priced by different fee models would otherwise share a reproduction identity. That
        # reasoning was measured and does not hold: the model is a function of the pinned
        # strategy revisions, and ``_pinned_items`` already hashes ``selected_revision_id``,
        # so the two runs' keys differ regardless. Adding it to ``execution_content`` would
        # therefore buy no discrimination while shifting EVERY execution_key — an undeclared
        # namespace shift with no version bump behind it, which is precisely what the
        # ``ENGINE_VERSION`` comments above exist to prevent. Adjudicated 2026-08-25.
        "commission_model": COMMISSION_MODEL,
        # A16, surfaced in the manifest body as well as in ``execution_content`` so a
        # reader of a persisted Result can see the policy provenance without recomputing
        # a hash. Same object, built once, so the two placements cannot disagree.
        "portfolio_policy": _portfolio_policy(),
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
    "ARBITRATION_POLICY_VERSION",
    "CLOCK_POLICY_VERSION",
    "COMMISSION_MODEL",
    "ENGINE_ALLOCATION_POLICY_VERSION",
    "ENGINE_VERSION",
    "MARK_STALENESS_POLICY",
    "METRIC_SET_VERSION",
    "OUTPUT_ARTIFACT_PROFILE",
    "ManifestBuildResult",
    "build_run_manifest",
    "pinned_item_labels",
]
