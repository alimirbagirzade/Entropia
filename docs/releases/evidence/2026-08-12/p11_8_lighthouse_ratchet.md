# P11-8 — Lighthouse, wired as a ratchet

**2026-08-12 (ADIM 43).** RC readiness §6.7 recorded P11-8 as *"Lighthouse hâlâ bağlı
değil"*. That was true. This records what was built, what was deliberately **not** built,
and the two authority collisions that had to be prevented rather than discovered later.

## 1. Why a ratchet and not a score threshold

The obvious wiring — "fail under 90" — was rejected before it was written. A number
nobody measured is either so low it can never fail or so high it fails on weather, and
this repository has already written down what happens to a gate that fails on weather
(`docs/performance/README.md` §1: *"a gate that can never fail is worse than no gate at
all"*). It has also already answered the question twice, the same way both times:
`frontend/e2e/a11y-baseline.json` freezes measured axe node counts, and ADIM 42's
`acceptance_coverage_baseline.json` freezes measured criterion counts.

So the third instance uses the second one's shape rather than inventing a pattern:
**today's measured score is the floor; it may only rise; no margin is subtracted.**

## 2. Scope — every audited route, no silent subset

`TARGET_PAGES` in `frontend/e2e/utils/screenshotMatrix.ts` is the single source of the
route list — the same list the axe scan, the keyboard probes and (since ADIM 39) the
visual regression suite walk. This gate does **not** write its own list and does **not**
subset it.

| | |
|---|---|
| Routes in `TARGET_PAGES` | **23** |
| Routes scored | **23** |
| Routes uncovered | **0** |

A route present in the matrix but absent from the baseline's `floors` **fails**, with a
message telling the author to baseline it. An unbaselined route is a hole, not a pass —
this is the one mechanism that stops the gate quietly shrinking as pages are added.

## 3. Noise is answered by stabilisation, not by tolerance

Lighthouse on a 2-vCPU shared runner is noisy. The two honest responses are to stabilise
the measurement or to admit the category cannot be gated. Widening a band until the gate
stops complaining is neither, so it was not done. What the spec does instead:

* **a discarded warm-up run** before the first scored route, so the first page in the
  matrix does not absorb V8 warm-up, first paint of the bundle and a cold HTTP cache;
* **median of `LH_REPEATS` (default 3) passes** per route, so one unlucky pass cannot
  move the reported score;
* **the observed repeat spread is printed and uploaded** with every run, so any future
  decision about whether a category can be gated at all starts from data.

`cpuSlowdownMultiplier` is **1**, not Lighthouse's default 4x mobile slowdown: the runner
is already slow, and modelling a device nobody has would widen exactly the noise this
gate has to survive.

## 4. Authority collision 1 — accessibility

axe-core is the shipped a11y authority: per-page, per-rule node ceilings, with a written
adjudication record (`docs/implementation/a11y_ci_ratchet_and_adjudication.md`) and a
signed permanent deviation (D-10) behind the 45 residual contrast nodes. A Lighthouse
accessibility score is a coarser number over the same DOM, and it can disagree.

**Resolution: the category is not requested at all.** `CATEGORIES` in
`specs/21-lighthouse.spec.ts` is `performance, best-practices, seo`. There is no
Lighthouse a11y number to disagree with axe, because none is produced.

**And the absolute rule, stated in three places** (spec header, baseline `policy` block,
this file): **no Lighthouse output is A-08 evidence.** The screen-reader audit ledger
(`docs/audit/a11y_screen_reader_audit_results.md`) records what a human heard with NVDA or
VoiceOver. No DOM scanner — axe included — can write to its §1 or §2. A11Y-08 remains
**not done**, its ledger remains **empty**, its four exit criteria remain unticked, and
nothing in this slice changes any of that.

## 5. Authority collision 2 — performance

`scripts/loadgen.py` already measures performance, and P10-7 in this same slice arms a
latency gate on it. Two performance gates that can disagree is exactly the failure mode
this repo keeps writing up, so the demarcation is written into **both** docs rather than
left implicit:

| | `loadgen.py` (P10) | Lighthouse (P11-8) |
|---|---|---|
| Subject | the **server** | the **browser** |
| Question | did the application's own work get more expensive? | did the page get slower to paint and become interactive? |
| Measures | per-endpoint HTTP p95, control-normalised | FCP / LCP / TBT / CLS / SI rolled into a category score |
| Unit of comparison | one API scenario | one route |
| Runs | nightly, `performance.yml` → `load-full` | per PR, `e2e.yml` → `lighthouse` |
| Fails on | ratio vs. frozen baseline > 2.5x | median score below frozen floor |

`docs/performance/README.md` §8 had already named *"frontend rendering"* as explicitly
outside the load driver's scope. This gate fills that declared gap — it is the missing
half, not a second opinion. **A green nightly says nothing about a bundle regression, and
a green Lighthouse score says nothing about a query that doubled.** Neither may be cited
for the other's question.

## 6. What this gate cannot see (mirrored into every report it writes)

* **The trace is cut at 20 s.** The SPA holds a persistent SSE stream, so Lighthouse's
  network-quiet condition can never fire — the same reason `specs/09` and `specs/13`
  cannot use `networkidle`. FCP and LCP land long before the cut; whatever a route does
  after it is not measured here.
* **Simulated throttling models the network from the trace.** It does not reproduce a
  real slow device, and a score is only comparable inside its own runner class — the same
  constraint `docs/performance/README.md` §2 records for the load baseline.
* **Raw metrics are reported, not gated.** A category score is a bounded, quantised
  number and survives being ratcheted; a raw millisecond on a shared runner is the
  weather §1 refuses to gate on. FCP/LCP/TBT/CLS/SI are in the artefact so a failing
  score can be diagnosed, and for no other purpose.
* **Any performance defect it finds is left open.** This is a CI/gate slice; product code
  is untouched. A low score is recorded at its measured value and fixed in its own PR.

## 7. Bootstrap: the gate ships UNARMED, on purpose

`frontend/e2e/lighthouse-baseline.json` lands with `"armed": false` and empty `floors`.

A floor written before the job has ever run would be the arbitrary threshold §1 of this
document rejects. So the first CI run **measures**: it walks all 23 routes, prints the
per-route scores and the repeat spread, writes
`lighthouse-report/lighthouse-baseline.measured.json`, gates **nothing**, and says so with
an explicit `::warning::`. A second commit freezes those floors and sets `"armed": true`.

An unarmed gate is loud. A **missing** baseline file is still a hard failure — a deleted
or unreadable baseline must never degrade into "every score is allowed".

## 8. What the bootstrap run measured

Run `31571413853`, job `94034026749`, branch `ci/rc-p11p8-lighthouse-and-latency-baseline`,
commit `d169912`. Job wall clock **9 m 48 s** end to end (stack boot, npm and browser
install included); the ratchet step itself **7.6 min** for 23 routes x 3 passes plus the
warm-up — 70 Lighthouse runs. Comfortably inside the 75-minute timeout, so the full matrix
was affordable and **no subset was ever needed**.

| Category | Frozen floor |
|---|---|
| `performance` | **100** on 22 routes, **98** on `panel-management` |
| `best-practices` | **96** on all 23 |
| `seo` | **82** on all 23 |

**Worst repeat spread in that run: 0 points, in every category, on every route.**

That number is true of the run and **false as a description of the gate**, which the very
next run proved — see §10. It is left here as measured rather than quietly upgraded into a
property, because "zero spread" as a general claim is exactly the kind of sentence that
ages badly and then gets cited.

Per-route metrics differentiate the pages even where the score does not — CLS runs from
0.000 to 0.085 (`panel-management`), Speed Index from 87 ms to 197 ms. That is the evidence
the run really visited 23 distinct authenticated pages rather than scoring one shell 23
times.

### The two limits this measurement exposes

**1. `performance` is saturated.** 100 on 22 of 23 routes is a real measurement, not
rounding — but it is measured against a **localhost** stack on Lighthouse's own desktop
preset (rtt 40 ms, 10 Gbps, `cpuSlowdownMultiplier: 1`; the shipped preset, not a
hand-loosened one). At that setting the score has almost no headroom left to lose, so:

* as a **ratchet** it is the strictest setting available — the floor says *"may not get
  worse at all"*, and any measurable degradation fails;
* as **evidence about real-world speed** it says very little. Nobody may cite "Lighthouse
  performance 100" as a claim that the app is fast on a user's machine. It is not that.

The asymmetry is written into the baseline's own `provenance.sensitivity_boundary`, so it
travels with the number instead of living only here.

**2. `best-practices` 96 and `seo` 82 are real deductions, and they are FROZEN, not
fixed.** This is a CI/gate slice; a defect found by a new gate is recorded and left open in
its own PR. Freezing has one consequence worth stating plainly: **a frozen deduction is an
invisible one** unless something keeps naming it. That is exactly why the spec was extended
to record `routes[].deductions` — the weighted audits that actually cost each route its
points — so even a green run still carries the list of what is wrong.

## 9. The armed run — and the claim it falsified

Run `31572385301`, job on commit `e707c61`, gate **armed**. Result: **green**, and 22 of
23 routes reproduced the frozen floors byte for byte.

The twenty-third did not, and it is the most useful thing this slice measured:

```
bootstrap run   panel-management: performance=98[98-98]
armed run       panel-management: performance=98[98-100]
```

Same median, wider range. **So "worst repeat spread: 0 points" was true of one run and is
not a property of this gate.** One route has real repeat variance, and the second run
found it. Three consequences, all of them recorded rather than smoothed over:

1. **The median is what held the floor**, not the absence of noise. Both runs medianed 98
   on that route. This is the stabilisation in §3 doing exactly the job it was added for —
   had the gate frozen a single pass, the floor would have been 100 and the armed run
   would have failed on weather at the first attempt.
2. **`panel-management`'s performance floor must stay at 98.** A future run that medians
   100 will make the tightened map suggest raising it; taking that suggestion arms a gate
   that fails the next time the same route medians 98. This is pinned in the baseline as
   `provenance.do_not_tighten` so it is read at the moment somebody is about to do it.
3. **The baseline's `provenance.repeat_spread_points` now records both runs**, not the
   flattering one.

## 10. What is actually frozen — the deductions, named

Recorded from the armed run's `routes[].deductions`. These are the audits that cost each
route its missing points, i.e. exactly what the floors are freezing:

| Category | Audit | Weight | Routes | What it says |
|---|---|---|---|---|
| best-practices | `errors-in-console` | 1 | **23 / 23** | Browser errors were logged to the console |
| seo | `meta-description` | 1 | **23 / 23** | Document does not have a meta description |
| seo | `robots-txt` | 1 | **23 / 23** | robots.txt is not valid |
| performance | `cumulative-layout-shift` | 25 | **1 / 23** | `panel-management`, CLS 0.085 |

Three of the four are **whole-app** defects, not per-page ones — they reproduce on every
route because they live in the shell (`index.html`) or at the origin (`/robots.txt`). The
fourth is a single page's layout shift, and it is also the reason that page scores 98
instead of 100.

**`errors-in-console` on all 23 routes deserves a second look by whoever picks it up:** a
console error on every authenticated page is a plausible symptom of something real, not a
lint nit, and this gate cannot tell which.

## 11. Open, not fixed

Product code is untouched. Every deduction above stays **open** and belongs in its own PR,
tracked as **[#677](https://github.com/alimirbagirzade/Entropia/issues/677)** rather than
left only in this file — a defect recorded solely inside the artefact that froze it is a
defect nobody will read again. The issue names the acceptance the same way #617 and #618
do: each fix lands with its floor tightened, so the repair and its proof arrive together.

**P11 is NOT closed:** `P11-1` (branch protection) is a repository setting and a human
decision, and `P11-6b` remains open. Because P11-1 is open, this gate — like the visual and
axe gates beside it — is a job, **not** a required status check: nothing mechanically stops
a merge over a red Lighthouse run today.
