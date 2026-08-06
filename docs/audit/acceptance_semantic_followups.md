<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# Semantic acceptance traceability — follow-ups found while mapping

Companion to `docs/audit/acceptance_semantic_map.yaml` and
`acceptance_semantic_traceability.md`. Everything here was found while tying
acceptance criteria to real test nodes, and **every claim below was re-verified
directly against `origin/main` before being written down** — none is inferred
from the absence of a test.

This slice is test-and-audit only: **no production file was changed.** Each item
below is a separate piece of work with its own reproduction.

---

## A. Spec-vs-code divergences (the spec names something the code does not have)

These are not merely untested. The behaviour or the identifier the acceptance row
names does not exist, so no test could cite it without inventing product.

| # | Criterion | Spec says | Code ships | Verified at |
|---|---|---|---|---|
| A-1 | `PL-08` | `PACKAGE_TIMING_INCOMPATIBLE`, raised from a package-declared timing capability | no such code anywhere; only strategy/signal-scoped `TICK_DATA_UNAVAILABLE` / `INTRABAR_DATA_UNAVAILABLE` | `grep -rn PACKAGE_TIMING_INCOMPATIBLE backend/src frontend/src` → no match |
| A-2 | `TR-06` | `DELETE_BLOCKED_BY_RUNNING_JOB` | `ObjectInActiveRunError` / `OBJECT_IN_ACTIVE_RUN`; the spec name survives only as prose | `backend/src/entropia/application/commands/deletion.py:102` (a comment) |
| A-3 | `TS-17` / `AOS-17` | `ACTIVE_RUN_DEPENDENCY` | `OBJECT_IN_ACTIVE_RUN` | same command; neither spelling is pinned by any test |
| A-4 | `AT-04` | `MARKET_DATA_INSTRUMENT_MISMATCH` at Save | enforced at RUN time as `RUN_FAILED_INSTRUMENT_MISMATCH` | `backend/src/entropia/jobs/backtest_engine.py` |
| A-5 | `MB-03` / `MB-25` | `UNSAVED_MAINBOARD_DRAFT`, `OBJECT_EDIT_FORBIDDEN` | `COMPOSITION_EMPTY`, `ACCESS_DENIED` | neither spec code exists in `backend/src` |
| A-6 | `AOS-02` | the literal message `Choose Trading Signal or Trade Log before continuing.` | absent; the design makes the state unconstructible | no match in the repo |
| A-7 | `RD-02` | available-time policy defaults to *Fixed delay*, delay *2 minutes* | defaults to `same_as_event_time`, no delay input | `frontend/src/components/ResearchLifecycle.tsx:310` vs `frontend/src/lib/researchData.ts:308-314` |
| A-8 | `RD-03` | dataset name / field meaning / instrument scope required server-side | `CreateDatasetRequest` declares `display_name: str \| None = None`, `provider_name: str \| None = None`, free-form `payload`; the shipped client sends nulls and the server accepts them | `backend/src/entropia/apps/api/routes/research_data.py` |

**These are adjudication requests, not bugs to fix blind.** Under the project's
O-03 convention the shipped name usually wins, in which case the fix is to correct
the spec row — but that is a product call, so nothing here was changed. The map
records each as an `uncovered` clause with both sides stated.

---

## B. Implementation gaps (a stored field or catalogued type with no live path)

| # | Criterion | Finding | Verified at |
|---|---|---|---|
| B-1 | `ESP-16` | `replacement_revision_id` is persisted, updated and echoed in the projection, but **nothing reads it** — the deprecation "replacement policy" the row describes has no resolution path | written at `commands/esp.py:411-467`, `repositories/esp.py:92-108`, echoed at `queries/esp.py:75`; no reader in `domain/esp/resolver.py` |
| B-2 | `AM-15` | `metric_profile` is **absent from `TRASH_OBJECT_LOCATIONS`**. Per the project's own K-06 rule, a type missing from that catalogue has no soft-delete path that writes a trash entry — so a deleted profile would leave the active projection without ever reaching Admin Trash | `backend/src/entropia/domain/trash/page.py` |
| B-3 | `AM-13` | no metric-bearing Agent surface: `result.query` returns only `{found, result_id, run_id}` and `agent_dataset` composes ledger/signals/equity/diagnostics/summary — no metric values, no registry metadata | `backend/src/entropia/domain/agent_lab/tool_gateway.py` |
| B-4 | `RF-13` | there is no `rationale_family.*` tool on the Agent Tool Gateway, so the row's literal scenario ("Agent creates a Family with the UI closed") cannot be executed at all | `ToolName` in `domain/agent_lab/tool_gateway.py` |
| B-5 | `CP-16` / `PC-15` | `ToolName` has no pre-check / create-package member; the only AGENT-principal test in `contract/test_create_package_contract.py` is a denial | same |
| B-6 | `AM-11` | `booking.py::close_position` increments `stops_hit` / `stop_streak` on any `reason == "stop_loss"` regardless of `is_full`, while relabelling the row `partial_exit` — which reads as contradicting the criterion's "partial leg appears only in diagnostics". **No test covers it either way.** Needs a product ruling before a fix | `backend/src/entropia/domain/backtest/execution/booking.py` |

---

## C. Test-quality findings (the test exists but does not assert what its name claims)

These are the findings that most directly justify this slice: under the old
ID-citation scan they all counted as covered.

| # | Criterion | Finding |
|---|---|---|
| C-1 | `TL-04` | `SOURCE_FILE_REQUIRED` appears in the whole suite **only in two docstrings** (`backend/tests/unit/test_trade_log_config.py`, lines 66 and 77). Both tests assert `any(str(i["field"]).startswith("import_binding") ...)` — neither calls the command or the route. |
| C-2 | `AL-10` | `test_stop_cancels_active_run_no_result` is named for the no-Result guarantee and **never queries `BacktestResult`**. `apply_pending_control` does call `advance_to_safe_checkpoint` and returns the id, but no test reads it back after a STOP. Doc 15's `test_backtest_run_cancellation.py` proves the property properly — for `backtest_run.cancel`, a different command. |
| C-3 | `AT-11` | `test_disabled_percentage_stop_produces_none` only asserts `enabled is False`. The actual filter, `compiler.py::filter_disabled_sections`, has no test at all (`grep filter_disabled backend/tests` → nothing), unlike its scaling sibling. |
| C-4 | `AL-05` | `create_directive` writes an `agent.directive.queued` audit + outbox row; grepping `backend/tests` for that string returns nothing. The only agent-audit tests assert how a kind is *bucketed*, not that anything emits it. |
| C-5 | `ESP-03` | all seven TA fixtures live in `apps/seed.py::_ESP_TA_RESOLVERS` behind `SEED_ESP_TA=1`, and **no test ever calls `_seed_esp_ta_resolvers`**. The suite only asserts hand-built `ta.vwap` and `ta.sma`; dropping or mis-signaturing the other five would pass CI. |
| C-6 | `RD-12` | the server-side Analyze replay guard is real and proven, but the shipped client mints a **fresh Idempotency-Key per click** (the frontend test's own title says so), so a double-click from the browser never exercises it. |
| C-7 | `RC-10` | no test proves a *newer catalog revision* leaves a pinned report non-stale; only `is_stale(a, a) is False`. |
| C-8 | `RH-16` | no test asserts a stale `expected_row_version` on `soft_delete_backtest_result` returns 409; only the dual-token contract test exists. |
| C-9 | `RF-15` | `test_rationale_persistence.py`'s docstring calls RF-15 uncovered. It is stale — RF-15 *is* asserted, in `test_acceptance_esp_package_gaps.py::test_seeded_ta_resolver_family_is_active_and_binds_esp_packages_by_id`. |
| C-10 | `PC-19` | `acceptance_id_map.md` §E.2's body text still says PC-19 "asserts only the FIRST clause". That sentence is stale — both clauses are covered on current main. The CLOSED block above it is accurate. |

---

## D. Corpus not yet mapped

`docs/spec/Entropia_V18_Master_Technical_Reference_v1_0.md` carries **21
module-level acceptance sections** ("Kabul Kriterleri" / "Kabul Testleri" /
"Acceptance tests"). They are the upstream originals the page documents restate —
Master §11.3 maps onto doc 08's Package Library rows — but the wording differs and
some rows have no page equivalent, so they are a second corpus, not a duplicate.
They are **not** in `acceptance_semantic_map.yaml` and are not counted anywhere in
the coverage tables.

`docs/E2E_ACCEPTANCE.md` and the stage handoff documents are likewise unmapped.

---

## E. Empty test directory

`backend/tests/deterministic/` contains only `__init__.py`, though `pyproject.toml`
registers a `deterministic` marker for "pinned-manifest backtest replay tests". The
same-candle engine assertions live in `backend/tests/unit/test_backtest_engine.py`
(`test_same_candle_entry_exit_default_suppresses_ambiguous_flat_entry`,
`test_same_candle_entry_exit_exit_first_admits_entry_after_flat_exit_noop`). Either
the directory or the marker is vestigial.
