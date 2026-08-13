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
> `2026-08-12T11:08:58Z` (`state_reason: reopened`) expressly to run this audit.
> The closure/evidence divergence this file used to carry is therefore
> **RESOLVED — by reading (B)**; the record of it is kept below as history, not
> as a live conflict. **This changes the tracking state and nothing else:** the
> four exit criteria are still `0 / 4` and A-08 is still `HUMAN-BLOCKED`. The
> worksheet did stop being empty on the same day, but that is the SR-2 session
> recorded in §1 — **2 of 184 cells** — not the issue's state moving. `#514`
> carries the `human-only` label; an agent or automated scan must not close it —
> nor re-open it.
>
> Recipe and rationale: [`a11y_screen_reader_audit_checklist.md`](../implementation/a11y_screen_reader_audit_checklist.md).
> Environment: `scripts/a11y-audit-stack.sh up`.

### Tracking-issue state — divergence RESOLVED 2026-08-12 (recorded 2026-08-07)

This block is the **canonical record** of the tracking-issue state. Every other
document points here instead of restating it.

| Fact | Value | How to re-derive |
|---|---|---|
| GitHub **#514** state | **OPEN** — re-opened `2026-08-12T11:08:58Z`, `state_reason: reopened` | `gh issue view 514 --json state,stateReason,updatedAt` |
| Issue label | `human-only` — *"Sadece insan kapatabilir; kanitsiz kapatma yasak"* | `gh issue view 514 --json labels` |
| Audit performed? | **STARTED, NOT DONE** — SR-2 opened 2026-08-12; **2 / 184** Section A cells, **0 / 10** flows; SR-1 never started | §1, §2 below |
| Exit criteria met? | **0 / 4** — all four still `☐` | §5 below |
| Findings committed? | **NO** — the register holds only its placeholder row | §3 below |

**The divergence is closed; the blocker is not.** From 2026-08-07 to 2026-08-12
this file recorded a conflict — the issue said `COMPLETED` while this worksheet
was empty. On `2026-08-12T11:08:58Z` a human resolved it by taking **reading
(B)**: re-opening #514 with the reason recorded on the issue itself —

> *"Reopened 2026-08-12 to run path (A) of the RC readiness report §6.1 … The
> 2026-08-07T03:52:03Z closure carried stateReason=COMPLETED while the worksheet
> was empty — 0/4 exit criteria, 0/46 routes, 0/20 flows, 0 recorded SR-BULGU.
> No signed permanent deviation exists for A-08. The audit stack is prepared and
> validated; auditor assignment is the remaining human step."*

**Only the tracking state moved.** Re-opening the issue is not a result any more
than closing it was: it added no auditor, no version string and no finding. The
gate is §5's four criteria, which are still `0 / 4`.

> **Mind the lettering — the two documents number their options in opposite
> directions.** In *this* file's table below, **(A)** = signed acceptance and
> **(B)** = the erroneous closure being reverted. In the readiness report
> ([`Entropia_V18_RC_Readiness_2026-08-07.md`](../releases/Entropia_V18_RC_Readiness_2026-08-07.md)
> §6.1), **(A)** = run the audit and **(B)** = signed deviation. The issue comment
> quoted above says *"path (A)"* in the **report's** sense — run the audit. Same
> two outcomes, two numberings; neither file was renumbered, because both are
> cited by ID elsewhere.

| Reading | Status | What it meant |
|---|---|---|
| **(A) Deliberate acceptance** | **NOT TAKEN** | Would have required a **signed permanent deviation** in the D-10 form — named signer, ISO date, explicit scope — in [`v18_visual_deviations.md`](../implementation/v18_visual_deviations.md). No signer was ever supplied, so **no such record exists**; none may be written on an agent's initiative. |
| **(B) Closed in error** | **TAKEN — 2026-08-12** | A human re-opened #514. This is the **second** evidence-free closure to be reverted; the first was `2026-07-30T19:05:32Z`, re-opened 2026-08-03. |

The recurrence stands as the finding: **#514 was closed twice without a single
committed result, and both closures had to be reverted.** That is why §5's exit
criteria — not the issue's state — are the gate. Under (B) the audit is simply
still outstanding, which is exactly where A-08 sits today.

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
GitHub #514 was closed on `2026-08-07T03:52:03Z` and re-opened on
`2026-08-12T11:08:58Z` with this table at `0 / 4` both times. Each move changed
the issue's state, not this file's contents; neither added an auditor, a version
string or a finding. The gate is this table. See the tracking-issue block in the
STATUS banner above.

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

**Re-measured again 2026-08-12 (ADIM 48, after K-2 + K-4 landed)** — CI job
`94221023796`, a **single cold run** on a fresh stack: 23 routes, **0 blocking
failures**, **67 advisory observations**. The drop is fully accounted for and
nothing was suppressed:

| Class | ADIM 44 (settled) | ADIM 48 (CI) | Why |
|---|---:|---:|---|
| skip link (K-2) | 23 | **0** | fixed — the class no longer fires on any route |
| no `<h1>` (K-4) | 1 | **0** | fixed |
| heading outline (K-5) | 21 | **22** | **+1: `/user-manual`**, moved in by K-4's fix |
| `contentinfo` (K-3) | 23 | 23 | untouched |
| `aria-live` (K-7) | 21 | 21 | untouched |
| focus indicator (K-6) | 1 | 1 | untouched |
| **total** | **90** | **67** | −23 −1 +1 |

**Two caveats that keep this honest.** (1) This is **one cold run**, and rule 1 below
says a cold run *under-reports* — so `22` for K-5 is a **floor**, not a settled figure;
the three flaky routes (`/analysis-lab`, `/backtest/history`, `/backtest/metrics`) all
happened to report in this run. (2) The `/user-manual` line is not an inference from
the count: the run printed the skip verbatim, which is what makes K-4's side effect a
**measurement** rather than a prediction.

> **Read the count caveat below before trusting any reach number in this table.**
> Two of the six classes are **not reproducible run to run**; four are rock-stable
> and can be taken at face value. The methodology note under the table says which.

| # | Observation | Reach | Status | What the audit should settle |
|---|---|---|---|---|
| K-1 | **D-10 — 45 accent-blue low-contrast nodes.** PO-signed permanent deviation dated 2026-07-30. WCAG 2.2 AA **1.4.3 is not met**; the product is not compliant for that criterion. | — | Adjudicated — **do not re-file** | Nothing. It is a *low-vision* axis, not a screen-reader one. Record anything **new** you hit. |
| K-2 | ~~**No skip link.** The first tabbable element on every route is the shell's `Log out` button, not an in-page jump target — so each route begins by tabbing the whole menu bar. WCAG 2.4.1.~~ → **FIXED 2026-08-12 (PO decision, PR #685).** `Layout.tsx` renders a clipped `Skip to main content` link as the shell's first child; `<main>` carries `id="main-content"` + `tabIndex={-1}`. **Recorded with the fix:** 2.4.1 was **already met** through the banner/navigation/main landmarks (technique ARIA11) — which is why axe's `bypass` rule stayed green throughout — so this was an **ergonomics** fix for keyboard users, not a conformance one. | was 23 / 23 routes | **FIXED** | Nothing structural. If the link is announced misleadingly (wrong name, wrong destination), file it as a **new** finding. |
| K-3 | **No `contentinfo` landmark.** The shell renders no `<footer>`; checklist A-2 expects four landmarks and only three exist. | 23 / 23 routes | Open — reported, not gated | Whether the absence is felt during landmark navigation, or is cosmetic. |
| K-4 | ~~**`/user-manual` has no `<h1>`.** It names itself with `<h2 class="page-title">` (`UserManual.tsx:181`).~~ → **FIXED 2026-08-12 (PO decision, PR #685).** The page now uses `<h1 class="page-title">` like the other 22 routes; `.page-title` is class-based, so the change is semantic only. Regression pin: `specs/17-page-coverage.spec.ts` declares `level: 1` (a *blocking* precheck for a missing `<h1>` was considered and **deliberately not added** — that probe races each page's first data render, and a flapping gate is worse than none). **Side effect, not hidden:** this page's outline is now `h1 → h3` where it was `h2 → h3`, so it **entered K-5's set** — measured, not predicted: CI job `94221023796` printed `/user-manual — heading outline: h1 "User Manual" -> h3 "ENTROPIA USER MANUAL"`, taking K-5 from `21 / 23` to `22 / 23`. | was 1 route | **FIXED** | A-1 still applies: is the page title announced on load? The fix changed the level, not the announcement. |
| K-5 | **Heading outline skips h2 almost everywhere** — `h1 → h3` directly (e.g. `/backtest/run`: `h1 "RUN & Backtest Results" → h3 "Composition"`). This is checklist **A-3**'s exact question, and it is now — with K-2 and K-4 fixed — the highest-reach observation left in the set. **`/market-data` skips two levels** (`h1 → h4`) and `/packages/library` carries a second skip (`h2 "Import package" → h5 "Recent imports"`). | **22 / 23 routes** — re-measured 2026-08-12 (ADIM 48, CI job `94221023796`); was `21 / 23`. **The +1 is `/user-manual`**, which K-4's fix moved into this set (`h1 "User Manual" → h3 "ENTROPIA USER MANUAL"`) — a known, accepted cost, not a discovery. Only `/` is now outside the set. ⚠ see caveat | Open — reported, not gated | A-3: does rotor heading navigation actually mislead, or does the jump read as harmless? Answer this **before** anyone proposes re-cutting 22 pages' outlines — the measured cost of doing so is **204 headings across ~40 files**, plus five tag-scoped CSS rules (`.card h3`, `.card h4`, `.ready-report-card h3`, `.state h3`, `.manual-drawer-header h3`) that silently drop a heading to the UA default if a tag moves without them. |
| K-6a | **Focus indicator not detectable by computed style** on the probed shell button: `outline: none; box-shadow: none`. The UA default ring may still paint — a computed-style probe cannot see it. WCAG 2.4.7. | probe: 1 element | Open — **needs a human eye**, not a machine | Whether a keyboard user can see where focus is. This is precisely the class the automation cannot settle. **A-08 settles this one; nothing else does.** |
| K-6b | **Focus-ring contrast below WCAG 1.4.11 Non-text Contrast (AA).** `global.css :focus-visible` painted `2px solid var(--accent)`, and **#00a9e8 measures 2.68:1 on white / 2.46:1 on #f5f5f5** — a focus indicator is a non-text UI component and owes **3:1**. Nothing in the repo measured this: axe does not run a focus-ring contrast rule, and the green ratchet was never evidence. **Separate criterion from K-1/D-10**, which is the 1.4.3 *text* axis. | every focusable node, 23 / 23 routes | **CLOSED 2026-08-12** — ring re-pointed to `var(--text)` (`#222222`) | Nothing. **Measured after the change:** 15.91:1 on white, 14.59:1 on #f5f5f5, 12.98:1 on the #e8e8e8 title bar, 5.94:1 on the #00a9e8 `dropdown-blue` panel, 4.92:1 on the #8f8f8f dropdown panel, and **4.50:1 on the #0092c8 menu-blue hover — the worst surface in the app**. All ≥ 3:1. `--accent` itself was not touched. |
| **K-7** | **No `aria-live` region in the initial DOM** on most routes. The probe reports the *initial* DOM only, so this does **not** mean a status region never appears — it means none is present before anything happens. WCAG 4.1.3 Status Messages (AA). **Measured since ADIM 28 but never listed here**; added 2026-08-12. | **21 / 23 routes** — ⚠ see caveat | Open — reported, not gated | Checklist **B-3 / B-4 / B-6** are exactly this question with a person attached: is the Ready Check verdict announced? the RUN queued→running→completed transition? a 409 OCC conflict? A region injected only at the moment of the update may or may not be announced — that is what you are there to hear. |

> **Three superseded rows were removed from this table on 2026-08-13** — it had carried
> **eight IDs in eleven rows** since PR #685. That PR (`ce823a8`) inserted updated `K-2`,
> `K-4` and `K-5` rows *plus a pre-split bare `K-6`*, without removing the rows they
> replaced and without seeing that `#688` (`04c6a9c`) had split `K-6` into `K-6a`/`K-6b`
> the previous evening. The result was a table that showed **`K-4` as FIXED and as Open**,
> **`K-5` at 22 / 23 and at 21 / 23**, and a `K-6` whose own explanatory paragraph below
> speaks only of `K-6a`/`K-6b`. The rows deleted are the **older** three in each pair
> (`K-4` Open, `K-5` 21 / 23, bare `K-6`); **no status, reach or wording of a surviving row
> was touched**, and the eight IDs above are now unique. Recorded rather than done
> silently: this is the canonical block every other document points at, so a reader who
> remembers eleven rows is owed the reason there are now eight.

K-2 through K-7 are **reported rather than gated on purpose** — with **K-6b as the
one exception**, and the exception is instructive about where the line is. Each of
the others' fixes is a product decision — add a footer? promote a heading and
re-cut 21 pages' outlines? mount a persistent status region? — that an
audit-preparation change has no mandate to make, and turning any of them into a
red CI gate would be making that decision by omission. K-6b was not a product
decision: 3:1 is a numeric AA threshold, the ring colour is not described by the
v18 mockup (which has no focus state at all), and the fix is one declaration that
changes no layout. That is why it could be closed here while K-6a — *can a person
see it?* — stays open for A-08. They stay visible in every precheck run's `::warning::`
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
| focus indicator (K-6a) | 1 | 1 | 1 | 1 | 1 | **stable** |
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

