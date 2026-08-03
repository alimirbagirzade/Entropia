# I-17 — Acceptance test ID traceability

**Slice:** `feat/t2-acceptance-id-traceability` · **Measured:** 2026-07-28 ·
**Baseline commit:** `eff8ffe` (origin/main)

> **Follow-up applied 2026-07-29** (`feat/i17-rf06-and-map-rename`): RF-06 gained a
> dedicated test and this file was renamed from `acceptance_id_traceability.md`.
> See **§G**. Sections §A–§F are the original 2026-07-28 record and are unchanged.

Reproduce every number below with:

```bash
python3 docs/audit/acceptance_id_scan.py
```

---

## §0. What this document is — and what it is NOT

`docs/spec/NN_*` §"Acceptance Tests" tables are the product's acceptance contract.
This audit asks one narrow question: **can a reader get from an acceptance ID to a
test that claims it?**

> **A zero-reference ID does NOT mean the behaviour is untested.**
> It means nothing in the suite *says* which test covers it. Most of the IDs closed
> in this slice were already covered — by tests that simply never named the ID.
> This is a traceability gap, not a coverage gap. The two are reported separately:
> §D lists IDs with no tag, §E lists the ones that are genuinely *uncovered*.

**Scan rule.** Only test files count — `backend/tests/**/*.py` and
`frontend/src/**/*.test.*`. Production-source comments are deliberately excluded: a
tag in `frontend/src/lib/tradeLog.ts` documents the implementation, it is not
evidence of a test. (The pre-slice baseline looked better than it was for exactly
this reason — several TL/AOS "hits" lived only in page and lib comments.)

---

## §A. Result

| Page | Prefix | Before | After | Untraced now |
|---|---|---|---|---|
| 02 Add Strategy / Strategy Details | `AT` | 9/25 | **20/25** | AT-04, AT-06, AT-07, AT-21, AT-24 |
| 03 Add Outsource Signal | `AOS` | 1/21 | **18/21** | AOS-12, AOS-16, AOS-20 |
| 04 Trading Signal | `TS` | 0/21 | **18/21** | TS-10, TS-16, TS-20 |
| 05 Trade Log | `TL` | 8/23 | **22/23** | TL-18 |
| 07 Pre-Check | `PC` | 4/22 | **14/22** | PC-01, PC-02, PC-14, PC-15, PC-16, PC-18, PC-19, PC-22 |
| 10 Rationale Families | `RF` | 12/18 | **16/18** | RF-13, RF-18 |
| **In-scope subtotal** | | **34/130** | **108/130** | 22 |
| 14 Backtest Ready Check | `RC` | 13/18 | 13/18 | RC-11…RC-15 |
| 16 Results History | `RH` | 2/16 | 2/16 | 14 IDs |
| 18 Analysis Lab | `AL` | 16/18 | 16/18 | AL-13, AL-15 |
| 21 User Manual | `UM` | 13/18 | 13/18 | UM-05, UM-12, UM-13, UM-14, UM-17 |
| 22 Future Dev | `FD` | 10/15 | 10/15 | FD-03, FD-06…FD-09 |
| **Total** | | **88/215** | **162/215** | 53 |

Docs 01, 11, 12, 13, 15, 17, 19, 20 publish acceptance tables with **no ID column
at all** and are outside this scan entirely (same structural problem as §C).

### Corrections to the brief

The brief's counts were re-derived from the repo. Three corrections:

1. **`PC-10` IS tagged** — `backend/tests/unit/test_language_detect.py:1` and
   `test_create_package_precheck_worker.py:13`. Doc 07 was 4 tagged / 18 untagged,
   not 3 / 19.
2. **`AOS-02` was NOT test-tagged.** Its only occurrence was a comment in
   `frontend/src/pages/OutsourceSignal.tsx` — production source, not a test. Under
   the scan rule above, AOS-01 was the page's only tagged ID (as the brief said),
   but for a different reason than a raw grep suggests.
3. **`TL-01`, `TL-14`, `TL-15` looked tagged to a naive grep** but only via
   `lib/tradeLog.ts` / `components/TradeLogEditor.tsx` comments. The brief's TL list
   is correct as a *test*-traceability list.

`TS-01…TS-21 = 0`, the 16 doc-02 `AT` IDs, and `RF-06/12/13/15/16/18` were all
confirmed exactly.

**AT-25 mismatch.** The brief describes AT-25 as "Agent private root edit reddi".
Doc 02 §12 AT-25 is **"Info content"** — every rendered ⓘ key must match the
catalog and no popover may silently change a field. The test written in this slice
implements the **spec's** AT-25. The behaviour the brief described is doc 02
**AT-22** (Authorization), which was already tagged in
`test_strategy_integration.py`. If a separate Agent-specific test was wanted,
that is AT-21 (Agent parity) — still open, see §E.

---

## §B. New tests written in this slice

| ID | Test | File | Verified |
|---|---|---|---|
| TL-04 | `test_ready_save_without_a_source_file_is_an_import_binding_issue`, `test_ready_save_with_a_blank_record_batch_is_an_import_binding_issue` | `backend/tests/unit/test_trade_log_config.py` | ✅ 12/12 pass |
| RF-12 | `test_strategy_without_a_rationale_family_blocks_ready_check` | `backend/tests/unit/test_readiness_validators.py` | ✅ 45/45 pass |
| RF-16 | `test_client_manipulated_delete_still_meets_the_server_guards` | `backend/tests/integration/test_rationale_persistence.py` | ⚠️ **not executed** — see §F |
| AT-25 | `gives every catalog key a non-empty title and body`, `resolves every ⓘ the strategy cards actually render`, `opening an ⓘ panel changes no form value and submits nothing` | `frontend/src/test/strategyForm.test.tsx` | ✅ 22/22 pass |

---

## §C. Docs 06 / 08 / 09 — the ID-less acceptance tables

These three pages ship acceptance tables whose first column is a **category**, not
an ID, so no test can cite them and the scanner cannot see them:

| Doc | Columns | Rows |
|---|---|---|
| 06 Add Package / Create Package | `Kategori`, `Doğrulanabilir senaryo / beklenen sonuç` | 16 |
| 08 Package Library | `Category`, `Acceptance scenario`, `Expected result` | 21 |
| 09 Embedded System Packages | `Category`, `Acceptance scenario`, `Expected result` | 20 |

**The spec files are canonical and are NOT edited.** Instead this audit assigns
**audit-local** IDs by row order. They are stable as long as the spec tables keep
their row order, and they exist so a test can cite something.

> Citation form in a test: `CP-07 (docs/audit, doc 06 row 7)`. Never write these
> into `docs/spec/`.

### C.1 — doc 06 Create Package → `CP-nn`

| ID | Category | Covering test (if any) |
|---|---|---|
| CP-01 | Canonical types | `unit/test_package_kind.py::test_legacy_types_are_rejected` |
| CP-02 | Add package derivation | `integration/test_derive_strategy_draft.py` |
| CP-03 | Use authorization | `unit/test_package_permissions.py`; `integration/test_package_sharing.py` |
| CP-04 | Request requiredness | `integration/test_create_package_persistence.py::test_description_route_skips_dependency_gate` |
| CP-05 | Runtime alignment | `unit/test_acceptance_create_package_runtime.py` *(added 2026-07-29, §H)* |
| CP-06 | Pre-Check stale | `integration/test_precheck_audit_events.py` (`precheck_stale`) |
| CP-07 | Missing ESP | `integration/test_create_package_persistence.py::test_missing_resolver_blocks_precheck_and_send` |
| CP-08 | Async resilience | `integration/test_create_package_precheck_worker.py` (durable QUEUED job) |
| CP-09 | Idempotency | `integration/test_create_package_persistence.py::test_create_draft_is_idempotent` |
| CP-10 | Revision immutability | `integration/test_create_package_revision_chain.py` |
| CP-11 | Baseline policy | `integration/test_create_package_baseline_worker.py` |
| CP-12 | Future-leak validation | `integration/test_create_package_candidate_validation_worker.py` |
| CP-13 | Approval policy | `integration/test_create_package_approve_dependency_gate.py`; `unit/test_create_package_policy.py` |
| CP-14 | Clear boundary | `frontend/src/test/createPackageClearBoundary.test.tsx` *(added 2026-07-29, §H)* |
| CP-15 | Trash / history | `integration/test_trash_page.py`; `integration/test_package_lifecycle.py` |
| CP-16 | Agent parity | `contract/test_create_package_contract.py` (agent principal) |

### C.2 — doc 08 Package Library → `PL-nn`

| ID | Category | Covering test (if any) |
|---|---|---|
| PL-01 | Canonical types | `unit/test_package_kind.py`; `unit/test_package_catalog.py` |
| PL-02 | Default list / policy | `integration/test_library_persistence.py::test_visibility_is_enforced_server_side` |
| PL-03 | Filter query | `integration/test_library_persistence.py::test_type_and_family_filters`, `::test_status_facet_and_text_filters` |
| PL-04 | External type rejection | `unit/test_package_kind.py::test_legacy_types_are_rejected` |
| PL-05 | Status separation | `integration/test_library_persistence.py::test_detail_projection_and_guards` |
| PL-06 | Metric applicability | `integration/test_acceptance_esp_package_gaps.py::test_condition_package_romad_is_not_applicable_and_nothing_can_sort_on_it` *(added 2026-07-29, §H)* |
| PL-07 | Use exact pinning | `integration/test_create_package_revision_chain.py` |
| PL-08 | Compatibility | `unit/test_readiness_validators.py` (`PACKAGE_TIMING_INCOMPATIBLE` family) |
| PL-09 | Dependency cycle | `unit/test_package_dependency_graph.py` |
| PL-10 | Foreign edit | `integration/test_library_persistence.py::test_permission_projection_on_rows` |
| PL-11 | Derive provenance | `integration/test_derive_strategy_draft.py` |
| PL-12 | Admin publish | `integration/test_package_lifecycle.py` |
| PL-13 | Non-admin publish | `unit/test_package_permissions.py` |
| PL-14 | Concurrency | `integration/test_package_lifecycle.py` (revision conflict) |
| PL-15 | Delete | `integration/test_library_persistence.py::test_soft_deleted_package_is_not_discoverable` |
| PL-16 | Restore | `integration/test_trash_page.py::test_restore_keeps_identity_marks_entry_and_audits` |
| PL-17 | Trash policy | `integration/test_trash_page.py::test_trash_surfaces_reject_non_admin` |
| PL-18 | Export | `integration/test_package_import_job.py` / `test_package_import_worker.py` |
| PL-19 | Import unresolved | `integration/test_package_import_worker.py` |
| PL-20 | Agent parity | `integration/test_gateway_parity.py` |
| PL-21 | V18 alignment | `frontend/src/test/library.test.tsx` |

### C.3 — doc 09 Embedded System Packages → `ESP-nn`

| ID | Category | Covering test (if any) |
|---|---|---|
| ESP-01 | Menu scope | `frontend/src/test/embedded.test.tsx` |
| ESP-02 | Canonical type enforcement | `unit/test_package_kind.py::test_legacy_types_are_rejected` |
| ESP-03 | V18 sample catalog | `integration/test_esp_persistence.py::test_seed_style_ta_resolvers_resolve` |
| ESP-04 | System facets | `integration/test_esp_persistence.py::test_list_filters_by_visibility_scope` |
| ESP-05 | Rationale seed | `integration/test_acceptance_esp_package_gaps.py::test_seeded_ta_resolver_family_is_active_and_binds_esp_packages_by_id` *(added 2026-07-29, §H; also doc 10 **RF-15**)* |
| ESP-06 | Resolver exact match | `integration/test_esp_persistence.py::test_resolve_returns_exact_revision_only_when_trusted` |
| ESP-07 | Name-only rejection | `integration/test_esp_persistence.py::test_resolve_signature_mismatch_and_adapter` |
| ESP-08 | Adapter rejection | `integration/test_esp_persistence.py::test_resolve_signature_mismatch_and_adapter` |
| ESP-09 | Evidence gate | `integration/test_esp_persistence.py::test_activate_without_evidence_rejected`, `::test_activate_with_empty_evidence_rejected` |
| ESP-10 | Timing integrity | `integration/test_esp_persistence.py::test_activation_blocked_when_validation_failed` |
| ESP-11 | Immutable revision | `integration/test_esp_persistence.py::test_soft_delete_preserves_revision_chain` |
| ESP-12 | Stale activation | `integration/test_esp_persistence.py::test_stale_registry_version_conflicts` |
| ESP-13 | Permission | `integration/test_esp_persistence.py::test_validation_by_non_owner_denied`; `unit/test_esp_policy.py` |
| ESP-14 | Agent parity | `unit/test_esp_policy.py` (agent principal) |
| ESP-15 | Missing resolver recovery | `integration/test_create_package_persistence.py::test_missing_resolver_blocks_precheck_and_send` |
| ESP-16 | Deprecation | `integration/test_esp_persistence.py::test_deprecate_closes_new_selection` |
| ESP-17 | Delete policy | `integration/test_esp_lifecycle_resolution.py::test_trusted_active_resolver_root_cannot_be_deleted`, `::test_deprecate_clears_the_pointer_then_the_delete_succeeds` *(added 2026-08-03, §E.2 closed)*; `integration/test_esp_persistence.py::test_soft_delete_preserves_revision_chain` (revision-chain half) |
| ESP-18 | Trash policy | `integration/test_trash_page.py::test_trash_surfaces_reject_non_admin` |
| ESP-19 | Export integrity | `integration/test_acceptance_esp_package_gaps.py::test_esp_revision_export_carries_identity_hash_and_dependency_manifest` *(added 2026-07-29; **PARTIAL → FULL on 2026-08-03**, G-02 export schema v2 — §E.4 closed)*; field-by-field fidelity, determinism, tamper detection and absent-evidence behaviour in `integration/test_esp_export_contract_v2.py`; import-side v1/v2 compatibility + trust boundary in `integration/test_package_import_schema_v2.py` |
| ESP-20 | Role-aware list | `integration/test_esp_persistence.py::test_list_filters_by_visibility_scope` |

> The mappings in §C are **stated, not scanner-verified** — they were established by
> reading each test, but no tool enforces them. To make them enforceable the tests
> must cite the audit-local IDs in their docstrings; that is deliberately left as a
> follow-up so this slice stays reviewable.

---

## §D. Adjudicated name differences

The specs name error codes the implementation ships under other names. Following
the **O-03 convention (shipped name wins)**:

| Spec ID | Spec code | Shipped code | Where |
|---|---|---|---|
| AOS-03 | `INVALID_ITEM_KIND` | `CLIENT_LEGACY_TYPE_REJECTED` | `domain/package/kind.py` |
| AT-04 | `MARKET_DATA_INSTRUMENT_MISMATCH` | *(no such code)* — enforced by the worker instrument-scope guard | `test_backtest_persistence.py::test_worker_fails_closed_on_instrument_mismatch` |
| AOS-12 | `KIND_REVISION_MISMATCH` | ~~*(unimplemented)*~~ → **shipped under the spec name** | `domain/mainboard/revision_binding.py` — see **§H** |

---

## §E. Genuine coverage gaps (not merely untagged)

Verified by reading the code, not inferred from the absence of a tag:

| ID | Gap |
|---|---|
| TS-20 / AOS-20 | **No Tool Gateway parity test for Trading Signal.** `test_gateway_parity_s4.py` covers Allocation + Trade Log (TL-22); `test_gateway_parity.py` covers ready-check/capability. The Signal line is unproven. |
| AT-21 | No Agent-parity test for the Strategy save line. |
| TS-16 / TL-18 / AOS-16 | No test asserts that expand/collapse writes no revision / audit / composition hash. Purely presentational today, but unpinned. |
| RF-15 / ESP-05 | No test asserts the V18 seed Family (`Embedded System / TA Resolver`) resolves ACTIVE with a matching ESP meta/filter relation. |
| AOS-12 | ~~`KIND_REVISION_MISMATCH` has no implementation and no test.~~ **Closed 2026-07-29 — see §H.** |
| AT-24 | Strategy soft-delete + historical manifest provenance is not asserted end-to-end. |
| PC-14, PC-19, PC-22 | Resolver-approval 403, soft-deleted-ESP historical manifest, and untrusted-string rendering are unasserted. |
| CP-05, CP-14, PL-06, ESP-19 | See §C. |

### E.1 — DEFECT found while writing the RF-12 test

`StrategyConfig.rationale_family_id` is declared `str = Field(...)` with **no
`min_length=1`** (`backend/src/entropia/domain/strategy/config.py:40`). Empirically:

* payload with the key **absent** → `STRATEGY_CONFIG_INVALID`, `NOT_READY` ✅ (RF-12 holds)
* payload with `rationale_family_id: ""` → parses, evaluates **`READY`** ❌

A manipulated client can therefore reach RUN with no Rationale Family, which is
exactly what RF-12 forbids. **This slice did not fix it** — the fix is a domain
change (`min_length=1`) plus a Ready Check regression test, which is behaviour
change and out of scope for a traceability slice. The hole is pinned as a comment
next to the passing RF-12 test so it cannot be silently lost.

**Recommended follow-up:** `fix/rf12-blank-rationale-family-blocks-ready`.

### E.2 — DEFECT found while writing the PC-19 test (added 2026-07-29, I-17-COV) — **CLOSED 2026-08-03**

> **CLOSED** by `fix/esp-lifecycle-resolution`. Reproduced once more on
> `origin/main` @ `ef47847` before any code was written (activate `ta.sma` →
> soft-delete its root → resolve → the same trusted revision came back,
> `resolved=True`), then fixed on both axes the finding named:
>
> * `domain/esp/resolver.py::evaluate_resolution` now takes `ResolverRootFacts`
>   and refuses a root that is not `deletion_state=active` +
>   `lifecycle_state=active` + `package_kind=embedded_system`
>   (`ROOT_NOT_ACTIVE` → `RESOLVER_NOT_ACTIVE` 409; `ROOT_MISSING` /
>   `WRONG_PACKAGE_KIND` → `RESOLVER_NOT_RESOLVED` 404);
> * `commands/deletion.py::_soft_delete_preflight` gained the deprecate-first
>   `DELETE_POLICY_BLOCKED` blocker (doc 09 §9.5 step 2) and is now invoked from
>   `soft_delete_registry_root` too, so `soft_delete_package` — the production
>   package-delete route, which bypassed the preflight entirely — is covered;
> * `jobs/create_package.py::registry_fingerprint` hashes the resolver root's
>   lifecycle alongside the registry pointer, so a root lifecycle change makes an
>   earlier PASSED scan `PRECHECK_STALE` server-side.
>
> Tests: `integration/test_esp_lifecycle_resolution.py` (24 cases) +
> `unit/test_esp_resolver.py` (root-gate cases). PC-19 clause 1 stays where it was,
> in `test_acceptance_esp_package_gaps.py`. The historical-pin guarantee is
> unchanged — see §H.2.

The original finding, kept verbatim for the record:

A **soft-deleted ESP still resolves for a new Pre-Check.** `soft_delete_entity`
runs no ESP-specific preflight (`commands/deletion.py::_soft_delete_preflight`
branches only on `work_object` and `rationale_family`) and leaves
`embedded_resolver_registry` untouched, while
`queries/esp.py::resolve_embedded_dependency` decides on the registry entry's
`trust_state` alone — it never reads the root's `deletion_state`. Probed
empirically on 2026-07-29: activate `ta.sma` → soft-delete its root → resolve →
the **same trusted revision came back**.

That is the second clause of doc 07 **PC-19** ("new Pre-Check does not resolve
soft-deleted/inactive ESP"), and the resolver's own docstring
(`queries/esp.py:228`) already advertises `deprecated / soft-deleted registry
entry -> RESOLVER_NOT_ACTIVE` — so the implementation contradicts its documented
contract, not merely the spec. The PC-19 test therefore asserts only the FIRST
clause (the historical manifest stays readable, which does hold) and pins the hole
in its docstring.

Adjacent, unasserted here: doc 09 **ESP-17** says the server should block or
redirect a soft-delete of an *active trusted* resolver toward deprecation. No such
preflight exists either — the probe's delete simply succeeded.

**Recommended follow-up:** ~~`fix/pc19-soft-deleted-esp-must-not-resolve`~~ — **done**,
landed as `fix/esp-lifecycle-resolution` (see the CLOSED block at the top of §E.2).

### E.3 — Missing surfaces the "Agent parity" rows name (added 2026-07-29, I-17-COV)

`domain/agent_lab/tool_gateway.py::ToolName` has **no `strategy.*` and no
`trading_signal.*` member** (it ships task/backtest/artifact/documentation tools
plus the post-V1 S4 allocation + trade_log set). So the literal "via Tool Gateway"
clause of doc 02 **AT-21** and doc 04 **TS-20** has nothing to call. The tests
added for those IDs prove the substance both rows are about — and what doc 03
**AOS-20** states outright ("Tool Gateway/**domain commands**") — namely that the
Agent reaches the same server truth on the same command line, under the same
policy, with no browser. The missing tools are an implementation gap, not a test
gap.

**Recommended follow-up:** `feat/gateway-strategy-and-signal-tools`.

### E.4 — Export manifest omits the ESP contract facts — **CLOSED 2026-08-03 (G-02)**

*Original finding (2026-07-29, I-17-COV).* Doc 09 **ESP-19** requires the export
artifact to carry "root/revision identity, content hash, signature, adapter ref,
evidence and dependency manifest". `commands/package_lifecycle.py::export_package`
built the manifest from the package **revision** only, while `runtime_adapter` and
`evidence` live on `embedded_resolver_contract` — so an ESP export shipped identity
+ content hash + dependency manifest (and the signature, because the seed/create
path puts it in `input_contract`), but **not the adapter ref and not the evidence**.
The ESP-19 test asserted exactly what was present and named the rest as a gap rather
than weakening the row.

**Resolution.** Export schema **v2** (`domain/package/export_contract.py`) adds
`export_schema_version`, `exporter_version`, `resolver_contract_snapshot` (canonical
key, signature, runtime adapter, warm-up, timing semantics, repaint, evidence) and
`validation_evidence_snapshot` (the certifying run, or an explicit
`legacy_incomplete_evidence` — never a fabricated pass). Both are read from the rows
the **exported** revision owns, so no old artifact is re-read through the current
head; live registry state stays outside the hashed manifest as `registry_observation`.
The ESP-19 row now asserts every clause of the sentence. Full contract, v1/v2
compatibility matrix and the determinism proof: `docs/audit/esp_export_schema_v2.md`.

**Honest boundary that remains.** A v1 and a v2 artifact of the same revision hash
differently — the field set differs. That is the point of versioning the schema, not
a regression: hashes are never compared across versions, and every recorded v1 hash
stays valid for the v1 artifact it covered.

---

## §F. Honest execution boundary

| Suite | Status |
|---|---|
| `backend` ruff / ruff format / mypy | ✅ clean (`mypy`: 356 source files) |
| `backend/tests/unit/test_trade_log_config.py` | ✅ 12/12 |
| `backend/tests/unit/test_readiness_validators.py` | ✅ 45/45 |
| `frontend/src/test/strategyForm.test.tsx` | ✅ 22/22 |
| `backend/tests/integration/test_rationale_persistence.py` (RF-16) | ✅ **PASSED IN CI** — see resolution below |

The RF-16 integration test **collects** (16 tests, imports resolve, ruff + mypy
clean) but could not be **run**: this machine's PostgreSQL reports

```
asyncpg.exceptions.OutOfMemoryError: out of shared memory
HINT: You might need to increase max_locks_per_transaction.
```

`max_locks_per_transaction = 64` is too small for the integration conftest's
whole-schema `create_all`, and the cluster's shared lock table was further consumed
by leaked `idle in transaction` connections from parallel worktree sessions
(`entropia_test_k09e`, `_o12`, `_o14`, `_t1` — the hazard CLAUDE.md documents).
Stale leaked connections older than 5 minutes were terminated; the limit persists
because the parameter is `PGC_POSTMASTER` and needs a **server restart**, which was
not performed since other sessions held active connections.

**RESOLVED.** PR #416's `Backend — lint, type, test` job ran the integration suite against a
real PostgreSQL and **passed** (28m38s,
[run 30341329121](https://github.com/alimirbagirzade/Entropia/actions/runs/30341329121)).
RF-16 is verified. The local limitation below is kept on record because it will recur on any
machine with the default `max_locks_per_transaction` and parallel worktree sessions.

To run it locally, raise the setting and restart PostgreSQL:

```bash
psql -U entropia -d postgres -c "ALTER SYSTEM SET max_locks_per_transaction = 256;"
```

then restart the server and re-run with an isolated database:

```bash
TEST_DATABASE_URL="postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_i17" uv run pytest tests/integration/test_rationale_persistence.py -q --no-cov
```

---

## §G. Follow-up slice — `feat/i17-rf06-and-map-rename` (2026-07-29)

The I-17 brief asked for two things this document did not yet satisfy. Both are
closed here; nothing in §A–§F is retracted.

### G.1 — RF-06 now has a dedicated test, not an adjacent tag

`RF-06` counted as *traced* in §A, but its only tag was the word `RF-06-adjacent`
in `integration/test_trash_page.py`. That tag was honest about its own limits: it
covered the **generic** restore contract (Admin-only gate, same root / same current
revision) for a `demo_entity`, and said nothing about the Rationale-Family half of
doc 10 §14 RF-06 — *"assignment projection'ları normal ASSIGNED durumuna döner"*.

New test — `integration/test_rationale_persistence.py::test_admin_restore_reactivates_family_and_assignment_projection`:

| RF-06 clause | Assertion |
|---|---|
| same root goes ACTIVE | `root_after.entity_id == family_id`, `deletion_state == ACTIVE` |
| same **current revision** | `root_after.current_revision_id == pinned_revision` + family-revision row count unchanged (no new revision appended) |
| projection returns to ASSIGNED | `assignment_state` walks `assigned` → `assigned_to_deleted_family` → `assigned`; `family_active` walks `True → False → True` |
| family selectable again | it re-enters `list_families(state="active")`, the list it left on delete (RF-05) |

`test_trash_page.py`'s docstring was re-pointed accordingly: it now claims the
generic half explicitly and names the module that owns the type-specific half.

**Why the test seeds the pin directly.** `assigned_to_deleted_family` is *derived*
at read time (`queries/rationale.py::_assignment_view`) from the package head's
`rationale_family_snapshot` — it is never stored. And the doc 20 §10 delete
preflight refuses to soft-delete a family that still holds a current ASSIGNED row
(`RATIONALE_FAMILY_IN_USE`). Those two facts together mean the projection can only
ever describe a revision that **pins** a family while no current assignment row
holds it, so the test seeds exactly that state and drives everything else —
delete, restore, both reads — through the real command/query path.

**Verified:** `pytest tests/integration/test_rationale_persistence.py` → **17/17**
and `test_trash_page.py` → **17/17**, both against a real PostgreSQL on an isolated
database (`entropia_i17rf06`). `ruff check` + `ruff format --check` clean. No `src/`
file changed — this is a test-only slice.

> The §F `max_locks_per_transaction = 64` hazard did **not** bite this run: no
> `idle in transaction` connections were leaked by parallel worktrees at the time.
> The setting is still 64, so §F's warning stands for future runs.

### G.2 — Renamed to `acceptance_id_map.md`

The brief asked for `docs/audit/acceptance_id_map.md`; the slice shipped
`acceptance_id_traceability.md`. Renamed via `git mv` (history follows the rename)
and all six inbound references updated: `acceptance_id_scan.py`,
`I17_LANDED_KICKOFF.md` (×3), `test_trading_signal_events.py`,
`test_rationale_persistence.py`.

### G.3 — Still open after this slice

Unchanged from §E — this slice closed a traceability nuance, not a coverage gap:
TS-20 / AOS-20 (Tool Gateway parity for Trading Signal), AT-21 (Agent parity on the
Strategy save line), TS-16 / TL-18 / AOS-16, RF-15 / ESP-05, AOS-12, AT-24,
PC-14 / PC-19 / PC-22, CP-05, CP-14, PL-06, ESP-19.

---

## §H. Re-measurement — 2026-08-03 (`origin/main` @ `0dcce69`)

> §A–§G above are the **2026-07-28 / 2026-07-29 record and are unchanged**. This section
> is a fresh run of the same scanner on current main, nothing else. Part of the
> ground-truth reset: [`current_main_ground_truth_2026-08-03.md`](current_main_ground_truth_2026-08-03.md).

Command and **real** exit code:

```bash
python3 docs/audit/acceptance_id_scan.py     # exit 0
```

Output verbatim — 347 test files scanned:

| Page | Prefix | 2026-08-03 | Missing now |
|---|---|---|---|
| 02 Add Strategy / Strategy Details | `AT` | **22/25** | AT-04, AT-06, AT-07 |
| 03 Add Outsource Signal | `AOS` | **21/21** | — COMPLETE |
| 04 Trading Signal | `TS` | **20/21** | TS-10 |
| 05 Trade Log | `TL` | **23/23** | — COMPLETE |
| 07 Pre-Check | `PC` | **17/22** | PC-01, PC-02, PC-15, PC-16, PC-18 |
| 10 Rationale Families | `RF` | **16/18** | RF-13, RF-18 |
| 14 Backtest Ready Check | `RC` | **13/18** | RC-11 … RC-15 |
| 16 Results History | `RH` | **2/16** | 14 IDs — **worst page by far** |
| 18 Analysis Lab | `AL` | **16/18** | AL-13, AL-15 |
| 21 User Manual | `UM` | **13/18** | UM-05, UM-12, UM-13, UM-14, UM-17 |
| 22 Future Dev | `FD` | **11/15** | FD-06, FD-07, FD-08, FD-09 |
| **GLOBAL** | | **174/215 (80%)** | **untraced = 41** |

Docs 06 / 08 / 09 remain invisible to the scan (no ID column — see §C), so the 80%
figure does **not** cover them.

### H.1 — §E.2 Tool Gateway gap: still open, re-verified

`ToolName` (`backend/src/entropia/domain/agent_lab/tool_gateway.py:23-59`) carries **23**
members. All ten literals below are **still ABSENT** repo-wide (0 hits in `backend/`):

`strategy.get_draft` · `strategy.create_draft` · `strategy.patch_draft` ·
`strategy.validate_draft` · `strategy.save_revision` ·
`trading_signal.upload_source_asset` · `trading_signal.request_import` ·
`trading_signal.get_import_report` · `trading_signal.create` · `trading_signal.create_revision`

Trap worth restating: the same-shaped `trade_log.*` quartet **does** exist — a different
work-object family, not evidence of parity. The **domain commands** for both families are
complete (`commands/strategy_draft.py`, `commands/trading_signal.py`); that is a separate
axis and does not close AT-21 / TS-20 / AOS-20.

### H.2 — PC-19 (soft-deleted ESP still resolves): **CLOSED 2026-08-03**

This section recorded the finding as unchanged on current main: `queries/esp.py:214-268`
decided on `entry.trust_state` alone, the Package Root's `deletion_state` and
`lifecycle_state` were never read, and no test covered the case. All three are now
false — resolution reads both root facets, `DELETE_POLICY_BLOCKED` enforces
deprecate-first, and `integration/test_esp_lifecycle_resolution.py` covers the case
(including the pre-fix database shape: a soft-deleted root under a still-`trusted_active`
pointer). Full record in §E.2.

**Not a defect, still true, still asserted:** a historical pinned revision stays readable
after its resolver is closed. The dependent revision is immutable and names an exact
`embedded_revision_id`, so it is read straight from `package_revision` and never comes
through `resolve_embedded_dependency` — the fix narrows the NEW-work path only
(`test_historical_pin_stays_readable_after_the_resolver_is_closed`, and PC-19 clause 1 in
`test_acceptance_esp_package_gaps.py`).

**Deliberately NOT done:** the soft-delete path still does not call
`esp_repo.set_trust_state`. Demoting the registry to `unavailable` on delete would be a
one-way door — `unavailable` is terminal in `domain/esp/state_machine.py`, so a restored
root could never be re-activated, contradicting doc 09 §9.5 step 4 ("restore … does not
automatically reinstate a resolver trust pointer **without policy re-evaluation**", i.e.
re-evaluation must stay possible). The invariant "a Trashed resolver root is never
`trusted_active`" is instead guaranteed by the deprecate-first blocker, and resolution
reads the root lifecycle directly rather than trusting the pointer to have been demoted.

### H.3 — §E.2 / H.1 Tool Gateway gap: **AT-21 half CLOSED 2026-08-03**, TS-20/AOS-20 still open

`feat/agent-strategy-tool-gateway` (post-V1 S5) added the five `strategy.*` members H.1
listed as ABSENT, so `ToolName` now carries **28**. The literal "via Tool Gateway" clause
of doc 02 **AT-21** is therefore callable and is proven end-to-end in
`backend/tests/integration/test_gateway_parity_strategy.py` (**23 tests**): the scope
table itself, create → get → patch → validate → save through the Gateway, config_hash
parity with the human line, ownership denial with the human line's own code, stale-OCC and
compiler-blocker durable failures, malformed-request rejection, gateway- and domain-key
idempotency, Mainboard containment, the durable `enqueue → run_tool_job` path with
audit/outbox/agent events + redelivery replay, and Analysis Lab history visibility.

**Still open, re-verified on the same commit:** the five `trading_signal.*` literals are
**unchanged ABSENT**, so doc 04 **TS-20** and doc 03 **AOS-20** keep the §E.2/H.1 status —
their substance is proven on the domain-command axis only. The `trade_log.*` trap in H.1
still applies, and now so does a `strategy.*` one: a `strategy.*` tool is **not** evidence
for the Signal family.

**Adjudicated while closing (full record: `docs/audit/agent_strategy_tool_gateway.md`):**
doc 18 §10's prose spelling `strategy.draft.create` is *not* the registry — the same table
also names `artifact.query`, `context_manifest.read`, `market_data.query` and
`research_data.query`, none of which are `ToolName` members either. The shipped
`<family>.<verb_object>` convention wins, and the rejected prose spelling is pinned by test.

**Deliberately NOT done:** no approve/publish/Admin/Trash tool (doc 18 §14, AL-12/AL-16
unchanged); `derive_strategy_draft_from_package`, `clear_strategy_draft` and
`set_strategy_rationale_family` stay unexposed; `jobs/agent_executor.py`'s stage machine
was not given a strategy step — *when* the Agent authors a strategy is a product decision
the corpus does not state, so it was not invented. The tools are offered at plan time
(`exposed_tool_names` → Coordinator menu) and nothing calls them autonomously yet.
