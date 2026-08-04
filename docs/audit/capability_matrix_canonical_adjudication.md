# Engine Capability Matrix — canonical adjudication (ADIM 11)

> **Audit-only.** No capability was activated. No production code, schema, migration,
> OpenAPI snapshot, codemap or engine semantics changed in the PR that carries this
> document. Every claim below was re-measured on the base SHA named here; nothing is
> inherited from a prior handoff, kickoff, backlog or README.

| | |
|---|---|
| **Base** | `origin/main` @ `53c28de` (PR #537 merged 2026-08-04T11:28Z) |
| **Audit date** | 2026-08-04 |
| **Branch** | `docs/audit-capability-matrix-adjudication` |
| **`ENGINE_VERSION`** | `backtest-engine-v18-same-candle-entry-exit` (`domain/backtest/manifest.py:118`) |
| **Alembic head** | `0043_i08_registry_strategy_fks` (single head) |
| **Matrix shape** | **62 rows / 22 `future_dev` / 14 field paths** (measured, not quoted) |
| **Method** | canonical spec read → static call-chain trace → **executable probe** against the real engine, the real Pydantic models and the real form modules → test inventory. Read-only sub-agents produced the per-domain evidence; every disposition-changing claim was then re-verified in the main session before being accepted. Three sub-agent conclusions were **overruled** (§9). |

---

## 0. Executive summary

The matrix's **enforcement machinery is sound**. The three surfaces it exists to keep in
agreement — engine, Ready Check, saved-config round-trip — genuinely agree, and the
Python↔TS mirror is byte-exact today. What is *not* sound is the **justification layer**
and the **presentation layer**: two rows record a blocker reason that the canon
contradicts, and **half the `future_dev` rows never reach the user at all**.

**Disposition of the 22 `future_dev` rows:**

| Disposition | Rows | Which |
|---|---:|---|
| `canonical_gap` | **16** | historical slippage · custom formula · cross leverage · the 9 concrete scaling-timeframe rungs · `use_package_default_tf` · volatility / volume / correlation filters |
| `product_decision_required` | **3** | best bid/ask · trend adjusted · divergence adjusted |
| `keep_future_dev` | **2** | spread filter · allow hedge |
| `eligible_for_implementation` | **1** | `scaling_logic.timeframe_mode = increasing_by_layer` |
| `incorrect_current_status` | **0** | — see below |

**No row's `future_dev` *status* is wrong, and nothing here justifies activating anything.**
`incorrect_current_status` scored zero against the matrix rows. It was tested hardest
against the **eight tick-dependent `active_v1` rows** (partial fills ×4, intrabar touch ×2,
limit-fill simulation, stop/limit priority simulation) on the hypothesis that they are
future-dev in disguise — the hypothesis was **refuted by measurement**: each one changes the
executed result (§3.2). The status field is honest everywhere. What is wrong is *recorded
reasons* (D-7) and *user-facing claims* (D-1, D-5, NET in §3.7).

**Ten defects, none of them "the matrix is too conservative":**

| # | Defect | Kind | Severity |
|---|---|---|---|
| **D-1** | **11 of 22 `future_dev` rows are rendered as ordinary, fully-selectable options with no disable and no note** — `StrategyGraphForm.tsx` never imports the generated matrix | UI ↔ Ready Check **false-negative** | **CRITICAL** |
| **D-2** | The exhaustiveness guard covers **9 of the matrix's 14 field paths**; 3 unguarded fields already carry `future_dev` rows | test gap | **HIGH** |
| **D-3** | 6 matrix fields are absent from the diagnostics provenance block, so a Result cannot be read back to the option that was rejected | provenance gap (#534 family) | MEDIUM |
| **D-4** | The restriction **action** space (`reduce`/`close`/`disable`/`warn`) is canonical, fails closed correctly, but has **no matrix field** — the run is inert while `capability_not_in_build` is empty | provenance / matrix gap | MEDIUM |
| **D-5** | `strategyGraph.ts:93-95` states the matrix "disables it in the form" for `increasing_by_layer`; it does not | stale comment | MEDIUM |
| **D-6** | `MODELLED_FILTER_TYPES` is a hand-maintained duplicate of the engine allow-list with no parity test | drift surface | MEDIUM |
| **D-7** | The recorded blocker reason for `increasing_by_layer` is **contradicted by canon**, and the one for the scaling-timeframe rows **overstates** what the replay cannot do | false justification | **HIGH** |
| **D-8** | Canonical error code `FORMULA_AST_INVALID` (doc 02 §—, line 2394) is never emitted | canon ↔ build divergence | LOW |
| **D-9** | **Three of four `signal_strength_adjustment` literals — including the shipped ACTIVE one — appear in no canonical document** | canon ↔ schema divergence | **HIGH** |
| **D-10** | `correlation_filter` is in the schema and in no canon; `regime_filter` is in canon and in no schema | canon ↔ schema divergence | **HIGH** |

D-1 is the headline. The generated mirror's own docstring states it exists "so the Strategy
editor can disable those options BEFORE a user builds a strategy on one"
(`engineCapabilityMatrix.generated.ts:10-12`). For 11 of 22 rows it does not.

---

## 1. Canonical authority and method

Authority order used throughout, per the working standard:

1. `docs/spec/Entropia_V18_Master_Technical_Reference_v1_0.md`
2. the relevant `docs/spec/01–22` page document (chiefly **02** Strategy Details, **13**
   Portfolio Equity Allocation)
3. the v18 HTML mockup — **visible UI only**, never semantics
4. current production code, migrations and tests

**Rules held throughout, without exception.** No formula, rung size, threshold, time
ordering or product decision was invented to fill a canonical hole. Where canon is silent
this document says *canonical gap* and names precisely what is missing. Trade prints were
never counted as quotes; spread and slippage were never derived from OHLCV; no correlation
was proposed without naming the second-instrument dependency; no custom-formula grammar was
sketched.

**"UI disabled" was never accepted as authorization.** Every row was traced through
Ready Check **and** the engine's own fail-closed gate **and** round-trip **and**
diagnostics — which is exactly how D-1 surfaced: the rows whose UI treatment is missing are
still refused by the server, so the defect is a disclosure failure, not an authorization
hole.

---

## 2. The matrix as it ships, and where it is enforced

```
$ uv run python -c "from entropia.domain.backtest.capabilities import *; ..."
total 62  future_dev 22  fields 14
```

Three enforcement points, all measured:

| Surface | Site | Behaviour |
|---|---|---|
| **Engine** | `domain/backtest/engine.py:1106` binds `capability_ok`; enforced at `engine.py:1438` inside `_open` | `_open` is "the single choke point every entry path funnels through (flat entry, conflict-driven stack / replace, and the scaling ladder)" (`engine.py:1435-1437`) — a `future_dev` selection opens **nothing** |
| **Ready Check** | `domain/readiness/validators.py:434-447` | one `STRATEGY_CAPABILITY_NOT_IN_BUILD` BLOCKER **per** selected option, message `"Not available in this build: '<label>' (<field_path>) …"`, remediation = `"Choose a supported option. " + dependency` |
| **Round-trip** | Pydantic models are bare `Literal`s with no coercing validators | a saved `future_dev` value survives read-back **byte-identically** in all three field kinds probed (simple enum, conditional subtree, array item) |

The reachability readers are the load-bearing subtlety and they are **correct**: an option
sitting on a collapsed subtree is *not* a selection. Proven by probe —

```
volatility_filter, enabled=false   → _read_filter_types ()      capabilities_are_modelled True
volatility_filter, enabled=true    → ('volatility_filter',)     capabilities_are_modelled False
timeframe='1h', scaling disabled   → _read_scaling_timeframe () capabilities_are_modelled True
timeframe='1h', scaling enabled    → ('1h',)                    capabilities_are_modelled False
```

`ADIM 10` (PR #537 §3.4) established the same rule for `_read_opposite_hedge`. That
reachability discipline is what D-1's frontend counterpart lacks.

**Generator parity is genuine.** `test_generated_typescript_mirror_is_up_to_date`
(`tests/unit/test_capability_matrix.py:490-506`) asserts full-file string equality against
`exporter.render()` — byte-exact, header and JSON indentation included. Regenerating today
to a temp path produces a byte-identical file (sha256 match); the tracked file was never
written.

---

## 3. Row-by-row adjudication

### 3.1 Costs and execution data — the two rows that need a series the run cannot pin

| | `data.costs.slippage_mode = historical_slippage_if_available` | `data.order_config.limit.price_rule = best_bid_ask` |
|---|---|---|
| **Matrix** | `capabilities.py:122-133`, generic blocker | `capabilities.py:153-165`, `STRATEGY_ORDER_TYPE_UNSUPPORTED` |
| **Engine gate** | matrix gate **only** — `_cost_params` (`execution/costs.py:128-134`) never branches on `slippage_mode` | **two independent** gates: `execution/fills.py:215-217` (`_MODELLED_LIMIT_PRICE_RULES` excludes it) **and** the matrix gate |
| **Ready Check** | `STRATEGY_CAPABILITY_NOT_IN_BUILD` | **both** `STRATEGY_CAPABILITY_NOT_IN_BUILD` and `STRATEGY_ORDER_TYPE_UNSUPPORTED` (measured) |
| **Tick unlocks it?** | n/a | **No** — measured with `tick_policy='require'` + prints: `order_execution_is_modelled=False`, `trades=0`. The rule test is unconditional on `tick_backed` |
| **Round-trip** | preserved (`slippage_value` stays `None`) | preserved |
| **Provenance** | **absent** (D-3) | **absent** (D-3) |
| **Canon** | Master Ref `:7427` "Historical model yalnız uyumlu execution dataseti varsa kullanılabilir"; dataset schema `:3457` `execution_cost decimal (optional…)` | doc 02 `:1564` defines the semantics; Master Ref §9.3 `:3444-3465` schematises `bid`/`ask`/`spread` with `ask ≥ bid` |
| **What canon does NOT supply** | **the formula** turning `execution_cost` into per-fill slippage, **the fill↔cost-row time ordering**, and unit normalisation. The field is even declared *optional* | only a number: `:3513` forbids simulating from a "çok eski" quote but **quantifies no staleness threshold** |
| **Disposition** | **`canonical_gap`** | **`product_decision_required`** |

The two look alike and are not. `SPREAD_EXECUTION` exists as a product data type
(`domain/market_data/enums.py:20`) and `StrategyConfig` pins **exactly one** dataset
(`domain/strategy/config.py:134-136`) — so *both* need a second pin. The difference is what
happens after the data arrives: for **bid/ask** canon already says what the number means, so
what remains is a scoped build plus one product-set threshold. For **historical slippage**
canon supplies an availability precondition and nothing else — no computation exists to
implement. Fabricating either from OHLCV or from trade prints is forbidden and was not
proposed.

### 3.2 The eight tick-dependent `active_v1` rows — `incorrect_current_status` REFUTED

The prompt asks whether "tick partial fills", "intrabar touch" and "stop-limit priority" are
honestly active. They are. Each was driven through the real engine on identical bars with
tick data off and on:

| Row | Tick OFF | Tick ON — measured difference |
|---|---|---|
| `partial_fill_policy` ∈ {allowed, minimum_50_percent, fill_remaining_as_market, cancel_remaining} | blockers `[EXECUTION_TIMING_UNSUPPORTED, ORDER_TYPE_UNSUPPORTED]`, `trades=0` | `entry_fill size=20` vs `50` for the `not_allowed` baseline; `partial_fills=2`; events `[remainder_resting, remainder_touch 30/50]` |
| `entry_timing = intrabar_touch` | blocker, `trades=0` | print authority **removes** a fill the bar-touch baseline takes (`trades=0, touch_orders_placed=1` vs baseline `trades=1`) |
| `exit_timing = intrabar_touch` | blocker, `trades=0` | same bars, two tick sets → `exit_signal @99.00 pnl=-150.00` vs `end_of_data @98.90 pnl=-155.00` |
| `entry_timing = limit_fill_simulation` | blocker; **also** blocked with tick ON + a market order type — the second half of the dependency is real | fills at `bar_seq=23` where the bar-touch baseline fills at `bar_seq=22` |
| `exit_timing = stop_limit_priority_simulation` | blocker | `bar_seq=22, same_bar_stop_limit=True` vs baseline `bar_seq=23, same_bar_stop_limit_fills=0` |

Every one has its own behavioural test (`tests/unit/test_backtest_tick_settings.py:283-528`).
Canon is sufficient here and the build matches it — Master Ref `:8968` requires a **BLOCKER**
when Intrabar Touch is selected with OHLCV only, which is exactly what ships. **No action.**

One narrow canonical gap is recorded honestly rather than dispositioned: canon enumerates
the five partial-fill policies (doc 02 `:1615`) but never says *where the filled fraction
comes from*. The build chose print **size** evidence and degrades explicitly
(`partial_fill_evidence_unavailable`, `execution/output.py:192`) rather than fabricating one.

### 3.3 Sizing, leverage, signal strength

**`formula_type = custom_formula` → `canonical_gap`.** Canon commits to a restricted DSL/AST
(Master Ref `:7546` "Sınırlı DSL/AST… parse/type/unit validation zorunlu"; doc 02 `:2820`
requires "AST/DSL parse, type check, allowlist function ve dependency resolver") but
**nowhere enumerates the operators, the allowed functions, the variable namespace or the
unit system**. Worse, `FormulaBasedSizing` (`config.py:760-764`) carries `formula_type` and
an untyped `formula_params` — **there is no field to hold an expression at all**, so a custom
formula cannot even be stored canonically. Engine fails closed at
`execution/sizing.py:85-86`. Also **D-8**: canon defines `FORMULA_AST_INVALID` (doc 02
`:2394`, 422) for an unparseable formula; the build never emits it.

**`leverage_mode = cross` → `canonical_gap`.** Master Ref §10.2 (`:7556`, section number
verified) delegates cross semantics to "Equity Allocation/portfolio risk modeli". That target
is empty: doc 13 mentions "margin" exactly once, in passing (`:1313`), and defines no
maintenance-margin formula, no shared-margin pool equation, no liquidation rule. Independently,
the engine is a single-position replay (`execution/sizing.py:273-274`), and cross is only
distinguishable from isolated with ≥2 concurrent positions. Two missing models, not one.

**`signal_strength_adjustment ∈ {trend_adjusted, divergence_adjusted}` →
`product_decision_required`** — and this is the row where the audit found more than expected.

```
$ grep -rniE "volatility.adjusted|trend.adjusted|divergence.adjusted" docs/spec/
(no matches)
```

Canon's option set is a **different axis entirely**. Doc 02 `:1057`:

> `No; Increase Size When Condition Package Is Met; Decrease Size When Condition Package Is Met; Use Size Bands…`

Canon enumerates *direction of adjustment*, gated by a pinned Condition Package. The schema
(`config.py:720-725`) enumerates *which signal property drives it*:
`no_adjustment / volatility_adjusted / trend_adjusted / divergence_adjusted`. Three of the
four shipped literals exist in **no** canonical document — **including `volatility_adjusted`,
which ships as `active_v1`** (**D-9**). Nor does the schema carry the condition refs, the
adjustment formula or the upper/lower band caps that Master Ref §10.3 (`:7565`, verified)
requires.

So the blocker is not "the trend formula is missing". It is that **nobody has decided which
taxonomy is real**, and a decision must precede any implementation on this field — including
any decision about the row that is already active. That is `product_decision_required`, not
`canonical_gap`.

*Contrast, for the boundary's sake:* `volatility_adjusted` is active because it computes a
**self-normalising ratio** of short-window to long-window mean relative range
(`engine.py:370-402`), clamped to `[0.5, 2.0]`, from engine-version constants with **no user
input** — the volatility *definition cancels* and a wrong one is bounded. `volatility_filter`
is future_dev because a **threshold comparison** consumes a user-supplied number whose meaning
is fixed by that definition, from an untyped `config` dict. The asymmetry is real and
architecturally sound. It is nevertheless an engine-invented formula that appears in no spec,
disclosed only through `ENGINE_VERSION`.

### 3.4 Scaling

**The 9 concrete rungs `1m,3m,5m,15m,30m,1h,2h,4h,1D` → `canonical_gap`.**
Doc 02 §5.7 runs lines 1073–1143. Its rows are Scaling Timeframe *Structure*, Timeframe
*Mode*, Custom Timeframe *Sequence*, Additional Layer Method, Price-Distance, Logic-Based,
Rules Required, Add Size, Scaling Limits. **There is no row for a flat scaling evaluation
timeframe.** The identical 10-value option set appears exactly once in doc 02 — at `:794`,
under **§5.3 Indicator Block**, a different field on a different object. A key
`scaling.timeframe` appears nowhere in either canonical document (only
`scaling.timeframe_mode`, at `:1086`).

A sub-agent argued `eligible_for_implementation` on the strength of the `_ReferenceSeries`
resampler already existing (`domain/backtest/indicators.py:545-580`, closed-bar, no look-ahead).
**Overruled.** The resampler's existence answers "could we build it", not "what should it
do" — and the field it would serve has no canonical definition, so implementing it means
inventing whether the override retimes the ladder's *decision points*, the *price series it
compares against*, or both. That is the definition of a canonical gap.

**`use_package_default_tf` → `canonical_gap`** — different in kind from its nine siblings and
therefore dispositioned separately. It is not a timeframe but a *resolution instruction*, and
it has no referent: under `price_distance_scaling` the subtree carries **no package at all**
(`config.py:891-896`), and under `logic_based_scaling` it may carry **many**
(`config.py:898-901`) with no tie-break rule anywhere in §5.7.

**`increasing_by_layer` → `eligible_for_implementation`** — the single row that moves, and the
one whose recorded reason is false.

The matrix says (`capabilities.py:464-468`): *"Doc 02 §5.7 names the mode but not the rung
size (next canonical timeframe vs. doubling are different ladders), so the engine fails closed
rather than guessing one."* That is true of **§5.7** and false of **doc 02**. The §6.1 ⓘ panel
(`02_…_v1_1.md:1998`) states the rung:

> "Increasing Timeframe by Layer: Her yeni layer'da sistem ana timeframe'den başlayarak **bir
> üst timeframe'e geçer**." — with the illustration "Ana timeframe 15m … sırasıyla 15m → 30m → 1h".

"Doubling" is not a live alternative; canon names one ladder, and it matches
`CANONICAL_TIMEFRAMES` index + 1 (`config.py:33`). The mechanism also already ships from S5c:
`layer_timeframe` (`execution/scaling.py:149-166`) and `layer_bucket` (`:169+`) already gate
layer N on a per-layer timeframe, and `engine.py:1039-1045` already caps ladder depth.

**Honest qualification, recorded rather than glossed:** the canonical sentence is normative
("geçer"), but its example hedges ("**gibi**", "kullanabilir"). One behaviour is genuinely
undecided — what happens past the top of the ladder (`1D`). The `custom_sequence` precedent
("runs out of ladder", `execution/scaling.py:156-159`) supplies the obvious answer, but it is
a decision, not a derivation, and belongs in the implementation issue.

**This row is not activated here and must not be activated without that decision, an
`ENGINE_VERSION` evaluation and tests.**

### 3.5 Restrictions

| Row | Canon | Missing | Disposition |
|---|---|---|---|
| `volatility_filter` | doc 02 `:1160-1164` (*too high; too low; spike; compression; ATR above/below threshold*); Master Ref `:7622` requires an explicit indicator/data dependency and typed threshold params | a computation for **4 of the 5** conditions (only ATR is computable), the **baseline window**, and the "typed payload" canon defers to — which the schema never typed (`config.py:986-989` is free-form `dict[str, Any]`) | `canonical_gap` |
| `spread_filter` | doc 02 `:1166-1170`; Master Ref `:7623` *"yalnız last price ile sahte spread hesaplanamaz"*; dataset fully schematised at §9.3 | **nothing canonical.** The blocker is a real, named **data** dependency: the run streams one OHLCV series and cannot pin a Spread/Execution revision | **`keep_future_dev`** |
| `volume_filter` | doc 02 `:1172-1176`; Master Ref `:7624` | the **baseline window** and threshold semantics for 4 of 5 conditions. Volume itself *is* in OHLCV — this is not a data problem | `canonical_gap` |
| `correlation_filter` | **none** | everything — the second instrument, how it is referenced and pinned, the window, the estimator, the calendar-alignment rule | `canonical_gap` |

`correlation_filter` is the worst row in the matrix and its problem is not the one the
dependency note describes. Measured:

```
$ grep -niE "correlation" docs/spec/02_*.md docs/spec/Entropia_V18_Master_Technical_Reference_v1_0.md \
    | grep -vi correlation_id
(no matches)
```

Neither canonical document contains the word outside audit-envelope `correlation_id`. Doc 02
§5.8 and Master Ref §12.2 both end their filter enumeration with **Regime Filter** (doc 02
`:1178-1182`, Master Ref `:7625`) — and `regime` appears **nowhere** in
`domain/strategy/config.py`. The schema ships a filter canon never defined and omits one canon
does define (**D-10**). Whether `correlation_filter` was meant to be `regime_filter` is a
product question, not an engineering one.

**Contrast — the three active filters, and D-4.** The claim that only the block-entries action
is modelled is verified in code (`engine.py:513-515`, `_MODELLED_FILTER_ACTIONS =
{"block","block_entries"}`, an absent action accepted as block). A saved `action:"reduce"`
is **not** silently downgraded: the value round-trips, `restrictions_are_modelled` returns
False, Ready Check blocks and the engine opens nothing. Correct fail-closed behaviour. But
the matrix has **no field path for the action** — measured, that same config yields
`capabilities_are_modelled=True` and `future_dev_selections=[]`, so the Result's structured
`capability_not_in_build` list is **empty while the run is inert**; the reason survives only
in a free-text warning. Canon treats these actions as first-class (doc 02 `:1202-1214`,
Master Ref `:7640-7641`), so an `active_v1` row silently carries a canonically-defined,
unmodelled action space.

### 3.6 Allow Hedge — adjudicated upstream, not re-derived

`conflict_position_handling.opposite_direction_hedge = allow_hedge` → **`keep_future_dev`**.

ADIM 10 closed this row end to end on the immediately preceding SHA
(`docs/audit/strategy_conflict_matrix_closure.md` §3.4): backend three-way parity is exact,
the value is inert (not a selection) when `exit_on_opposite_signal` is ON, and the dependency
— two concurrent opposite positions with independent margin and PnL — is real for a
single-position replay. The one open defect, the Strategy form's false "Ready Check blocks
it" claim on the **default** config, is already filed as **#533**. Nothing is re-filed here;
§4 D-1 reports the *converse* defect on other rows, which #533 does not cover.

### 3.7 NET — outside the matrix, and disclosed as something it cannot do

`NET` is **not a capability-matrix row**. It lives on a separate surface as
`CrossItemConflictPolicy.NET` (`domain/allocation/enums.py:35-52`), the cross-item
counterpart of doc 02's per-strategy conflict handling.

**Canonically it is barely there.** Master Ref §6.3 (`:8196`) says conflict rules *may limit*
two items holding opposing positions and that a blocked item's capital is never transferred.
Doc 13 §8.4 step 6 (`:907`) repeats only the non-transfer rule. **Neither document enumerates
a policy set, and neither defines netting/offset semantics** — at what price, in whose ledger,
how PnL is attributed. Doc 13's own draft-write contract (`:816`) lists the body as
`{ enabled, initial_capital, compounding_mode, reserve_cash_percent, entries[] }` — **no
`conflict_policy` field at all**. → **`canonical_gap` + `product_decision_required`.**

**And its disclosure is counterfactual.** ADIM 3 contained shared capital allocation entirely
(`domain/allocation/capability.py`, `SHARED_ALLOCATION_STATUS = "future_dev"`), so an enabled
plan leads with a **BLOCKER** and no shared run is admitted. NET nevertheless still emits its
pre-containment WARNING. Measured:

```
--- conflict_policy = NET
   BLOCKER  SHARED_MODE_NOT_IN_BUILD     field=enabled
   WARNING  CONFLICT_POLICY_NET_V1       field=conflict_policy
--- conflict_policy = BLOCK_OPPOSITE
   BLOCKER  SHARED_MODE_NOT_IN_BUILD     field=enabled
```

The warning text says *"the engine executes NET conservatively as BLOCK_OPPOSITE"*
(`domain/allocation/rules.py:220-227`), and the browser repeats it as a **select label** —
`NET: "Net (V1: executed as Block opposite)"` (`frontend/src/lib/allocation.ts:231`). Under
containment **no shared run executes at all**, so both statements advertise an execution
behaviour that cannot occur. The `CrossItemConflictPolicy` docstring
(`enums.py:41-47`) is stale for the same reason. The downgrade code still exists at
`engine.py:862-871` and would become reachable again the moment containment lifts — which is
precisely when NET's undefined semantics would start producing numbers.

This is a **disclosure defect, not an authorization hole**: the run is refused. But
"conservatively substituted" is exactly the silent-fallback shape the standard forbids, and
here it is being *advertised* while not even happening.

---

## 4. Product-decision list — human decisions, not agent work

An agent must not resolve any of these. Each needs a named owner.

| # | Decision | Why it cannot be derived | Related |
|---|---|---|---|
| **P-1** | **Which `signal_strength_adjustment` taxonomy is canonical** — canon's *Increase / Decrease / Size Bands* gated by a Condition Package, or the shipped *volatility / trend / divergence*? | Two orthogonal axes; picking one is a product commitment. Affects the **active** `volatility_adjusted` row, not only the two `future_dev` rows | D-9, §3.3 |
| **P-2** | **Is `correlation_filter` meant to be `regime_filter`?** | Canon defines Regime and never mentions correlation; the schema does the reverse | D-10, §3.5 |
| **P-3** | **Stale-quote threshold for `best_bid_ask`** | Master Ref `:3513` forbids simulating from a "çok eski" quote but sets no number | §3.1 |
| **P-4** | **Does V1 own a second dataset pin?** (a Spread/Execution revision alongside the market dataset) | Gates `best_bid_ask` **and** `spread_filter` together; it is a schema + manifest + run-admission commitment | §3.1, §3.5 |
| **P-5** | **Which volatility / volume filter conditions ship** (ATR-only and MA-only are viable subsets) | Canon pins a computation for 1 of 5 and 1 of 5 respectively | §3.5 |
| **P-6** | **NET: define it or remove it.** Define netting semantics (price, ledger, PnL attribution) — or drop the value and stop advertising a downgrade | Canon defines no policy set; doc 13's draft contract has no such field | §3.7 |
| **P-7** | **`increasing_by_layer` top-of-ladder behaviour** past `1D` | The `custom_sequence` "runs out of ladder" precedent is the obvious answer but is still a choice | §3.4 |
| **P-8** | **Should the restriction action space become matrix-enumerable?** | Canon defines 5 actions; 1 is modelled; today the gap is invisible in structured provenance | D-4 |

**P-1, P-2 and P-6 also touch already-shipped behaviour**, so they rank above the rest. They
overlap the still-open **#535** (6 of doc 02 §5.9's conflict rows untyped, 3 defaults
divergent) — the same class of canon↔schema divergence on an adjacent surface. They should be
decided together, not row by row.

---

## 5. Implementation candidates — one issue each, none implemented here

Ordered by value ÷ risk. **Every one is a separate PR.** Nothing below was built in this PR.

| # | Candidate | Scope | Depends on |
|---|---|---|---|
| **C-1** | **Wire the generated matrix into `StrategyGraphForm`** (D-1) — give its `SelectField` the same `capabilityField` parameter `StrategyConfigForm` has, gate the note on `scaling.enabled` / `filter.enabled` to mirror the backend readers, and delete the duplicated `MODELLED_FILTER_TYPES` (D-6) | frontend only; no wire contract, no route, no OCC token | — |
| **C-2** | **Close the exhaustiveness guard** (D-2) — add the 5 matrix-present-but-unguarded field paths to `_SCHEMA_FIELDS` | one test file | — |
| **C-3** | **Correct the two false justifications** (D-7) and the stale comment (D-5) | comment/docstring text only, zero behaviour | — |
| **C-4** | **Extend the diagnostics provenance block** (D-3) with `slippage_mode`, `limit.price_rule`, `partial_fill_policy`, `formula_type`, `scaling_timeframe`, `scaling_timeframe_mode` | joins **#534**, which reports the same defect for two other fields — should be one PR | #534 |
| **C-5** | **Implement `increasing_by_layer`** (§3.4) — canon supplies the rung, S5c supplies the mechanism | **P-7**; needs an `ENGINE_VERSION` evaluation and behavioural tests | P-7 |

C-1 is the highest-value item in this audit and is independent of every product decision.
C-2 and C-3 are near-zero-risk. C-5 is the only one that changes engine behaviour and is the
only one gated on a product decision.

---

## 6. Verification performed for this audit

| Check | Result |
|---|---|
| Backend targeted — capability matrix (incl. the byte-exact Python↔TS parity pin), readiness validators, scaling, scaling timeframe mode, restrictions, sizing, signal strength, tick settings, limit orders | **271 passed, exit 0** |
| Backend targeted — allocation rules (NET + containment) | **18 passed, exit 0** |
| Frontend targeted — `engineCapabilityMatrix`, `capabilityLib` (`--no-file-parallelism`) | **14 passed, 2 files, exit 0** |
| Capability generator regenerated to a temp path and diffed against the tracked mirror | **byte-identical** (sha256 match); tracked file never written |
| Engine fail-closed, per `future_dev` row | `capabilities_are_modelled=False`, `trades=0`, `capability_not_in_build` populated |
| Reachability readers (disabled filter / disabled scaling) | **inert, as designed** — probes in §2 |
| Production behaviour diff | **empty — docs-only**, `git diff --name-only origin/main` returns one path under `docs/` |

Full suite not run: this PR changes no code. The targeted set covers every module this audit
makes a claim about, including the parity guard and the fail-closed gate.

---

## 7. Honest boundary — what this audit did NOT do

- **No capability was activated.** `SHARED_ALLOCATION_STATUS`, `CAPABILITY_MATRIX` and every
  status literal are untouched.
- **No canonical hole was filled.** Where canon is silent this document names the silence.
  No formula, rung, threshold, window, estimator or grammar was invented.
- **`allow_hedge` was not re-derived** — ADIM 10 measured it on the preceding SHA and #533
  already carries its open defect.
- **D-1's blast radius was measured on the form modules, not in a browser.** The probe drove
  `StrategyGraphForm`'s render path and observed zero disabled options and a null
  `aria-describedby`; no human or screen-reader session was run. The **server-side** claim —
  that these 11 rows are still refused by Ready Check and the engine — *was* measured
  directly and holds.
- **The `_ReferenceSeries` resampler was read, not exercised** for a scaling override; the claim
  that it "could serve" a timeframe override is deliberately **not** used to justify a
  disposition (§3.4).
- **`increasing_by_layer` is dispositioned `eligible`, not implemented.** Its canonical
  sentence is normative but its illustration hedges ("gibi", "kullanabilir"), and P-7 is open.
