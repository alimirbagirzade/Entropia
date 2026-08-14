<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge bir ÖLÇÜMDÜR, canlı handoff DEĞİLDİR.** `ac5cf50`'de
> ölçülen durumu kaydeder; SHA'lar, sayılar ve "next" maddeleri bayatlayabilir. Güncel
> otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`.
> **`historical` işareti bu belgenin bulgularını geçersiz kılmaz** — bu repoda her denetim
> kaydı `historical`'dır (üç W0 denetimi dahil), çünkü `current` yalnız canlı kickoff'a
> aittir ve `check_classification` bunu CI'da zorlar.

# P-B — Final closure reconciliation

**DOCS-ONLY. No production behaviour was changed by this session.** The only non-`docs/`
edit is a stale docstring sentence in one oracle test (§5.4); it changes no assertion and no
executable statement. `backend/src`, `frontend/src` and `backend/alembic/versions` are
byte-identical to `origin/main`.

This document reconciles the three W0 forensic audits against **current `main`**, and keeps
four axes apart on purpose:

| Axis | Question it answers |
|---|---|
| **IMPLEMENTATION TRUTH** | what the code on `main` actually does, measured this session |
| **DOCUMENTATION TRUTH** | what the repository's documents claim, and where that has expired |
| **GITHUB BOOKKEEPING** | issue/PR state — a record of work, never evidence of it |
| **PRODUCT DECISION** | what a human must rule on before code may move |

Conflating them is what produced most of the drift repaired below. A closed issue is not a
fixed defect; a green test is not a working feature; an existing symbol is not a wired one.

---

## §0 — Base

| | |
|---|---|
| **Measured on** | **`ac5cf50fe3f1257ffff9c5c10eec833bfdb3ce3f`** (`origin/main`) |
| Measurement date | **2026-08-14** (the closure wave is dated 2026-08-13; the filename carries the wave, this row carries the clock) |
| Base of the three source audits | `0d8bf8f7134d86d77a7eee10023dadd3d80aab0d` |
| Delta | **`0d8bf8f` → `ac5cf50`: 9 commits**, including PRs **#707, #708, #710, #711, #716, #717, #718**. Two of them changed `backend/src`. |
| alembic head | `0043_i08_registry_strategy_fks` (single head, unchanged) |
| `ENGINE_VERSION` | `backtest-engine-v18-gap-adjusted-stop-fill` (`domain/backtest/manifest.py:126`) — **unchanged on `main`** |
| `SHARED_ALLOCATION_STATUS` | `future_dev` (`domain/allocation/capability.py:105`) |
| Release verdict | **BLOCKED. Blocker count 1 (A-08 only).** Unchanged by this session. |

**Two pull requests are in flight against this base and are NOT merged.** Every statement in
this document describes `main`, not either branch:

| PR / branch | What it would change | State |
|---|---|---|
| **#720** `feat/stage-58-sizing-commission-zero-size` | fixes #550 / #551 / #552; bumps `ENGINE_VERSION` to `backtest-engine-v18-percent-sizing-per-fill-commission` | **OPEN**, `mergeable_state: blocked`, 52 files, +1090 −226 |
| `fix/closure-e2-ready-check-batching` (P-E2) | batches the two residual Ready Check N+1 legs | **NOT MERGED** — 1 commit ahead of `ac5cf50` |

> **The prompt's input `docs/decisions/closure_product_decisions_2026-08-13.md` does not
> exist.** `docs/decisions/` contains exactly one file, `2026-08-03_shared_portfolio_containment.md`.
> The `PD-1…PD-7` decisions cited by PR #720 and by the #550 reopen comment have **no
> repo-side record at all** (§7.1). This is a documentation-truth gap, not a missing input.

---

## §1 — The three source audits, and what has expired since

All three are `doc-status: historical` and correctly marked. They were measured at `0d8bf8f`.
Nothing below rewrites their historical bodies; this section records which of their statements
stopped being true.

| Source audit | PR | Verdict on current `main` |
|---|---|---|
| `closure_w0_shared_portfolio_2026-08-13.md` (P-A1) | #707 | **Conclusions all hold.** Every `portfolio_engine.py` line number is **+13** (§3.1). |
| `closure_w0_financial_semantics_2026-08-13.md` (P-A2) | #708 | **All three defects still live on `main`**, re-verified this session at the same `file:line`. Its "6 PO decisions pending" is now **partly superseded** — see §7. |
| `closure_w0_research_perf_obs_drift_2026-08-13.md` (P-A3) | #710 | **DR-1 and DR-5 are CLOSED** (§5.1). DR-2/DR-3/DR-4 were still live and are repaired here. §B's two N+1 legs are still live on `main`. |

### 1.1 Expired statements, named

| Statement | Where | Status on `ac5cf50` |
|---|---|---|
| "`run_portfolio` at `portfolio_engine.py:518`" | P-A1 §0, §1, matrices | **stale coordinate** → `:531` |
| "`ItemParticipant` at `portfolio_engine.py:238`" | P-A1 §0, §2 | **stale coordinate** → `:251` |
| "DR-1 … Not repaired here" | P-A3 §D.4 | **CLOSED** by `056aafe` (#698); recorded by #711 |
| "DR-5 … stale comment in production source" | P-A3 §E.2 | **CLOSED** by #711 |
| "K-3 OPEN — reported, not gated. PO." | P-A3 §D.3 | **ADJUDICATED** (D-11) — P-A3's own §I addendum already says so |
| "PO decisions pending: 6" | P-A2 §Executive verdict | **partly superseded** by PD-2 / PD-6 and PR #720 (§7) |
| "`repository_facts.md` records 3541 collected" | P-A3 §E.3 | now **3545** |

---

## §2 — Canonical decisions in force

| Decision | Source | Binding on |
|---|---|---|
| ADR 0002 is **Accepted** (2026-08-05) | `docs/adr/0002-…md` header, §16 | the unified-clock programme |
| **ADIM 16 is NO LONGER SKIPPED** | ADR 0002 **§12 AMENDMENT** (`:713`), PR #602 | supersedes `:690`'s "never written" paragraph *in the same file* |
| ADR §16 human gate | ADR 0002 §16 | any slice that changes a shipped number |
| Shared-allocation containment | `docs/decisions/2026-08-03_shared_portfolio_containment.md` | `SHARED_ALLOCATION_STATUS` |
| D-10 — 45 accent-blue nodes, **signed permanent deviation** | `a11y_ci_ratchet_and_adjudication.md` §4 | WCAG 1.4.3 — **product is not conformant for this SC** |
| D-11 — no `contentinfo` landmark required | same, §4b | retires K-3 as an expectation defect |
| **#550 option A — adopt canon (percent)** | GH #550 comment, 2026-08-04, re-affirmed 2026-08-13 | sizing semantics |
| **PD-2 — per-FILL commission is canonical** | cited by PR #720; **no repo-side record** | commission split |

**ADR 0002 §12's self-correction is the single most misread thing in this repository.** Line
690 says ADIM 16 "was never written, and is now formally SKIPPED"; line 713 explicitly
supersedes it. A reader who stops at `:690` concludes the opposite of the truth. The ADR is
**not** drifted — but every document that quotes `:690` without `:713` is.

---

## §3 — Implementation truth: shared portfolio subsystem

### 3.1 `_ItemStepper` is PRODUCTION-ACTIVE. The "never written" claim is dead.

Measured chain on `ac5cf50`, every hop re-derived this session:

```
application/jobs/backtest_engine.py:859   run_engine(...)        <- PRODUCTION worker
  └─ domain/backtest/engine.py:3279       def run_engine
       └─ engine.py:3350                  stepper = _build_stepper(...)
            └─ engine.py:793              def _build_stepper
                 └─ engine.py:3263        return _ItemStepper(...)   <- CONSTRUCTION
                      └─ engine.py:756    class _ItemStepper         <- DEFINITION
```

`_ItemStepper` is reached on **every single-item backtest run that ships today**. It is not a
future artefact, not a test fixture and not dead code. Any document written in the present
tense saying the ADIM 16 stepper "was never written" / "hiç yazılmadı" is **false as of
2026-08-05 (PR #602)**.

The `E(t)` injection point also already ships: `_phase_entry(bar, *, equity)` at
`engine.py:2448`, documented verbatim as *"the SHARED `E(t)` for a portfolio participant"*.

> **Consequence for planning, stated plainly:** `CLAUDE.md` §4.1 blocker **(a)** — the
> phase-split bar — is **CLOSED and has been since #602**. Only blocker **(b)** remains.

### 3.2 The five symbols: EXISTS and UNWIRED are two facts, and both must be written

The recurring documentation failure is writing one half. A symbol that exists is not wired; a
symbol that is unwired has not therefore been left unwritten. Current `main`:

| Symbol | Definition (current) | Exists? | Production callers | Test callers | Correct one-line description |
|---|---|:--:|---|---|---|
| `run_portfolio` | `domain/backtest/portfolio_engine.py:531` | **YES** | **ZERO** | `tests/unit/oracles/portfolio_harness.py` (via `simulate`) | **Implemented and shipped as a symbol; unreachable from production.** |
| `ItemParticipant` | `portfolio_engine.py:251` (`Protocol`) | **YES — as a Protocol only** | **no implementors in `backend/src`** | `_ScriptedParticipant` (`portfolio_harness.py`) | **The contract exists; no production adapter implements it.** |
| `project_portfolio_run` | `execution/portfolio_projection.py:513` | **YES** | **ZERO** — module has zero importers in `backend/src` | `test_backtest_portfolio_projection.py` | **Implemented and unwired.** |
| `build_portfolio_manifest` | `execution/provenance.py:473` | **YES** | **ZERO** — module has zero importers in `backend/src` | `test_backtest_portfolio_provenance.py` | **Implemented and unwired.** |
| `_ItemStepper` | `engine.py:756` | **YES** | **`run_engine` — production** | stepper + phase suites | **Implemented and ACTIVE.** |

**`ItemParticipant` needs its two halves kept apart too.** The Protocol at `:251` is real,
typed and used in `run_portfolio`'s signature. What does not exist is a **production adapter**
that implements it over the real engine. The only implementation in the repository is
test-owned (`_ScriptedParticipant`) and is a timestamp→script lookup that decides nothing.
Writing "`ItemParticipant` does not exist" is wrong; writing "`ItemParticipant` is
implemented" is also wrong.

### 3.3 The shipped path, and the single line where it diverges

The worker's outer loop is the **item list**, not the merged timestamp axis:

> **`backend/src/entropia/application/jobs/backtest_engine.py:299`** — `for prepared in prepared_items:`

Each pass calls `_replay_strategy` (`:323`) → `run_engine` (`:859`), which consumes that item's
**entire** bar axis before the loop advances; `combine_item_runs` (`:364`) then folds the
finished runs in pin order. Everything downstream — the item-local ledger, the per-item `E`,
the non-time-ordered composite curve — follows from this one loop variable.

### 3.4 The remaining blocker is a SHAPE mismatch, not a missing file

Three phases book; the loop needs them to **describe** so it can arbitrate first:

| `ItemParticipant` requires | `_ItemStepper` offers | Gap |
|---|---|---|
| `carry(view) -> CarryCharges \| None` | `carry(bar) -> None` | returns nothing; charges immediately |
| `mandatory_exit(view, *, held) -> MandatoryExit \| None` | `held(bar) -> bool` | returns a flag; books the exit itself |
| `entry(view, snapshot, *, held) -> ItemIntent \| None` | `entry(bar, *, equity) -> None` | returns nothing; books without arbitration |

Closing it touches `run_engine`'s bar body — the statements the **46 golden digests** cover.
That is the **ADR §16 human gate**, and it is in force.

---

## §4 — Implementation truth: financial semantics

**All three defects are live on `ac5cf50`.** Re-verified this session at the exact line:

| # | Site on current `main` | Verbatim |
|---|---|---|
| **#550** | `domain/backtest/execution/sizing.py:216` | `return Decimal(sizing.base_position_size)` — a unit count, while every UI surface renders `%` |
| **#551** | `domain/backtest/engine.py:1462` | `if alloc_on and size <= _ZERO:` — the guard fires only under allocation |
| **#552** | `domain/backtest/execution/booking.py:93` | `commission_lot = costs.commission * 2 if is_full else costs.commission * 2 * fraction` |

`ENGINE_VERSION` is unchanged on `main`, which independently confirms that none of the option-A
work has landed.

**PR #720 would fix all three, and is open.** Its existence changes nothing about `main`, and
this document does not treat an open PR as a fix. Two things in it are worth recording because
they are decisions, not code:

1. It **deliberately reverses** the documented invariant in `_open`'s docstring
   (*"Independent mode books even a bust-equity 0-size fill"*) — that is P-A2's **PO-4**, and
   the PR answers it rather than patching around it.
2. It cites **PD-2 (2026-08-13)** as making per-FILL commission canonical — P-A2's **PO-6**.
   §7.1 records that PD-2 has no repo-side record.

**Still open even if #720 merges:** P-A2 §3.2(c) — canon (Master Ref line 3110) defines
commission as **bps on notional**, while the field remains a flat per-fill amount with no
currency and no resolved default published in the manifest. PD-2 settled the *split*, not the
*basis*. PR #720 states this itself.

---

## §5 — Documentation corrections

### 5.1 Already closed upstream — recorded so they are not re-derived

| ID | Claim | Closed by |
|---|---|---|
| **DR-1** | `a11y_screen_reader_audit_results.md` §6 carried three duplicated K rows with contradictory contents | `056aafe` (**#698**); the removal was recorded by **#711** |
| **DR-5** | `portfolio_engine.py:48` said the ADIM 16 stepper *"was never written"* | **#711** — the honest-boundary item now says **"What is missing is the ADAPTER, not the stepper"** |

`#711` is why every `portfolio_engine.py` coordinate in the W0 audits is **+13**.

### 5.2 Repaired in this PR — stale numbers presented as current truth

`docs/generated/repository_facts.md` is the **single authority** for repository counts, is
CI-gated (`--check`), and says of itself: *"No test pass count either: every test number below
is a collected node count from a static walk. Only a full CI run reports passes."*

| ID | Location | Stale claim | Why it is wrong | Repair |
|---|---|---|---|---|
| **DR-2** | `CLAUDE.md:102` (§Conventions, **present tense**) | *"ölçülen toplam %92.06, 2712 passed; frontend %84.67 line"* | The same file says 3987 passed / %93.53 at §Current position. `2712/92.06` is the ADIM-era baseline, correct **only** in `coverage_baseline.md` (which is `doc-status: historical`) | point at the generated artefact and at CI; drop the frozen numbers |
| **DR-3** | `README.md:730` | *"enforces `--cov-fail-under=90` (measured: 92.06%)"* | same frozen baseline | same |
| **DR-4** | `CLAUDE.md:102 / :323 / :549` | three different frontend figures (`%84.67` · `722/71` · `721/70`) | `repository_facts.md` records **716 call sites in 72 files**; both present-tense file counts are below the generated count | name the authority once |

**Why CI never caught these.** `generate_repository_facts.py`'s stale-assertion scan checks the
alembic head, `ENGINE_VERSION`, `SHARED_ALLOCATION_STATUS` and five invariant rules. **Test
counts and coverage percentages are not among them.** The gate is not failing — it was never
pointed at these numbers. Closing that is a separate, real piece of work (§10).

### 5.3 Still open — recorded, not repaired here

| ID | Claim | Why not repaired here |
|---|---|---|
| **DR-6** | `query_budgets.json` covers 1 of Ready Check's 4 resolver legs | P-E2 is in flight over the same file; repairing it here would conflict |
| **DR-7** *(new)* | **GH #582's body is stale in three places** — it says `grep "def run_portfolio"` returns no match, that the stepper was "never written", and that A17 carries "4 `xfail(strict=True)`". All three are false: `run_portfolio` exists (`:531`), the stepper ships (§3.1), and the deliberate strict-xfail count is **1** | an issue body is GitHub bookkeeping — **HUMAN-ACTION-REQUIRED** (§6.3). The issue's OPEN state is **correct**; only its body has expired |
| **DR-8** *(new)* | **PD-1…PD-7 have no repo-side record** (§7.1) | writing a decision record on an agent's initiative would forge an adjudication — **HUMAN-ACTION-REQUIRED** |

### 5.4 The one non-`docs/` edit

`backend/tests/unit/oracles/test_oracle_portfolio_containment_gate.py` — the docstring of
`test_the_phase_loop_exists_but_no_production_path_reaches_it` still said the
`ItemParticipant`-backed replay *"is ADR §12's ADIM 16 stepper and was never written"*. P-A1
flagged this and P-A3's DR-5 fixed only the `portfolio_engine.py` twin; this is the surviving
instance, and it is the one a reader of the containment gate hits first.

**Corrected to name the adapter as the missing piece.** No assertion, no expectation and no
executable statement changed — the test's behaviour is identical. It does not collide with PR
#720, whose only edit to this file is at `:229-233`.

### 5.5 New — the portfolio subsystem had ZERO codemap coverage

`docs/CODEMAPS/` contained **no mention** of `portfolio_engine`, `run_portfolio`,
`ItemParticipant`, `project_portfolio_run` or `build_portfolio_manifest`. Measured:
`grep -rl` over all six maps returned nothing.

**Why the gap exists and why no gate caught it:** `generate_repository_facts.py::check_codemap_coverage`
requires a codemap row for every **application** module and every dramatiq actor. The unified-clock
island lives under `domain/backtest/`, which the gate does not cover. The gap is structural,
not an oversight by any one slice.

A **§Unified-clock portfolio island** section is added to `docs/CODEMAPS/BACKEND_LAYERS.md`
(§12 of this document is its rationale). It records, for each symbol, definition site,
production-caller count and the one-line description from §3.2 — so the next reader who greps a
codemap for `run_portfolio` finds it *with its containment*, rather than finding nothing and
concluding the subsystem does not exist.

---

## §6 — Issue-state truth

### 6.1 Measured state — **not changed by this session**

| # | Subject | State | `state_reason` | Labels / milestone | Linked PR |
|---:|---|---|---|---|---|
| **514** | A-08 human SR acceptance audit | **OPEN** | `reopened` | `human-only` | none |
| **544** | NET cross-item policy undefined | **OPEN** | `reopened` | `blocks-adim-19`, `product-decision` · *ADIM 16-20* | none |
| **550** | sizing executes as units, UI says `%` | **OPEN** | `reopened` | — | **#720 (OPEN)** |
| **551** | phantom 0-size trade | **OPEN** | `reopened` | — | **#720 (OPEN)** |
| **552** | partial close pays 1.4 round trips | **OPEN** | `reopened` | — | **#720 (OPEN)** |
| **558** | neither bundle pins available-time policy | **OPEN** | `reopened` | `product-decision` | none |
| **559** | DST fold/gap have no canonical rule | **OPEN** | `reopened` | `blocks-mixed-zone-axis`, `product-decision` · *ADIM 16-20* | none |
| **582** | ADIM 20 blocked | **OPEN** | `reopened` | — | none |
| **617** | ready-check market-data leg N+1 | **CLOSED** | `completed` | — | #619 *(see §6.2)* |
| **618** | pinned ESP resolver N+1 | **CLOSED** | `completed` | — | **none** |

### 6.2 Issue-state drift: **CLOSED. The ledger and the code now agree.**

> **This is the correction the prompt asks for, and it must be stated precisely.**
> Earlier reports carried a *"three closed issues hiding a live defect"* narrative about
> #550/#551/#552. **That narrative is HISTORICAL.** A human reopened all three on
> 2026-08-13 and closed #617/#618 the same day at 11:07Z. **The drift is finished.**
>
> **The defects are still live. What changed is the record, not the code.** Anyone reading
> an older document that describes the issues as "closed while the defect ships" is reading
> an expired statement about **bookkeeping**, not a retracted finding about **behaviour**.

Two traps, both resolved from git rather than from GitHub's linkage:

* **#617's closing PR (#619) is the MEASUREMENT PR, not the repair.** #619
  (*"perf(test): establish load and query regression budgets"*) wrote the budget row that
  *found* the N+1. The repair is `6da8a95` = **PR #681**, which fixed **both** #617 and #618 —
  which is also why #618 is genuinely fixed while carrying **no linked PR at all**.
  **Linkage is not provenance.**
* **`CLAUDE.md`'s ADIM 46 record is stale.** It says *"izleme kaydı (issue durumu) insan
  kararı, #617/#618 açık kaldı"*. Both were closed `completed` on 2026-08-13. Repaired.

**Residual N+1: still live on `main`.** P-A3 §B measured slope 1.0 on the signal leg
(`readiness_check.py:554`) and the research leg (`:749`). Both are still there on `ac5cf50`;
`research_data.py` still has only the singular `get_dataset_root` (`:388`) with no batch
counterpart. **P-E2 has NOT landed** — it is one unmerged commit. No issue was ever filed for
either leg.

### 6.3 HUMAN-ACTION-REQUIRED

This PR closes no issue, opens no issue and changes no label. The following need a human:

| Action | Target | Why an agent must not do it |
|---|---|---|
| Refresh the stale body (DR-7) | **#582** | issue bodies are the author's record; the OPEN state is already correct |
| Correct claim (b) in the body | **#551** | P-A2 refuted it with a positive control and PR #720 re-confirmed the refutation; the issue still asserts it as *"the load-bearing one"* |
| Record PD-1…PD-7 in `docs/decisions/` (DR-8) | repo | writing an adjudication an agent did not receive would forge it |
| File the two residual N+1 legs | new issue | §6.2 |
| Everything about **#514** | **#514** | `human-only`; untouched by this session |

---

## §7 — Product decisions waiting

### 7.1 The decisions exist only in GitHub prose

PR #720 cites **PD-2**; #550's reopen comment cites **PD-6**. Neither appears anywhere in
`docs/`, `CLAUDE.md` or `docs/decisions/`. `docs/decisions/` holds exactly one file.

**This matters beyond tidiness.** #550's own decision comment names the convention:
*"record the adjudication in `CLAUDE.md` the way O-02 / O-12 / O-30 were"*. A decision that
lives only in a comment thread is invisible to `grep`, invisible to a fresh session, and
invisible to CI — which is precisely how the adjudications that *are* recorded (O-02, O-12,
O-30, O-31, D-10, D-11) earn their authority.

### 7.2 Open, with what each blocks

| # | Decision | Source | Status on `ac5cf50` | Blocks |
|---|---|---|---|---|
| **PO-1** | #550 — percent vs unit; do min/max become percent bounds? | P-A2 §7 | **DECIDED (option A)** 2026-08-04, re-affirmed 2026-08-13; **unimplemented on `main`**, implemented in #720 | sizing |
| **PO-2** | Does `min_position_size` survive? It has no canonical or mockup counterpart and *increases* size | P-A2 §1.4(i) | **OPEN** | sizing |
| **PO-3** | On exceeding Max Single Position: clamp or block? Master Ref §10.2 says *"clamp değil blocker"*; code clamps silently. Plus: add strategy-level `max_total_exposure_percent`? | P-A2 §1.3 | **OPEN** — survives PO-1 either way | sizing |
| **PO-4** | Does the bust-equity 0-size fill survive the guard? | P-A2 §2.5 | **ANSWERED by #720** (deliberately reversed, disclosed) — needs ratification when #720 merges | #551 |
| **PO-5** | #550 transition gate: BLOCK or WARN? | P-A2 §5.3 | **ANSWERED by #720** — `STRATEGY_SIZING_SEMANTICS_UNCONFIRMED` **blocks** | #550 |
| **PO-6** | Commission model A / B / C | P-A2 §3.3 | **SPLIT decided (PD-2 → per-FILL). BASIS still OPEN** — canon says bps-on-notional; unit/currency and resolved default still unpublished in the manifest | #552 |
| **PO-7** | Is the unwired `execution_key` reuse path an accepted boundary or an open defect? | P-A2 §7 | **OPEN** — 11 `ENGINE_VERSION` rationales claim a property that has no lookup to protect | process |
| **PO-8** | #558 bundle hash shape — per-member fields vs §9.2's top-level arrays (two of whose five arrays name concepts **that do not exist in the product**) | P-A3 §A.5 | **OPEN** | strict xfail |
| **PO-9** | #558 replay compatibility — `run_idempotent.response_ref` returns the old shape (the O-30 precedent) | P-A3 §F | **OPEN** | same |
| **PO-10** | Should `compile_agent_data_bundle` inherit the approval freeze? | P-A3 §A.3 | **OPEN** — the hash collision is reachable **only** on this path | — |
| **PO-11** | #559 fold/gap rule; and separately **may E4/E5 proceed with it open?** | P-A3 §E.4 | **OPEN** | see §9b |
| **PO-12** | #544 — define NET or remove it | GH #544 | **OPEN**, `blocks-adim-19` | arbitration |
| **PO-13** | Wire `alert-notification-proof.sh` as a CI gate? | P-A3 §C | **OPEN** | observability residue 3 |
| **PO-14** | K-5 / K-7 — re-cut 22 pages' heading outlines (**measured: 204 headings across ~40 files**)? Mount a persistent status region? | P-A3 §F | **OPEN** (K-3 retired by D-11) | A-08 preparation |

---

## §8 — Deliberately contained capabilities

**`SHARED_ALLOCATION_STATUS = "future_dev"` is not a gap, a regression or unfinished work. It
is DELIBERATE FAIL-CLOSED CONTAINMENT**, decided and recorded
(`docs/decisions/2026-08-03_shared_portfolio_containment.md`), with two independent
enforcement points:

| # | Site | Surface | Effect |
|---|---|---|---|
| **1 — the hard gate** | `application/commands/backtest_run.py:542` | run admission | refuses with `ALLOCATION_SHARED_MODE_NOT_IN_BUILD`. Sits **after** the snapshot load and **before** `build_run_manifest` (`:573`) — **no run, no manifest, no job row** is created. Every admission path funnels through it. |
| **2 — the diagnosable gate** | `domain/allocation/rules.py:154` | `validate_allocation` | emits a `SHARED_MODE_NOT_IN_BUILD` BLOCKER on the Portfolio page, plan-revision freeze and Ready Check |

Guard 1 reads the immutable snapshot dict directly, so the refusal survives a bypassed or
regressed readiness evaluation. **Independent mode is untouched** and replays byte-identically.

### 8.1 The containment gate's green state must be read in the right direction

`tests/unit/oracles/test_oracle_portfolio_containment_gate.py` is **negative-assertion**
(`assert callers == []`). A green run does **not** mean the shared engine works — **it proves
production cannot reach `run_portfolio`.** Two specifics that invert if misread:

* `test_the_same_trades_read_5000_sequentially_and_3000_on_one_clock` passes **because the
  shipped fold still reports the wrong number** (`5000.00`). The day it reports `3000.00`,
  this test fails — **and that failure is the acceptance proof.**
* `test_the_containment_flag_and_engine_version_are_both_untouched` passes because the flag
  and version have not moved.

**E5 must NARROW this gate to an authorised-caller allowlist, never delete it**, and must not
touch the two assertions that pin `SHARED_ALLOCATION_STATUS` and the `5000.00` defect —
those are the *lift* gate (ADIM 20), not the *wiring* gate.

### 8.2 Also deliberate, also not gaps

| Item | Why it is not a defect |
|---|---|
| `MARK_STALENESS_POLICY = "undefined_pending_od2"`, `CONTENTION_SELECTION_STATUS = "recommended_pending_approval"` | ADR §13.1 assigns both flips to ADIM 20 — **documented, not drifted** |
| Retention auto-purge, LLM generation, Graphic View renderer | out of V1 scope by decision (`CLAUDE.md` §KAPSAM DIŞI) |
| The 1 strict xfail | a **product decision** (#558), not a bug: `test_research_point_in_time_parity.py::test_both_bundles_pin_the_available_time_policy`, declared at `:580` |

---

## §9 — Release blockers

> ## Blocker count: **1**. Verdict: **BLOCKED**. Unchanged by this session.

| # | Blocker | Measured state |
|---|---|---|
| **1** | **A-08 — human screen-reader acceptance audit** | **0 / 4** exit criteria · **2 / 368** Section A cells (**2 / 184** SR-2, **0 / 184** SR-1) · **0 / 46** routes complete · **0 / 20** flows · SR-1 **never started** · 0 findings · auditor role **unassigned** (the one session was run by the product owner, screen-reader role `neither`). GH **#514 OPEN**, `human-only`. |

**Automated preparation and human acceptance are different things, and no document may
conflate them.** ADIM 28 built the scaffold; ADIM 44 made the stack runnable (9/9 + runbook);
ADIM 56 ran the first session. **None of that is the audit.** The axe-core ratchet, the
keyboard-flow spec and the 23-route structural prechecks are **all green and none of them is
A-08 evidence** — the precheck report stamps `screen_reader_verified: false` itself.

Criteria 1 and 2 **cannot** be closed by SR-2 work at all: both name both combinations, so a
flawless complete SR-2 pass would still leave criterion 1 at `1/2` and criterion 2 at `23/46`.

**No document may show A-08 as `Complete`, `PASS` or `Done`.** The `A08_COMPLETE` invariant in
`generate_repository_facts.py` enforces this in CI.

Separately and independently: **WCAG 2.2 AA 1.4.3 is not met** under signed permanent
deviation **D-10** (45 accent-blue nodes). The product cannot be called conformant for that SC.

---

## §10 — Non-blocking debt

Recorded as debt, deliberately **not** promoted to blockers:

| Item | Why not a blocker |
|---|---|
| **#550 / #551 / #552** | real financial defects, live on `main`; fix is in flight (#720). Not release-blocking by the standing verdict — the blocker list has been 1 throughout |
| Two Ready Check N+1 legs (slope 1.0) | latency on a page the user waits on; **fails closed identically** to the batched path. No correctness impact |
| #558 hash collision | reachable **only** on the Agent bundle path over a non-approved revision; the evidence bundle is protected by the lifecycle freeze |
| Observability residues 1–5 | the *config* half of the notification path is gated on every PR; the *delivery* half (`alert-notification-proof.sh`) is **not a CI gate** — an operator must remember to run it. Residues 1 and 4 cannot be closed inside this repository at all |
| K-5 (22/23), K-6a, K-7 (21/23) | K-6a and K-5 can be closed **only** by A-08. Counts drift ±1 between runs — the first run is cold and under-reports |
| **DR-6** | budget coverage gap; P-E2 owns the file |
| **The stale-number gate gap** *(new)* | `generate_repository_facts.py` does not check test counts or coverage percentages, which is exactly how DR-2/DR-3/DR-4 survived CI. Pointing the gate at them would prevent the next recurrence |
| `execution_key` written but never read | PO-7; 11 bump rationales claim a property with no lookup behind it |

---

## §11 — Exact next design questions

Ordered. Each is stated so it can be answered without re-deriving §3.

1. **Does the describe/book split land as a pure refactor first?** The adapter needs
   `carry` / `mandatory_exit` / `entry` to **return descriptions** before arbitration. That
   touches the statements the **46 golden digests** cover. Land it in its own PR with **zero
   digests moved** — *if a digest moves, stop: that is a re-price, not a restructure.*
2. **Where does the adapter live?** Placing it at `domain/backtest/execution/participant.py`
   avoids containment assertion 6 **by construction** (the check exempts
   `path.parent.name == "execution"`). It does **not** avoid assertions 1–5.
3. **How is the shared path selected?** `combine_item_runs` is **also the independent-mode
   path**, and doc 13 §1.1 makes independent a first-class complete mode. A wiring that routes
   *all* multi-item runs through `run_portfolio` **silently re-prices every independent-mode
   composite Result** — no flag, no version bump, no user-visible change. The branch must be
   `alloc_probe is not None and shared_allocation_is_executable()`, decided at **one** place.
4. **Where do the cancellation checkpoints go?** `run_portfolio` owns its own tick loop, so
   checkpoint #3 (`jobs/backtest_engine.py:303`) has nowhere to live unless the loop yields.
   Checkpoint #4 enforces doc 15 §16 (*a CANCELLED run produces no `BacktestResult`*). **A21
   is a blocking sub-task of E5, not of ADIM 20.**
5. **Which arbitration wins?** `PriorItemInterval` forward-only precedence and
   `execution/arbitration.py` are **two live answers to one question**; ADR §12 row 19 says
   arbitration *retires* the former. Retire it **on the shared path only**, in the same PR —
   and **#544 (NET) is still OPEN**, so one of the two has no canonical definition to be
   correct against.
6. **Does #559 gate this work?** — see §9b below.
7. **Does the `ENGINE_VERSION` bump for #550/#551/#552 land before or after the adapter?**
   The bump touches the same source as PR B's 46-digest byte-identity gate. **Maintainer call**
   (ADR §15 R-4). If #720 merges first, the digest baseline the adapter must hold unmoved is
   the *new* one.

### §9b — Is #559 (DST) a precondition of E4/E5? **Ruling: NO, mechanically. YES, by written decision. Unenforced either way.**

The two source audits appear to disagree, and the disagreement is real enough to name:

| Audit | What it says | What it is based on |
|---|---|---|
| **P-A1** §11 | lists #559 under **NOT MET**, as a containment-lift precondition | **ADR prose** — §14's condition list |
| **P-A3** §E.4 | *"not a mechanical prerequisite … removing the issue would not change a line of the wiring"* | **code measurement** |

**Both are correct about different things, and the resolution is P-A3's** because it measured:

* the merged axis **never reads a source timezone** — `execution/clock.py`'s `tick_key` calls
  `parse_utc(timestamp, source_zone=None)` because replayed bars are UTC-normalized at ingest.
  The axis consumes **instants**, never wall clocks.
* the DST rule is applied **upstream**, at ingest and at the funding reader, both on the
  single-item path today.
* **no admission gate refuses a mixed-zone composition.** `grep` for `source_timezone` /
  `timezone_mode` / `timezone_iana` over `readiness_check.py`, `backtest_run.py` and
  `domain/readiness/validators.py` returns **zero** hits. Nothing compares zones across items
  anywhere.

**So the plan dependency is this:** #559 does not block writing the adapter or the call site.
It **is** a stated ADR precondition (`0002-…md:745`) for the merged axis *spanning mixed-zone
sources* — a scope the wiring makes reachable **for the first time**. The escalation is real
and worth stating: today a mis-collapsed folded hour misprices **one item's own** run; on a
merged axis the same cell shifts the **shared valuation point every item sees at that tick**.

**Nothing in the code enforces this precondition — it lives only in ADR prose.** Whether E4/E5
may proceed with #559 open is therefore **PO-11**, a product call, not a code fact.

---

## §12 — Where the three audits disagree

Recorded rather than smoothed over, with the evidence class each rests on:

| # | Disagreement | P-A1 | P-A2 | P-A3 | Resolution |
|---|---|---|---|---|---|
| 1 | **#559 as an E4/E5 gate** | ADR prose → treats as NOT MET | — | code measurement → not mechanical | **P-A3 on mechanics, P-A1 on the written decision.** Both stand; see §9b |
| 2 | **The stale-stepper claim** | flags the **containment-gate docstring** | — | DR-5 flags **`portfolio_engine.py:48`** | **Complementary, not contradictory** — two instances of one claim. P-A3's was fixed by #711; P-A1's survived and is fixed here (§5.4) |
| 3 | **#551's cross-item leakage** | — | **REFUTED** with a positive control | — | **P-A2 stands**, independently re-confirmed by PR #720. The **issue body still asserts it** → §6.3 |
| 4 | **PO decision count** | — | *"pending: 6"* | lists 7 (different numbering) | **Neither is current.** The two lists overlap but are numbered independently; §7.2 merges them into one PO-1…PO-14 |
| 5 | **`_ItemStepper`'s status** | **IMPLEMENTED-ACTIVE**, closes blocker (a) | — | DR-5 — only the *reason* was stale, not the conclusion | **Agree.** The subsystem is contained; the *justification* for saying so was what had expired |

**No disagreement was found on:** the blocker count (1), the verdict (BLOCKED), the
containment being deliberate, or A-08's numbers.

---

## §13 — Master finding table

| Finding | Canonical | Current Code (`ac5cf50`) | Previous Doc Claim | Corrected Claim | GitHub State | Action |
|---|---|---|---|---|---|---|
| `_ItemStepper` | ADR §12 ADIM 16 (amended) | `engine.py:756`, reached via `run_engine:3279` ← worker `:859` | *"never written"* (`:690`, containment docstring, #582) | **PRODUCTION-ACTIVE since #602. Blocker (a) is CLOSED.** | #582 open, body stale | docstring fixed §5.4; **#582 body = human** |
| `run_portfolio` | doc 13 §8.3, ADR §4 | `portfolio_engine.py:531` — **0 production callers** | *"grep returns no match"* (#582) | **EXISTS and is UNWIRED — both halves** | #582 open | codemap §5.5 |
| `ItemParticipant` | ADR §6 | `portfolio_engine.py:251` — **Protocol only**, no production implementor | *"CONFIRMED-MISSING"* | **Protocol EXISTS; the production ADAPTER does not** | #582 open | §3.2, §3.4 |
| `project_portfolio_run` | ADR §14 A4/A18 | `execution/portfolio_projection.py:513` — module has **0 importers** | — | **EXISTS and is UNWIRED** | #582 open | codemap §5.5 |
| `build_portfolio_manifest` | doc 13 §13, ADR §10.1 | `execution/provenance.py:473` — module has **0 importers** | — | **EXISTS and is UNWIRED** | #582 open | codemap §5.5 |
| `SHARED_ALLOCATION_STATUS` | ADR §10.4, doc 13 §14 | `capability.py:105` = `future_dev`; 2 enforcement points | sometimes read as a gap | **DELIBERATE FAIL-CLOSED CONTAINMENT** | — | §8 |
| #550 sizing units | Master Ref §10.1 | `sizing.py:216` — **live** | — | live; option A decided, **unimplemented on `main`** | **OPEN** `reopened`, PR #720 open | §4 |
| #551 phantom trade | Master Ref §10.1 | `engine.py:1462` — **live** | body's claim (b) refuted | live for metrics + fee; **(b) does NOT reproduce** | **OPEN** `reopened`, PR #720 open | body fix = human |
| #552 commission | Master Ref 3110 / 7513 | `booking.py:93` — **live** | — | live; **split decided (PD-2), basis still open** | **OPEN** `reopened`, PR #720 open | §7 |
| #617 / #618 | — | repaired by `6da8a95` (**#681**) | *"#617/#618 açık kaldı"* (ADIM 46) | **CLOSED `completed` 2026-08-13 11:07Z.** #619 is the **measurement** PR, not the repair | **CLOSED** | `CLAUDE.md` repaired §6.2 |
| Residual N+1 legs | — | `readiness_check.py:554`, `:749` — slope **1.0**, live | — | live; **P-E2 NOT merged** | **no issue exists** | file one = human |
| #558 | doc 12 §9.1/§9.2 | `bundle_hash` invariant under policy change (measured) | — | live; **product decision** | **OPEN** `reopened`, `product-decision` | §7 |
| #559 | doc 12 §5.2 | fold→first occurrence, gap→accepted; **no zone gate anywhere** | read as an E4/E5 gate | **not mechanical; ADR-written; unenforced** | **OPEN**, `blocks-mixed-zone-axis` | §9b |
| A-08 | checklist §5 | 2/368 cells, 0/4 criteria | prep sometimes read as the audit | **HUMAN-BLOCKED. Prep ≠ audit.** | **#514 OPEN** `human-only` | untouched |
| DR-1 / DR-5 | — | repaired | *"not repaired here"* | **CLOSED** (#698 / #711) | — | recorded |
| DR-2 / DR-3 / DR-4 | `repository_facts.md` | 3545 collected · 716 call sites / 72 files | `2712` · `92.06%` · `84.67%` presented as current | **stale baseline; the generated artefact is the authority; only CI reports passes** | — | repaired §5.2 |
| PD-1…PD-7 | — | — | cited by #720 / #550 | **no repo-side record exists** | — | **human** |
| Codemap portfolio coverage | — | none | — | **structural gap — the coverage gate does not reach `domain/`** | — | filled §5.5 |

---

## §14 — Stopping condition

This document stops at the ADR §16 human gate and at the `product-decision` label. It changes
no production behaviour, no test expectation, no `ENGINE_VERSION`, no feature flag and no
issue state. Everything it corrects is a **claim**, not a **behaviour** — with the single
exception of a docstring sentence that had become false (§5.4).

**Next:** P-C1 + P-C2.
