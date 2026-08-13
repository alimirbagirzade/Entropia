<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# P-A3 — Research provenance · performance residual · observability · drift

**Read-only closure audit, 2026-08-13.** No production code, no test, no issue state was
changed by this session. Everything below is either a measurement taken in this container
or a citation with a `file:line` a reader can re-derive.

---

## 0. Base SHA and environment

| Fact | Value |
|---|---|
| `BASE_SHA` | **`0d8bf8f7134d86d77a7eee10023dadd3d80aab0d`** |
| Expected by the prompt | `31ed27dfc1f3bf7448b0e03c7c732d22d8b758c4` |
| Difference | **one commit**, `0d8bf8f` *"docs: name the PR behind every landed slice heading (#702)"* — merged after the prompt was written |
| Does the difference affect any measurement here? | **No.** `#702` touches `docs/PROJECT_HISTORY.md`, `docs/STAGE2_HANDOFF.md` and `CLAUDE.md` heading lines only; no file under `backend/src`, `frontend/src`, `ops/` or `docs/performance/` is in its diff. Every §0 row below was re-measured at `0d8bf8f` regardless. |
| Alembic head | `0043_i08_registry_strategy_fks` (single head) — matches `repository_facts.md` |
| `documentation-truth` gate | `uv run python ../scripts/generate_repository_facts.py --root .. --check` → **`exit=0`**, *"artefacts fresh, documents classified, no stale claims"* |
| Postgres | 16, local cluster started for this session; `entropia`/`entropia` on `:5432` |
| Working tree at close | clean apart from this file |

### Commands actually run

| Command | Exit | Result |
|---|---:|---|
| `uv run pytest -q --no-cov -rxX tests/integration/test_research_point_in_time_parity.py` | **0** | 16 passed, **1 xfailed** |
| `uv run pytest -q --no-cov tests/integration/test_query_budgets.py` | **0** | 8 passed |
| `uv run pytest -q --no-cov tests/contract/test_alert_rules_contract.py tests/contract/test_alert_notification_contract.py` | **0** | 79 passed |
| `scripts/generate_repository_facts.py --check` | **0** | gate OK |

Two throwaway harnesses were written under `backend/tests/integration/`, run, and
**deleted before commit** (`git status` verified clean). They are reproduced verbatim in
§B.3 and §A.4 so the measurements can be repeated; they are not repo tests and were never
staged.

---

## A. Research provenance (#558)

### A.1 The three artefacts side by side

Sources: `application/jobs/research_data.py::compile_agent_data_bundle` (`:487`),
`::compile_backtest_evidence_bundle` (`:519`), `::_seal_bundle` (`:553`);
`application/commands/backtest_run_context.py::_research_entries` (`:344`);
`domain/backtest/manifest.py::build_run_manifest`.

`✅` = present · `❌` = absent · `⛔` = the field does not exist in the product at all.
"In hash" = whether the value is inside the artefact's own content hash
(`bundle_hash` for the two bundles; `execution_key` **and** `manifest_hash` for the manifest —
`data_time_context` is a member of `execution_content`, `manifest.py:…execution_content`).

| Field (doc 12 §9.1/§9.2) | Agent Data Bundle | in `bundle_hash` | Backtest Evidence Bundle | in `bundle_hash` | Run Context Manifest | in hash |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| `research_revision_id` | ✅ | **yes** | ✅ | **yes** | ✅ `revision_id` | **yes** |
| `research_content_hash` | ✅ | **yes** | ✅ | **yes** | ✅ (`pinned_content_hash` + `revision.content_hash`) | **yes** |
| `usage_scope` | ✅ | **yes** | ✅ | **yes** | ✅ | **yes** |
| `available_time_policy` | ❌ | — | ❌ | — | ✅ | **yes** |
| `available_delay_seconds` | ❌ | — | ❌ | — | ✅ | **yes** |
| `event_time` semantics | ❌ | — | ❌ | — | ✅ `event_time_semantics` | **yes** |
| `frequency_policy` | ❌ | — | ❌ | — | ✅ | **yes** |
| timezone (`source_timezone_mode` / `_iana`) | ❌ | — | ❌ | — | ✅ both | **yes** |
| instrument mapping (`instrument_mapping_ref`) | ❌ | — | ❌ | — | ✅ | **yes** |
| linked market dataset revision | ✅ `market_dataset_revision_id` | **yes** | ✅ | **yes** | ✅ | **yes** |
| market content hash | ✅ | **yes** | ✅ | **yes** | ✅ (via `_data_time_entry`) | **yes** |
| feature definitions | ❌ | — | ❌ | — | ✅ `feature_definitions[]` (id, name, version, hash, approval state) | **yes** |
| `field_definition_version` | ❌ | — | ❌ | — | ✅ | **yes** |
| alignment policy version | ⛔ | — | ⛔ | — | ⛔ | — |
| missing / stale policy | ⛔ | — | ⛔ | — | ⛔ | — |

**Two of the fields the issue lists do not exist anywhere in the product.**
`git grep -n alignment` over `backend/src` returns only tick-alignment diagnostics
(`engine.py:895`, `execution/output.py:182`) and a portfolio-provenance `time_alignment`
block — nothing named an *alignment policy version*. A search for
`missing_policy|stale_policy|missing_data_policy|forward_fill` over `backend/src` returns
**zero** hits. So for those two rows the answer is not "excluded from the hash", it is
"never modelled" — a materially different decision for the PO than adding a field.

`validation_policy_version` and `semantic_meaning_version` are columns on
`ResearchDatasetRevision` (`models/research_data.py:…`) that **no** artefact carries.

### A.2 Does `bundle_hash` cover the timing policy? — **No. Proven.**

`_seal_bundle` (`jobs/research_data.py:553`) hashes exactly
`{bundle_kind, members, compiler_version, …extra}`. A member is the five-field dict above.
`manifest_hash` → `shared/hashing.content_hash` = `sha256(canonical_json(payload))`.

The timing fields are **separate columns**, not payload bytes:
`content_hash=content_hash(payload)` is written once at revision creation
(`repositories/research_data.py:95`, `:136`), while `available_time_policy`,
`available_delay_seconds`, `frequency_policy`, `source_timezone_*` and
`event_time_semantics` are their own mapped columns, written later by
`commands/research_data.py::set_time_policy` (`:549`–`:553`) which **never touches
`payload` or `content_hash`**.

**Can the same `bundle_hash` be produced under two different timing policies? YES — measured.**

Harness: seed a market dataset, approve it; create a research dataset whose head revision is
`VERIFIED` (not yet APPROVED); call the production `rd_cmd.set_time_policy` with
`FIXED_DELAY / 120s`, compile an Agent Data Bundle; call `set_time_policy` again with
`FIXED_DELAY / 7200s` on the same revision, compile again.

```
POLICY_A      = ('fixed_delay',  120, 'fcc1504e…07afbdc')
POLICY_B      = ('fixed_delay', 7200, 'fcc1504e…07afbdc')   <- content_hash IDENTICAL
BUNDLE_HASH_1 = 5d1c403f6e5315685a26b742eb880d0e1ce28e9fd53d3ac06a390c44801d99f6
BUNDLE_HASH_2 = 5d1c403f6e5315685a26b742eb880d0e1ce28e9fd53d3ac06a390c44801d99f6   <- IDENTICAL
```

Both member lists are byte-identical. **The delay changed by a factor of 60 and neither
hash moved.** A bundle therefore cannot attest, from its own contents, which availability
rule it was compiled under.

### A.3 The mitigation in #558's body is **narrower than the issue states**

`#558` says: *"ADIM 13 narrowed the blast radius by freezing the policy once a revision is
approved (`ensure_time_policy_mutable`), so the drift is no longer reachable through
`set_time_policy` after approval."*

That is true of the **Backtest Evidence Bundle** and false of the **Agent Data Bundle**:

| | admits | frozen states reachable? |
|---|---|---|
| `compile_backtest_evidence_bundle` | `admit_bundle_member(for_execution=True)` → revision **must** be `APPROVED` (`jobs/research_data.py:474`–`:477`) | Policy is already frozen at compile time — `TIME_POLICY_FROZEN_STATES = {APPROVED, APPROVAL_REVOKED, DEPRECATED}` — and every state reachable afterwards is also frozen. Pinned by `test_an_approved_revision_cannot_be_retimed_in_place`. |
| `compile_agent_data_bundle` | `admit_bundle_member(for_execution=False)` → any **consumable** state, `DRAFT`/`VERIFIED` included | **Not frozen.** The measurement in §A.2 runs entirely on this path. |

So the invariant the evidence bundle enjoys is held by a **lifecycle freeze, not by the
hash**. That distinction matters for the PO decision: if the freeze were ever relaxed — or
if a new surface compiled an evidence bundle from a pre-approval revision — the hash would
not detect it, because the hash never covered the field. The Agent bundle has no such
freeze today.

### A.4 Strict xfail

| | |
|---|---|
| **Node ID** | `tests/integration/test_research_point_in_time_parity.py::test_both_bundles_pin_the_available_time_policy` |
| Declared at | `tests/integration/test_research_point_in_time_parity.py:580` (decorator), test body `:589` |
| Marker | `pytest.mark.xfail(strict=True)`, reason cites **GH #558** |
| Run result | `XFAIL` — file `exit=0`, 16 passed / 1 xfailed |
| What it pins | that the Run manifest **does** pin `available_time_policy == "fixed_delay"` and that both bundle members **should** and do not. It asserts the *canonical* expectation and fails, rather than asserting the defect. |
| Bug or product decision? | **Product decision.** `repository_facts.md` records exactly 1 xfail (1 strict) in the tree and `CLAUDE.md` already classifies it as a product decision. The code is internally consistent and deterministic; what is undecided is the artefact *shape* (§A.5). Nothing here is a latent crash or a wrong number. |

### A.5 If the hash SHAPE changes — what happens to stored bundles (PO decision, not taken here)

Two shapes are on the table, and doc 12 §9.2 literally spells the second:

1. **Per-member fields** — each member gains the manifest's `revision` sub-dict
   (`available_time_policy`, `available_delay_seconds`, `event_time_semantics`,
   `frequency_policy`, `source_timezone_mode/_iana`, `instrument_mapping_ref`,
   `field_definition_version`). Mirrors code that already exists and is already tested.
2. **Top-level arrays** — `available_time_policies[]`, `feature_definition_revision_ids[]`,
   `instrument_mapping_revision_ids[]`, `alignment_policy_versions[]`,
   `missing_and_stale_policies[]`, as §9.2's field list is written. Two of those five name
   things that do not exist (§A.1), so this shape cannot be adopted whole without also
   deciding whether to model them.

**What happens to already-sealed bundles, measured rather than assumed:**

* `bundle_hash` is **not** a foreign key anywhere. `git grep bundle_hash` over
  `backend/src` returns exactly two lines, both inside `_seal_bundle`. No column stores it,
  no query re-reads it, no gate compares it.
* The sealed body **is** stored in one place that matters: `run_idempotent` keeps the
  command's response in `response_ref`. A replay of a pre-change `Idempotency-Key` returns
  the OLD shape. This repo has already been bitten by exactly that (O-30, `request_purge`
  backfills `deletion_state` on replay) — so a shape change needs the same treatment or a
  deliberate decision to let old replays return the old shape.
* Old bundles cannot be back-filled truthfully for a **draft** revision whose policy was
  edited after sealing: the value at seal time is not recoverable from the row. For
  `APPROVED` revisions it is recoverable, because the freeze makes the live value equal to
  the seal-time value.

**Not decided here.** Options stated, none chosen.

---

## B. Performance — Ready Check N+1 residuals

### B.1 The prompt's premise is confirmed, and it is a **reuse** job for one leg only

| Line | Call | Verdict |
|---|---|---|
| `readiness_check.py:404` | `market_repo.get_revisions(...)` | batched (O-24b) |
| `readiness_check.py:411` | `market_repo.get_dataset_roots(...)` | **batched, correct** (#617 / ADIM 46) |
| `readiness_check.py:554` | `market_repo.get_dataset_root(...)` inside `for item, config, ref in signals:` (`:550`) | **loop-inner N+1** |
| `readiness_check.py:749` | `research_repo.get_dataset_root(...)` inside `for item, config, revision_id in funded:` (`:735`) | **loop-inner N+1** |

`market_repo.get_dataset_roots(session, entity_ids) -> dict[str, EntityRegistry]`
(`repositories/market_data.py:406`) already exists. So:

* **Signal leg (`:554`) — directly reusable, no new repository method.** Both the strategy
  leg and the signal leg dereference **market dataset** roots, and the batch helper applies
  the same `entity_type == "market_dataset"` guard in SQL that `get_dataset_root` applies in
  Python — an absent row and a wrong-type row are equally absent from the map, so the
  fail-closed `MARKET_DATA_DEPENDENCY_BLOCKED` branch stays byte-identical. This is the
  #617 repair applied a second time.
* **Research leg (`:749`) — the helper is NOT reusable, for two independent reasons.**
  (a) **Entity axis:** `market_data.py:33` `ENTITY_TYPE = "market_dataset"`;
  `research_data.py:42` `ENTITY_TYPE = "research_dataset"`. Passing research entity ids to
  the market batch returns an **empty map**, which would silently flip every funding source
  to `root_active=False` — a fail-*open*-looking blocker storm, not a no-op.
  (b) **Module:** `research_data.py` has `get_revision`/`get_revisions`/`get_dataset_root`
  but **no `get_dataset_roots`** (verified by enumerating the module's defs). So this leg
  needs the batch counterpart written, mirroring `market_data.py:406`.

### B.2 Extra round trips per item — **measured, not estimated**

Method: the same `before_cursor_execute` listener and cold-identity-map protocol
`tests/integration/test_query_budgets.py::_all_statements` uses; two sizes in one session.

| Leg | function | n=1 | n=11 | **slope** | extra round trips for n items |
|---|---|---:|---:|---:|---|
| Signal price fallback | `_resolve_signal_market_data_issues` (`:522`) | **2** | **12** | **1.0** | **n** (1 batched `IN()` + n `EntityRegistry` reads) |
| Research funding source | `_resolve_research_sources` (`:705`) | **2** | **12** | **1.0** | **n** (1 batched `IN()` + n `EntityRegistry` reads) |
| *(reference)* market data | `_resolve_market_data_issues` (`:391`) | 2 | 2 | 0 | 0 — repaired by #617 |

The statement dumps confirm the shape exactly: one
`SELECT market_dataset_revision …` / `SELECT research_dataset_revision …` followed by
**eleven identical** `SELECT entity_registry …` statements.

**This is the same defect #617 described, in two legs it never named.** #617's title is
*"the market-data leg still reads one dataset root per Strategy item"* and its acceptance
was scoped to `readiness_check.market_data_leg`. It closed exactly what it named. **No
issue was ever filed for the signal leg or the research leg.**

### B.3 `query_budgets.json` does not measure either leg — and why

`docs/performance/query_budgets.json` has six surfaces. Exactly one is a Ready Check leg:
`readiness_check.market_data_leg`, and `test_query_budgets.py:44` imports **only**
`_resolve_market_data_issues`. Its fixture (`:315`–`:326`) builds `MainboardItemKind.STRATEGY`
items with `payload={"data": {"market_dataset_revision_id": …}}`.

That fixture cannot reach either residual:

* the signal leg is keyed on `MainboardItemKind.TRADING_SIGNAL` with a parseable
  `TradingSignalConfig` whose `price_policy.source` is one of the two OHLCV-fallback modes
  (`_SIGNAL_OHLCV_FALLBACK_SOURCES`, `:83`) **and** a non-null
  `approved_market_data_revision_ref` — a config the strategy fixture never builds;
* the research leg needs `data.funding.enabled = true` with a resolvable
  `source_revision_id`, and the budget fixture's payload does not even carry a `funding`
  block.

So the budget's coverage gap is not an oversight in the gate's design — the gate counts
*every* statement of whatever it is pointed at. It is a **coverage** gap: three of Ready
Check's four resolver legs are not pointed at by any surface.

### B.4 Every other loop-inner single-row read in `readiness_check.py`

The prompt asked for a full scan. There are **six** more, none budgeted:

| Line | Read | Inside | Axis |
|---|---|---|---|
| `:371` | `strat_repo.get_strategy_revision` (via `_resolve_strategy_payload`, called at `:339`) | `for item, available in enabled:` (`:332`) | per Strategy item carrying a §7.1 mirror pin |
| `:472` | `market_repo.find_approved_tick_revision_for_instrument` | `for item in items:` (`:463`) | per tick-requiring Strategy item — **no batch counterpart exists**; it is keyed on `instrument_id`, not `entity_id`, so this one genuinely needs a new query, not a reuse |
| `:638` | `resolve_indicator_plan(session, config)` | `for item in items:` (`:626`) | per Strategy item; itself multi-statement — **not measured here** |
| `:779` | `readiness_repo.resolve_trade_log_batch` (via `_resolve_external`, called at `:341`) | `for item, available in enabled:` | per Trade Log item |
| `:789` | `readiness_repo.resolve_signal_revision` (same caller) | same loop | per Trading Signal item |
| `:850` | `resolve_settlement_currencies(session, available_items)` | not loop-inner — takes the whole list | — (listed only so the scan is complete) |

`:472` and `:638` are called out because they are the two that a "reuse `get_dataset_roots`"
framing does **not** cover.

> **This section is measurement only.** P-E2 is writing `readiness_check.py` in parallel;
> nothing here was changed, and the file is byte-identical to `0d8bf8f`.

---

## C. Observability — four layers, kept apart

**Prometheus firing is not delivery.** The four links are separately shipped, separately
guarded, and only three of the four are gated.

| Layer | What ships it | Gate | Is it a **CI gate**? | Evidence |
|---|---|---|:--:|---|
| **DETECTION** | `infrastructure/observability/metrics.py` (3 HTTP families) + `apps/api/routes/metrics.py` (4 async families: `entropia_jobs_depth`, `entropia_job_lease_age_seconds`, `entropia_worker_heartbeat_age_seconds`, `entropia_outbox_lag_seconds`) → **7 families** | `test_alert_rules_contract.py` derives the allowed metric set **from the exposition code itself** | **YES** — `ci.yml` `Backend` job | 79 contract assertions passed here, `exit=0` |
| **VALIDATION** | `ops/alerts/entropia.rules.yml` — **11 rules, 7 `page` + 4 `ticket`** (counted); `ops/prometheus/prometheus.yml` scrape + `alerting:` block | `promtool check config` + `check rules` + `test rules` over `entropia.rules.test.yml`; `test_every_job_matcher_names_a_declared_scrape_job`; `test_prometheus_sends_its_alerts_to_the_shipped_alertmanager` | **YES** — `ci.yml` job `alerts`, step *"Validate alert rules and scrape config"* (`scripts/alert-rules-gate.sh`) | `ci.yml:254` |
| **ROUTING** | `ops/alertmanager/alertmanager.yml` — root receiver `entropia-page` (a real one), `severity=ticket` child route, 3 inhibit rules, both receivers `url_file`-backed | `amtool check-config` + `amtool config routes test` + `test_alert_notification_contract.py` (structural — `amtool` returns SUCCESS on a receiver with **no** notifier configs, so amtool alone is not enough) | **YES** — `ci.yml:262` (`scripts/alert-notification-gate.sh`) | `ci.yml:262` |
| **DELIVERY** | `ALERTMANAGER_NOTIFY_URL` → operator's receiver; `ops/alertmanager/entrypoint.sh` refuses to exec without a valid http(s) URL (fail-closed) | `scripts/alert-notification-proof.sh` — 4 phases (fail-closed / up / provenance-by-hash / a real `EntropiaApiDown` POSTed to a logging receiver) | **NO** | `git grep alert-notification-proof .github/workflows` → **no match**. Only `alert-rules-gate.sh` (`:254`) and `alert-notification-gate.sh` (`:262`) are wired. |

### C.1 The three known residues — verified, and there are **five**

`docs/runbooks/alert-notification.md` §5 already lists five. All three the prompt names are
confirmed, unchanged:

| # | Residue | Verified how | Status |
|---|---|---|---|
| 1 | **Rules never evaluated against real production series.** `promtool test rules` uses synthetic series; the delivery proof fires one structural rule (`up == 0`). | The rules test file is `ops/alerts/entropia.rules.test.yml`, a fixture. Nothing in the repo ingests production series. | **OPEN — cannot be closed by any gate in this repository.** Not a signed deviation. |
| 2 | **Nothing monitors the monitor.** `prometheus_notifications_errors_total` lives on Prometheus's own `/metrics`. | `ops/prometheus/prometheus.yml` declares **one** `scrape_configs` job — `entropia-api` → `api:8000`. Prometheus does not scrape itself. | **OPEN** |
| 3 | **Delivery proof is not a CI gate.** | grep over `.github/workflows` (above) | **OPEN** |
| 4 | No on-call rotation / escalation / acknowledgement — Alertmanager has no ack concept, `repeat_interval` is the whole mechanism (`1h` page / `12h` ticket). | `alertmanager.yml` route block | **OPEN — organisational, outside this repo** |
| 5 | Per-queue worker liveness unobservable — a dead `worker-backtest` leaves the shared heartbeat fresh. | `METRIC_ALERT_MATRIX.md` §4 | **OPEN — needs a new metric, not a new receiver** |

**Nothing here regressed and nothing here closed.** The honest summary is the one the
runbook already writes: the *config* half of the notification path is gated on every PR;
the *delivery* half is proven by a script an operator has to remember to run.

---

## D. Accessibility (A-08) — record only

Canonical block: `docs/audit/a11y_screen_reader_audit_results.md` §STATUS ▸
*Tracking-issue state*. **#514 was not touched** (`human-only`).

### D.1 Keep these seven things apart

| Category | State | Is it A-08 evidence? |
|---|---|---|
| Automated axe-core ratchet (`specs/13-a11y-scan.spec.ts`) | green, blocking in CI | **No** |
| Keyboard flow (`specs/14-keyboard-flow.spec.ts`) | green | **No** |
| Structural prechecks (`specs/20-a11y-prechecks.spec.ts`) | 23 routes, 0 blocking failures, **67 advisory** (CI job `94221023796`, single cold run) — its own report stamps `screen_reader_verified: false` | **No** |
| Human audit **preparation** | complete (ADIM 28 scaffold, ADIM 44 stack 9/9 + runbook) | **No — preparation is not the audit** |
| Real **NVDA / Firefox / Windows (SR-1)** | **never started** | — |
| Real **VoiceOver / Safari / macOS (SR-2)** | **1 session**, 2026-08-12, auditor = product owner, screen-reader-role `neither` | yes, for 2 cells |
| Findings / retests / signed deviations | **0 findings**, 0 retests, **0 signed A-08 deviations** (none may be written on an agent's initiative) | — |

### D.2 The count, re-derived from the tables (not copied from the banner)

Parsed programmatically from §1's two tables:

| Metric | Value | Note |
|---|---:|---|
| Section A cells, **both** combinations | **2 / 368** | 46 runs × 8 checks |
| Section A cells, **SR-2 half** | **2 / 184** | 23 routes × 8 checks — the banner's framing |
| Section A cells, **SR-1 half** | **0 / 184** | |
| Routes **complete** (all 8 checks) | **0 / 46** | route 1 of SR-2 holds A-1 + A-2 only; partial ≠ complete |
| Flows | **0 / 20** (0/10 per combination) | |
| **Exit criteria met** | **0 / 4** | criteria 3 and 4 are *empty*, not *met* |
| Findings register | placeholder row only | |

Criteria 1 and 2 **cannot** be closed by any SR-2 work: both name both combinations, and a
flawless complete SR-2 run would still leave criterion 1 at `1/2` and criterion 2 at `23/46`.

**Verdict: `A-08 HUMAN-BLOCKED`. No document may show A-08 as `Complete` or `PASS`.**
The `A08_COMPLETE` invariant rule in `generate_repository_facts.py` enforces this in CI.

### D.3 K-1 … K-7 — refreshed

| ID | Subject | Reach | **Status** |
|---|---|---|---|
| K-1 | D-10, 45 accent-blue low-contrast nodes, WCAG **1.4.3** not met | — | **ADJUDICATED** — PO-signed permanent deviation 2026-07-30. Do not re-file. |
| K-2 | No skip link (2.4.1 ergonomics) | was 23/23 | **CLOSED** 2026-08-12, PR #685 |
| K-3 | No `contentinfo` landmark | 23/23 | **OPEN** — reported, not gated. PO. |
| K-4 | `/user-manual` had no `<h1>` | was 1 route | **CLOSED** 2026-08-12, PR #685 |
| K-5 | Heading outline skips h2 (`h1 → h3`) | **22 / 23** (floor — single cold run; ±1 on `/analysis-lab`, `/backtest/history`, `/backtest/metrics`) | **OPEN** — this is checklist A-3, and A-3 on route 1 was deliberately left `—` in the SR-2 session, so **K-5 is exactly as open as before that session** |
| K-6a | Focus indicator not detectable by computed style (2.4.7) | probe: 1 element | **OPEN — only A-08 can close it.** The current probe cannot: a programmatic `el.focus()` does not match `:focus-visible`. |
| K-6b | Focus-ring contrast < 3:1 (**1.4.11**, non-text) | was every focusable node, 23/23 | **CLOSED** 2026-08-12 — ring re-pointed to `var(--text)`; worst measured surface now 4.50:1 (`#0092c8` menu-blue hover) |
| K-7 | No `aria-live` region in the **initial** DOM (4.1.3) | 21/23 (unstable class) | **OPEN** — reported, not gated. Settled by B-3 / B-4 / B-6. |

### D.4 **NEW — drift inside the canonical A-08 document itself**

`docs/audit/a11y_screen_reader_audit_results.md` §6's observation table contains
**three duplicated finding IDs with contradictory contents**:

| ID | line | says | line | says |
|---|---:|---|---:|---|
| K-4 | 462 | **FIXED** 2026-08-12 | **465** | *"Open — reported, not gated"* |
| K-5 | 463 | reach **22 / 23**, `/user-manual` moved in | **466** | reach **21 / 23**, *"unchanged"* |
| K-6 | **464** | pre-split bare `K-6` row (2.4.7 only) | 467 / 468 | `K-6a` + `K-6b`, the split that supersedes it |

`git blame` names the cause precisely: **`ce823a8` (PR #685, ADIM 50)** inserted updated
K-2 / K-4 / K-5 rows *plus a stale bare `K-6` row* at lines 460–464 without removing the
pre-existing rows at 465–466, and without noticing that `04c6a9c0` (ADIM 48) had already
split K-6 into K-6a/K-6b at 467–468. The prose beneath the table uses only the K-6a/K-6b
vocabulary, so the table and its own explanation disagree.

**Consequence:** a reader who scrolls to the first `K-4` row sees FIXED; a reader who
scrolls past it sees Open. Both rows are in the canonical block that every other document
points at. **Not repaired here** — this session is read-only, and re-editing another
slice's record is the mistake ADIM 50 already recorded once. Filed as item **DR-1** below.

---

## E. Documentation and issue-state drift

### E.1 Issue state — measured 2026-08-13, **not changed**

| # | Title (short) | state | `state_reason` | labels | milestone | closing PR (GitHub) | last update |
|---:|---|---|---|---|---|---|---|
| **514** | A-08 human NVDA + VoiceOver acceptance audit | **OPEN** | `reopened` | `human-only` | — | **none** (`total_count: 0`) | 2026-08-12T11:08:58Z |
| **550** | sizing fields execute as unit counts, UI labels them percent | **OPEN** | `reopened` | — | — | none | 2026-08-13T10:30:08Z |
| **551** | three sizing paths open a phantom 0-size trade | **OPEN** | `reopened` | — | — | none | 2026-08-13T10:30:17Z |
| **552** | partial close pays 1.4 commission round trips | **OPEN** | `reopened` | — | — | none | 2026-08-13T12:42:15Z |
| **558** | neither research bundle pins the available-time policy | **OPEN** | `reopened` | `product-decision` | — | none | 2026-08-12T13:25:33Z |
| **559** | DST fold / gap have no canonical rule | **OPEN** | `reopened` | `blocks-mixed-zone-axis`, `product-decision` | **ADIM 16-20 — unified clock programme** | none | 2026-08-12T13:25:47Z |
| **617** | ready-check market-data leg reads one root per Strategy item | **CLOSED** | `completed` | — | — | **#619** *(see trap below)* | closed 2026-08-13T11:07:15Z by `alimirbagirzade` |
| **618** | pinned ESP resolver re-validation costs 2 round trips per pin | **CLOSED** | `completed` | — | — | **none** | closed 2026-08-13T11:07:16Z by `alimirbagirzade` |

**The prompt's measurement is confirmed exactly.** Five `reopened`, two closed `completed`
today at 11:07Z by a human, #514 open with `human-only` and zero linked PRs.

> ### Issue-state drift: **NONE.**
> The ledger and the code now agree on all eight. The "three closed issues hiding a live
> defect" narrative that earlier reports carried is **finished** — it was closed by the
> human's 11:07Z action, not by anything in this audit, and it is not re-derived here.

**The `#617 → #619` trap, resolved from git rather than from the linkage.** GitHub shows
#619 (*"perf(test): establish load and query regression budgets"*, MERGED) as #617's
closing PR. That PR **measured** the N+1 and wrote the budget row; it did not repair
anything. The repair is:

```
git log -S "get_dataset_roots" -- backend/src/entropia/infrastructure/postgres/repositories/market_data.py
6da8a95  perf(query): collapse the readiness and dependency-pin N+1 loops (#617, #618) (#681)
```

**`6da8a95` = PR #681** fixed **both** #617 and #618 — which is also why #618 has no linked
PR at all while being genuinely fixed. Linkage is not provenance.

**Each of the three engine issues was spot-verified live on `0d8bf8f`:**

| # | Claim | Verified at | Still live? |
|---:|---|---|---|
| 550 | `_raw_position_size` returns `base_position_size` verbatim while the UI labels it `%` | `execution/sizing.py:216` returns `Decimal(sizing.base_position_size)`; `StrategyConfigForm.tsx:592` renders `unit="%"` | **YES** |
| 551 | zero-size guard applies only under allocation | `engine.py:1462` — `if alloc_on and size <= _ZERO:` | **YES** |
| 552 | `commission * 2 if is_full else commission * 2 * fraction` | `execution/booking.py:93` — verbatim | **YES** |

(The `file:line` values inside the issue bodies have drifted — `engine.py:1457`→`1462`,
`StrategyConfigForm.tsx:607`→`592`, `research_data.py:452-460`→`:508-514`. Cosmetic; the
symbols resolve.)

### E.2 Documentation drift — findings

| ID | Category | Claim | Reality | Source |
|---|---|---|---|---|
| **DR-1** | docs contradict themselves | `a11y_screen_reader_audit_results.md` §6 shows K-4 as **FIXED** *and* as **Open**; K-5 as **22/23** *and* **21/23**; a superseded bare **K-6** row alongside K-6a/K-6b | Three duplicated IDs, introduced by `ce823a8` (PR #685) | §D.4 above; lines 462↔465, 463↔466, 464↔467/468 |
| **DR-2** | stale test count in a **present-tense** doc | `CLAUDE.md:92` (§Conventions): *"ölçülen toplam **%92.06**, **2712 passed**; frontend **%84.67** line"* | `CLAUDE.md:547` in the **same file** says **3987 passed / 1 xfailed**, coverage **%93.53**. `docs/releases/evidence/2026-08-10/p10b_backend_suite.txt:11-12` is the receipt for the later figure. `2712/92.06` is the ADIM-era baseline preserved in `docs/audit/coverage_baseline.md:47` — correct **there** (a historical record), stale in §Conventions. | `CLAUDE.md:92` vs `:547` |
| **DR-3** | stale test count | `README.md:730`: *"backend suite enforces `--cov-fail-under=90` (measured: **92.06%**)"* | measured 93.53% at ADIM 31 | `README.md:730` |
| **DR-4** | internal disagreement, frontend | `CLAUDE.md` carries **three** frontend figures: `:92` `%84.67`; `:323` `722 passed / 71 dosya, %84.90`; `:549` `721 passed / 70 dosya, %84.92` | `repository_facts.md` records **716 call sites in 72 files** (static). The file **count** in both present-tense claims is below the generated count. | `CLAUDE.md:92`, `:323`, `:549` |
| **DR-5** | **stale comment in production source** | `domain/backtest/portfolio_engine.py:48`: *"ADR §12's **ADIM 16** stepper, **which was never written** (`grep -n "def step" engine.py` returns nothing; the bar loop is nested at `engine.py:1782` inside a ~1100-line function)"* | The stepper **exists**: `engine.py:793 _build_stepper`, whose own docstring says *"(ADR-0002 §12 ADIM 16)"*; `engine.py:3177 _step`. The prescribed grep returns **two** hits. `engine.py:1782` is a `SignalEventRow` constructor, not a bar loop. Landed as PR #602. | `portfolio_engine.py:48` |
| **DR-6** | **budget coverage gap, not doc drift** | `query_budgets.json` covers 1 of Ready Check's 4 resolver legs | Two unmeasured legs carry a **measured** slope of 1.0 (§B.2); four more loop-inner reads are unmeasured (§B.4). No issue exists for any of them. | §B |

**DR-5 needs care: only the *reason* is stale, not the *conclusion*.**
`portfolio_engine.py`'s honest-boundary item 1 — *"No production caller"* — is still true.
`SHARED_ALLOCATION_STATUS` is `future_dev`, `jobs/backtest_engine.py` still loops over items
and folds with `combine_item_runs`, and
`test_the_phase_loop_exists_but_no_production_path_reaches_it` is the assertion that keeps
it so. What is stale is the *justification* offered for it and the grep recipe that was
supposed to let a reader verify it — a reader who runs that grep today gets two hits and
concludes the boundary is gone, when it is not.

### E.3 Checked and found **clean** — recorded so nobody re-derives it

* **`docs/adr/0002-…md` is NOT drifted.** Line 690 says *"ADIM 16 was never written, and is
  now formally SKIPPED"*, but **line 713 carries an explicit amendment**: *"AMENDMENT
  (2026-08-05, PR #602) — ADIM 16 is NO LONGER SKIPPED. The paragraph above is superseded."*
  The ADR corrects itself in place. The four *historical* documents that still say "never
  written" (`ADIM17_LANDED_KICKOFF.md:55`, `ADIM20_BLOCKED_KICKOFF.md:44`,
  `unified_portfolio_oracle_acceptance.md:64`, `PROJECT_HISTORY.md:3800` — which even
  annotates *"sonradan kapandı: PR #602"*) are all `doc-status: historical`. Only the
  production-source comment (DR-5) reads as present tense.
* **`repository_facts.md` is fresh** — `--check` exit 0.
* **`3541 collected` vs `3987 passed` is not drift.** The generated figure is a *static
  collection* count that cannot expand `parametrize`/`.each`; the file says so itself.
* **Why DR-2/DR-3/DR-4 survived CI.** `generate_repository_facts.py`'s stale-assertion scan
  checks the alembic head, `ENGINE_VERSION`, `SHARED_ALLOCATION_STATUS` and five invariant
  rules (`A08_COMPLETE`, `WCAG_CONFORMANCE`, `RUN_IS_RESULT`, `SIGNAL_IS_PACKAGE`,
  `FUTURE_DEV_ACTIVE`). **Test counts and coverage percentages are not among them.** The
  gate is not failing to do its job; it was never pointed at these numbers.

### E.4 #559 — does the DST decision really block shared-portfolio wiring (E4/E5)?

The label `blocks-mixed-zone-axis` and the milestone *"ADIM 16-20 — unified clock
programme"* invite the reading that #559 gates the `ItemParticipant` adapter and the
`jobs/backtest_engine.py:298` call site. **Measured from the code, it does not.**

| Question | Measured answer |
|---|---|
| Does the merged axis read a source timezone? | **No.** `execution/clock.py:185` (`tick_key`, `:177`) — `tick_key` calls `parse_utc(timestamp, source_zone=None)`, with the stated reason *"replayed bars are UTC-normalized at ingest, so a naive value is an honest `None` rather than a guessed UTC"*. The axis consumes instants, never wall clocks. |
| Where is the DST rule actually applied? | **Upstream, at ingest and at the funding reader** — `domain/market_data/validation_rules.py::resolve_timestamp` and `domain/backtest/funding.py::parse_utc`, both via `replace(tzinfo=source_zone)` with `fold` defaulting to 0. Both are on the *single-item* path today. |
| Is there an admission gate that refuses a mixed-zone composition? | **No.** `git grep source_timezone\|timezone_mode\|timezone_iana` over `readiness_check.py`, `backtest_run.py` and `domain/readiness/validators.py` returns **zero** hits. Nothing compares zones across items anywhere. |
| What does the ADR actually say? | `docs/adr/0002-…md:745`: *"GH **#559** (DST rule) **before the merged axis spans mixed-zone sources**"*, and `:853` R-2: *"DST fold/gap resolution is an accidental default and a merged axis makes it cross-item."* |

**Verdict.** #559 is **not a mechanical prerequisite** of E4/E5: no code path in the
participant adapter or the call site reads a declared source timezone, and removing the
issue would not change a line of the wiring. It **is** a stated ADR precondition for the
merged axis *spanning mixed-zone sources* — a scope the wiring makes reachable for the
first time. The consequence is a semantic one and worth stating plainly: today a
mis-collapsed folded hour misprices **one item's own** run; on a merged axis the same cell
shifts the **shared valuation point every item sees at that tick**. That escalation is
real, and **nothing in the code enforces the precondition** — it lives only in ADR prose.

So: **not blocking by construction, blocking by written decision, and unenforced.**
Whether E4/E5 may proceed with #559 open is a PO call, not a code fact.

---

## F. PO / canonical decisions awaited

| # | Decision | Owner | Blocked artefact |
|---|---|---|---|
| **PO-1** | **#558 shape.** Do bundle members gain the manifest's timing sub-dict, or does the bundle gain doc 12 §9.2's top-level arrays? Two of §9.2's five named arrays (`alignment_policy_versions[]`, `missing_and_stale_policies[]`) name concepts **that do not exist in the product** — adopting the literal shape means also deciding whether to model them. | PO | strict xfail `test_both_bundles_pin_the_available_time_policy` |
| **PO-2** | **#558 replay compatibility.** A shape change changes `bundle_hash`. No column stores it, but `run_idempotent.response_ref` stores the sealed body — a pre-change key replays the old shape (the O-30 precedent). Backfill, version, or accept? | PO | same |
| **PO-3** | **Agent Data Bundle freeze.** Should `compile_agent_data_bundle` inherit the approval freeze, or is a bundle over a mutable draft the intended Agent-research semantics? §A.2 shows the hash collision is reachable **only** on this path. | PO | — |
| **PO-4** | **#559 fold / gap.** First-occurrence-wins vs `TIME_POLICY_INVALID`; ingest-only vs backward audit. And separately: may E4/E5 proceed with it open (§E.4)? | PO | ADR 0002 §12 R-2 |
| **PO-5** | **#550 / #551 / #552** — all three need an `ENGINE_VERSION` bump plus golden-digest regeneration; #550 additionally needs a transition gate because saved revisions **cannot** be migrated mechanically. | PO | engine correctness |
| **PO-6** | **Delivery proof in CI.** Wiring `alert-notification-proof.sh` costs minutes of wall clock and a Docker network on every PR. Accept or keep it as release evidence? | human | Observability residue 3 |
| **PO-7** | **K-3 / K-5 / K-7.** Add a `<footer>`? Re-cut 22 pages' heading outlines (**measured cost: 204 headings across ~40 files + five tag-scoped CSS rules**)? Mount a persistent status region? | PO | A-08 preparation |

---

## G. Release blockers

**Blocker count: 1. Unchanged. Verdict: BLOCKED.**

| # | Blocker | Why it blocks |
|---|---|---|
| **1** | **A-08 — human screen-reader acceptance audit.** `0 / 4` exit criteria; **2 / 368** Section A cells; **0 / 46** routes complete; **0 / 20** flows; SR-1 never started; 0 findings; auditor role unassigned (the one session was run by the product owner, screen-reader role `neither`). GH #514 OPEN, `human-only`. | No artefact in this tree can close it. WCAG 2.2 AA is separately not met for **1.4.3** under signed deviation D-10 (K-1). |

**Nothing in this audit added or removed a blocker.** The items in §E.2 and §B are debts and
drift, not release blockers, and are recorded as such deliberately:

* **DR-5** is a stale comment, not a behaviour change — the containment it describes still holds.
* **§B**'s two N+1 legs are a latency regression on a page the user waits on, not a
  correctness defect; they fail closed identically to the batched path.
* **§A**'s hash collision is reachable only on the Agent bundle path over a non-approved
  revision, and the evidence bundle is protected by the lifecycle freeze.
* **§C**'s five residues were already written down as residues before this session.

---

## H. Reproducing the two measurements

Both harnesses were deleted; they are recorded here so the numbers are checkable.

**§A.2 — bundle hash under two policies.** Seed principals; `md_cmd.create_market_dataset` →
set `VERIFIED` → `md_cmd.approve_market_dataset_revision`; `rd_cmd.create_research_dataset`
with `UsageScope.RESEARCH_BACKTEST`; set the head revision to
`ResearchRevisionState.VERIFIED` (**not** `APPROVED` — approval freezes the policy);
`rd_cmd.set_time_policy(..., AvailableTimeSpec(FIXED_DELAY, 120))`;
`rd_jobs.compile_agent_data_bundle`; `set_time_policy(..., 7200)`; compile again. Compare
`bundle_hash` and `revision.content_hash`.

**§B.2 — leg slopes.** Copy `test_query_budgets.py::_all_statements` verbatim (the
`session.expunge_all()` is load-bearing — a warm identity map reports ~1 for a per-row
surface). For the signal leg build `MainboardItemKind.TRADING_SIGNAL` items with a **full**
`TradingSignalConfig` payload — the model is `_Strict`, so a partial `price_policy`-only dict
raises `PydanticValidationError` and `_signal_price_pins` skips the item, yielding a
misleading **0 statements**; reuse `test_readiness_signal_market_data.py::_signal_payload`.
For the research leg build STRATEGY items whose `data.funding` is
`{enabled: true, source_revision_id: <real rrev>}`. Measure at n=1 and n=11 in one session.
