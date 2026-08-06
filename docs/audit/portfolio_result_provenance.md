<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# ADIM 19 — unified portfolio manifest, ledger artifact and per-item attribution

**Branch:** `feat/portfolio-unified-result-artifacts` · **Base:** `origin/main` `9739466`
· **Date:** 2026-08-05

This is the evidence record for the slice. It states the manifest schema and its version
knobs, the legacy-compatibility and migration decision, the `ENGINE_VERSION` decision, and
the attribution reconciliation proof — including the two divergences found while writing it.

---

## 0. What is contained, and what actually ships

| Module | Contained? | Rollback |
|---|---|---|
| `domain/backtest/execution/provenance.py` | **yes** — nothing in production imports it | delete the module |
| `domain/backtest/execution/attribution.py` | **yes** — only `provenance.py` imports it | delete the module |
| `domain/backtest/portfolio_mode.py` | **no** — production read path | revert; the field is additive |

`SHARED_ALLOCATION_STATUS` is **unchanged** (`future_dev`). No shared run can be admitted,
`ENGINE_VERSION` is untouched, there is no migration, and the OpenAPI snapshot is byte-identical.
The four pre-existing containment tests were updated **deliberately** (each now names the new
contained importer explicitly rather than loosening its assertion), and a fifth and sixth were
added for the two new modules.

---

## 1. Manifest schema and version knobs

`execution/provenance.py::PortfolioManifest`. `identity` is a sha256 over
`execution_content()` via the shipped `shared.manifest.manifest_hash`.

```
portfolio_simulation = {
  "policy_versions": {
    "portfolio_manifest_version":        "portfolio-manifest-v1",
    "engine_version":                    <caller-supplied>,
    "clock_policy_version":              "clock-policy-v1",
    "intent_contract_version":           "item-intent-v1",
    "portfolio_ledger_policy_version":   "portfolio-ledger-v1",
    "arbitration_policy_version":        "arbitration-policy-v1",
    "engine_allocation_policy_version":  "portfolio-allocation-v1",
    "attribution_policy_version":        "portfolio-attribution-v1",
    "contribution_method":               "additive_pnl_decomposition",
    "money_quantum": "0.01", "quantity_quantum": "1E-8",
    "money_rounding": "ROUND_HALF_EVEN",
    "mark_staleness_policy":  "undefined_pending_od2",     # OD-2 is OPEN
    "mark_staleness_status":  "open_decision",
    "mark_staleness_tracking":"ADR 0002 §13 OD-2"
  },
  "portfolio_allocation": { ... },        # Modül 11 §10 literal shape, see §2
  "items": [ {item_id, pin_ordinal, item_kind, root_id,
              selected_revision_id, data_revisions} ],
  "conflict_policy": { policy, supported, opposite_same_instrument,
                       same_direction_same_instrument, separate_position_books,
                       shares_capital, canon, undefined_semantics,
                       selection_policy, selection_status },
  "time_alignment": { timeline_identity, tick_count, first_t_ms, last_t_ms },
  "ledger_artifact": { artifact_type, row_count, checksum, schema_version } | null,
  # NOT hashed:
  "identity": <sha256>,
  "presentation": { "item_labels": {...} },
  "divergences": [ ... ]
}
```

**Display labels are outside the hash.** `execution_content()` excludes
`presentation.item_labels`, mirroring the split `manifest.pinned_item_labels` already makes
for the sequential manifest (`manifest.py:160-185`). Proof:
`test_the_manifest_identity_ignores_display_labels` renames every item and asserts
`identity` is unchanged while `presentation` differs. Mutation **M4** (moving labels into the
hashed content) is killed by that test.

**Tamper-evidence.** `test_the_manifest_identity_is_tamper_evident` parametrises four
independent mutations (engine version, timeline, ledger artifact, sleeve amounts); a fifth
test changes a pinned `selected_revision_id`. Each shifts `identity`.

**Open decisions are disclosed, not guessed.** OD-2 (mark staleness) has no answer in canon,
so `mark_staleness_policy` carries the literal `"undefined_pending_od2"` — following the
precedent `arbitration.CONTENTION_SELECTION_STATUS` set for OD-3. `attribution.py` therefore
values a *stale-but-usable* mark and refuses to invent a staleness cutoff
(`test_a_stale_mark_is_usable_and_its_staleness_is_not_thresholded_here`).

---

## 2. The allocation block — canon field names, verbatim

Modül 11 §10 (`Master Technical Reference:8313-8333`) writes
`backtest_run_manifest.portfolio_allocation` literally. Those names are reproduced exactly:
`plan_revision_id`, `enabled`, `initial_capital`, `reserve_amount`, `compounding_mode`,
`entries[].{composition_item_snapshot_id, item_revision_id, share_percent,
initial_sleeve_capital}`, `engine_allocation_policy_version`. doc 13 §13 adds the currency/FX
refs and the resolved sleeve amounts. `test_the_allocation_block_uses_canon_field_names_verbatim`
pins the exact key set.

**The amounts are copied, never recomputed.** `allocation_provenance_from_derived` projects
the frozen `PortfolioAllocationPlanRevision.derived_amounts` payload
(`allocation_plan.py:380`) — the same figures the user previewed. Mutation **M10** (reading
`capital_available` where `initial_capital` belongs) is killed.

**Independent mode is explicit.** doc 13 §13 allows a null revision id but requires
`enabled=false` to be stated; an absent block would read as "unknown", not "off"
(`independent_allocation_provenance`, `test_independent_mode_states_enabled_false_explicitly`).

### The gap this closes, reproduced before any code was written

`validate_allocation` already computes every canon-required figure and
`_resolve_allocation` (`readiness_check.py:846`) **discards it** — the returned `_derived` is
never used. A probe on the doc 13 §14 test 10 fixture (10,000 USDT, reserve 10 %, shares
40/35/15) produced:

```
DerivedAmounts: reserved_cash 1000.00 · capital_available 9000.00 ·
                sleeves 3600.00 / 3150.00 / 1350.00 · unallocated 900.00
manifest['capital_execution'] keys: [config, config_hash, enabled, plan_id, plan_revision_id]
'initial_sleeve_capital'            anywhere in the manifest JSON: False
'engine_allocation_policy_version'  anywhere in the manifest JSON: False
```

`test_doc13_test10_sleeve_amounts_match_the_shipped_preview_exactly` proves parity by
**calling** `validate_allocation` and `build_sleeve_plan`, not by restating their arithmetic.

---

## 3. Finding: preview and execution round the same sleeve differently

`allocation.rules._money` quantizes with **ROUND_HALF_UP** (`rules.py:50`);
`portfolio_ledger.MONEY_ROUNDING` is **ROUND_HALF_EVEN** (`portfolio_ledger.py:107`). At a
half-cent tie they disagree:

| capital | reserve | share | preview (frozen) | executed (exact) | executed (HALF_EVEN) |
|---|---|---|---|---|---|
| 1000.10 | 0 % | 50 % | `500.05` | `500.050000` | `500.05` |
| 1000.10 | 0 % | 25 % | **`250.03`** | `250.025000` | **`250.02`** |

doc 13 §13 forbids exactly this (*"float rounding ile manifest/preview mismatch üretme"*), and
**no canon rule picks a winner**. Nothing is invented here: the manifest carries the frozen
preview amount, and `sleeve_amount_divergences()` **reports** the disagreement per entry
(`SLEEVE_AMOUNT_DIVERGENCE`) instead of silently preferring one side.
`test_the_half_cent_tie_divergence_is_reported_not_silently_resolved` pins both numbers;
mutation **M5** (suppressing the report) is killed.

> **Open item for the maintainer.** Which quantization is canonical for
> `initial_sleeve_capital` is a product decision. Until it is answered, a tie leaves a
> 0.005 discrepancy between the number the user was shown and the number the ledger will
> size against. It is disclosed, not resolved.

---

## 4. Ledger artifact reference and checksum

`ledger_artifact_ref()` reuses the **shipped** `artifacts.compute_artifact_checksum` with
`ArtifactType.EQUITY_CURVE` and `ARTIFACT_CHECKSUM_SCHEMA_VERSION = "artifact-checksum-v1"`
— not a second hashing scheme — so a manifest reference and a persisted
`result_artifact_checksum` row are verifiable against each other. The expectation in
`test_the_ledger_artifact_checksum_is_the_shipped_artifact_checksum` is *produced by calling
that function*, never a pasted digest.

`ledger_equity_rows` emits `t_ms` for every point **including the seed point** (whose `t_ms`
is `None`), so a series that gains a seed cannot collide with one that never had it
(`test_the_seed_point_is_part_of_the_checksummed_series`; mutation **M6** killed). A run with
no equity points carries `ledger_artifact = null` rather than a fabricated empty reference.

---

## 5. Attribution reconciliation evidence

### The gap, reproduced first

`PortfolioLedger.attribution` books the realised half per item and reconciles by
construction. The probe confirmed the identity holds (`482.50 == 482.50`) **and** that:

```
ItemAttribution has an 'unrealized' field? False
PortfolioValuation fields: [t_ms, equity, gross_exposure, net_exposure,
                            gross_exposure_percent, unrealized_pnl,
                            marked_gross_exposure, marked_net_exposure, unmarked_items]
  -> per-item unrealised breakdown present? False
```

So a per-item breakdown could not be reconciled against a **marked** portfolio total.

### The decomposition, and why it is this one

`CONTRIBUTION_METHOD = "additive_pnl_decomposition"`, versioned by
`ATTRIBUTION_POLICY_VERSION = "portfolio-attribution-v1"`:

```
net_realized_i      = realized_pnl_i − fees_i − funding_i − other_costs_i
total_contribution_i= net_realized_i + unrealized_i
Σ net_realized_i        == equity        − pool_initial      (exact, residual 0)
Σ total_contribution_i  == marked_equity − pool_initial      (exact, residual 0)
```

A **leave-one-out marginal is not derivable from one shared-clock replay**: removing an item
changes every sibling's sleeve capacity, solvency headroom and arbitration outcome from that
tick onward. The sequential path can fold one only because its items never interacted
(`portfolio._contribution_block`). Canon defines no marginal formula for the shared clock, so
none was invented — `COUNTERFACTUAL_MARGINAL_STATUS =
"not_derivable_without_re_simulation"` records the omission in the artifact itself.

`realized_residual != 0` **raises** `AttributionResidualError` rather than being reported as a
tolerance: that identity is guaranteed by the ledger, so a mismatch is a defect. Mutation
**M1** (downgrading the raise) is killed.

### Missing marks are disclosed, never imputed

An open position with no usable mark makes that item's `unrealized` **`None`**, lands it in
`unmarked_items`, and sets `marked_reconciled` to `None` — an unknown, not a failure. The
realised identity still holds and is still reported. Modül 12 §9 forbids fallback; mutation
**M2** (turning a missing mark into `0`) is killed.

### Correlation parity

`attribution.pearson` is numerically identical to the shipped sequential
`portfolio._pearson`, and the parity test **calls the shipped function** over five fixtures
including the `n<2` and zero-variance cases. `contribution_correlation` reuses the shipped
key names, 4-dp cell formatting and strict-upper-triangle average, so the two eras read alike.
The series is per-tick **deltas**, not levels — a cumulative series would mostly measure a
shared trend.

---

## 6. Legacy compatibility and the migration decision

**Decision: no migration, no backfill, no rewrite.**

- No persisted Result is mutated, re-run or re-interpreted (ADR 0002 §10.4, doc 15 §3.2).
  `test_labelling_does_not_rewrite_the_immutable_artifact` reads a Result twice and asserts
  the stored diagnostics blob is byte-identical afterwards.
- The new parser understands both shapes. `resolve_portfolio_simulation_mode` classifies a
  Result from its **own** pinned manifest + **own** pinned diagnostics:

  | evidence | mode |
  |---|---|
  | pinned `portfolio_simulation.policy_versions.portfolio_manifest_version` | `unified_clock` |
  | `warnings` contains `portfolio_curve_sequential_not_unified_clock` | `legacy_sequential` |
  | `engine_kind == "v1_bar_replay"`, or `composition.strategy_count <= 1` | `single_item` |
  | anything else | `unknown` |

- **`unknown` is a real answer.** A Result whose diagnostics were not retained is *not*
  assumed to be a sequential fold — absence of evidence is not evidence. Mutation **M7**
  (defaulting to legacy) is killed.
- **The live flag cannot re-label history.** The resolver never reads
  `SHARED_ALLOCATION_STATUS`;
  `test_flipping_the_live_capability_flag_cannot_relabel_a_stored_result` flips it to
  `active_v1` and re-classifies the same inputs, and
  `test_the_resolver_reads_nothing_beyond_its_two_arguments` asserts the module source
  contains no `AsyncSession`, no `repositories` import and no `await`.
- `LEGACY_SEQUENTIAL_RESULT_NOTE` was defined in `allocation/capability.py:138` and **never
  consumed** by anything. ADR 0002 §10.4 requires exactly that label at read time; it is now
  wired in, reused verbatim rather than copied.

### Both read surfaces, one rule

The Result **detail** (`GET /backtest-results/{id}`) and the Results **History** index
(`GET /backtest-results`) both return `portfolio_simulation`, and both call
`domain.backtest.portfolio_mode` rather than re-implementing the classification — so the list
and the detail cannot drift apart about the same Result
(`test_the_history_index_labels_each_row_from_its_own_evidence` asserts the two payloads are
equal). The index matters because it puts Results side by side: a sequential fold's drawdown
and a unified valuation's drawdown are different quantities, and listing them without saying
so is misleading.

**No N+1.** The index loads the markers for a whole page in **two batched `IN (...)` reads**
(`bt_repo.get_portfolio_mode_markers`), mirroring the existing `_load_digests` /
`_load_summaries` pattern, and extracts only the JSONB paths it needs — never a per-row full
manifest or full diagnostics blob, which are two of the largest columns in the schema.
`test_the_history_index_reads_the_modes_in_a_bounded_number_of_queries` wraps the repository
call and asserts it fires exactly **once** per page.

### Finding: a single-item Result was indistinguishable from an undiagnosed one

Discovered by a failing integration test, not by inspection. The single-item bypass
(`execution/output.py:369`) emits **no** `composition` block at all, so `strategy_count`
alone could not tell "one item ran" from "diagnostics were never retained". The engine's own
`engine_kind` marker (`"v1_bar_replay"` vs `"v1_bar_replay_composition"`) resolves it; both
values are pinned and engine-authored.

---

### Export: deliberately unchanged

`POST /backtest-results/{id}/exports` is **not** touched. An export is a copy of the
immutable artifact rows, and its integrity contract is
`compute_export_checksum(export_type, fmt, schema_version, source_manifest_hash, rows)`
(`domain/backtest/export.py:79`). Injecting a *derived, read-time* label into that payload
would change the checksum of every export and make the export schema depend on a
classification that is not part of the artifact. The provenance an export needs is already
there: it pins `source_manifest_hash`, and that manifest is exactly what
`resolve_portfolio_simulation_mode` reads. So the mode stays a read-time label on the two
read surfaces, and `EXPORT_SCHEMA_VERSION` does not move. Existing export tests are
unmodified and green.

---

## 7. `ENGINE_VERSION` decision — **no bump in this slice**

ADR 0002 §10.3 schedules the bump for the containment lift. Evaluated explicitly:

- **Executed behaviour is unchanged.** No production code path calls the new modules; the
  engine, the fill model, the sizing chain and the sequential fold are untouched.
- **A bump would be a gratuitous regression.** `execution_key` is derived from
  `execution_content` including `engine_version` (`manifest.py:228-239`), so bumping shifts
  the namespace and makes **every** existing Result non-reusable for an idempotent re-RUN —
  for a change that alters no number.
- **Therefore the 46 golden digests must all be unchanged, including
  `contract.execution_key`.** That is an assertion of this slice, not a hope:
  `test_no_portfolio_manifest_field_ships_in_the_shipped_manifest_yet` asserts the shipped
  `manifest.py` still reads `ENGINE_VERSION = "backtest-engine-v18-gap-adjusted-stop-fill"`
  and contains none of the new field names, and the four pre-existing
  `test_no_*_field_ships_in_the_manifest_yet_and_the_engine_version_stands` tests remain green.

**Tripwire.** The policy versions are pinned by name and value in
`test_every_policy_knob_is_pinned_in_the_manifest`. Changing any of them fails that test,
which is the moment to decide whether the change warrants an `ENGINE_VERSION` bump. Once the
unified path genuinely executes, ADIM 20 bumps to
`backtest-engine-v18-unified-clock-portfolio` and moves these versions into
`execution_content`.

**Golden baseline:** `backend/tests/unit/engine_golden_digests.json` is **unmodified**
(`engine_version: backtest-engine-v18-gap-adjusted-stop-fill`, 46 digests).

---

## 8. Honest boundaries

1. **The unified phase loop does not exist.** ADR §12's ADIM 18 (`run_portfolio`) was never
   written — PR #575 landed arbitration instead. Nothing produces a unified Result today, so
   `PORTFOLIO_MODE_UNIFIED_CLOCK` is **unreachable in production**; it is exercised only by
   tests using a synthetic pinned manifest. That is deliberate — the parser must accept the
   shape before the producer exists — but it must not be read as "unified runs work".
2. **The new manifest section is not wired into the shipped manifest.** `manifest.py` is
   untouched; wiring is ADIM 20's job together with the containment lift.
3. **`portfolio_simulation` is not published in the OpenAPI schema.** The route
   `GET /backtest-results/{id}` returns a bare `dict[str, Any]`
   (`apps/api/routes/backtest.py:164-168`), so the whole Result-detail body — not just this
   field — is absent from `docs/openapi.json`. This is a pre-existing O-30-shaped gap;
   retyping that endpoint is a separate slice. The snapshot is therefore unchanged, and the
   drift guard stays green while the contract stays invisible. **Recorded, not hidden.**
4. **The half-cent sleeve divergence (§3) is disclosed, not fixed** — it needs a product
   decision.
5. **ADR 0002 is still `Proposed`** and its §16 requires approval before implementation.
   ADIM 15/16/17/18 and now 19 have all landed without a recorded approval, and §12's
   numbering still does not match what shipped. Both gates remain open.
6. **`ItemAttribution` is a mutable dataclass** owned by the ledger; `attribute()` only reads
   it. Nothing in this slice makes it immutable.

---

## 9. Mutation evidence

Ten deliberate defects were injected into the new code one at a time; the targeted suites
were re-run for each and the source restored afterwards. **All ten were killed.**

| id | defect | killed by |
|---|---|---|
| M1 | reconciliation residual no longer raises | `test_realised_rows_sum_to_the_portfolio_with_zero_residual` |
| M2 | unmarked position's unrealised becomes `0` | `test_an_unmarked_position_leaves_unrealised_unknown_rather_than_zero` |
| M3 | row order drops `pin_ordinal` | `test_rows_are_ordered_by_pin_ordinal_then_item_id` |
| M4 | display labels enter the hashed content | `test_the_manifest_identity_ignores_display_labels` |
| M5 | sleeve divergences always empty | `test_the_half_cent_tie_divergence_is_reported_not_silently_resolved` |
| M6 | checksum drops `t_ms` | `test_the_seed_point_is_part_of_the_checksummed_series` |
| M7 | `unknown` defaults to `legacy_sequential` | `test_a_result_with_no_retained_diagnostics_is_unknown_not_legacy` |
| M8 | a stale warning outranks the pinned manifest | `test_a_half_written_unified_section_does_not_claim_unified` |
| M9 | comparability always `true` | `test_the_context_states_comparability_rather_than_leaving_it_to_be_inferred` |
| M10 | allocation amount read from the wrong key | `test_doc13_test10_sleeve_amounts_match_the_shipped_preview_exactly` |

M3's first run reported *pattern not found* (the harness literal was stale after
`ruff format` reflowed the line) — it was re-applied against the real source text and killed.
A "pattern not found" is a stale harness, **not** a passing result, and is reported as a
survivor by design.
