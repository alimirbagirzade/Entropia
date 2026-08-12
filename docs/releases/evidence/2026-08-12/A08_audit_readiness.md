<!-- doc-status: historical -->
# A-08 — the audit is now RUNNABLE. It has still not been run.

**Slice:** ADIM 44 · **Date:** 2026-08-12 · **Base:** `e719af1` (origin/main)
**Verdict:** RC blocker **(1) STAYS OPEN.** Exit criteria **0 / 4**. Nothing below is
a screen-reader result, and none of it may be transcribed into §1, §2 or §3 of
`docs/audit/a11y_screen_reader_audit_results.md`.

## 1. Does the stack still come up on current main? — YES, 9 / 9

The last verification was at `1f4b88b`. `main` has moved nine slices since (ADIM 30–43:
harness, CSP, Dockerfile, schema parity, visual coverage, Lighthouse). Measured, not
assumed — full transcript in `a08_audit_stack_validation.txt`:

```
$ scripts/a11y-audit-stack.sh up
  PASS  stack is up                        PASS  /me reports is_admin=true
  PASS  seed exit 0                        PASS  SEED_E2E_GOLDEN — market datasets present (1)
  PASS  API ready at …:18200/api/v1        PASS  SEED_E2E_GOLDEN/SEED_ESP_TA — Package Library (13)
  PASS  web app served at …:18280          PASS  SEED_RATIONALE — rationale families present (6)
  PASS  /meta.auth_mode=session            PASS  23/23 routes served
  PASS  Admin session obtained
========== RESULT ==========   9 passed, 0 failed
```

**Nothing needed fixing.** No auditor appointment is blocked on the environment.

## 2. Precheck counts refreshed — and one of them refused to hold still

Run as Admin against that seeded stack. The worksheet said *"Re-run it before the
audit — a stale count is worse than none."* That instruction was necessary but not
sufficient, which only running it **five times** revealed:

| Class | run 1 | run 2 | run 3 | run 4 | run 5 | |
|---|---:|---:|---:|---:|---:|---|
| skip link (K-2) | 23 | 23 | 23 | 23 | 23 | stable |
| `contentinfo` (K-3) | 23 | 23 | 23 | 23 | 23 | stable |
| no `<h1>` (K-4) | 1 | 1 | 1 | 1 | 1 | stable |
| focus indicator (K-6) | 1 | 1 | 1 | 1 | 1 | stable |
| heading outline (K-5) | **18** | 21 | 20 | 21 | 21 | ⚠ converges to **21** |
| `aria-live` (K-7) | **10** | 20 | 20 | 21 | 21 | ⚠ converges to **21** |
| total advisories | 76 | 89 | 88 | 90 | 90 | ⚠ converges to **90** |

Same commit, same stack, same seed, same Admin. Blocking failures: **0** in all five.

**The single most useful thing measured this slice:** run 1 is cold and
**under-reports**. Had the count been "refreshed" from one run — exactly what the
worksheet's own instruction invites — K-5 would have been rewritten from `21/23` to
`18/23`, i.e. the refresh would have made the table **less** accurate than the stale
figure it replaced. The worksheet's existing `21/23` was correct all along.

A residual flake survives warm-up on three named routes — `/analysis-lab`,
`/backtest/history`, `/backtest/metrics` — and `/analysis-lab` flips between two warm
runs. So the honest form is *"21, ±1, on three known routes."*

**Cause:** the probe reads the *initial* DOM and races each page's first data render.
A route caught mid-load shows neither its `h3` section headings nor its loading status
region, and drops out of both counts.

**Recorded, not fixed** — deliberately. Changing when the probe samples would silently
change what K-5 and K-7 *mean*, and those two are precisely what the human audit
exists to adjudicate; K-2…K-7 are out of gate on purpose (RC §6.5). The remedy, when
someone takes it on deliberately, is to settle the route's data before probing (not a
fixed timeout) and re-baseline the table in the same commit.

## 3. K-7 — an observation that was measured but never listed

`aria-live inventory: no live region in the initial DOM`, **21 / 23 routes**, WCAG
4.1.3 (AA). It has been in `precheck-results.json` since ADIM 28 and had **no row** in
the worksheet's "where to look first" table. It is the second-highest-reach
observation in the set, and it maps onto checklist **B-3 / B-4 / B-6** — the Ready
Check verdict, the RUN `queued→running→completed` transition, and the 409 OCC
conflict. Added as **K-7**.

It does **not** mean no status region ever appears; the probe only sees the initial
DOM. Whether a region injected at update time is announced is a question for a person.

## 4. Auditor runbook

`docs/implementation/a11y_screen_reader_audit_runbook.md` — one page, English (the
auditor may be external; the worksheet they fill is English too). Stack bring-up
including the remote-screen-reader case (`A11Y_HOST=<LAN IP>` — NVDA is on Windows,
the stack usually is not), Admin sign-in, the 23 routes in worksheet order, the 10
Section-B flows, how to allocate `SR-BULGU-nn` and file it through
`.github/ISSUE_TEMPLATE/a11y_screen_reader_finding.yml`, the session-header fields to
fill before starting, and four things not to do.

## 5. What this slice did NOT do

* **The audit.** Not run. Exit criteria **0 / 4**; §1, §2 and §3 untouched and empty.
* **GitHub #514.** Not touched. It carries `human-only`; it is closed while the
  worksheet is empty, and that divergence stands exactly as recorded.
* **K-2…K-7.** Not fixed. Each remedy is a product decision, and K-5/K-6/K-7 are
  questions the audit is supposed to answer first.
* **D-10.** Untouched, and unrelated — it is the low-vision axis (WCAG 1.4.3) only.

An empty template is not evidence. A verified environment is not an audit.
