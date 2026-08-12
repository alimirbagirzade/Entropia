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
