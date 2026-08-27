<!-- doc-status: historical -->

# Final closure — current-main delta forensics (2026-08-25)

> **What this is.** A READ-ONLY forensic comparison between the 2026-08-13 closure
> baseline `e2fa521` and the real `origin/main` of 2026-08-25. No production line was
> changed by this audit. Every claim below was re-derived from the tree, the call graph
> or an executed test — prior audits, `CLAUDE.md` and issue CLOSED states were treated
> as **hypotheses to falsify**, and three of them did not survive.
>
> **This document FREEZES the moment it measured.** Re-derive before trusting it.
>
> ### Post-measurement addendum — 2026-08-25, after this audit's base
>
> **§4 C-4 (#559) and §4 C-5 (#544) were acted on within hours of this audit, on the
> owner's instruction: both issues were RE-OPENED** (`state_reason: reopened`), each with a
> written reason recorded on the issue naming the measurement above.
>
> **The findings below are NOT rewritten.** They record what was true at `a7261de`, and the
> ISSUE-STATE-DRIFT classification was correct then. What changed is the **tracking**, not
> the decision: `G8` and `G14` are still unsigned, both code paths are still byte-identical
> to the baseline, and preconditions 20/21 stay amber. This is the same distinction the
> A-08 ledger draws about #514 — *"re-opening the issue is not a result any more than
> closing it was"*. Recorded here, rather than edited into §4, following the precedent of
> `284d8a1e` (*"record that #698 resolved DR-1 … after this audit's base"*).

---

## §0 — Session start record (verbatim)

```
git fetch --all --prune          -> ok; origin/main cfce51e..a7261de
git status --short               -> (empty)  WORKTREE CLEAN
git rev-parse --abbrev-ref HEAD  -> claude/entropia-v18-delta-forensics-eiiapn
git rev-parse origin/main        -> a7261deb615e795ca5428f1f11543427a72bcddb
```

**Worktree was CLEAN.** No reset, stash or clean was performed, and no production file
was touched.

**One environment fact that shapes every "before" claim below.** The container's clone
was **shallow** (56 commits) and did **not contain `e2fa521`**: the first
`git log e2fa521..origin/main` returned `fatal: bad object`. The baseline was fetched
explicitly and the clone unshallowed (`git fetch --unshallow`, 1399 commits) *before*
any diff was read. An auditor who skips this step measures a range that silently starts
at the wrong commit.

| Fact | Value |
|---|---|
| Baseline | `e2fa52173a302aa6e9e1b0a23ba6061e6ccd8b86` — 2026-08-13 11:48:49 +0300 — *"test(acceptance): prove external-object run provenance survives revision and delete (#692)"* |
| Current `origin/main` | `a7261deb615e795ca5428f1f11543427a72bcddb` — 2026-08-25 12:34:07 +0300 |
| Baseline is an ancestor of HEAD | **yes** (`git merge-base --is-ancestor` → true) — linear delta, no divergence |
| Commits in range | **150** |
| Open PRs at measurement | **1** — #824 (`docs/stage-109-landed`) |
| Environment built for this audit | `uv sync --all-extras` (backend `.venv`). Postgres 16 installed but **DOWN**; `frontend/node_modules` **absent**. |

---

## §1 — Method, and its honest limits

1. **Call graph over symbol names.** A symbol existing proves nothing; every A-section
   answer below was decided by grepping *production importers and call sites* under
   `backend/src`, not by the presence of a definition.
2. **Executed tests, not cited tests.** 123 backend unit tests were actually run in this
   container (§9). Everything requiring Postgres or npm was **not run** and is reported
   as CI-authoritative.
3. **Issue state is not evidence.** Each of the eight named issues was read for a written
   decision, a closing PR, *and* the code it claims to describe. Two failed all three.

**What this audit could NOT do, stated up front:**

* **No integration/contract/e2e run** — no Postgres daemon, no `node_modules`. Backend
  full-suite pass count and coverage remain **CI's authority**.
* **No frontend gate run** — lint, typecheck, vitest and coverage were not executed.
* **CI on the exact HEAD is INCOMPLETE.** `a7261de` CI run #2286 was `in_progress` at
  measurement time. The newest *completed, green* main run is `32d2c96` (run #2283,
  2026-08-25T08:15Z) — one commit behind HEAD, and that commit is docs-only.

---

## §2 — Section A: shared portfolio

The headline: **the shared-portfolio programme moved further in this window than in any
previous one.** `C3` (the participant adapter) and `C4` (the worker branch) both landed.
But **the containment flag did not move**, so every one of those parts is reachable only
from tests. The correct classification for the programme as a whole is
**IMPLEMENTED-BUT-CONTAINED**, and that is a genuinely different state from the
baseline's **IMPLEMENTED-BUT-UNWIRED**.

### A-1 — Did `run_portfolio` gain a production caller?

**NO.**

| | |
|---|---|
| file:path | `backend/src/entropia/domain/backtest/portfolio_engine.py:717` |
| symbol | `run_portfolio` |
| caller | **none in `backend/src`** — grep for `run_portfolio` across production returns the definition, the `__all__` entry, and four *docstring* mentions (`participant.py:247`, `execution/intents.py:15`, `execution/arbitration.py:11`, `execution/portfolio_ledger.py:20`). Zero call sites. |
| commit SHA | — (unchanged in range) |
| test | `tests/unit/oracles/test_oracle_portfolio_containment_gate.py` — `_LOOP_ENTRY_POINTS = ("run_portfolio", "iter_portfolio")` |
| doc | `portfolio_engine.py:728` — *":func:`iter_portfolio`, exhausted."* |
| issue state | n/a |
| before | no production caller |
| after | no production caller |
| classification | **IMPLEMENTED-BUT-UNWIRED** |
| confidence | **HIGH** |

**The subtlety that matters.** The worker *does* now drive the phase loop — but through
**`iter_portfolio`** (`portfolio_engine.py:628`), the generator, not through
`run_portfolio`, its exhausting wrapper. Answering "did the phase loop get wired?" by
grepping `run_portfolio` alone returns **NO** and is **misleading**. The containment gate
knows this and greps for *both* entry points; an auditor grepping one name would draw the
wrong conclusion. See A-4.

### A-2 — Is there a real `ItemParticipant` implementation?

**YES — this is the single largest delta in the window.**

| | |
|---|---|
| file:path | `backend/src/entropia/domain/backtest/participant.py:193` (file is **new**, 530 lines) |
| symbol | `_EngineParticipant`, built by `build_engine_participant` (`participant.py:466`), structurally proven against the Protocol by `_protocol_check` (`:515`) |
| caller | `application/jobs/backtest_engine.py:1079`, inside `_shared_clock_inputs` |
| commit SHA | **`2cda24f5`** — *"feat(closure-c3): add the engine-backed ItemParticipant and its two invariants (#777)"* |
| test | `tests/unit/oracles/test_oracle_engine_participant.py` (641 lines, 14 tests) — **executed, 14 passed** |
| doc | `docs/decisions/closure_participant_importer_allowlist_2026-08-18.md` (signed Option A) |
| issue state | n/a |
| before | **no production implementation**; the only `ItemParticipant` was the test-owned `_ScriptedParticipant` |
| after | exactly **one** production implementation, wrapping `engine._ItemStepper` |
| classification | **IMPLEMENTED-BUT-CONTAINED** |
| confidence | **HIGH** |

Two invariants ship with it and are the reason it is safe rather than lucky:
**reconciliation** (pool attribution == item ledger delta) and **sleeve parity** —
`Ci(t)` derived twice and compared on **every deciding tick**, raising
`ParticipantDivergenceError` (`participant.py:107`) on a split. Preconditions 7 and 8 of
the containment-lift list, both `❌` on 2026-08-17, are now **GREEN**.

**It refuses more than it runs, deliberately.** `_unsupported_shapes`
(`participant.py:115`) is a construction-time refusal table of **eleven** strategy shapes
— deferred/resting entry and exit fills, non-immediate order types, partial closes,
scaling, same-direction stacking, `close_existing` hedges, missing allocation, cross-item
`PortfolioRules`, absent indicator plan, and any down capability gate. See A-10.

### A-3 — Any engine adapter besides `_ItemStepper`?

**NO second simulation engine — one adapter *over* `_ItemStepper`.**

`_EngineParticipant` holds an **already-built** `_ItemStepper`
(`participant.py:205`, constructed by `engine._build_stepper` at
`jobs/backtest_engine.py:1062`) and drives four of its five phases. It never calls
`tail`. Production `class .*Participant` definitions: exactly one
(`_EngineParticipant`). Test-only: `_ScriptedParticipant`
(`tests/unit/oracles/portfolio_harness.py:157`) and `_ClosingParticipant`
(`tests/unit/oracles/test_oracle_portfolio_finalize.py:41`).

**Classification: IMPLEMENTED-BUT-CONTAINED · confidence HIGH.** There is no rival
replay implementation, which is the outcome the design asked for.

### A-4 — Is the worker's outer loop still item-based?

**YES on the shipped path — and a tick-based SIBLING now exists beside it.**

`jobs/backtest_engine.py:367` is a new branch:

```python
if len(prepared_items) > 1 and _use_unified_clock(capital_execution):
    unified = await _replay_shared_clock(...)     # tick-driven, shared pool
    ...
else:
    for prepared in prepared_items:               # :395 — UNCHANGED item loop
```

| | |
|---|---|
| symbol | `_use_unified_clock` (`:159`), `_replay_shared_clock` (`:1147`) |
| commit SHA | **`39947256`** (#799), repaired by **`3f557c72`** (#805) |
| test | `tests/unit/test_shared_clock_branch_predicate.py`, `tests/integration/test_shared_clock_worker_branch.py` |
| before | one unconditional item loop |
| after | item loop preserved verbatim in the `else` arm; shared arm added above it |
| classification | **IMPLEMENTED-BUT-CONTAINED** |
| confidence | **HIGH** |

The branch is a **conjunction of two independent gates**, and the docstring at `:159`
states why either alone silently re-prices every independent composite Result:
`shared_allocation_is_executable()` (the build flag) **AND**
`shared_allocation_requested(capital_execution)` (the run's own snapshot). Since
`SHARED_ALLOCATION_STATUS == "future_dev"` (A-8), the first conjunct is **always False**
and the `else` arm is the only reachable one.

### A-5 — Is `combine_item_runs` still used in shared mode?

**It is not used on the shared path at all — and it is untouched on the independent one.**

`combine_item_runs` (`execution/portfolio.py:312`) has exactly one production caller,
`jobs/backtest_engine.py:469`, and that call site is **inside the `else` arm**. The
shared arm replaces it with `project_portfolio_run` (A-6) rather than folding finished
runs — deliberately, because folding sequential runs is what produces the wrong drawdown
the containment message describes.

**Classification: IMPLEMENTED-ACTIVE (independent path) · confidence HIGH.**

**This is where the window's one real regression lived.** `#799` named its shared-branch
loop variable `prepared`, so the worker carried a **second copy** of the literal
`for prepared in prepared_items:` — the exact string the containment tripwire greps for.
Deleting the real independent loop then left the gate **GREEN**. Recorded and repaired by
**`3f557c72` (#805)**: the helper now loops over `pinned`, and the assertion became
`worker.count("for prepared in prepared_items:") == 1`. **Verified live: the count is 1.**
See §7.3.

### A-6 — Did `project_portfolio_run` gain a production caller?

**YES.** This is the clearest single reversal of a baseline finding.

| | |
|---|---|
| file:path | `backend/src/entropia/domain/backtest/execution/portfolio_projection.py:513` |
| symbol | `project_portfolio_run` |
| caller | **`application/jobs/backtest_engine.py:1245`** (imported at `:110`), inside `_replay_shared_clock` |
| commit SHA | **`39947256`** (#799) |
| test | `test_oracle_portfolio_containment_gate.py` — `_AUTHORISED_PROJECTION_CALLERS = ["application/jobs/backtest_engine.py"]` (`:128`, asserted `:347`) |
| doc | ADIM 35 record; `portfolio_engine.py:77` |
| issue state | n/a |
| before | **zero importers in `backend/src`** (ADIM 59 / `closure_w0_shared_portfolio_2026-08-13.md`) |
| after | exactly **one** authorised production caller |
| classification | **IMPLEMENTED-BUT-CONTAINED** |
| confidence | **HIGH** |

### A-7 — Did `build_portfolio_manifest` gain a production caller?

**NO.**

| | |
|---|---|
| file:path | `backend/src/entropia/domain/backtest/execution/provenance.py:473` |
| symbol | `build_portfolio_manifest` |
| caller | **none** — the only other mention is a docstring at `portfolio_projection.py:67` |
| before / after | no production caller / no production caller |
| classification | **IMPLEMENTED-BUT-UNWIRED** |
| confidence | **HIGH** |

This is precondition 22's other half and it did **not** move: the run manifest still
carries **none** of the four policy fields the lift requires
(`engine_allocation_policy_version`, `clock_policy_version`,
`arbitration_policy_version`, `mark_staleness_policy` — pinned as absent by
`test_oracle_portfolio_containment_gate.py:374`).

### A-8 — What is `SHARED_ALLOCATION_STATUS`?

**`"future_dev"` — byte-for-byte unchanged.**

| | |
|---|---|
| file:path | `backend/src/entropia/domain/allocation/capability.py:105` |
| commit SHA | — `git diff e2fa521..origin/main -- .../capability.py` is **EMPTY** |
| generated artefact | `docs/generated/repository_facts.md:28` → `future_dev` (gate `--check` **executed, passed**) |
| classification | **DELIBERATE-FUTURE-DEV** |
| confidence | **HIGH** |

Two independent refusals still stand in front of the branch:
`commands/backtest_run.py:545` (run admission) and `_use_unified_clock` — both reading
the same flag, so no HTTP request, retry or Agent path can construct a run that enters
the shared arm.

### A-9 — Is a unified Result actually persisted to the DB?

**The wiring exists and is complete; the path is unreachable.**

On the shared arm, `_replay_shared_clock` returns an `EngineOutput` that is assigned to
the same `output` name both arms produce (`:379`), flows through `derive_metric_values`
(`:485`), past cancellation checkpoint #4, into
**`result = await bt_repo.create_result(...)`** at **`:495`** — the *identical* tail the
independent arm uses. So a unified Result **would** persist, with its own provenance
token `ENGINE_KIND = "v1_unified_clock_portfolio"`
(`portfolio_projection.py:109`), distinct from `combine_item_runs`'
`"v1_bar_replay_composition"` (`execution/portfolio.py:570`).

| | |
|---|---|
| before | no shared path existed; nothing to persist |
| after | full persist path wired, **structurally unreachable** behind A-8 |
| classification | **IMPLEMENTED-BUT-CONTAINED** |
| confidence | **HIGH** (code path traced end to end) / **MEDIUM** on runtime behaviour — no integration test was executed in this container; that evidence is CI's |

The shared arm also gained the cancellation checkpoint the merged axis needs: **#3b**,
tick-strided (`_TICK_CHECKPOINT_STRIDE`, `:1224`), because the merged clock deletes the
between-items boundary checkpoint #3 sits on. Precondition 10 → **GREEN**. A real
`UnboundLocalError` bug on that path (progress dict read a name only the independent arm
binds) was found by a negative control and fixed inside #799 — recorded at `:340-348`.

### A-10 — Are P2 (pending fills) and P8 (scaling) closed?

**NO. They are REFUSED, not modelled — and the user-facing half does not exist.**

| | |
|---|---|
| file:path | `backend/src/entropia/domain/backtest/participant.py:115` (`_unsupported_shapes`) |
| symbol | rows 4–6 (deferred/resting entry fill, deferred exit fill, resting order type) = **P2**; rows 8–9 (scaling ladder, same-direction stacking) = **P8** |
| caller | `build_engine_participant` → raises `UnsupportedStrategyShapeError` at **construction**, before any bar is admitted |
| commit SHA | `2cda24f5` (#777) |
| doc | `participant.py:42` — *"P-C2 §C.3.7 (deferred fills) and §C.3.8 (scaling) each recommend option (a) — block the shape at admission — and **`C6` is where those become user-visible Ready Check blockers**."* |
| issue state | **G11** briefed `c2a7d03c` (#771); **G12** signature block created `234b6bc9` (#752) — briefed ≠ signed |
| before | not modelled, not refused |
| after | refused engine-side; **`C6` not shipped** — `grep` over `domain/readiness/enums.py` finds **no** blocker code for either shape |
| classification | **PARTIAL** (engine-side fail-closed) + **PRODUCT-DECISION-REQUIRED** (G11/G12 unsigned, `C6` unbuilt) |
| confidence | **HIGH** |

The consequence, stated plainly: a user configuring a scaling or limit-order strategy in
a shared composition would today get an **`ENGINE_ERROR` run failure** from
`_replay_shared_clock`'s `except` (`:1176`), not a Ready Check blocker. That is
fail-closed and honest, but it is not the designed UX, and it is one of the reasons the
flag cannot lift.

---

## §3 — Section B: financial correctness

All three defects were shipped by **one** commit, **`5e524652`** (#720,
2026-08-14), which is the only commit in the window that **moved money**.

**Hard evidence, measured not asserted** — `backend/tests/unit/engine_golden_digests.json`:

| Measurement | Result |
|---|---|
| Scenario count | **46 → 50** (4 added: `sizing.base_percent_of_capital`, `sizing.impossible_window_opens_nothing`, `costs.commission_round_trip`, `costs.commission_scale_ladder`) |
| Digests **changed** | **29 of 46** |
| `engine_version` in the file | `backtest-engine-v18-gap-adjusted-stop-fill` → **`backtest-engine-v18-percent-sizing-per-fill-commission`** (`manifest.py:145`) |
| Digests at `dc2902fc` (C1), `c78b15b7` (C2), `2cda24f5` (C3), `39947256` (C4) | **byte-identical to HEAD** — every shared-portfolio slice is behaviour-neutral |

That last row is the important one: it independently confirms that the four
shared-portfolio commits changed no shipped number, and that the 29 moved digests are
attributable to #720 alone.

### B-1 (#550) — Is UI-percent / engine-percent parity real in current code?

**YES.**

| | |
|---|---|
| file:path | `backend/src/entropia/domain/backtest/execution/sizing.py:171` |
| symbol | **`_percent_of_capital`** (new, single conversion point) → used by `_raw_position_size` (`:287`), `_clamp_to_limits` (`:226`, `:230`) and the new public `max_position_size_cap` (`:236`) |
| caller | `max_position_size_cap` exists precisely so the two `engine.py` call sites that bind the cap against an *already-open* position (scaling ladder layer check, stacking tranche check) read the same percent, not a unit count |
| commit SHA | `5e524652` (#720) |
| test | `tests/unit/oracles/test_oracle_sizing.py` — **executed, passed** |
| doc | `sizing.py:258-285` cites Master Ref §10.1, doc 02's ⓘ panel, the V18 mockup and the shipped form |
| issue state | **#550 CLOSED completed 2026-08-14, closing PR #720 (MERGED)** — state matches code |
| before | `return Decimal(sizing.base_position_size)` verbatim as a unit count |
| after | `size = equity × pct / 100 / entry_price`, quantized to `_QTY` in one place |
| classification | **RESOLVED-SINCE-BASELINE** |
| confidence | **HIGH** |

**The transition gate is real and — contrary to my own first reading — it is
clearable.** `PositionSizing.size_semantics` (`domain/strategy/config.py:742`) is
`None` for pre-cutover revisions, and `domain/readiness/validators.py:468` raises
`STRATEGY_SIZING_SEMANTICS_UNCONFIRMED` (`readiness/enums.py:77`) scoped to revisions
that actually carry one of the three magnitudes.

I initially flagged an unclearable blocker, because
**`frontend/src/components/StrategyConfigForm.tsx` has ZERO commits in this window** and
never mentions `size_semantics`. That inference was wrong: the stamp lives one layer
down, at **`frontend/src/lib/strategyForm.ts:627`**, asserted by
`frontend/src/test/strategyForm.test.tsx:191`. Saving from the form clears the blocker.
**No finding.** I record the false start because the grep that produced it is the obvious
one to run.

### B-2 (#551) — Is the `size <= 0` guard independent of allocation? Can a 0-notional interval create cross-item conflict?

**YES to the first. NO to the second — and the second was never true.**

| | |
|---|---|
| file:path | `backend/src/entropia/domain/backtest/engine.py:1587` |
| symbol | the guard inside `_evaluate_entry` |
| before | **`if alloc_on and size <= _ZERO:`** (`e2fa521:engine.py:1462`) — zero-size positions opened in independent mode, the default |
| after | **`if size <= _ZERO:`** — allocation-independent, with `led.portfolio_block_reason = SIZE_RESOLVED_TO_ZERO` (`:1617`), the constant published at `execution/sizing.py:414` by `600be00c` (#729, F1) |
| commit SHA | `5e524652` (#720); constant promoted by `600be00c` (#729) |
| test | `tests/unit/oracles/test_oracle_sizing.py` (incl. new `sizing.impossible_window_opens_nothing` golden) — **executed, passed** |
| issue state | **#551 CLOSED completed, closing PR #720** — matches code |
| classification | **RESOLVED-SINCE-BASELINE** |
| confidence | **HIGH** |

**On the "load-bearing" cross-item claim, I re-measured rather than inherited.** #551
§(b) argued a phantom 0-notional position could satisfy `BLOCK_OPPOSITE` and block a
later item's genuine entry, because `execution/rules.py:69` gates on direction alone and
never reads `peak_notional`. **That gate line is unchanged.** But the intervals it
consumes are built by `engine.py::build_prior_intervals` (`:708`), which drops any window
whose peak notional is not positive:

```python
notional = _safe_decimal(iv.get("peak_notional"))
if notional is None or notional <= _ZERO:
    continue
```

So the leak was **already impossible at baseline**, by a filter one layer upstream of the
gate the issue pointed at. The #551 fix removes the phantom position at source; it did
not close the cross-item hole, because that hole did not exist. **Two independent
defences now stand.** Classification of the sub-claim: **CONFIRMED-MISSING (the defect,
not the fix)** — i.e. the reported cross-item defect was not reproducible then or now.
**Confidence HIGH.**

### B-3 (#552) — Is the commission model explicit, and do implementation / schema / docstring / tests agree?

**They agree. One canonical question remains open.**

| | |
|---|---|
| file:path | `backend/src/entropia/domain/backtest/execution/booking.py:111` |
| symbol | `close_position` |
| before | `commission_lot = costs.commission * 2 if is_full else costs.commission * 2 * fraction` — a partially-closed position paid **1.4** round trips |
| after | **`commission_lot = costs.commission`** — one close is one fill and pays one commission |
| commit SHA | `5e524652` (#720) |
| test | `tests/unit/oracles/test_oracle_position_lifecycle.py` + two **new** goldens (`costs.commission_round_trip`, `costs.commission_scale_ladder`) — **executed, passed** |
| issue state | **#552 CLOSED completed, closing PR #720** — matches code |
| classification | **RESOLVED-SINCE-BASELINE** |
| confidence | **HIGH** |

Four-way agreement, checked one by one:

| Surface | Says | Agrees? |
|---|---|---|
| implementation | `booking.py:111` — one commission per close fill; entry fill charged separately at `:239-240` | ✅ |
| schema | `domain/strategy/config.py:313` — `description="Per-trade fee"` | ✅ |
| docstring | `booking.py:86-96` — *"This close is ONE fill and pays ONE `commission`"*, and it names the old model it replaced | ✅ |
| tests | four goldens plus the lifecycle oracle | ✅ |
| helper naming | `execution/costs.py:128` — `_cost_params` returns `(half_spread, slippage_fraction, per_fill_commission)` | ✅ |

**Still open, and it is not a code defect.** The commission **BASE** was never
adjudicated: the shipped field is a **flat per-fill amount**, while Master Ref §8's
reading is **bps-on-notional**. `docs/decisions/closure_product_decisions_2026-08-13.md`
§Karar 1 remains **unsigned**. #720 shipped the *distribution* decision (PD-2) without
the *base* decision. **Classification: PRODUCT-DECISION-REQUIRED · confidence HIGH.**

---

## §4 — Section C: research

### C-1 — Does the strict `xfail` still exist?

**NO — removed, not relaxed.**

| | |
|---|---|
| file:path | `backend/tests/integration/test_research_point_in_time_parity.py:14-20` |
| symbol | `test_both_bundles_pin_the_available_time_policy` |
| commit SHA | `69027104` (#730, P-E3 / ADIM 66) |
| generated artefact | `docs/generated/repository_facts.md:31` → **`Backend xfail markers: 0 (0 strict)`** (was `1 (1 strict)`) |
| verification | the file's own header records the marker was **REMOVED because the product changed**, not weakened to `strict=False` |
| classification | **RESOLVED-SINCE-BASELINE** |
| confidence | **HIGH** |

### C-2 — Do both bundles pin the available-time policy?

**YES — through one shared function, so neither surface can be poorer than the other.**

| | |
|---|---|
| file:path | `backend/src/entropia/application/jobs/research_data.py:549` |
| symbol | **`_pin_member`** → `TimingProvenance.from_row(revision).as_bundle_member(...)` |
| caller | **both** compilers: `compile_agent_data_bundle` (`:520`) and `compile_backtest_evidence_bundle` (`:543`) |
| commit SHA | `69027104` (#730); re-expressed through the shared object by `b7d3789e` (#734, R1) and `f5b08c27` (#742, R2) |
| test | `tests/unit/test_research_bundle_member_projection.py`, `tests/unit/test_research_point_in_time.py` — **executed, passed** |
| issue state | **#558 CLOSED completed 2026-08-17** with a **written three-part decision in the closing comment**, and Karar 2 signed A1+A2 (2026-08-14) — **state matches code and reasoning** |
| before | member = 5 fields, **no timing field** |
| after | member carries `available_time_policy`, `available_delay_seconds`, `event_time_semantics`, `frequency_policy`, `source_timezone_mode`, `source_timezone_iana`, plus `instrument_mapping_ref` |
| classification | **RESOLVED-SINCE-BASELINE** |
| confidence | **HIGH** |

### C-3 — Does `bundle_hash` cover those fields?

**YES, and the coverage is structural.**

`_seal_bundle` (`research_data.py:596`) builds `body` **including** the members and the
three derived top-level arrays (`available_time_policies`,
`instrument_mapping_revision_ids`, `feature_definition_revision_ids`), then computes
`bundle_hash = manifest_hash(body)` (`:622`). `resolved_at` and `bundle_hash` are added
**after** hashing — correctly, since a timestamp inside the hash would make it
irreproducible.

`_derived` (`:579`) **sorts**, and that `sorted()` is load-bearing: canonical JSON sorts
object keys but **not** array elements, so an unsorted projection would make the hash
depend on caller argument order.

`_BUNDLE_COMPILER_VERSION = "research-bundle-v2"` (`:72`) lives *inside* the hashed body
and separates the old and new hash spaces by itself — which is why no migration or
dual-read was needed.

**Two §9.2 names are deliberately ABSENT** — `alignment_policy_versions[]` and
`missing_and_stale_policies[]` have zero shipped source. They are **not** emitted as `[]`,
because an empty array asserts *"there are none"* (a provenance lie) where the truth is a
provenance **gap**. Recorded as a signed class-D deviation.
**Classification: DELIBERATE-FUTURE-DEV · confidence HIGH.**

### C-4 — #559 (DST fold / gap): **ISSUE-STATE-DRIFT**

**The issue is CLOSED. The code is byte-identical to baseline. No decision was ever
written down.**

| | |
|---|---|
| file:path | `backend/src/entropia/domain/market_data/validation_rules.py:218` and `domain/backtest/funding.py` |
| symbol | `resolve_timestamp` / `parse_utc` — both still `replace(tzinfo=source_zone)`, i.e. Python's `fold=0` default |
| caller | research + market ingest; funding schedule builder |
| commit SHA | **none** — `git diff e2fa521..origin/main` over both files is **EMPTY** |
| test | `tests/unit/test_research_point_in_time.py` — the three **characterization** tests still pin fold→first-occurrence and gap→accepted. **Executed, passed.** |
| doc | `docs/audit/closure_w0_containment_lift_preconditions_2026-08-17.md:98` lists **`G8` (#559) ❌** |
| issue state | **CLOSED `completed` 2026-08-18T07:23:47Z** · **0 comments** (`get_comments` → `[]`) · **0 closing PRs** · milestone *"ADIM 16-20 — unified clock programme"* |
| before | open; behaviour undecided; two characterization tests pinning it |
| after | **closed**; behaviour **identical**; still undecided; signature block still empty |
| classification | **ISSUE-STATE-DRIFT** (tracking resolved 2026-08-25 — see the addendum; the **decision** is still open) |
| confidence | **HIGH** |

The folded hour's second occurrence remains **unaddressable from a source file**: one
hour of data per DST-observing year silently collapses onto the earlier instant. That may
well be the right product answer — but it has not been *made*, and `G8` is a
gate the containment lift depends on. Closing the issue removed the tracking without
supplying the decision. **This is the same failure shape the repository already
adjudicated once for A-08 (#514) in ADIM 29/51.**

### C-5 — #544 (NET semantics): the same drift, a second time

Discovered while verifying C-4 — the two were closed **one second apart**.

| | |
|---|---|
| file:path | `domain/allocation/rules.py:220-227` (warning), `domain/allocation/enums.py:37-52` (docstring), `frontend/src/lib/allocation.ts:231` (label) |
| commit SHA | **none** — `git diff e2fa521..origin/main` over all three is **EMPTY** |
| issue state | **CLOSED `completed` 2026-08-18T07:23:46Z** · **0 comments** · **0 closing PRs** · labels `product-decision`, `blocks-adim-19` |
| before / after | NET undefined, disclosure counterfactual / **unchanged** |
| classification | **ISSUE-STATE-DRIFT** (tracking resolved 2026-08-25 — see the addendum; the **decision** is still open) |
| confidence | **HIGH** |

Precondition 20 (`G14`) is therefore still open on the evidence, and the counterfactual
disclosure #544 called out — *"the engine executes NET conservatively as BLOCK_OPPOSITE"*,
advertised while containment means no shared run executes — is still shipping verbatim in
both the warning and the browser label.

**One genuine improvement, unrecorded on the issue:** the new phase loop **refuses** NET
rather than downgrading it —
`execution/arbitration.py:148` `NET_SUPPORT_STATUS = "undefined_in_canon"`, with
`NET_UNDEFINED_SEMANTICS` enumerating the five things that must be decided and
`NET_TRACKING_ISSUE = "GH #544"` still pointing at the now-closed issue. Fail-closed on
the contained path, counterfactual on the shipped one.

---

## §5 — Section D: performance

### D-1 — Do the signal leg and research leg still read `get_dataset_root` inside the loop?

**NO — both were batched. `CLAUDE.md` says otherwise and is stale (see §7.1).**

| | |
|---|---|
| file:path | `backend/src/entropia/application/commands/readiness_check.py:629` (signal leg), `:818` (research funding leg) |
| symbol | `market_repo.get_dataset_roots` / **`research_repo.get_dataset_roots`** (new plural reader, mirroring the market one field for field) |
| caller | `_resolve_signal_market_data_issues`, `_resolve_research_sources` |
| commit SHA | **`bb1e76c6`** — *"perf(stage-62): batch the signal and research dataset-root lookups"*, merged as **#712** (`06503698`) |
| test | `backend/tests/integration/test_query_budgets.py` (Postgres — **not executed here**) |
| doc | `docs/performance/query_budgets.json` → both rows `per_item: 0`, `queries_large: 2` |
| before | slope **1.0** each (12 statements at 11 items) |
| after | **`per_item: 0`** |
| classification | **RESOLVED-SINCE-BASELINE** |
| confidence | **HIGH** (source + budget file) / **MEDIUM** on the measured slope — the budget test needs Postgres and is CI's evidence |

Four more legs were batched in the same window: `tick_data_leg` (P1, `ab51d080` #751),
`admission_tick_pins` (P4, `347fe19c` #754 — the **first** budget row on the admission
path), `strategy_mirror_leg` (P2, `c2c966e3` #766). Singular `get_dataset_root` survives
only at non-loop call sites (single-entity commands and queries).

**One leg remains N+1, deliberately.** `_resolve_external`
(`readiness_check.py:360`, inside `for item, available in enabled:`) is still per-item,
because batching it changes **which row wins** when two items pin the same
`work_object_revision_id` — a column that is **not UNIQUE**. That is gate **G15**, an
undecided product question, not an oversight.
**Classification: PRODUCT-DECISION-REQUIRED · confidence HIGH.**

### D-2 — Do the query-budget tests cover the full production path?

**PARTIAL — better than at baseline, and the gaps are self-documented.**

A whole-operation row now exists: `readiness_check.run_readiness_check` (added by
`e865b965`, #741 / P3), measuring end-to-end rather than per-helper, precisely because
growth *between* legs is invisible to every per-leg row. It records
**`per_item: 1`** — an honest measurement of leg 3, not a passing grade.

Three limits the budget file states about itself, which I verified rather than took
on trust:

1. **The identity-map blind spot.** A `session.get` on a PK a batch already warmed issues
   **no SQL**, so the counter cannot see it. `strategy_mirror_leg`'s note says the row
   therefore catches a *removed* batch, not a *redundant read*. Enforcement of that shape
   is a **source-level** assertion, not a count.
2. **A row is only as wide as its fixture.** `run_readiness_check`'s own note records
   that its trade-log fixture never opens the tick leg, and that a fixture leaving
   `tick_policy` at `inherit` reports a green slope of **0** for a leg that never ran.
3. **Coverage is not universal.** Ten surfaces are budgeted. Run admission has exactly
   **one** row (`admission_tick_pins`) and the rest of admission is unmeasured.

**Classification: PARTIAL · confidence HIGH.**

---

## §6 — Section E: A11Y

### E-1 — Is there real new human evidence in the worksheet?

**NO. Not one cell.**

| | |
|---|---|
| file:path | `docs/audit/a11y_screen_reader_audit_results.md` |
| commit SHA | `99a7f302` (#820), `32d2c969` (#822), `d012a639` (#719) — **+176 / −12 lines, all prose** |
| Section A | **2 / 184** cells — unchanged from 2026-08-12 |
| Section B | **0 / 10** flows — unchanged |
| SR-1 (NVDA / Firefox) | **never started** — no machine, no auditor |
| Exit criteria | **0 / 4**, all `☐` |
| classification | **CONFIRMED-MISSING** |
| confidence | **HIGH** |

#820's own commit message is explicit and honest: *"A-08 stays HUMAN-BLOCKED. No cell was
filled, no counter moved."* It also records that the precheck refresh was **attempted and
failed** (no Docker daemon, no minio) and that the counts were **deliberately left at
their 2026-08-12 provenance** rather than refreshed from an improvised stack — a
differently-provisioned stack races the first data render, which is the documented reason
K-5 and K-7 drift between runs.

The 176 added lines are a next-session card, corrections to stale §4/§6.4 statements, and
four stale `note:` strings in `20-a11y-prechecks.spec.ts`. **Real work; not audit
evidence.**

### E-2 — Do #514's state and the evidence say the same thing?

**YES — and this is the one place where a previously-recorded drift is genuinely closed.**

| | |
|---|---|
| issue state | **#514 OPEN**, `state_reason: reopened`, label `human-only`, last updated 2026-08-12T11:08:58Z |
| evidence | worksheet says `A-08 HUMAN-BLOCKED`, 2/184, 0/10, 0/4 |
| agreement | **CONSISTENT** — both say "started, nowhere near done" |
| classification | **CONFIRMED-MISSING** (the audit) / **no drift** (the tracking) |
| confidence | **HIGH** |

**Contrast with C-4 / C-5.** #514 is open *because a human deliberately re-opened it
rather than let a CLOSED state stand over an empty ledger*. #559 and #544 are the mirror
image: closed states standing over unchanged code and unwritten decisions. The repository
has already adjudicated the right answer for this exact shape — it just was not applied
to those two.

---

## §7 — Documentation and process drift

### §7.1 — `CLAUDE.md` contradicts itself about P-E2 — **DOCUMENTATION-DRIFT**

| | |
|---|---|
| file:path | `CLAUDE.md:1818-1820` |
| claim | *"**Ready Check'in kalan İKİ N+1 bacağı hâlâ canlı** (`readiness_check.py:554` sinyal, `:749` research; ölçülen slope **1.0**) — P-E2 **merge EDİLMEDİ** ve ikisi için **hiç issue açılmadı**"* |
| measured | P-E2 **is** merged (`bb1e76c6`, PR #712); both budget rows read **`per_item: 0`**; the cited line numbers no longer point at those reads |
| self-contradiction | **`CLAUDE.md:1368`**, in the same file, records *"ADIM 62 … P-E2, PR #712"* as landed |
| gate coverage | `scripts/generate_repository_facts.py --check` — **executed, PASSES**. It validates generated artefacts and doc classification; it does **not** read narrative prose. |
| classification | **DOCUMENTATION-DRIFT** |
| confidence | **HIGH** |

Same block, same sentence: *"#514/#558/#559 **açık kaldı**"* — **#558 and #559 are both
closed** (2026-08-17 and 2026-08-18).

### §7.2 — `CLAUDE.md`'s `Next:` pointer is stale — **DOCUMENTATION-DRIFT**

`CLAUDE.md:1826` still reads *"**Next:** **PR B** — `ItemParticipant` adaptörü +
`jobs/backtest_engine.py:299` call site"*. **PR B landed** — the adapter as `2cda24f5`
(#777) and the call site as `39947256` (#799). `jobs/backtest_engine.py:299` is now
inside `_prepare_strategy`, unrelated to the seam. **Confidence HIGH.**

### §7.3 — A real regression, introduced and repaired inside the window

**The only REGRESSED-SINCE-BASELINE finding — and it is already fixed.**

| | |
|---|---|
| file:path | `backend/tests/unit/oracles/test_oracle_portfolio_containment_gate.py:285-296`; cause in `application/jobs/backtest_engine.py` |
| introduced by | **`39947256`** (#799) — the shared-branch helper looped with the same variable name, giving the worker a **second copy** of `for prepared in prepared_items:` |
| effect | deleting the **real** independent item loop left the containment tripwire **GREEN** — i.e. every independent composite Result could be silently re-priced through the shared fold, with no flag, no `ENGINE_VERSION` bump and nothing a reader could see |
| window | on `main` from 2026-08-24T04:18Z to 2026-08-24T07:34Z (~3h16m) |
| repaired by | **`3f557c72`** (#805) — helper renamed to `pinned`; assertion strengthened from `in` to `count(...) == 1` |
| verified now | `grep -c "for prepared in prepared_items:"` → **1**; gate tests **executed, 55 passed** |
| classification | **REGRESSED-SINCE-BASELINE → RESOLVED** |
| confidence | **HIGH** |

**The transferable lesson:** a text-scan tripwire proves *presence*, not *singularity*. A
comment quoting the guarded line is indistinguishable from the line itself to a scanner —
which is why #805's explanatory comment deliberately does **not** spell it out.

### §7.4 — The containment invariant was deliberately WEAKENED

Not a defect — a signed, documented change of what containment means. Recording it
because a reader comparing gate source across the window will otherwise misread it.

| | before | after |
|---|---|---|
| loop callers | `assert callers == []` — *nothing* calls the phase loop | `_AUTHORISED_LOOP_CALLERS = ["application/jobs/backtest_engine.py"]` (`:123`, asserted `:279`) |
| projection callers | zero importers | `_AUTHORISED_PROJECTION_CALLERS` — same single module (`:128`, `:347`) |
| importer allowlist | one signed module | **unchanged** — `d4efac3a`/#801 signed Option A specifically so the worker stays a **CALLER** of the phase loop, never an **IMPORTER** of its vocabulary |

The gate's own comment (`:119`) states the cost: *"the invariant is genuinely weaker (no
production REQUEST reaches the loop)"*. The signed decision
(`closure_c4_worker_importer_visibility_2026-08-19.md`) also accepts an explicit honest
boundary — **the worker's reach into the contained subsystem is invisible to the importer
guard**: *"it does not import"* is true, *"it does not access"* is false.
**Classification: DOCUMENTATION-DRIFT risk, not a defect · confidence HIGH.**

### §7.5 — Acceptance-debt ledger: verified live, no drift

Re-derived by executing the scanner rather than reading the ledger:

```
acceptance ratchet OK: 55 partial / 7 uncovered against a frozen ceiling of 55 / 7;
classes {'A': 1, 'B': 23, 'C': 6, 'D': 32}
OK: 383 criteria / 1175 clauses validate against the live test tree
```

306 covered / 55 partial / 7 uncovered / 383 total; open debt **62**. **Matches
`CLAUDE.md`'s ADIM 107/108 figures exactly.** Docs 16 and 18 are complete (16/16, 18/18).
**No drift · confidence HIGH.**

---

## §8 — Containment-lift preconditions, re-measured

`closure_w0_containment_lift_preconditions_2026-08-17.md` recorded **2 of 22 green**.
Re-measured against `a7261de`:

| # | Precondition | 2026-08-17 | **2026-08-25** | Evidence |
|---|---|---|---|---|
| 1 | (baseline green) | ✅ | ✅ | — |
| 7 | Reconciliation invariant | ❌ | **✅** | `participant.py:17-28`; `test_oracle_engine_participant.py` |
| 8 | Sleeve-parity invariant | ❌ | **✅** | `participant.py:345`, checked every deciding tick |
| 9 | `_use_unified_clock` branch | ❌ | **✅** | `jobs/backtest_engine.py:159`, `:367` |
| 10 | Tick-strided cancel checkpoint (A21) | ❌ | **✅** | checkpoint #3b, `:1224` |
| 11 | Gate narrowed to an authorised-caller allowlist | ❌ | **✅** | `_AUTHORISED_LOOP_CALLERS`, `:123` |
| 12 | Behavioural proof independent runs never enter the loop | ❌ | **✅** | `test_shared_clock_worker_branch.py`; two-world gate |
| 13 | Deferred-fill / limit-order admission blocker (P2, **G11**) | ❌ | ❌ *briefed `c2a7d03c`* | engine-side refusal only; `C6` unbuilt |
| 14 | Scaling admission blocker (P8, **G12**) | ❌ | ❌ *block created `234b6bc9`* | same |
| 15 | OD-6(a) blocker | ❌ | ❌ | `execution/intents.py:19` |
| 16 | OD-1(a) blocker | ❌ | ❌ | `execution/clock.py:38` |
| 17 | OD-2 mark policy flip | ❌ | ❌ | `provenance.py:80` = `"undefined_pending_od2"` |
| 18 | `CONTENTION_SELECTION_STATUS` flip | ❌ | ❌ | `arbitration.py:195` = `"recommended_pending_approval"` |
| 19 | R-1 allocation revision pin | ✅ | ✅ | `test_allocation_revision_pin.py` |
| 20 | GH **#544** closed | ❌ open | ⚠️ **was closed-undecided; RE-OPENED 2026-08-25**. **2026-08-27: decision `B` SHIPPED** (`0044_drop_net_conflict_policy` — NET dropped from the enum, column CHECK added, `B3` halt guard). The row asks for the ISSUE to be closed and that is `human-only`. | §5 C-5 + addendum — **still not a green** |
| 21 | GH **#559** closed | ❌ open | ⚠️ **was closed-undecided; RE-OPENED 2026-08-25** | §4 C-4 + addendum — **still not a green** |
| 22 | A15 bump + A16 manifest policy fields | ❌ | ❌ | manifest carries **none** of the four (`test_...containment_gate.py:374`) |

**Count: 8 of 22 green (was 2).** Preconditions 20 and 21 are marked ⚠️ and **not
counted green**: the literal wording ("issue closed") is now satisfied, but the decision
the precondition exists to secure was never written. Counting them would move the tally
to 10 on a technicality and is exactly the substitution this audit was asked to refuse.

**`G10`** (ADR §16 Gate 2 — flag-flip approval) has still **not been requested**.
**`G16`** (A-08 / #514) remains open, so the RC verdict is blocked regardless.

---

## §9 — Final summary table

| Requirement | `e2fa521` state | Current `origin/main` state | Changed commit | Classification | Confidence |
|---|---|---|---|---|---|
| **A-1** `run_portfolio` production caller | none | none (worker calls `iter_portfolio` instead) | — | IMPLEMENTED-BUT-UNWIRED | HIGH |
| **A-2** real `ItemParticipant` | none (test-only) | `_EngineParticipant`, 1 prod caller | `2cda24f5` (#777) | IMPLEMENTED-BUT-CONTAINED | HIGH |
| **A-3** engine adapter besides `_ItemStepper` | none | one adapter *over* `_ItemStepper`; no rival engine | `2cda24f5` | IMPLEMENTED-BUT-CONTAINED | HIGH |
| **A-4** worker outer loop | item, unconditional | item in `else`; tick-driven sibling above | `39947256` (#799) | IMPLEMENTED-BUT-CONTAINED | HIGH |
| **A-5** `combine_item_runs` in shared mode | only path | **not used** on shared arm; unchanged on independent | `39947256` | IMPLEMENTED-ACTIVE (indep.) | HIGH |
| **A-6** `project_portfolio_run` caller | **zero importers** | **one authorised caller** (`:1245`) | `39947256` | IMPLEMENTED-BUT-CONTAINED | HIGH |
| **A-7** `build_portfolio_manifest` caller | none | none | — | IMPLEMENTED-BUT-UNWIRED | HIGH |
| **A-8** `SHARED_ALLOCATION_STATUS` | `future_dev` | **`future_dev`** (file diff empty) | — | DELIBERATE-FUTURE-DEV | HIGH |
| **A-9** unified Result persisted | no path | full persist path wired, unreachable | `39947256` | IMPLEMENTED-BUT-CONTAINED | HIGH / MED (runtime) |
| **A-10** P2 / P8 | not modelled | refused at construction; `C6` unbuilt | `2cda24f5` | PARTIAL + PRODUCT-DECISION-REQUIRED | HIGH |
| **B-1** #550 percent parity | units vs `%` label | `_percent_of_capital`, one conversion | `5e524652` (#720) | RESOLVED-SINCE-BASELINE | HIGH |
| **B-1b** #550 transition gate | none | `size_semantics` + `STRATEGY_SIZING_SEMANTICS_UNCONFIRMED`, clearable | `5e524652` | IMPLEMENTED-ACTIVE | HIGH |
| **B-2** #551 zero-size guard | `alloc_on and size<=0` | `size <= 0` | `5e524652` | RESOLVED-SINCE-BASELINE | HIGH |
| **B-2b** #551 0-notional cross-item leak | filtered by `build_prior_intervals` | same filter + guard | — | CONFIRMED-MISSING (defect not reproducible) | HIGH |
| **B-3** #552 commission model | 1.4 round trips | per-fill; impl/schema/docstring/tests agree | `5e524652` | RESOLVED-SINCE-BASELINE | HIGH |
| **B-3b** commission BASE (flat vs bps) | undecided | **undecided**, Karar 1 unsigned | — | PRODUCT-DECISION-REQUIRED | HIGH |
| **C-1** #558 strict xfail | 1 strict | **0 (0 strict)**, removed not relaxed | `69027104` (#730) | RESOLVED-SINCE-BASELINE | HIGH |
| **C-2** both bundles pin time policy | neither | both, via `_pin_member` | `69027104`, `f5b08c27` | RESOLVED-SINCE-BASELINE | HIGH |
| **C-3** `bundle_hash` covers them | invariant under policy change | covered; `research-bundle-v2` | `69027104` | RESOLVED-SINCE-BASELINE | HIGH |
| **C-3b** 2 of §9.2's names absent | absent | absent, signed class-D | — | DELIBERATE-FUTURE-DEV | HIGH |
| **C-4** #559 DST | open, undecided | **was closed**, code identical, 0 comments/PRs → **re-opened 2026-08-25** | — | **ISSUE-STATE-DRIFT** (tracking resolved; decision open) | HIGH |
| **C-5** #544 NET | open, counterfactual | **was closed**, all 3 files identical → **re-opened 2026-08-25** | — | **ISSUE-STATE-DRIFT** (tracking resolved; decision open) | HIGH |
| **D-1** signal + research legs | slope 1.0 each | **`per_item: 0`** both | `bb1e76c6` (#712) | RESOLVED-SINCE-BASELINE | HIGH |
| **D-1b** leg 3 `_resolve_external` | per-item | **per-item**, gate G15 | — | PRODUCT-DECISION-REQUIRED | HIGH |
| **D-2** budgets cover full path | per-leg only | whole-operation row added, `per_item: 1` | `e865b965` (#741) | PARTIAL | HIGH |
| **E-1** new human SR evidence | 2/184, 0/10 | **2/184, 0/10** | — | CONFIRMED-MISSING | HIGH |
| **E-2** #514 state vs evidence | consistent (reopened) | **consistent** | — | no drift | HIGH |
| **§7.1** `CLAUDE.md` P-E2 claim | — | contradicts itself and the code | — | **DOCUMENTATION-DRIFT** | HIGH |
| **§7.2** `CLAUDE.md` `Next: PR B` | — | PR B landed | — | **DOCUMENTATION-DRIFT** | HIGH |
| **§7.3** containment tripwire shadow | intact | broken by #799, **repaired by #805** | `39947256` → `3f557c72` | **REGRESSED → RESOLVED** | HIGH |
| **§7.4** containment invariant | `callers == []` | one authorised caller (signed) | `39947256`, `d4efac3a` | signed weakening | HIGH |
| **§7.5** acceptance debt | — | 55/7, A1 B23 C6 D32 — verified live | many | no drift | HIGH |

---

## §10 — Closing block

**Current `origin/main` SHA:** `a7261deb615e795ca5428f1f11543427a72bcddb`
(2026-08-25 12:34:07 +0300)

**Commits since `e2fa521`:** **150** (baseline confirmed an ancestor; linear delta)

### Resolved findings (9)

1. **#550** — percent-of-capital sizing, single conversion point, plus a clearable
   transition gate (`5e524652`)
2. **#551** — zero-size guard made allocation-independent (`5e524652`); the cross-item
   half was never reproducible
3. **#552** — per-fill commission; implementation, schema, docstring and tests agree
   (`5e524652`)
4. **#558** — both bundles pin the time policy; `bundle_hash` covers it; strict xfail
   **removed** (`69027104`, `b7d3789e`, `f5b08c27`)
5. **#617 / #618 siblings** — Ready Check signal + research legs batched to `per_item: 0`
   (`bb1e76c6`)
6. **Tick-data leg, admission tick pins, strategy mirror leg** batched
   (`ab51d080`, `347fe19c`, `c2c966e3`)
7. **Whole-operation Ready Check budget** added — the between-legs blind spot now measured
   (`e865b965`)
8. **`ItemParticipant` adapter + two invariants** shipped; preconditions 7/8 green
   (`2cda24f5`)
9. **Shared-clock worker branch + tick-strided cancel checkpoint**; preconditions
   9/10/11/12 green (`39947256`, `3f557c72`)

### Still-open findings (9)

1. **A-08 human screen-reader audit** — 2/184 cells, 0/10 flows, SR-1 never started,
   **0/4** exit criteria. #514 correctly OPEN. **The sole RC blocker.**
2. **#559 (G8)** — **re-opened 2026-08-25** with the measurement recorded on the issue; the
   DST fold/gap rule is still undecided and the code is still baseline-identical
3. **#544 (G14)** — **re-opened 2026-08-25**, same treatment; NET still undefined and the
   counterfactual disclosure still shipping
4. **Commission BASE** (flat per-fill vs bps-on-notional) — Karar 1 unsigned
5. **G11 / G12** — P2 and P8 admission blockers briefed but unsigned; **`C6` unbuilt**
6. **G15** — Ready Check leg 3 `_resolve_external` N+1; batching it changes which
   non-UNIQUE row wins
7. **G10** — ADR §16 Gate 2 flag-flip approval **never requested**
8. **Preconditions 15–18** — OD-6, OD-1, OD-2, `CONTENTION_SELECTION_STATUS` all pending
9. **Precondition 22** — run manifest carries none of the four policy fields;
   `build_portfolio_manifest` still uncalled

### New regressions (1, already repaired)

* **Containment tripwire shadowed by #799** — a duplicate loop header let the gate stay
  green with the guarded loop deleted. Live on `main` ~3h16m; repaired by **#805**, which
  also strengthened `in` → `count(...) == 1`. **Verified fixed.**

### New hidden implementations (4)

Shipped, functional, and reachable **only from tests** — the category most likely to be
misread as "done":

1. **`domain/backtest/participant.py`** (530 lines) — a complete engine-backed
   `ItemParticipant` with two runtime invariants and an eleven-shape refusal table
2. **`_replay_shared_clock`** (`jobs/backtest_engine.py:1147`) — a full tick-driven
   co-simulation arm with its own cancel checkpoint and three fail-closed error paths
3. **`project_portfolio_run` wiring** — the shared arm's Result projection, now with one
   authorised caller
4. **The complete unified-Result persist path** — `output` → `derive_metric_values` →
   `bt_repo.create_result`, sharing the independent arm's tail verbatim

All four sit behind `SHARED_ALLOCATION_STATUS == "future_dev"` and the admission guard.
**Nothing a user can reach executes any of it.**

### Tests actually executed (this container)

```
uv sync --all-extras                                            exit 0
uv run pytest --no-cov -p no:randomly  (9 files)                exit 0
    123 passed in 1.63s          0 failed   0 skipped   0 xfail
      tests/unit/oracles/test_oracle_portfolio_containment_gate.py
      tests/unit/oracles/test_oracle_engine_participant.py
      tests/unit/test_shared_clock_branch_predicate.py
      tests/unit/test_shared_allocation_two_world_gate.py
      tests/unit/test_shared_allocation_containment.py
      tests/unit/oracles/test_oracle_sizing.py
      tests/unit/oracles/test_oracle_position_lifecycle.py
      tests/unit/test_research_bundle_member_projection.py
      tests/unit/test_research_point_in_time.py

uv run pytest tests/unit/test_backtest_engine_golden.py          exit 0   2 passed
python scripts/generate_repository_facts.py --check              exit 0
    "documentation-truth gate OK — artefacts fresh, documents classified,
     no stale claims."
python docs/audit/acceptance_semantic_scan.py --report           exit 0
    306 covered / 55 partial / 7 uncovered / 383 criteria / 1175 clauses
python docs/audit/acceptance_semantic_scan.py --ratchet          exit 0
    55 partial / 7 uncovered vs frozen 55 / 7; {'A':1,'B':23,'C':6,'D':32}
```

**NOT executed, and therefore NOT claimed:** the backend integration / contract / e2e
suites (no Postgres daemon), backend coverage (`--no-cov` throughout), and **every**
frontend gate (no `node_modules`). Pass counts and coverage percentages for those remain
**CI's authority**. Exit codes above were read separately from stdout; no output was piped
through `tail`.

### CI evidence

| Run | SHA | Status |
|---|---|---|
| CI #2286 | **`a7261de` (HEAD)** | **`in_progress`** at measurement — *the current HEAD has no completed CI* |
| CI #2283 | `32d2c96` | `success` — newest completed green main run (docs-only commit) |
| CI #2280 / #2278 / #2275 / #2273 / #2271 / #2269 / #2267 / #2264 | | all `success` |

Main's recent history is uniformly green. **`a7261de` itself is unverified by CI at the
time of this audit** — it is a docs-only closing commit, but that is an inference, not a
CI result.

### Recommended implementation sequence

Ordered by *what unblocks what*, not by size. Items 1–3 are signatures, not code, and
three of the four cost nothing but a decision.

1. ~~**Re-open #559 and #544, or record their decisions.**~~ **The re-open half is DONE
   (2026-08-25)** — both carry a written reason on the issue. **The decisions are still
   owed:** write the DST fold/gap rule and the define-or-remove-NET answer into
   `docs/decisions/` with a signature, the way Karar 2 was recorded for #558, then close
   them again. Until that exists, `G8` and `G14` block the lift and preconditions 20/21
   stay amber. **Still the cheapest item and the one most likely to be mistaken for done —
   a re-opened issue is not a decision either.**
2. **Sign `G11` + `G12`** (P2 deferred fills, P8 scaling). Both are briefed; the engine
   already refuses these shapes. The signature is the only thing standing between the
   refusal table and `C6`.
3. **Sign the commission BASE (Karar 1).** #720 shipped the distribution model (PD-2)
   while the base — flat per-fill vs bps-on-notional — stayed unadjudicated. A shipped
   financial model with half its adjudication missing is the same debt shape #552 was.
4. **Build `C6`** — turn `participant._unsupported_shapes` into user-visible Ready Check
   blockers. Today a scaling or limit-order strategy in a shared composition would fail
   as `ENGINE_ERROR` at replay rather than being refused at admission. Depends on 2.
5. **Decide `G15`**, then batch Ready Check leg 3. The question is which row wins on a
   non-UNIQUE `work_object_revision_id` — a correctness question with a performance
   side-effect, in that order.
6. **Preconditions 15–18** (OD-6, OD-1, OD-2, `CONTENTION_SELECTION_STATUS`), then
   **precondition 22** (`build_portfolio_manifest` wiring + the four manifest policy
   fields + the A15 `ENGINE_VERSION` bump). This is the bulk of the remaining engineering.
7. **Request `G10`** (ADR §16 Gate 2). It has never been asked for. It cannot be the last
   step discovered.
8. **`C9` / the flag flip — LAST.** Preconditions stand at **8 of 22**. The measured
   consequence of lifting early is on record: the sequential fold reports drawdown
   **5000** where the truth is **3000**.
9. **A-08** runs on its own track and gates the RC verdict independently of all of the
   above. It needs an **auditor and a Windows/NVDA machine** — neither of which any
   further code slice can supply.

**Verdict unchanged: BLOCKED. One blocker — A-08.** No slice in this window changed the
blocker count, and none claimed to.

---

*Read-only forensic audit. No production file was modified. Every number above was
re-derived from `a7261de`; the executed-test block is this container's own measurement,
and everything attributed to CI is labelled as such.*
