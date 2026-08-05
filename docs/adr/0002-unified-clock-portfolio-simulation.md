# ADR 0002 — Unified-clock multi-item portfolio co-simulation

- **Date:** 2026-08-04
- **Status:** **Accepted** (2026-08-05, PO/maintainer). §13's seven open decisions are resolved
  in the amendment table at §13.1. Approval was given *after* ADIM 15–19 had already landed —
  that ordering is recorded rather than smoothed over; see §16.
- **Scope:** the execution model for Shared Equity Allocation (doc 13 / Master Ref Modül 11).
- **Relates to:** `backend/src/entropia/domain/allocation/capability.py` (the containment this
  ADR is the exit plan for), GH #544 (NET), #559 (DST), #550/#551/#552 (sizing/booking,
  untouched by this ADR).
- **Base:** `origin/main` @ `f4e2fd3`. Every code claim below was read on that commit.

> **Docs-only.** This ADR changes no production code. It exists so the design is settled
> and so the PR boundaries of ADIM 15–20 are frozen. Its delivery-plan numbering was
> **corrected at ADIM 18** to match what actually shipped — see the note under §12.

---

## 1. Context

### 1.1 What canon requires

Canon is unusually specific about the *shape* of shared-capital execution:

- **Master Ref Modül 11 §5.2** (`:8097`) defines the valuation point: *"V1de valuation point, her
  simulasyon timestampinde zorunlu exit/stop/funding/fee islemleri islendikten sonra ve yeni entry
  intentleri execute edilmeden onceki portfolio ledger durumudur."*
- **Modül 11 §5.2** (`:8121`): *"Ayni timestampteki tum itemler ayni valuation snapshotini gorur;
  item sirasina gore gizli avantaj yaratilmaz."*
- **Doc 13 §8.3** (`:893`): *"Aynı timestampte engine, mandatory stop/exit/funding/fee olaylarını
  önce resolver; ardından **tek bir** portfolio valuation snapshotı üretir. Tüm aktif itemler aynı
  snapshotla entry/scale intent üretir. UI row sırası, DOM orderı veya API arrival orderı allocation
  sonucu değiştiremez."*
- **Doc 13 §13** (`:1265`) raises that to a normative implementation rule; **doc 13 §14 test 11**
  (`:1311`) pins it as acceptance.
- **Modül 12 §9.2** (`:8811`) fixes the per-clock-step order and requires it to be versioned in the
  engine contract and written to the manifest (`:8829`). **Doc 15 §9.3** (`:675`) restates the same
  eight steps in English.

Capital arithmetic (doc 13 §8.3, Modül 11 §5.1–§5.3):

```
P0 = initial_capital ;  r = reserve_cash_percent/100 ;  R0 = P0*r   # fixed nominal
A0 = max(0, P0 - R0) ;  Ci0 = A0*wi/100 ;  U0 = A0 - sum(Ci0)
Compound: E(t) = P0 + realized_pnl(t) - fees(t) - funding(t) - other_realized_costs(t)
          A(t) = max(0, E(t) - R0) ;  Ci(t) = A(t)*wi/100
Fixed:    Ci_fixed = A0*wi/100
allowed_size = min(desired_size, remaining_sleeve_capacity, item_risk_limits, ledger_solvency_limit)
```

### 1.2 What ships today

The engine does not do this, and the repository already says so in its own code.

- `run_engine` (`backend/src/entropia/domain/backtest/engine.py:755`) simulates **one item against
  one pinned bar stream**. Its only bar loop is `for batch in bar_batches: for raw in batch:`
  (`engine.py:1782-1783`).
- The worker loops **over items**, not over time:
  `for prepared in prepared_items:` (`backend/src/entropia/application/jobs/backtest_engine.py:298`),
  each item replayed to completion with its own `_Ledger` (`engine.py:846`) seeded from the **full**
  pool P0 (`resolve_allocation_execution`, `engine.py:614-649`, returns `initial_capital=p0` for
  every item).
- `combine_item_runs` (`domain/backtest/execution/portfolio.py:312`) then **concatenates** the
  finished runs' realized-PnL progressions in manifest pin order (`portfolio.py:400-436`).
- Consequences, both financial:
  1. the composite "portfolio equity curve" is not a time series — its points carry item-order
     timestamps, so `max_drawdown` and everything derived from it is measured along a curve that
     never existed;
  2. under `COMPOUND_PORTFOLIO_EQUITY` an item's sleeve compounds off **its own** equity and can
     never see a sibling's PnL, fees or funding — the pool is shared in name only.

Both are pinned by a test that asserts the *defect* on purpose:
`backend/tests/unit/test_shared_allocation_containment.py::test_composite_portfolio_curve_is_not_time_ordered`
(`:139-190`) constructs two items whose trades interleave in wall-clock time and asserts the shipped
`max_drawdown == 5000.00` while a hand-computed unified-clock replay of the *same four closes* gives
`3000.00` — a **66 % overstatement**.

### 1.3 Containment, and why this ADR exists

Because a shared-mode run would publish those numbers as an immutable canonical Result, shared mode
is **failed closed**, not merely disclosed:

- `SHARED_ALLOCATION_STATUS = "future_dev"` (`domain/allocation/capability.py:105`);
- `validate_allocation` raises `SHARED_MODE_NOT_IN_BUILD` as the **lead** blocker
  (`domain/allocation/rules.py:150-163`);
- an **independent** admission guard reads the immutable snapshot directly and refuses the run even
  if readiness were bypassed (`application/commands/backtest_run.py:543-557` →
  `ReadinessIssueCode.ALLOCATION_SHARED_MODE_NOT_IN_BUILD`).

Independent mode (`enabled=false`) is untouched and is a **complete, canonical mode** (doc 13 §1.1).

`capability.py:76-93` already states six **removal conditions**. This ADR turns them into a design:

| # | Removal condition (verbatim, condensed) | Addressed in |
|---|---|---|
| 1 | outer loop = merged timestamp axis, not the item list | §4, §5 |
| 2 | ONE shared ledger holding P0, R0, U0 | §7 |
| 3 | mandatory events first, then exactly ONE `E(t)`; every item sizes `Ci(t)` against it | §8 |
| 4 | symmetric conflict/exposure arbitration, deterministic id tie-break, no share transfer | §9 |
| 5 | doc 13 §14 test 11 passes; composite curve time-ordered by construction | §14 |
| 6 | `ENGINE_VERSION` bumped so no sequential-era Result is idempotently reused | §10 |

---

## 2. Current call graph and data structures (the baseline this ADR replaces)

```
apps/worker/actors.py:141  run_backtest_engine (dramatiq, queue="backtest")
  └─ application/jobs/backtest_engine.py:135  run_backtest
       ├─ :219  _resolve_enabled_strategies                    (STRATEGY items only)
       ├─ :255  _prepare_strategy   (per item: bars, indicators, funding, ticks, allocation)
       ├─ :298  for prepared in prepared_items:                ◄── THE ITEM LOOP
       │     └─ :322 _replay_strategy → domain/backtest/engine.py:755 run_engine
       │              └─ engine.py:1782  for batch in bar_batches: for raw in batch:
       ├─ :347  single-item fast path (byte-identical, no compose)
       └─ :363  domain/backtest/execution/portfolio.py:312 combine_item_runs   ◄── sequential fold
```

Load-bearing structures (`domain/backtest/execution/state.py` unless noted):

| Concern | Symbol | Notes |
|---|---|---|
| bar | `_Bar` `:26` | `timestamp: str` (**a string**, `:30`), OHLCV as `Decimal` |
| position | `_Position` `:38` | exactly **one** per item run (`engine.py:1146`) |
| capital | `_Ledger` `:172` | `equity`, `peak`, `funding_paid`, `equity_points` — one per **item** today |
| frozen config | `_RunConfig` `:369` | everything `run_engine` reads, never mutated |
| allocation | `AllocationExecution` `:291` | `initial_capital` (= P0 for **every** item), `reserve_percent`, `compound`, `item_share_percent` |
| cross-item | `PortfolioRules` `:341`, `PriorItemInterval` `:319` | forward-only, pin-order precedence; `start_ms/end_ms` are **UTC epoch ms** |
| output | `EngineOutput` (`engine.py:188`), `ItemRun` (`engine.py:208`) | |

Every equity mutation site (exhaustive): `execution/booking.py:96` (realized PnL, commission netted),
`booking.py:222` (partial-fill remainder commission), `engine.py:1953` (funding),
`engine.py:2909` / `engine.py:3095` (stack / ladder add commission). Sizing always reads the *current*
`led.equity` (`execution/sizing.py:282-317`), which is why funding is applied at the top of the bar.

Non-Strategy items today: `_enabled_non_strategy_items` (`jobs/backtest_engine.py:647-676`) records
Trading Signal / Trade Log items with `output=None` — **no standalone simulation is run for them**,
although `ALLOCATABLE_ITEM_KINDS` (`domain/allocation/rules.py:41-46`) lets all three kinds take a
sleeve. See OD-6.

---

## 3. Decision

**Adopt a unified-clock, batch-by-timestamp co-simulation**: the engine's outer loop becomes the
merged, ordered set of *valuation points* across all active items; per item it keeps a resumable
replay cursor; one shared ledger holds the pool; exactly one portfolio valuation snapshot is
published per tick and every item forms its intent against that snapshot.

### 3.1 Alternatives considered

| Option | Summary | Verdict |
|---|---|---|
| **A. Sequential fold (status quo)** | replay each item whole, concatenate | **Rejected.** Proven wrong drawdown (§1.2); cannot share capital at all; contradicts doc 13 §8.3 directly. |
| **B. Event-sourced clock** | materialize a persisted event log, replay it | **Rejected.** Adds a serialization/storage layer and a second source of truth to an engine that is deliberately a pure function of `(config, bars, allocation)` (`engine.py:617-620`). Determinism is *already* structural here; event sourcing buys replay-debuggability we get more cheaply from the existing decision trace. |
| **C. Batch-by-timestamp (merged axis outer loop)** | one loop over merged decision times; per-item cursors; one snapshot per tick | **Chosen.** It is the literal shape canon describes ("her simulation clock adımı", Modül 12 §9.2). It is the smallest delta from the existing phase structure. It makes "same snapshot for all items" true *by construction* rather than by discipline. It matches removal condition #1 verbatim. |
| **D. Per-item actor / coroutine with a barrier** | same semantics as C, implemented with concurrency | **Rejected.** Identical semantics at strictly higher risk: a deterministic replay gains nothing from concurrency, and any scheduling nondeterminism becomes a reproducibility bug in an artifact that must be byte-identical (golden digests, `execution_key`). |

### 3.2 The invariant that bounds the blast radius

> **Single-item reduction.** With exactly one executing item, the merged axis **is** that item's own
> bar axis and the shared ledger **is** that item's ledger. A single-Strategy composition must
> therefore replay **byte-identically** to today.

**Where the boundary actually is — stated at the code level, because the obvious answer is wrong.**

The invariant does **not** hold because the unified loop "degenerates naturally": it would not. Today
an `EquityPoint` is appended **only** inside `close_position` (`execution/booking.py:137`; the sole
other append is the run seed, `engine.py:849`), so funding-induced equity changes produce no point at
all. A ledger that also records them (§7) yields a curve with *more* points and a different digest
even where every trade and every metric is identical.

Nor is the worker-level shortcut `if len(item_runs) == 1 and not non_executing:`
(`application/jobs/backtest_engine.py:347-350`) sufficient, because it never fires for the tests that
matter: **`grep -c run_backtest backend/tests/unit/test_backtest_engine_golden.py` returns `0`** — 42
of the 46 golden scenarios call `run_engine()` directly and the other 4 call `combine_item_runs()`
directly. Nothing in `run_backtest` protects them.

> **The boundary is therefore the engine entry point, not the worker.** `run_engine(...)`
> (`domain/backtest/engine.py:755`) keeps its signature **and its semantics**: one item, its own
> `_Ledger`, per-close equity points. ADIM 16 extracts its bar-loop body into a resumable stepper and
> `run_engine` becomes a thin driver that runs that stepper to completion — observably unchanged.
> The P0–P9 phase machinery, the shared `PortfolioLedger` and the per-tick equity rule live in a
> **new** entry point (`run_portfolio(...)`) that the worker calls only when more than one item
> executes. A bare `run_engine(allocation=…, portfolio_rules=…)` call never enters the phase loop.

That is what makes A14 checkable rather than aspirational, and it is a binding constraint on ADIM 16
and 18, not a hope.

This yields a falsifiable prediction over the 46 recorded golden scenarios
(`backend/tests/unit/engine_golden_digests.json`), checked against `_scenarios()` in
`backend/tests/unit/test_backtest_engine_golden.py`:

- **38 scenarios must NOT move.** All are single-item replays — including
  `sizing.allocation_sleeve_compound` / `sizing.allocation_sleeve_fixed` (single item *with*
  allocation on, `:345-351`), and `portfolio.rules_none` (`:454`, `prules._run(config, rules=None)` —
  a single-item run with no portfolio rules at all, despite the `portfolio.` prefix).
- **4 scenarios move or are replaced:** `portfolio.combine`, `portfolio.combine_reversed`,
  `portfolio.combine_shared_pool`, `portfolio.combine_non_executing_only` — direct
  `combine_item_runs` calls (`:475-483`).
- **4 scenarios are replaced, not re-digested:** `portfolio.rules_block_opposite`,
  `portfolio.rules_exposure_cap`, `portfolio.rules_exposure_invalid`, `portfolio.rules_net_downgrade`.
  Their fixture feeds *synthetic prior intervals* into a single-item run (`:425-433`); ADIM 19 retires
  that concept, so the scenarios must be rebuilt as genuine two-item co-simulations.

Any *other* digest moving in ADIM 15–20 is a regression, not an intended change.

---

## 4. The global clock

### 4.1 Tick key

- **`t_ms: int`** — UTC epoch milliseconds. Chosen over the raw `str` timestamp because the codebase
  already uses epoch ms as its cross-item time key (`PriorItemInterval.start_ms/end_ms`,
  `state.py:336-337`, via `_epoch_ms_or_none`, `engine.py:693-702`) and because string ordering is
  only accidentally correct for mixed offset forms.
- **One tick = one valuation point.** Items are *not* part of the tick key: canon requires every item
  at time `t` to see the same snapshot, so the item dimension must live *inside* a tick, never
  alongside it.

### 4.2 Tick set

```
ticks(run) = sorted( ⋃_i decision_times(item_i) )        # deduplicated
```

`decision_times(item_i)` is the set of instants at which item *i*'s pinned base bars become
decidable. **Funding/fee events do not create ticks**; they are applied per item at the first tick
`t ≥ available_at` (this is exactly today's behaviour — `due_funding_charges`,
`execution/costs.py:85`, consumes every record with `available_at <= decision_time`).

This definition satisfies §3.2 by construction: with one item, `ticks(run) == decision_times(item_1)`.

### 4.3 What a bar's timestamp means (adjudication A-1)

`RecordTimeBasis` (`domain/market_data/enums.py:71-77`, values `BAR_CLOSE` / `BAR_OPEN` /
`EVENT_TIME`) is persisted (`models/market_data.py:79-80`) and pinned into the manifest
(`commands/backtest_run_context.py:324`) — and is **never read inside `domain/backtest/`**. The engine
uniformly treats `bar.timestamp` as *the instant this bar's OHLC becomes decidable* (see
`engine.py:386-388`, `engine.py:1815-1818`).

> **A-1 — the unified clock keeps the shipped convention: `decision_time == bar.timestamp`, read as
> an absolute UTC instant.** It does **not** start branching on `record_time_basis`.

Rationale: every shipped Result was produced under this convention; changing it is a *second*
semantic change that would land in the same digest refresh as the clock change, and the two would be
indistinguishable afterwards — the exact failure mode `docs/ADIM12_LANDED_KICKOFF.md:63-67` warned
about for #549. Honoring `record_time_basis` is a separate, later decision (**OD-1**).

### 4.4 Ordering *within* a tick

- **Intent formation is order-free by construction** (all items read one frozen snapshot; §6).
- Where per-item work must be serialized against the shared ledger (fills, arbitration), items are
  ordered by the stable tuple **`(pin_ordinal, item_id)`**, where `pin_ordinal` is the index from
  `_pinned_items` (`domain/backtest/manifest.py:140-157`, already a deterministic
  `(root_id, selected_revision_id)` sort — never DOM order, never request-arrival order).
- No `set`/`dict` iteration may influence a numeric outcome. Note the one existing float site,
  `_pearson` (`execution/portfolio.py:170-182`), which stays float-based and analytic-only.

---

## 5. Item-local bars, MTF, and missing/stale data

Each item keeps its own cursor. The clock advances the cursor; it does not reinterpret the data.

- **MTF stays item-local and unchanged.** Higher timeframes are *resampled from that item's own base
  bars* by `floor(epoch / span)` bucketing (`domain/backtest/indicators.py:178-185`), and a higher-TF
  candle becomes readable only on the **first base bar of the next bucket** (`indicators.py:908-937`;
  pinned by `test_higher_tf_cross_is_only_readable_after_the_candle_closes`,
  `tests/unit/test_backtest_multi_timeframe.py:92-99`). That one-base-bar visibility lag is shipped
  behaviour and is **preserved**, not silently corrected — correcting it would move single-item
  digests and violate §3.2.
- **Research/funding availability is re-derived per item at every tick.** The single gate
  `is_eligible_for_decision(available_at, decision_time, has_instrument_mapping)`
  (`domain/research_data/time_policy.py:199-211`) is evaluated against **that item's decision time at
  this tick**, never once per item-stream. PR #560's parity tests
  (`tests/integration/test_research_point_in_time_parity.py`) fix the contract each cursor must obey;
  the clock restructure must not weaken it.
- **A tick at which item *i* has no bar is not a decision for item *i*.** It produces **no intent**
  from that item. Its open position is still **marked** so that `E(t)` is a portfolio-wide number.
- **Marking a position at a tick with no fresh bar requires a policy that canon does not supply.**
  Modül 15 §10 (`:10311-10322`) fixes alignment/stale/missing rules for *research data* and forbids
  unbounded forward-fill; it says nothing about marking a *position* across heterogeneous item
  calendars. → **OD-2**.
- **Heterogeneous calendars have no existing utility to reuse.** There is no cross-instrument merge,
  align, reindex or gap-fill anywhere in `backend/src` (`engine.py:792-795` states the deferral
  explicitly). This is new ground, not a refactor.
- **DST.** Fold resolves to `fold=0` (first occurrence) and a nonexistent gap time is silently
  accepted — both an accidental `zoneinfo` default, characterized in
  `docs/audit/research_point_in_time_matrix.md:114` and open as **GH #559**. A merged axis spanning
  sources in different declared zones inherits this. The clock must not paper over it: #559 is a
  **prerequisite decision**, not a consequence (see §13).

---

## 6. The item intent contract

```python
@dataclass(frozen=True, slots=True)
class ItemIntent:
    item_id: str
    kind: Literal["entry", "scale_in", "exit", "partial_exit", "no_op", "blocked"]
    direction: str | None                 # "long" | "short" | None
    desired_size: Decimal                 # pre-cap, from Strategy Details sizing
    reference_price: Decimal              # the price the intent was formed at
    reason: str                           # decision-trace token
    evidence: Mapping[str, Any]           # evaluated rule ids, block ids
```

Contract:

1. **Pure.** `form_intent(item_view, portfolio_snapshot) -> ItemIntent` is a function. It performs no
   ledger write, no I/O, and no mutation of item state.
2. **Blind to siblings.** It may read the portfolio *snapshot* (an aggregate) but never another
   item's position, cursor or pending order — doc 13 §8.4 step 4 / Modül 11 §6.2 step 4: *"Bir itemin
   yeni orderi baska itemin signal gorusunu degistirmez."*
3. **Idempotent.** Calling it twice at the same tick yields an equal value.
4. **Stops, exits, funding and fees are NOT intents.** They are mandatory events resolved *before*
   the snapshot exists (Modül 11 §5.2). Modelling them as intents would put them after the
   valuation point and invert the canonical order.
5. `no_op` and `blocked` are first-class: a suppressed intent must be *emitted and traced*, never
   silently dropped.

---

## 7. Shared ledger and portfolio snapshot

```python
@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:              # published ONCE per tick, immutable
    t_ms: int
    equity: Decimal                   # E(t)
    reserve_nominal: Decimal          # R0 — fixed at run start, never re-derived
    allocatable: Decimal              # A(t) = max(0, E(t) - R0)
    sleeve_capacity: Mapping[str, Decimal]   # item_id -> Ci(t)
    deployed_notional: Mapping[str, Decimal]
    unallocated: Decimal              # U(t)

class PortfolioLedger:                # ONE instance per run (mutable)
    pool_initial: Decimal             # P0
    reserve_nominal: Decimal          # R0
    cash: Decimal
    realized_pnl: Decimal
    fees: Decimal
    funding: Decimal
    positions: dict[str, _Position | None]    # item_id -> at most one position
    equity_points: list[EquityPoint]          # appended when E(t) moves; time-ordered
    position_intervals: list[dict]            # held windows — see note below
```

Rules:

- **One ledger.** `_Ledger` (`state.py:172`) becomes per-run, not per-item; the five equity-mutation
  sites (§2) write into it, tagged with the originating `item_id` for attribution.
- **A sleeve is a cap, not a wallet.** Allocation is an outer cap layer (Modül 11 §6.1); capital is
  not physically partitioned. `remaining_sleeve_capacity_i = max(0, Ci(t) - deployed_notional_i)`.
- **`R0` is fixed nominal** (doc 13 §0.2, §6.1; Modül 11 §1.2.6) — never re-derived from `E(t)`.
- **`U0` is never borrowed** (doc 13 §1.1, Modül 11 §1.2.7).
- **Fixed mode** holds `Ci_fixed = A0*wi/100`; PnL still books to the ledger (Modül 11 §5.3).
- **Existing open positions are never force-rebalanced** when equity moves (doc 13 §8.3, §6.1).
- **`position_intervals` is kept, and its consumer changes.** `_Ledger.position_intervals`
  (`state.py:199`) is populated on every full close (`booking.py:151-158`, *"Always captured (cheap,
  additive); consumed only when portfolio rules are configured"*) and today feeds
  `build_prior_intervals` → `PriorItemInterval`, i.e. exactly the forward-only mechanism ADIM 19
  retires. The journal itself stays — it is the per-item held-window record the Result's exposure and
  contribution blocks read — but after ADIM 19 nothing consumes it as a *constraint input*, because
  overlap is observed live in the shared ledger instead of reconstructed from a finished run.
- **Equity-series rule: append one point at every tick at which `E(t)` changed**, plus the run seed —
  so the composite curve is time-ordered *by construction* (removal condition #5). Canon fixes no
  cardinality: Modül 12 §10 (`:8850`) requires only *"Timestamped equity, drawdown, exposure,
  allocated capital and portfolio state"*.

  Why this exact rule, and not "one point per tick": canon's `E(t)` is **realized-only**
  (doc 13 §8.3 — realized PnL, fees, funding, other realized costs; unrealized moves are absent).
  `E(t)` therefore changes at exactly three kinds of event, all already implemented: trade close
  (`booking.py:96`), funding (`engine.py:1953`), and remainder/stack/ladder commission
  (`booking.py:222`, `engine.py:2909`, `engine.py:3095`). Emitting a point at each captures every
  movement of `E(t)` **exactly**, while a point at every tick would add only flat repeats — more
  data, no more information, and a much larger artifact on a 1m axis.

  Consequence to declare, not hide: today's curve records **only** trade closes, so a funding charge
  between two trades is invisible to `max_drawdown`. Under this rule the portfolio curve sees it.
  Metric *definitions* are unchanged (see §10.3), but the series feeding them becomes complete →
  **OD-7**.

---

## 8. Phase order (the versioned engine contract)

Derived from **Modül 12 §9.2** (steps 99–106, `:8813-8827`), **doc 15 §9.3** (`:675`), **Modül 11
§5.2 / §6.2**, and **doc 13 §8.4**. Executed once per tick.

### 8.1 State diagram

Run-level state machine (unchanged from doc 15 §9.3 — the clock lives inside `RUNNING`):

```
RequestBacktestRun -> QUEUED -> PROVISIONING -> RUNNING -+-> SUCCEEDED -> immutable BacktestResult
                                                         +-> FAILED    -> diagnostics only, no Result
                                                         +-> CANCELLED -> diagnostics only, no Result
```

Inside `RUNNING`, the unified clock is the following state machine. One full cycle is one tick; `PV`
is the single point at which portfolio state is frozen and published.

```
                    +----------------------------------------------+
                    |               CLOCK ADVANCE                  |
                    |  t <- next(merged axis); no bar => mark only  |
                    +----------------------+-----------------------+
                                           v
   === MANDATORY (ledger writes; no discretion) ==============================
     P0 admit data(t) -> P1 funding/fee -> P2 pending fills -> P3 stop/exit
   ==========================================+===============================
                                           v
                    +----------------------------------------------+
                    |  PV - PUBLISH ONE PortfolioSnapshot(t)       |
                    |  E(t) -> A(t)=max(0,E(t)-R0) -> Ci(t)        |
                    |  FROZEN: no writer may run until P7          |
                    +----------------------+-----------------------+
                                           v
   === DISCRETIONARY (reads PV only; no ledger writes) ======================
     P4 form intents (order-free, parallel-safe, one per active item)
          |
          v
     P5 conflict / exposure arbitration ------> blocked --+  (share NOT moved)
          |                                               |
          v                                               |
     P6a sizing -> item risk limits   (pure; order vs P5 immaterial, A-2)
          |                                               |
          v                                               v
     P6b sleeve cap Ci(t) -> ledger solvency --> rejected / capped
   ==========================================+===============================
                                           v  admitted
   === APPLY (ledger writes, (pin_ordinal, item_id) order) ==================
     P7 schedule/execute -> P8 same-direction scaling -> P9 commit
     P9: append exactly ONE EquityPoint(t) + decision trace + diagnostics
   ==========================================+===============================
                                           v
                        more ticks? -- yes --> CLOCK ADVANCE
                                     \- no ---> finalize -> SUCCEEDED
```

Two properties are visible in the shape, and are the reason for it: **(i)** nothing between `PV` and
`P7` may write to the ledger, so every item provably reads the same `E(t)`; **(ii)** the only ordered
regions are the ledger-writing ones, so item order can never influence *what an item decides* — only
the sequence in which already-admitted work is applied.

### 8.2 Phase table

| # | Phase | Scope | Writes ledger? | Canon |
|---|---|---|---|---|
| P0 | Admit data available at `t` (per-item cursors; research/funding availability re-derived) | per item | no | M12 §9.2/99; doc 15 (1) |
| P1 | Funding / fee / carry on open positions | per item | **yes** | M12 §9.2/100; doc 15 (2) |
| P2 | Resolve open orders and previously scheduled fills | per item | **yes** | M12 §9.2/101; doc 15 (3) |
| P3 | Mandatory protection/stop and exit logic, per manifest priority policy | per item | **yes** | M12 §9.2/102; doc 15 (4) |
| **PV** | **Publish exactly ONE `PortfolioSnapshot`: `E(t)`, `A(t)`, `Ci(t)` for every item** | **global, frozen** | no | **M11 §5.2; doc 13 §8.3, §8.4/3** |
| P4 | Every active item forms its `ItemIntent` against **PV** | per item, order-free | no | doc 13 §8.4/4; M11 §6.2/4 |
| P5 | Cross-item conflict / exposure arbitration | global | no | M11 §6.3; M12 §9.2/103 |
| P6a | Strategy-Details sizing + item risk limits (pure; position vs P5 immaterial — see A-2) | per item | no | M11 §6.1 layers 2–3 |
| P6b | Allocation sleeve cap `Ci(t)` → ledger solvency | per item, tie-break order | no | doc 13 §8.4/5; M11 §6.1 layers 4–5, §6.3 |
| P7 | Schedule / execute admitted orders per execution model | per item | **yes** | M12 §9.2/104; doc 15 (6) |
| P8 | Same-direction scaling | per item | **yes** | M12 §9.2/105; doc 15 (7) |
| P9 | Append **one** equity point at `t`; state snapshot, decision trace, diagnostics | global | **yes** | doc 13 §8.4/7; M12 §9.2/106 |

Two adjudications were required to build this table:

> **A-2 — conflict arbitration precedes the *sleeve cap* specifically (P5 before P6b).**
>
> The two documents genuinely order this differently, and neither states a precedence rule for
> resolving that. Modül 11 §6.3 (`:8196`) says *"Allocation bu conflict kararindan sonra
> uygulanir."* Doc 13 §8.4 — whose own title is *"Deterministik pipeline ve Conflict Rules
> ilişkisi"* (`:895`) — numbers conflict as step 6, after the sleeve check in step 5. **This ADR
> does not claim doc 13 "isn't really a sequence"; it is one.**
>
> Nor does doc 13 §0.1 settle it. That section is a *Source Traceability Map* — it records where doc
> 13's content was **derived** from (*"Birincil canonical kaynak"*, `:41-43`). It is provenance, not
> a conflict-resolution precedence rule, and must not be used as one.
>
> So this is an **adjudication**, in the same sense as O-02 / O-12 / O-30 in `CLAUDE.md`, and it
> needs sign-off. It is adjudicated toward Modül 11 §6.3 for two reasons: (a) §6.3 is a *direct
> statement about the relationship* between the conflict decision and allocation, whereas doc 13
> step 6's sentence is the **non-transfer** invariant (*"o itemin shareı diğer itemlere run içinde
> otomatik devredilmez"*), which holds at every phase regardless of order; (b) the financial stakes
> are low and should be stated honestly — a conflict-blocked item is rejected under either order, so
> the choice changes the **reported reason and decision trace**, not the fill.
>
> **A-2 is deliberately narrow.** §6.3 licenses "conflict precedes *allocation*", i.e. the
> sleeve-cap layer of Modül 11 §6.1's five-layer table (`:8170-8176`: signal → sizing → item risk →
> allocation sleeve → portfolio ledger). It does **not** license "conflict precedes sizing and item
> risk limits", and Modül 11 §6.2's own numbered pipeline never mentions Conflict Rules at all. P6
> is therefore split: **P6a** (sizing + item risk limits) is a pure per-item computation whose
> position relative to P5 cannot change any outcome — a blocked intent's size is irrelevant — so
> canon's silence there is harmless; **P6b** (sleeve cap) is the layer §6.3 actually places after
> conflict.

> **A-3 — Modül 11 §6.2 and Modül 12 §9.2 are reconciled, not in conflict.**
> M12 step 103 computes *whether a new entry is allowed* (conflict/exposure/allocation) **before**
> step 104 evaluates entry signal blocks; M11 §6.2 generates intents (step 4) **before** checking
> them (step 5). Reconciliation: **P4 forms the intent, P5–P6b compute the permission envelope, P7
> schedules the order.** Both readings are satisfied; neither document is overridden.

Modül 12 (`:8829`) additionally requires: a step's result may be used by a later step **in the same
clock step**, but no next-bar/next-event information may leak backwards, and the exact precedence
must be pinned in `engine_contract_version` and written to the manifest. §10 does that.

---

## 9. Conflicts, capacity contention, NET, cross-margin

### 9.1 Sleeve contention is structurally impossible; solvency contention is not

Because `sum(wi for active) <= 100` is a hard blocker (doc 13 §10.1, Modül 11 §7.1) and `Ci(t)` is a
share of `A(t)`, the sleeves can never oversubscribe the allocatable pool. Contention can therefore
arise **only** through `ledger_solvency_limit` — when cash or required margin is short.

### 9.2 What canon already decides

Modül 11 §5.3 (`:8140-8141`) decides the *response*: *"Ledger insolvency veya gerekli teminat
yetersizse engine orderi **reddeder**, kismi fill veya sessiz borrow yapmaz."*

> **Derived, not invented: a solvency shortfall produces a REJECT, never a partial fill and never a
> borrow.** This closes the "partial capacity policy" question at the response level.

What canon does **not** decide is *which* competing intent is rejected when several would fit
individually but not together. → **OD-3**.

### 9.3 Invariants that hold regardless of OD-3

- A blocked item's share is **never** transferred to another item within the run (doc 13 §8.4/6,
  §13; M11 §6.3). Share structure is fixed for the life of the run snapshot.
- Arbitration must be **symmetric and deterministic** with an id-based tie-break
  (`capability.py:85-87`) — no item may gain an advantage from a user-visible ordering (doc 13 §13).
- Every rejection is emitted to the decision trace with a typed reason; silence is forbidden.

### 9.4 NET — out of scope, and lifting containment does not fix it

`CrossItemConflictPolicy.NET` (`domain/allocation/enums.py:37-53`) is executed conservatively as
`BLOCK_OPPOSITE` today (`domain/allocation/rules.py:217-228`, downgrade path
`domain/backtest/engine.py:862-871`), disclosed as `CONFLICT_POLICY_NET_V1`. Canon defines **no**
netting semantics — not the netting price, not which ledger holds the net position, not PnL
attribution; doc 13's own draft contract (`:816`) has no `conflict_policy` field at all (the column
arrived with migration `0035_portfolio_rules`, after doc 13 v1.1).

> **The unified clock does not define NET.** It removes NET's stated *excuse* ("needs a unified-clock
> co-simulation") without supplying its semantics. **GH #544 must be closed before or with ADIM 19**;
> otherwise NET must remain an explicitly disclosed downgrade with corrected, present-tense wording.

### 9.5 Cross-margin — explicitly out of scope

Doc 13 mentions "margin" exactly once (`:1313`, acceptance test 12: no silent borrow) and defines no
maintenance-margin formula, no shared-margin equation and no liquidation rule; Master Ref §10.2
delegates `leverage_mode=cross` semantics to a portfolio risk model that does not exist
(`docs/audit/capability_matrix_canonical_adjudication.md:188-193`, status `canonical_gap`).

> The shared ledger is a **prerequisite** for a future cross-margin model, not an implementation of
> one. `position_sizing.leverage_mode = cross` stays `canonical_gap` after ADIM 20. Nothing in this
> ADR may be read as shipping cross-margin.

---

## 10. Manifest, versioning, attribution, historical compatibility

### 10.1 Three canon-required manifest fields are missing today

Doc 13 §13 (`:1277`) and Modül 11 §10 (`:8313-8333`) require the shared-mode manifest to carry the
exact plan revision, **resolved sleeve amounts**, **currency/FX refs**, the compounding mode and
**`engine_allocation_policy_version`**. The shipped `capital_execution` snapshot carries only
`{enabled, plan_id, plan_revision_id, config_hash, config}`
(`application/commands/readiness_check.py:829-835`); `grep -rn "allocation_policy" backend/ docs/openapi.json`
returns **nothing**. Benign today only because shared mode is contained. **Must close before ADIM 20.**

### 10.2 A latent pinning drift, found while writing this ADR

`_resolve_allocation` (`readiness_check.py:805-838`) documents itself as *"pins the plan's current
revision config where one exists … else the live draft"*, but the code unconditionally builds
`config = _plan_to_config(plan, entries)` from the **live draft rows** and then records
`plan_revision_id = plan.current_revision_id` as a bare pointer. Nothing asserts that the pinned
config byte-matches the named revision row (`PortfolioAllocationPlanRevision.config`).

Doc 13 §8.5 requires the composition snapshot to fix the *exact* plan revision. The snapshot is taken
once and never re-joined, so this is not a live-join defect — but "plan revision N" and "what was
actually simulated" can diverge. **Recorded as risk R-1; must be resolved before shared mode
executes.** It is out of scope for the clock work itself and should be a separate narrow PR.

### 10.3 Version plan

| Knob | Today | After ADIM 20 |
|---|---|---|
| `ENGINE_VERSION` (`domain/backtest/manifest.py:126`) | `backtest-engine-v18-gap-adjusted-stop-fill` | **bump** — proposed `backtest-engine-v18-unified-clock-portfolio` |
| `execution_key` namespace | derived from `execution_content` incl. `engine_version` (`manifest.py:228-239`) | shifts automatically ⇒ no sequential-era Result can be idempotently reused for a unified-clock re-RUN (removal condition #6) |
| `engine_allocation_policy_version` | **absent** | added, canon value `portfolio-allocation-v1` |
| new: `clock_policy_version` | — | pins the tick-set rule (§4.2) + A-1 |
| new: `arbitration_policy_version` | — | pins §9 (incl. the OD-3 outcome) |
| new: `mark_staleness_policy` | — | pins the OD-2 outcome |
| `SHARED_ALLOCATION_STATUS` (`capability.py:105`) | `future_dev` | `active_v1` — **only** after §14 passes |
| `METRIC_SET_VERSION` | `metric-set-v1` | unchanged (metric definitions do not change) |

**Note on CLAUDE.md drift:** `CLAUDE.md` §Current position states `ENGINE_VERSION =
backtest-engine-v18-same-candle-entry-exit` and "78 pass + 1 `xfail(strict)`" in the oracle package.
Both are **stale** on `f4e2fd3`: `manifest.py:126` reads `…gap-adjusted-stop-fill`, and
`grep -rn xfail backend/tests/unit/oracles/` returns **zero** hits (#549 was fixed by PR #555). Trust
the source files.

### 10.4 Historical compatibility (non-negotiable)

- **No persisted Result is mutated, re-run or re-interpreted.** Old shared-pool Results stay
  byte-identical and keep their own pinned `portfolio_curve_sequential_not_unified_clock`
  diagnostic; they are *labelled* at read time via `LEGACY_SEQUENTIAL_RESULT_NOTE`
  (`capability.py:138-149`), never rewritten.
- Result attribution keeps reading the **pinned** manifest (`domain/backtest/history.py:252-329`,
  `mainboard_item_labels`) — never a live composition join.
- OpenAPI: `tests/contract/test_openapi_contract.py::test_openapi_snapshot_is_current` trips on any
  response-model change; the fix is `make openapi` committed in the same PR. Only ADIM 20 (Result
  portfolio metadata) is expected to touch it.

---

## 11. Failure, rollback, determinism, performance

**Rollback is already built.** Flipping `SHARED_ALLOCATION_STATUS` back to `"future_dev"`
(`capability.py:105`) refuses every shared run again through two independent guards (validation and
run admission). No migration, no data change, no Result invalidation. Every slice below must keep
that one-constant rollback intact until ADIM 20.

**Failure semantics.** A worker that cannot place a tick, mark a position, or resolve an item cursor
**fails the run** (`RUN_FAILED_*`) rather than skipping — Modül 12 §9 forbids fallback. Partial
output is never published as a Result (doc 15 §9.3: only `SUCCEEDED` produces one).

**Determinism.**
- Merge on `(t_ms, pin_ordinal)`; never on set/dict iteration order.
- `Decimal` throughout; the single float site (`_pearson`, `portfolio.py:170-182`) stays
  analytic-only and outside the ledger.
- No wall-clock, no randomness inside the replay (verified: `datetime.now(UTC)` appears only in the
  worker's job bookkeeping, never in `run_engine`).
- Existing determinism tests must keep passing:
  `oracles/test_oracle_properties.py:123` (replay determinism), `:97-120` (batch invariance),
  `tests/unit/test_backtest_multi_timeframe.py:196-215` (MTF batch invariance).
- **New invariant to add:** *cross-item* batch invariance — the merged axis result must not depend on
  how each item's bars were chunked. No test covers this today.

**Performance.**
- The merged axis must be a **streaming k-way merge** over the existing chunked bar iterators
  (`stream_bars=iter_bar_batches`, `jobs/backtest_engine.py:135`). Materializing all items' bars is
  not acceptable.
- Peak memory should *fall* relative to today (one ledger + N cursors, instead of N complete
  `EngineOutput`s held for the final fold). Per-tick overhead rises with item count.
- **Checkpointing regresses and must be redesigned.** O-06 today checkpoints *between items*
  (`jobs/backtest_engine.py:298-301`); a unified clock deletes that boundary. A time-based checkpoint
  (every K ticks, at a phase boundary — P9 is the only safe one) is required to keep cancel/pause
  behaviour (Modül 12 §8.2: cancel applies only at a safe checkpoint).

---

## 12. Delivery plan — ADIM 15–20 (frozen boundaries)

Each step is one branch, one PR, independently revertible. **No step lifts containment except 20.**

| ADIM | Deliverable | Primary files | Tests | Rollback |
|---|---|---|---|---|
| **15** | Merged-axis clock primitive: `t_ms` key, streaming k-way merge over item bar iterators, `(pin_ordinal, item_id)` tie-break. Pure, unused by the engine. | new `domain/backtest/execution/clock.py` | new unit tests: dedup, single-item reduction (§3.2), interleaving, empty/one-sided axes, stream-not-materialize | delete the module — nothing imports it |
| **16** | ~~Make per-item replay **resumable**: extract the bar-loop body of `run_engine` into a stepper.~~ **SKIPPED — see the correction note below.** | — | — | n/a |
| **17** | `PortfolioLedger` + `PortfolioSnapshot`; `Ci(t)` derived from one `E(t)`; `R0`/`U0` held once. Multi-item path only. | `execution/state.py`, `execution/sizing.py`, new `execution/portfolio_ledger.py` | sleeve arithmetic vs doc 13 §14 test 10 (3600/3150/1350, U0=900); compound vs fixed | revert; single-item path untouched |
| **18** | The per-tick phase loop (§8) in a **new** `run_portfolio(...)` entry point over an `ItemParticipant` contract. `run_engine` is not routed through it (§3.2). **Landed without the worker call site** — see the correction note. | new `domain/backtest/portfolio_engine.py` | doc 13 §14 **test 11** (all items see one `E(t)`; item order irrelevant); time-ordered curve; **cross-item batch invariance** — all 25 portfolio oracles carried over from the test-owned driver **unchanged** | delete the module; nothing calls it |
| **19** | Conflict/exposure arbitration (§9): symmetric, deterministic, solvency **reject** (never partial, never borrow), full decision trace. Retires `PriorItemInterval` forward-only precedence. | `execution/rules.py`, `domain/allocation/rules.py` | doc 13 §14 **tests 12, 13**; the five `portfolio.rules_*` digests re-recorded; no-share-transfer proof | revert; forward-only rules restored |
| **20** | Manifest fields (§10.1), `ENGINE_VERSION` bump, digest regeneration, **containment lift**, Result portfolio metadata + OpenAPI, codemaps. | `manifest.py`, `capability.py`, `readiness_check.py`, `docs/openapi.json`, `docs/CODEMAPS/*` | §14 acceptance matrix in full; rewrite `test_shared_allocation_containment.py` | flip `SHARED_ALLOCATION_STATUS` back to `future_dev` |

> **Correction (2026-08-05, ADIM 18) — the numbering above was written before the slices ran,
> and two rows did not survive contact with the code. Recorded here rather than quietly
> re-plotted, because §15 R-4 makes the *separation* of "restructure" from "re-price" a risk
> control, and one half of it is gone.**
>
> **The shipped slice numbers and this table's numbers are offset by one.** Because ADIM 16 was
> skipped, everything after it shipped one row early and a row was added at the end. Both
> vocabularies are in use across `docs/PROJECT_HISTORY.md`, the PR titles and the issue tracker,
> so the map is written here once rather than inferred each time:
>
> | §12 row | Shipped as | PR |
> |---|---|---|
> | 15 merged-axis clock | ADIM 15 | #567 |
> | 16 resumable stepper | **skipped** | — |
> | 17 shared ledger | ADIM 17 | #573 |
> | 18 intent layer (first half of the row) | ADIM 16 | #571 / #572 |
> | 18 phase loop (second half of the row) | **ADIM 18** | this slice |
> | 19 arbitration | ADIM 18 | #575 |
> | (not in §12) result provenance | ADIM 19 | #581 |
> | 20 manifest + containment lift | attempted as ADIM 20, **blocked** (#582) | #583 / #584 |
>
> **ADIM 16 was never written, and is now formally SKIPPED.** Its purpose was to let a
> per-item replay be advanced to a given `t` so the phase loop could interleave items. ADIM 18
> reaches the same place from the other side: `run_portfolio` is a **separate entry point** with
> its own tick loop and its own participant contract, so `run_engine`'s body is never touched
> and the 46 golden digests cannot move — which was ADIM 16's entire proof obligation. The
> stepper is therefore not a prerequisite of the phase loop.
>
> It *is* still the prerequisite of the **worker call site**. An `ItemParticipant` backed by the
> real engine has to advance one item to `t` and report what it decided; nothing in
> `engine.py` can do that today (the bar loop is nested at `engine.py:1782` inside a
> ~1100-line function). So ADIM 18 shipped the loop **without** the `jobs/backtest_engine.py`
> change its original row promised: the worker still loops over items and folds them with
> `combine_item_runs`. That gap is the whole of what keeps the containment closed, and it is
> asserted, not assumed — `tests/unit/oracles/test_oracle_portfolio_containment_gate.py::
> test_the_phase_loop_exists_but_no_production_path_reaches_it`.
>
> **Consequence, stated plainly:** R-4's mitigation (*"an ADIM 16 refactor that silently changes
> a single-item number — 46-digest invariance is the gate"*) still holds for ADIM 18 and was
> verified. But when the participant is eventually written, restructure and re-price will land
> together, and a moved digest will be harder to attribute than this plan intended.
>
> ---
>
> **AMENDMENT (2026-08-05, PR #602) — ADIM 16 is NO LONGER SKIPPED; the paragraphs above are
> superseded on that one point.** The stepper was written and merged as a pure refactor *before*
> any participant work started, so the consequence feared one paragraph up **did not
> materialise**: restructure and re-price are separated again. `run_engine`'s body up to the bar
> loop is now `_build_stepper` (`engine.py:779`), returning an `_ItemStepper` (`engine.py:755`)
> of `step(bar)` / `finalize()` / `output()` / `open_position()` plus the live ledger and run
> config; `run_engine` (`engine.py:3174`) keeps its signature, its docstring and its semantics
> and is a nine-line driver over it. The ten names that cross a bar boundary were **measured**
> by an AST pass, not guessed (`engine.py:1761-1763`); the other 83 the body binds were
> eliminated by definite-assignment analysis. Acceptance was R-4's gate and nothing else:
> **all 46 golden digests unmoved and `tests/unit/engine_golden_digests.json` itself unchanged**,
> plus `tests/unit/test_backtest_engine_stepper.py` (10 tests) locking the half no digest can
> see — the same scenarios replayed one bar per call, suspended between every pair of bars,
> digest-identical.
>
> **Unchanged by this amendment:** ADIM 16 added **no** caller — `jobs/backtest_engine.py:298`
> still loops over items, `:363` still folds with `combine_item_runs`,
> `SHARED_ALLOCATION_STATUS` stays `future_dev`, `ENGINE_VERSION` is untouched, and
> `test_the_phase_loop_exists_but_no_production_path_reaches_it` is still green. The adapter and
> the call site are a separate PR, which is the point. The **numbering** mismatch this section
> documents also stands: two shipped slices are called ADIM 16 (the intent layer, #571/#572, and
> this stepper, #602); they were not renumbered — records disambiguate as `ADIM 16 (ADR §12)`.

**Prerequisites that are not part of ADIM 15–20** and must be scheduled separately:
GH **#559** (DST rule) before the merged axis spans mixed-zone sources; GH **#544** (NET) before or
with ADIM 19; **R-1** (§10.2, revision pinning) before ADIM 20; **OD-1…OD-6** (§13) before the slice
that depends on each.

**`test_shared_allocation_containment.py` will be rewritten, not re-digested.** Its central test
asserts the defect on purpose (`:139-190`); once the clock lands, its assertions invert — the curve
becomes time-ordered and `max_drawdown` becomes `3000.00`. That inversion **is** the acceptance
proof, and the file should be renamed accordingly.

---

## 13. Open decisions (product / maintainer) — do not guess these

| ID | Question | Canon status | Options | Recommendation (**needs approval**) |
|---|---|---|---|---|
| **OD-1** | Should the engine honor `record_time_basis` (BAR_OPEN vs BAR_CLOSE vs EVENT_TIME) when building decision times? | Field is persisted and pinned; **never read** by the engine. Canon documents the distinction (Modül 4 §11.1) but the engine has one convention. | (a) keep the shipped convention (A-1) and additionally **block** a shared run whose pinned revisions declare *different* bases; (b) honor the field, changing single-item semantics; (c) keep as-is silently | **(a).** (b) entangles two semantic changes in one digest refresh; (c) lets two differently-based datasets be merged as if identical. |
| **OD-2** | How is an open position marked at a tick where its own item has no fresh bar? | Silent. Modül 15 §10 covers *research* staleness only and forbids unbounded forward-fill. | (a) carry the last closed bar's close forward with a declared `stale_after` bound + diagnostic counter; (b) exclude unmarked items from `E(t)`; (c) block runs whose calendars diverge | **(a).** (b) understates equity and breaks `E(t)`'s definition; (c) forbids the legitimate mixed-calendar portfolio the feature exists for. |
| **OD-3** | When several intents are individually affordable but jointly insolvent, which is rejected? | Silent on *selection*. The *response* (reject, no partial, no borrow) is decided by M11 §5.3. | (a) admit in `(pin_ordinal, item_id)` order until cash is exhausted, reject the rest; (b) reject **all** competing intents (fully symmetric, order-free); (c) pro-rata partial — **forbidden by M11 §5.3** | **(a)**, since `capability.py:85-87` already commits to "deterministic id-based tie-breaking". Reviewers should weigh (b): it is the only rule with *no* systematic ordering advantage, at the cost of rejecting trades that could have filled. |
| **OD-4** | Does `Ci(t)` cap **new notional at entry only**, or total held notional continuously? | Doc 13 §8.3 caps `allowed_size` for *new entry/scale*; §8.3/§6.1 forbid force-rebalancing existing positions. A position can therefore exceed `Ci(t)` after equity falls. | (a) entry/scale-time cap only (literal reading); (b) continuous cap with forced reduction — contradicts the no-rebalance rule | **(a)** — it is the literal canonical reading; recorded here only because the drift it permits is counter-intuitive and should be knowingly accepted. |
| **OD-5** | Is FX conversion in scope? Base Currency must match every item's settlement currency **or** a pinned approved FX dataset must exist (doc 13 §5.1, M11 §1.2.5). | Rule is canonical; the conversion **mechanism** is GAP-16, deferred (`engine.py:792-795`). | (a) keep out of scope: shared runs remain **single-currency**, mismatch stays a blocker (`ALLOCATION_FX_DEPENDENCY`); (b) build FX conversion inside this programme | **(a).** FX is a separate programme; bundling it would double the surface of an already large change. |
| **OD-6** | May a Trading Signal / Trade Log item hold a sleeve when the engine runs no simulation for it? | Doc 13 §1.1 and M11 §2.2 say yes, they may take a sleeve. The engine runs **nothing** for them (`jobs/backtest_engine.py:647-676`, `output=None`) while `ALLOCATABLE_ITEM_KINDS` admits all three kinds (`allocation/rules.py:41-46`). | (a) block a shared plan whose active entries include a non-executing kind; (b) allow, and disclose the sleeve as permanently idle; (c) implement Trading Signal / Trade Log execution | **(a) for ADIM 20**, with (c) as a later programme. Under (b) a user's 40 % share silently does nothing — the exact silent-degradation shape the working standard forbids. |
| **OD-7** | The portfolio equity series now records funding-induced changes to `E(t)`, which today's per-trade-close curve omits (§7). Does a *more complete* series feeding an unchanged metric definition warrant a `METRIC_SET_VERSION` bump? | Canon fixes no series cardinality (M12 §10, `:8850`). | (a) no bump — `metric-set-v1` definitions are unchanged, only the series is complete; (b) bump to `metric-set-v2` so old and new portfolio drawdowns are never compared as like-for-like | **(a)**, because `ENGINE_VERSION` already forks the `execution_key` namespace and no cross-era comparison can be silent. Flagged because a reviewer may reasonably prefer (b). |

### 13.1 Amendment table — resolutions (2026-08-05)

Approval of this ADR resolves every open decision above **to its stated recommendation**. Each
row below is the decision of record; the "Recommendation" column of §13 is now history, not a
question. Nothing was resolved against its recommendation, so no rationale in §13 needs
rewriting — only its status.

| ID | Resolution | Effect on the delivery plan |
|---|---|---|
| **OD-1** | **(a)** — keep the shipped convention (A-1). A shared run whose pinned revisions declare *different* `record_time_basis` values is **blocked**. | The blocker is not built. It belongs with the readiness check, before the axis is allowed to span mixed-basis revisions. |
| **OD-2** | **(a)** — carry the last closed bar's close forward with a declared `stale_after` bound and a diagnostic counter. | Not built. `run_portfolio` marks nothing: `E(t)` is realized-only, exactly as `PortfolioLedger` defines it, so no unmarked position can silently enter equity. Building the mark policy is a prerequisite of ADIM 20, not of the loop. |
| **OD-3** | **(a)** — on joint insolvency, admit in `(pin_ordinal, item_id)` order until cash is exhausted and reject the rest. | Already the shipped behaviour: `arbitration.CONTENTION_SELECTION_POLICY == "pin_order_admission"`. |
| **OD-4** | **(a)** — `Ci(t)` caps new notional at entry/scale time only; a position that drifts past its sleeve after equity falls is **not** force-reduced. | Already the shipped behaviour (`PortfolioLedger.set_position` checks only the increase). |
| **OD-5** | **(a)** — FX stays out of scope; shared runs remain single-currency and a mismatch stays an `ALLOCATION_FX_DEPENDENCY` blocker. | Unchanged. |
| **OD-6** | **(a) for ADIM 20** — block a shared plan whose active entries include a non-executing kind; Trading Signal / Trade Log execution stays a later programme. | Not built. `run_portfolio` takes only participants with a bar stream, so a non-executing kind cannot silently hold an idle sleeve *inside the loop*; admission is where the block belongs. |
| **OD-7** | **(a)** — no `METRIC_SET_VERSION` bump. `ENGINE_VERSION` already forks the `execution_key` namespace, so no cross-era comparison can be silent. | Applies at ADIM 20, with the `ENGINE_VERSION` bump. |

**Two of these are recorded in the ADR but not yet in the code, and that divergence is
deliberate.** `provenance.MARK_STALENESS_POLICY` still reads `"undefined_pending_od2"` and
`arbitration.CONTENTION_SELECTION_STATUS` still reads `"recommended_pending_approval"`. Both are
declarative strings published through `build_portfolio_manifest`, which nothing calls yet; ADR
§10.3 places the manifest fields in **ADIM 20**, and flipping a policy label before the manifest
that carries it exists would advertise a decision no artifact records. **ADIM 20 owns both
flips**, together with R-5 (*"must not merge until every OD is recorded in the manifest as a
versioned policy"*) — which this table is now the input to, not a substitute for.

---

## 14. Acceptance matrix (the gate for lifting containment)

| # | Criterion | Source | Evidence required |
|---|---|---|---|
| A1 | Outer loop is the merged timestamp axis, not the item list | `capability.py:76-77` | code + clock unit tests (ADIM 15/18) |
| A2 | Exactly one ledger holds `P0`, `R0`, `U0` | `capability.py:78-79` | `PortfolioLedger` singleton; no per-item `_Ledger` on the shared path |
| A3 | Mandatory events resolve first, then exactly **one** `E(t)`; every item sizes `Ci(t)` against it | doc 13 §8.3/§8.4; M11 §5.2 | phase-order test asserting PV is published once per tick and read by all items |
| A4 | **Item order does not change the result** | doc 13 §13, §14 test 11 | permuting `mainboard_items` yields an identical `EngineOutput` digest |
| A5 | Composite equity curve is time-ordered **by construction** | `capability.py:88-89` | `stamps == sorted(stamps)`; the 5000/3000 fixture now reports `3000.00` |
| A6 | Compound mode: sleeves recompute from portfolio `E(t)` incl. siblings' PnL/fees/funding | doc 13 §8.3; §14 test 11 | two-item fixture where item B's loss shrinks item A's next sleeve |
| A7 | Fixed mode: sizing base stays `Ci_fixed`; no auto-compounding; no silent borrow | doc 13 §14 test 12; M11 §5.3 | fixture + solvency reject event |
| A8 | Desired size over sleeve ⇒ deterministic cap/reject; allocation never bypasses item risk limits | doc 13 §14 test 13; M11 §6.1 | sizing chain test |
| A9 | A blocked item's share is **never** transferred | doc 13 §8.4/6, §13 | conflict fixture asserting sibling sleeves unchanged |
| A10 | Solvency shortfall ⇒ reject; never partial fill, never borrow | M11 §5.3 | ledger test + typed decision-trace event |
| A11 | `R0` fixed nominal; `U0` never borrowed | doc 13 §0.2, §6.1; M11 §1.2.6/7 | equity-path test across a large drawdown |
| A12 | Sleeve arithmetic exact | doc 13 §14 test 10 | `R0=1000`, `A0=9000`, `3600/3150/1350`, `U0=900` |
| A13 | **37 non-portfolio golden digests unchanged**; only the 9 `portfolio.*` scenarios move | §3.2 | regenerated `engine_golden_digests.json` diff reviewed scenario-by-scenario |
| A14 | Single-Strategy composition byte-identical | §3.2 | golden + full engine suite |
| A15 | `ENGINE_VERSION` bumped; `execution_key` namespace shifted | `capability.py:90-91` | `test_engine_execution_key_namespace_shifts_with_the_engine_version` + a new `_PRIOR_ENGINE_VERSION` |
| A16 | Manifest carries plan revision, resolved sleeve amounts, FX refs, compounding mode, `engine_allocation_policy_version`, `clock_policy_version`, `arbitration_policy_version`, `mark_staleness_policy` | doc 13 §13; M11 §10 | manifest test + OpenAPI snapshot |
| A17 | Point-in-time integrity preserved per item per tick | PR #560 tests | `tests/integration/test_research_point_in_time_parity.py` green, unweakened |
| A18 | Cross-item batch invariance | new (§11) | chunking each item's bars differently yields an identical digest |
| A19 | Historical Results unchanged and correctly labelled | doc 13 §11.1; §10.4 | legacy shared-pool Result read back byte-identical with `LEGACY_SEQUENTIAL_RESULT_NOTE` |
| A20 | Rollback proven: flipping `SHARED_ALLOCATION_STATUS` refuses shared runs again | §11 | containment tests retained and green under the flag |
| A21 | Cancel/pause still lands on a safe checkpoint | M12 §8.2 | tick-based checkpoint test |
| A22 | Full backend suite green at the configured gate (`--cov-fail-under=90`) | `backend/pyproject.toml:133` | single-invocation run, exit code read separately |

---

## 15. Consequences

**Accepted**

- The engine's outer loop changes shape; ADIM 16 is a pure refactor whose only proof is that
  **nothing moves**. That is deliberate: it separates "restructure" from "re-price".
- Nine golden scenarios are expected to move. Each must be reviewed individually — a moved digest is
  only acceptable with a written reason.
- `PriorItemInterval` / forward-only pin-order precedence and
  `PORTFOLIO_RULES_SEQUENTIAL_WARNING` (`execution/output.py:83-88`) become obsolete at ADIM 19;
  `COMPOSITION_CURVE_WARNING` (`portfolio.py:67`) becomes false at ADIM 20 and must be removed from
  *new* results while remaining readable on old ones.
- Checkpoint granularity changes from per-item to per-K-ticks (§11).

**Rejected / deferred, stated so nobody infers otherwise**

- Cross-margin and portfolio liquidation are **not** shipped (§9.5).
- NET netting semantics are **not** defined here (§9.4, GH #544).
- FX conversion stays out of scope (OD-5).
- Trading Signal / Trade Log execution stays out of scope (OD-6).
- `record_time_basis` semantics are not changed (A-1 / OD-1).
- Retention auto-purge, LLM generation and the Graphic View renderer remain out of scope as before.

**Risks**

| ID | Risk | Mitigation |
|---|---|---|
| R-1 | Manifest pins the live draft while naming a revision id (§10.2) | separate narrow PR before ADIM 20; add an assertion that the pinned config hash matches the named revision row |
| R-2 | DST fold/gap resolution is an accidental default (GH #559) and a merged axis makes it cross-item | close #559 before the axis spans mixed-zone sources |
| R-3 | Two pinned revisions declaring different `record_time_basis` merge as if identical | OD-1(a) blocker |
| R-4 | An ADIM 16 refactor that silently changes a single-item number | 46-digest invariance is the gate; no other assertion is trusted |
| R-5 | Lifting containment while OD-2/OD-3 are unanswered would re-introduce an undisclosed policy | ADIM 20 must not merge until every OD is recorded in the manifest as a versioned policy |

---

## 16. Stopping condition — discharged (2026-08-05)

This ADR is **Accepted**. §13's decisions are recorded as resolutions in the §13.1 amendment
table, and §12's boundaries are corrected to match what shipped.

**The approval gate was not honoured in order, and that is recorded rather than tidied away.**
The condition read: *implementation does not begin until the PO / maintainer approves it.*
ADIM 15, 17, 19 and the ADIM 20 oracle suite all landed while the status was still `Proposed`
(PRs #566, #573, #575, #581, #583). Approval arrived at ADIM 18. What that cost is knowable and
small — every one of those slices was contained, none was reachable from production, and the
containment guards are what made the cost small rather than luck. What it *would* have cost had
a slice touched `run_engine` is exactly the risk §15 R-4 names, so the gate is not a formality
and should hold for ADIM 20, which is the first slice that changes a shipped number.

This document is still not evidence that any part of the design is built. **What is built, on
this commit:** the six ADIM 15–19 primitives, and the ADIM 18 phase loop `run_portfolio` — with
no production caller. **What is not:** the worker call site (needs the participant described in
the §12 correction note), the OD-1/OD-2/OD-6 gates, and all of ADIM 20.
