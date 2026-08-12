<!-- doc-status: historical -->

# A-08 — human screen-reader audit: results and evidence

> **On the `doc-status` marker.** This file is a *forward-looking worksheet*, not
> a record of a past state — but the repository's vocabulary has only two values,
> and `current` is reserved for the single live slice kickoff
> (`scripts/generate_repository_facts.py::ALWAYS_HISTORICAL_GLOBS` makes every
> `docs/audit/*.md` historical). It is marked `historical` to satisfy that gate,
> not because its contents are stale. What *is* true of a historical record
> applies here too: re-derive the counts in §6 before trusting them.

> ## STATUS: `A-08 HUMAN-BLOCKED`
>
> **The audit has STARTED and is nowhere near done.** This file stopped being an
> empty worksheet on **2026-08-12**, when the **SR-2 (VoiceOver / Safari /
> macOS)** session was opened and the first cells were recorded from a human.
> What it holds is **2 of Section A's 184 cells** (23 routes × 8 checks) on the
> **SR-2 half only**, and **0 of 10 flows**. **SR-1 (NVDA / Firefox / Windows)
> has not been started at all**, so §5's criteria 1 and 2 cannot close no matter
> how far SR-2 goes.
>
> Nothing in this repository — not the axe-core ratchet, not the keyboard spec,
> not the automated prechecks added alongside this file — may be transcribed
> into these tables as a screen-reader result. **A partly filled worksheet is
> evidence for exactly the cells a person filled and for nothing else.**
> An empty template is not evidence — and almost every cell below is still
> empty. A `—` is not a quiet `PASS`, and the completion counters are
> deliberately not rounded up.
>
> **The tracking issue is OPEN again.** A human re-opened **GitHub #514** on
> `2026-08-12T11:08:58Z` in order to run this audit, which is what resolved the
> closure/evidence divergence recorded below — read that block before citing the
> issue's history. `#514` carries the `human-only` label; an agent or automated
> scan must not close it — nor re-open it. It stays open until §5's four exit
> criteria are `☑`, and this worksheet is at **2 / 184**.
>
> Recipe and rationale: [`a11y_screen_reader_audit_checklist.md`](../implementation/a11y_screen_reader_audit_checklist.md).
> Environment: `scripts/a11y-audit-stack.sh up`.

### Tracking-issue state — closure/evidence divergence (recorded 2026-08-07, resolved 2026-08-12)

This block is the **canonical record** of the divergence. Every other document
points here instead of restating it. **It is kept after the resolution**: the
issue was closed without evidence twice, and that pattern is a finding in its own
right, not something a later re-open erases.

| Fact | Value | How to re-derive |
|---|---|---|
| GitHub **#514** state | **OPEN** — re-opened `2026-08-12T11:08:58Z` by the owner, `state_reason: reopened`; the prior closure was `2026-08-07T03:52:03Z` with `state_reason: completed` | `gh issue view 514 --json state,closedAt,stateReason` |
| Issue label | `human-only` — *"Sadece insan kapatabilir; kanitsiz kapatma yasak"* | `gh issue view 514 --json labels` |
| Audit performed? | **STARTED, NOT DONE** — SR-2 opened 2026-08-12; **2 / 184** Section A cells, **0 / 10** flows; SR-1 never started | §1, §2 below |
| Exit criteria met? | **0 / 4** — all four still `☐` | §5 below |
| Findings committed? | **NO** — the register holds only its placeholder row | §3 below |

**A closed issue is not evidence of a completed audit.** From 2026-08-07 to
2026-08-12 this file recorded the conflict rather than resolving it, because
choosing between the two readings below was a **human** decision an agent could
neither make nor enact — each one either changes the issue's state or adds a
signature. **On 2026-08-12 the owner enacted reading (B)** and re-opened the
issue, stating that the audit was the remaining human-only release gate. Reading
(A) was therefore never taken: **no signed permanent deviation for A-08 exists**,
and none may be written on an agent's initiative.

| Reading | What it would mean | What it requires — human action |
|---|---|---|
| **(A) Deliberate acceptance** | The product owner knowingly accepted shipping without the audit | A **signed permanent deviation** in the D-10 form — named signer, ISO date, explicit scope — recorded in [`v18_visual_deviations.md`](../implementation/v18_visual_deviations.md). **No signer has been supplied, so no such record exists**, and none may be written on an agent's initiative. |
| **(B) Closed in error** — **ENACTED 2026-08-12** | The tracking issue was closed by mistake | A human **re-opens #514**. Done: the owner re-opened it at `2026-08-12T11:08:58Z`. This is the **second** evidence-free closure to be reverted — the first was `2026-07-30T19:05:32Z`, re-opened 2026-08-03. |

Neither reading lets A-08 be reported as done. Under **(A)** what is accepted is
the *absence* of the audit, not a result; under **(B)** — the one taken — the
audit is simply still outstanding, and the session recorded in §1 is the first
work against it. The recurrence is itself the finding: **#514 was closed twice
without a single committed result**, which is why §5's exit criteria — not the
issue's state — are the gate. That cuts both ways: the issue being open again is
no more a result than its being closed was.

---

## 0. Session header — fill one block per combination, before starting

Both blocks are mandatory: `~/.claude/rules/accessibility.md` requires **two**
screen readers, and a single-combination run cannot satisfy A-08.

### SR-1 — NVDA (latest stable) / Firefox / Windows

| Field | Value |
|---|---|
| Auditor (name / role) | — |
| Screen-reader user? (regular user / certified auditor / neither) | — |
| Date (ISO 8601) | — |
| Operating system + version | — |
| Screen reader + version | NVDA (latest stable) — version: — |
| Browser + version | Firefox — version: — |
| Stack commit (`git rev-parse HEAD`) | — |
| Seed flags | `SEED_E2E_GOLDEN=1 SEED_ESP_TA=1 SEED_RATIONALE=1` |
| Stack URL | — |
| Session recording / audio evidence path | — |
| Elapsed time | — |

### SR-2 — VoiceOver / Safari / macOS

| Field | Value |
|---|---|
| Auditor (name / role) | Ali Mirbagirzade (product owner) |
| Screen-reader user? (regular user / certified auditor / neither) | **`neither`** — see the scope limit below |
| Date (ISO 8601) | 2026-08-12 |
| Operating system + version | macOS 15.3 |
| Screen reader + version | VoiceOver (macOS 15.3) |
| Browser + version | Safari 18.3 |
| Stack commit (`git rev-parse HEAD`) | `7dd1dfe` |
| Seed flags | `SEED_E2E_GOLDEN=1 SEED_ESP_TA=1 SEED_RATIONALE=1` |
| Stack URL | `http://127.0.0.1:18280` |
| Session recording / audio evidence path | — (none captured) |
| Elapsed time | **~42 min of recorded session** (`17:46Z` → `18:28Z`, 2026-08-12) — see the caveat |

> **What the elapsed figure is, and is not.** It is the wall-clock span of the
> *recorded* session — first header commit to the auditor stopping — and it is
> the only span anyone measured. The auditor's own time at the machine is **not
> included and was not clocked**: the stack was brought up on their Mac before
> the recording began. Do not use this number to estimate what a full 23-route
> Section A costs; two of 184 cells were filled in it.

> **Scope limit — the auditor is not a screen-reader user.** `neither` is the
> honest answer to the third row and it is recorded rather than smoothed over.
> It does **not** invalidate this session: what an auditor *hears* is the
> evidence A-08 asks for, and a first-time VoiceOver user hears it as well as
> anyone. What it does limit is the *negative* half — an experienced user knows
> which announcements should have come and did not, and notices friction a
> newcomer reads as normal. So a `PASS` in this session means "the expected
> announcement was heard", not "an expert found nothing wrong", and the absence
> of findings on a route is weaker evidence here than a finding is.
>
> **Provenance.** The stack was brought up on the auditor's own Mac, not in an
> agent container: the container this session ran in cannot pull the stack's
> base images (the environment's network policy answers `403` to
> `production.cloudfront.docker.com:443`), so `scripts/a11y-audit-stack.sh up`
> failed there three times and was run by the auditor instead. It reported
> `0 failed`.

---

## 1. Section A — per-page baseline

23 routes × 2 combinations = **46 runs**.

> **Why 23 rows for “22 pages”.** The checklist counts the 22 numbered spec
> documents. Doc 19 contributes **two** routes (`/panel/management`, `/panel/logs`),
> so the route matrix — the same
> `frontend/e2e/utils/screenshotMatrix.ts::TARGET_PAGES` the axe scan walks — is 23
> long. Auditing 22 rows would leave one Admin page unaudited.

Cell values: `PASS` · `FAIL` · `N/A` (state the reason) · `—` (not run).
A `FAIL` **must** carry a finding ID from §3.

- **A-1** — Page title announced on load; exactly one `<h1>`
- **A-2** — Landmark navigation reaches banner / navigation / main / contentinfo
- **A-3** — Heading navigation h1→h2→h3 with no skipped level
- **A-4** — Every interactive element reachable with the virtual cursor
- **A-5** — Buttons announce as button, links as link (no `div onClick`)
- **A-6** — Accessible names of unlabelled controls are meaningful
- **A-7** — Tables read with their `<th scope>` column header
- **A-8** — Decorative images silent (`alt=""`), meaningful images described

### SR-1 — NVDA (latest stable) / Firefox / Windows

| # | Route | Doc | A-1 | A-2 | A-3 | A-4 | A-5 | A-6 | A-7 | A-8 | Finding IDs |
|---:|---|---:|---|---|---|---|---|---|---|---|---|
| 1 | `/` | 1 | — | — | — | — | — | — | — | — | — |
| 2 | `/strategy` | 2 | — | — | — | — | — | — | — | — | — |
| 3 | `/outsource-signal` | 3 | — | — | — | — | — | — | — | — | — |
| 4 | `/trading-signal` | 4 | — | — | — | — | — | — | — | — | — |
| 5 | `/trade-log` | 5 | — | — | — | — | — | — | — | — | — |
| 6 | `/packages/create` | 6 | — | — | — | — | — | — | — | — | — |
| 7 | `/packages/pre-check` | 7 | — | — | — | — | — | — | — | — | — |
| 8 | `/packages/library` | 8 | — | — | — | — | — | — | — | — | — |
| 9 | `/packages/embedded` | 9 | — | — | — | — | — | — | — | — | — |
| 10 | `/rationale-families` | 10 | — | — | — | — | — | — | — | — | — |
| 11 | `/market-data` | 11 | — | — | — | — | — | — | — | — | — |
| 12 | `/research-data` | 12 | — | — | — | — | — | — | — | — | — |
| 13 | `/portfolio` | 13 | — | — | — | — | — | — | — | — | — |
| 14 | `/backtest/ready-check` | 14 | — | — | — | — | — | — | — | — | — |
| 15 | `/backtest/run` | 15 | — | — | — | — | — | — | — | — | — |
| 16 | `/backtest/history` | 16 | — | — | — | — | — | — | — | — | — |
| 17 | `/backtest/metrics` | 17 | — | — | — | — | — | — | — | — | — |
| 18 | `/analysis-lab` | 18 | — | — | — | — | — | — | — | — | — |
| 19 | `/panel/management` *(Admin)* | 19 | — | — | — | — | — | — | — | — | — |
| 20 | `/panel/logs` *(Admin)* | 19 | — | — | — | — | — | — | — | — | — |
| 21 | `/trash` *(Admin)* | 20 | — | — | — | — | — | — | — | — | — |
| 22 | `/user-manual` | 21 | — | — | — | — | — | — | — | — | — |
| 23 | `/future-dev` | 22 | — | — | — | — | — | — | — | — | — |

**SR-1 Section A completion:** 0 / 23 routes.

### SR-2 — VoiceOver / Safari / macOS

| # | Route | Doc | A-1 | A-2 | A-3 | A-4 | A-5 | A-6 | A-7 | A-8 | Finding IDs |
|---:|---|---:|---|---|---|---|---|---|---|---|---|
| 1 | `/` | 1 | PASS | PASS ᴷ³ | — | — | — | — | — | — | — |
| 2 | `/strategy` | 2 | — | — | — | — | — | — | — | — | — |
| 3 | `/outsource-signal` | 3 | — | — | — | — | — | — | — | — | — |
| 4 | `/trading-signal` | 4 | — | — | — | — | — | — | — | — | — |
| 5 | `/trade-log` | 5 | — | — | — | — | — | — | — | — | — |
| 6 | `/packages/create` | 6 | — | — | — | — | — | — | — | — | — |
| 7 | `/packages/pre-check` | 7 | — | — | — | — | — | — | — | — | — |
| 8 | `/packages/library` | 8 | — | — | — | — | — | — | — | — | — |
| 9 | `/packages/embedded` | 9 | — | — | — | — | — | — | — | — | — |
| 10 | `/rationale-families` | 10 | — | — | — | — | — | — | — | — | — |
| 11 | `/market-data` | 11 | — | — | — | — | — | — | — | — | — |
| 12 | `/research-data` | 12 | — | — | — | — | — | — | — | — | — |
| 13 | `/portfolio` | 13 | — | — | — | — | — | — | — | — | — |
| 14 | `/backtest/ready-check` | 14 | — | — | — | — | — | — | — | — | — |
| 15 | `/backtest/run` | 15 | — | — | — | — | — | — | — | — | — |
| 16 | `/backtest/history` | 16 | — | — | — | — | — | — | — | — | — |
| 17 | `/backtest/metrics` | 17 | — | — | — | — | — | — | — | — | — |
| 18 | `/analysis-lab` | 18 | — | — | — | — | — | — | — | — | — |
| 19 | `/panel/management` *(Admin)* | 19 | — | — | — | — | — | — | — | — | — |
| 20 | `/panel/logs` *(Admin)* | 19 | — | — | — | — | — | — | — | — | — |
| 21 | `/trash` *(Admin)* | 20 | — | — | — | — | — | — | — | — | — |
| 22 | `/user-manual` | 21 | — | — | — | — | — | — | — | — | — |
| 23 | `/future-dev` | 22 | — | — | — | — | — | — | — | — | — |

**SR-2 Section A completion:** 0 / 23 routes.

> **`0`, not `1` — route 1 is partial, and partial is not complete.** Route 1
> (`/`) carries A-1 and A-2 and nothing else. A route counts here only when all
> eight checks carry a result, so the two cells it does hold are reported in the
> table rather than rounded up into this counter.

> **ᴷ³ on route 1's A-2.** The auditor navigated the rotor's Landmarks list and
> heard `banner`, `navigation` and `main`. **`contentinfo` was absent** — this
> is K-3, already measured on 23/23 routes, and it is *not* re-filed as a
> finding. `PASS` records the auditor's own judgement that the absence was
> **cosmetic** — it did not impede landmark navigation — and it does **not**
> mean four landmarks were heard. Three were.
>
> **A-3 on route 1 is deliberately `—`, not a result.** Asked whether the
> `h1 → h3` jump misled rotor navigation, the auditor answered *"I didn't
> notice the jump"*, which does not distinguish "navigated the heading list and
> was not misled" (an answer to K-5) from "did not inspect the levels" (no
> answer at all). The cell stays empty until that is settled. **K-5 remains
> open**: nothing here supports re-cutting — or keeping — 21 pages' heading
> outlines.

---

## 2. Section B — Entropia critical flows

10 flows × 2 combinations = **20 runs**.
Flow definitions and why each is critical: checklist §B.

### SR-1 — NVDA (latest stable) / Firefox / Windows

| # | Flow | Route(s) exercised | Result | Finding IDs |
|---|---|---|---|---|
| B-1 | Add menu (Mainboard `+ Add`) | — | — | — |
| B-2 | Add Package popover | — | — | — |
| B-3 | Ready Check result (Passed / Failed / Warnings) | — | — | — |
| B-4 | Backtest RUN progress + SSE events | — | — | — |
| B-5 | Error envelope (`code` / `message` / `remediation`) | — | — | — |
| B-6 | OCC conflict (409) | — | — | — |
| B-7 | File upload (Market Data / Trade Log / Trading Signal / Research Data) | — | — | — |
| B-8 | Trash restore / purge confirmation | — | — | — |
| B-9 | Long tables (Package Library, Results History) | — | — | — |
| B-10 | Login | — | — | — |

**SR-1 Section B completion:** 0 / 10 flows.

### SR-2 — VoiceOver / Safari / macOS

| # | Flow | Route(s) exercised | Result | Finding IDs |
|---|---|---|---|---|
| B-1 | Add menu (Mainboard `+ Add`) | — | — | — |
| B-2 | Add Package popover | — | — | — |
| B-3 | Ready Check result (Passed / Failed / Warnings) | — | — | — |
| B-4 | Backtest RUN progress + SSE events | — | — | — |
| B-5 | Error envelope (`code` / `message` / `remediation`) | — | — | — |
| B-6 | OCC conflict (409) | — | — | — |
| B-7 | File upload (Market Data / Trade Log / Trading Signal / Research Data) | — | — | — |
| B-8 | Trash restore / purge confirmation | — | — | — |
| B-9 | Long tables (Package Library, Results History) | — | — | — |
| B-10 | Login | — | — | — |

**SR-2 Section B completion:** 0 / 10 flows.

---

## 3. Findings register

One row per finding. **Every column is required** — a finding missing its
environment cannot be reproduced, and a finding missing its disposition cannot
be closed. File each one as a GitHub issue with
`.github/ISSUE_TEMPLATE/a11y_screen_reader_finding.yml` and put the issue
number in *Evidence*.

| ID | Auditor | Date | OS | Screen reader + ver | Browser + ver | Route | Flow | Expected | Observed | WCAG SC | Severity | Disposition | PO | Evidence | Retest |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| *(none recorded — audit not run)* | | | | | | | | | | | | | | | |

**Column contract**

| Column | Allowed values / format |
|---|---|
| `ID` | `SR-BULGU-nn`, allocated in order, never reused |
| `Auditor` | Person who heard it. Not a tool name. |
| `Date` | ISO 8601 (`2026-08-06`) |
| `OS` | e.g. `Windows 11 23H2`, `macOS 15.3` |
| `Screen reader + ver` | e.g. `NVDA 2026.1`, `VoiceOver (macOS 15.3)` |
| `Browser + ver` | e.g. `Firefox 141.0`, `Safari 18.3` |
| `Route` | the path from §1, e.g. `/backtest/ready-check` |
| `Flow` | `A-n` / `B-n`, or `—` if neither |
| `Expected` | what the auditor should have heard |
| `Observed` | what was actually heard — verbatim where possible |
| `WCAG SC` | success criterion + level, e.g. `4.1.3 Status Messages (AA)` |
| `Severity` | `blocker` (task impossible) / `major` (task possible, badly) / `minor` |
| `Disposition` | `FIX` or `PO-APPROVE` — no third value |
| `PO` | who signed a `PO-APPROVE`; empty for `FIX` |
| `Evidence` | issue number + audio/recording path |
| `Retest` | `—` until re-verified; then `PASS <date> <auditor>` |

A `PO-APPROVE` is a **signed permanent deviation**, recorded in
[`v18_visual_deviations.md`](../implementation/v18_visual_deviations.md) like D-10.
It is not a way to clear a row.

---

## 4. Retest checklist (run after every FIX lands)

A fix verified by reading the diff is not verified. Each `FIX` returns to the
screen reader that found it.

| # | Step | Done |
|---:|---|---|
| 1 | The FIX is merged to `main` and the audit stack is rebuilt from that commit (`scripts/a11y-audit-stack.sh down && … up`) | ☐ |
| 2 | Fixture validation passes on the rebuilt stack | ☐ |
| 3 | The finding is reproduced **on the same combination that found it** — expected announcement now heard | ☐ |
| 4 | The **other** combination is re-checked on that route (a fix for one SR can break the other) | ☐ |
| 5 | The route's full Section A row is re-run — the fix introduced no new failure | ☐ |
| 6 | Any flow in §2 touching that route is re-run | ☐ |
| 7 | `Retest` column set to `PASS <date> <auditor>`; the issue is closed **by a human** | ☐ |
| 8 | `npm run a11y` (axe ratchet + prechecks) still green on the fix commit | ☐ |

---

## 5. Exit criteria — all four, or A-08 stays open

Copied from the checklist so this file can be read alone:

| # | Criterion | Met |
|---:|---|---|
| 1 | Both SR-1 and SR-2 were run | ☐ (**0 / 2** — SR-2 *started*, not run to completion; SR-1 not started) |
| 2 | Section A complete on all 23 routes; Section B on all 10 flows, for both combinations | ☐ (**0 / 46** routes, **0 / 20** flows — route 1 of SR-2 is partial, and partial ≠ complete) |
| 3 | Every finding carries `FIX` or `PO-APPROVE` | ☐ (no findings recorded yet — vacuous, not satisfied) |
| 4 | Every `FIX` has landed **or** become a PO-signed deviation | ☐ (nothing to land yet — vacuous, not satisfied) |

**No SR-2 session can ever tick criteria 1 or 2 on its own.** Both name *both*
combinations explicitly, and **SR-1 (NVDA / Firefox / Windows) has not been
started**. Even a flawless, complete SR-2 run — 23/23 routes and 10/10 flows —
would leave criterion 1 at `1 / 2` and criterion 2 at `23 / 46` routes. This is
stated here so nobody reads a future "SR-2 complete" line as A-08 nearing done:
**the remaining half is a whole second audit on a different operating system.**

Criteria 3 and 4 are `☐` for a reason worth naming: they are *empty*, not *met*.
Zero findings after 2 of 184 cells is not a clean bill — it is a sample too
small to have produced one.

### Session log

| Session | Combination | Date | Auditor | What was covered | Outcome |
|---|---|---|---|---|---|
| 1 | **SR-2** — VoiceOver / Safari / macOS 15.3 | 2026-08-12 | Ali Mirbagirzade (product owner, `neither`) | Route 1 `/` — A-1, A-2 only | 2 / 184 Section A cells; 0 findings; **K-5 not settled** (A-3 left `—`) |

**Where the next session picks up:** route 1's **A-3** (the `h1 → h3` heading
question, K-5 — read the note under §1's SR-2 table for exactly what was asked
and why the answer did not count), then A-4…A-8, then routes 2–23, then §2's ten
flows. After that, the entire SR-1 combination.

Until all four are `☑`, **no document may show A-08 as `Complete` or `PASS`** —
including this one.

**The tracking issue's state satisfies none of the four — in either direction.**
GitHub #514 was closed on `2026-08-07T03:52:03Z` with this table still at `0 / 4`;
the closure changed the issue's state, not this file's contents, and it added no
auditor, no version string and no finding. Re-opening it on `2026-08-12T11:08:58Z`
added none of those things either. The gate is this table. See the divergence
block in the STATUS banner above.

---

## 6. What the automation already measured — and what it does not mean

`npm run a11y` in `frontend/e2e` runs three things against this same seeded
stack. **None of them is a screen-reader result**, and none may be copied into
§1 or §2:

| Artifact | What it proves | What it does NOT prove |
|---|---|---|
| `specs/13-a11y-scan.spec.ts` (axe-core) | The DOM carries roles, names and contrast ratios within a frozen ceiling | That anything is **announced**, in what order, or intelligibly |
| `specs/14-keyboard-flow.spec.ts` | Login → Mainboard → Add menu is operable with the keyboard alone | Nothing about the virtual cursor, or about what the user hears while doing it |
| `specs/20-a11y-prechecks.spec.ts` | Structural preconditions (no duplicate `<h1>`, landmarks, dialog name + Escape + focus restore) hold, and reports advisory observations | That the structure is *announced usefully*. Its own report stamps `screen_reader_verified: false` on every record. |

The prechecks exist to stop the auditor's first ten minutes being spent on
defects a machine could have found. They shrink the audit's input. They do not
shrink its scope.

### Already-known observations — read before you start

Six of these were **measured** by the precheck run. They are **not** findings —
nobody has heard them yet, and a DOM measurement cannot tell you whether a
screen-reader user is actually impeded. They are where to look first.

**Re-derived 2026-08-12 (ADIM 44)** against a freshly seeded stack as Admin,
**five consecutive runs**: 23 routes, **0 blocking failures**, **90 advisory
observations** once the numbers settle. The figure previously recorded here was
`85`, from the ADIM 28 preparation run.

> **Read the count caveat below before trusting any reach number in this table.**
> Two of the six classes are **not reproducible run to run**; four are rock-stable
> and can be taken at face value. The methodology note under the table says which.

| # | Observation | Reach | Status | What the audit should settle |
|---|---|---|---|---|
| K-1 | **D-10 — 45 accent-blue low-contrast nodes.** PO-signed permanent deviation dated 2026-07-30. WCAG 2.2 AA **1.4.3 is not met**; the product is not compliant for that criterion. | — | Adjudicated — **do not re-file** | Nothing. It is a *low-vision* axis, not a screen-reader one. Record anything **new** you hit. |
| K-2 | **No skip link.** The first tabbable element on every route is the shell's `Log out` button, not an in-page jump target — so each route begins by tabbing the whole menu bar. WCAG 2.4.1. | 23 / 23 routes | Open — reported, not gated | Whether the rotor makes this a non-issue in practice, or whether it really costs a jump per page. |
| K-3 | **No `contentinfo` landmark.** The shell renders no `<footer>`; checklist A-2 expects four landmarks and only three exist. | 23 / 23 routes | Open — reported, not gated | Whether the absence is felt during landmark navigation, or is cosmetic. |
| K-4 | **`/user-manual` has no `<h1>`.** It names itself with `<h2 class="page-title">` (`UserManual.tsx:181`) — a divergence already recorded in `frontend/e2e/utils/pageTruth.ts:15`. Every other route uses `<h1>`. | 1 route | Open — reported, not gated | A-1: is the page title announced on load? |
| K-5 | **Heading outline skips h2 almost everywhere** — `h1 → h3` directly (e.g. `/backtest/run`: `h1 "RUN & Backtest Results" → h3 "Composition"`). This is checklist **A-3**'s exact question, and it is the highest-reach structural observation in the set. | **21 / 23 routes** — re-derived 2026-08-12, **unchanged**; ⚠ see caveat | Open — reported, not gated | A-3: does rotor heading navigation actually mislead, or does the jump read as harmless? Answer this **before** anyone proposes re-cutting 21 pages' outlines. |
| K-6 | **Focus indicator not detectable by computed style** on the probed shell button: `outline: none; box-shadow: none`. The UA default ring may still paint — a computed-style probe cannot see it. WCAG 2.4.7 / 1.4.11. | probe: 1 element | Open — **needs a human eye**, not a machine | Whether a keyboard user can see where focus is. This is precisely the class the automation cannot settle. |
| **K-7** | **No `aria-live` region in the initial DOM** on most routes. The probe reports the *initial* DOM only, so this does **not** mean a status region never appears — it means none is present before anything happens. WCAG 4.1.3 Status Messages (AA). **Measured since ADIM 28 but never listed here**; added 2026-08-12. | **21 / 23 routes** — ⚠ see caveat | Open — reported, not gated | Checklist **B-3 / B-4 / B-6** are exactly this question with a person attached: is the Ready Check verdict announced? the RUN queued→running→completed transition? a 409 OCC conflict? A region injected only at the moment of the update may or may not be announced — that is what you are there to hear. |

K-2 through K-7 are **reported rather than gated on purpose.** Each one's fix is
a product decision — add a footer? promote a heading and re-cut 21 pages'
outlines? mount a persistent status region? — that an audit-preparation change has
no mandate to make, and turning any of them into a red CI gate would be making
that decision by omission. They stay visible in every precheck run's `::warning::`
output and in `a11y-report/precheck-results.json` until a human resolves them.

### How these counts were obtained — and why two of them are a range

Reach counts come from `specs/20-a11y-prechecks.spec.ts` run against a seeded
stack as Admin. The instruction that used to stand here — *"re-run it before the
audit; a stale count is worse than none"* — was **necessary but not sufficient**,
and running it five times in a row is what showed why:

| Class | run 1 | run 2 | run 3 | run 4 | run 5 | Verdict |
|---|---:|---:|---:|---:|---:|---|
| skip link (K-2) | 23 | 23 | 23 | 23 | 23 | **stable** |
| `contentinfo` (K-3) | 23 | 23 | 23 | 23 | 23 | **stable** |
| no `<h1>` (K-4) | 1 | 1 | 1 | 1 | 1 | **stable** |
| focus indicator (K-6) | 1 | 1 | 1 | 1 | 1 | **stable** |
| heading outline (K-5) | 18 | 21 | 20 | 21 | 21 | ⚠ **converges to 21** |
| `aria-live` (K-7) | 10 | 20 | 20 | 21 | 21 | ⚠ **converges to 21** |
| **total advisories** | 76 | 89 | 88 | 90 | 90 | ⚠ **converges to 90** |

Same commit, same stack, same seed, same Admin. Two rules follow, and both matter
more than the numbers themselves:

1. **Discard the first run after `scripts/a11y-audit-stack.sh up`.** It is cold and
   it *under-reports* — run 1 claimed 18 routes for K-5 where the settled answer is
   21. A single cold re-run would have "refreshed" this table into being **less**
   accurate than it already was. Run it at least twice and take the later figure.
2. **A residual flake survives warm-up.** `/analysis-lab`, `/backtest/history` and
   `/backtest/metrics` flip between runs on both unstable classes, and
   `/analysis-lab` flips even between two warm runs. Treat "21 / 23" as *"21, ±1,
   and you know which three routes the ±1 lives on."*

**Why:** the probe reads the *initial* DOM, so it races the pages' first data
render — a route caught mid-load shows neither its `h3` section headings nor its
loading status region, and drops out of both counts. That is a defect in the
*measurement*, not in the product, and it is **recorded here rather than fixed**:
changing when the probe samples would silently change what K-5 and K-7 mean, and
those two are the observations the human audit exists to adjudicate. The remedy
when someone does take it on deliberately is to settle the page before probing
(await the route's data, not a fixed timeout) — and to re-baseline this table in
the same commit.

**None of this is a screen-reader result.** A count that varies by cache warmth is
still a DOM count.

