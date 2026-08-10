# Real Docker E2E acceptance (audit §9.4 / §9.5 / §9.6 — W7)

`scripts/e2e-acceptance.sh` runs the three mandated authentication acceptance
flows **and the five product acceptance flows** against a **real Dockerized
stack**, each in a fully isolated Compose project so it can run alongside your
normal `make up` stack and never touches its data.

```bash
make e2e            # all four flows in sequence
make e2e-session    # §9.4 clean session-mode bootstrap
make e2e-legacy     # §9.5 legacy credentialless-Admin upgrade
make e2e-dev-auth   # §9.6 dev-mode X-Actor-Id impersonation
make e2e-flows      # the five acceptance flows (a)-(e)
# or directly: scripts/e2e-acceptance.sh [session|legacy|dev-auth|flows|all]
# E2E_KEEP_UP=1 leaves the `flows` stack running for inspection.
```

Requires a running Docker engine (Docker Desktop or OrbStack) and `curl`.
It is a bash harness (like `scripts/smoke.sh`); on Windows run it under WSL or
Git Bash.

## Isolation contract (why it is safe next to your real stack)

| Concern | Guarantee |
|---|---|
| Compose project | Always `entropia-e2e-<flow>`. A hard guard **refuses** to `down -v` anything whose name is not that prefix, so `entropia` (your `make up` project) can never be destroyed. |
| Volumes | Compose namespaces named volumes by project, so `pgdata` becomes `entropia-e2e-session_pgdata` — separate storage, wiped only for the E2E project. |
| Host ports | Each flow publishes on a distinct high range (API `1800x`, web `1808x`, Postgres `1543x`, …) via the new `${*_HOST_PORT}` defaults in `docker-compose.yml`, so it coexists with `5432/8000/8080`. |
| Container env | Backend containers read a git-ignored `.env.e2e.<flow>` via `ENTROPIA_ENV_FILE`; your real `.env` is never read or written. |
| Service token | A strong `ENTROPIA_SERVICE_TOKEN` is generated per run and **never printed**. |
| Cleanup | An EXIT/INT/TERM trap tears the isolated project (with its volumes) down even on failure or Ctrl-C, and deletes the generated env file. |

Default behavior of `docker-compose.yml` is unchanged: every new
`${VAR:-default}` resolves to the previous literal, so `make up` is identical.

## What each flow asserts

All backend-observable numbered steps from the audit are asserted directly
against the live API. Every flow prints `PASS`/`FAIL` per step and the script
exits non-zero if any step fails.

- **§9.4 session-clean** — session `/meta`; strong service token present;
  mode-safe provisioning; bootstrap-Admin signup on a fresh DB; logout→login;
  exact `/me` principal + role; Mainboard/strategy not 401; session retained on
  refresh; normal User created + Admin surface `403`; revoked token →
  `401 SESSION_INVALID`; every worker plane broker-connected (`worker-default`,
  `worker-data`, `worker-backtest`, `worker-agent`, `worker-agent-executor`,
  `agent-coordinator`, `scheduler`); full acceptance gate
  (`scripts/acceptance.sh`) — API, web, Postgres, Redis, MinIO, scheduler,
  coordinator, all workers.
- **§9.5 legacy-upgrade** — seed a credentialless `user_admin` + owned records
  under dev; flip to `AUTH_MODE=session` on the **same volumes** (no reset);
  provision twice (idempotent); bootstrap a real Admin over the legacy row;
  log in + reach `/admin/users`; a shape-independent Postgres snapshot proves
  IDs / ownership / the `user_admin` row / audit history are preserved; the
  last login-capable Admin cannot be self-demoted.
- **§9.6 dev-auth** — base + `docker-compose.dev-auth.yml`; `/meta.auth_mode=dev`;
  login rejected with `AUTH_MODE_MISMATCH`; a stale Bearer resolves anonymous;
  `X-Actor-Id: user_admin` authenticates that principal; a Bearer alongside
  `X-Actor-Id` is ignored; protected pages return non-401.

### The five acceptance flows (`flows`)

Added in ADIM 30 to close RC readiness blocker 2 (§6.2). Body:
`scripts/lib/acceptance-flows.sh`. It reuses this script's isolation contract,
hermetic env file, `dc`/`req` helpers and PASS/FAIL tally — it is not a second
harness. The stack is seeded with `SEED_E2E_GOLDEN` + `SEED_ESP_TA` +
`SEED_RATIONALE`, the same three fixtures CI and the a11y audit stack use.

Two layers, and neither is allowed to stand in for the other:

- **Browser layer** — the journeys `frontend/e2e/specs/*` already implement are
  **run, not reimplemented**: `05` + `18` (flow a), `20-library` (flow b), `06`
  (flow e's delete → purge leg), pointed at the isolated stack via
  `E2E_BASE_URL` / `E2E_API_BASE_URL`.
- **Server layer** — everything no layer covered: **(c)** ESP lifecycle (create →
  validate → registry OCC → trust gate) and the package export envelope,
  **(d)** Trading Signal / Agent tool surfaces, **(e)** the **restore** leg spec
  `06` skips, plus the four invariants a browser cannot prove because a browser
  only sees what the UI chose to render:

  1. Trading Signal / Trade Log are **not** Packages — absent from the Library
     catalog, and a package root is a 404 on the Trading Signal surface.
  2. **Backtest Run ≠ Backtest Result** — a refused admission leaves the Results
     plane untouched; only a SUCCEEDED run materialises a Result.
  3. **UI hidden/disabled is not authorization** — every Admin/owner surface is
     re-attacked with a plain USER token and must answer 403 server-side.
  4. Long work runs on the **durable queue** — admissions are 202 + a job id and
     are followed through the worker, never short-circuited.

A step that cannot run is recorded **SKIP** on its own counter and is never
folded into the pass total.

## Where this runs

Until ADIM 22 these flows ran **only** on a developer's machine — no workflow
invoked them, so a broken install or upgrade path could land green. The legacy
flow is now executed by `.github/workflows/install-acceptance.yml` (job
**legacy-upgrade**) nightly and on manual dispatch; the fresh-install path is
covered on every PR by that workflow's **fresh-install** and
**migration-acceptance** jobs. See
[`docs/INSTALL_ACCEPTANCE.md`](INSTALL_ACCEPTANCE.md) for the full chain and
which link is proven where.

**`flows` is NOT yet a CI gate.** No workflow invokes it, so a regression in the
five acceptance flows can still land green — exactly the exposure the paragraph
above describes for the auth flows before ADIM 22. Their **browser** halves are
gated (`.github/workflows/e2e.yml` runs specs 05 / 18 / 20-library / 06 on every
push and PR to `main`); the **server** halves are not gated anywhere. Wiring the
subcommand into CI means paying for a second 12-container stack per run and is a
deliberate open decision, not an oversight.

## Honest boundaries

- **Browser-level steps** (DevActorControl visibility, exactly-one redirect, the
  frontend sending no `Authorization` header) are asserted at the frontend layer
  (audit §9.3): `frontend/src/test/*` and `frontend/e2e/specs/01-auth.spec.ts`.
  This harness asserts the **backend contract** those behaviors depend on and
  cross-references them.
- **Per-plane job execution** (data/backtest/agent pipelines end to end) is
  exercised by backend integration — `backend/tests/integration/test_e2e_pipeline.py`.
  This harness asserts every worker plane is up and broker-connected, and does
  not re-drive full pipelines from the shell.
- **`flows` (c): a POSITIVE resolver activation is not driven here.** The probe
  resolver ships no runnable test vectors, so its validation legitimately ends
  `failed` and the registry refuses to promote it. The flow asserts that refusal
  — the security-relevant direction — and records a **SKIP** for the positive
  activate → deprecate path, which is covered in-process by
  `backend/tests/integration/test_esp_persistence.py`.
- **`flows` (d): the Tool Gateway call log is not exercised.** A freshly seeded
  stack has no agent task, so `GET /agent-tasks` is a legitimate empty 200 and
  the per-task tool-call read is recorded as a **SKIP**, not a pass.
