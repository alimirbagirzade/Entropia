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
| 10 | Rationale Families | `/rationale-families` | `rationale-families--1440.png` | `baseline/rationale-families` | OPEN — assignment rows raw ids (P-16); deep-compare pending (A-06) |
| 11 | Market Data | `/market-data` | `market-data--1440.png` | `baseline/market-data` | OPEN — registry digest columns (P-09) |
| 12 | Research Data | `/research-data` | `research-data--1440.png` | `baseline/research-data` | OPEN — registry-first hierarchy (P-10); deep-compare pending (A-06) |
| 13 | Portfolio / Equity Allocation | `/portfolio` | `portfolio--1440.png` | `baseline/portfolio` | OPEN — raw `mbi_…` ids (P-11); PO D-4 |
| 14 | Backtest Ready Check | Mainboard modal (deep `/backtest/ready-check`) | `ready-check--1440.png` | `baseline/ready-check` | OPEN — P0 surface = Mainboard modal, not standalone (M-10) |
| 15 | RUN & Backtest Results | Mainboard RUN + `/backtest/run` | `run-results--1440.png` | `baseline/run-results` | OPEN — inline result surface + charts (M-11/P-13/F-06) |
| 16 | Results History | `/backtest/history` | `results-history--1440.png` | `baseline/results-history` | OPEN — collapsed metric digest (P-12); PO D-5 |
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
| **F-01** synchronous `_enqueue_stub_job` → real worker lifecycle | ✔ `create_package.py:1248` | W3 | Not started |
| **F-04** breakout-proxy contradictory paths | doc | W3 | Not started |
| **F-05 / M-05** capability matrix (UI ↔ engine parity) | doc | W3 | Not started |
| **F-07** residual raw-id presentation sweep | overlaps P-11/12/16 | W3 | Not started |
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
