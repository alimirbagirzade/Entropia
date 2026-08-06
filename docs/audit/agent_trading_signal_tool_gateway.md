<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# Agent Trading Signal Tool Gateway parity (TS-20 / AOS-20) — policy, scope table, payload limits

**Branch:** `feat/agent-trading-signal-tool-gateway` · **Base:** `origin/main` @ `d6bbe9b`
**Closes:** doc 04 §15 **TS-20**, doc 03 §14 **AOS-20** (literal "via Tool Gateway" clause)
**Test:** `backend/tests/integration/test_gateway_parity_trading_signal.py` (33 tests)

---

## 1. What was actually broken (reproduced before writing code)

On `origin/main` @ `d6bbe9b`, `ToolName` carried **28** members and **zero**
`trading_signal.*`. All five literals raised `ToolPolicyScopeError`:

```
ToolName members: 28   ·  exposed (no capabilities): 26
trading_signal.upload_source_asset : ToolPolicyScopeError -> Unknown agent tool
trading_signal.request_import      : ToolPolicyScopeError -> Unknown agent tool
trading_signal.get_import_report   : ToolPolicyScopeError -> Unknown agent tool
trading_signal.create              : ToolPolicyScopeError -> Unknown agent tool
trading_signal.create_revision     : ToolPolicyScopeError -> Unknown agent tool
```

TS-20 says the Agent does this **"via Tool Gateway"**. There was nothing to call, so
the row's literal sentence was untestable — exactly what
`test_acceptance_agent_parity_gaps.py`'s docstring already admitted. After the slice:
**33** members, **31** exposed, all five parse.

Only the *Gateway* axis was missing. The domain-command axis was already proven, and
this slice does not restate it: the handlers add **no** business logic.

---

## 2. Tool registry + scope table (`TOOL_ALLOWED_SCOPES`)

| Tool | Scopes | Queue | Backing command/query (doc 04 §10) |
|---|---|---|---|
| `trading_signal.upload_source_asset` | `research` | `agent` | `commands/trading_signal.py::upload_source_asset` |
| `trading_signal.request_import` | `research` | `agent` | `::request_trading_signal_import` |
| `trading_signal.get_import_report` | `observation`, `research` | `agent` | `queries/trading_signal.py::get_import_report` |
| `trading_signal.create` | `research`, `proposal` | `agent` | `::create_trading_signal_and_attach` |
| `trading_signal.create_revision` | `research`, `proposal` | `agent` | `::create_trading_signal_revision` |

**None is `execution`.** doc 04 §15 **TS-21** states that selecting or saving a Signal
never creates a Backtest Result, so none of these may take the heavy `agent-high`
plane away from real runs; a run stays the separate `backtest.request` tool. All five
are ungated (not CR-08 Future-Dev tools), so an Agent planning with no operational
capability still sees the whole line.

### 2.1 Adjudication — naming

Doc 04 §10's parity table is written in **agent-intent** terms and names the real
backing command in its own "Tool / domain capability" column. The registry follows the
**command**, by the same rule the strategy family established (doc 18 §10's prose
`strategy.draft.create` was likewise not the registry).

| doc 04 §10 intent | Backing capability named there | Shipped literal | Why |
|---|---|---|---|
| `trading_signal.create` | direct structured draft command | `trading_signal.create` | verbatim, no adjudication needed |
| `trading_signal.import_events` | `UploadSourceAsset` **+** `RequestTradingSignalImport` | `upload_source_asset` **and** `request_import` | the table itself names two commands; they have two different durability stories (an immutable content-addressed asset vs. a durable data-queue job). Fusing them would have hidden the admission/completion boundary. |
| `trading_signal.validate` | `ValidateTradingSignalDraft / GetImportReport` | `get_import_report` | only `GetImportReport` exists as a command — the §9.2 config compiler runs *inside* create/create_revision, it is not a separate entry point. No validate-only command was invented. |
| `trading_signal.save_revision` | `CreateTradingSignalRevision` | `create_revision` | matches the sibling external work object (`trade_log.create_revision`) so the two read identically |

Rejected spellings are **pinned by test**
(`test_the_doc04_intent_spellings_are_not_the_registry`): `import_events`, `validate`,
`save_revision`, `attach`, `delete` all raise.

---

## 3. Policy boundaries (each measured by test)

| Boundary | Where it is enforced | Observable |
|---|---|---|
| Trading Signal is **never** a Package (CR-01) | no handler names `PackageKind`; `item_kind` derived server-side from the root in `attach_mainboard_item` | `PackageRoot` count `== 0`; item kind `trading_signal` |
| Human Mainboard is never auto-mutated | `_resolve_attach_workspace` resolves the **caller's own** default board; for an Agent principal that is `agent_research` | human board `items == []` and `composition_hash` unchanged; agent board holds the item |
| Foreign workspace refused | `attach_mainboard_item` → `_require_owned_workspace` | recorded **REJECTED**, human board untouched |
| Foreign private root refused | `create_trading_signal_revision` → `ensure_can_edit` | recorded **REJECTED**, human's revision count still 1 |
| Save ≠ Ready PASS ≠ Run | command returns `ready_state="STALE"` | asserted on the Gateway response |
| `available_time` never inferred | pinned inside the command from the import's earliest accepted event | revision `available_time` == `10:03` (availability), **not** `10:00` (event time) |
| Import must supply availability | a file with no `available_time` column fails the import | `import_status == "failed"`, `create` then fails, no revision written |
| Revision OCC | `expected_head_revision_id` (a revision id, **not** a row_version — this is *not* a dual-token op) | stale token → durable FAILED `WORK_OBJECT_REVISION_CONFLICT` |
| No auto-repin | command sets `auto_repinned: False` | the Mainboard item still points at revision 1 after revision 2 lands |

---

## 4. Payload limits — the F-03 byte gate now applies to the UI-less plane

**The defect this closes.** The human page's size / whole-document-UTF-8 / CSV-schema
gate lived at the **multipart route** (`apps/api/upload.py`). A Tool Gateway caller has
no route, so those three controls simply did not apply to the Agent — the command layer
only ran the extension/type sniff. A browser-bound control that silently stops applying
to the Agent is precisely what doc 04 §10's "Agent Boundary" forbids.

The gate moved to `domain/importing/source_file.py` and **both planes now call one
implementation**:

| Control | Limit / rule | Error code (identical on both planes) |
|---|---|---|
| size | `MAX_SOURCE_UPLOAD_BYTES` = **50 MiB** | `UPLOAD_TOO_LARGE` |
| empty | zero bytes rejected | `VALIDATION_ERROR` |
| encoding | whole document decodes as UTF-8, no NUL | `UPLOAD_ENCODING_INVALID` |
| schema | at least one non-empty CSV header row (`require_csv_schema=True`, mirroring the route) | `UPLOAD_SCHEMA_INVALID` |
| type | extension + binary-signature sniff (already in the command) | `FILE_TYPE_NOT_ALLOWED` |
| hash / dedup | sha256 content address, per-owner dedup (already in the command) | — |

`apps.api.upload.DEFAULT_MAX_UPLOAD_BYTES` is now an **alias** of the domain constant,
not a second literal — two literals would drift the first time one was tuned. The
route's bounded stream read (`max_bytes + 1`) deliberately stays at the route: that is
the streaming protection, and it has no meaning for an in-memory caller. The F-03 unit
suites (`test_upload_validation.py`, `test_source_file_gate.py`, 30 tests) pass
unchanged, which is the evidence the extraction is behaviour-preserving.

**Gate order note.** On the Gateway plane the byte gate runs *before* the command's
type gate — the same order the route uses (`validate_multipart_upload`, then the
command). So a non-UTF-8 file reports `UPLOAD_ENCODING_INVALID` on both planes, not a
type error on one and an encoding error on the other.

### 4.1 Raw bytes are stored **by reference**, never inlined

The `agent_tool_call` row is the long-lived agent-history surface (it is what the
Analysis Lab call-history query reads back). Copying a multi-megabyte ledger into its
`request` JSONB would duplicate the asset into evidence storage forever — and would do
it *even for a file about to be rejected for being too large*, which is the one case
where writing it is most obviously wrong.

`_persistable_request` therefore de-references the payload **before the INSERT**:

```json
{"original_filename": "signals.csv",
 "content_ref": {"sha256": "5d1d…", "size_bytes": 128}}
```

The handler still receives the bytes in memory. The digest is the **same sha256** the
upload command content-addresses the asset by, so the row still names the exact object
— the reference is the stronger record, not a lossy one. Scoped to the signal family
on purpose: the landed `trade_log.*` tools have their own recorded envelope shape and
this slice does not restate it.

**Remaining exposure, stated honestly:** the *durable job* payload
(`enqueue_tool_call` → `jobs.payload`) still carries the inline bytes for the enqueued
path, because the worker replays that payload to execute. The 50 MiB ceiling is what
bounds it; the asset-reference path is what keeps it out of the long-lived evidence
row. Every downstream tool (`request_import`, `create`, `create_revision`) already
takes **ids only**, so the bytes cross the envelope exactly once.

---

## 5. Import is admission, not completion

`request_import` returning `status: "succeeded"` means the durable job was **admitted**.
The job's own lifecycle is namespaced to **`import_status`** so it can never shadow the
envelope's terminal call status (doc 18 §9.2 envelope-wins rule) and can never be
misread as "the import finished". `get_import_report` namespaces the same way — and
that field legitimately changes vocabulary mid-flight (the `jobs` status while the
worker runs, the normalized revision's status once it lands), which is exactly why it
must not be read as the call's status.

### 5.1 The broker hand-off (a real defect found while building this)

`enqueue_job` only INSERTs a QUEUED row; the **caller** dispatches the dramatiq actor
after commit. Every human route does this (`routes/trading_signal.py:103`). The Tool
Gateway did not — and the `data` queue is **deliberately excluded** from the
scheduler's automatic redelivery sweep (`ACTOR_BY_QUEUE`) because it is multi-actor. An
agent-admitted import would therefore have sat `queued` until an Admin manually ran the
redelivery action. A tool call reporting `succeeded` over work that could never start is
the silent-fallback shape this system forbids.

`_run_agent_tool` now performs the hand-off **after its commit**, via
`pending_data_job_dispatch` + `DATA_ACTOR_BY_KIND` — mirroring
`routes/admin_panel.py::_dispatch_data_jobs`. Sending before the commit would race the
actor against a row it cannot yet read.

**A replay dispatches nothing.** `run_import` has **no terminal-state guard**, so
re-sending a finished job would parse the file twice and write a second normalized
revision. A redelivered tool call admitted no new work, so `pending_data_job_dispatch`
returns `None` for it.

---

## 6. Negative controls (each new guard was proven to bite)

Every control below was disabled in turn and the naming test re-run; all five went red,
so none of them is inert decoration:

| Guard disabled | Test that went red |
|---|---|
| worker hand-off call in `_run_agent_tool` | `test_the_worker_actually_performs_the_hand_off_after_it_commits` |
| F-03 byte gate in the upload handler | `test_an_oversize_upload_is_refused_with_the_pages_own_code` |
| payload de-referencing | `test_the_durable_envelope_stores_a_reference_not_the_raw_bytes` |
| `import_status` namespacing | `test_import_admission_is_not_completion` |
| replay no-re-dispatch guard | `test_redelivery_replays_and_never_re_dispatches_the_import` |

---

## 7. Honest boundaries — what this slice does NOT close

- **`trading_signal.attach` as a standalone re-pin** and **`trading_signal.delete`**
  (doc 04 §10's last two rows) have no tool — on *either* external-work-object family.
  Attach-at-save **is** covered (`trading_signal.create` carries the `attach` flag), so
  TS-20's own verb list is served; the residue is the shared Mainboard/lifecycle
  surface, not the signal line. `trading_signal.export` is likewise out (the trade_log
  family deferred its export too).
- **`trade_log.request_import` has the identical missing broker hand-off.** It was
  verified, not assumed: its handler enqueues a `data` job and nothing dispatches it.
  It is left untouched because rewriting the Trade Log tools is explicitly out of scope
  for this slice. It is a real, currently-shipped defect and should be the next step.
- **Double-dispatch window.** If an Agent reuses a *domain* `idempotency_key` under a
  *new* gateway key, `run_idempotent` returns the same `job_id` and it is dispatched
  again. The human route behaves identically (it calls `send_job` unconditionally), so
  this is a pre-existing property of the data queue shared by both planes, not
  something this slice introduces. Making the Agent plane stricter than the page would
  have been an invented product decision.
- **No migration, no OpenAPI change, no frontend change.** `agent_tool_call.tool_name`
  is a plain `String(64)`; the longest new literal (`trading_signal.upload_source_asset`) is 34 chars. No route was added, so
  the OpenAPI drift guard stays green.
