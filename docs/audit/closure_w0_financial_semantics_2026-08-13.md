<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# P-A2 — Financial semantics, forensic re-verify (#550 / #551 / #552)

**READ-ONLY audit. No production code, no test expectation, no `ENGINE_VERSION`, no issue
state was changed.** Every verdict below is a number this session produced by running the
shipped engine on this base, not a restatement of an issue body.

## Base

| | |
|---|---|
| Base SHA | `0d8bf8f7134d86d77a7eee10023dadd3d80aab0d` |
| Expected by the shared agreement | `31ed27dfc1f3bf7448b0e03c7c732d22d8b758c4` |
| Delta | **one commit ahead** — `0d8bf8f` *"docs: name the PR behind every landed slice heading (#702)"*, `docs/` only. No `backend/src`, no `frontend/src`, no test change. The re-measurements below are therefore taken on `0d8bf8f` and are unaffected by the delta. |
| `alembic head` | `0043_i08_registry_strategy_fks` (untouched) |
| `ENGINE_VERSION` | `backtest-engine-v18-gap-adjusted-stop-fill` (untouched) |
| Issue state at audit time | #550 `open` (`reopened`), #551 `open` (`reopened`), #552 `open` (`reopened`) |

**Issue state was not used as evidence.** Two of the three issues turned out to be right in
substance; one carries a load-bearing claim that does **not** reproduce (§2, claim (b)).

## Executive verdict

| Issue | Verdict | Live on this base? |
|---|---|---|
| **#550** — sizing unit vs percent | **CONFIRMED, all three fields** | **YES** — divergence is unbounded in instrument price (measured 612× at a BTC-like price) |
| **#551** — zero-size phantom trade | **CONFIRMED in part, REFUTED in part** | **YES** for the phantom trade + metric pollution (4 paths, not 3). **NO** for the cross-item leakage the issue calls "the load-bearing one" — it is filtered upstream. |
| **#552** — commission on partial closes | **CONFIRMED, and worse than reported** | **YES** — three separate divergences, only one of which the issue names |

**Live defect count: 3 issues → 7 distinct reproduced defects** (§Matrix). **PO decisions
pending: 6.**

---

## §1 — #550: `base_position_size` / `min` / `max` — canonical vs UI vs schema vs engine

### 1.1 The four-layer table

| Layer | Source | `base_position_size` means | `min` / `max` position size mean |
|---|---|---|---|
| **Canonical (Master Ref §10.1, line 7552)** | "Base Position Size ⓘ \| **Position Size %** \| **Resolved capitalın yüzdesi.** Pozitif olmalı" | **percent of resolved capital** | §10.2 names **Max Single Position** = "Tek position için **nominal/sermaye yüzdesi** limiti" and **Max Total Exposure**. **There is no minimum.** |
| **Canonical (doc 02 §6, line 1015 / 1030 / 1039)** | `sizing.base_position_size.percent` **or typed unit**; "required >0" | percent (with an explicit "or typed unit" escape hatch) | `limits.max_single_position_percent` (>0), `limits.max_total_exposure_percent` (>0, >= max single) |
| **V18 mockup (`index_...v18.html:5696`, :5706, :5707)** | `<label>Position Size</label> … <span class="inline-unit">%</span>` | **percent** | **Max Single Position `%`** and **Max Total Exposure `%`**. **No Min Position Size field exists in the mockup.** |
| **Shipped frontend** | `StrategyConfigForm.tsx:591-592` — `label="Base position size" unit="%"`, rendered as a literal `%` chip beside the input (`TextField`, :111-115) | **percent** — and the shipped ⓘ panel (`lib/strategyForm.ts:85`) states it verbatim: *"Equity 10.000 USD ve Position Size %10 ise ilk pozisyon **nominal olarak 1.000 USD** üzerinden oluşturulur"* | `:675-676` `label="Min position size" unit="%"`; `:681-682` `label="Max position size" unit="%"` (panel `maxSinglePosition`: *"tek pozisyon equity'nin %25'inden büyük açılamaz"*) |
| **API / domain schema** | `domain/strategy/config.py:711` — `base_position_size: Decimal \| None`. **No unit, no `gt=0`, no `le=100`.** Only a presence validator (:742). | **untyped bare number** | `:770-771` `min_position_size` / `max_position_size`: `Decimal \| None`, no unit, no constraint, **no ordering check** |
| **Engine** | `execution/sizing.py:216` — `return Decimal(sizing.base_position_size)` | **raw quantity of units (contracts/coins)** — no capital, no price, no `/100` on this path | `sizing.py:186-187` + the `_clamp_to_limits` docstring (:182-183): *"Caps are in the **same UNITS as the size (contracts/coins)**, applied verbatim (unquantized)"* → **units** |

Five sources say percent. One — the engine — says units, and the schema is silent so the
disagreement is never caught at the boundary.

**Corroborating negative control inside the same module:** `risk_percentage_per_trade` is
`unit="%"` in the UI *and* a real percent in the engine (`sizing.py:221`,
`usable_equity * risk% / _HUNDRED`). The percent reading is already implemented here; these
three fields are the outliers, not the norm. The codebase also *names* its percent fields —
`max_total_exposure_percent`, `reserve_percent`, `item_share_percent`,
`risk_percentage_per_trade` — and these three carry no such suffix.

### 1.2 Numeric proof (measured, this session, `run_engine` on the oracle geometry)

Equity 10 000. User types **10** into the field the shipped UI labels `%`.

| Case | Instrument price | Shipped `size` | Shipped notional | Shipped notional / equity | Canonical `size` | Canonical notional | Canonical / equity | Ratio |
|---|---|---|---|---|---|---|---|---|
| **A** | 102 | `10` units | **1 020.00** | 10.20 % | `9.80392157` | 1 000.00 | 10.00 % | 1.02× |
| **B** | 61 200 | `10` units | **612 000.00** | **6 120 %** | `0.01633987` | 1 000.00 | 10.00 % | **612×** |

Case B's run finishes at `final_equity = 22 240.00` on a 10 000 account after two bars — a
+122 % result produced entirely by the unit misreading. **The divergence is unbounded in
instrument price**, and nothing downstream rescues it: the shipped `PositionSizeLimits` caps
are expressed in the *same contested units*, and there is **no strategy-level Max Total
Exposure field at all** (see 1.4).

Max-position-size case (same geometry, `base=50`, `max_position_size=25`, price 102):
shipped clamps to **25 units = 2 550.00 notional = 25.50 % of equity**; the canonical
`max_single_position_percent = 25` would give **24.50980392 units = 2 500.00 = 25.00 %**.
The near-match here is coincidental — it exists only because the fixture's price is ≈100.

### 1.3 The leverage order the canonical requires, and the step that is missing

Canonical chain (Master Ref §10.1 + §10.2 + the ⓘ panel's *"kaldıraç etkisi **ayrıca**
uygulanır"*):

```
resolved capital  ──(× pct / 100)──▶  notional  ──(÷ entry_price)──▶  units  ──(× leverage)──▶  final units
                                                                            ──(× strength)──▶
                                                          ──(clamp / block on % caps)──▶
```

Shipped chain (`sizing.py::_position_size`, :262-265):

```
base value (verbatim)  ──(× leverage)──▶  ──(× strength)──▶  ──(clamp to UNIT caps)──▶ final units
```

**Missing steps: the `× pct / 100` and the `÷ entry_price`.** The engine jumps straight from
the stored number to units. The leverage/strength multiplications are in the right *place*
(after the base, before the caps) — they are simply applied to a wrong base. Two further
order deviations:

* **the caps are compared in units, not against a percent-of-capital basis** — so the cap is
  wrong by the same unbounded factor as the base;
* **Master Ref §10.2 says the over-limit outcome is "clamp değil blocker veya explicit cap
  policy"** — the shipped `_clamp_to_limits` **silently clamps** (`sizing.py:191-193`). No
  blocker, no disclosed cap policy. This is a second, independent §10.2 divergence that
  survives even if the unit question is answered.

### 1.4 Two shipped-field findings this audit adds to #550

**(i) `min_position_size` has no canonical counterpart, and it *increases* size.**
Master Ref §10.2 names exactly two limits (Max Single Position, Max Total Exposure); the v18
mockup renders exactly those two; doc 02 §6 lists exactly those two. `min_position_size` is
present only in the shipped schema and shipped UI, and `sizing.py:192-193` pushes a computed
size **UP** to it. Pinned today by
`test_oracle_sizing.py::test_a_min_limit_pushes_the_size_up` (50 requested → **80** booked,
pnl 160.00). A floor that enlarges a position beyond what the strategy's own method asked for
is a risk-increasing behaviour with no canonical basis.

**(ii) Strategy-level Max Total Exposure does not exist.** `max_total_exposure_percent` is
implemented **only** at the allocation-plan / portfolio level (`models/allocation.py:91`,
`commands/allocation_plan.py`) — correctly as a percent. Doc 02 §6 puts
`limits.max_total_exposure_percent` on the **strategy** config; `PositionSizeLimits`
(`config.py:769-771`) has no such field. The shipped UI even carries the ⓘ **panel** for it
(`lib/strategyForm.ts:101`, "Max Total Exposure") **attached to no field** — the panel is
dead text. So the one canonical control that would bound the Case-B blow-up is absent from
the strategy layer.

### §1 verdict

**#550 CONFIRMED and live**, on all three fields it names, plus two adjacent findings the
issue does not name (1.4). The issue's own worked table is reproduced and extended; its claim
that "pinned Results are safe — no equality gate compares a stored version against the current
constant" is **independently confirmed** here (§5).

---

## §2 — #551: the zero-size phantom trade

### 2.1 The guard's real condition (read, not guessed)

`domain/backtest/engine.py:813`

```python
alloc_on = allocation is not None
```

`domain/backtest/engine.py:1462` (the issue cites `:1457` — **line drift, same statement**)

```python
size = _planned_size(direction, fill_raw, strength)
if alloc_on and size <= _ZERO:
    return None
```

**The guard is bound to allocation mode.** `alloc_on` is true *iff* the caller passed an
`AllocationExecution`. In independent mode — the default — a non-positive size falls through
and opens a position. This is not incidental: `_open`'s own docstring (`engine.py:1434-1436`)
states it as an intentional invariant — *"Independent mode books even a bust-equity 0-size
fill (preserving the risk-based no-phantom-profit invariant)"*. That sentence matters for the
fix (§2.4).

### 2.2 The eight scenarios, measured one by one

Harness: oracle geometry (20 flat bars at 100, long entry at 102, exit at 104), zero costs
unless stated. Independent = no `allocation`; Allocation = `P0=100 000, r=10 %, wi=5 %`.

| # | Scenario | Entry event | `size` | trades | `total_trades` | `win_rate` | zero-notional interval? | **Live?** | Site |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **independent + `base_position_size = 0`** | `entry_fill` | `0` | 1 | **1** | **0.0000** | **yes** (`peak_notional 0.00`) | **YES** | `engine.py:1462` |
| 2 | **allocation + `base_position_size = 0`** | `entry_blocked` (`sleeve_zero_capacity`) | — | 0 | 0 | `None` | no | **NO** — correct | `engine.py:1462` |
| 3 | **Kelly zero edge** (`W=0.5, R=1`), independent | `entry_fill` | `0E-8` | 1 | **1** | **0.0000** | **yes** | **YES** | `sizing.py:102` → `:227` |
| 3b | Kelly zero edge, allocation | `entry_blocked` (`sleeve_zero_capacity`) | — | 0 | 0 | `None` | no | **NO** — correct | — |
| 4 | **`min=80` > `max=20`**, independent | `entry_fill` | `0` | 1 | **1** | **0.0000** | **yes** | **YES** | `sizing.py:188-189` |
| 4b | `min > max`, allocation | `entry_blocked` (`sleeve_zero_capacity`) | — | 0 | 0 | `None` | no | **NO** — correct | — |
| 5 | **`max_position_size = 0`**, independent | `entry_fill` | `0` | 1 | **1** | **0.0000** | **yes** | **YES** — *path the issue does not list* | `sizing.py:190-191` |
| 6 | **`base_position_size = -5`**, independent | `entry_fill` | **`-5`** | 1 | 1 | 0.0000 | interval `peak_notional = **-510.00**` | **YES — worse than zero** (§2.3) | `sizing.py:216` + `:184` |

Supplementary measurements on the same base:

* **zero-size trade pollutes the money too.** Scenario 1 re-run with `commission = 7`:
  the 0-unit position books `pnl = **-14.00**`, `final_equity = **9 986.00**`. A position that
  never carried risk pays a **full round trip**. (This is #551 and #552 compounding.)
* **`risk_based_sizing` IS reachable, contrary to the issue.** The issue says it "cannot reach
  it: `stop_loss_point` is schema-guarded `gt=0`". True for the stop, but the *equity* leg is
  not guarded: measured `_position_size(risk_based, equity=0) = 0E-8` and
  `(equity=-500) = 0E-8` — `sizing.py:217` clamps equity to `max(equity, 0)` and then divides
  it. Kelly behaves identically. **So the reachable-path count is 4 method-paths + bust
  equity, not 3.**
* **No gate upstream stops any of these.** `sizing_is_modelled()` returns **True** for
  `base=0`, `base=-5`, `min>max` and the zero-edge Kelly config, so Ready Check's
  `STRATEGY_SIZING_UNSUPPORTED` blocker never fires (`readiness/validators.py:453`). The
  schema accepts `base_position_size = "-5"` and `"0"`, and accepts `min=80, max=20` and
  `min=-10, max=-1` — measured directly against the Pydantic models.

### 2.3 New finding: a NEGATIVE size is booked, and its PnL sign is inverted

`_raw_position_size` returns the stored value **verbatim** for the base branch
(`sizing.py:216`), and `_clamp_to_limits` **short-circuits on non-positive input**
(`sizing.py:184`: `if limits is None or size <= _ZERO: return size`) — a deliberate choice, so
a `min` floor cannot resurrect the 0 sentinel, but it also means a **negative** size passes
through untouched. Measured: `base_position_size = "-5"` opens a `-5`-unit long and books
`pnl = **-10.00**` on a bar that moved **+2.00 in the position's favour**. The sign of the
result is inverted.

`sizing.py`'s own docstring (:209-212) already names this as the hazard it guards against —
*"a bust account yields size 0, never a negative size — a negative size would invert the PnL
sign of every subsequent trade (review CRITICAL)"* — but that guard is applied to **equity**
only, never to the explicitly-stored base size. Master Ref §10.1 says *"Pozitif olmalı"* and
doc 02 says *"required >0"*; the schema enforces neither.

**This is a strictly more severe variant of #551 and is not in the issue text.**

### 2.4 REFUTED: the cross-item leakage (#551 claim (b))

The issue calls this *"the load-bearing one"*:

> A full close appends to `led.position_intervals`, and the portfolio-rules gate consumes
> those records by **direction alone** (`execution/rules.py:69`) … So a phantom 0-notional
> position can satisfy `BLOCK_OPPOSITE` and **block a later-pinned item's genuine entry**.

**This does not reproduce on this base.** The reading of `rules.py:69` is correct in
isolation, but it looks at the wrong end of the pipeline. `conflicts_with_prior` iterates
`rules.prior_intervals`, and the **only** producer of `PriorItemInterval` in the tree is
`engine.py::build_prior_intervals` (verified by grep; the worker's single call site is
`application/jobs/backtest_engine.py:334`), which drops non-positive notionals **before** the
gate ever sees them:

```python
notional = _safe_decimal(iv.get("peak_notional"))
if notional is None or notional <= _ZERO:
    continue                                    # engine.py:722-724
```

Measured end-to-end through the real pipeline, **with a positive control**:

| Item | `EngineOutput.position_intervals` | after `build_prior_intervals` | `conflicts_with_prior(dir="short")` |
|---|---|---|---|
| **phantom** (`base_position_size = 0`) | `['0.00']` | **0 intervals** | **`False`** — no block |
| **real** (`base_position_size = 50`) | `['5100.00']` | 1 interval | `True` — blocks, as designed |

The real item blocking proves the probe is sensitive; the phantom item not blocking is
therefore a fact about the code, not about the probe. The behaviour is additionally pinned by
an existing test:
`tests/unit/test_backtest_portfolio_rules.py::test_build_prior_intervals_fails_closed_on_bad_bounds_and_drops_zero_notional`.

**Consequence for planning:** #551's severity argument rests on this claim, and the claim is
false. What remains is real but is a **metrics/artifact** defect (trade count, win-rate
denominator, average trade, expectancy, a zero-notional row in the persisted
`position_intervals`) plus the **money** leak when commission > 0 — not a composition-level
result-corrupting one. **The issue body should be corrected before this is scheduled.** Note
also that the negative-size case (§2.3) is dropped by the same filter, so a **-510.00**
notional window silently vanishes from cross-item constraints rather than corrupting them.

### 2.5 The fix the issue proposes conflicts with a documented invariant

#551's minimum fix is `if size <= _ZERO: return None` — dropping `alloc_on`. That would also
suppress the **bust-equity** fill, which `_open`'s docstring (`engine.py:1435-1436`) calls a
deliberate invariant: *"Independent mode books even a bust-equity 0-size fill (preserving the
risk-based no-phantom-profit invariant)."* Suppressing it is very likely correct, but it is a
**behaviour decision about a documented invariant**, not a two-word patch. → PO item **PO-4**.

### §2 verdict

**#551 CONFIRMED for the phantom trade and metric pollution — on 4 method paths plus bust
equity (issue says 3) — plus one unreported and more severe negative-size variant.
REFUTED for the cross-item leakage claim (b), with a positive control.**

---

## §3 — #552: commission on partial closes

### 3.1 Five sources side by side

| # | Source | What it says |
|---|---|---|
| 1 | **Canonical — Master Ref line 3110** | "Commission rule \| Strategy/Backtest config \| **Notional üzerinden bps bazlı** işlem komisyonu" — a **basis-point rate on notional** |
| 1b | **Canonical — Master Ref line 7513 (§ partial exit)** | "Close 25/50/75% gibi eylemler mevcut miktarın yüzdesi üzerinden deterministik hesaplanır. Rounding policy, instrument quantity incrementi ve **komisyon dağılımı engine manifestinde açık olmalıdır**." — canon **prescribes no split formula**; it requires the split to be **published in the manifest** |
| 1c | **Canonical — Master Ref line 7425** | "Commission \| Sayısal giriş. \| **Birim/para formatı konfigürasyonla açık olmalı**; boşsa policy default değil, **manifestte resolved default** taşınmalıdır." |
| 2 | **`booking.py:83-84` DOCSTRING** | "Commission is charged proportional to the fraction so **N partial lots summing to the whole position pay exactly one round-trip**." |
| 3 | **`booking.py:93` CODE** | `commission_lot = costs.commission * 2 if is_full else costs.commission * 2 * fraction` — and `booking.py:221-222` (extra-fill / partial-fill top-up) charges `costs.commission` **one-sided**; `engine.py:2952` and `engine.py:3129-3133` charge one-sided at stack-tranche and scale-layer fill time |
| 4 | **API / DB schema** | `config.py:313` — `commission: Decimal \| None = Field(default=None, description="**Per-trade fee**")`. A **flat amount per fill**, not a rate, not a bps figure, **no currency/unit field**. `costs.py:129` reads it as `per_fill_commission`. |
| 5 | **Oracle test** | `test_oracle_position_lifecycle.py::test_a_partial_lot_pays_commission_in_proportion_but_the_final_close_pays_a_full_one` — asserts `[-65.60, -14.00]`, `final_equity 9920.40`, and its docstring **names the divergence and cites #552** |

### 3.2 Three divergences, not one

**(a) The one #552 reports — total fee scales with the number of partial lots.** Measured
directly against `close_position` (commission 7 ⇒ one round trip = 14.00; every lot closed at
the entry price so gross PnL is 0 and the equity delta *is* the fee):

| Split | lots | **measured total fee** | round trips | documented invariant | per-fill model would be |
|---|---|---|---|---|---|
| 1 lot (100 %) | 1 | **14.00** | 1.00 | 14.00 ✅ | 14.00 |
| 40 % + full remainder | 2 | **19.60** | 1.40 | 14.00 ❌ | 21.00 |
| 50 % + full remainder | 2 | **21.00** | 1.50 | 14.00 ❌ | 21.00 |
| 40 %, 40 %, full | 3 | **25.20** | 1.80 | 14.00 ❌ | 28.00 |
| 25 %, 25 %, 25 %, full | 4 | **24.50** | 1.75 | 14.00 ❌ | 35.00 |
| 9 × 10 %, full | 10 | **26.60** | 1.90 | 14.00 ❌ | 77.00 |

The docstring's invariant holds **only** for the 1-lot case. The cause is structural: the
final `is_full` close takes a **whole round trip regardless of the remaining size**, so the
total asymptotes to **2 round trips** as the number of partials grows. Closing a position in
3 parts costs **25.20** where closing it in 1 costs **14.00** — an **80 % higher** fee for the
same position, same entry, same exit price.

End-to-end confirmation through `run_engine` (commission 7, `move_stop_to_entry` aftermath):
`close_percentage=100` → `9822.00`; `=40` → **`9920.40`** (matches the pinned oracle exactly);
`=10` → `9969.60`.

**(b) NOT in the issue — the fee tracks the fraction PARAMETER, not the quantity closed.**
`close_size = pos.size * fraction` uses the **current** size (which shrinks each lot), but
`commission_lot` uses the same bare `fraction` against a full round trip. Measured, 50 units,
three 25 % lots:

| lot | `fraction` | **units actually closed** | **fee charged** |
|---|---|---|---|
| 1 | 0.25 | 12.50 | 3.50 |
| 2 | 0.25 | 9.3750 | 3.50 |
| 3 | 0.25 | 7.031250 | 3.50 |

Identical fees for 12.5, 9.375 and 7.03 units. The fee is **decoupled from quantity**, so it
cannot be reconciled with *any* per-notional or per-quantity cost model — including the one
canon prescribes.

**(c) NOT in the issue — the shipped cost model is flat-per-fill; canon says bps on notional.**
Master Ref line 3110 defines commission as a **bps rate on notional**. The shipped field is
`Decimal` "Per-trade fee", applied as a flat amount (`costs.py:134`, `booking.py:93`)
independent of size and price. Consequence measured in §2.2: a **0-unit** position pays the
same 14.00 as a 5 100-notional one. Under a bps-on-notional model both the phantom-trade fee
and divergence (b) disappear by construction. **Canon's unit/currency requirement (line 7425)
is also unmet** — the field carries no currency and the manifest publishes no resolved
default.

### 3.3 The three options and their financial consequence

**This is a PO decision. Nothing below is a recommendation** — the model is not derivable
from the shipped code, and canon prescribes only that the split be *published*, not what it is.

Reference position: 50 units in at 102 (5 100 notional), out at 102, `commission = 7`.

| | **A — per FILL** | **B — one round trip per POSITION** | **C — bps on notional (canon §8, line 3110)** |
|---|---|---|---|
| Rule | every fill (entry, each exit lot, each layer, each partial-fill top-up) pays `commission` | the position pays `commission × 2` total, apportioned across lots by **realized quantity** | `fee = notional_of_the_fill × bps / 10 000`, charged on every fill |
| 1 lot | 14.00 | 14.00 | e.g. 10 bps → 5.10 + 5.10 = **10.20** |
| 40 % + remainder | **21.00** | **14.00** | 5.10 + 2.04 + 3.06 = **10.20** |
| 3 partials + remainder | **35.00** | **14.00** | **10.20** |
| Scales with | number of **fills** | nothing (fixed per position) | **notional** |
| vs today (19.60 / 25.20) | **higher** | **lower** | depends entirely on the bps figure |
| 0-unit phantom position (§2) | still charged **14.00** | still charged **14.00** | **0.00** — self-correcting |
| Matches the shipped schema description? | **yes** (`"Per-trade fee"`) | no | no — needs a **new field** (`commission_bps`) + migration + UI |
| Matches canon? | no | no | **yes** (line 3110) |
| Matches today's docstring? | no | **yes** (:83) | no |
| Migration cost | none — reinterprets the same field | none | **schema + migration + UI + saved-revision transition gate** (a bare `7` cannot be mechanically read as bps) |
| Fixes divergence (b)? | **yes** | **yes** | **yes** |
| Direction of change vs today | over-charges more | under-charges | not comparable |

Today's behaviour is **none of the three** and sits between A and B, at a point that depends
on how the user happened to split their exits. **Whichever is chosen, canon line 7513 requires
the resulting `komisyon dağılımı` to be published in the engine manifest** — the manifest does
not carry it today (`manifest.py:224-237`: `execution_content` carries pinned item refs, not
resolved cost parameters). That publication requirement is independent of the choice.

### §3 verdict

**#552 CONFIRMED and live, with two divergences the issue does not name.** The reported
1.4-round-trip figure is reproduced exactly (19.60 on `commission = 7`), and the shape
generalises to 1.75–1.90 round trips at 3–10 lots.

---

## §4 — Oracle forensics: which tests pin canon, which pin shipped behaviour

`cd backend && uv run pytest -q --no-cov tests/unit/oracles/test_oracle_sizing.py tests/unit/oracles/test_oracle_position_lifecycle.py`
→ **`exit=0`, 22 passed in 0.39s.**

**All 22 pass, and that is not evidence that anything is fixed.** Four of them pass *because*
they pin the defect. Each was read at source, not inferred from its name.

| Test | Pins | Evidence in its own source |
|---|---|---|
| `test_base_position_size_is_taken_as_the_size` | **SHIPPED** | docstring: *"SPEC BOUNDARY … The shipped engine reads it as an absolute quantity of units. **This oracle pins the SHIPPED reading**; the divergence is filed as issue #550."* |
| `test_a_max_limit_pulls_the_size_down` | **SHIPPED** | 50 → 20 **units**; correct only under the unit reading |
| `test_a_min_limit_pushes_the_size_up` | **SHIPPED** | 50 → **80** units; the floor itself has no canonical counterpart (§1.4 i) |
| `test_a_min_above_max_window_books_a_zero_size_trade` | **SHIPPED** | docstring: *"**DIVERGENCE, pinned deliberately** … Filed as issue #551."* Asserts `total_trades == 1`. |
| `test_a_partial_lot_pays_commission_in_proportion_but_the_final_close_pays_a_full_one` | **SHIPPED** | docstring: *"**DIVERGENCE, pinned deliberately** … charged 1.4 round trips (19.60) — neither three per-fill commissions (21.00) nor the single round trip the booking layer documents … Filed as issue #552."* |
| `test_risk_based_sizing_spends_the_risk_budget_across_the_stop_distance` | **CANONICAL** | reproduces doc 02's own worked example (10 000 @ 1 % → 100 USD), stated in the module docstring |
| `test_no_leverage_normalizes_to_one_x_whatever_multiplier_is_saved` | **CANONICAL** | quotes Master Ref §10.2 verbatim |
| `test_cross_margin_opens_no_position_at_all` | **CANONICAL** | §10.2's cross-margin exclusion, fail-closed |
| `test_an_unallocated_item_gets_no_sleeve_and_therefore_no_fill` | **CANONICAL** | doc 13 §8.3/§8.4 step 5-6, money-denominated sleeve |
| `test_the_sleeve_caps_a_size_the_strategy_asked_for` | **CANONICAL** in mechanism, **SHIPPED** in input | sleeve arithmetic is canonical and money-denominated; the `base_position_size: "1000000"` input is a unit figure |
| `test_a_non_positive_kelly_edge_opens_nothing` | **MISLEADING NAME** | asserts `_entry_size(out) == 0` only. **The name promises "opens nothing"; the engine opens a 0-size position and books a trade** (measured §2.2 row 3). The name describes canon, the assertion describes shipped. |
| `test_isolated_leverage_multiplies_the_computed_size` | **SHIPPED** in basis | the multiplication order is canonical; the base it multiplies is the unit reading |
| remaining 10 (lifecycle: partial fractions, aftermath rules, scaling ladder, gap rule) | **CANONICAL** | doc 02 §5.3/§5.7, Master Ref §7.1/§11.1-§11.4; unaffected by all three issues |

**Load-bearing consequence:** a green oracle suite on this base is **compatible with all three
defects being live**. When any of these lands, these five files must be *recomputed*, not
merely re-run — and `test_a_non_positive_kelly_edge_opens_nothing` should gain the trade-count
assertion its name already promises.

---

## §5 — `ENGINE_VERSION` boundary: recommendation and reasoning

### 5.1 Do the three fixes move golden/oracle results?

| Fix | Moves money? | Moves artifact shape? |
|---|---|---|
| **#550** | **Yes, on every run using `base_position_size` or the limits** — size changes, so notional, exposure, PnL, drawdown and equity curve all change | no |
| **#551** | **Yes** — a suppressed phantom removes a trade row, an equity point and a `position_intervals` record; `total_trades` / `win_rate` / average trade all change. With `commission > 0` the **final equity** changes too (measured: `9986.00` → `10000.00`) | **yes** — journal `seq` renumbering, one fewer trade row |
| **#552** | **Yes, on every commissioned run with more than one exit lot** | no |

All three cross the bar the existing `ENGINE_VERSION` history sets.

### 5.2 One boundary or three?

**Recommendation: ONE `ENGINE_VERSION` string, and it depends only on how many WAVES they
land in — not on how many defects they are.**

The repo already adjudicated this exact question. `manifest.py:101-105`:

> *"v18-min-n-filtered-events-artifact (I-02 merged onto I-15a): this branch carries BOTH
> engine changes, so the version names both. **It is NOT a third behavioural change — the
> single string exists because the namespace must shift relative to EACH predecessor**"*

The namespace is a **single opaque string inside `execution_content`** (`manifest.py:229`),
not a set of feature flags. It cannot express "differs from predecessor P₁ but not P₂". So:

* **land all three in one PR → exactly one bump**, a name that mentions all three, one golden
  regeneration. This is what #550 and #551 already argue for on their own grounds (shared
  `_clamp_to_limits` path, shared three fields, "0 percent" *is* the #551 phantom once #550
  lands), and #552 joins cheaply because it touches a disjoint file (`booking.py`) with no
  merge risk;
* **land them separately → three bumps and three golden regenerations**, and each intermediate
  Result is incomparable with both its predecessor and successor. Strictly more expensive with
  no benefit — the namespace gives no finer attribution either way.

Suggested string if landed together, following the shipped naming convention (lowercase,
hyphenated, names every behavioural change):
`backtest-engine-v18-percent-sizing-zero-size-block-commission-model`.

**Separate boundaries would only be justified if the PO answers PO-1/PO-2/PO-3 at different
times.** That is a scheduling outcome, not a design choice — and it costs two extra golden
regenerations.

### 5.3 Is there an execution-key namespace? Yes — and it is weaker than the comments imply

**Mechanism, verified:**

1. `engine_version` is a member of `execution_content` (`manifest.py:229`), which is hashed
   into `execution_key` (`:239`). A bump therefore shifts the key for every composition.
2. Every Result stores its **own** `execution_key` **and** `engine_version` in
   `result_manifest_snapshot` (`models/backtest.py:395-396`), described in the model docstring
   as *"doc 15 §12 historical integrity"*. Historical Results are **self-describing**: each
   carries the engine identity that produced it.
3. `queries/backtest_run.py:222-223` reads both back for display.

**Honest boundary — and it corroborates #550's own claim:** `execution_key` in this build is
only ever **WRITTEN**. There is **no `SELECT … WHERE execution_key = …`** anywhere in `src/`
(grep across queries and repositories returns only writes at
`repositories/backtest.py:133` and `:407`). The "never idempotently reused for a re-RUN
(INF-04/INF-05)" phrasing repeated throughout `manifest.py` describes the *intended* property
of the namespace, but **no reuse lookup exists to be namespaced.** Likewise there is no
equality gate comparing a stored `engine_version` against the current constant.

**What actually protects historical Results is therefore:**

* they are **immutable rows** that store their own `engine_version` — nothing re-interprets a
  stored Result through the current engine;
* there is **no re-derivation path** — a Result is written once by the worker and read back
  verbatim.

**Risk is therefore NOT in pinned Results — it is in saved strategy REVISIONS.** #550 states
this precisely and this audit confirms the mechanism: a revision stores a bare number whose
*meaning* changes, and no mechanical migration exists (`50` is 51 % of a 10 000 account at
price 102 and 5 000 % of it at price 10 000 — and the pinned market revision's price still
does not recover the user's **intent**). Without a visible transition gate, every
pre-existing strategy would **silently run at a different size on its next RUN**. #550's
proposed Ready Check blocker is the right shape; it is a **PO decision** whether it blocks or
warns (**PO-5**).

**Second, independent transition hazard — not in any issue:** #552 has the *same* problem in a
weaker form. Under option **C** (bps on notional) a saved `commission = 7` cannot be read as
`7 bps` without changing every commissioned run's cost by orders of magnitude. Options A and B
reinterpret nothing (the field's meaning — a per-fill amount — is unchanged; only the
apportionment rule moves), so **only option C carries a revision-migration cost.**

---

## §6 — Historical compatibility risk

| Risk | Severity | Basis |
|---|---|---|
| A stored Result is re-interpreted under new semantics | **None** | Results are immutable rows carrying their own `engine_version`; no re-derivation path; no equality gate. Verified by grep. |
| A stored Result is idempotently reused for a re-RUN under a shifted namespace | **None — the reuse path does not exist** | No `SELECT` on `execution_key` anywhere in `src/`. The bump is correct discipline but is currently protecting a gate that is not wired. **This is itself an open item** (§7, PO-6). |
| **A saved strategy revision silently runs at a different size after #550** | **HIGH** | The stored number's meaning changes; no mechanical migration is possible; nothing today would surface the change to the user. |
| A saved revision silently runs at a different cost after #552 | **LOW under options A/B, HIGH under option C** | A/B change apportionment only; C reinterprets the stored value's unit. |
| Golden fixtures drift un-attributably | **MEDIUM** | Three fixes, one digest regeneration. #551 warns correctly that digest-diffing **over-reports** — scan fixtures for the *condition* (non-positive resolved size; >1 exit lot with commission > 0; non-empty `base_position_size`/limits) rather than diffing digests, the way #549's blast radius was measured. |
| Cross-item composition results change | **None from #551** | The zero-notional interval never reaches the conflict gate (§2.4, measured with a positive control). It changes from #550, because real sizes change. |

---

## §7 — PO decisions required (open questions, deliberately unanswered)

**PO-1 — #550: is `base_position_size` a percent of resolved capital, or a unit count?**
Five shipped/canonical sources say percent, the engine says units. #550's body records a
decision comment ("adopt canon, option A"); **this audit does not treat an issue comment as an
adjudication.** Needs a recorded ruling in the repo. Sub-questions the ruling must also
answer: do `min_position_size` / `max_position_size` become percent bounds on the same basis?

**PO-2 — #550/§1.4: does `min_position_size` survive at all?**
It exists in no canonical source and in no v18 mockup field, and it *increases* size beyond
what the strategy asked for. Options: keep as a shipped extension (document it), or remove it.
Removing it is a breaking schema change.

**PO-3 — #550/§1.3: on exceeding Max Single Position, does the engine clamp or block?**
Master Ref §10.2 says *"clamp değil blocker veya explicit cap policy"*; the shipped code
silently clamps. Independent of PO-1 — it stays open even if the unit question is answered.
Related: **should a strategy-level `max_total_exposure_percent` be added?** It exists in canon
and in the mockup, its ⓘ panel is already shipped attached to no field, and it is the one
control that would bound the §1.2 Case-B blow-up.

**PO-4 — #551: does the bust-equity 0-size fill survive the zero-size guard?**
`_open`'s docstring calls it a deliberate invariant ("preserving the risk-based
no-phantom-profit invariant"). #551's blanket `if size <= _ZERO: return None` suppresses it.
Suppressing is probably right — but it changes a documented invariant, so it needs a ruling.

**PO-5 — #550: does the saved-revision transition gate BLOCK or WARN?**
No mechanical migration is possible (§5.3). A Ready Check blocker stops every pre-existing
strategy until a human restates the value; a warning lets them run at a silently different
size. Both have real costs.

**PO-6 — #552: which commission model — A (per fill), B (one round trip per position), or C
(bps on notional)?**
§3.3 documents the financial consequence of each. Canon (line 3110) points at **C**; the
shipped schema description points at **A**; the shipped docstring points at **B**. Today's
behaviour is none of them. **Whichever is chosen, canon line 7513 additionally requires the
`komisyon dağılımı` to be published in the engine manifest, and line 7425 requires the
currency/unit and the resolved default to be published too** — neither is published today.
**Model must not invent this answer.**

**PO-7 — process, surfaced by this audit: is the un-wired `execution_key` reuse path an
accepted boundary or an open defect?**
Eleven `ENGINE_VERSION` bump rationales in `manifest.py` justify themselves by
"never idempotently reused for a re-RUN (INF-04/INF-05)". No reuse lookup exists. Either the
rationale text should stop claiming a property the build does not have, or the lookup is
missing work. **Out of scope for the three financial issues; recorded so it is not lost.**

---

## §8 — Matrix

Classes follow the repo's `debt_class` vocabulary
(`docs/audit/acceptance_coverage_debt_ledger.md`): **A** = ships under a different name ·
**B** = implemented, assertion missing · **C** = not assertable · **D** = the named
code/field/behaviour does not exist (product work; several need a product ruling first).

| ID | Finding | Issue | Verdict | Class | Site | Evidence |
|---|---|---|---|---|---|---|
| **F-1** | `base_position_size` executes as units; UI, mockup, both canonical docs and the shipped ⓘ panel all say percent | #550 | **CONFIRMED — live** | **D** (needs PO-1) | `sizing.py:216` vs `StrategyConfigForm.tsx:591-592` | §1.2 Case A/B; 612× at price 61 200 |
| **F-2** | `min_position_size` / `max_position_size` execute as units; UI labels both `%` | #550 | **CONFIRMED — live** | **D** (PO-1) | `sizing.py:186-193` vs `.tsx:675-682` | §1.2 Case C |
| **F-3** | `min_position_size` has no canonical or mockup counterpart and *increases* size | *new* | **CONFIRMED — live** | **D** (PO-2) | `sizing.py:192-193` | oracle `test_a_min_limit_pushes_the_size_up`: 50 → 80 |
| **F-4** | Strategy-level `max_total_exposure_percent` absent; its ⓘ panel ships attached to no field | *new* | **CONFIRMED — live** | **D** (PO-3) | `config.py:769-771`; `lib/strategyForm.ts:101` | grep: exists only at allocation level |
| **F-5** | Over-limit **clamps silently**; §10.2 requires blocker or explicit cap policy | *new* | **CONFIRMED — live** | **D** (PO-3) | `sizing.py:191-193` | Master Ref §10.2 |
| **F-6** | Zero-size phantom trade in independent mode; guard bound to `alloc_on` | #551 | **CONFIRMED — live**, 4 method paths + bust equity (issue says 3) | **D** (PO-4) | `engine.py:1462` (issue cites `:1457`) | §2.2 rows 1/3/4/5; `total_trades=1`, `win_rate=0.0000` |
| **F-7** | Phantom position pays a **full round trip** when `commission > 0` | *new* | **CONFIRMED — live** | **D** | `booking.py:93` + `engine.py:1462` | `pnl = -14.00`, `final_equity 9986.00` |
| **F-8** | **Negative** `base_position_size` books a negative-size position with **inverted PnL sign** | *new* | **CONFIRMED — live, more severe than #551** | **D** | `sizing.py:216` + `:184`; `config.py:711` (no `gt=0`) | `size=-5`, `pnl=-10.00` on a +2.00 move; `peak_notional=-510.00` |
| **F-9** | No upstream gate: schema accepts `0` / `-5` / `min>max`; `sizing_is_modelled` returns `True` for all | *new* | **CONFIRMED — live** | **D** | `config.py:711,770-771`; `sizing.py:116`; `readiness/validators.py:453` | direct model + predicate probes |
| **F-10** | Phantom 0-notional interval blocks a later item's entry | #551 (b) | **REFUTED** — does not reproduce | **C** (issue text needs correction) | `engine.py:722-724` filters before `rules.py:69` | phantom → 0 intervals → `False`; **positive control**: real → 1 interval → `True` |
| **F-11** | Partial-close total fee scales with lot count: 1.40–1.90 round trips vs the documented 1.00 | #552 | **CONFIRMED — live** | **D** (PO-6) | `booking.py:93` vs docstring `:83-84` | §3.2(a): 14.00 / 19.60 / 21.00 / 25.20 / 24.50 / 26.60 |
| **F-12** | Fee tracks the **fraction parameter**, not the quantity closed | *new* | **CONFIRMED — live** | **D** (PO-6) | `booking.py:86` vs `:93` | 12.5 / 9.375 / 7.03 units all charged **3.50** |
| **F-13** | Cost model is flat-per-fill; canon requires **bps on notional**, plus unit/currency and resolved default in the manifest | *new* | **CONFIRMED — live** | **D** (PO-6) | `config.py:313`; `costs.py:134` | Master Ref lines 3110 / 7425 |
| **F-14** | Commission **apportionment is not published in the manifest** as canon requires | *new* | **CONFIRMED — live** | **D** (PO-6) | `manifest.py:224-237` | Master Ref line 7513 |
| **F-15** | 5 oracle tests pin **shipped** (defective) behaviour; `test_a_non_positive_kelly_edge_opens_nothing` promises canon in its name but asserts shipped | — | **CONFIRMED** | **B** | §4 table | 22 passed, `exit=0` — green is compatible with all three defects live |
| **F-16** | `execution_key` is written but never read; the reuse property 11 `ENGINE_VERSION` rationales claim is not wired | *new* | **CONFIRMED** | **D** (PO-7, out of scope) | `repositories/backtest.py:133,407`; no `SELECT` | grep across `src/` |
| **F-17** | Leverage multiplies a **risk-budget-derived** size, so a 2 % risk config loses 10 × its stated budget at 10× leverage | *new, adjacent* | **CONFIRMED — live** | **D** (needs its own ruling) | `sizing.py:264` | measured: `lev=10` → size 500, loss at the configured 4.00 stop = **2 000.00** vs the configured 200.00 budget |

---

## §9 — Commands run (reproducible on this base)

```
cd backend
uv sync --all-extras
uv run pytest -q --no-cov \
  tests/unit/oracles/test_oracle_sizing.py \
  tests/unit/oracles/test_oracle_position_lifecycle.py
# exit=0 — 22 passed in 0.39s
```

Plus five throwaway probes driving the shipped `run_engine` / `close_position` /
`_position_size` / `build_prior_intervals` / `conflicts_with_prior` directly (not committed —
they assert nothing and would be dead weight in the suite; every number they produced is
transcribed above with its inputs so it can be re-derived).

**Not run:** full backend suite, `mypy`, `ruff`, OpenAPI export, `alembic heads`, frontend
suite. This session changed no code and no test, so those gates measure the unchanged base;
**CI is the authority** for them.
