<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# P-E5 — worker shared-path wiring (`C4`): precondition measurement

**Verdict: NOT BUILDABLE on this base. Zero production lines written, deliberately.**

| Field | Value |
|---|---|
| Base measured | `dc2902fc0444ee7ecb26c51c2501a1c0fb653508` (`origin/main`) |
| Expected base in the prompt | `31ed27dfc1f3bf7448b0e03c7c732d22d8b758c4` — **an ancestor, 68 commits behind**. Every number below was re-measured on `dc2902f`; nothing is inherited, including from the P-E4 record. |
| Product code changed | **none** |
| Containment status | `future_dev` — **unchanged** (`domain/allocation/capability.py:105`) |
| Containment gate | **green, untouched** (`tests/unit/oracles` 115 passed, exit 0) |
| Single-item golden | **unchanged** — `engine_golden_digests.json` not touched |

The slice requested is `C4` in `docs/implementation/final_closure_ordered_plan_2026-08-13.md`
§6 — *"E5 worker branch + tripwire"*. That table states its prerequisite in one word:
**`C3` merged**. `C3` is the engine-backed `ItemParticipant` adapter. It has not landed.

---

## 1. What moved since the P-E4 record — one link, and it is a real one

`docs/audit/closure_e4_adapter_precondition_measurement_2026-08-17.md` measured four blockers at
`6902710`. **`main` has gained three commits since, and one of them discharges Blocker 1.**

`#735` (`dc2902f`, *"split P1, P3 and P4 into describe and booking halves"*) is `C1`. The
describe/book split is shipped and sits on `_ItemStepper`'s **public** surface
(`domain/backtest/engine.py:818`):

| Phase | DESCRIBED (books nothing) | BOOKED |
|---|---|---|
| P1 carry | `compute_carry` (`:841`) → `_CarryPlan \| None` | `book_carry` (`:844`) |
| P3 mandatory exit | `evaluate_held` (`:851`) → `_HeldDecision \| None` | `apply_held` (`:858`) |
| P4 entry | `evaluate_entry` (`:863`) → `_EntryDecision \| None` | `apply_entry` (`:870`) |

This matters for **this** prompt specifically. The prompt's ADR §16 paragraph names two obstacles
and instructs the agent to read how the design document solved them:

> *"(a) faz-bölünmüş bar ve (b) book-etmeyen değerlendirme girişi engelleri nasıl çözülmüş?"*

**Both are now closed, and neither is closed by this slice.** (a) `_ItemStepper` has been
phase-split since `#602`; (b) is exactly what `#735` shipped. The E4 record's Blocker 1 —
*"all three hooks map onto callables that book, and none returns a describable value"* — is
**no longer true** and should not be re-cited from that document.

That is the whole of the good news. The chain advanced by one link; three remain.

---

## 2. Blocker A — `C2` has not landed, so the loop has nothing to drive and no seam to settle on

`C3` (the adapter) requires `C2`. Measured against the tree, not the log:

| Required by the design (`closure_design_portfolio_performance_2026-08-13.md` §C.5) | Present on `dc2902f`? | Measurement |
|---|---|---|
| `ItemParticipant.settle` | **NO** | `grep "def settle" portfolio_engine.py` → 0 hits |
| `ItemParticipant.finalize` | **NO** | `grep "def finalize" portfolio_engine.py` → 0 hits |
| P10 finalize phase | **NO** | `PHASE_ORDER` (`:129`) = `("P1","P3","PV","P4","P5","P6b","P7","P9")` — 8 phases |
| `iter_portfolio` (tick-drivable loop) | **NO** | 0 hits in `backend/src` |

The `ItemParticipant` Protocol on this base (`portfolio_engine.py:270`) still declares exactly
three properties and three hooks — `carry` (`:296`), `mandatory_exit` (`:299`), `entry` (`:303`).
There is no `settle`, so there is no callback through which the loop can tell a participant
*"your intent was admitted"*, and no `finalize`, so end-of-data has no seam.

This is not a detail the worker branch can route around. The design document's own E5 flowchart
(§C.5, `:538-540`) spells the shared branch as three calls:

```
participants = [_EngineParticipant(p) for p in prepared_items]   # C3 — absent
for index, tick in enumerate(iter_portfolio(...)):               # C2 — absent
    ...
output = project_portfolio_run(run, items, execution_key, item_count)   # present
```

**Two of the three do not exist.** One-third of a branch is not a branch.

---

## 3. Blocker B — there is no `ItemParticipant` implementation in `backend/src` at all

This is the prompt's own stop condition, and it is unavoidable rather than a matter of care.

```
grep -rn "ItemParticipant" backend/src --include=*.py
  → domain/backtest/portfolio_engine.py only (the Protocol's own definition)

grep -rln "ItemParticipant" backend/ --include=*.py
  → backend/src/entropia/domain/backtest/portfolio_engine.py     (definition)
  → backend/tests/unit/oracles/portfolio_harness.py              (test-owned)
  → backend/tests/unit/oracles/test_oracle_portfolio_containment_gate.py  (test-owned)

ls backend/src/entropia/domain/backtest/participant.py
  → No such file or directory
```

The prompt requires the shared path to use *"gerçek `ItemParticipant`'lar"*. **Zero exist.** The
only implementations in the repository are `_ScriptedParticipant` and its harness, both owned by
the oracle package. Wiring the worker on this base would therefore mean pointing the production
shared path at a test fixture — which the prompt names verbatim as a condition under which
"Complete" must not be written:

> *"shared production path hâlâ fake/test participant kullanıyorsa"*

There is no version of this slice that ships on this base and does not do that.

---

## 4. Blocker C — `G9` and `G13` are unsigned human gates, and they gate `C2`

Unchanged from the E4 record; re-measured, not inherited
(`final_closure_ordered_plan_2026-08-13.md` §5, `:195` and `:199`):

- **`G9`** — ADR §16 Gate 1: amend ADR §6/§8 to add `settle`, `finalize`, P10, `iter_portfolio`.
  Status: **NOT REQUESTED.** The ADR is `Accepted`; amending an accepted contract needs the
  signature that accepted it.
- **`G13`** — the P10 end-of-data equity point: append at the last `t_ms`, or fold into it.
  Status: **UNDECIDED.** Appending puts two points on one instant and breaks ADR §14 A5's
  by-construction sortedness claim — a contract question, not an implementation detail.

The prompt's own hard precondition is explicit about this: *"ADR amendment'ı onaylandı mı?
ONAYSIZ BAŞLAMA."* It is not approved. ADR §16 (`:860`) is equally explicit that the gate
*"is not a formality"*, and records that it was already dishonoured once in ADIM 15/17/19 —
noting that the cost was small **only** because none of those slices touched `run_engine`.
This slice touches the worker call site, which is the case §15 R-4 names.

Neither gate is dischargeable by an agent.

---

## 5. Blocker D — the importer-allowlist conflict is still live, re-measured on the real gate

The containment gate has **two independent** assertions on the phase loop, and they answer
differently for an adapter — verified by reading
`tests/unit/oracles/test_oracle_portfolio_containment_gate.py` on this base:

1. **`run_portfolio` caller check** (`:180-185`): `assert callers == []`.
2. **`_PHASE_LOOP_MODULES` importer check** (`:168-177`): the allowlist is
   `([], ["domain/backtest/portfolio_engine.py"])`, and the filter skips only files whose
   `path.parent.name == "execution"`.

An adapter at `domain/backtest/participant.py` must import `execution.clock`,
`execution.intents` and `execution.portfolio_ledger` to name its own types — its parent is
`backtest`, not `execution`, so it lands in `importers` and the assertion **fails**. That is by
construction, not by carelessness: the plan chose the location precisely so the guard would
turn red rather than be dodged.

So the adapter still requires a **reviewed allowlist widening**, which the plan assigns to a
human (step 4 of E4 §7). This slice's own instruction — *make the gate pin the expected caller
by name* — is correct in principle and is anticipated by the gate's own docstrings (*"When the
call site lands, this test is the one that must be updated deliberately"*, `:206`). But it is
`C4`'s work, and `C4` is downstream of two absent slices and two unsigned gates.

---

## 6. What was NOT done, and why that is not a narrowing

No branch was added to `application/jobs/backtest_engine.py`. The three anchors the prompt names
are unchanged and were confirmed to still be at the cited lines: `:299` `for prepared in
prepared_items:`, `:323` `_replay_strategy`, `:364` `combine_item_runs`.

A "shared path" that constructed `_ScriptedParticipant` from production code, or that imported the
oracle harness, would satisfy the diff and none of the requirement — and it would move the
test-owned fixture into `backend/src`, which the design document forbids in terms (§C.5: *"That
fixture is test-owned and must never be importable from `backend/src`"*).

The containment gate was **not** modified. Its assertions are the record that the shared path is
unreachable; changing them while the path they describe does not exist would make the guard
blind rather than satisfied. No negative control was run against a gate change, because no gate
change was made.

No test was written, because no product behaviour changed. `_ScriptedParticipant` was not
touched.

---

## 7. The unblocked path, in order

| Step | Slice | Blocked by | Dischargeable by an agent? |
|---|---|---|---|
| ~~1~~ | ~~`C1` — describe/book split~~ | — | **DONE — `#735`, `dc2902f`** |
| 1 | `G9` + `G13` signatures | human | **no** |
| 2 | `C2` — `settle` / `finalize` / P10 / `iter_portfolio` | `G9` + `G13` | yes, after 1 |
| 3 | Importer-allowlist decision for `participant.py` | human review | **no** |
| 4 | `C3` — the adapter | `C2` + step 3 | yes, after 1–3 |
| 5 | `C4` — **this slice** | `C3` | yes, after 1–4 |

**The critical path now begins with a signature, not with code.** That is the single most
useful thing this measurement establishes: every engineering prerequisite an agent could have
discharged has been discharged. `C1` was the last one.

`C5` (R-1 allocation-plan pinning) remains disjoint from this chain, has **no** prerequisites
(§6 table), and is the plan's recommended second-lane filler. It was **not** started here — the
prompt says *"Yalnız bu slice"*, and silently substituting a different slice would be a scope
change, not a rescue.

---

## 8. Evidence

```text
base                                                              dc2902f (origin/main), tree clean
uv sync --all-extras                                              exit 0
uv run pytest tests/unit/oracles -q --no-cov                      exit 0   115 passed
uv run pytest tests/unit/oracles \
             tests/unit/test_backtest_engine_describe_book.py     exit 0   125 passed
uv run python ../scripts/generate_repository_facts.py --root .. --check
                                                                  exit 0   "documentation-truth gate OK"
git diff -- backend/                                              empty (no product change)
```

The suites were run **before** the decision to stop, as a baseline the next attempt can use to
prove it moved nothing — not to justify the stop after the fact.
