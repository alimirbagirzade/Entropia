<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# C1 / E4a — is `_phase_tail`'s scaling section separable?

**Answer: separable as a describe/book PAIR, but NOT orderable before the stacking section
books. For a shared run that is the same as "not separable" — and it makes P-C2 §C.3.8
option (a) mandatory rather than recommended (gate G12).**

`final_closure_ordered_plan_2026-08-13.md` §3 `C1` asks this slice to *size* the question and
concedes the plan's own answer was asserted from the call graph:

> *"P-C2 concedes this separability was asserted from the call graph, **not** from reading the
> 474-line body."*

This is the reading. `_phase_tail` was **not modified** by C1 — it is character-identical to
`origin/main` (verified by extracting the function from both trees and comparing). F3 also
claims `_phase_tail`, so touching it here would have collided.

---

## 1. The body, measured

`_phase_tail` spans **474 lines** and has exactly four top-level sections:

| Lines | Section | What it is |
|---|---|---|
| `:2959`–`:2997` | close-deferred fill | a `pending` exit that fills at this bar's close |
| `:2998`–`:3252` | **stacking / conflict** (~255 lines) | opposite-signal close, stack, replace |
| `:3253`–`:3411` | **the scale ladder** (~159 lines) | the P8 candidate this question is about |
| `:3412`–`:3423` | tail bookkeeping | `prev_entry_signal`, `prev_scale_signal`, `window.append` |

## 2. The scaling section on its own IS a clean describe/book shape

Its guard is a single expression and its writes are a contiguous, identifiable set:

```python
if (
    position is not None
    and scaling_active
    and pending is None
    and len(led.trades) == trades_before_bar
    and position.layers_filled < scale_max_layers
):
```

| Writes | Site |
|---|---|
| `position.scale_reference = bar.close` | `:3300` |
| `position.layers_filled += 1` | `:3367` |
| `led.equity -= commission` | `:3381` |
| `led.scale_layers_rejected` / `led.scale_layers_added` | `:3343` / `:3376` |

Everything before those is candidate computation (cross detection, the S5c per-layer
closed-bar timeframe gate). Mechanically, a `_evaluate_scale` / `_apply_scale` pair is the
same refactor the three phases just received.

## 3. But its guard reads three things the STACKING section writes

This is the finding, and it was measured rather than reasoned:

| The scaling guard reads | The stacking section writes it at |
|---|---|
| `position is not None` | `:3098` (`position = _do_open(...)`), `:3221` (`position = None`) |
| `len(led.trades) == trades_before_bar` | `:3091` `_close(...)`, `:3098` `_do_open(...)`, `:3220` `_close(...)` |
| `position.layers_filled` | indirectly — after `:3098` the position is a NEW one, so `layers_filled` is 0 |

`trades_before_bar` is captured at the TOP of the bar (`_phase_admit`, `:1981`), so both
sections share one *"no trade has been booked on this bar yet"* budget. Booking a stack, a
replace or an opposite-signal close **consumes** it and closes the scaling window.

`pending` is the one guard conjunct the stacking section does **not** write (measured: 0
rebinds), so it is not part of the coupling.

## 4. Why that is fatal for a shared run specifically

For the item's own sequential timeline the coupling is harmless — describe scaling *after*
stacking has booked, which is exactly today's order.

The shared loop cannot do that. ADR-0002 §8's phase order publishes `E(t)` once and collects
every item's intents at P4 **before** arbitrating. A scaling intent cannot be formed at P4,
because whether the item may scale at all depends on whether *this bar's* stacking outcome
booked a trade — and that stacking outcome is itself a capital event the pool must arbitrate.

So modelling scaling as a P8 phase needs **two arbitration rounds per bar**:

```
P4  collect entry/stack intents -> arbitrate -> book
P8  collect scale intents (now that P4 booked) -> arbitrate -> book
```

ADR §8 has one. Adding a second is not a refactor; it changes the versioned engine contract
and every `PortfolioSnapshot` identity assumption that rests on one valuation per tick.

## 5. Consequence for the gates

- **G12 (P8 — scaling on shared runs)**: P-C2 §C.3.7/§C.3.8 recommends *(a) block at
  admission*. This measurement makes (a) the only option that does not reopen ADR §8. If the
  decision goes the other way, the cost is a second arbitration round, not more refactoring —
  that is the honest price tag, and it belongs in the decision entry.
- **`C1`'s stop condition is therefore NOT triggered in the destructive sense.** The plan says
  *"if `_phase_tail`'s scaling section proves inseparable, stop and report"*. It is reported
  here. C1's three-phase split stands on its own and is unaffected: `_phase_tail` was not
  touched, and `run_portfolio` already raises `UnsupportedIntentKindError` for scale intents
  today, so the fail-closed posture is already the shipped one.

## 6. What this does NOT claim

- It does **not** claim the scale ladder is unsplittable. Section 2 shows the opposite.
- It does **not** re-decide G12. That is a product/maintainer signature.
- It does **not** cover the close-deferred-fill or stacking sections' own separability —
  C1 was asked about scaling, and only scaling was read at this depth.
