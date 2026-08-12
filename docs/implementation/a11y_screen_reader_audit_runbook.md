<!-- doc-status: historical -->
> **HISTORICAL RECORD — this is not the live slice handoff.** It records the audit
> procedure as of the date below. Current authority: `CLAUDE.md` §Current position +
> `docs/generated/repository_facts.md` (generated, gated in CI with `--check`).
> The one number here that rots is the route count; re-derive it from
> `frontend/e2e/utils/screenshotMatrix.ts::TARGET_PAGES` (a contract test pins it).

# A-08 — auditor runbook (read this first, it is one page)

> **Written in English on purpose.** The rest of this repository documents itself in
> Turkish; this file is handed to the person doing the audit, who may be an external
> screen-reader professional, and it is the companion to
> [`a11y_screen_reader_audit_results.md`](../audit/a11y_screen_reader_audit_results.md),
> which is also English.

**Your job:** drive this product with a real screen reader and write down what you
hear. Nothing in this repository substitutes for that. The automated checks (axe-core,
keyboard flow, structural prechecks) already ran; they measure the DOM, not the
announcement, and **no output of theirs may be copied into the results worksheet.**

**Budget:** two combinations × (23 routes + 10 flows). Expect two sessions, not one.
Partial is fine and expected — record what you did, leave the rest `—`. A half-filled
worksheet is evidence; an empty one is not.

---

## 1. Before you start (5 minutes)

You need **both** combinations. One is not enough and never becomes enough:

| # | Screen reader | Browser | Platform |
|---|---|---|---|
| **SR-1** | NVDA, latest stable | Firefox | Windows |
| **SR-2** | VoiceOver | Safari | macOS |

Open these two files side by side and keep them open:

* **Worksheet** — `docs/audit/a11y_screen_reader_audit_results.md` — where results go.
* **Checklist** — `docs/implementation/a11y_screen_reader_audit_checklist.md` — what
  each check (A-1…A-8, B-1…B-10) actually asks.

---

## 2. Bring the stack up (one command)

Requires Docker. From the repository root:

```bash
scripts/a11y-audit-stack.sh up
```

It builds, starts, seeds the three fixtures, and then validates that the fixtures
landed. **It must end with `0 failed`.** If it does not, stop — you would be auditing
empty pages for a seeding reason rather than a product reason. It prints the web URL,
the API URL and the Admin credentials on success.

**Running the screen reader on a different machine** (the usual case: the stack on
macOS, NVDA on a Windows box). Pass the host's LAN address — one knob, and it must be
an address the auditor's browser can actually open:

```bash
A11Y_HOST=192.168.1.20 scripts/a11y-audit-stack.sh up
```

`0.0.0.0` is rejected on purpose: it is a bind address, not a reachable one, and it
would bake an unopenable URL into the web bundle and the CORS allowlist.

Useful afterwards — neither re-builds anything:

```bash
scripts/a11y-audit-stack.sh validate   # re-check the fixtures mid-session
scripts/a11y-audit-stack.sh status     # what is running, where
```

**The stack stays up until you tear it down.** That is deliberate — an automatic
teardown would destroy your session the moment the script returned.

## 3. Sign in

Sign in as the **Admin** printed by the `up` output. Admin is not optional: `/trash`,
`/panel/management` and `/panel/logs` do not render without it, and they are three of
the routes on the list.

---

## 4. Order of work

**Section A first, all 23 routes, then Section B.** Section A teaches you the shell;
Section B assumes you already know how it announces.

The 23 routes, in the order the worksheet lists them. "22 pages" elsewhere counts spec
*documents* — doc 19 contributes two routes, so the route list is 23 long:

| # | Route | # | Route |
|---:|---|---:|---|
| 1 | `/` | 13 | `/portfolio` |
| 2 | `/strategy` | 14 | `/backtest/ready-check` |
| 3 | `/outsource-signal` | 15 | `/backtest/run` |
| 4 | `/trading-signal` | 16 | `/backtest/history` |
| 5 | `/trade-log` | 17 | `/backtest/metrics` |
| 6 | `/packages/create` | 18 | `/analysis-lab` |
| 7 | `/packages/pre-check` | 19 | `/panel/management` *(Admin)* |
| 8 | `/packages/library` | 20 | `/panel/logs` *(Admin)* |
| 9 | `/packages/embedded` | 21 | `/trash` *(Admin)* |
| 10 | `/rationale-families` | 22 | `/user-manual` |
| 11 | `/market-data` | 23 | `/future-dev` |
| 12 | `/research-data` | | |

Then the 10 flows, checklist section B: **B-1** Add menu · **B-2** Add Package popover
· **B-3** Ready Check result · **B-4** Backtest RUN progress + SSE · **B-5** error
envelope (`code` / `message` / `remediation`) · **B-6** OCC conflict (409) · **B-7**
file upload + rejected file type · **B-8** Trash restore/purge confirmation · **B-9**
long tables · **B-10** Login.

**Where to look first.** The preparation already measured six structural observations
(K-2…K-7) in the worksheet's *"Already-known observations"* table. They are **not**
findings — nobody has heard them. They are the highest-yield places to point a screen
reader. Three of them can only be settled by you, and product decisions are waiting on
your answer: **K-5** (does the `h1 → h3` jump actually mislead rotor navigation?),
**K-6** (can you see where focus is?) and **K-7** (do the Ready Check verdict, the RUN
state change and a 409 conflict get announced at all?).

**If you re-run the prechecks yourself, run them twice and use the second result.** The
probe races the pages' first data render, so the first run after `up` under-reports —
by three routes on K-5 and eleven on K-7 in the measured case. The worksheet's
methodology note carries the five-run spread and names the three routes that stay
flaky even warm.

---

## 5. Recording what you hear

**Per session, before you start:** fill the session header block in worksheet §0 for
the combination you are running — auditor, screen-reader version, browser version, OS,
date. A result with no version string cannot be reproduced later.

**Per check:** fill the cell in worksheet §1 (Section A) or §2 (Section B). Leave `—`
for anything you did not run. Do not guess.

**Per defect:** allocate the next `SR-BULGU-nn` in the worksheet's §3 findings
register, then open a GitHub issue with the **A11Y — screen-reader finding (A-08)**
template (`.github/ISSUE_TEMPLATE/a11y_screen_reader_finding.yml`). Every field of
that template maps one-to-one onto a register column, so the issue and the worksheet
cannot drift. Each finding needs a status: **FIX** or **PO-APPROVE**.

An axe-core violation is not a screen-reader finding — file those as ordinary bugs.

---

## 6. Four things not to do

1. **Do not copy any automated output into §1, §2 or §3.** An empty template is not
   evidence, and a template filled from a DOM scan is worse: it looks like evidence.
2. **Do not re-file K-1.** The 45 accent-blue low-contrast nodes are a PO-signed
   permanent deviation (D-10, 2026-07-30) on the *low-vision* axis. Record anything
   **new** you hit, not that.
3. **Do not touch GitHub #514.** It carries the `human-only` label. It is currently
   closed while the worksheet is empty — that divergence is recorded, not resolved,
   and resolving it is a product-owner decision.
4. **Do not fix K-2…K-6 on the way past.** Each one's remedy is a product decision
   (add a footer? re-cut 21 pages' heading outlines?) and K-5/K-6 are precisely what
   your session is meant to answer first.

## 7. When you stop

```bash
scripts/a11y-audit-stack.sh down    # removes the volumes; the seeded data is gone
```

A-08 closes only when all four of worksheet §5's exit criteria are `☑`: both
combinations run; Section A complete on all 23 routes and Section B on all 10 flows,
for both; every finding carrying FIX or PO-APPROVE; every FIX landed or converted into
a PO-signed deviation. **Until then no document may show A-08 as Complete, PASS or
Done — and closing the tracking issue satisfies none of the four.**
