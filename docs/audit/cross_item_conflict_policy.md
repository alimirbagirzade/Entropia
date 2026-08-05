# Cross-item conflict policy table and the NET capability state

- **Slice:** cross-item conflict / capacity arbitration (ADR 0002 §9, phases P5 / P6b).
- **Module:** `backend/src/entropia/domain/backtest/execution/arbitration.py`.
- **Tests:** `backend/tests/unit/test_backtest_cross_item_arbitration.py`.
- **Status:** pure, contained. **Nothing in production imports it**; the rollback is
  "delete the module". `ENGINE_VERSION`, every golden digest and the containment flag
  (`SHARED_ALLOCATION_STATUS = "future_dev"`) are unchanged.

This document mirrors `CONFLICT_POLICY_TABLE` in prose. The **code is the authority**; this
exists so a reviewer can read the decision without reading the module, exactly as
`portfolio_ledger_accounting.md` does for the shared ledger.

---

## 1. The policy table

| Policy | Executes? | Opposite direction, same instrument | Same direction, same instrument | Separate position books | Shares capital |
|---|---|---|---|---|---|
| `KEEP_SEPARATE` | yes | **allowed** | allowed | yes | **yes** |
| `BLOCK_OPPOSITE` | yes | **blocked** (typed reason + counterparty) | allowed | yes | **yes** |
| `NET` | **no — refused** | undefined | undefined | yes | yes |

`shares_capital` is `True` on every row and is stated rather than assumed. The policy governs
**positions**, never the pool: `KEEP_SEPARATE` keeps separate position *books*, it does not
hand an item a private wallet. The sleeve cap `Ci(t)`, the composition-wide Max Total Exposure
cap and the ledger solvency limit apply identically under every policy (Modül 11 §6.1).

An absent, blank or `KEEP_SEPARATE` token is the absence of a cross-item rule — the same
reading `engine.resolve_portfolio_rules` uses when it returns `None`. **An unknown token is
refused**, not failed closed to blocking: the shipped sequential gate blocks on an
unrecognised token (`engine.py:866-871`), which executes a policy nobody can name; refusing
produces no Result at all, which is strictly safer.

## 2. How a conflict is resolved

Two counterparty shapes, and they are decided differently on purpose.

**Held position — the holder always wins, whatever its pin ordinal.** The shipped rule is
forward-only: *"an EARLIER-pinned item holds the opposite direction, so the LATER-pinned
item's entry is blocked"* (`CrossItemConflictPolicy` docstring). That pin-order half is an
artifact of the sequential loop, which physically cannot see a later item's position while
replaying an earlier one. A merged axis can. What canon states is that conflict rules limit
two items **opening** opposing positions (Modül 11 §6.3), and doc 13 §8.3 forbids
force-rebalancing an open position — so closing a sibling's position to make room is not an
outcome canon offers. ADR §12 retires the forward-only precedence at this slice.

**Two intents at the same tick — the lower `(pin_ordinal, item_id)` is admitted.** This is
ADR §4.4's tie-break applied verbatim. `pin_ordinal` is the manifest's deterministic
`(root_id, selected_revision_id)` sort — never DOM order, never API arrival order, never DB
iteration order (doc 13 §13). Permuting the caller's input cannot change any outcome, because
the order is read from the pinned profile.

**Instrument identity fails closed.** Two KNOWN, different instruments cannot conflict;
anything else may. An unknown identity on either side is treated as potentially the same
instrument and recorded with the shipped L4 gate token
`portfolio_conflict_symbol_unknown_fail_closed` in the diagnostics — verbatim the reading of
`execution/rules.py::conflicts_with_prior`.

**A mandatory P3 intent is never arbitrated.** Stops, exits, funding and fees resolve before
the valuation point (ADR §6 rule 4; Modül 11 §5.2), so by P5 they are already in the ledger.
Offering one to `arbitrate()` raises. A consequence worth naming: a stop that fires at tick
`t` releases its position *before* `PV`, so the opposing item's entry at the same `t` is
admitted — not by an exception, but because there is nothing left to conflict with.

## 3. Capacity contention, and what OD-3 leaves open

`allowed_size = min(desired, remaining sleeve, item risk limits, ledger solvency)`
(doc 13 §8.3) is the shared ledger's own `resolve_capacity`. Arbitration adds the one figure a
per-item question cannot see: **the capital this tick's earlier admissions already committed**.
The ledger is frozen between `PV` and `P7`, so `available_capital` reads the same number for
every item; without a running tally two items would each be granted the whole pool.

- The three **cap** layers clamp — a `capped` outcome is a smaller **admitted size**, not a
  partially filled order (doc 13 §14 test 13).
- The **solvency** layer may only reject, and rejects **whole**: Modül 11 §5.3 —
  *"engine orderi reddeder, kismi fill veya sessiz borrow yapmaz"*. "1000 is left, take 1000"
  is not an available answer.
- A **blocked item's capacity is never handed to a sibling.** The contention loop only ever
  subtracts what an admitted order commits; no branch adds a blocked item's sleeve, share or
  headroom to anybody (doc 13 §8.4 step 6, §13; Modül 11 §6.3). The test proves it by
  comparing the survivor's grant with and without the blocked item present.

> **OD-3 is OPEN.** Canon decides the *response* to a shortfall (reject, never partial, never
> borrow) and that is what ships here. It does not decide **which** of several individually
> affordable intents is refused. ADR §13 OD-3 recommends admitting in
> `(pin_ordinal, item_id)` order until the pool is exhausted — the tie-break the containment's
> own removal condition #4 already commits to — and flags the alternative a reviewer may
> prefer: reject **all** competing intents, the only rule with no systematic ordering
> advantage, at the cost of refusing trades that could have filled.
>
> The recommendation is implemented and **labelled**, not silently adopted:
> `selection_policy="pin_order_admission"` and
> `selection_status="recommended_pending_approval"` travel in every report and in every
> contended decision's diagnostics, so a Result produced under this rule can always be told
> from one produced under a different resolution.

## 4. NET — refused, not downgraded

`NET_SUPPORT_STATUS = "undefined_in_canon"`.

The shipped sequential engine executes `NET` conservatively as `BLOCK_OPPOSITE` and discloses
the downgrade (`engine.py:862-871`, `CONFLICT_POLICY_NET_V1`). **That downgrade is not carried
forward.** Presenting a block as if it were netting advertises a semantics canon has never
defined — the finding of GH #544 — and ADR §9.4 is explicit that the unified clock removes
NET's stated *excuse* without supplying its *meaning*. So this layer raises
`UnsupportedConflictPolicyError` before any decision exists, rather than producing a report
full of blocks that could be read as "NET ran".

Five things must be decided before `NET` can be implemented:

1. **netting price** — at what price two opposing item positions offset;
2. **position custody** — which item's book holds the netted position, and what the other holds;
3. **fee attribution** — whether the offset charges one commission, two, or none;
4. **realized PnL attribution** — how the netted result is split between the two items;
5. **margin / collateral** — what committed capital a netted pair ties up. Master Ref §10.2
   delegates `leverage_mode=cross` to a portfolio risk model that does not exist, so this one
   is blocked on a second gap (ADR §9.5 — cross-margin is explicitly out of scope).

Each is a product decision, not an engineering choice. Any of them guessed here would produce
numbers a user could not audit against canon.

**The shipped path is untouched.** `engine.py`'s NET downgrade still reads exactly as it did
and is pinned by `test_the_shipped_sequential_conflict_gate_is_untouched`, so no replay and no
digest moves. Shared mode remains contained
(`SHARED_ALLOCATION_STATUS = "future_dev"`), so neither path can publish a Result today.

## 5. Reason vocabulary — this layer introduces none of its own

The clock, the intent layer and the shared ledger each had to name states that only exist once
there is a shared axis. Arbitration does not:

| Reason | Source |
|---|---|
| `portfolio_conflict_blocked` | the shipped engine (`engine.py:1446`) |
| `sleeve_zero_capacity` | the shipped engine (`sizing.blocked_reason`) |
| `portfolio_max_total_exposure` | the shipped engine (`engine.py:1474`) |
| `no_requested_size`, `unpriceable_capacity`, `max_position_notional_exceeded`, `ledger_insolvent` | the shared ledger's `LEDGER_LAYER_REASONS` |

What is new at this layer is *which item* is refused, not *what kind of refusal exists*, so a
new vocabulary would only give reviewers two names for one finding. `ARBITRATION_REASONS` is
closed over exactly the set above and a test asserts it.

## 6. Determinism and replay

- Decisions are emitted in pinned `(pin_ordinal, item_id)` order, re-sorted back from the
  P6b pass so the report's shape depends on the manifest and not on how the tick resolved.
- `ArbitrationReport.identity` is a sha256 over the policy version, the selection policy, the
  tick, the snapshot identity and every decision's outcome / reason / binding constraint /
  counterparty / grant. Permuting the inputs leaves it unchanged; changing any outcome moves
  it.
- The module reads only the frozen ledger, the published snapshot, the intents (which name
  their own pinned revision) and the profile map built from the manifest pins. There is no
  session, no query and no `await` anywhere in it — a plan edited after the run cannot change
  how a historical report resolved (doc 13 §11.1).
- `arbitrate()` refuses to run against a writable ledger (`LedgerNotFrozenError`): P5/P6b sit
  between `PV` and `P7` (ADR §8.1), and against an unfrozen ledger a sibling's booking could
  move `E(t)` under the items still being arbitrated.

## 7. Out of scope for this slice (stated so nobody infers otherwise)

- The per-tick **phase loop** / `run_portfolio` entry point.
- **Result attribution**, diagnostics persistence and the signal-event stream. Rejected and
  partial decisions are produced as typed values carrying `item_id`, reason, counterparty and
  binding layer — ready for a Result to record — but nothing here writes one.
- **Manifest fields.** `arbitration_policy_version` lands with the `ENGINE_VERSION` bump at
  the containment-lift slice (ADR §10.3); a test asserts it is still absent from
  `manifest.py`.
- **Containment lift.** `SHARED_ALLOCATION_STATUS` stays `future_dev`.
- **Cross-margin / netting.** ADR §9.4, §9.5.
- **OD-2** (how a position with no fresh bar is marked) — unanswered, and not touched here.
