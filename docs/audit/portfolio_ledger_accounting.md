<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# Shared portfolio ledger — accounting spec, fixtures and reconciliation

**Slice:** ADIM 17 — one shared ledger, one valuation snapshot, one capacity answer
**Code:** `backend/src/entropia/domain/backtest/execution/portfolio_ledger.py`
**Tests:** `backend/tests/unit/test_backtest_portfolio_ledger.py` (59 functions, 100 cases)
**Base:** `origin/main` @ `3a2aea9`, `ENGINE_VERSION = backtest-engine-v18-gap-adjusted-stop-fill`
**Policy:** `LEDGER_POLICY_VERSION = "portfolio-ledger-v1"`
**ADR:** 0002 §7 (shared ledger + snapshot), §8.2 P6b (the cap layers), §9 (solvency)

---

## 1. What this document is

The ledger is the one place in the programme where money is added up. This file states the
arithmetic it implements, **where each rule comes from in canon**, the hand-computed fixtures
that pin it, and — separately — what each figure was *reconciled against* on the shipped side.

It is deliberately three things and not one:

* a **spec**, so §2's formulas can be checked against doc 13 / Master Ref without reading code;
* a **fixture record**, so §3's numbers can be recomputed by hand;
* a **reconciliation report**, so §4 says which shipped surface each claim was compared with
  and — where nothing could be compared — says so.

It is *not* evidence that shared mode runs. Shared allocation stays contained
(`SHARED_ALLOCATION_STATUS = "future_dev"`), nothing in production imports this module, and
the rollback is still "revert the slice".

---

## 2. The arithmetic

### 2.1 Capital structure — resolved once, never re-derived

```
P0 = quantize(initial_capital, 0.01)          # the shared pool
r  = max(reserve_cash_percent, 0) / 100
R0 = P0 * r                                   # FIXED NOMINAL — never re-applied to E(t)
A0 = max(0, P0 - R0)                          # allocatable initial pool
Ci0 = A0 * wi / 100                           # item i's initial sleeve
U0 = A0 - sum(Ci0)                            # unallocated cash — never auto-borrowed
```

Source: doc 13 §8.3 and Master Ref Modül 11 §5.1, character for character. The `max(…, 0)` on
`r` and the `quantize` on `P0` are the shipped engine prologue's own
(`engine.py:838-841`, `resolve_allocation_execution`), kept so the ledger's `A0` is the number
the engine already computes.

Refused at construction (`InvalidCapitalPlanError`), because each is a canonical Ready-Check
blocker (doc 13 §10.1, Modül 11 §7.1) and a bypassed readiness state must not seed a pool that
does not add up: `P0 <= 0`; any `wi < 0`; `sum(wi) > 100`.

### 2.2 Equity — realized only

```
E(t) = P0 + realized_pnl(t) - fees(t) - funding(t) - other_realized_costs(t)
```

Source: doc 13 §8.3, Modül 11 §5.2. **Unrealized movement is absent from `E(t)` by canon**, so
a mark never enters it (§2.5).

`A(t) = max(0, E(t) - R0)`; `Ci(t) = A(t) * wi / 100` under `COMPOUND_PORTFOLIO_EQUITY`;
`Ci = Ci0` under `FIXED_INITIAL_PORTFOLIO_CAPITAL` (Modül 11 §5.3 — *"Ci_fixed zamanla
degismez"*). Both modes book PnL, fees and funding; fixed only refuses to let them move the
sizing base.

### 2.3 The identity is exact by construction

Every booking applies its delta with the **shipped incremental quantization** —
`equity = quantize(equity + delta, 0.01)` (`booking.py:96`, `engine.py:1953`) — and then files
**the delta that was actually applied** into its bucket. Therefore

```
E(t) == P0 + realized - fees - funding - other      # to the cent, at every point
```

is true by construction rather than approximately. Accumulating the buckets independently and
subtracting at read time is **not** equivalent: rounding is translation-invariant across an
exact multiple of the quantum only when the half-even tie-break agrees. Worked counter-example
(pinned by `test_the_bucket_records_the_delta_that_was_actually_applied`):

| step | value |
|---|---|
| equity after a 0.01 gain | `10000.01` |
| a `0.005` fee, applied to the SUM | `quantize(10000.005) = 10000.00` → **0.01 applied** |
| the same fee rounded on its OWN | `quantize(0.005) = 0.00` → **0.00 recorded** |
| independent accumulation would report | equity `10000.00`, fees `0.00` → identity off by a cent |

### 2.4 What is a cost, and what is already in the price

| Cost | Where it lives | Ledger line |
|---|---|---|
| spread (`half_spread`) | folded into the fill price by `costs._effective_fill` | **none** — already inside `gross_pnl` |
| slippage | same | **none** — already inside `gross_pnl` |
| commission (round trip) | `booking.close_position`'s `commission_lot` | `fees` |
| commission (scale / stack / remainder lot) | `booking.py:222`, `engine.py:2909`/`:3095` | `fees` |
| funding / carry | `costs.due_funding_charges`, signed | `funding` |
| anything else realized | doc 13 §8.3's fourth term | `other_costs` |

Booking spread or slippage a second time would double-count every fill. Pinned by
`test_spread_and_slippage_are_inside_the_price_and_are_never_booked_again`, which reads the
prices off a real `run_engine` replay rather than restating them.

### 2.5 Exposure and marking

* **committed capital == entry-basis notional** (`quantize(entry_price * size, 0.01)`) — the
  shipped convention (`_Position.entry_notional`, `sizing._cap_to_sleeve` caps *notional*
  against the sleeve). Canon defines no maintenance-margin formula and Master Ref §10.2
  delegates `leverage_mode=cross` to a portfolio risk model that does not exist, so **no
  margin model is introduced here** (ADR §9.5).
* `gross_exposure = Σ notional` — what the caps and the solvency limit read.
* `net_exposure = Σ signed notional` — a **measurement**. Nothing offsets a long against a
  short: no cap, no headroom and no solvency figure is computed from it. Netting semantics are
  undefined in canon (ADR §9.4, GH #544), and computing capacity from a net figure would ship
  `NET` by accident. Pinned by `test_net_exposure_is_measured_and_offsets_nothing`.
* **marking** happens at the tick's one valuation point and is reported *beside* `E(t)`. A
  position with no usable mark makes `unrealized_pnl` and both `marked_*` figures `None` and
  lands in `unmarked_items` — never valued at zero. Whether a stale price may mark a position,
  and for how long, is **OD-2 and unanswered**: `MarkPrice` records the authority and the
  staleness the clock measured and chooses no policy.

### 2.6 Capacity — three caps and one reject

```
allowed = min(desired, remaining_sleeve, item_risk_limit, exposure_headroom)   # CLAMP
then:  granted_notional > ledger_solvency_limit  =>  REJECT the whole order    # NEVER trim
```

| Layer | Headroom | Outcome | Reason token | Source |
|---|---|---|---|---|
| `remaining_sleeve` | `max(0, Ci(t) - deployed_i)` | cap, or reject at 0 | `sleeve_zero_capacity` * | doc 13 §8.3; ADR §7 |
| `max_position_notional` | supplied by the caller | cap, or reject at 0 | `max_position_notional_exceeded` | M11 §6.1 layer 3 |
| `max_total_exposure` | `max(0, cap - gross_exposure)` | cap, or reject at 0 | `portfolio_max_total_exposure` * | doc 13 §8.4 |
| `ledger_solvency` | `max(0, A(t) - gross_exposure)` | **reject only** | `ledger_insolvent` | M11 §5.3 |

The sleeve headroom is read from the **snapshot** and the solvency headroom from the **ledger**,
so while the ledger is frozen the snapshot must be the one it published — a snapshot from
another tick is refused (`MismatchedSnapshotError`), never averaged across two valuation
points.

\* the shipped engine's own decision-trace tokens (`sizing.blocked_reason:344`,
`engine.py:1474`), reused verbatim so a rejection reads in one vocabulary. The four tokens this
layer *adds* are closed in `LEDGER_LAYER_REASONS`.

`item_risk_limit` is honoured **only when the caller supplies one**: its authority is Strategy
Details (applied at P6a by `sizing._clamp_to_limits`), so an omitted limit is absent from the
decision's `limits` map rather than a fabricated infinity.

Solvency may never cap, because a trimmed order *is* the partial fill Modül 11 §5.3 forbids:
*"Ledger insolvency veya gerekli teminat yetersizse engine orderi reddeder, kismi fill veya
sessiz borrow yapmaz."* Which of several jointly-insolvent intents is rejected is **OD-3** and
is not decided here.

### 2.7 Rounding — the versioned part

| Knob | Value | Note |
|---|---|---|
| money quantum | `0.01` | `execution.constants._MONEY` — the engine's own step |
| quantity quantum | `1e-8` | `execution.constants._QTY` — `_cap_to_sleeve`'s step |
| rounding | `ROUND_HALF_EVEN` | pinned explicitly rather than inherited from the ambient `decimal` context; identical to every recorded golden digest, which was produced under the default |
| sleeve arithmetic | **unquantized** | `A(t) * wi / 100` is left exact; only published money figures quantize |

`ROUND_HALF_UP` in `allocation/rules.py:51` is **display** rounding at the last step of the
preview, over the same unrounded arithmetic — not a second policy.

### 2.8 Phase discipline is structural

`publish_snapshot(t)` **freezes** the ledger; every booking and position mutation raises
`LedgerFrozenError` until `begin_apply(t)`. ADR §8.1 requires that nothing between `PV` and
`P7` writes; making it an exception rather than a convention means "every item read the same
`E(t)`" cannot be violated by a caller getting the phase order wrong. `begin_apply` refuses a
different instant than the one that published.

---

## 3. Manual oracle fixtures

Every number below was computed by hand from §2 and written into the test as a literal.

### 3.1 The canonical split — doc 13 §14 test 10

`P0 = 10,000`, `r = 10%`, shares `40 / 35 / 15`:

| Figure | Value |
|---|---|
| `R0` | `1,000.00` |
| `A0` | `9,000.00` |
| `Ci0` (40 / 35 / 15) | `3,600` / `3,150` / `1,350` |
| `U0` | `900` |

Modül 11 §5.4 states the same pool at `40 / 30 / 20` → `3,600` / `2,700` / `1,800`, `U0 = 900`.
Both are pinned; two independent statements of one rule.

### 3.2 Compound vs fixed — Modül 11 §5.4

At `E(t) = 10,500`: `R0` stays `1,000`, `A(t) = 9,500`, and the 40% item's sleeve becomes
`3,800`. Under fixed it stays `3,600` at every equity tested (`10,500`, `8,000`, `10,000`, `0`).

### 3.3 The reserve across a drawdown

| `E(t)` | `A(t)` |
|---|---|
| `10,000` | `9,000` |
| `5,000` | `4,000` |
| `1,000` | `0` |
| `500` | `0` (floored, never negative) |

A ledger that re-applied 10% would hold back only `500` at an equity of `5,000` — freeing
capital exactly when the portfolio can least afford it.

### 3.4 Two items competing for one pool, no directional conflict

`P0 = 10,000`, `r = 0` → `A0 = 10,000`; shares `60 / 40` → sleeves `6,000` / `4,000`; **fixed**
mode; **both items long**, so nothing here is a conflict decision.

Item B loses `6,000` → `A(t) = 4,000`. Item A then asks for `50 @ 100 = 5,000`:

| Layer | Headroom | Verdict |
|---|---|---|
| `remaining_sleeve` | `6,000` | fits |
| `ledger_solvency` | `4,000` | **short by 1,000 → REJECT the whole order** |

A `4,000` partial fill would be exactly the silent trim canon forbids. Item B's own `10 @ 100`
is admitted in the same snapshot. Sibling sleeves and `U` are unchanged by the rejection
(doc 13 §8.4 step 6 — a blocked item's share is never transferred).

### 3.5 The solvency edge in fixed mode

`P0 = 10,000`, `r = 10%`, shares `40 / 35`, fixed. A `-8,500` loss leaves `A(t) = 500` while
`item_a`'s sleeve still reads `3,600`. `30 @ 100` is rejected with `ledger_insolvent`; the
decision's `limits` records **both** figures (`remaining_sleeve = 3,600`,
`ledger_solvency = 500.00`) so the trace shows the sleeve fitting and the pool not.

---

## 4. Reconciliation report

Each row is a claim, the shipped surface it was compared against, and the result. "Compared"
means the test calls the shipped code and asserts equality — not that the numbers look alike.

| # | Ledger claim | Reconciled against | Result |
|---|---|---|---|
| R1 | `R0` / `A0` / `Ci0` / `U0` for doc 13 §14 test 10 | `allocation.rules.validate_allocation` → `DerivedAmounts` (the preview the **user** is shown) | **agree to the cent** — Modül 11 §5.1 requires preview and engine to agree, and nothing enforced it before |
| R2 | `Ci(t)` for one item, compound **and** fixed | `sizing.sleeve_capital(_RunConfig, equity)` — the shipped per-item sleeve | **identical** across 2 modes × 3 shares (incl. `0`) × 4 equities (incl. one under the reserve) = 24 cases |
| R3 | granted units after the sleeve cap | `sizing._cap_to_sleeve(desired, sleeve, price)` | **identical** across 3 prices × 3 desired sizes |
| R4 | the whole single-item chain | a real `run_engine` replay of the shipped oracle `test_the_sleeve_caps_a_size_the_strategy_asked_for` | **identical**: `44.11764706` units, `88.24` PnL, `100,088.24` final book |
| R5 | equity progression under mixed sub-cent deltas | a hand-written copy of the shipped `quantize(equity + delta, 0.01)` rule | **identical** step for step over 6 deltas |
| R6 | a zero-share item fills nothing | shipped oracle `test_an_unallocated_item_gets_no_sleeve_and_therefore_no_fill` | **same refusal** (`sleeve_zero_capacity`), book unchanged at `P0` |
| R7 | spread/slippage not double-booked | engine's own emitted `entry_price`/`exit_price` at 1% slippage (`103.02` / `102.96`) | equity delta **equals** `TradeRow.pnl`; all three cost lines stay `0` |

**Not reconcilable, and stated as such:**

| Claim | Why there is nothing to compare with |
|---|---|
| multi-item `E(t)` and cross-item sleeve interaction | the shipped engine has **no** shared ledger — each item runs its own `_Ledger` seeded from the full pool. There is no second implementation to agree with; §3.4/§3.5 are hand-computed only. |
| `net_exposure` | nothing shipped measures it; `execution.rules.prior_exposure_at` sums *prior* items' peak notional on a forward-only basis, which is a different quantity and is retired at ADIM 19. |
| marked (unrealized) figures | the shipped curve records realized closes only; there is no shipped mark-to-market figure at all. |
| the portfolio equity curve's cardinality | `state.EquityPoint` is appended per trade close (`booking.py:137`); the portfolio curve appends per **tick at which `E(t)` moved**. These are different series by design (ADR §7) and are **not** expected to match. |

---

## 5. Mutation record

A passing suite is not evidence on its own — the ADIM 15 record makes that a standing
requirement for the slices that introduce new behaviour. Twelve mutations were applied to the
module, one at a time, and the suite re-run (M11 was added with the guard it attacks):

| # | Mutation | Result |
|---|---|---|
| M1 | `available_capital` ignores the reserve | caught |
| M2 | fixed mode compounds anyway | caught |
| M3 | quantize the **delta** instead of the sum | caught |
| M4 | solvency trims instead of rejecting | caught |
| M5 | `fees` accumulated independently of the applied delta | caught |
| M6 | the no-borrow guard bounds the standing total, not the increase | **survived the first pass** |
| M7 | an unmarkable position valued at zero | caught |
| M8 | the deployed map covers only open positions | caught |
| M9 | `publish_snapshot` does not freeze | caught |
| M10 | `R0` re-derived from live equity | caught |
| M11 | a snapshot from another tick accepted by `resolve_capacity` | caught |
| M12 | an open position reversed in place instead of closed first | caught |

**M6 is the honest part.** Bounding the *total* rather than the *increase* still passed every
test in the first suite, because nothing exercised a resize of a position the pool could no
longer afford to open from scratch — which is exactly the shape doc 13 §8.3's no-force-rebalance
rule protects. `test_only_the_increase_in_committed_capital_is_checked_against_the_pool` was
written afterwards (a scale-in that exactly consumes the headroom, and a **reduction** while
underwater), and M6 is caught. Second pass: **12/12 caught, 0 survivors.**

---

## 6. Honest boundaries

* **Contained.** Nothing in production imports the module; `run_engine` keeps its signature and
  its semantics; no golden digest, `ENGINE_VERSION`, `execution_key`, manifest field, migration
  or OpenAPI operation moves. Rollback is `git revert`.
* **No phase loop.** `run_portfolio` and the per-tick ordering are ADIM 18. This slice is the
  state that loop mutates plus the arithmetic it mutates it with.
* **No arbitration.** Which of several jointly-insolvent intents is rejected (**OD-3**) and any
  cross-item conflict / `NET` semantics (ADR §9.4, GH #544) are out of scope by instruction.
* **No mark policy.** **OD-2** is open; the ledger records where a price came from and how stale
  it was, and refuses to invent a `stale_after` bound.
* **A reversal is a close then an open.** `set_position` refuses an in-place direction flip: netting the new notional against the old would check only the difference against the pool, when a reversal releases one commitment and takes another. Found by review, not by a failing test — the guard and `M12` were added together.
* **No margin model.** `leverage_mode=cross` stays `canonical_gap` (ADR §9.5). Committed capital
  is entry-basis notional and nothing else.
* **`PortfolioEquityPoint` is a new type**, not `state.EquityPoint`. ADR §7 sketched reusing the
  shipped one; its `exposure` field means *the closed lot's* notional over the equity before the
  close, which is not what a portfolio curve records. Reusing it would have kept the field names
  while silently redefining two of them. The adapter, if one is wanted, belongs to ADIM 20.
* **ADR 0002 is still `Proposed`** and its §16 conditions implementation on PO approval. No
  approval is recorded in the repository; ADIM 15, 16 and this slice all landed without one.
