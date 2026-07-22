# Entropia Runtime Authentication Remediation — Delivery Evidence Package

> Consolidated delivery report mandated by
> `docs/spec/Entropia_Authentication_Remediation_Claude_Code_Deep_Audit.md` §13 (closes
> **TEST-12**). One traceable record mapping every audit finding → landing commit → test, plus
> the §10 verification-command results. **Stale-by-default**: numbers below were produced live on
> **2026-07-22** against `origin/main` @ `6e3fab9`; re-run §7 before trusting them.

## 1. Branch, commit, PR

- **Delivery branch:** `docs/auth-remediation-test12-delivery`
- **Base commit (origin/main HEAD at delivery):** `6e3fab9`
- **PR:** _(added on open — see closing note)_
- Functional remediation landed across PRs **#346–#364** (waves W1–W8 + residuals); this doc adds
  no code, only the consolidated evidence §13 requires.

## 2. Changed files by area (across waves #346–#364)

- **Backend** — `apps/api/routes/auth.py` (mode-gated login, BACK-01), `apps/api/deps.py`
  (one credential per transport), `apps/api/sse.py` (authenticated + minimal SSE, AUTH-11),
  `apps/seed.py` (mode-aware provisioning, PROV-01..06), `application/commands/*`,
  `infrastructure/postgres/repositories/identity.py`, `config/settings.py`.
- **Frontend** — runtime-auth provider + app shell (AUTH-02/03/07), `lib/*` credential-header
  selector (AUTH-05/06), invalid-session coordinator (AUTH-08/09/10), `/login` gating (AUTH-04).
- **Provisioning** — `apps/seed.py` mode-aware baseline; `scripts/ensure-service-token.*` (DEP-02).
- **Deployment** — `docker-compose.yml` (provision one-shot + worker healthchecks, PROV-06/DEP-05),
  `docker-compose.dev-auth.yml` (explicit dev profile, DEP-01/04), `scripts/*`, `Makefile`.
- **Tests** — `backend/tests/contract|integration|unit`, `frontend/src/test`, `e2e/`.
- **Documentation** — `README.md` (auth model + startup + upgrade), this delivery report.

## 3. Final runtime-auth architecture

`/meta.auth_mode` is the single runtime source of truth. The frontend boots a runtime-auth
provider from `/meta` (fail-closed while in flight — no control flashes), and the shell selects
session-login vs dev-actor controls **from server mode, never from token presence**. Exactly one
credential is attached per transport (session → `Authorization` Bearer; dev → `X-Actor-Id`).
Human login is rejected outside session mode at the API boundary. A single invalid-session
coordinator clears identity-bound state once and redirects once on `SESSION_INVALID`; 403/access
denial never clears the session; cross-tab sync via storage relay. SSE authenticates its handshake
and emits a minimal invalidation envelope, not raw outbox. Provisioning is mode-aware: session
installs bootstrap a real credentialed Admin, legacy credentialless Admin data is preserved (never
deleted/demoted) with a safe upgrade path, and the last login-capable Admin is protected.

## 4. Existing-database upgrade steps

1. **Back up first:** `pg_dump` the live database before any mode change.
2. `git pull` → `uv sync` (backend) → `uv run alembic upgrade head` (schema; no auth-only migration
   in this remediation — schema unchanged).
3. Set `AUTH_MODE=session` in `.env`; ensure a strong non-committed service token via
   `scripts/ensure-service-token.sh` (`.ps1` on Windows).
4. Start the stack; the mode-aware seed upgrades a legacy credentialless Admin **in place** (adds a
   credential, PII-free audit note) without touching owned domain rows. **Operator input required**
   only to set the first Admin credential via the bootstrap window (`/panel/provisioning`).
5. Covered by `test_legacy_admin_upgrade.py` / `test_legacy_upgrade.py` (idempotent, fail-closed 2nd run).

## 5. Local session startup (default)

```bash
make up            # or: docker compose up -d --build   (AUTH_MODE=session is the product default)
```

## 6. Explicit dev-auth startup (local-only override)

```bash
make up-dev-auth   # or: docker compose -f docker-compose.yml -f docker-compose.dev-auth.yml up -d --build
```

## 7. Verification commands and numerical results (run live 2026-07-22, isolated)

| Command | Result |
|---|---|
| `ruff check .` | **PASS** — All checks passed |
| `ruff format --check .` | **PASS** — 571 files already formatted |
| `mypy src` | **PASS** — no issues in 344 source files |
| `python -m entropia.apps.api.openapi_export --check` | **PASS** — snapshot up to date |
| `pytest --no-cov -q` | **PASS (exit 0)** — 1841 tests collected, all green (1 benign ResourceWarning) |
| `tsc --noEmit` (typecheck) | **PASS** — clean |
| `eslint .` (lint) | **PASS** — clean |
| `vitest run` | **PASS** — 577/577 across 58 files |
| `npm run build` | **PASS (exit 0)** — built; only a non-blocking bundle-size (>500 kB) advisory |

## 8. Clean-session E2E

Landed W7 — commit `26cea44` (PR #360), real isolated Docker E2E for the session-clean acceptance
flow (§9.4). **Not re-executed this session** (see §12).

## 9. Legacy-upgrade E2E / integration

**PASS** — `backend/tests/integration/test_legacy_admin_upgrade.py` + `test_legacy_upgrade.py`
reconstruct a legacy credentialless Admin (+ Principal, owned domain rows, audit/outbox, Agent),
run the upgrade twice, and assert: new credentialed Admin, PII-free note, fail-closed 2nd attempt,
byte-for-byte legacy preservation, last-operational-Admin protection (§9.5). Green in the §7 run.

## 10. Dev-auth E2E

Landed W7 — commit `26cea44` (PR #360), real dev-mode Docker acceptance flow (§9.6). **Not
re-executed this session** (see §12).

## 11. Compose service-health evidence

`docker-compose.yml` applies the `x-worker-healthcheck` anchor to `worker-default`, `worker-data`,
`worker-backtest`, `worker-agent`, `agent-coordinator`, and `scheduler`; a `provision` one-shot
(depends on `migrate`) gates all runtime planes via `*needs-provision` (PROV-06/DEP-05).

## 12. Remaining honest boundary

- **Docker E2E (§8, §10) not re-run in this delivery session.** The three acceptance flows landed
  and passed under W7 (`26cea44`, PR #360) and run in CI. They were deliberately **not** re-executed
  here to honor the audit's §10 safety rule (never point isolated-volume tear-down at the operator's
  live Entropia Compose project). Re-run via `make accept` / `make accept-dev-auth` in a separately
  named Compose project when a full local re-proof is wanted. This is an evidence-freshness boundary,
  **not** a deferred acceptance item — no §11 criterion is unmet.
- **Frontend bundle-size advisory** (>500 kB) is a Vite optimization hint, not a failure (build exit 0).

## 13. Finding → status → evidence matrix

| Finding | Status | Evidence |
|---|---|---|
| AUTH-01 runtime mode in metadata | CLOSED | `de9c890`, `f0a5614` (OpenAPI); `test_auth_mode_contract.py` |
| AUTH-02 app-wide runtime auth state | CLOSED | runtime-auth provider; `runtimeAuthProvider.test.tsx` |
| AUTH-03 shell chooses UI from mode | CLOSED | `authModeShell.test.tsx` |
| AUTH-04 login route rejected in dev | CLOSED | `f7462c0` (PR #347) |
| AUTH-05 one credential per transport | CLOSED | `bea75ec`; `authHeaderMatrix.test.ts` |
| AUTH-06 multipart single credential | CLOSED | `authHeaderMatrix.test.ts` (multipart case) |
| AUTH-07 local storage not identity truth | CLOSED | runtime-auth provider; shell tests |
| AUTH-08 central invalid-session handling | CLOSED | `4c9ce34` (PR #361) |
| AUTH-09 401 ≠ always login | CLOSED | `4c9ce34`, `becad2b` |
| AUTH-10 cross-tab session sync | CLOSED | `4c9ce34`, `46fa1c9` (PR #364) |
| AUTH-11 authenticated minimal SSE | CLOSED | `f330418` (PR #349); `test_sse_auth.py` |
| BACK-01 login rejects mode-incompatible token | CLOSED | `auth.py:119`; `test_auth_mode_login_gate.py` |
| PROV-01 seeding auth-mode aware | CLOSED | `seed.py` `should_seed_dev_admin()` |
| PROV-02..05 credential-aware Admin count | CLOSED | `1cf8a26` (PR #357) |
| PROV-06 mode-safe Compose baseline | CLOSED | `d9121bd` (PR #363); `provision` one-shot |
| DEP-01 local default not dev | CLOSED | `.env.example:62` `AUTH_MODE=session` |
| DEP-02 session rejects empty service token | CLOSED | `scripts/ensure-service-token.*` |
| DEP-03 safe config migration in update scripts | CLOSED | `8448484` (PR #362) |
| DEP-04 explicit Compose auth profiles | CLOSED | `docker-compose.dev-auth.yml` |
| DEP-05 worker/coordinator/scheduler health | CLOSED | `30100cd` (PR #358); healthcheck anchor |
| DEP-06 docs/smoke describe correct model | CLOSED | `8448484` (PR #362); `smoke.sh` |
| TEST-01 `/meta.auth_mode` contract | CLOSED | `test_auth_mode_contract.py` |
| TEST-02 frontend mode/UI matrix | CLOSED | `authModeShell.test.tsx` |
| TEST-03 transport mutual exclusivity | CLOSED | `authHeaderMatrix.test.ts` |
| TEST-04 backend dev-mode Bearer failure | CLOSED | `test_auth_mode_login_gate.py`, `test_auth_mode_transport.py` |
| TEST-05 real legacy-upgrade (not fresh DB) | CLOSED | `test_legacy_admin_upgrade.py` |
| TEST-06..10 auth test matrix + stale session | CLOSED | `eacd5aa`, `1e67ce4` (PR #359) |
| TEST-11 Makefile unmasks frontend failure | CLOSED | `30100cd` (PR #358) |
| TEST-12 consolidated delivery evidence | CLOSED | **this document** |
