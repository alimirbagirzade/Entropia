# Backtest financial oracles — fixtures and hand calculations

**Slice:** ADIM 12 — independent single-item financial oracle baseline
**Code:** `backend/tests/unit/oracles/` (79 scenarios: 78 passing, 1 `xfail(strict)`)
**Base:** `origin/main` @ `061d6d7`, `ENGINE_VERSION = backtest-engine-v18-same-candle-entry-exit`

---

## 1. What these tests are for

The engine suite already has two kinds of protection, and both stay:

* **golden digests** (`tests/unit/test_backtest_engine_golden.py` + `engine_golden_digests.json`)
  — they detect *change*, but a change that also updates the digest passes;
* **helper unit tests** (`test_backtest_costs.py`, `test_backtest_fills.py`, …) — they call
  `_effective_fill` / `_position_size` / `due_funding_charges` to build their expectations, so
  they agree with those helpers by construction.

Neither answers: **is the number the engine produced the number the arithmetic says it should
be?** These oracles do. Every expected value here was computed by hand from the rule, written
as a literal, and only then compared with the engine. The single production import is
`run_engine` plus the typed inputs it consumes — no arithmetic helper is imported anywhere in
the package.

They exist as the **baseline for the unified-clock work**: they pin what the current
single-item engine does, so a change to the clock can be shown to preserve (or deliberately
change) each number.

---

## 2. Shared geometry

Every fixture opens with **20 flat bars at 100**, so the 20-bar SMA sits exactly at 100 — the
arithmetic of a mean over 20 copies of one number is not in question. **Bar 21** crosses it,
which makes the signal bar known without reading the indicator implementation. The signal
spec uses `validity="current_candle_only"`, so it is an EDGE: live on the cross bar only, and
a later bar cannot silently re-fire an entry and change a ledger a test hand-computed.

Baseline config: 50 units, no costs, `current_candle_close` in and out.
Baseline long: in at **102**, out at **104**, `pnl = (104 - 102) × 50 = 100.00`.

---

## 3. The arithmetic the oracles are computed from

```
half_spread     = spread / 2
slip            = slippage_value / 100
effective buy   = quantize((raw + half_spread) × (1 + slip), 0.01)
effective sell  = quantize((raw - half_spread) × (1 - slip), 0.01)

pnl (long)      = quantize((exit_eff - entry_basis) × size - commission × 2 × fraction, 0.01)
pnl (short)     = the same with the sign of (exit - entry) flipped

drawdown        = peak_equity - equity
exposure        = quantize(closed_notional / equity_before × 100, 0.0001)

funding charge  = quantize(notional × rate × (+1 long | -1 short), 0.01)

percentage stop = entry × (1 ∓ loss_percentage/100)      long / short
trailing level  = extreme × (1 ∓ trail_percentage/100)   once extreme ≥ entry × (1 + lock_in/100)

risk size       = quantize(equity × risk% / 100 / stop_loss_point, 1e-8)
kelly f*        = kelly_fraction × (W - (1 - W) / R),  clamped at 0
kelly size      = quantize(equity × f* / entry_price, 1e-8)
size            = clamp(raw × leverage × strength, min, max)

sleeve          = A0 × wi / 100,  A0 = P0 - R0,  R0 = P0 × r/100   (doc 13 §8.3 verbatim)
sleeve cap      = quantize(sleeve / entry_price, 1e-8)

scale threshold = reference × distance_percent / 100 (adverse)
layer size      = initial × value/100 | current × value/100 | fixed
new basis       = quantize((basis × size + fill × add) / (size + add), 0.01)
```

---

## 4. Worked calculations, by module

### `test_oracle_entry_exit_timing.py` — 10 scenarios

| fixture | calculation | expected |
|---|---|---|
| current candle close, long | in 102 (bar 21 close), out 104 (end of data) | pnl 100.00, equity 10100.00 |
| market fill simulation | identical fill path to the above | 102 in, pnl 100.00 |
| current candle close, short | in 98, out 96, `(96-98)×50×(-1)` | pnl 100.00 |
| next candle open | fill at bar 22's OPEN 103, out 106 | 103.00 in, pnl 150.00 |
| next candle close | fill at bar 22's CLOSE 104, out 106 | 104.00 in, pnl 100.00 |
| deferred entry into a gap up | bar 22 opens 108; a peeking engine would prefer 102 | 108.00 in, pnl 50.00 |
| exit signal, immediate | out at bar 22 close 99, `(99-102)×50` | pnl -150.00 |
| flat-position entry+exit on one bar | default `use_intrabar_data_if_available` | no trade, equity 10000.00 |
| end of data | marked out at the last close 107 | pnl 250.00, reason `end_of_data` |
| signal bar identity | SMA(20) over 20×100 ⇒ cross can only be bar 21 | `bar_seq == 21` |

### `test_oracle_costs.py` — 14 scenarios

| fixture | calculation | expected |
|---|---|---|
| zero cost | control | 102 / 104, pnl 100.00 |
| spread 0.40, long | buy 102+0.20, sell 104-0.20 | 102.20 / 103.80, pnl 80.00 |
| spread 0.40, short | sell 98-0.20, buy 96+0.20 | 97.80 / 96.20, pnl 80.00 |
| slippage 0.5%, long | 102×1.005, 104×0.995 | 102.51 / 103.48, pnl 48.50 |
| slippage 0.5%, short | 98×0.995, 96×1.005 | 97.51 / 96.48, pnl 51.50 |
| spread then slippage | (102+0.20)×1.005 = 102.711 → 102.71; (104-0.20)×0.995 = 103.281 → 103.28 | pnl 28.50 |
| commission 7 | 100.00 - 7×2 | pnl 86.00 |
| cost reaches the run total | | net_profit 86.00, equity 10086.00 |
| funding, long pays | notional 102×50 = 5100; 5100×0.001 = 5.10 | lot 100.00, equity 10094.90 |
| funding, short receives | notional 98×50 = 4900; -4.90 | lot 100.00, equity 10104.90 |
| funding dated after the last bar | cursor never reaches it | equity 10100.00 |
| funding available while flat | consumed, not charged | equity 10100.00 |
| available_time vs event_time | same event, availability day 22 vs 23 | charge lands on bar 22 vs bar 23, both 5.10 |
| empty schedule | | equity 10100.00 |

### `test_oracle_orders.py` — 10 scenarios

| fixture | calculation | expected |
|---|---|---|
| limit at the signal price, touched | limit 102 rests from bar 22, low 101 reaches it | 102.00 in on bar 22, pnl 200.00 |
| limit never touched | lows 103 / 104 vs a 102 limit | no trade, `limit_order_cancelled` |
| convert to market on expiry | 1-candle validity ⇒ fills at bar 22 close 104 | pnl 100.00 |
| minus offset 2 | limit 102-2 = 100, never reached | no trade |
| plus offset 2 | limit 102+2 = 104, reached; fills at the LEVEL | 104.00 in, pnl 100.00 |
| stop entry, opens below the trigger | max(102, open 101) | 102.00 in, pnl 100.00 |
| stop entry gapped through | max(102, open 105) | 105.00 in, pnl 100.00 |
| short stop entry gapped | min(98, open 95) | 95.00 in, pnl 100.00 |
| trigger never reached | highs stay under 102 | no trade |
| trigger offset +3 | trigger 105; bar 22 tops at 104, bar 23 reaches it | 105.00 in on bar 23, pnl 50.00 |

### `test_oracle_protection_stops.py` — 13 passing + 1 `xfail`

| fixture | calculation | expected |
|---|---|---|
| percentage stop, long | 102×0.99 = 100.98, executed at the level | pnl -51.00 |
| percentage stop, short | 98×1.01 = 98.98 | pnl -49.00 |
| absolute stop | level 101 verbatim | pnl -50.00 |
| trailing, activated | activate at 102×1.008 = 102.816; extreme 106 ⇒ 106×0.98 = 103.88 | pnl +94.00 |
| trailing, not activated | needs 102×1.05 = 107.10, high is 102.50 | no stop, pnl -75.00 |
| most conservative | \|102-101.50\| = 0.50 beats \|102-100.98\| = 1.02 | absolute wins, pnl -25.00 |
| priority order (default rank) | percentage → trailing → absolute | percentage wins, pnl -51.00 |
| explicit priority order | `["absolute", "percentage"]` | absolute wins, 101.50 |
| all_active, one rule short | low 101.20 touches 101.50 only | no stop, pnl -35.00 |
| stop+exit, stop priority | V18 default | 100.98, pnl -51.00 |
| stop+exit, exit priority | closes at bar close 99 | pnl -150.00 (99.00 worse) |
| stop+exit, record both | one close, both reasons journalled | 1 trade at 100.98 |
| stop+exit, first trigger wins | stop is intrabar, exit is close-confirmed | 100.98 |
| **gap through the stop (`xfail`)** | bar range 88–92, level 100.98 unattainable; open 90 ⇒ `(90-102)×50` | expected **-600.00**, shipped **-51.00** → **issue #549** |

### `test_oracle_sizing.py` — 13 scenarios

| fixture | calculation | expected |
|---|---|---|
| base size | 50 units | pnl 100.00 |
| risk based | 10000×2%/100 = 200; 200/4 = 50 units | pnl 100.00 |
| fractional Kelly | f* = 0.5×(0.6-0.4/2) = 0.20; 2000/102 = 19.60784314 | pnl 39.22 |
| full Kelly | f* = 0.40; 4000/102 = 39.21568627 | pnl 78.43 (exactly double) |
| negative Kelly edge | 0.3 - 0.7/1 = -0.40, clamped | size 0 |
| max limit | 50 → 20 | pnl 40.00 |
| min limit | 50 → 80 | pnl 160.00 |
| isolated 3x | 50×3 = 150 | pnl 300.00 |
| no leverage with a stale 3 | normalizes to 1x | 50 units, pnl 100.00 |
| cross margin | not modelled | no trade, `leverage_unsupported` |
| **min 80 above max 20** | window unsatisfiable → size 0 | 0-size trade booked → **issue #551** |
| sleeve cap | R0 = 10000, A0 = 90000, Ci = 4500; 4500/102 = 44.11764706 | pnl 88.24, equity 100088.24 |
| unallocated item (wi = 0) | Ci = 0, no fallback to own capital | no trade, equity 100000.00 |

### `test_oracle_position_lifecycle.py` — 8 scenarios

| fixture | calculation | expected |
|---|---|---|
| partial 40%, move stop to entry | lot 20 units at 99 → -60.00; remainder stops at the 102 basis → 0.00 | equity 9940.00 |
| partial 40%, lock in profit | remainder stop pinned to 99 → `(99-102)×30 = -90.00` | equity 9850.00 |
| partial 40%, close all | collapses to a 100% exit at 99 → -150.00 | reason `exit_signal` |
| **partial + commission 7** | lot 14.00×0.4 = 5.60 → -65.60; full close 14.00 → -14.00 | 1.4 round trips → **issue #552** |
| ladder, percent of initial | threshold 102×0.99 = 100.98; +25 at 100.90; basis 7622.50/75 = 101.63 | pnl 177.75 |
| ladder, fixed amount 10 | basis 6109/60 = 101.81666 → 101.82 | pnl 130.80 |
| ladder over the cap | 75 units vs a 60 cap → rejected whole, never trimmed | pnl 100.00, reason `max_total_exposure` |
| ladder disabled | populated subtree, `enabled: false` | byte-identical to no ladder |

### `test_oracle_properties.py` — 10 scenarios

| property | statement |
|---|---|
| money conservation | `final_equity = initial + Σ lot pnl`; `net_profit = final - initial` |
| funding is outside the lots | lots 100.00, net_profit 94.90, difference exactly the 5.10 charge |
| equity curve identity | drawdown 51.00 = peak - equity; exposure 51.0000 = 5100/10000×100 |
| batch invariance | batch sizes 1 / 3 / 8 / 50 give identical summary, trades and event order |
| replay determinism | the same inputs twice give the same ledger |
| disabled settings are free | disabled trailing + absolute ≡ percentage-only, byte for byte |
| date blackout | covers the cross bar → no trade, `filtered_no_entry` on bar 21 |
| consecutive loss filter | `max_losses=1` → second entry refused; 9949.00 vs the control's 9999.00 |
| no fill before its signal | `entry_fill.bar_seq ≥ entry_signal.bar_seq` |
| MTF closed-bar rule | HTF candle 4 publishes on the 10:00 bar, so the entry pays 14.00, not the 12.00 a look-ahead would have taken |

---

## 5. Spec-open conventions these oracles pin

The V18 canon deliberately defers most execution arithmetic to the engine manifest
(Master Ref §10.13: the exact order "bir enum listesi ve engine_version ile manifestte
saklanır"). Where the spec is **silent or open**, these tests pin the SHIPPED convention and
say so in the module docstring — they are a baseline, not a claim the spec mandates it:

| area | spec status | pinned convention |
|---|---|---|
| fill price per execution-timing option | enum only, **no price mapping stated** | close / next open / next close as named |
| spread + slippage sign and order | **no adverse-side rule stated** | adverse both sides; spread first, then the percentage |
| commission per side vs round trip | **not stated** | `commission × 2` per full close |
| funding sign | doc 02 says "düşülür veya … eklenir" | long pays a positive rate, short receives |
| gap through a limit / stop level | **spec silent** | touched limit fills at its level; stop entry at `max(trigger, open)` |
| triggered stop's execution price | **spec silent** (it fixes only the trigger level) | at the level — the one provably-unattainable case is issue #549 |
| default stop precedence | **no canonical order exists**; `priority_order` is user-supplied ids | percentage → trailing → absolute |
| `most_conservative` comparator | qualitative only ("closes earlier / less risk") | tightest adverse distance, canonical rank as tie-break |
| Kelly sizing | **absent from the spec entirely** | `f* = kf × (W - (1-W)/R)`, clamped at 0 |
| min position size | **absent from the spec entirely** | engine-only field |

---

## 6. Divergences found and filed

| # | severity | summary |
|---|---|---|
| [#549](https://github.com/alimirbagirzade/Entropia/issues/549) | high | a protection stop gapped through at the open still books the unattainable level — understates the loss on **every** gapped stop-out, and contradicts the engine's own `max(trigger, open)` rule for stop ENTRIES |
| [#550](https://github.com/alimirbagirzade/Entropia/issues/550) | high / product decision | `base_position_size` is executed as a unit count; canon (and the V18 form's `%` suffix) define it as a percent of resolved capital |
| [#551](https://github.com/alimirbagirzade/Entropia/issues/551) | medium | a `min > max` size window opens a phantom 0-size trade instead of opening nothing, inflating `total_trades` and the loss count |
| [#552](https://github.com/alimirbagirzade/Entropia/issues/552) | medium | a partially-closed position pays 1.4 commission round trips, not the single round trip its booking layer documents |

None of these were fixed in this slice — it is test-only by construction, and each fix
changes engine semantics (an `ENGINE_VERSION` decision plus a golden-digest refresh).

## 7. Honest boundary

These oracles cover the **single-item** engine only. Multi-item co-simulation over a unified
clock, cross-currency FX conversion, and the tick/print execution modes (`intrabar_touch`,
`limit_fill_simulation`, `stop_limit_priority_simulation`, partial-fill policies beyond
`not_allowed`) are **not** covered here: the first two are not implemented, and the third
needs a pinned tick revision, which is a different fixture shape. The partial-fill decision
table stays covered by its existing helper tests.
