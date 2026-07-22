# Real Docker E2E acceptance (audit §9.4 / §9.5 / §9.6 — W7)

`scripts/e2e-acceptance.sh` runs the three mandated authentication acceptance
flows against a **real Dockerized stack**, each in a fully isolated Compose
project so it can run alongside your normal `make up` stack and never touches
its data.

```bash
make e2e            # all three flows in sequence
make e2e-session    # §9.4 clean session-mode bootstrap
make e2e-legacy     # §9.5 legacy credentialless-Admin upgrade
make e2e-dev-auth   # §9.6 dev-mode X-Actor-Id impersonation
# or directly: scripts/e2e-acceptance.sh [session|legacy|dev-auth|all]
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
  `401 SESSION_INVALID`; every worker plane broker-connected; full acceptance
  gate (`scripts/acceptance.sh`) — API, web, Postgres, Redis, MinIO, scheduler,
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
