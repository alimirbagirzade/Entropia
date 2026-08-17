<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# P-E4 — engine-backed `ItemParticipant` adapter: precondition measurement

**Verdict: NOT BUILDABLE on this base. Zero production lines written, deliberately.**

| Field | Value |
|---|---|
| Base measured | `6902710490414ea28dfb8114cdc0caa25e6a3657` (`origin/main`) |
| Expected base in the prompt | `31ed27dfc1f3bf7448b0e03c7c732d22d8b758c4` — **an ancestor, 83 commits behind**. Every number below was re-measured on `6902710`; nothing is inherited. |
| Product code changed | **none** |
| Containment status | `future_dev` — **unchanged** |
| Containment gate | **green, untouched** (`tests/unit/oracles` 115 passed, exit 0) |
| Single-item golden | **unchanged** — `engine_golden_digests.json` not touched |

---

## 1. What the slice was asked to build, and why it cannot be

The request is `C3` in `docs/implementation/final_closure_ordered_plan_2026-08-13.md` §3
(PACKAGE C): *one new module, `domain/backtest/participant.py`, an engine-backed
`ItemParticipant`*. That plan states `C3`'s prerequisite in one line: **`C2` merged**, and
`C2`'s own prerequisites are **`C1` merged + G9 signed + G13 decided**.

**`C1` and `C2` have not landed.** The four commits `main` gained after the plan was written
(`c49f5e7`) are `#727` (agent allowlist), `#728` (the plan itself), `#729` (closure-F1) and
`#730` (closure-E3). None is a Package C slice.

That was verified against the tree rather than inferred from the log.

---

## 2. Blocker 1 — the describe/book split (`C1`) is absent, so a read-only proposal is
structurally impossible

The prompt's first non-negotiable invariant is *"intent proposal READ-ONLY: participant
state'ini MUTATE ETMEZ"*. On this base, **all three** `ItemParticipant` hooks map onto
`_ItemStepper` callables that book, and none of them returns a describable value.

| Protocol hook (`portfolio_engine.py`) | Must return | `_ItemStepper` field | Bound to | What it actually does |
|---|---|---|---|---|
| `carry` (`:296`) | `CarryCharges \| None` | `carry` | `_phase_carry` (`engine.py:1964`) | `nonlocal funding_idx`; writes the ledger. Returns `None`. |
| `mandatory_exit` (`:299`) | `MandatoryExit \| None` | `held` | `_phase_held` (`engine.py:2315`) | `nonlocal exit_touch, pending, position`. Returns `bool`. |
| `entry` (`:303`) | `ItemIntent \| None` | `entry` | `_phase_entry` (`engine.py:2499`) | `nonlocal pending, position, sizing_equity, working_limit, working_stop`. Returns `None`. |

Bindings: `engine.py:3326`, `:3328`, `:3329`.

There is no rollback path either. The replay state (`pending`, `position`, `working_limit`,
`working_stop`, `funding_idx`) lives in `_build_stepper`'s closure (`engine.py:795`–`:3335`) and
is not reachable through `_ItemStepper`'s public fields — `open_position()` exposes the position
and nothing else. A "call it, read what it booked, undo it" adapter is therefore not merely
inelegant, it is **not expressible**, and it would in any case be a second booking policy, which
the prompt forbids (*YENİ ENGINE YAZMA*).

**The repository's own containment gate already states this finding in prose**
(`tests/unit/oracles/test_oracle_portfolio_containment_gate.py:145-147`):

> *"The remaining gap is one of SHAPE — the stepper's phases BOOK, while `ItemParticipant` needs
> them to DESCRIBE so the loop can arbitrate first."*

Closing that gap is `C1`, whose production surface is *inside* `_build_stepper` — a different
slice, with its own acceptance (`engine_golden_digests.json` byte-unchanged) and its own
unmeasured risk (`_phase_tail`'s scaling separability was asserted from the call graph, **not**
from reading the 474-line body).

---

## 3. Blocker 2 — the Protocol is still write-only (`C2`), so two of the twelve headings have
no seam

The prompt requires *admitted action apply* and *finalization*. Neither has an attachment point.

| Required by the prompt | Present on this base? | Measurement |
|---|---|---|
| `ItemParticipant.settle` | **NO** | `grep "def settle" portfolio_engine.py` → 0 hits |
| `ItemParticipant.finalize` | **NO** | `grep "def finalize" portfolio_engine.py` → 0 hits |
| P10 finalize phase | **NO** | `PHASE_ORDER` (`:129`) = `("P1","P3","PV","P4","P5","P6b","P7","P9")` — 8 phases |
| `iter_portfolio` (tick-drivable loop) | **NO** | 0 hits; `run_portfolio` builds all ticks in one comprehension (`:624`) |

The consequence is not cosmetic. Without `settle`, an adapter has no callback through which the
loop can tell it *"your intent was admitted"* — so the only place left to book would be inside
`entry()` itself, i.e. **before arbitration has run**. That commits item capital the pool may
then refuse, with no `PortfolioSnapshot` behind it. It is the precise silent-degradation shape
the plan's `C6` stop condition names.

The prompt also requires *cancellation checkpoint* wiring, which the plan assigns to `C4`
(`application/jobs/backtest_engine.py`), and *projection* / *manifest*, which the plan assigns to
`C4` and `C7`. Those are outside an adapter-only slice by the plan's own no-touch lists.

---

## 4. Blocker 3 — G9 and G13 are unsigned human gates

`C2` amends an **`Accepted`** ADR. ADR `0002` §6 (item intent contract) and §8 (phase order)
contain no `settle`, no `finalize`, no P10, no `iter_portfolio` — measured by grep over the ADR:
the only `finalize` hits are `:442` (a state-machine diagram) and `:719` (a description of
today's `_ItemStepper`).

- **G9** — ADR §16 Gate 1, the §6/§8 amendment. Status: **not requested**.
- **G13** — the P10 end-of-data equity point: append at the last `t_ms`, or fold into it.
  Status: **undecided**. Appending puts two points on one instant and breaks ADR §14 A5's
  by-construction sortedness claim, so this is a contract question, not an implementation detail.

ADR §16 (`:860`) is explicit that the approval gate *"is not a formality"*. The prompt's own stop
list names *"çözülmemiş canonical/PO kararı"* first. Neither gate is dischargeable by an agent.

---

## 5. Blocker 4 — the prompt's "gate stays green" expectation and the design document are in
direct conflict, and the design document is right

The prompt says: *"Bu slice YALNIZ ADAPTER yazıyorsa … gate hâlâ yeşil kalmalı. Kırmızıya
dönüyorsa: kapsam kaymış demektir — DUR ve raporla."*

The gate has **two independent** assertions, and they answer differently:

1. **`run_portfolio` caller check** (`:180-186`) — an adapter does not call `run_portfolio`, so
   this **stays green**. This is the assertion the prompt is thinking of.
2. **`_PHASE_LOOP_MODULES` importer check** (`:168-177`) — this **necessarily turns red**.

The second result is not a scope slip; it is forced by the type signatures. `ItemParticipant`'s
members are typed in terms of six classes, and **`portfolio_engine.__all__` (`:627`) re-exports
none of them**:

| Type the Protocol requires | Defined in | In `_PHASE_LOOP_MODULES`? |
|---|---|---|
| `ItemBarStream` | `execution/clock.py:98` | yes |
| `ItemTickView` | `execution/clock.py:117` | yes |
| `ItemIdentity` | `execution/intents.py:238` | yes |
| `PortfolioSnapshot` | `execution/intents.py:271` | yes |
| `ItemIntent` | `execution/intents.py:459` | yes |
| `OpenPosition` | `execution/portfolio_ledger.py:325` | yes |

Any module outside `execution/` that implements the Protocol must therefore contain the literal
`execution.clock import` / `execution.intents import` / `execution.portfolio_ledger import`, which
is exactly what the check greps for.

The plan anticipated this and treats the redness as the *point* of putting the adapter at
`domain/backtest/participant.py` rather than inside `execution/`:

> *"placing it at `domain/backtest/execution/participant.py` would dodge the containment gate's
> importer check by construction, making the guard blind rather than satisfied. Outside, the
> guard turns red and the allowlist must be widened explicitly and reviewed."*

So the honest adapter requires a **reviewed allowlist widening** — which this prompt forbids
(*"Gate'i bu slice'ta ZAYIFLATMA"*). The two instructions cannot both be satisfied. This is
recorded as a question for the human, not resolved here: **widening the importer allowlist by one
named module is a reviewed change to a deliberate tripwire, and is not an agent's call.**

---

## 6. What was NOT done, and why that is not a narrowing

No partial adapter was written. The three trivial members (`identity`, `stream`,
`instrument_id`) are expressible today; the three that carry the semantics (`carry`,
`mandatory_exit`, `entry`) are not. A module shipping three properties and three hooks that
cannot honestly describe anything would trip the importer gate, satisfy none of the twelve
headings, and read in the tree as *"the adapter exists"*. That is the mark-without-covering shape
ADIM 48 recorded and the plan's `C8` stop condition names again.

No test was written, because there is no product behaviour to pin. `_ScriptedParticipant` was
**not** touched — it remains the oracle harness's own instrument.

---

## 7. The unblocked path, in order

| Step | Slice | Blocked by | Dischargeable by an agent? |
|---|---|---|---|
| 1 | `C1` — describe/book split in `_build_stepper` | **nothing** | **yes** — prerequisites NONE, no ADR gate, no `ENGINE_VERSION` change; gate is 50 digests unmoved |
| 2 | G9 + G13 signatures | human | **no** |
| 3 | `C2` — `settle` / `finalize` / P10 / `iter_portfolio` | `C1` + G9 + G13 | yes, after 1–2 |
| 4 | Importer-allowlist decision for `participant.py` | human review | **no** |
| 5 | `C3` — **this slice** | `C2` + step 4 | yes, after 1–4 |

`C5` (pin the allocation plan revision) is disjoint from all of the above and is the plan's
recommended second-lane filler while the `C1 → C4` chain is serial.

---

## 8. Evidence

```text
base                     6902710 (origin/main), working tree clean
uv sync --all-extras                                              exit 0
uv run pytest tests/unit/oracles -q --no-cov                      exit 0   115 passed
uv run pytest tests/unit/test_backtest_engine_stepper.py \
             tests/unit/test_backtest_item_intents.py -q --no-cov exit 0    55 passed
git diff -- backend/                                              empty (no product change)
```

Baselines are recorded so the next attempt can prove it moved nothing. The suites were run
**before** any decision to stop, not to justify one after the fact.
