<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# Research Data point-in-time — consumption map, parity matrix and no-lookahead evidence

**Slice:** ADIM 13 — Research Data point-in-time and Agent/Run parity
**Base:** `origin/main` @ `c610600` (PR #553 + #554 merged)
**Code:** `backend/tests/unit/test_research_point_in_time.py` (27 scenarios)
· `backend/tests/integration/test_research_point_in_time_parity.py` (13 passing + 4 `xfail(strict)`)
**Narrow production fix:** `domain/research_data/time_policy.py::ensure_time_policy_mutable`
(one call site: `application/commands/research_data.py::set_time_policy`)

> **STATUS UPDATE (2026-08-06, later slice).** Everything below is the ADIM 13 record and is
> left verbatim — the probe transcripts are the evidence. Two of the four discrepancies have
> since been FIXED: **D-2 (#556, research half)** and **D-3 (#557)**. The gateway now routes
> every research member through `jobs/research_data.py::admit_bundle_member`, the same
> admission gate the compilers use, and resolves the Feature-Input-Only precondition with
> `has_approved_feature_definition` instead of reading the caller's claim. The file is now
> **16 passing + 1 `xfail(strict)`** (#558 only). Still open: **#558** (product decision) and
> the **market half of #556** (`data_bundle.resolve` checks market-revision existence only).

---

## 1. The question this slice answers

Does a Research Data revision carry the **same canonical point-in-time truth** into an
Agent research bundle as it does into a Backtest execution bundle?

The answer is *mostly yes, with four confirmed asymmetries* — one of which was fixable
inside the shared time-policy layer and was fixed; three of which live outside it and are
proved by `xfail(strict=True)` tests anchored to open issues. Nothing was fixed on a
suspicion: every defect below was **reproduced against a real database on `c610600`**
before it was written down.

---

## 2. Consumption path map

Four surfaces can pin a research revision. They are compiled by four different pieces of
code, which is why parity has to be *proved* rather than assumed.

| # | Surface | Entry point | Reachable as |
|---|---|---|---|
| **A1** | Agent tool gateway | `application/jobs/agent_tools.py:376` `_handle_data_bundle_resolve` | `data_bundle.resolve` tool (`ToolName.DATA_BUNDLE_RESOLVE`) |
| **A2** | Agent bundle compiler | `application/jobs/research_data.py:431` `compile_agent_data_bundle` | `POST /research-datasets/bundles/agent` |
| **B1** | Evidence bundle compiler | `application/jobs/research_data.py:464` `compile_backtest_evidence_bundle` | `POST /research-datasets/bundles/backtest-evidence` |
| **B2** | Run manifest | `application/commands/backtest_run_context.py:344` `_research_entries` | every `request_backtest_run` |

**A1 and A2 are two independent implementations of the same concept** and enforce different
rule sets (§5, rows L-1 and S-3). A1 has no in-`src` caller — only the tool surface and
tests reach it.

### What each surface reads

| Field | A1 gateway | A2 agent bundle | B1 evidence bundle | B2 run manifest | Execution (`queries/funding.py`) |
|---|---|---|---|---|---|
| `revision_id` (exact pin) | ✔ | ✔ | ✔ | ✔ | ✔ |
| `content_hash` | — | ✔ pinned | ✔ pinned | ✔ pinned **and** compared | ✔ compared |
| `usage_scope` | ✔ gated | ✔ recorded, not gated | ✔ gated | ✔ recorded | ✔ gated |
| `revision_state` | **✗** | ✔ consumable-only | ✔ must be `approved` | ✔ recorded | ✔ must be `approved` |
| root `deletion_state` | **✗** | ✔ | ✔ | (manifest liveness gate) | (manifest liveness gate) |
| `available_time_policy` / `available_delay_seconds` | **✗** | **✗** | validated, **not pinned** | ✔ pinned | ✔ read live |
| `event_time_semantics` | **✗** | **✗** | **✗** | ✔ pinned | ✗ never read |
| `source_timezone_mode` / `_iana` | **✗** | **✗** | **✗** | ✔ pinned | ✔ read live (`revision_source_zone`) |
| `instrument_mapping_ref` | **✗** | **✗** | **✗** | ✔ pinned | ✔ gated |
| `category_key` | **✗** | **✗** | **✗** | ✔ pinned | ✔ must be `funding_rate` |

### The engine's single research feed

The V1 engine consumes **exactly one** research feed — the pinned funding-rate source:

```
config.data.funding  →  queries/funding.py::resolve_funding_schedule
                     →  domain/backtest/funding.py::build_funding_schedule   (resolve_available_at per row)
                     →  domain/backtest/execution/costs.py::due_funding_charges
                     →  domain/research_data/time_policy.py::is_eligible_for_decision   ← the ONE gate
```

`grep -rn "research" domain/backtest/` hits exactly four things: `funding.py` (the schedule
builder), `execution/costs.py:39` (the eligibility gate), `history.py` (read-back of the
manifest snapshot — never the live root), and `result_visibility.py` (an unrelated ACL that
happens to say "Agent research"). **No research value reaches indicators, filters or
signals**, and `engine.py`'s only research-related import is `funding.py`. This is stated as
an honest boundary, not a defect — see §6.

---

## 3. Time vocabulary: what exists, what does not

| Concept | Status on `c610600` |
|---|---|
| `event_time` | Native-schema column, resolved by convention (`EVENT_TIME_COLUMN_CANDIDATES`). Normalized to UTC **at ingest** under the declared zone. |
| `available_time` | **Derived, never stored per record.** Computed by `resolve_available_at(event_at, policy, delay)` at schedule-build time. |
| `available_time_policy` | Revision-level: `same_as_event_time`, `fixed_delay`, `provider_publish_timestamp`, `custom_documented_rule`. The last two **fail closed** on the funding path — the generic reader has no per-record publish/custom input and refuses rather than degrading to event time. |
| `ingestion_time` (per record) | **Does not exist.** Only `created_at` on the revision row. "Late arrival" is therefore modelled purely by `available_at` — which is the correct axis for eligibility. |
| `timezone` | `source_timezone_mode` + `source_timezone_iana`. `exchange` mode carries no identifier → `source_zone=None` → naive cells are **unresolvable, never assumed UTC**. |
| `revision` | Immutable id; `content_hash` covers the **payload bytes only**, not the timing metadata. |
| `interval` / cadence | `frequency_policy` is declared and pinned in the manifest but is **not enforced** against the records. Doc 12 §5.2 already says frequency is not a coverage guarantee. |
| `as-of` | `is_eligible_for_decision(available_at, decision_time, has_instrument_mapping)` — the single gate, inclusive at the boundary. |
| `tolerance` / max staleness | **Does not exist.** An arbitrarily old eligible record stays eligible forever; there is no maximum-age bound. Canon declares none either. |
| `missing` | Unparseable event time or non-finite rate → the row **drops**; an all-dropped source **fails closed**. |
| `forward-fill` | **Not implemented anywhere.** Doc 12 §8.4 rule 5 ("only when a field definition allows it") is therefore satisfied vacuously — there is no carry-forward code that could fire silently. |
| `stale` | Revision lifecycle only (`deprecated` / `approval_revoked`); no data-level staleness concept. |
| `late arrival` | Expressed as `available_at > decision_time`; the record simply never fires, and replaying the same bar yields the same answer. |

---

## 4. Evidence matrix

Legend — **PROVEN**: a passing test locks it. **CHARACTERIZED**: the behavior ships and is
pinned by a test, but canon declares no rule, so the test records rather than endorses it.
**DISCREPANCY**: canon and code disagree; the test states canon and is `xfail(strict=True)`.

### T — time model

| # | Scenario | Canon | Verdict | Evidence |
|---|---|---|---|---|
| T-1 | Event time is never a proxy for usable time (10:15 event + 2m delay is ineligible at 10:15, eligible at 10:17) | §8.4 r2, §14 "Time safety" | **PROVEN** | `test_a_fixed_delay_source_is_ineligible_at_its_own_event_time` |
| T-2 | `available_at == decision_time` is **included** | §8.4 r2 (`<=`) | **PROVEN** | `test_a_record_available_exactly_at_the_decision_time_is_eligible` |
| T-3 | `available_at = t + 1 **microsecond**` is excluded; ±1 µs flips it both ways | §8.4 r2 | **PROVEN** (pre-existing coverage stopped at 1 second) | `test_one_microsecond_after_the_decision_time_is_not_eligible`, `test_the_microsecond_boundary_is_the_only_difference_either_side` |
| T-4 | Two records sharing one `available_at` both fire, exactly once each — no silent dedupe | §8.4 r3 | **PROVEN** | `test_two_records_sharing_one_available_at_both_fire_exactly_once` |
| T-5 | A late-arriving record never fires for an earlier decision time, and re-replay is identical | §8.4 r2 | **PROVEN** | `test_a_late_arriving_record_never_fires_for_an_earlier_decision_time` |
| T-6 | An approved revision's available-time policy cannot be rewritten in place | §11, §14 "Revision immutability" | **FIXED this slice** (was a live defect) | `test_an_approved_revision_cannot_be_retimed_in_place`, `test_the_canonical_recovery_is_a_new_revision_that_leaves_v1_intact` |
| T-7 | A bundle pins the time policy it was compiled under | §9.1, §9.2 `available_time_policies[]` | **DISCREPANCY → #558** | `test_both_bundles_pin_the_available_time_policy` (`xfail`) |
| T-8 | A non-UTC declared zone reaches the funding schedule; a naive row under an unresolvable zone drops instead of being read as UTC | §5.2, §8.4 r1 | **PROVEN** (every prior funding test passed `UTC`) | `test_a_naive_new_york_event_time_lands_on_the_true_utc_instant`, `test_a_naive_row_under_an_unresolvable_zone_drops_instead_of_assuming_utc` |
| T-9 | DST **fold** (ambiguous) and DST **gap** (nonexistent) local wall clocks | canon **silent** | **CHARACTERIZED → #559** | `test_an_ambiguous_dst_fold_string_resolves_to_the_first_occurrence`, `test_a_nonexistent_dst_gap_string_is_accepted_not_rejected` |
| T-10 | The ingest normalizer and the funding reader — two separate implementations — agree on every DST case | (invariant, not canon) | **PROVEN** | `test_the_ingest_normalizer_and_the_funding_reader_agree_on_every_dst_case` |
| T-11 | A resolved available time can never precede its event time | §8.4 | **PROVEN** (pre-existing + re-proved through the builder) | `test_a_resolved_available_time_can_never_precede_its_event_time` |

**T-9 detail (the behavior that ships).** Declared zone `America/New_York`, offset-less cell:

| case | source cell | resolves to | flagged |
|---|---|---|---|
| fold — 01:30 occurs twice (EDT, then EST) | `2024-11-03T01:30:00` | `2024-11-03T05:30:00Z` (the **first**/EDT occurrence) | no |
| gap — 02:30 never occurred | `2024-03-10T02:30:00` | `2024-03-10T07:30:00Z` | no |

Both readers use `datetime.replace(tzinfo=zone)`, so `fold` defaults to `0`. Consequence: the
**second occurrence of a folded hour is unaddressable from a source file** — an offset-less
string cannot express `fold=1`. Deterministic and reproducible, but undeclared.

### S — usage scope (doc 12 §9.3)

| # | Scenario | Verdict | Evidence |
|---|---|---|---|
| S-1 | `agent_research_only` → allowed for Agent research, forbidden for the evidence bundle, rejected at `policy_scope="execution"` | **PROVEN** on all three surfaces | `test_agent_research_only_is_allowed_for_research_and_forbidden_for_execution` |
| S-2 | `feature_input_only` **without** an approved definition → blocked from the evidence bundle, still allowed for Agent research | **PROVEN** | `test_feature_input_only_without_an_approved_definition_is_blocked` |
| S-2b | `feature_input_only` **with** an approved definition → admitted (the required path actually opens the gate) | **PROVEN** (positive path had no coverage) | `test_feature_input_only_with_an_approved_definition_enters_the_evidence_bundle` |
| S-3 | The Feature-Input-Only gate is decided **server-side**, not from a caller-supplied boolean | ~~**DISCREPANCY → #557**~~ → **FIXED**, marker removed | `test_the_agent_tool_gateway_resolves_the_feature_definition_server_side` (now passing) |

### L — lifecycle (doc 12 §11, §14)

| # | Scenario | Verdict | Evidence |
|---|---|---|---|
| L-1 | A soft-deleted root is blocked from **new** bundle use | **PROVEN on A1/A2/B1** (was a DISCREPANCY for A1 → #556, now **FIXED**) | `test_a_soft_deleted_root_is_blocked_from_both_bundle_compilers` + `test_the_agent_tool_gateway_blocks_a_soft_deleted_root` (both passing) |
| L-2 | A `deprecated` / `approval_revoked` revision is blocked from **new** bundle use | **PROVEN on A1/A2/B1** (was a DISCREPANCY for A1 → #556, now **FIXED**) | `test_a_non_consumable_revision_is_blocked_from_both_bundle_compilers` + `test_the_agent_tool_gateway_blocks_a_deprecated_revision` (both passing) |
| L-3 | A historical correction leaves the previously pinned revision **and its compiled bundle** byte-identical | **PROVEN** | `test_the_canonical_recovery_is_a_new_revision_that_leaves_v1_intact` (recompiled `bundle_hash` and `members` are equal) |
| L-4 | The freeze does not break the ordinary creation flow (a draft is still editable) | **PROVEN** | `test_a_pre_approval_revision_may_still_be_retimed_through_the_command` |

### P — exact pins (doc 12 §9.1 "'Latest approved' dynamic resolution forbidden")

| # | Scenario | Verdict | Evidence |
|---|---|---|---|
| P-1 | A1, A2 and B1 pin the same revision id; A2 and B1 pin the same `content_hash`; a newer revision under the same root moves none of them, and the recompiled `bundle_hash` is unchanged | **PROVEN** | `test_every_bundle_surface_pins_the_same_exact_revision_identity` |
| P-2 | B1 (evidence bundle) and B2 (Run manifest) agree on revision id, content hash and usage scope | **PROVEN** | `test_the_run_manifest_pins_the_same_revision_identity_as_the_evidence_bundle` |
| P-3 | Funding off pins no research feed at all (an empty list, not an unresolved pin) | **PROVEN** | `test_funding_disabled_pins_no_research_feed_at_all` |

---

## 5. Confirmed discrepancies

All four were reproduced on `c610600` before being written down.

### D-1 — an approved revision could be retimed in place · **FIXED**

`set_time_policy` guarded only ownership (`ensure_can_edit_draft` checks owner/Admin, **not**
revision state), so an APPROVED revision's `available_time_policy`, `available_delay_seconds`
and source timezone could be rewritten while `content_hash` — which covers payload bytes only
— stayed identical. Because `queries/funding.py` re-reads those fields **live** at run time,
two runs pinning the same revision id could resolve different `available_at` values and book
different funding costs while presenting an identical manifest snapshot.

Probe output before the fix:

```
PROBE C1: state=approved  before=(None, None)  after=(fixed_delay, 7200)
          content_hash=b704109aaf…  (unchanged)
```

Canon: doc 12 §11 *"available-time policy change → new Research Dataset Revision. In-place
overwrite forbidden."* · §14 *"Approved v1.0 is not mutated; a v1.1 draft/analysis/revision is
created. Existing run/result stay bound to v1.0."*

**Fix (the whole of it):** `domain/research_data/time_policy.py` gains
`TIME_POLICY_FROZEN_STATES` + `time_policy_is_frozen` + `ensure_time_policy_mutable`, called
once from inside `set_time_policy`'s idempotent body (inside, per the 2a lesson, so a
completed-key replay returns its cached reference instead of re-judging an advanced state).
Frozen = `approved` / `approval_revoked` / `deprecated`; an unreadable state fails closed as
frozen. Result: 409 `LIFECYCLE_BLOCKED` with `field_path="available_time_policy"`,
`suggested_action="create_new_revision"`, `retryable=false`.

The canonical recovery already existed and is unchanged: `create_research_dataset_revision`
appends a fresh DRAFT and advances the head, and the policy is set there.

### D-2 — `data_bundle.resolve` reads no lifecycle state · **#556** · research half **FIXED**

A soft-deleted root and a `deprecated`/`approval_revoked` revision both pin successfully
through the Agent **tool** surface, while the Agent **bundle compiler** blocks both:

```
data_bundle.resolve        -> {'status': 'succeeded', 'research_revision_ids': ['rrev_…']}
compile_agent_data_bundle  -> NotFoundError: Research revision 'rrev_…' is not available.
```

Same handler, secondary defect: the market half checks existence only while its docstring
claims it pins *"approved Market"*.

**Fix (later slice).** The research half now calls
`jobs/research_data.py::admit_bundle_member` — the same gate `compile_agent_data_bundle`
and `compile_backtest_evidence_bundle` were refactored onto — so a soft-deleted root and a
non-consumable revision are refused a NEW bundle on the tool surface too, as a recorded
`rejected` / `RESEARCH_INPUT_BLOCKED` outcome rather than a crash. The gateway calls it with
`for_execution=False` on both scopes on purpose: it pins a *context* manifest, not a
`BacktestEvidenceBundle`, so it does not inherit the evidence compiler's ACTIVE+APPROVED and
time-policy preconditions (a landed acceptance test pins a draft revision into an
execution-scope context bundle, and the run re-derives those itself).
**The market half is NOT fixed** — the docstring no longer claims "approved Market", and the
ACTIVE-root + APPROVED-revision gate for a pinned market revision stays open on #556.

### D-3 — the Feature-Input-Only gate is decided from client input · **#557** · **FIXED**

`agent_tools.py:396` reads `has_approved_feature_definition` **from the request body** and
feeds it straight into `ensure_allows_evidence_bundle`; the twin resolves it with a real
`SELECT` (`jobs/research_data.py:488`). With no `ResearchFeatureDefinition` row at all:

```
data_bundle.resolve(has_approved_feature_definition=True)  -> succeeded
compile_backtest_evidence_bundle                           -> FieldMeaningInsufficient
```

Mitigating context (why not CRITICAL): the engine does not execute this pin. Ready Check
(`validators.py:782`) and the worker gate (`queries/funding.py:59-93`) both re-derive scope
and state from the database, so the false pin corrupts recorded Agent provenance rather than
an executed run.

**Fix (later slice).** `has_approved_feature_definition` (the private helper, published) is
now called by BOTH surfaces, and the gateway no longer reads
`research_revisions[].has_approved_feature_definition` from the request at all — the field is
simply ignored, so a caller asserting a precondition that does not hold gets a recorded
`rejected` outcome instead of a pin. The `ensure_allows_evidence_bundle` rule itself stayed
where it always was, in `domain/research_data/usage_scope.py`; only its *input* moved from
the caller to the database.

### D-4 — no bundle pins the time policy · **#558**

Doc 12 §9.1 requires the Agent Data Bundle to pin *"exact revision IDs, usage scope **and time
policy**"*; §9.2 names `available_time_policies[]` in the `BacktestEvidenceBundle` field list.
Neither bundle member carries any time field, so `bundle_hash` is **invariant** under a
time-policy change and a bundle cannot attest, from its own contents, which availability rule
it was compiled under. The Run manifest already pins all of it, so the two execution-evidence
surfaces disagree. (Four further §9.2 fields — `feature_definition_revision_ids[]`,
`instrument_mapping_revision_ids[]`, `alignment_policy_versions[]`,
`missing_and_stale_policies[]` — are absent for the same reason and are folded into #558.)

D-1's fix removes the *reachable drift*; the *missing pin* is what #558 tracks.

---

## 6. Honest boundaries

* **The engine consumes one research feed.** Funding rate only. Research Data is not an
  indicator, filter or signal input in V1. Every point-in-time proof about *execution* is
  therefore a proof about the funding path; nothing here claims a research feature pipeline
  exists. No fake join was written to make the matrix look fuller.
* **§8.4 rule 3's "select the latest eligible record" is unexercised.** It describes reading a
  *value as of t*; the funding consumer applies each *event* once (`due_funding_charges`
  advances a monotonic cursor). Both are correct for their own semantics, but the
  latest-value-as-of join has no implementation because nothing reads a research *level*.
* **`event_time_semantics` is pinned but never enforced.** The Run manifest records it;
  no code on the backtest path branches on it. Ready Check does not check it either.
* **No as-of tolerance exists.** An eligible record never expires. Canon declares no bound,
  so none was invented.
* **The `verified` state stays retimable.** D-1's freeze starts at `approved`. Doc 12 §5.2
  says a rule change "invalidates timing validation and any prior analysis", which implies a
  `verified` revision should drop back to needing re-analysis when retimed — that reset is
  **not** implemented and was out of this slice's scope.
* **A2 does not validate the time policy, by design.** Doc 12 §9.3 admits every scope into
  Agent research and an Agent bundle performs no as-of resolution, so an incomplete policy
  does not make it unusable. Only B1, whose members are replayed against decision times,
  requires a resolvable rule. This asymmetry is asserted as intended
  (`test_the_agent_bundle_does_not_validate_the_time_policy_by_design`), not filed as a defect.
* **A1 has no in-`src` caller.** `data_bundle.resolve` is reachable only through
  `dispatch_tool_call` from the tool surface (plus three test files). The autonomous loop
  never asks for it: `application/jobs/agent_executor.py` dispatches `backtest.ready_check`
  (`:413`), `backtest.request` (`:470`), `result.query` (`:550`) and `artifact.create`
  (`:584`) — and nothing else. That bounds #556/#557's blast radius today; it does not
  close them, because the tool remains callable by any Agent-role principal.
* **Frontend:** untouched. No DTO changed, no route, react-query key, OCC token or
  Idempotency-Key was modified.
