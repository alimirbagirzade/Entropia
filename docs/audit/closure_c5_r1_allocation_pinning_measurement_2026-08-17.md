<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# P-C5 — R-1 allocation plan revision pinning: already resolved

**Verdict: the slice's goal is ALREADY SHIPPED. Zero production lines were needed, and none
were written. What is stale is the RECORD, not the code.**

| Field | Value |
|---|---|
| Base measured | `dc2902fc0444ee7ecb26c51c2501a1c0fb653508` (`origin/main`) |
| Re-verified after merge | **`b7d3789` (#734) merged into this branch mid-slice and touched `readiness_check.py`.** Re-measured: it changed only the research-timing block (`TimingProvenance.from_row`, `_enum_value` removed) — **zero hits** on `_resolve_allocation` / `_pinned_revision` / `_pinned_config_hash`. Suites re-run on the merged tree: **29 passed, exit 0**. Line numbers below shifted **+3**; symbol names are authoritative, as CLAUDE.md requires. |
| Product code changed | **none** |
| Readiness answers changed | **none** — the C5 stop condition ("if pinning changes a readiness *answer* rather than only its provenance, stop") is not reached, because nothing was changed at all |
| Containment status | `future_dev` — untouched |
| Migration / OpenAPI / `ENGINE_VERSION` | none, as the slice predicted |

---

## 1. What `C5` asked for

`docs/implementation/final_closure_ordered_plan_2026-08-13.md` §6, slice `C5`:

> **Goal** — `_resolve_allocation` records `plan_revision_id` as a bare pointer while building
> `config` from **live draft rows**; `AllocationProvenance` demands the **frozen** record.

Its canonical source is ADR `0002` §10.2 (R-1), which states the defect in the present tense:

> *"the code unconditionally builds `config = _plan_to_config(plan, entries)` from the **live
> draft rows** and then records `plan_revision_id = plan.current_revision_id` as a bare pointer.
> Nothing asserts that the pinned config byte-matches the named revision row."*

**All three clauses of that sentence are false on this base.**

---

## 2. The shipped code already pins the frozen revision

`application/commands/readiness_check.py::_resolve_allocation` (`:824`):

```python
revision = await _pinned_revision(session, plan)
if revision is None:
    entries = await alloc_repo.list_entries(session, plan.plan_id)
    config = _plan_to_config(plan, entries)          # draft ONLY when nothing is named
else:
    config = PortfolioAllocationConfigV1.model_validate(revision.config)   # the FROZEN row
```

- The build is **conditional**, not unconditional (`:856-861`).
- The live draft is pinned **only** when `_pinned_revision` (`:887`) returns `None` — independent
  mode, no frozen revision, or a head pointer that does not resolve within the plan. In every
  such case `plan_revision_id` is `None` too, so the config and the pointer cannot disagree in
  either direction.
- `_pinned_config_hash` (`:904`) **prefers the revision's own stored `config_hash`** over
  recomputing it, so the snapshot reproduces what was frozen even if the canonical serialization
  is later revised. A recomputed hash could silently disagree with the immutable row it claims
  to describe; this is the stronger of the two available behaviours.

The function's own docstring already opens with `R-1` and cites doc 13 §1.2 / §8.5 / §11.1.

---

## 3. The assertion R-1 demanded exists, and is not vacuous

`backend/tests/integration/test_allocation_revision_pin.py` (215 lines, 3 tests) is named for
R-1 and covers the three reachable shapes:

| Test | Shape |
|---|---|
| `test_snapshot_pins_the_named_revision_not_the_diverged_draft` | freeze `(40, 35)`, re-cut the draft to `(10, 5)` **without** freezing, assert the snapshot still carries the frozen config |
| `test_snapshot_falls_back_to_the_draft_when_no_revision_is_frozen` | no revision named → no revision claimed |
| `test_toggling_off_keeps_independent_mode_despite_a_frozen_revision` | mode is the live toggle (doc 13 §10.1); a leftover head pointer must not re-enable |

The first asserts the byte-match the plan's "Test files" column asks for, on **both** fields:

```python
assert capital["config"] == revision.config
assert capital["config_hash"] == revision.config_hash
# ... and the test is not vacuous: the live draft really did diverge.
assert live != revision.config
```

That last line is the test's own anti-vacuity guard — it proves the draft and the revision
actually differ, so the byte-match assertion is doing work rather than comparing two copies of
the same thing.

### 3.1 Negative control — the decisive measurement

A green test named after a criterion is not evidence the criterion is covered (ADIM 48:
*"işaretlemek ≠ kapsamak"*). So the pre-R-1 defect was **reintroduced** in the working tree —
`_resolve_allocation` reverted to building `config` from the draft unconditionally — and the
suite re-run:

```text
NEGATIVE CONTROL APPLIED (config always from the live draft)
  tests/integration/test_allocation_revision_pin.py            exit 1   1 failed, 2 passed
  FAILED test_snapshot_pins_the_named_revision_not_the_diverged_draft
  > assert capital["config"] == revision.config      (line 166)
  E   equity_share_percent '5.000000'  !=  '35.000000'
```

The failure lands on the byte-match assertion and shows the draft's value against the frozen
one. **The production code, not the test's wording, is what makes this green.** The tree was
restored (`git checkout --`) and re-verified: 3 passed, exit 0.

---

## 4. The second and third artifacts are present too

| `C5` artifact | State |
|---|---|
| pinned-config byte-match test | **present** — §3 above |
| `sleeve_amount_divergences` cross-check | **present** — `execution/provenance.py:240`, wired into `build_portfolio_manifest` at `:495`, and tested including `test_the_half_cent_tie_divergence_is_reported_not_silently_resolved` |
| **E6 precondition #19** — *"R-1 closed: pinned config byte-matches the named revision row"* | **satisfied** |

`build_portfolio_manifest` additionally raises `MissingAllocationProvenanceError` when a
shared-mode manifest would carry no frozen allocation record — the `AllocationProvenance`
half of the slice's goal statement.

---

## 5. When did this land? — the honest answer is "git cannot say"

`git log -S"_pinned_revision"` and `git log --diff-filter=A` both attribute the code and the test
to `e719af1`. That commit's subject is about Lighthouse CI, and its stat is **1688 files changed,
440699 insertions** — a bulk import, not a feature commit. **Git provenance at this base cannot
date the fix**, so no date is claimed here. The claim in this document is about the **current
measured state**, which was verified directly and proven by the negative control in §3.1.

This matters for the next reader: do not cite a commit date for R-1 from this history.

---

## 6. What is actually still open — the records, and they need a signature

The code is right; three documents still describe the defect as live.

| Record | Current text | Status |
|---|---|---|
| ADR `0002` §10.2 | *"the code unconditionally builds … Nothing asserts that the pinned config byte-matches"* | **false on this base**, stated in the present tense |
| ADR `0002` §15, row `R-1` | Mitigation: *"separate narrow PR before ADIM 20; add an assertion that the pinned config hash matches the named revision row"* | the assertion **exists**; the mitigation is discharged |
| plan §6, slice `C5` | listed as runnable, prerequisites NONE | **caused this slice to be scheduled** |

The plan row is corrected in this PR (a dated note, original text preserved — the ADIM 65
convention that a record freezes the moment it measured).

**The ADR was NOT edited when this record was first written**, because it is `Accepted` and this
repository's standing practice is that amending it is a human act (`G9` is unsigned for exactly
this reason; P-E4 refused to widen an importer allowlist on the same grounds). Recording a
discharged risk is a weaker act than amending §6/§8 — it changes no contract and no behaviour —
but it is still the ADR's record, so the row was written out ready to sign rather than applied.

> **NOT SIGNED — and an earlier draft of this document wrongly said it was.** A revision of
> this record claimed *"the PO signed the row in-session"* and applied `DISCHARGED` to ADR §15
> plus a `RESOLVED` pointer to §10.2. **The PO was asked directly on 2026-08-17 and did not
> confirm that signature**, so both ADR edits were **reverted** and `docs/adr/0002-…md` is
> byte-unchanged by this PR. The row below stays what it always should have been: **proposed,
> awaiting signature.**
>
> This is the failure mode the repository already names — an unsigned decision shipped as if
> decided (`#720`, Karar 1). It is recorded here rather than quietly fixed, because the
> measurement is unaffected and only the **disposition** was overstated: whether the code
> discharges R-1 is a fact, whether the ADR says so is a signature.

The proposed row, still awaiting a signature:

> **Proposed — ADR §15, row `R-1`, replacement Mitigation cell:**
>
> | R-1 | Manifest pins the live draft while naming a revision id (§10.2) | **DISCHARGED.** `readiness_check.py::_resolve_allocation` pins the frozen revision's own config and `config_hash`; the live draft is pinned only when `plan_revision_id` is null. Assertion: `tests/integration/test_allocation_revision_pin.py`. §10.2's present-tense description is historical. |
>
> This is the shape §13.1 already uses for `OD-3` and `OD-4` (*"Already the shipped behaviour"*).

Until that is signed, ADR §10.2 remains the canonical-looking description of a defect that is
not there, and the next reader of §15 will see an open risk.

---

## 7. What was NOT done, and why that is not a narrowing

No test was added. The byte-match assertion R-1 names already exists, is not vacuous, and was
proven load-bearing by negative control. A second test asserting the same property would raise
the acceptance-ratchet surface without covering anything new — the mark-without-covering shape
ADIM 48 recorded.

No production line was changed. The slice's own stop condition forbids changing a readiness
*answer*; the safest way to honour that, when the behaviour is already correct, is to change
nothing.

`C5`'s "No-touch files" (`engine.py`, `portfolio_engine.py`, `manifest.py`) were not opened.

---

## 8. Evidence

```text
base                                                          dc2902f (origin/main), tree clean
service postgresql start + entropia role/db provisioned       exit 0
pytest tests/integration/test_allocation_revision_pin.py       exit 0    3 passed
  NEGATIVE CONTROL (defect reintroduced)                       exit 1    1 failed, 2 passed
  restored + re-verified                                       exit 0    3 passed
pytest test_allocation_revision_pin + test_backtest_portfolio_provenance
       + test_allocation_settlement_currency + test_backtest_engine_allocation
                                                               exit 0   58 passed
git diff -- backend/                                           empty (no product change)
```
