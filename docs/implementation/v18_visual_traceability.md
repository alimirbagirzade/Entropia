# Entropia V18 — Visual & Requirement Traceability Matrix

> **Mandated by** the 22-July-2026 deep audit
> (`docs/spec/Entropia_V18_Current_UI_vs_Prototype_Deep_Audit_Claude_Code_Remediation.md`)
> **Finding A-04**: a count of generated PNGs is not coverage traceability. This file maps
> every one of the 22 page documents and every production route/state to either a prototype
> reference **or** a documented "no independent prototype screen" rule with the correct
> host-state reference.
>
> **Authored:** 2026-07-22 · **Against:** `origin/main` = `6e3fab9` (audit base commit).
> **Nothing here is product-owner approved.** Every visual disposition that requires a PO
> signature is marked `OPEN — PO DECISION REQUIRED` and routes to the D-1…D-9 record in
> `docs/implementation/v18_final_acceptance.md §4`. Per the audit §2 rule 5, an unsigned
> `PO-APPROVE` is **not** approval and its parent requirement is **not** complete.

---

## 1. Per-document visual coverage matrix (audit A-04)

Legend for **Prototype ref**: a `screenshots/prototype/*--1440.png` filename, or
`HOST-STATE` = this screen has **no independent prototype capture** because in the prototype
it is a Mainboard action / overlay / placeholder, not a standalone page (the audit's explicit
allowance). **Current** = `frontend/e2e/screenshots/baseline/<dir>/`. **Diff/fidelity** is the
prototype-fidelity disposition (regression stability is a *separate* claim — audit A-02).

| # | Page document | Production route | Prototype ref | Current baseline | Prototype-fidelity disposition |
|---|---|---|---|---|---|
| 01 | Mainboard | `/` | `mainboard--1440.png` | `baseline/mainboard` | OPEN — hierarchy/row divergence (M-01/M-02); PO D-1/D-9 |
| 02 | Strategy Details | `/strategy` **+ Mainboard inline row** | `strategy-details--1440.png` | `baseline/strategy-details` | OPEN — density/tokens (M-03); PO D-1/D-9 |
| 03 | Add Outsource Signal | Mainboard Add action (deep-link `/outsource-signal`) | **HOST-STATE** — Mainboard Add menu (no independent prototype screen) | `baseline/outsource-signal` | Route reclassified as deep-link (P-01); primary = Mainboard |
| 04 | Trading Signal | `/trading-signal` **+ inline** | `trading-signal--1440.png` | `baseline/trading-signal` | OPEN — oversized workbench vs compact (M-06); PO D-6/F-6 |
| 05 | Trade Log | `/trade-log` **+ inline** | `trade-log--1440.png` | `baseline/trade-log` | OPEN — same composition issue (M-07); PO D-6/F-6 |
| 06 | Add / Create Package | `/packages/create` | `create-package--1440.png` | `baseline/create-package` | OPEN — labels/layout/persist (P-03/04/05); PO D-2/D-3 |
| 07 | Pre-Check | Create Package overlay (deep `/packages/pre-check`) | **HOST-STATE** — Create Package status card + overlay | `baseline/pre-check` | OPEN — primary/secondary surface confusion (P-02) |
| 08 | Package Library | `/packages/library` | `package-library--1440.png` | `baseline/package-library` | OPEN — Market/TF facets + IA (P-06/P-07) |
| 09 | Embedded System Packages | `/packages/embedded` | `embedded-packages--1440.png` | `baseline/embedded-packages` | OPEN — scoped catalog presentation (P-08); deep-compare pending (A-06) |
| 10 | Rationale Families | `/rationale-families` | `rationale-families--1440.png` | `baseline/rationale-families` | OPEN — deep-compare pending (A-06). P-16 raw-id claim is STALE: assignment rows name the package (`package_name ?? package_root_id`) and family (`current_family_name`) since `20ccacc` — verified `RationaleFamilies.tsx:637` |
| 11 | Market Data | `/market-data` | `market-data--1440.png` | `baseline/market-data` | OPEN — registry digest columns (P-09) |
| 12 | Research Data | `/research-data` | `research-data--1440.png` | `baseline/research-data` | OPEN — registry-first hierarchy (P-10); deep-compare pending (A-06) |
| 13 | Portfolio / Equity Allocation | `/portfolio` | `portfolio--1440.png` | `baseline/portfolio` | OPEN — **PO D-4 unsigned**. P-11 raw-`mbi_` claim is STALE: sleeve rows, the picker, the example line (PR #375) and — since the F-07 sweep — validation-issue rows all name the item, with the id kept as a secondary binding key |
| 14 | Backtest Ready Check | Mainboard modal (deep `/backtest/ready-check`) | `ready-check--1440.png` | `baseline/ready-check` | OPEN — P0 surface = Mainboard modal, not standalone (M-10) |
| 15 | RUN & Backtest Results | Mainboard RUN + `/backtest/run` | `run-results--1440.png` | `baseline/run-results` | OPEN — inline result surface + charts (M-11/P-13/F-06) |
| 16 | Results History | `/backtest/history` | `results-history--1440.png` | `baseline/results-history` | OPEN — **PO D-5 unsigned**. P-12 collapsed metric digest landed (`3c6887c`): the row carries completed-at / timeframe / symbol beside the `result_id`, so the id is no longer the row's only discriminator |
| 17 | Arrange Metrics | `/backtest/metrics` | `arrange-metrics--1440.png` | `baseline/arrange-metrics` | Preserve semantics; equivalent populated/locked compare pending (A-06) |
| 18 | Analysis Lab | `/analysis-lab` | `analysis-lab--1440.png` | `baseline/analysis-lab` | OPEN — equivalent active-task compare pending (A-06) |
| 19 | Panel Management | `/panel/management` | `panel-management--1440.png` | `baseline/panel-management` | OPEN — machine policy strings (P-15); deep-compare pending (A-06) |
| 19 | Panel Logs | `/panel/logs` | `panel-logs--1440.png` | `baseline/panel-logs` | OPEN — backtest-log primary view (P-14); deep-compare pending (A-06) |
| 20 | Trash | `/trash` | `trash--1440.png` | `baseline/trash` | Preserve lifecycle; exact row/filter compare + a11y pending |
| 21 | User Manual | `/user-manual` | `user-manual--1440.png` | `baseline/user-manual` | OPEN — baseline completeness + anchors compare pending (A-06) |
| 22 | Future Dev | `/future-dev` | **HOST-STATE** — placeholder / capability-gated (no active prototype screen) | `baseline/future-dev` | Placeholders NOT counted as feature completion (F-09) |

**Inventory reconciliation (audit A-04):** 20 prototype refs + 3 HOST-STATE screens
(03 Add Outsource Signal, 07 Pre-Check, 22 Future Dev) = 23 production baseline route dirs.
No document is silently omitted, double-counted, or represented by the wrong host screen.

**Approval column (PO fills):** every OPEN row above is closed only by a signed D-1…D-9
decision in `v18_final_acceptance.md §4` linked to the exact screenshot pair, behavior, date,
approver, and scope. Until then the parent requirement stays **not complete** (audit A-05).

---

## 2. 47-finding → existing-wave disposition (the "same topic" guard)

Purpose: prevent re-doing work R2 already closed, and separate what is **blocked on the PO**
from what is **open engineering**. Verified against `6e3fab9` code + R2 truth docs on 2026-07-22.

### Bucket 1 — SAME topic as R2 D-1…D-9 (BLOCKED on product-owner signature)

| Audit finding | = R2 decision | Note |
|---|---|---|
| A-05 (`PO-APPROVE` treated as approved) | the D-1…D-9 gate itself | audit §2 rule 5 |
| P-17 (titles/spacing/tokens accepted) | D-1 | `v18_visual_deviations.md` |
| P-03 / P-04 (Create Package labels / layout) | D-2 / D-3 | F-2 / F-3 |
| P-11 (Portfolio raw `mbi_…`) ✔verified | D-4 | `Portfolio.tsx` |
| P-12 (Results History collapsed digest) | D-5 | F-5 |
| M-06 / M-07 (TS/TL oversized workbench) | D-6 | F-6 density |
| A-07 (228 serious contrast nodes) | D-7 | A11Y-01 (a/b/c) |
| A-02 / A-03 / A-04 / M-10 / M-11 (equivalent-state, fidelity) | D-9 / 20.11 | prototype-fidelity layer |

### Bucket 2 — Already-documented honest boundaries (not new, tracked OPEN)

A-06 (10-page deep compare: 03,07,09,10,12,17,18,19,21,22) · A-08 (NVDA/VoiceOver manual a11y) ·
A11Y-02 `link-in-text-block` (D-8) · F-02 (NL package generation = Future-Dev) ·
F-03 (multi-item unified-clock portfolio) · P-13 / F-06 (ResultDetail charts + AI Review).

### Bucket 3 — Genuinely OPEN engineering (NOT PO-blocked) — R3 waves

| Finding | Verified | R3 wave | Status |
|---|---|---|---|
| **M-12** nav forbidden package kinds | ✔ `nav.ts:202-203` | W1 | **DONE** (removed + regression test) |
| **A-01** `*-inline` visual cases hit standalone routes | ✔ spec 31-33 | W1 | **DONE** (renamed `*-standalone`; inline coverage = spec-08) |
| **F-08** docker web health `localhost:80` IPv6 | ✔ compose ~203 | W1 | **DONE** (`127.0.0.1:80`) |
| **A-04** this traceability matrix | ✔ absent | W1 | **DONE** (this file) |
| **P-05** Create Package unpersisted fields (Compatible family / Indicator link) | ✔ `CreatePackage.tsx:460` | W2 | Not started |
| **P-06** Package Library Market/Timeframe facets | ✔ `Library.tsx:238` | W2 | Not started |
| **P-09** Market Data registry columns (Source/Coverage/Resolution) | doc | W2 | Not started |
| **P-10** Research Data registry-first hierarchy | doc | W2 | Not started |
| **P-14** Panel Logs backtest-log primary view | doc | W2 | Not started |
| **F-01** synchronous `_enqueue_stub_job` → real worker lifecycle | ✔ `jobs/create_package.py` (4 kinds) | W3 | **DONE** (F-01a/b/c: Pre-Check · candidate · validation · baseline-parse all admissions + durable workers; `_enqueue_stub_job`/`_enqueue_completed_job` deleted; acceptance in `test_create_package_{precheck,candidate_validation,baseline}_worker.py`) |
| **F-04** breakout-proxy contradictory paths | doc | W3 | Not started |
| **F-05 / M-05** capability matrix (UI ↔ engine parity) | ✔ `domain/backtest/capabilities.py` (59 rows, 22 `future_dev`) | W3 | **DONE** (canonical matrix per option VALUE; engine fail-closed gate at the `_open` choke point + `capability_not_in_build` trace/L4 warnings; Ready Check `STRATEGY_CAPABILITY_NOT_IN_BUILD` "Not available in this build"; editor disables `future_dev` options with the dependency note from the generated `engineCapabilityMatrix.generated.ts` mirror. Found + closed a real silent hole: `slippage_mode='historical_slippage_if_available'` passed all nine per-domain predicates and ran as a ZERO-slippage backtest. `ENGINE_VERSION` → `backtest-engine-v18-capability-matrix`. Acceptance in `test_capability_matrix.py` + `engineCapabilityMatrix.test.tsx`) |
| **F-07** residual raw-id sweep | ✔ **COMPLETE** 2026-07-29 (§4) | W3 | Presentation half 2026-07-27 (2 Portfolio residuals fixed, §4.3); backend display-DTO half 2026-07-29 (all **4** residuals closed, §4.4). Migration `0041`; `ENGINE_VERSION` → `-per-item-labels` (artifact shape, not behaviour) |
| **F-09** README/status honesty rewrite | doc | W3 | Not started |

**Rule:** a Bucket-3 item is `DONE` only with working behavior + passing acceptance test.
A Bucket-1/2 item cannot be `Complete` without the PO signature or an explicit Future-Dev gate.

---

## 3. Wave-1 completion evidence (2026-07-22)

- **M-12** — `frontend/src/app/nav.ts` (2 forbidden entries removed) +
  `frontend/src/test/nav.test.tsx` new case "no menu leaf advertises Trading Signal / Trade Log
  package kinds". vitest **578/578**.
- **A-01** — `frontend/e2e/specs/11-visual-regression.spec.ts` cases renamed
  `strategy/trading-signal/trade-log-standalone`; baselines `git mv` to matching names (identical
  pixels — no PO re-approval); header cross-references spec-08 (inline behavioral) + spec-12
  (prototype). Inline acceptance ("fails if inline editor removed") already enforced by spec-08.
- **F-08** — `docker-compose.yml` web healthcheck `http://localhost:80/` → `http://127.0.0.1:80/`
  with rationale comment. (Docker not run in this session; change is deterministic.)
- **A-04** — this file.
- **Frontend verify:** `tsc --noEmit` ✓ · `eslint` (changed files) ✓ · `vitest` 578/578 ✓ ·
  `npm run build` ✓.

---

## 4. F-07 raw-id sweep — empirical result (presentation 2026-07-27, display DTOs 2026-07-29)

**Why this section exists.** §2 Bucket 3 carried F-07 as `Not started` with the note
"overlaps P-11/12/16". Those three landed, so the row could not be trusted either way.
This is the empirical sweep that replaces the assumption.

### 4.1 Method

A JSX **text-node** scan of every non-test `frontend/src/**/*.tsx`: each `{expr}` in a
visible-text position (`>{expr}` / `{expr}<`, attributes and function signatures excluded)
whose expression reads an `*_id` field. **161 renders across 31 files.** The raw count is
NOT the finding — F-07's own acceptance permits IDs in support/audit surfaces:

> *Required correction:* Add display DTOs at query boundaries; never reconstruct names from
> IDs in the browser. **Keep copyable IDs in advanced detail for support/audit.**
> *Acceptance:* **No common task requires recognizing an opaque identifier.**

So each render was classified as **primary identity for a common task** (a violation) or
**advanced/audit detail** (explicitly permitted).

### 4.2 Verified NOT violations (permitted advanced detail)

- `Mainboard.tsx:313` — inside the **closed** `<details>` "Composition settings" disclosure.
- `PanelLogs.tsx:420` (+ `subject_id`, `technical.*`) — Panel Logs *is* the audit console;
  IDs live in its `<dl class="kv">` detail drawer.
- `Library.tsx:477` — "Head revision" in a detail `<dl>`; the package row above names `pkg.name`.
- The bulk of the 161 — success notices ("Revision appended — `<code>rev…</code>`") and detail
  panels in `MarketData` / `ResearchData` / `CreatePackage` / `StrategyDetailsPanel` /
  `TradeLogEditor` / `TradingSignalEditor` / `Embedded` / `FutureDev` / `AnalysisLab`, each
  carrying a human name alongside.
- `RationaleFamilies.tsx:637` — `package_name ?? package_root_id` (P-16 satisfied).

### 4.3 Residuals FIXED in this slice (presentation-only)

Both are on Portfolio — the page P-11 supposedly swept — and both were fixable with labels the
frontend **already held**, so no DTO, route, react-query key, OCC token, Idempotency-Key, hook,
SSE type, `lib/*.ts` data logic or `app/nav.ts` entry was touched.

| # | Site | Defect | Fix |
|---|---|---|---|
| 1 | `Portfolio.tsx:1002` (pre-fix) | `IssuesTable` showed a **bare `composition_item_id`** as the sole identification of which item a validation issue was about — the page computed `labelByItem` for every *other* surface but never passed it here | `IssuesTable` takes `labelByItem`; renders `ItemLabel` (name primary, id secondary). Threaded to both call sites, incl. `SaveResultCard` via `draftQuery.data.draft.entries` |
| 2 | `Portfolio.tsx:621` (pre-fix) | the example line fell back to `?? sleeve.composition_item_id`, i.e. **promoted the raw `mbi_` id to the primary name** — contradicting its own contract comment (`allocation.ts:57-60`: "NEVER the raw mbi_ id") | falls back to the new `UNLABELLED_ITEM` constant; the id stays as the secondary binding key |

New shared helper `labelsByCompositionItem()` (module-private) replaces the ad-hoc map build.

**Acceptance test:** `portfolio.test.tsx` → *"names the item a validation issue points at,
instead of a bare id (F-07)"* — asserts the label is inside the **issue row itself** (`within`),
with the id still present. **Proven RED:** reverting only the `IssuesTable` render to the
pre-sweep `<code>{issue.composition_item_id}</code>` fails this test and only this test.

### 4.4 Residuals CLOSED by the backend display-DTO slice (2026-07-29)

These four were real F-07 violations whose DTOs carried **no human label**. Inventing one in
the browser is precisely the "reconstruct names from IDs" the finding forbids, so each got
F-07's stated correction — *add display DTOs at query boundaries* — as a backend change.

**Doc-drift correction (measured 2026-07-29):** `ResultDetail.tsx` is
`frontend/src/components/ResultDetail.tsx`, **not** under `pages/`. Line numbers below are
re-measured; the earlier table gave paths only.

| Site (measured) | Field added | Where it is captured — and why there |
|---|---|---|
| `pages/PreCheck.tsx:129` | `display_label` (+ `created_at`) on `PackageRequestSummary` | `queries/create_package.py::_request_display_labels` — two batched lookups per page: the produced package's `input_contract.name`, else the pinned Rationale Family's `display_name`. Both are names a user gave an object the request genuinely references; neither is derived from an id. A request pinning neither sends `null` |
| `pages/Library.tsx:1263`, `1279` | `source_package_name` on `PackageImportReport` | `commands/package_import.py::submit_package_import` reads `manifest["name"]` at SUBMIT time (migration `0042`). Captured there, not joined from the resulting root, because a `blocked`/`failed` import never produces a package — and a later rename of the imported copy must not rewrite what was imported |
| `components/ResultDetail.tsx:424` (`PerItemCard`), `:595` (`MarginalCard`) | `item_label` on `PerItemBreakdown` and `ContributionMarginal` | composition snapshot `item_manifest.items[].label` -> run manifest `mainboard_item_labels` -> `ItemRun.item_label` -> persisted result diagnostics. **The result is immutable**, so the label is frozen at run time; a live join would mislabel a result whose items have since changed |
| `pages/ReadyCheck.tsx:295` | `scope_label` on `ReadinessIssue` | `queries/readiness_check.py::_scope_labels` reads the snapshot the REPORT pinned. **The report is immutable + `is_current`-tracked**, so labelling it from the live composition would be actively wrong |

Presentation contract: the new `components/LabelledId.tsx` renders the server label as the
PRIMARY text with the raw id kept beneath/beside as the muted copyable token, and renders the
**id alone** when the label is null. It never derives a name from an id.

**Two invariants worth naming.**

1. **A display label must not fork reproducibility.** `mainboard_items` is hashed into
   `execution_key`, so the labels ride a SEPARATE manifest key (`mainboard_item_labels`)
   outside `execution_content`. Renaming a composition item therefore leaves `execution_key`
   byte-identical and an identical replay still reproduces. Pinned by
   `tests/unit/test_f07_manifest_item_labels.py`.

   **This is NOT the same question as the version bump.** The golden guard
   (`test_backtest_engine_golden.py`) caught what the reasoning above does not cover: the
   composite *artifact* grew a field, so the four `portfolio.combine*` scenarios moved
   (every strategy-replay scenario stayed byte-identical — engine BEHAVIOUR is unchanged).
   `ENGINE_VERSION` is therefore bumped to **`backtest-engine-v18-min-n-filtered-events-per-item-labels`**, for
   exactly the reason v17 recorded when it added the per-item breakdown itself: without the
   bump a stale pre-label result is idempotently REUSED for a re-RUN of the same composition
   (INF-04/INF-05) and its rows stay id-only forever — the fix would never reach an existing
   composition. A one-time namespace shift, not label-sensitivity.
2. **Backward compatibility is by omission, not backfill.** Pre-slice snapshots, manifests and
   `package_import_job` rows carry no label; every reader degrades to an empty map / `null` and
   the UI falls back to the id. Backfilling them would fabricate labels those artifacts never
   observed.

Doc 06 §510-512 ("V18 has no editable field; name is generated after C.D.P as *New [Type]
Package*") was **unimplemented** — request-born packages read back nameless, which is why the
Pre-Check picker had nothing but ids. `commands/create_package.py::_generated_package_name`
now writes it at C.D.P. No new user-facing input was added: doc 06 explicitly says the request
has no editable name field before C.D.P.

`ResultsHistory.tsx:170` remains deliberately **not** a violation: a backtest result has no
user-assigned name, and since P-12 the row carries completed-at / timeframe / symbol, so the id
is not the sole discriminator. Its digest shape is PO-owned (D-5).

### 4.5 Verification

**Presentation half (2026-07-27):** `eslint` ✓ · `tsc -b --noEmit` ✓ · `vitest` **608/608**.
Backend untouched → no `ENGINE_VERSION` bump, no migration.

**Backend display-DTO half (2026-07-29):** `ruff check` ✓ · `ruff format --check` ✓ ·
`mypy src` ✓ (372 files) · alembic `0042` **up/down/up** ✓ + column parity verified against
`\d package_import_job` · frontend `eslint` ✓ · `tsc -b --noEmit` ✓ · `vitest`
**654/654** (62 files, `--no-file-parallelism`). Backend full suite run locally on a
worktree-private DB: **1 failed / 2732 passed** on the first pass — the failure was the
golden guard doing its job (see the bump note in §4.4); after the `ENGINE_VERSION` bump +
regenerated `engine_golden_digests.json` the affected modules pass. **CI is the authority.**

Both new invariants were **proven RED**: putting `label` into `_pinned_items` fails
`test_labels_do_not_change_the_execution_key` + `test_labels_are_absent_from_the_hashed_pin_set`
and nothing else; making `_scope_labels` join the live composition fails
`test_renaming_the_item_does_not_relabel_an_existing_report` and nothing else.

> **F-07 is now Complete as a whole** — presentation (§4.3) and display DTOs (§4.4).
>
> **Honest boundary carried forward:** these four route bodies are declared `dict[str, Any]`,
> so the new fields are **not published in `docs/openapi.json`** and the drift guard cannot see
> them (the same blind spot O-30 recorded). Giving the four legacy routes typed response models
> is a separate change with its own idempotent-replay compatibility analysis — it is NOT done
> here.
