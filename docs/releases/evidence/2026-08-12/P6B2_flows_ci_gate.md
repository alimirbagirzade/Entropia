<!-- doc-status: current -->

# ADIM 45 — RC §6.2 blocker 2: `flows` wired as a CI gate

**Date:** 2026-08-12 · **Base:** `origin/main` @ `853a358` · **Branch:** `ci/rc-blocker2-flows-gate` · **PR:** #680

RC readiness §6.2 kept blocker 2 open in its own words:

> Kapsam boşluğu kapandı ve beş akış koştu, ama **`flows` bir CI kapısı değildir** — yerel bir
> komuttur, hiçbir workflow onu koşmaz, dolayısıyla bir regresyon sessizce geri gelebilir.

The coverage existed. The gate did not. This slice wires it and adjudicates the two SKIPs.

---

## 1. The gate runs — from the JOB LOG, not the badge

| | |
|---|---|
| Workflow run | [31591633498](https://github.com/alimirbagirzade/Entropia/actions/runs/31591633498) (`E2E`, event `pull_request`) |
| Job | `Acceptance flows (a)-(e) — five flows vs. an isolated stack (RC §6.2)` — id **94097720164** |
| Conclusion | **success** |
| Job wall-clock | `2026-08-12T11:23:39Z` → `11:26:35Z` = **2m56s** |
| Harness itself | **`duration_seconds=137`** (the rest is checkout + node + Playwright install) |
| Verdict line | **`67 passed, 0 failed, 1 skipped`** → `E2E ACCEPTANCE OK` |

Raw log: [`p6b2_acceptance_flows_ci_job.log`](p6b2_acceptance_flows_ci_job.log) (639 lines, ANSI stripped).

**The stack really came up** — this is the check that a fast green run must survive.
`docker compose up -d --build` at `11:23:5x`, seed PASS at `11:25:22`, and all seven planes
reported broker-connected with `restarts=0`:

```
PASS  [flows] seed (SEED_E2E_GOLDEN + SEED_ESP_TA + SEED_RATIONALE) exit 0
PASS  [flows] plane worker-default broker-connected (health=healthy restarts=0)
PASS  [flows] plane worker-data / worker-backtest / worker-agent /
              worker-agent-executor / agent-coordinator / scheduler   (all healthy)
```

**The browser layer really ran** (it is the part most likely to degrade to a SKIP on a bare runner):

```
PASS  [browser] npm ci ok (lockfile untouched)
PASS  [browser] chromium available
PASS  [browser] all four journeys passed against this stack — 5 passed
```

### Cost, measured

A **second full stack (12 containers)** on its own runner, ~3 minutes of runner time. Because it is
a *sibling* job of `e2e`/`a11y`/`lighthouse`/`e2e-dev` it runs in **parallel** with them, so it adds
**~0 to the workflow's wall-clock** — `lighthouse` (75-minute budget) dominates — and only to the
minutes bill. §6.2 anticipated the cost as possibly prohibitive and floated nightly or reduced
scope; **neither was needed.** Scope was not cut and the gate is not advisory.

### Blocking, not advisory

No `continue-on-error`, no `|| true`. The harness exits 1 on any FAIL and 2 when Docker is
missing/hung; both fail the job. `set -o pipefail` around the `tee` is load-bearing — without it the
step would inherit *tee's* status and a failing acceptance run would report green, which is the very
bug class this gate exists to catch.

> **Out of scope, stated so it is not mistaken for done (P11-1):** a **required-status-check** rule in
> branch protection is what makes a red check actually *stop* a merge. That is a repository setting
> and a human decision. **Until it is set, this gate reports honestly but does not hold the merge
> button.**

---

## 2. The two SKIPs — a SKIP is not a PASS

Skip count went **2 → 1**. Pass count went **60 → 67**.

### (ii) Tool Gateway call log — **CLOSED**

The old reason was "no agent task exists on a freshly seeded stack". The fix was **not** to seed a
task: a seeded row would prove only that the read endpoint can project a fixture. `[d5]` now waits
for the **real** task `commands/agent_loop.py::_spawn_followup_task` materialises when the
`agent-coordinator` plane consumes the directive `[d4]` already posts.

```
PASS  [d5] the Coordinator materialised task agttask_01KZTVGX139HHVH8JV1WKA03FC from the
           directive — the 202 was consumed, not merely accepted
PASS  [d5] the task's provenance is source=directive
PASS  [d5] Tool Gateway call log served for the REAL task ... (typed envelope, 0 call(s) logged)
PASS  [d5] NON-NEGOTIABLE 3 — USER -> GET the tool-call log = 403
```

The same wait **upgrades non-negotiable 4** from *"the admission was ACCEPTED"* to *"the admission
was CONSUMED by the durable plane"*. A 202 that nothing ever picks up is precisely the silent failure
that rule exists to catch, and nothing here would previously have noticed it.

**Honest boundary:** the log is asserted as **served**, not as non-empty (`0 call(s) logged` above).
Whether the executor has dispatched a governed tool call by that instant is a timing fact about the
executor plane; asserting a count would make the step flaky rather than stronger. The count is
printed, so a regression is visible.

### (i) Positive ESP `activate` → `deprecate` — **STAYS a SKIP, reason corrected**

The recorded reason was *"the harness does not synthesise test vectors"*. That was **half true, and
that half is now fixed** — real vectors are sent and `vectors_run` went **0 → 2**:

```
PASS  [c2] validate -> 200 (state=failed, vectors_run=2)
PASS  [c2] the declared vectors were parsed as executable vectors (vectors_run=2, not the dropped-string 0)
PASS  [c2] fail-closed holds: complete evidence + an unlisted canonical key -> validation_state=failed (doc 09 §7)
PASS  [c5] the refusal is the VALIDATION gate (409 RESOLVER_VALIDATION_REQUIRED), not the evidence-presence gate
```

The **real** reason is structural — a three-way lock between shipped invariants:

1. validation can only PASS for the six keys in `indicators.py::VALIDATABLE_RESOLVER_KEYS`
   (`ta.sma/ema/rma/wma/rsi/vwap`); everything else fails closed by design (doc 09 §7);
2. `apps/seed.py::_ESP_TA_RESOLVERS` seeds **all six** as `trusted_active` under `SEED_ESP_TA=1`,
   which the flows stack sets because the browser layer's Pre-Check needs them resolvable;
3. `esp/state_machine.py::_ALLOWED` permits activation **only from `candidate`**, and `deprecated`
   is terminal apart from `unavailable`.

**The intersection is empty.** On a `SEED_ESP_TA` stack no canonical key is both validatable and
activatable, and no ordering of harness calls creates one. Closing it needs either a second Compose
stack seeded without `SEED_ESP_TA` (a whole new 12-container CI job for one assertion) or a change to
`seed.py` — product code, out of scope for a CI-wiring slice. In-process coverage remains
`backend/tests/integration/test_esp_persistence.py`.

Proved locally against the shipped validator, not assumed —
[`p6b2_esp_vector_local_proof.txt`](p6b2_esp_vector_local_proof.txt):

```
probe key           -> state=failed  vectors_run=2   ("No executable compute for 'af.probe.rc.v1'")
OLD string payload  -> state=failed  vectors_run=0
ta.sma/ema/rma/wma  -> state=passed  vectors_run=2
```

The vectors are **arithmetically correct for every MA variant**, so the probe's refusal is provably
about the *key*, not about a payload rigged to fail.

**Two new pins keep this adjudication from rotting.** `[c2]` pins `validation_state=failed` — if an
arbitrary caller-named key ever becomes certifiable, the gate goes **red** and forces this
adjudication to be reopened rather than letting it slide through as a quietly-improved harness. `[c5]`
pins `409 RESOLVER_VALIDATION_REQUIRED` specifically, because `_ensure_validation_passed` calls
`_ensure_activation_evidence` **first** — with the old string payload the refusal could have been
either gate, and "not 200" could not tell them apart.

---

## 3. Skip ceiling — the hole that wiring this into CI would otherwise have opened

A SKIP does not fail the run. As a local command that was fine. As a **gate** it means a step that
*quietly stops running* — a vanished browser toolchain, an unseeded fixture, a new `af_skip` added in
passing — keeps the gate green while measuring less than it did yesterday. That is the same
"a regression can come back silently" failure the gate was wired to prevent, reintroduced one level up.

`E2E_MAX_SKIPS` pins the **adjudicated** count; CI sets it to `1`. Unset = no ceiling, so a
developer's local run and `.github/workflows/install-acceptance.yml` (which runs `legacy`, zero skips)
are unchanged. It does **not** bless skips — raising it is a §6.2 decision, and the failure message
says so.

---

## 4. Concurrency (brief item 3)

Full detail: [`p6b2_concurrency_verification.txt`](p6b2_concurrency_verification.txt).

**The brief's premise was stale.** It called the `ci.yml` concurrency defect *"ÖLÜMCÜL"* for this
gate; it was already repaired in ADIM 34 and is still repaired. Both `ci.yml:9-14` and `e2e.yml:10-12`
carry `cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}`, which evaluates **false** on main.

The new job lives in `e2e.yml` **specifically so it inherits a block that is already correct** rather
than adding a second one that has to be kept correct. Workflow-level concurrency applies to every job,
so nothing job-specific had to be authored — and there is no new place for the defect to reappear.

The historical damage is confirmed from the API, and stated **precisely**:

```
e8d1d48 (#633)  CI run 31189395028  conclusion=cancelled  total_jobs=0
bc59dae (#634)  CI run 31189634665  conclusion=cancelled  total_jobs=0
```

`total_jobs=0` — cancelled before a single job was dispatched. **Precision that matters:** on both
SHAs the cancelled run was **`CI`**; `E2E`/`Security`/`Performance`/`Install acceptance` all
*succeeded*. So `e2e.yml` — this job's home — was never the victim. Recorded that way rather than
letting "their CI never ran" be read as "nothing ran".

---

## 5. What this does NOT close

* **Blocker 1 (A-08)** — untouched. The screen-reader audit ledger is still empty. Tracking issue
  **#514 was reopened by a human on 2026-08-12** (`state=OPEN`, `stateReason=REOPENED`, label
  `human-only`), which resolves the closed-issue/empty-ledger divergence via path (B). No agent may
  close it.
* **P11-1 (branch protection)** — repository setting, human decision. See the callout in §1.
* **Verdict stays `BLOCKED`.** Blocker count **2 → 1**.
