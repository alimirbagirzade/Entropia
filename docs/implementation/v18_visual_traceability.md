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
| **F-07** residual raw-id presentation sweep | ✔ swept empirically 2026-07-27 (§4) | W3 | **Presentation layer DONE** — 2 Portfolio residuals fixed; **4 residuals REMAIN** and need a backend display DTO (§4) |
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

## 4. F-07 raw-id presentation sweep — empirical result (2026-07-27)

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

### 4.4 Residuals that REMAIN — need a backend display DTO (NOT presentation-only)

These are real F-07 violations, but their DTOs carry **no human label**, and inventing one in
the browser is precisely the "reconstruct names from IDs" the finding forbids. Each needs
F-07's stated correction — *add display DTOs at query boundaries* — which is a backend query
change and therefore outside this presentation-only slice.

| Site | Defect | Why not fixable here |
|---|---|---|
| `PreCheck.tsx:124` | the request picker's **"Request" column is a bare `request_id`**; Type / Source / State are kinds, not names. Choosing your own request = recognizing an opaque id — a common task, on a page F-07 names explicitly | the Create-Package request DTO (`lib/createPackage.ts`) exposes no name/title field |
| `Library.tsx:1259`, `1274` | import-job rows identified only by `import_job_id` (status badge + `package_kind` alongside) | the import-job DTO carries no label |
| `ResultDetail.tsx:420`, `589` | per-item breakdown rows render `{item_kind} <code>{item_id}</code>`, and leave-one-out rows render `Without <code>{entry.item_id}</code>` — reading a result breakdown is a common task | `PerItemBreakdown` / `ManifestItemRef` have no label field. The result is **immutable and pinned**; joining the *live* composition's labels would mislabel a result whose items have since changed — the label must come from the manifest, i.e. the server |
| `ReadyCheck.tsx:291` | issue rows show a bare `scope_id` (same defect class as the Portfolio issue table that this slice fixed) | `ReadinessIssue` has no label field, and the report is immutable + `is_current`-tracked; labelling a **stale** report from the live composition would be actively wrong |

`ResultsHistory.tsx:170` is deliberately **not** listed as a violation: a backtest result has no
user-assigned name, and since P-12 the row carries completed-at / timeframe / symbol, so the id
is not the sole discriminator. Its digest shape is PO-owned (D-5).

### 4.5 Verification

`eslint` ✓ · `tsc -b --noEmit` ✓ · `vitest` **608/608** (was 607; +1 new case), run with
`--no-file-parallelism`. Backend untouched → **no `ENGINE_VERSION` bump** (no engine behavior
change) and **no migration**.

> **Honest boundary:** this slice closes the F-07 *presentation* layer. F-07 cannot be marked
> Complete outright while §4.4's four surfaces still require a reader to recognize an opaque
> identifier. Those four are the follow-up backend display-DTO slice.
