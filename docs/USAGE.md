# Entropia — Usage Guide (end-to-end)

How a person actually drives the system, from login to a compared backtest
result. Every step below maps to a screen from the 24-screen map in the root
README and to a typed, audited backend command. The whole golden path is also
**executable as one integration test**:
`backend/tests/integration/test_e2e_pipeline.py` (ingest → package → strategy →
mainboard → ready check → RUN → result → history → trash/restore).

> Authority: this guide is a convenience narrative. The per-screen contracts
> live in [`spec/`](spec/) and the invariants in
> [`ARCHITECTURE.md`](ARCHITECTURE.md) / [`DOMAIN_MODEL.md`](DOMAIN_MODEL.md).

---

## 1. Signing in

| `AUTH_MODE` | How you authenticate |
| --- | --- |
| `dev` (default) | No login. The web app header has an **act as** box that sends `X-Actor-Id`; seed `user_admin` + `agent_alpha` with `uv run python -m entropia.apps.seed`. |
| `session` | Real login on **`/login`**: sign up / log in → argon2id-verified credentials → an opaque Bearer session token. |

- **First Admin (session mode):** set `ENTROPIA_BOOTSTRAP_ADMIN_EMAIL` in the
  environment, then sign up with that email — it is promoted to Admin **only
  while no active Admin exists**. The **Admin Provisioning** screen
  (`/panel/provisioning`) shows whether that window is open.
- In **every** mode the server resolves your role from the database per
  request. Hiding a menu item is UX, never authorization.

## 2. Roles — who can do what

| Role | Can |
| --- | --- |
| **User** | Own the full workspace: ingest data, create packages/strategies/work objects, compose the Mainboard, run Ready Check + backtests, manage own results. |
| **Supervisor** | Everything a User can, **plus** direct the Alpha Agent (Analysis Lab messages/directives at Normal/High priority). |
| **Admin** | Everything above, **plus** the approval plane: approve market/research revisions, approve/publish packages, activate/deprecate ESP resolvers, assign roles, runtime pause/resume/stop, Trash restore/purge, Panel/Logs, System Metrics, operator recovery. |
| **Agent** (non-login system actor) | Runs continuously backend-side; uses the same commands via the Tool Gateway; can only create proposals — never approve, publish, touch Trash, or assign roles. |

## 3. The golden path

### 3.1 Ingest market data — `/market-data`
1. **Create dataset** (type, instrument, title) → a root with a DRAFT revision.
2. **Upload** the raw file (two-step: start → finalize; bytes land in object
   storage content-addressed — the page never carries raw bytes).
3. **Run analysis** — a durable 202 job parses and profiles the file.
4. **Confirm the schema mapping** (column → canonical field).
5. **Admin approves** the revision. Only APPROVED revisions are pinnable
   downstream. Corrections create a **new revision or successor** — history is
   never rewritten.

### 3.2 (Optional) Research data — `/research-data`
Same ingest chain, plus: a link to the market revision it contextualizes,
an **available-time policy** (what the backtest may know and when), and
field/feature definitions. Admin approve/revoke gates use.

### 3.3 Create a package — `/packages/create` and `/packages/pre-check`
1. Compose a request: kind (Indicator / Condition / ESP), output contract,
   declared dependency keys, a Rationale Family (`/rationale-families`).
2. **Pre-Check** resolves every declared key against the resolver registry
   (`/packages/embedded` — seeded `ta.*` / `cond.*` resolvers are
   trusted-active out of the box with `SEED_ESP_TA=1`).
3. **Generate candidate** — deterministic manifest + content hash.
4. **Create draft** from the candidate, then **Admin approves** → published,
   visible in the **Package Library** (`/packages/library`).

### 3.4 Author a strategy — `/strategy`
Create root + editor draft → edit the payload (entry/exit blocks pinning the
published package revision + the approved market revision, position sizing,
protections) → **Validate** (pure compiler pass, issues verbatim) → **Save** —
an immutable strategy revision. The draft carries an OCC token
(`expected_draft_row_version`), so a stale tab gets a 409, never a silent
overwrite.

### 3.5 Compose the Mainboard — `/` 
Attach the strategy (and any Trading Signal / Trade Log work objects, imported
via `/trading-signal` · `/trade-log` or the `/outsource-signal` chooser). Pin
exact revisions ("Use This Revision"), enable/disable, reorder, label. The
composition **fingerprint** changes with every pin/enable — that is what Ready
Check certifies. (Optional) set an allocation plan in `/portfolio`.

### 3.6 Ready Check → RUN — `/backtest/ready-check` → `/backtest/run`
Ready Check runs the full server preflight and produces an **immutable
readiness report** bound to the fingerprint. RUN admission re-runs the
preflight and requires the same fingerprint (`409` if the composition moved),
then returns **202 + run id**: a manifest pinning exact revision ids goes to
the backtest worker. The engine reads **only the manifest** — never "latest".
Identical re-runs with the same pins reuse the result (idempotent
`execution_key`).

### 3.7 Results — `/backtest/run?result=` → `/backtest/history` → `/backtest/metrics`
A succeeded run materializes an immutable Result (metrics, manifest excerpt,
artifacts). History is a server-sorted keyset index: **compare exactly two**
results (informational, never ranked), soft-delete your own. **Arrange
Metrics** shapes which metrics your result views display (apply / lock /
unlock) — presentation only, it never mutates stored values.

### 3.8 Undo — `/trash` (Admin)
Soft-deleted objects land in Trash with a dependency snapshot: **Restore**
(OCC + idempotent) or **Permanently delete** (typed confirmation phrase +
re-auth proof → a durable purge job).

## 4. The Alpha Agent — `/analysis-lab`
The research Agent runs continuously backend-side (browser close never stops
it). Supervisors/Admins queue **messages/directives** (Normal/High — consumed
at safe checkpoints, never preempting a running task); Admins can
pause/resume/stop the runtime. The task detail shows checkpoints, directives,
and the **tool-call history** (every gateway call with request/response).
The Agent's outputs are proposals — a human Admin still approves.

## 5. Live updates & safety rails (what you'll notice everywhere)

- **SSE refresh signals** (`GET /api/v1/events`): pages revalidate when the
  server publishes a change; on reconnect the app refetches everything. SSE is
  never trusted as state — screens always re-read authoritative projections.
- **OCC everywhere:** mutations carry an expected-version token; a stale tab
  gets a `409` with the exact server head, never last-write-wins.
- **Idempotency-Key** on every mutating command: a retried request returns the
  original effect exactly once.
- **Everything is audited:** the Panel's Logs tab (`/panel`, Admin) is an
  append-only projection over the audit trail with correlation chains.
- **Ops:** `/panel/metrics` renders the Prometheus exposition
  (`GET /api/v1/metrics`); `make smoke` verifies a running stack from outside.

## 6. Out of scope (deliberate)

Live/paper trading, broker connectivity, LLM package generation, retention
auto-purge, and the Graphic View renderer are **not** part of V1 — see
`POST_V1_KICKOFF.md` for the boundary list.
