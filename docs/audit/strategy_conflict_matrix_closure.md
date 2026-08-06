<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# Strategy Conflict Matrix — closure audit (ADIM 10)

> **Audit-only.** No production code, schema, migration, OpenAPI snapshot or engine
> semantics changed in the PR that carries this document. Every claim below was
> re-measured on the base SHA named here; nothing is inherited from a prior handoff,
> kickoff, backlog or README.

| | |
|---|---|
| **Base** | `origin/main` @ `57c9d0e` (PR #530 merged) |
| **Audit date** | 2026-08-04 |
| **Branch** | `docs/audit-strategy-conflict-matrix` |
| **`ENGINE_VERSION`** | `backtest-engine-v18-same-candle-entry-exit` |
| **Alembic head** | `0043_i08_registry_strategy_fks` (single head) |
| **Method** | canonical spec read → static call-chain trace → **executable probe** against the real engine → test inventory. Every behavioural claim marked *measured* was produced by running `run_engine`, not by reading it. |

---

## 0. Executive summary

The four conflict rows the project believed it had closed (**Stop + Exit**, **Multiple
Stops**, **Same Candle Entry / Exit**, **Stop Mode**) are genuinely closed end to end:
saved literal → UI select → round-trip → engine consumer → diagnostics → tests. Multiple
Stops has a **real consumer**, not just an enum. `first_trigger_wins` states its OHLCV
authority boundary honestly and flags it per event.

The audit nevertheless found **six defects/gaps**, of which two are contract defects
reproducible on the current build:

| # | Finding | Kind | Fix venue |
|---|---|---|---|
| **F-1** | `entry_exit_collision` is emitted by the engine but is **absent from the published `decision_trace_event_types`** taxonomy | contract defect (measured) | issue → separate PR |
| **F-2** | The Strategy form tells the user "Allow Hedge … **Ready Check blocks it**" on the **default** config, where Ready Check demonstrably does **not** block | UI ↔ Ready Check parity defect (measured) | issue → separate PR |
| **F-3** | `same_candle_entry_exit` and `stop_priority_order` are the only conflict fields **missing from the diagnostics provenance block** that carries all their siblings | provenance gap (measured) | issue → separate PR |
| **F-4** | **6 of doc 02 §5.9's 12 canonical rows have no typed field at all**; 3 shipped rows carry a **default that differs from the canonical default** | canonical gap / product decision | issue → product decision |
| **F-5** | `overlapping_signal_policy` (all 4 values), `same_candle_entry_exit` (3 of 5 values) and an explicit `most_conservative` have **no test**; six conflict fields sit **outside** the capability-matrix exhaustiveness guard | test gap | issue → separate PR |
| **F-6** | `docs/POST_V1_SPEC_GAP_BACKLOG_ROUND3.md` declares "**S5b** conflict matrix eksik alanları (doc 02 §5.9)" **fully closed** on the strength of 4 rows out of 12 | stale doc | **fixed docs-only in this PR** |

No production behaviour was changed. F-1…F-5 are filed as issues with paste-ready prompts
(§6); F-6 is corrected in this PR because it is a documentation claim, not behaviour.

---

## 1. Canonical authority and what it demands

The authority chain for this slice is:

1. `docs/spec/Entropia_V18_Master_Technical_Reference_v1_0.md` **§13 (Bölüm 9)**, line 7646 —
   the 12-row conflict rule table.
2. `docs/spec/02_Entropia_V18_Add_Strategy_Strategy_Details_Page_Documentation_v1_1.md` **§5.9**, line 1239 —
   the same 12 rows **with the V18 default and the full option set per row**. This is the
   page-level authority and is more specific than the Master Reference.
3. `docs/spec/index_guncellenmis_duzeltilmis_v18.html` — the visual prototype renders
   **12 `<select>` controls** under `9. CONFLICT / POSITION HANDLING RULES`
   (offsets 204907 → 208304), matching doc 02 §5.9 row for row.

All three agree: **12 rows**.

### 1.1 Canonical rows vs. shipped typed fields

`ConflictPositionHandling` (`backend/src/entropia/domain/strategy/config.py:997-1056`)
exposes **6 fields**; `ProtectionStopLogic` (`:602-666`) adds 3 more. Measured field set:

```
['exit_on_opposite_signal', 'opposite_direction_hedge', 'overlapping_signal_policy',
 'same_candle_entry_exit', 'same_direction_stacking', 'stop_exit_conflict']
```

| # | doc 02 §5.9 row | Canonical default | Shipped field | Shipped default | Verdict |
|---|---|---|---|---|---|
| 1 | Long + Short | Ignore Both | — | — | **missing** (structurally unreachable, §3.9) |
| 2 | Entry + Exit *(in-position)* | Exit Has Priority | — | — | **missing** |
| 3 | Entry + Restriction | Restriction Blocks Entry | — (no `action` field on `RestrictionFilter`) | hardcoded block | **missing** |
| 4 | **Stop + Exit** | Stop Has Priority | `stop_exit_conflict` | `stop_has_priority` ✅ | **shipped, default matches** |
| 5 | **Multiple Stops** | **First Trigger Wins** | `stop_conflict_resolution` | `most_conservative` ⚠️ | **shipped, default DIFFERS** |
| 6 | Scaling + Stop | Stop Blocks Scaling | — | fixed ordering | **partial** (§3.3) |
| 7 | Open Pos. + Opposite | Close Current, Then Wait | `opposite_direction_hedge` (3 of 5 opts) | `allow_hedge` ⚠️ | **partial, default DIFFERS** |
| 8 | **Same Candle Entry / Exit** | Use Intrabar Data If Available | `same_candle_entry_exit` | same ✅ | **shipped, default matches** |
| 9 | Same-Direction Signal | Add Layer If Scaling Allows | `same_direction_stacking` | `allow_stacking` ⚠️ | **shipped, default DIFFERS** |
| 10 | Opposite-Direction Signal | Close Current, Then Wait | — (folded into #7) | — | **missing as a separate policy** |
| 11 | Allow Multiple Same Direction | No | — | — | **missing** |
| 12 | Allow Opposite While Open | No | — | — | **missing** |
| — | *(not a canonical row)* | — | `overlapping_signal_policy` | `queue_sequential` | **extra field, no canonical parent** |
| — | Stop Mode (doc 02 §5.6 / Master Ref §9.1) | Any Active | `stop_trigger_requirement` | `any_active` ✅ | **shipped, default matches** |

Measured defaults (probe A/D, §5.1):

```
overlapping_signal_policy : queue_sequential      stop_trigger_requirement  : any_active
same_direction_stacking   : allow_stacking        stop_conflict_resolution  : most_conservative
opposite_direction_hedge  : allow_hedge           stop_priority_order       : null
exit_on_opposite_signal   : true
stop_exit_conflict        : stop_has_priority
same_candle_entry_exit    : use_intrabar_data_if_available
```

`grep` over `backend/src/entropia` for `long_short`, in-position `entry_exit`,
`stop_blocks_scaling` / `reduce_scal*`, `allow_multiple_same*`, `allow_opposite_while*`
returns **zero** hits — rows 1, 2, 6, 10, 11, 12 are absent, not renamed.

> **Note on renaming.** Rows 4/5/8 and Stop Mode *were* renamed rather than missing — that
> is exactly the lesson `POST_V1_SPEC_GAP_BACKLOG_ROUND3.md` records. Rows 1/2/6/10/11/12
> are a different case: the audit searched for the canonical *concept*, not only the
> canonical token, and found no field, no engine branch and no capability row.

---

## 2. Status legend

| Status | Meaning |
|---|---|
| `complete` | Canonical options, default, saved path, engine consumer, diagnostics and tests all present and consistent. |
| `complete_with_disclosed_downgrade` | Shipped faithfully, but some option values share one executed behaviour **and the boundary is disclosed** in a user-reachable surface (trace event / diagnostics / capability note). |
| `honest_future_dev` | Not executed, and gated fail-closed at Ready Check **and** the engine, with the dependency named. |
| `partial` | Some canonical options/behaviour shipped, the rest silently unreachable. |
| `missing` | No typed field, no engine branch, no disclosure. |
| `canonical_gap` | The spec itself is silent or self-contradictory; a decision is required before code. |
| `product_decision_required` | Behaviour is defensible but diverges from canon; a human must ratify or reject. |

---

## 3. Per-row evidence

### 3.1 Stop + Exit — `complete_with_disclosed_downgrade`

| Attribute | Evidence |
|---|---|
| **Canonical options** | doc 02 §5.9: Stop Has Priority; Exit Has Priority; Record Both Reasons; First Trigger Wins |
| **Saved path** | `conflict_position_handling.stop_exit_conflict` |
| **Enum / literal** | `config.py:1030-1038` — exactly the 4 canonical values |
| **Default** | `stop_has_priority` — **matches canon** |
| **UI** | `StrategyConfigForm.tsx:764-769` `SelectField` "Stop + Exit conflict"; options `strategyForm.ts:260-265`; ⓘ panel `strategyForm.ts:111-114` |
| **Round-trip** | extract `strategyForm.ts:490` · merge `strategyForm.ts:666` |
| **Compiler** | none required (a policy token, not a pinned dependency) |
| **Capability matrix** | not enumerated — every value executes, so the matrix (which enumerates only what is *gated*) correctly omits it (`capabilities.py:676-684`) |
| **Ready Check** | no blocker — correct, nothing here is unmodelled |
| **Engine consumer** | `engine.py:890` read → `engine.py:2260-2302` collision branch |
| **Ordering** | Fires **only** when the exit also fills this bar (`exit_sched == "immediate"`, `engine.py:2260`). A deferred exit loses to an intrabar stop via the `elif` at `:2303` — no collision is claimed where none exists. |
| **Tick dependency** | none. The tie is resolved *structurally*: the stop is an intrabar high/low touch, the exit signal is close-derived, so the stop precedes the close by construction (`config.py:1026-1029`). This is a determinism claim, **not** an approximation — correctly, no `approximated` flag is emitted here. |
| **Diagnostics** | `stop_exit_conflict` + `stop_exit_collisions` (`output.py:451-452`) |
| **Manifest** | pinned transitively — the immutable strategy revision carries the field; `build_run_manifest` (`manifest.py:180`) pins the revision + composition fingerprint + `engine_version`, not inline field values |
| **Version history** | landed PR #208; collision event made **unconditional** by F-10 (`engine.py:2271-2273`) |
| **Tests** | all four values: `test_backtest_engine.py:654, :668, :683, :697`; golden digest `test_backtest_engine_golden.py:123-131` + `engine_golden_digests.json:18` |

**Disclosed downgrade.** *Measured* (probe H): only `exit_has_priority` changes the trade
outcome; `stop_has_priority`, `record_both_reasons` and `first_trigger_wins` execute the
stop identically. This is disclosed: since F-10 the `stop_exit_collision` event is emitted
on **every** collision carrying `executed`, `also_triggered` and the governing `policy`, so
a reader of the trace sees that the stop executed under `first_trigger_wins`. **Verdict:
honest.**

---

### 3.2 Multiple Stops — `complete_with_disclosed_downgrade` (⚠ default diverges)

| Attribute | Evidence |
|---|---|
| **Canonical options** | First Trigger Wins; Most Conservative Stop Wins; Priority Order; Record All / Execute Highest Priority |
| **Saved path** | `protection_stop_logic.stop_conflict_resolution` (+ `stop_trigger_requirement`, `stop_priority_order`) |
| **Enum / literal** | `config.py:641-666` — exactly the 4 canonical values |
| **Default** | `most_conservative` — **canon says `First Trigger Wins`** ⚠ (see F-4b) |
| **UI** | `StrategyGraphForm.tsx:1335-1340` "Same-bar resolution"; `:1329-1334` "Stop mode"; ordered-list editor `StopPriorityEditor` `:1217-1309`, rendered only for `priority_order` / `record_all_execute_highest` (`:1342`) |
| **Round-trip** | extract `strategyGraph.ts:835-837` · merge `strategyGraph.ts:1128-1136`; preserved across a flat Apply (`strategyForm.ts:593-597`) |
| **Capability matrix** | no `protection_stop_logic.*` path exists — see F-5 |
| **Ready Check** | no blocker |
| **Engine consumer** | **real, not decorative**: `fills.py:518-615 _resolve_stop` — builds the enabled-rule set from price stops + logic blocks, applies `stop_trigger_requirement` as the AND/OR gate (`:567-569`) and `stop_conflict_resolution` as the winner rule (`:571-608`) |
| **Ordering** | `_stop_priority_index` (`fills.py:492-504`) always yields a **total, deterministic** order: an explicit `stop_priority_order` leads, every omitted key is appended in canonical §9.2 order (logic blocks in display order, then percentage, trailing, absolute). `most_conservative` uses `(distance, priority)` so ties break deterministically. |
| **Tick dependency** | **the only genuinely tick-dependent row.** `first_trigger_wins` resolves the true first touch from the print path when ticks exist (`fills.py:578-598`); without ticks — or when the print path never reaches a triggered level — it falls back to `most_conservative` and sets `approximated_first=True` (`:599-600`). |
| **Diagnostics** | `stop_trigger_requirement`, `stop_conflict_resolution`, `logic_stop_triggers`, `tick_first_trigger_resolutions` (`output.py:454-456, :499`); per-event `stop_resolution` with `first_trigger_approximated` and (only when real) `first_trigger_tick_resolved` (`engine.py:1743-1753`). **`stop_priority_order` is not published** — see F-3. |
| **Version history** | landed PR #259; logic-stop blocks F-08; tick resolution F-07i (B) |
| **Tests** | 9 `_resolve_stop` unit tests `test_backtest_logic_stop.py:137-215`; 5 tick-path tests `test_backtest_intrabar_execution.py:242-296`; 2 event tests `:374, :390`; 2 engine-level `test_backtest_logic_stop.py:368, :376` |

**Prompt question — "is Multiple Stops a real consumer or only an enum?"**
**Real consumer, verified.** `_resolve_stop` branches on both fields and the branches are
proven to change the executed price and reason (`test_backtest_logic_stop.py:184` picks
`absolute`@98 under an explicit priority list where `most_conservative` would pick
`percentage`@99).

**Prompt question — `any_active` / `all_active` determinism.**
Deterministic. `all_active` is exact set equality against the *enabled* key set
(`fills.py:568`), so it cannot fire on a partial trigger; tested both ways at
`test_backtest_logic_stop.py:166, :172, :262`. Diagnostics echo the requirement and the
`stop_resolution` event carries it per firing.

**Prompt question — does `first_trigger_wins` state its OHLCV authority boundary honestly?**
**Yes.** Three separate surfaces say the same thing: the schema description
(`config.py:653-654`), the code (`fills.py:578-600`), and the **per-event**
`first_trigger_approximated: true` flag. Crucially the flag is per event, not per run, so a
reader can tell exactly which bars were approximated. The complementary flag
`first_trigger_tick_resolved` is stamped **only** when a real print order decided it
(`engine.py:1752-1753`), so a tick-less trace stays byte-identical rather than carrying a
misleading `false`. **Verdict: honest, and better than the minimum the spec asks for.**

**Disclosed downgrade / divergence.** The default is `most_conservative`, not the canonical
`First Trigger Wins`. The in-code rationale (`config.py:613-614`) is that
`any_active + most_conservative` reproduces pre-F-08 behaviour byte-for-byte. That is a
defensible engineering decision, but it is **not recorded anywhere outside a source
comment** and it silently contradicts the page spec. → **F-4b, product decision.**

---

### 3.3 Scaling + Stop — `partial`

| Attribute | Evidence |
|---|---|
| **Canonical options** | Stop Blocks Scaling *(default)*; Allow Scaling; Reduce Scaling Size |
| **Saved path** | **none** |
| **Enum / literal** | **none** — `grep -rniE "stop_blocks_scaling|reduce_scal"` over `backend/src/entropia` → 0 hits |
| **Default** | n/a |
| **UI** | **no control** (the v18 prototype has one, offset 206579) |
| **Capability matrix / Ready Check** | **not represented** — no `future_dev` row, no blocker |
| **Engine consumer** | **fixed ordering, not a policy.** Within one bar the stop/exit block runs at `engine.py:2230-2340`; the scaling ladder runs later at `:2946-3110` behind `position is not None and … len(led.trades) == trades_before_bar` (`:2947-2951`), and `trades_before_bar` is captured at bar start (`:1782`). A stop that fires this bar sets `position = None` **and** appends a trade row, so **both** guards fail. |
| **Ordering** | The engine therefore implements exactly the canonical **default** ("Stop Blocks Scaling"), unconditionally. |
| **Tick dependency** | none |
| **Diagnostics** | none for this rule (`scale_layers_added` / `scale_layers_rejected` exist but do not name a stop as the blocker) |
| **Tests** | no test targets *this rule*; the ordering is an emergent property of two guards |

**Prompt question — "is Scaling+Stop a separate option or fixed ordering?"**
**Fixed ordering.** The shipped engine hardcodes the canonical default. The user cannot
select `Allow Scaling` or `Reduce Scaling Size`, and — unlike `allow_hedge` — nothing tells
them so: there is no capability row, no Ready Check blocker and no UI note. The behaviour is
*correct for the default*; the gap is that two canonical options are silently unreachable.
→ **F-4a.**

---

### 3.4 Opposite Signal / hedge — `partial` + `honest_future_dev` (⚠ UI parity defect)

| Attribute | Evidence |
|---|---|
| **Canonical options** | **two separate rows**, 5 options each — "Open Pos. + Opposite" and "Opposite-Direction Signal": Close Current, Then Wait; Ignore; Close Current; Close Current, Then Reverse/Open Opposite; Hedge If Allowed. Plus "Allow Opposite While Open" (No / Yes / Only Hedge Mode). |
| **Saved path** | `conflict_position_handling.opposite_direction_hedge` + `.exit_on_opposite_signal` |
| **Enum / literal** | `config.py:1014-1020` — **3** values + a bool |
| **Default** | `allow_hedge` + `exit_on_opposite_signal=true` — canon says "Close Current, Then Wait" / "No" ⚠ |
| **UI** | `StrategyConfigForm.tsx:757-763` (the **only** conflict control carrying `capabilityField`) + checkbox `:776-780` |
| **Round-trip** | extract `strategyForm.ts:485-489` · merge `:664-665` |
| **Capability matrix** | `capabilities.py:526-548` — `close_existing`/`ignore` = `active_v1`; `allow_hedge` = `future_dev`, blocker `STRATEGY_CONFLICT_HANDLING_UNSUPPORTED`. Mirrored at `engineCapabilityMatrix.generated.ts:508-530`, pinned byte-for-byte by `test_capability_matrix.py:490`. |
| **Ready Check** | `validators.py:644-655` (`conflict_handling_is_modelled`) + `:434-447` (`future_dev_selections` → `STRATEGY_CAPABILITY_NOT_IN_BUILD`) |
| **Engine consumer** | `engine.py:557-576` fail-closed gate (shared predicate) + `:2680-2730` policy branches |
| **Diagnostics** | `opposite_direction_hedge`, `exit_on_opposite_signal`, `conflict_handling_modelled`, `opposite_signal_closes`, `conflict_signals_ignored` (`output.py:444-450`) |
| **Tests** | engine `test_backtest_restrictions.py:573, :583, :599, :609`; predicate `:305`; readiness `test_readiness_validators.py:558, :573`; capability `test_capability_matrix.py:369, :444` |

**Prompt question — `allow_hedge` Future-Dev UI / Ready Check / engine parity.**

The **backend** three-way parity is exact and deliberate: `conflict_handling_is_modelled`
(`engine.py:573-576`), the capability reader `_read_opposite_hedge` (`capabilities.py:638-645`)
and the Ready Check blocker all apply the *same* rule — with `exit_on_opposite_signal` ON the
position closes before the hedge branch is reached, so the saved `allow_hedge` is **inert**
and correctly does **not** block. Measured (probe B/C):

```
DEFAULT (allow_hedge + exit_on_opposite=True):
  future_dev_selections()       : []          conflict_handling_is_modelled : True
HEDGE  (allow_hedge + exit_on_opposite=False):
  future_dev_selections()       : ['conflict_position_handling.opposite_direction_hedge=allow_hedge']
  conflict_handling_is_modelled : False
```

**The frontend breaks that parity.** `SelectField` decides its capability note from the
*value alone* — it has no access to `exit_on_opposite_signal`
(`StrategyConfigForm.tsx:152-162`, note text `:190-201`). Because the form default for
`opposite_direction_hedge` is `allow_hedge` (`strategyForm.ts:365`), **a brand-new strategy
renders the note "Allow Hedge is saved but will not run — Ready Check blocks it"** while
Ready Check demonstrably does not block it and the run trades normally
(`test_capability_matrix.py:444` proves the run trades). The note's own dependency sentence
then contradicts its preamble ("Accepted only as an INERT value when 'exit on opposite
signal' is ON"). The error direction is *safe* (over-warning, never under-warning), but a
false blocker claim on the default form is a real defect. → **F-2.**

**Canonical divergence.** Two canonical 5-option rows plus a 3-option permission row are
collapsed into one 3-value enum and a bool; `Close Current, Then Wait` and
`Close Current, Then Reverse` have no representation, and the shipped default (`allow_hedge`)
is the canonical *last* option rather than the canonical default. → **F-4a/F-4b.**

---

### 3.5 Same Candle Entry / Exit — `complete_with_disclosed_downgrade` (⚠ two gaps)

| Attribute | Evidence |
|---|---|
| **Canonical options** | Use Intrabar Data If Available; Exit First; Stop First; Ignore Trade; Conservative Rule |
| **Saved path** | `conflict_position_handling.same_candle_entry_exit` |
| **Enum / literal** | `config.py:1047-1056` — exactly the 5 canonical values |
| **Default** | `use_intrabar_data_if_available` — **matches canon** |
| **UI** | `StrategyConfigForm.tsx:770-775`; options `strategyForm.ts:270-276` |
| **Round-trip** | extract `strategyForm.ts:491-494` · merge `:667` |
| **Capability matrix / Ready Check** | not enumerated / no blocker |
| **Engine consumer** | `engine.py:895` read → `:1828-1852`. Scope is **flat position only** (`position is None and entry_signal is not None and exit_hit`). |
| **Ordering** | Runs immediately after signal aggregation (`:1824-1826`) and **before** the stop evaluators advance (`:1856`), so a suppressed entry can never leak into the stop path. |
| **Tick dependency** | **none, and the event says so.** `use_intrabar_data_if_available` cannot invent an order because both decisions are close-confirmed; the event stamps `intrabar_order_available: False` unconditionally (`engine.py:1847`) rather than pretending a tick path would help. |
| **Diagnostics** | ⚠ **the policy token is NOT published** — measured: `'same_candle_entry_exit' in diagnostics → False`, while all five sibling conflict fields are published (`output.py:440-455`). Only the shared `suppressed_entries` counter (`:518`) reflects it, and that counter is also incremented by two unrelated paths (`engine.py:2427, :2447`). → **F-3** |
| **Manifest** | pinned transitively via the strategy revision |
| **Version history** | landed **PR #513**, `ENGINE_VERSION` bumped to `backtest-engine-v18-same-candle-entry-exit` |
| **Tests** | `test_backtest_engine.py:715` (default) · `:731` (`exit_first`) · schema default `test_strategy_config_validation.py:745` |

**Prompt question — verify the #513 same-candle chain in real code and tests.**
Verified. PR #513's claims hold: the five values are saved, the engine resolves the
flat-position collision, the `entry_exit_collision` event carries policy + resolution, the
form select round-trips, and the engine namespace was bumped. Measured (probe G):

```
use_intrabar_data_if_available  trades=0 collisions=7 resolution=ambiguous_entry_suppressed
exit_first                      trades=4 collisions=4 resolution=flat_exit_noop_then_entry
stop_first                      trades=0 collisions=7 resolution=ambiguous_entry_suppressed
ignore_trade                    trades=0 collisions=7 resolution=ambiguous_entry_suppressed
conservative_rule               trades=0 collisions=7 resolution=ambiguous_entry_suppressed
```

Four of five values share one executed behaviour, distinguished only by the `policy` echo in
the event — which matches what `config.py:1044-1046` claims, so the downgrade is disclosed
*in the trace*. Two defects sit on top of it:

1. **F-1 (contract defect).** The `entry_exit_collision` event type is **missing from
   `DECISION_TRACE_EVENT_TYPES`** (`output.py:42-71`), whose own comment calls itself "the
   full event taxonomy the bar-replay engine emits". Its sibling `stop_exit_collision` is
   present. Measured:

   ```
   emitted signal-journal event types : ['entry_exit_collision']
   >>> EMITTED BUT NOT PUBLISHED IN THE TAXONOMY: ['entry_exit_collision']
   entry_exit_collision in DECISION_TRACE_EVENT_TYPES: False
   stop_exit_collision  in DECISION_TRACE_EVENT_TYPES: True
   ```

   A consumer that treats the published `decision_trace_event_types` as complete cannot
   discover the event. **No guard catches this**: the pin test
   (`test_backtest_decision_trace.py:258-268`) asserts the diagnostics *echo* equals the
   constant — a self-consistency check that says nothing about what the engine actually
   emits.
2. **F-3 (provenance gap).** The policy token is absent from the diagnostics provenance
   block; `stop_priority_order` is missing for the same reason.
3. **F-5 (test gap).** `stop_first`, `ignore_trade` and `conservative_rule` have **no
   dedicated test** — nothing would fail if one of them silently started admitting entries.

---

### 3.6 Same-direction multiple positions — `partial`

| Attribute | Evidence |
|---|---|
| **Canonical options** | "Same-Direction Signal": Add Layer If Scaling Allows *(default)*; Ignore New Signal; Open Separate Position; Reset Entry Price. **Plus** "Allow Multiple Same Direction": No *(default)*; Yes; Only If Scaling Allows. |
| **Saved path** | `conflict_position_handling.same_direction_stacking` |
| **Enum / literal** | `config.py:1007-1012` — `allow_stacking`, `replace_existing`, `scale_existing`, `ignore` |
| **Default** | `allow_stacking` — canon says "Add Layer If Scaling Allows" (= `scale_existing`) ⚠ |
| **UI** | `StrategyConfigForm.tsx:751-756`; options `strategyForm.ts:245-250` |
| **Round-trip** | extract `strategyForm.ts:481-484` · merge `:663` |
| **Engine consumer** | `engine.py:1091` read → `:2680-2740`. `scale_existing` **delegates** growth to the scaling ladder and traces `stacking_scale_only` with `scaling_enabled` (`:2712-2727`) — so "only if scaling allows" is honoured rather than faked. |
| **Diagnostics** | `same_direction_stacking`, `stack_entries_added`, `stack_entries_rejected`, `positions_replaced`, `conflict_signals_ignored` (`output.py:443-450`) |
| **Tests** | all four values: `test_backtest_restrictions.py:487, :502, :511, :523`; cap rejection `:535`; restriction interaction `:552`; proxy inertness `:624` |

**Findings.** The four shipped values map onto the four canonical ones (Add Layer→`scale_existing`,
Ignore→`ignore`, Open Separate→`allow_stacking`, Reset Entry→`replace_existing`), but the
mapping is **nowhere recorded**, so a reader comparing the UI to the spec sees four different
labels. The shipped default picks the canonical *third* option. The separate canonical row
"Allow Multiple Same Direction" (whose canonical default `No` would forbid stacking outright)
has no field at all — the shipped default does the opposite of that canonical default.
→ **F-4a/F-4b.**

---

### 3.7 Overlapping / pending signals — `partial`

| Attribute | Evidence |
|---|---|
| **Canonical options** | **none — this row does not exist in doc 02 §5.9, the Master Reference §13, or the v18 prototype.** |
| **Saved path** | `conflict_position_handling.overlapping_signal_policy` |
| **Enum / literal** | `config.py:1000-1005` — `queue_sequential`, `cancel_pending`, `merge_signals`, `ignore_if_active` |
| **Default** | `queue_sequential` |
| **UI** | `StrategyConfigForm.tsx:745-750`; options `strategyForm.ts:238-243` |
| **Round-trip** | extract `strategyForm.ts:477-480` · merge `:662` |
| **Engine consumer** | **none.** `engine.py:1093` reads it into `overlap_policy`; the only other use is `output.py:442`, which copies it verbatim into diagnostics. There is no branch anywhere. |
| **Diagnostics** | `overlapping_signal_policy` — echoed verbatim |
| **Tests** | **none behavioural.** Only the schema default (`test_strategy_config_validation.py:740`) and payload round-trips. |

**Measured (probe F): all four values produce a byte-identical run.**

```
queue_sequential  trades=2  fingerprint=9eda937f1fb51a97
cancel_pending    trades=2  fingerprint=9eda937f1fb51a97
merge_signals     trades=2  fingerprint=9eda937f1fb51a97
ignore_if_active  trades=2  fingerprint=9eda937f1fb51a97
```

The engine argues this is *vacuous* rather than *unimplemented*: at most one aggregated
signal exists per evaluation window, because the signal-block rule plus the long-wins
tie-break resolve same-window concurrency first (`engine.py:569-572`). That argument is
plausible and consistent with §3.9 below.

**Why it is still `partial`, not `complete_with_disclosed_downgrade`:** the disclosure lives
**only in a source comment**. The field is echoed into diagnostics verbatim, which reads as
"this policy was honoured"; there is no capability row, no note, and no test. A future change
that makes overlapping signals reachable would silently keep ignoring the setting.
→ **F-5.**

---

### 3.8 Partial close + stop aftermath, and tick-less same-bar ordering — `complete`

| Attribute | Evidence |
|---|---|
| **Saved path** | `position_exit_logic.partial_aftermath` (`move_stop_to_entry`, `trailing_stop`, `lock_in_profit`, `close_all`) |
| **Capability matrix** | enumerated **and** conditional: `_read_partial_aftermath` (`capabilities.py:603-609`) returns `()` when `close_percentage >= 100`, so an unreachable value on a collapsed subtree is correctly **not** a selection |
| **Ready Check** | `trailing_stop` without a configured protection trailing rule → `partial_close_modelled=False`, fail-closed run, warning `partial_close_unsupported:trailing_stop` |
| **Engine consumer** | `apply_partial_aftermath`; interaction with protection stops proven at `test_backtest_leverage_trailing.py:364` (aftermath force-activates the trail; forced anchor `entry*1.02` → the remainder stops at the trailed level) |
| **Diagnostics** | `partial_aftermath`, `partial_close_modelled`, `partial_closes`, `lock_in_locks`, `trailing_lock_in_active` (`output.py:416-423`) |
| **Tests** | unit `test_backtest_scaling_ladder.py:66-113`; predicate + engine `test_backtest_partial_close.py:160-310`; stop interaction `test_backtest_leverage_trailing.py:331, :352, :364` — **all four values covered positively and negatively** |

**Tick-less same-bar ordering** is the honest core of this row and it is proven three ways:
`first_trigger_wins` without ticks stays conservative **and flagged**
(`test_backtest_intrabar_execution.py:278`); with *contradictory* ticks that never reach a
triggered level it **also** falls back rather than guessing (`:287`); and the trace omits
`first_trigger_tick_resolved` entirely on a tick-less bar (`:390`), so absence of evidence is
never dressed up as evidence. **No fabricated intrabar ordering anywhere in this row.**

Minor gap (not a defect): `close_all` has no `apply_partial_aftermath` unit test — it is
proven only at engine level (`test_backtest_partial_close.py:244`).

---

### 3.9 Long + Short (concurrent opposite entry signals) — `missing`, but structurally unreachable

Canon (row 1) wants a 5-option enum defaulting to "Ignore Both". No field exists. The engine
instead resolves ties in `aggregate()` — "long wins a tie" (`indicators.py:1163-1170`).

**The tie is structurally unreachable at that call site.** `_viable_direction`
(`indicators.py:1097-1115`) requires **every** required evaluator's `current_signal` to equal
the candidate direction, and an evaluator holds exactly one signal — so `long` and `short`
cannot both be viable in the same window. The long-wins line is a defensive tie-break over a
state the aggregation model cannot produce, which is also the premise the
`overlapping_signal_policy` vacuity argument rests on (§3.7).

Verdict: the **behaviour** is defensible; the **canonical row** is unrepresented and the
reasoning is recorded only in source comments. → **F-4a.**

---

## 4. Answers to the audit's direct questions

| # | Question | Answer |
|---|---|---|
| 3 | Verify the #513 same-candle chain in real code and tests | **Verified** — chain intact end to end (§3.5). Two defects found *on top of* it: F-1 (event outside the published taxonomy) and F-3 (policy not in diagnostics); three of five values untested. |
| 4 | Is Multiple Stops a real consumer or only an enum? | **Real consumer** — `fills.py:518-615`, branches proven to change executed price and reason (§3.2). |
| 5 | `any_active` / `all_active` determinism and diagnostics | **Deterministic** (exact set equality, total priority order); echoed in diagnostics and per `stop_resolution` event (§3.2). |
| 6 | Does `first_trigger_wins` honestly state the OHLCV authority boundary? | **Yes**, on three surfaces, with a **per-event** approximation flag and a tick-resolved flag stamped only when real (§3.2). |
| 7 | `allow_hedge` Future-Dev UI / Ready Check / engine parity | **Backend parity exact; frontend breaks it.** The default form shows a false "Ready Check blocks it" claim (§3.4). → **F-2** |
| 8 | Is Scaling + Stop a separate option or fixed ordering? | **Fixed ordering** — the canonical default is hardcoded by two guards; the other two canonical options are unreachable and undisclosed (§3.3). |

---

## 5. Reproducing this audit

### 5.1 Probes

The probes are audit instruments, not tests — they live in the session scratchpad and are
**not** committed. Reproduce from `backend/`:

- **Probe 1** — shipped defaults + hedge gating (`future_dev_selections`,
  `conflict_handling_is_modelled` for default vs. hedge-without-exit-on-opposite).
- **Probe 2** — engine equivalence: run `run_engine` once per option value and fingerprint
  `summary + trades + events` (excluding the trivially-different `policy` echo) to measure
  which values change anything.
- **Probe 3** — taxonomy completeness: compare emitted event types against
  `diagnostics["decision_trace_event_types"]`.

All measured outputs quoted in this document come from those three runs.

### 5.2 Verification run for the PR carrying this document

See §7.

---

## 6. Issues raised

F-1…F-5 are filed as GitHub issues, each with a paste-ready prompt. **None of them is fixed
here** — this PR changes no production code. F-6 is corrected in this PR.

| Finding | Issue | Severity |
|---|---|---|
| F-1 `entry_exit_collision` outside the published decision-trace taxonomy | [#532](https://github.com/alimirbagirzade/Entropia/issues/532) | **HIGH** — published contract is incomplete; no guard catches the drift |
| F-2 Strategy form claims Ready Check blocks the default hedge value | [#533](https://github.com/alimirbagirzade/Entropia/issues/533) | **MEDIUM** — false blocker claim on every new strategy; error direction is safe |
| F-3 `same_candle_entry_exit` / `stop_priority_order` missing from diagnostics provenance | [#534](https://github.com/alimirbagirzade/Entropia/issues/534) | **MEDIUM** — the resolved policy is not reconstructable from a Result |
| F-4 6 of 12 canonical §5.9 rows unrepresented; 3 shipped defaults diverge from canon | [#535](https://github.com/alimirbagirzade/Entropia/issues/535) | **HIGH** — product decision; no agent may pick a default |
| F-5 conflict test gaps + six fields outside the capability exhaustiveness guard | [#536](https://github.com/alimirbagirzade/Entropia/issues/536) | **MEDIUM** |

Each issue carries the measured reproduction and a paste-ready prompt. **F-4 is a product
decision** — it explicitly forbids an agent from inventing a default or an option semantics.

---

## 7. Honest boundaries of this audit

- **No production behaviour was measured under a real Postgres run.** The probes drive
  `run_engine` directly with synthetic bars; the DB-backed resolution path is covered by the
  existing integration tests cited, not re-run here.
- **The "structurally unreachable" claims** in §3.7 and §3.9 are proven against the *current*
  aggregation model (`_viable_direction`). They are not invariants enforced by a test — if
  the aggregation model changes, both vacuity arguments must be re-derived.
- **Frontend evidence** (§3.4, and the UI/round-trip rows throughout) is static: file:line
  reads of the components, lib and generated matrix. The false-blocker note in F-2 was
  derived from the rendering logic plus the *measured* backend defaults, not from a rendered
  browser screenshot.
- **Rows 1, 2, 3, 6, 10, 11, 12 were searched by concept, not only by token** — the mistake
  `POST_V1_SPEC_GAP_BACKLOG_ROUND3.md` made. Absence is asserted on the basis of: no schema
  literal, no engine branch, no capability row, no UI control.
