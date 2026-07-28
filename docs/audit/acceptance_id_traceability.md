# I-17 — Acceptance test ID traceability

**Slice:** `feat/t2-acceptance-id-traceability` · **Measured:** 2026-07-28 ·
**Baseline commit:** `eff8ffe` (origin/main)

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
| CP-05 | Runtime alignment | — **no test** (`RUNTIME_UNAVAILABLE` path) |
| CP-06 | Pre-Check stale | `integration/test_precheck_audit_events.py` (`precheck_stale`) |
| CP-07 | Missing ESP | `integration/test_create_package_persistence.py::test_missing_resolver_blocks_precheck_and_send` |
| CP-08 | Async resilience | `integration/test_create_package_precheck_worker.py` (durable QUEUED job) |
| CP-09 | Idempotency | `integration/test_create_package_persistence.py::test_create_draft_is_idempotent` |
| CP-10 | Revision immutability | `integration/test_create_package_revision_chain.py` |
| CP-11 | Baseline policy | `integration/test_create_package_baseline_worker.py` |
| CP-12 | Future-leak validation | `integration/test_create_package_candidate_validation_worker.py` |
| CP-13 | Approval policy | `integration/test_create_package_approve_dependency_gate.py`; `unit/test_create_package_policy.py` |
| CP-14 | Clear boundary | — **no test** |
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
| PL-06 | Metric applicability | — **no test** (ROMAD-on-Condition sort scope) |
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
| ESP-05 | Rationale seed | — **no test** (this is also doc 10 **RF-15**, see §E) |
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
| ESP-17 | Delete policy | `integration/test_esp_persistence.py::test_soft_delete_preserves_revision_chain` |
| ESP-18 | Trash policy | `integration/test_trash_page.py::test_trash_surfaces_reject_non_admin` |
| ESP-19 | Export integrity | — **no test** |
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
| AOS-12 | `KIND_REVISION_MISMATCH` | *(unimplemented)* | — |

---

## §E. Genuine coverage gaps (not merely untagged)

Verified by reading the code, not inferred from the absence of a tag:

| ID | Gap |
|---|---|
| TS-20 / AOS-20 | **No Tool Gateway parity test for Trading Signal.** `test_gateway_parity_s4.py` covers Allocation + Trade Log (TL-22); `test_gateway_parity.py` covers ready-check/capability. The Signal line is unproven. |
| AT-21 | No Agent-parity test for the Strategy save line. |
| TS-16 / TL-18 / AOS-16 | No test asserts that expand/collapse writes no revision / audit / composition hash. Purely presentational today, but unpinned. |
| RF-15 / ESP-05 | No test asserts the V18 seed Family (`Embedded System / TA Resolver`) resolves ACTIVE with a matching ESP meta/filter relation. |
| AOS-12 | `KIND_REVISION_MISMATCH` has no implementation and no test. |
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

---

## §F. Honest execution boundary

| Suite | Status |
|---|---|
| `backend` ruff / ruff format / mypy | ✅ clean (`mypy`: 356 source files) |
| `backend/tests/unit/test_trade_log_config.py` | ✅ 12/12 |
| `backend/tests/unit/test_readiness_validators.py` | ✅ 45/45 |
| `frontend/src/test/strategyForm.test.tsx` | ✅ 22/22 |
| `backend/tests/integration/test_rationale_persistence.py` (RF-16) | ⚠️ **NOT EXECUTED** |

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

**RF-16 must be treated as unverified until CI runs it.**

To run it locally, raise the setting and restart PostgreSQL:

```bash
psql -U entropia -d postgres -c "ALTER SYSTEM SET max_locks_per_transaction = 256;"
```

then restart the server and re-run with an isolated database:

```bash
TEST_DATABASE_URL="postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_i17" uv run pytest tests/integration/test_rationale_persistence.py -q --no-cov
```
