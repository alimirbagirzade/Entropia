# P10-7 — the activation clock had already run out

**Measured 2026-08-12.** RC readiness report §6.7 records P10-7 as *"aktivasyon için 5
gecelik baseline gerekiyor"*. That sentence was written on 2026-08-07 and was never
re-checked. It is stale: the collector this slice was told to look for **already
existed**, had **already been running**, and the fifth night landed on **2026-08-11**.

## 1. Was there a collector?

Yes — `.github/workflows/performance.yml` → job `load-full`, added in ADIM 24, on
`schedule: "23 4 * * *"`. Nothing had to be built. The work of this slice was
therefore not "start the clock" but "read the clock, then arm the gate".

## 2. How many nights had it collected?

Every scheduled run of the workflow, from `gh run list --workflow=performance.yml
--event=schedule`, with the artifact list per run from
`gh api repos/:owner/:repo/actions/runs/<id>/artifacts`:

| # | run id | date (UTC) | head sha | `load-full` | `loadgen-baseline` artifact |
|---|---|---|---|---|---|
| 1 | 31152127539 | 2026-08-07 | `610ed200` | success | present, 5487 B, not expired |
| 2 | 31241156717 | 2026-08-08 | `2cf7283d` | success | present, 5465 B, not expired |
| 3 | 31296683657 | 2026-08-09 | `2cf7283d` | success | present, 5441 B, not expired |
| 4 | 31359834251 | 2026-08-10 | `e35cf61f` | success | present, 5419 B, not expired |
| 5 | 31461912952 | 2026-08-11 | `4e9512d2` | success | present, 5487 B, not expired |
| 6 | 31567849357 | 2026-08-12 | `c697fad9` | success | present, 5432 B, not expired |

**Six of five.** All six on the same runner class (`github-ubuntu-latest`), the same
parameters (concurrency 16, repeats 40), the same auth profile (`session-login`), and
**zero errors** in any of them. `docs/performance/README.md` §6 step 1 asks for "at
least five ... from the same runner class"; that condition was satisfied on night five.

### The cancellation hazard, checked rather than assumed

`ci.yml`'s historical concurrency defect (a queued run on `main` cancelling its
predecessor) would be fatal to a nightly collector — a cancelled night is an
uncollected night. It does not apply here, and this was verified two ways:

* **By reading the expression.** `performance.yml` sets
  `cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}`. On a `schedule` event
  `github.ref` **is** `refs/heads/main`, so the expression is `false` and a scheduled
  run cannot be cancelled by anything.
* **By reading the log.** Six consecutive scheduled runs completed with
  `conclusion: success` and a real artifact. None were cancelled, and
  `nightly-failure-notice` never fired. A green badge alone would not have shown this —
  the per-run job list and artifact list were pulled for each of the six.

## 3. Where does the baseline live, and does it survive between runs?

Two different lifetimes, and only one of them has to be long:

* **The nightly artifact** (`loadgen-baseline`, 30-day retention) is the *input* to the
  decision. It only has to live long enough to be read once. All six were still
  downloadable when this measurement ran.
* **The gate's baseline is a tracked file** — `docs/performance/baseline_ci.json`,
  committed in this slice. Once committed, the gate does not depend on artifact
  retention at all. This is the answer to "does it survive between CI runs": it
  survives because it is in git, not because GitHub keeps it.

## 4. Which run was frozen, and why that one

§6 step 3 says "commit the median run". Ranked by each run's median
control-normalised p95 across the 16 comparable warm scenarios:

```
31241156717  2026-08-08  1.586
31296683657  2026-08-09  1.696
31461912952  2026-08-11  2.091   <- frozen as baseline_ci.json (lower-middle of six)
31359834251  2026-08-10  2.181
31567849357  2026-08-12  2.252
31152127539  2026-08-07  2.424
```

Six is even, so there is no single middle run; the lower-middle was taken. Freezing the
*fastest* night would have made every ordinary night look like a regression, and
freezing the slowest would have hidden one.

## 5. The band, derived from the data

Full per-scenario table: `p10_7_control_normalised_spread.txt`.

* Raw control drift across the six nights: **1.71x** — this is the weather the
  normalisation exists to cancel, and it is why a raw p95 gate was never an option.
* Control-normalised max/min spread, worst scenario: **1.92x** (`hypotheses`).
* What the gate actually measures is each night against the **committed** baseline, not
  min against max. Replaying all six against `baseline_ci.json`, the worst ratio any
  night produced is **1.62x** (`admin_logs`, the 2026-08-07 night).

§6 step 3 asks for roughly 1.5x the observed spread. Against the quantity the gate
really evaluates: `1.5 x 1.62 = 2.43`, rounded up to one decimal → **`--max-ratio 2.5`**.
The looser reading (1.5 x the 1.92 max/min spread = 2.88) was rejected as weaker
evidence for a wider band.

## 6. Verdict of §6 step 5

Step 5 allows the honest answer "no useful band exists, leave it off". That escape hatch
is **not** taken, and here is the reasoning made explicit rather than assumed:

* the band clears every observed night with **1.54x headroom**, so it is not a gate that
  fails on weather;
* it still fails a 3.0x regression, proven on the real committed baseline rather than a
  synthetic fixture (`p10_7_ratio_gate_replay.txt`);
* and a 2.4x regression passes — the band is genuinely wide, and that limit is stated
  rather than hidden. A regression between 1.7x and 2.5x will not be caught by this
  gate. Six samples cannot bound a tail; tightening is a later decision with more
  nights behind it, recorded in README §6.

## 7. Honest boundary

* The band rests on **six** nights from **one** runner class. It says nothing about any
  other machine, and `docs/performance/README.md` §2 already forbids comparing across
  classes.
* Three of the six nights sit on two shas (`2cf7283d` twice), so the sample covers five
  distinct commits, not six independent codebases.
* The gate runs on the **nightly only**. A PR that regresses latency 3x merges green and
  is caught the following morning by `load-full` + `nightly-failure-notice`. That is the
  deliberate trade `docs/performance/README.md` §1 makes; it is not an oversight.
