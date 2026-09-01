<!-- doc-status: historical -->
# A-08 — human screen-reader acceptance: release evidence bundle

**Date:** 2026-09-01 · **Base:** `9c48b0da` (origin/main, ADIM 157) · **Slice:** ADIM 158
**VERDICT: BLOCKED** — exit criteria **0 / 4**, tracking issue **#514 OPEN** (`human-only`).

> **What this bundle is.** The complete, dated accounting of the human evidence
> A-08 requires — 46 route sessions, 20 critical-flow executions, findings,
> dispositions, retests, signed deviations, tracking-issue state — measured
> against the repository's canonical worksheet
> ([`docs/audit/a11y_screen_reader_audit_results.md`](../../../audit/a11y_screen_reader_audit_results.md))
> and against GitHub, on the date above.
>
> **What this bundle is not.** It adds **no human evidence**. No screen-reader
> session ran for it, no cell was filled by it, and nothing in it may be
> transcribed into the worksheet's §1–§3. The only measurements this slice
> performed are the two an agent may honestly perform: **environment
> re-validation** (§8) and **DOM prechecks** (§8) — both stamped
> `screen_reader_verified: false` by their own tooling. Fabricating a session,
> an auditor name, a version string or a finding would be strictly worse than
> the empty cells; none was fabricated.

---

## 1. Exit criteria — 0 / 4 (re-derived 2026-09-01)

| # | Criterion | Met | Re-derived state (2026-09-01) |
|---:|---|---|---|
| 1 | Both SR-1 and SR-2 were run | ☐ | **0 / 2** — SR-2 *started* (1 session, 2026-08-12), not run to completion; **SR-1 never started** |
| 2 | Section A complete on all 23 routes and Section B on all 10 flows, for both combinations | ☐ | **0 / 46** routes complete (1 partial), **0 / 20** flows |
| 3 | Every finding carries `FIX` or `PO-APPROVE` | ☐ | Vacuous, not satisfied — **0 findings recorded** after 2 of 184 Section A cells; a sample that small is not a clean bill |
| 4 | Every `FIX` has landed **or** become a PO-signed deviation | ☐ | Vacuous, not satisfied — nothing to land yet |

**SR-1 complete: NO. SR-2 complete: NO.** No document — this one included — may
show A-08 as `Complete` or `PASS` while this table has an empty box.

## 2. Route-session accounting — all 46, one row each

23 routes × 2 combinations. `—` = the session never ran. The single non-empty
entry is quoted from the worksheet, not re-measured — evidence lives there.

| # | Route | SR-1 (NVDA / Firefox / Windows) | SR-2 (VoiceOver / Safari / macOS) |
|---:|---|---|---|
| 1 | `/` | — not started | **PARTIAL — 2 / 8 cells** (A-1 `PASS`, A-2 `PASS` ᴷ³; A-3…A-8 `—`) · 2026-08-12 · Ali Mirbagirzade (`neither`) · macOS 15.3 · VoiceOver (macOS 15.3) · Safari 18.3 · stack `7dd1dfe` |
| 2 | `/strategy` | — not started | — not started |
| 3 | `/outsource-signal` | — not started | — not started |
| 4 | `/trading-signal` | — not started | — not started |
| 5 | `/trade-log` | — not started | — not started |
| 6 | `/packages/create` | — not started | — not started |
| 7 | `/packages/pre-check` | — not started | — not started |
| 8 | `/packages/library` | — not started | — not started |
| 9 | `/packages/embedded` | — not started | — not started |
| 10 | `/rationale-families` | — not started | — not started |
| 11 | `/market-data` | — not started | — not started |
| 12 | `/research-data` | — not started | — not started |
| 13 | `/portfolio` | — not started | — not started |
| 14 | `/backtest/ready-check` | — not started | — not started |
| 15 | `/backtest/run` | — not started | — not started |
| 16 | `/backtest/history` | — not started | — not started |
| 17 | `/backtest/metrics` | — not started | — not started |
| 18 | `/analysis-lab` | — not started | — not started |
| 19 | `/panel/management` *(Admin)* | — not started | — not started |
| 20 | `/panel/logs` *(Admin)* | — not started | — not started |
| 21 | `/trash` *(Admin)* | — not started | — not started |
| 22 | `/user-manual` | — not started | — not started |
| 23 | `/future-dev` | — not started | — not started |

**Totals: 0 / 46 complete · 1 / 46 partial · 45 / 46 untouched.** Route 1 / SR-2
is partial and partial ≠ complete (the worksheet's own counter reads `0 / 23`
for the same reason).

## 3. Critical-flow accounting — all 20, one row each

10 flows × 2 combinations. Every execution: **not run**.

| # | Flow | SR-1 | SR-2 |
|---|---|---|---|
| B-1 | Add menu (Mainboard `+ Add`) | — | — |
| B-2 | Add Package popover | — | — |
| B-3 | Ready Check result (Passed / Failed / Warnings) | — | — |
| B-4 | Backtest RUN progress + SSE events | — | — |
| B-5 | Error envelope (`code` / `message` / `remediation`) | — | — |
| B-6 | OCC conflict (409) | — | — |
| B-7 | File upload (four surfaces + rejected file type) | — | — |
| B-8 | Trash restore / purge confirmation | — | — |
| B-9 | Long tables (Package Library, Results History) | — | — |
| B-10 | Login | — | — |

**Totals: 0 / 20 executed.**

## 4. Findings, dispositions, retests

| Ledger | Count | State |
|---|---:|---|
| Findings recorded (`SR-BULGU-nn`) | **0** | Register holds only its placeholder row |
| Findings awaiting disposition | 0 | Nothing to disposition — **vacuous**, not clean: 2 / 184 cells is too small a sample to have produced one |
| `FIX` findings awaiting retest | 0 | Nothing to retest |
| `PO-APPROVE` deviations arising from the audit | 0 | None — and none may be written on an agent's initiative |

Every future finding must carry the full 16-column register row (auditor, OS,
screen-reader + version, browser + version, date, route/flow, expected,
observed verbatim, WCAG SC, severity, `FIX`/`PO-APPROVE`, PO signature,
evidence, retest) — the worksheet's §3 column contract and the
`a11y_screen_reader_finding.yml` issue template enforce this shape.

## 5. Signed deviations — explicit, unchanged, not converted

Both pre-existing signed deviations remain **deviations**. Neither is restated
here as compliance, and neither covers A-08.

| ID | Signed | Signer | What it says — verbatim consequence |
|---|---|---|---|
| **D-10** | 2026-07-30 | alimirbagirzade (product owner) | 45 accent-blue low-contrast nodes frozen in the a11y baseline. **WCAG 2.2 AA 1.4.3 is NOT met; the product cannot be marketed as compliant for that criterion.** New or increased violations still break the CI ratchet. Register: `docs/implementation/a11y_ci_ratchet_and_adjudication.md` §4. |
| **D-11** | 2026-08-13 | alimirbagirzade (product owner) | Entropia ships no footer; the product's landmark set is **three** (`banner`/`navigation`/`main`) and checklist A-2 expects three. **Not a WCAG compliance claim** (no SC requires `contentinfo`) — and not a compliance gap either. The K-3 precheck advisory is **not silenced** (still fires 23/23); the decision fixed its disposition, not the measurement. Real footer *content* later = a **new** decision. Register: same file, §4b. |
| *(A-08 scope)* | — | — | **No signed deviation exists for A-08 itself.** The 2026-08-07 evidence-free closure of #514 was explicitly *not* converted into one; reading (A) in the worksheet's tracking table is recorded **NOT TAKEN**. An agent must never author one. |

## 6. #514 — tracking state reconciled with evidence

Re-measured 2026-09-01 via `gh issue view 514`:

| Fact | Value |
|---|---|
| State | **OPEN** — re-opened `2026-08-12T11:08:58Z` (`state_reason: reopened`), by a human, expressly to run this audit |
| Label | `human-only` — an agent must neither close nor re-open it |
| Activity since re-open | **None** (`updatedAt` = the re-open timestamp) |
| Consistent with the ledger? | **YES** — open issue ↔ 0 / 4 exit criteria ↔ 2 / 184 cells. No divergence exists today. |
| History worth keeping | Closed **twice** without a single committed result (2026-07-30, 2026-08-07); both closures reverted by humans (2026-08-03, 2026-08-12). The issue's state is not the gate in either direction — the worksheet's §5 table is. |

## 7. Why this bundle cannot be PASS — and what would make it one

The remaining work is **human by definition** (checklist §"Neden
otomatikleştirilemez": announcement order, live-region audibility, name
intelligibility and virtual-cursor behaviour do not exist in the DOM). In
order:

1. **SR-2 continuation** — machine and auditor exist; the runbook §0 card names
   the exact next cell (route 1 `/`, A-3 on the rewritten question, then
   A-4…A-8, then routes 2–23, then B-1…B-10). Even completed, SR-2 alone leaves
   criterion 1 at 1 / 2 and criterion 2 at 23 / 46.
2. **SR-1 scheduling** — the entire NVDA / Firefox / Windows half has **no
   machine and no auditor assigned**. This is a scheduling decision, not a
   session; nothing in the repository can take it.
3. Both combinations to completion; every finding dispositioned `FIX` /
   `PO-APPROVE`; every `FIX` retested on the combination that found it.
4. Then — and only then — a human closes #514, and this bundle's verdict line
   can be re-issued as PASS by the session that holds the evidence.

## 8. What WAS measured today — environment, not audit

Both artifacts below are machine measurements. Both are stamped
`screen_reader_verified: false` by their own tooling.

**8.1 Audit stack re-validated on current main — 9 passed / 0 failed.** The
last validation was at `7dd1dfe` (2026-08-12); `main` has moved ~60 slices
since. `scripts/a11y-audit-stack.sh up` was run on the auditor's own Mac (the
same machine class the SR-2 session used; the Docker daemon exists here — the
2026-08-25 container obstacle in worksheet §6.1a does not apply):
build + start + migrate + seed + validate, all green — Admin session, three
seed-flag fixtures, 23/23 routes served. Transcript:
[`a08_stack_validation.txt`](a08_stack_validation.txt). **The stack was left
RUNNING for the next human session** (web `http://127.0.0.1:18280`, Admin
`e2e_admin`; teardown is deliberately explicit: `scripts/a11y-audit-stack.sh down`).

**8.2 Structural prechecks re-run — three runs, 0 blocking failures, and one
instrument lesson.** Raw reports:
[`run1`](a08_precheck_results_run1.json) · [`run2`](a08_precheck_results_run2.json)
· [`run3`](a08_precheck_results_run3.json).

| Class | run 1 (cold) | run 2 (warm) | run 3 (warm) | Verdict vs 2026-08-12 provenance |
|---|---:|---:|---:|---|
| skip link (K-2, tripwire) | 0 | 0 | 0 | silent — no regression of PR #685 |
| no `<h1>` (K-4, tripwire) | 0 | 0 | 0 | silent — no regression of PR #685 |
| `contentinfo` (K-3, D-11) | 23 | 23 | 23 | stable, unchanged |
| heading outline (K-5) | 21 | **22** | **22** | **re-confirms 22 / 23** (warm ×2; `/user-manual` in the set, `/` out) |
| focus indicator (K-6a) | 1 | 1 | 1 | stable, unchanged — still waits on a human eye |
| `aria-live` (K-7) | 15 | **19** | **16** | **UNSTABLE on this host** — spread far wider than the recorded ±1; see below |
| blocking failures | 0 | 0 | 0 | — |

**The K-7 instability is a measurement finding, not a product one, and its
mechanism was traced to source:** `components/Loading.tsx` renders
`role="status" aria-live="polite"`, so a route the probe catches **mid-load**
carries an initial live region and **leaves** K-7's set — the initial-DOM race
documented in the worksheet's methodology note, operating in the **opposite
direction** to the one recorded there. On this host the routes entering/leaving
between warm runs (`/packages/create`, `/packages/embedded`,
`/packages/pre-check`, `/trade-log`, `/trading-signal`) are Loading-bearing
pages, not the three known-flaky routes. Consequence, recorded in worksheet
§6.1d: **K-7's last runner-class-comparable figure stays 21 / 23
(2026-08-12)**; today's envelope on this host is 15–19. Either way it is a DOM
count — the question K-7 actually asks (B-3 / B-4 / B-6: is anything
*announced*?) is untouched and still belongs to the human.

## 9. Bundle contents

| File | What it is |
|---|---|
| `A08_acceptance_evidence_bundle.md` | this accounting |
| `a08_stack_validation.txt` | stack re-validation transcript, ANSI-stripped, password redacted |
| `a08_precheck_results_run1.json` | precheck report, cold run (discarded per the run-twice rule) |
| `a08_precheck_results_run2.json` | precheck report, warm run |
| `a08_precheck_results_run3.json` | precheck report, warm run |

Canonical, living counterparts: worksheet
`docs/audit/a11y_screen_reader_audit_results.md` (results + §6.1d for today's
refresh) · checklist `docs/implementation/a11y_screen_reader_audit_checklist.md`
· runbook `docs/implementation/a11y_screen_reader_audit_runbook.md` §0 (next
session card) · RC report `docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md`
(release verdict).
