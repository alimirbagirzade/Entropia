# Entropia Runtime Authentication Remediation

## Deep Code Audit and Non-Negotiable Implementation Directive for Claude Code

**Repository:** `alimirbagirzade/Entropia`  
**Audited branch:** `main`  
**Audited commit:** `620dae9e439e32fe35fdbf593bde24804000fdb7`  
**Audit date:** 2026-07-21  
**Authority:** This task is the user's explicit implementation request. It overrides any repository guidance that would otherwise classify frontend work as presentation-only.

---

## 1. Executive verdict

Claude, the current repository contains roughly **30% of the infrastructure needed by the previous authentication-remediation task**, but it does not contain the repository-level fix requested by the user. The useful 30% was largely present before the last correction document:

- strict backend `dev` versus `session` transport semantics;
- password credentials and opaque revocable sessions;
- signup, login, logout, and first-Admin bootstrap primitives;
- server-side role resolution;
- service-token verification for non-human principals;
- some backend integration tests and a session-mode browser suite.

The remaining work is not cosmetic. The missing 70% is the integration contract that makes those parts behave as one system:

- the frontend does not know the runtime authentication mode;
- the UI selects authentication controls from local token presence instead of server mode;
- all frontend transports can send both credential mechanisms at once;
- the default local profile is still `dev` while the UI offers real login;
- normal seeding can create a credentialless Admin that blocks real Admin bootstrap;
- an existing database has no safe session-mode upgrade path;
- invalid sessions are not centrally cleared;
- the SSE channel is unauthenticated and cannot carry the current Bearer/header model;
- tests deliberately use setup paths that mask the real default-installation and upgrade failures.

This document is not a proposal and not a request for another analysis. Implement every mandatory item, prove it with the required tests, and deliver the resulting commit/PR and evidence.

---

## 2. The three questions you must understand before editing

### 2.1 What did you build?

You built two individually reasonable backend authentication paths:

1. `AUTH_MODE=dev` trusts `X-Actor-Id` locally and resolves the role from the database.
2. `AUTH_MODE=session` accepts a live Bearer session for humans or a service token plus an Agent principal ID for non-human callers.

You also built a frontend that independently knows how to:

- show a real login/signup form;
- store a returned session token;
- show a dev actor input;
- attach a Bearer token;
- attach `X-Actor-Id`.

The defect is that these frontend features are active together without a runtime-mode contract. They are not coordinated with the backend mode.

### 2.2 What were you required to build?

You were required to build **one runtime-selected authentication system**, not two independent feature sets placed next to each other.

The backend runtime mode must be published as a non-secret contract. The frontend must load that contract before deciding what authentication UI to show or which credential to send. Seeding, provisioning, local startup, upgrades, tests, and documentation must use the same mode decision.

In session mode, a successful login must create an identity that every subsequent protected request recognizes. In dev mode, the application must use only the dev actor workflow and must never issue or advertise a human session that the backend will ignore.

### 2.3 What did you misunderstand?

You treated the following incorrect assumptions as if they were true:

- **Incorrect:** “A token exists in local storage, therefore the browser is authenticated.”  
  **Correct:** Authentication is server-resolved. A token is only a candidate credential. `/me` and the active runtime mode determine whether it is valid.

- **Incorrect:** “Sending both headers is safe because the backend ignores one.”  
  **Correct:** That protects the backend from spoofing, but it does not provide deterministic frontend state. It created the exact `login 200 -> protected request 401` failure.

- **Incorrect:** “In dev mode no session token exists.”  
  **Correct:** `/login` is currently available in dev mode and stores a token, so this assumption in `Layout.tsx` is demonstrably false.

- **Incorrect:** “A green session-mode E2E proves local authentication works.”  
  **Correct:** CI rewrites `AUTH_MODE` to session and uses a special seed mode that skips the blocking Admin. It does not test the normal defaults or an existing database.

- **Incorrect:** “Any active Admin closes first-Admin bootstrap safely.”  
  **Correct:** In session mode an active Admin without a credential cannot log in. Counting that record as an operational Admin can permanently lock out the installation.

- **Incorrect:** “Authentication is a UI-only adjustment, so `frontend/src/lib/*.ts` should not change.”  
  **Correct:** This is a runtime/security integration task. The user explicitly authorizes and requires changes in frontend transport and session logic. The presentation-only restriction in `CLAUDE.md` does not apply to this task.

---

## 3. Current failure, reproduced from code and runtime

The current repository produces the failure through this chain:

1. `.env.example` sets `AUTH_MODE=dev`.
2. `Login.tsx` always renders a working login/signup form.
3. `useLogin` stores the token returned by `/auth/login`.
4. `Layout.tsx` sees the token and hides `DevActorControl`.
5. `apiClient.ts` sends the Bearer token.
6. `deps.py`, correctly following dev-mode rules, ignores the Bearer token and looks only for `X-Actor-Id`.
7. The frontend has hidden the only control that can set the accepted dev identity.
8. `/me` becomes anonymous and protected pages return `UNAUTHENTICATED`.

The running `/meta` response currently contains only:

```json
{
  "name": "Entropia V18",
  "version": "0.1.0",
  "environment": "local",
  "api_base_path": "/api/v1"
}
```

It does not disclose `auth_mode`, so the browser cannot resolve the ambiguity.

---

## 4. What is already correct and must be preserved

Do not rewrite working security boundaries merely to make the frontend easier.

### 4.1 Preserve strict backend mode selection

`backend/src/entropia/apps/api/deps.py` correctly does the following:

- session mode accepts a valid human Bearer session;
- session mode ignores a bare human `X-Actor-Id`;
- the service line requires the configured service token and an enabled non-human principal;
- the service line cannot impersonate a human;
- dev mode resolves only the dev actor header;
- roles are re-read from the database on every request.

Do not add a fallback from an invalid session to `X-Actor-Id`. Do not trust a client-supplied role. Do not accept dev mode outside `ENTROPIA_ENV=local`.

### 4.2 Preserve credential and session security

Keep the following existing properties:

- Argon2id password hashes;
- opaque random session tokens;
- only token hashes stored in the database;
- expiration and revocation checks;
- generic invalid-credential responses;
- audit events for login success/failure and session closure;
- server-side role resolution.

### 4.3 Preserve user data and ownership

The upgrade must not delete, rename, demote, reassign, or rewrite the existing `user_admin` principal or its domain ownership. Existing audit rows, outbox rows, revisions, datasets, packages, strategies, results, and other user-owned data must remain untouched.

---

## 5. Exhaustive findings and required corrections

## AUTH-01 — Runtime auth mode is missing from the public metadata contract

**Severity:** P0  
**Evidence:** `backend/src/entropia/apps/api/routes/meta.py`, `frontend/src/lib/types.ts`, `docs/openapi.json`

**Claude, you did this:** You published environment and build metadata, but not the authentication mode.

**You should have done this:** Publish a closed `dev | session` value from the same `Settings` object that drives `request_context`.

**You misunderstood this:** The frontend cannot infer backend authentication policy from token presence, build-time variables, hostname, or environment name.

**Required correction:**

- Add `auth_mode: Literal["dev", "session"]` to `MetaResponse`.
- Populate it from `get_settings().auth_mode`.
- Add `auth_mode: "dev" | "session"` to the frontend `Meta` type.
- Regenerate and commit `docs/openapi.json`.
- Add backend route/contract tests for both values.
- Add frontend type/contract fixtures containing the field.
- Do not expose service-token state, bootstrap email, tokens, or secrets.

**Proof required:** A real `GET /api/v1/meta` in each profile returns the exact active mode.

## AUTH-02 — There is no application-wide runtime authentication state

**Severity:** P0  
**Evidence:** `useMeta()` is consumed only as an ordinary React Query inside `Layout`; `Login` is outside the layout; `apiClient` has no mode input.

**Claude, you did this:** You fetched `/meta` for an environment badge after the application shell had already started its other queries.

**You should have done this:** Initialize a single runtime-auth state before rendering mode-dependent routes and before protected requests choose credentials.

**You misunderstood this:** `/meta` is not merely decorative metadata. Its `auth_mode` value is a boot contract.

**Required correction:**

- Introduce a small runtime-auth store/provider, for example `runtimeAuth.ts` plus `RuntimeAuthProvider`.
- Model at least `loading`, `ready`, and `error`; `ready` must carry `dev | session`.
- Load `/meta` through an explicitly anonymous bootstrap request that does not depend on already initialized auth state.
- Mount the provider high enough to cover both `/login` and the app shell.
- While mode is loading, show a neutral bootstrap state; do not render Login, Logout, or DevActorControl.
- On metadata failure, fail closed with a visible retry action. Do not guess a mode.
- Avoid circular imports between the runtime store, API client, QueryClient, and router.

**Proof required:** A delayed `/meta` test shows no incorrect auth controls before the response arrives.

## AUTH-03 — The application shell chooses UI from token presence instead of runtime mode

**Severity:** P0  
**Evidence:** `Layout.tsx` renders `{token ? null : <DevActorControl />}` and `AuthControl` uses only the stored token.

**Claude, you did this:** You treated a local token as the switch between real login and dev impersonation.

**You should have done this:** Use `meta.auth_mode` as the primary switch and `/me` as server truth inside the selected mode.

**You misunderstood this:** A stale or ignored token is not an authenticated state and must never hide the accepted credential control.

**Required correction:**

- In session mode, render only Login/Sign Up or validated session identity plus Logout.
- In session mode, never render `DevActorControl`.
- In dev mode, render `DevActorControl` regardless of any stored session token.
- In dev mode, never render a functional Login/Sign Up or Logout control.
- Do not show “signed in” merely because a token exists.
- Gate role/admin presentation on the server `/me` projection, as the current code already does for menus.

**Proof required:** Component tests cover the complete matrix: mode, token present/absent, `/me` authenticated/anonymous, and metadata loading/error.

## AUTH-04 — The login route remains functional in dev mode

**Severity:** P0  
**Evidence:** `/login` is an unconditional route and `Login.tsx` never reads runtime mode. Backend `/auth/login` issues a token in either mode.

**Claude, you did this:** You built a real login endpoint and page without checking whether the running backend will honor the returned session.

**You should have done this:** Prevent dev mode from advertising or issuing a human session that the request pipeline deliberately ignores.

**You misunderstood this:** Hiding a navigation link is insufficient. A direct visit and a direct API call can still reproduce the impossible-success sequence.

**Required correction:**

- Direct `/login` in dev mode must show a clear local-development explanation and a link back to the application.
- The form must not render in dev mode.
- Add a typed backend mode-mismatch rejection for `POST /auth/login` in dev mode so the API cannot return an unusable session token. Use a stable canonical error code such as `AUTH_MODE_MISMATCH`; do not return 200.
- Dev-mode signup may remain available as an explicit test/developer account-creation primitive if needed, but it must not auto-login or claim a usable Bearer session.
- Session mode must retain the current login/signup behavior.

**Proof required:** Dev-mode direct browser and API tests prove that no successful ignored session can be created.

## AUTH-05 — JSON and text requests send both human credential mechanisms

**Severity:** P0  
**Evidence:** `apiClient.ts::executeRequest` and `apiGetText` independently attach Bearer and `X-Actor-Id` whenever each local value exists.

**Claude, you did this:** You relied on the backend to ignore the wrong header.

**You should have done this:** Select exactly one human credential transport from runtime mode.

**You misunderstood this:** Backend spoofing resistance does not make ambiguous frontend state correct.

**Required correction:**

- Build one shared credential-header selector driven by the initialized runtime mode.
- Session mode: add only `Authorization: Bearer <session-token>` when a token exists.
- Dev mode: add only `X-Actor-Id: <dev-actor-id>` when an actor is selected.
- Anonymous bootstrap endpoints (`/meta`, health, signup, login, bootstrap status) must remain callable before identity initialization.
- A stale session token in dev mode must not be sent.
- A stale dev actor value in session mode must not be sent.
- Preserve caller-supplied OCC, ETag, Idempotency-Key, and content headers.

**Proof required:** Unit tests inspect headers for JSON GET/POST and text GET under both modes and with both stale values simultaneously present.

## AUTH-06 — Multipart uploads duplicate the same mode error

**Severity:** P0  
**Evidence:** `frontend/src/lib/upload.ts` reads both stores and attaches both headers.

**Claude, you did this:** You fixed ordinary fetch behavior in one place but left a separate XHR credential implementation.

**You should have done this:** Reuse the same mode-aware header decision in every transport.

**You misunderstood this:** Market Data, Research Data, Package, Trading Signal, and Trade Log uploads are protected requests too.

**Required correction:**

- Make XHR upload authentication use the shared mode-aware selector.
- Do not duplicate mode logic in `upload.ts`.
- Route canonical session-invalid upload responses through the same stale-session handler as normal fetch requests.
- Preserve progress, cancellation, multipart fields, OCC headers, and Idempotency-Key behavior.

**Proof required:** Upload tests assert mutually exclusive headers in both modes and session invalidation behavior.

## AUTH-07 — Local storage is presented as identity truth

**Severity:** P0  
**Evidence:** `AuthControl` displays `getStoredUser()` and “signed in” solely when a token exists.

**Claude, you did this:** You used the login response cache as proof of a current identity.

**You should have done this:** Treat stored user metadata as display-only and only after `/me` validates the session in session mode.

**You misunderstood this:** The stored role/name can outlive token expiration, revocation, account disablement, or a backend mode change.

**Required correction:**

- Use `/me.is_authenticated` to decide whether a session is authenticated.
- While a stored token is being validated, render a neutral “validating session” state.
- Never render authenticated controls when `/me` is anonymous.
- Continue using the server role/admin projection; never trust the role copied into local storage.
- If display name remains locally cached, use it only after the server confirms the same session principal.

**Proof required:** A token plus anonymous `/me` never renders a signed-in user.

## AUTH-08 — Canonical invalid sessions are not centrally handled

**Severity:** P0  
**Evidence:** `apiClient` throws `ApiError`; only explicit logout calls `clearSession`; no `SESSION_INVALID` coordinator exists.

**Claude, you did this:** You displayed repeated 401 errors and left the invalid token in storage.

**You should have done this:** Clear the invalid session exactly once, invalidate identity-bound cache, and route the user to login where appropriate.

**You misunderstood this:** Rendering an error is not session lifecycle management. The same stale token continues to poison every request.

**Required correction:**

- Trigger invalidation only for the canonical `status=401` and `code=SESSION_INVALID` response.
- Clear the local session once even if many concurrent requests fail.
- Cancel/remove or invalidate identity-dependent queries so previous-user data is not displayed.
- Redirect protected-route users to `/login`, preserving a safe internal return path.
- Do not redirect when already on `/login`.
- Do not retry the failed request automatically.
- Reset the one-shot guard after a later successful login.
- Apply the same handling to JSON, text, upload, and authenticated event-stream handshakes.

**Proof required:** Concurrent `SESSION_INVALID` responses produce one clear and one navigation, with no retry/redirect loop.

## AUTH-09 — All 401 responses are incorrectly treated as “go to login”

**Severity:** P1  
**Evidence:** `ErrorState.tsx` maps every `ApiError` with status 401 to the same Login action.

**Claude, you did this:** You classified by HTTP status only.

**You should have done this:** Distinguish missing authentication, invalid session, invalid credentials, and re-authentication failures by canonical code and context.

**You misunderstood this:** Not every 401 means that the global browser session should be destroyed.

**Required correction:**

- `SESSION_INVALID` uses the central invalid-session flow.
- `UNAUTHENTICATED` may show Login in session mode, but in dev mode it must instruct the user to select a dev actor.
- `INVALID_CREDENTIALS` on login/reauth stays local to that form and must not clear another valid session unless the server explicitly says the session is invalid.
- Never clear a session for `403`, `ACCESS_DENIED`, `FORBIDDEN`, or Admin-only denial.

**Proof required:** Tests cover each canonical code and prove 403 leaves the session intact.

## AUTH-10 — Session state is not synchronized across browser tabs

**Severity:** P1  
**Evidence:** `session.ts` notifies only in-memory listeners and does not listen for the browser `storage` event.

**Claude, you did this:** You made session state reactive only within one tab.

**You should have done this:** Propagate login/logout/clear events across tabs using the existing external-store model.

**You misunderstood this:** `localStorage` writes do not automatically call the current module's listener set in other tabs.

**Required correction:**

- Add a single `storage` listener for the session keys.
- Emit store updates when another tab changes or removes the session.
- Avoid registering duplicate listeners under React Strict Mode/HMR.
- Test logout in one simulated tab updates the other subscriber.

## AUTH-11 — The SSE stream is outside the authentication model and leaks raw global events

**Severity:** P0 security  
**Evidence:** Backend `GET /events` has no actor dependency; frontend native `EventSource` cannot send Bearer or `X-Actor-Id`; backend broadcasts raw outbox event dictionaries to every subscriber.

**Claude, you did this:** You treated SSE as a harmless refresh channel and left it anonymous, while sending complete outbox payloads.

**You should have done this:** Authenticate the stream consistently and expose only the minimum non-sensitive invalidation signal the frontend actually consumes.

**You misunderstood this:** “Refresh signal” does not mean its payload is public. Native EventSource also cannot satisfy the current header-based auth contract.

**Required correction:**

- Require an authenticated actor for `/events` in both modes.
- Do not hold a request-scoped database session open for the entire stream; authenticate during the handshake with a short-lived session, then close it before streaming.
- Replace native EventSource with a fetch-stream SSE client or another header-capable implementation.
- Use the same mode-aware credential selector.
- On a `SESSION_INVALID` handshake, invoke the global invalid-session flow.
- Do not put human session tokens in query parameters or logs.
- Since the frontend ignores event data, stop broadcasting raw outbox payloads. Emit a minimal non-sensitive invalidation envelope, or implement authorization-aware per-subscriber filtering.
- Preserve reconnect backoff, pagehide/pageshow cleanup, heartbeat behavior, and cache invalidation taxonomy.

**Proof required:** Anonymous stream access fails; dev and session authenticated streams connect; raw domain/audit payloads are absent; reconnect behavior remains tested.

## BACK-01 — Backend login can return a token that the selected mode will never accept

**Severity:** P0  
**Evidence:** Auth routes do not consult `settings.auth_mode` before login; `deps.py` intentionally ignores sessions in dev mode.

**Claude, you did this:** You made token issuance independent from token acceptance.

**You should have done this:** Make those two decisions mode-consistent.

**You misunderstood this:** UI gating alone does not make the acceptance criterion “login 200 -> protected 401 is impossible” true at the API boundary.

**Required correction:** Reject human login in dev mode with the canonical mode-mismatch error described in AUTH-04. Do not modify `deps.py` to accept Bearer as a dev fallback.

## PROV-01 — Identity seeding is not auth-mode aware

**Severity:** P0  
**Evidence:** `apps/seed.py::_seed` calls `seed_identities` unless `SEED_E2E_GOLDEN`; `seed_identities` always creates an active Admin without a credential and an Agent; the code does not read `Settings.auth_mode`.

**Claude, you did this:** You treated the old dev impersonation seed as a universal installation seed.

**You should have done this:** Seed human dev identities only in explicit dev mode, while still provisioning required system identities in session mode.

**You misunderstood this:** A credentialless Admin is usable through `X-Actor-Id` but unusable through session login.

**Required correction:**

- Split system/Agent seeding from dev human seeding.
- Session mode: ensure required Agent/system principals and baseline capabilities, but do not create the credentialless Admin HumanUser.
- Dev mode: preserve the explicit `user_admin` and Agent seed behavior.
- Read mode from `get_settings()` at execution time; do not rely on unrelated E2E flags.
- Keep the operation idempotent.

**Proof required:** Fresh session seed has no credentialless human Admin; fresh dev seed has the expected dev Admin; both contain the required Agent/system rows.

## PROV-02 — The existing credentialless Admin blocks real Admin bootstrap

**Severity:** P0  
**Evidence:** `sign_up` uses `count_active_admins() == 0`; the count does not join `human_credentials`.

**Claude, you did this:** You implemented a secure “only first Admin” count without defining what an operational Admin means in session mode.

**You should have done this:** In session mode, close bootstrap only when an active login-capable Admin exists.

**You misunderstood this:** An active role row without credentials is not an administrator who can recover or operate a session-mode installation.

**Required correction:**

- Add a repository query for active **login-capable** Admins: active/non-deleted `HumanUser`, role Admin, joined to a valid `HumanCredential`.
- Under the existing advisory lock, session-mode bootstrap must use this operational count.
- If the only Admin is the legacy credentialless `user_admin`, allow the configured bootstrap-email signup to create a new real Admin.
- Do not delete, demote, rename, attach a guessed password to, or transfer ownership from the legacy principal.
- Preserve the existing dedicated bootstrap audit/outbox event; add an auditable reason/metadata indicating legacy upgrade when applicable without exposing credentials or email.
- If an active credentialed Admin already exists, remain fail-closed.

**Proof required:** A database containing credentialless `user_admin` plus owned domain data can bootstrap a new credentialed Admin; every existing row and owner ID remains unchanged.

## PROV-03 — Last-Admin protection can still lock a session installation

**Severity:** P0  
**Evidence:** `application/commands/role_assignment.py` and `application/commands/roles.py` use `count_active_admins`, which counts the legacy credentialless Admin. The older `roles.py` path also lacks the shared advisory lock around count-and-demote.

**Claude, you did this:** You protected against reaching zero Admin role rows, not against reaching zero administrators who can log in.

**You should have done this:** Protect the last operational Admin according to the active authentication mode.

**You misunderstood this:** After legacy upgrade, the credentialless Admin can make the count equal two and allow demotion of the only real session Admin, locking the installation again.

**Required correction:**

- In session mode, last-Admin protection must count active credentialed Admins.
- In dev mode, it may count active dev Admin role rows.
- Apply the same advisory lock and same invariant to every role-change endpoint, including the legacy `/users/{id}/role` command path.
- Add concurrency and legacy-data regression tests.

## PROV-04 — Seed idempotency fails for partial principal state

**Severity:** P1  
**Evidence:** `seed_identities` checks for `HumanUser`, then unconditionally inserts `Principal`; `_ensure_admin_principal` can legitimately leave a bare Principal.

**Claude, you did this:** You tested idempotency only after both parent and child rows existed.

**You should have done this:** Make each parent/child ensure operation idempotent independently.

**You misunderstood this:** E2E and interrupted upgrades can leave a valid bare Principal without a HumanUser or Agent child.

**Required correction:**

- Check/ensure Principal separately from HumanUser or Agent.
- Validate an existing principal has the expected principal type; fail closed on a type conflict.
- Never insert a duplicate Principal.
- Add tests for bare human principal, bare agent principal, complete identity, and conflicting type.

## PROV-05 — Bootstrap status reports the wrong operational truth

**Severity:** P1  
**Evidence:** `/auth/bootstrap-status` exposes only `active_admin_exists`, using the non-credential-aware count.

**Claude, you did this:** You told the operator the bootstrap window was closed even when nobody could log in as Admin.

**You should have done this:** Report enough non-PII booleans to distinguish role existence from session-operable Admin existence.

**You misunderstood this:** The provisioning page is an operational recovery tool, not merely a role-table viewer.

**Required correction:**

- Preserve booleans only; never expose the configured email.
- Add an operational field such as `login_capable_admin_exists` and, if useful, `legacy_credentialless_admin_exists`.
- Derive whether bootstrap is open from the same locked rule used by signup, not a contradictory UI-only formula.
- Update `Provisioning.tsx`, its types, OpenAPI, and tests.

## PROV-06 — Normal Compose startup does not perform mode-safe baseline provisioning

**Severity:** P1  
**Evidence:** Compose runs migrations but no normal seed/provisioning one-shot; E2E manually executes the seed afterward.

**Claude, you did this:** You left Agent/capability provisioning as a manual command and relied on the test workflow to run it.

**You should have done this:** Make normal local startup deterministically provision required non-human/baseline rows without creating a session-blocking human Admin.

**You misunderstood this:** Migration success does not imply runtime bootstrap success.

**Required correction:** Add a mode-aware, idempotent provisioning step after migrations and before services that require system identities. Do not seed demo/user-owned domain data unless explicitly requested.

## DEP-01 — The recommended local-browser profile still defaults to dev impersonation

**Severity:** P0  
**Evidence:** `.env.example`, `Settings.auth_mode`, README, and `docs/USAGE.md` call dev the default.

**Claude, you did this:** You documented how to switch to session manually.

**You should have done this:** Make normal local browser use session mode by default and make dev impersonation an explicit opt-in profile.

**You misunderstood this:** Documentation cannot repair a default that immediately presents a contradictory UI.

**Required correction:**

- `.env.example` for normal local browser use must use `AUTH_MODE=session`.
- Define a separate explicit dev-auth environment/Compose override or command.
- Keep `Settings` test defaults deliberate; do not let test convenience silently dictate product startup defaults.
- Name commands clearly, for example `up` for session and `up-dev-auth` for impersonation.

## DEP-02 — Session mode permits an empty service token

**Severity:** P0 operational/security  
**Evidence:** `.env.example` leaves `ENTROPIA_SERVICE_TOKEN` empty; Settings explicitly treats empty as disabled; E2E switches to session without generating a token.

**Claude, you did this:** You made the service line optional even in the full local stack.

**You should have done this:** Ensure a strong, nonempty, noncommitted token exists for the normal session profile.

**You misunderstood this:** The fact that current scheduler/workers primarily call application/DB code directly does not justify shipping an unusable API service-auth line.

**Required correction:**

- Generate at least 32 random bytes for a missing local service token during explicit local configuration.
- Never commit or print the token.
- Never reuse a human session token.
- Do not overwrite an existing nonempty token.
- Make the full session profile fail clearly if the token is missing, or make startup generation deterministic before containers start.
- Update E2E setup to generate a test-only token.
- Do not add unnecessary internal HTTP self-calls merely to “use” the token; prove existing processes remain healthy.

## DEP-03 — Update scripts preserve secrets but do not migrate configuration safely

**Severity:** P0 upgrade  
**Evidence:** `update.ps1` and `update.sh` leave every existing `.env` untouched and then declare the update complete.

**Claude, you did this:** You correctly avoided overwriting secrets, but you also ignored newly required keys and legacy unsafe defaults.

**You should have done this:** Perform a non-destructive configuration audit/migration.

**You misunderstood this:** “Do not overwrite secrets” does not mean “never inspect or report configuration drift.”

**Required correction:**

- Detect missing required keys without echoing their values.
- Append only genuinely missing non-secret keys where safe.
- Generate a missing service token without replacing an existing one.
- Detect legacy `AUTH_MODE=dev` and require an explicit session/dev profile choice; do not silently change an intentional dev setup.
- Provide a dedicated idempotent `configure-local-session` command that changes only the necessary auth keys and optionally records the bootstrap email.
- Create a timestamped `.env` backup before any explicit migration.
- Never log passwords, tokens, or bootstrap email.
- Return nonzero on unresolved required configuration instead of printing “Update complete.”

## DEP-04 — Docker and task runners do not expose explicit authentication profiles

**Severity:** P1  
**Evidence:** One Compose file and generic `up/restart` commands consume whichever `.env` happens to exist.

**Claude, you did this:** You overloaded one implicit configuration file with two incompatible use cases.

**You should have done this:** Make profile selection visible and reproducible.

**You misunderstood this:** An environment comment is not an operational profile.

**Required correction:**

- Add explicit session and dev-auth startup commands/overrides for Windows and POSIX.
- Ensure `bootstrap.ps1`, `bootstrap.sh`, `dev.ps1`, `dev.sh`, `tasks.ps1`, and Makefile agree.
- Default browser startup to session.
- Keep dev impersonation local-only and visibly named.
- Preserve existing volumes unless the operator explicitly requests destructive reset.

## DEP-05 — Runtime health evidence does not cover scheduler, coordinator, and every worker

**Severity:** P1  
**Evidence:** `/health/ready` checks Postgres, Redis, and object storage only; most Compose worker services have no healthcheck.

**Claude, you did this:** You equated API dependency readiness with full-stack process health.

**You should have done this:** Prove every long-running process starts and performs its intended work under session configuration.

**You misunderstood this:** A running API does not prove workers or coordinator are operational.

**Required correction:** Add meaningful health/evidence appropriate to each process, or exercise each worker plane through real jobs in acceptance tests and assert terminal success. At minimum, fail acceptance if any Compose service exits/restarts or logs repeated configuration/provisioning errors.

## DEP-06 — User documentation and smoke checks describe the old contradictory model

**Severity:** P1  
**Evidence:** README and `docs/USAGE.md` call dev default; `smoke.sh` primarily uses `X-Actor-Id` and only warns that session may be active.

**Claude, you did this:** You documented both modes but did not document a single safe default workflow or migration.

**You should have done this:** Give separate, copy-pasteable session and dev-auth runbooks.

**You misunderstood this:** A user following the recommended quick start should not need to understand the internal mismatch before the app works.

**Required correction:**

- Normal local session setup, first Admin, login, refresh, logout, and restart instructions.
- Explicit dev-auth setup and DevActorControl instructions.
- Existing-database upgrade instructions that preserve data.
- Session-aware and dev-aware smoke commands with real assertions.
- Remove statements that imply login and dev actor controls coexist safely.

## TEST-01 — No `/meta.auth_mode` contract tests exist

**Severity:** P0 test gap

**Claude, you did this:** You tested Settings values but not the public contract consumed by the frontend.

**You should have done this:** Test the route, generated schema, frontend type, and runtime bootstrap.

**You misunderstood this:** An internal configuration test does not prove that the running browser can discover the configuration.

**Required correction:** Add backend tests for dev/session metadata, regenerate OpenAPI, and add frontend contract/bootstrap tests.

## TEST-02 — Frontend tests do not cover the mode/UI matrix

**Severity:** P0 test gap

**Claude, you did this:** Existing auth tests check token storage and a Bearer header only.

**You should have done this:** Test every mode-dependent control and stale-value combination.

**You misunderstood this:** Testing each feature in isolation does not test the mode-selection state machine that decides which feature is legal.

**Required correction:** Add tests for:

- dev mode with no token;
- dev mode with stale token;
- session mode with no token;
- session mode with valid token and authenticated `/me`;
- session mode with token but anonymous/invalid `/me`;
- mode loading and metadata error;
- direct `/login` in dev;
- no DevActorControl in session;
- no functional login controls in dev;
- no client-supplied role decisions.

## TEST-03 — Transport tests do not prove mutual exclusivity

**Severity:** P0 test gap

**Claude, you did this:** You asserted Bearer is attached when a token exists and omitted when absent.

**You should have done this:** Assert the full mode-driven header matrix across fetch, text, XHR upload, and the event stream.

**You misunderstood this:** The important invariant is not merely that a valid header can be added; it is that the incompatible header can never be added in the selected mode.

**Required correction:** Put both stale local values in storage, choose one runtime mode, and prove only the permitted header is sent.

## TEST-04 — Backend tests miss the exact dev-mode Bearer failure

**Severity:** P0 test gap

**Claude, you did this:** You tested session mode ignoring a bare actor header but did not test dev mode ignoring Bearer or rejecting login issuance.

**You should have done this:** Pin both sides of the strict mode contract.

**You misunderstood this:** A one-directional test allows the exact opposite-direction mismatch to survive unnoticed.

**Required correction:** Add tests proving:

- dev request context ignores Bearer and resolves only dev actor;
- dev login returns typed mode mismatch, not 200;
- session mode ignores bare human actor header;
- session mode accepts a valid Bearer;
- service token cannot impersonate a human;
- non-local dev configuration fails startup.

## TEST-05 — Provisioning tests use a fresh database and miss the real upgrade case

**Severity:** P0 test gap

**Claude, you did this:** You proved bootstrap with zero Admins and fail-closed behavior with a credentialed Admin created by signup.

**You should have done this:** Test the exact legacy database produced by the old seed.

**You misunderstood this:** A fresh schema is not representative of an upgraded installation whose blocking record was created by an earlier release.

**Required correction:** Build an integration fixture containing:

- `user_admin` active Admin HumanUser with no credential;
- its Principal row;
- representative domain rows owned/created by that principal;
- audit/outbox history;
- required Agent/system identities.

Run the upgrade/provisioning path twice. Prove a new bootstrap-email signup becomes a credentialed Admin, a second attempt does not create another Admin, every legacy row remains unchanged, and last-operational-Admin protection works.

## TEST-06 — E2E rewrites the mode and masks the default-installation defect

**Severity:** P0 test design defect  
**Evidence:** `.github/workflows/e2e.yml` copies `.env.example` and uses `sed` to switch to session.

**Claude, you did this:** You proved an explicitly repaired test environment, not the recommended local default.

**You should have done this:** Make the recommended session profile itself correct and test it without ad hoc mode surgery.

**You misunderstood this:** Test setup that silently fixes the product configuration can only prove the test setup, not the user's installation path.

**Required correction:** The session E2E job must use the same normal-local profile users receive. Any test-only values may supply secrets/email, but must not correct a wrong auth-mode default.

## TEST-07 — E2E special seeding masks the credentialless-Admin blocker

**Severity:** P0 test design defect  
**Evidence:** `SEED_E2E_GOLDEN=1` deliberately skips `seed_identities`.

**Claude, you did this:** You bypassed the exact state that existing installations contain.

**You should have done this:** Keep the clean-install test and add a separate legacy-upgrade test.

**You misunderstood this:** A fixture designed to make a golden path possible cannot serve as evidence for the migration path it intentionally skips.

**Required correction:** Do not remove the useful golden fixture, but never use it as evidence that normal seed/upgrade behavior is correct. Add a dedicated legacy-volume upgrade E2E or integration test.

## TEST-08 — Auth E2E assertions are too weak

**Severity:** P0 test design defect  
**Evidence:** `01-auth.spec.ts` mostly asserts URL, Mainboard heading, and header controls.

**Claude, you did this:** You used a static page heading as the post-login success anchor.

**You should have done this:** Assert server authentication and protected responses directly.

**You misunderstood this:** The Mainboard heading may render while its protected query displays `UNAUTHENTICATED`.

**Required correction:** The real session E2E must assert:

1. signup creates the exact user;
2. auto-login or login stores a session;
3. `/me` returns `is_authenticated=true`, exact principal ID, and server role;
4. `/mainboards/default` is not 401;
5. `/strategy-drafts` is not 401;
6. protected UI contains no `UNAUTHENTICATED` state;
7. refresh keeps the same principal;
8. logout revokes and clears the session;
9. the old token receives `SESSION_INVALID` after logout;
10. a normal User does not receive Admin UI;
11. service processes remain healthy.

## TEST-09 — There is no real dev-mode browser acceptance flow

**Severity:** P0 test gap

**Claude, you did this:** One E2E helper probes mode and adapts, but no test asserts the dev-mode UI contract.

**You should have done this:** Run an explicit dev-auth stack and assert its visible and transport behavior.

**You misunderstood this:** An adaptive helper that works around either mode is not a test that either mode satisfies its own contract.

**Required correction:** Add a dev E2E that proves:

- Login/Sign Up form is not offered;
- direct `/login` shows the dev explanation;
- DevActorControl is always visible even with a stale token in storage;
- selecting `user_admin` authenticates through `X-Actor-Id`;
- requests do not send Bearer;
- protected pages work;
- dev mode remains impossible outside local environment.

## TEST-10 — Stale-session behavior has no regression suite

**Severity:** P0 test gap

**Claude, you did this:** You tested explicit logout and generic 401 rendering, but not server-revoked, expired, or invalid tokens already stored by the browser.

**You should have done this:** Test the complete invalid-session lifecycle, including concurrency, cache cleanup, navigation, and re-login.

**You misunderstood this:** Logout success is not representative of an asynchronous server-side session invalidation discovered by unrelated protected requests.

**Required correction:** Add frontend tests for invalid, expired, revoked, concurrent failures, 403 preservation, query cleanup, safe return path, login reset, and no loop. Add a real browser test that corrupts/revokes the token and observes one clean return to login.

## TEST-11 — The generic Makefile test target hides frontend failure

**Severity:** P1 CI/local integrity  
**Evidence:** `Makefile` runs `npm test --silent || true`.

**Claude, you did this:** You made the aggregate test command succeed even when frontend tests fail.

**You should have done this:** Propagate the frontend test exit code.

**You misunderstood this:** A convenience target must not produce false-green acceptance evidence.

**Required correction:** Remove `|| true`. Mirror fail-fast behavior in Windows task scripts and document the authoritative commands.

## TEST-12 — There is no complete delivery evidence package

**Severity:** P1 process

**Claude, you did this:** Prior work reported existing tests and architecture without demonstrating every requested acceptance flow.

**You should have done this:** Deliver changed files, migration/configuration action, commands, exact results, and honest boundaries.

**You misunderstood this:** A completion claim is not evidence unless every requested operating mode and upgrade path is tied to a reproducible passing result.

**Required correction:** The final PR description must map every acceptance criterion below to code and a passing test/evidence artifact. “Tests pass” without command and result is insufficient.

---

## 6. Required target architecture

The exact symbol names may differ, but the following responsibilities are mandatory.

### 6.1 Runtime mode bootstrap

```text
Browser starts
  -> anonymous GET /meta
  -> validate auth_mode is dev|session
  -> publish ready runtime-auth state
  -> render the matching auth UI
  -> enable protected queries with one credential mechanism
```

Public bootstrap requests must not wait on identity. Protected page queries should not race ahead while mode is unknown.

### 6.2 One credential-header function

All transports must call one deterministic function:

```text
mode=session + token -> Authorization only
mode=session + no token -> no human auth header
mode=dev + actor -> X-Actor-Id only
mode=dev + no actor -> no human auth header
mode=unknown -> only explicitly anonymous bootstrap calls are permitted
```

No code path may independently read both stores and attach both credentials.

### 6.3 One invalid-session coordinator

```text
response is 401 SESSION_INVALID
  -> atomic/one-shot invalidation
  -> clear token + cached user
  -> cancel/remove identity-owned queries
  -> redirect once when appropriate
  -> wait for a new successful login before rearming
```

Do not couple navigation directly into low-level fetch code. Use an event/callback/provider boundary that avoids router and QueryClient import cycles.

### 6.4 Mode-aware provisioning

```text
dev seed:
  ensure dev Admin principal + HumanUser
  ensure Agent/system principals
  ensure baseline capabilities

session seed:
  DO NOT create credentialless Admin HumanUser
  ensure Agent/system principals
  ensure baseline capabilities
```

### 6.5 Legacy session upgrade algorithm

Use the existing advisory lock. Under session mode:

1. Count active credentialed Admins.
2. If at least one exists, bootstrap remains closed.
3. If none exists and bootstrap email matches, allow creation of the new credentialed Admin even if credentialless legacy Admin rows exist.
4. Audit the new Admin bootstrap and note legacy-upgrade context without PII.
5. Leave all legacy rows and ownership untouched.
6. Make repeated execution a no-op/fail-closed after the first credentialed Admin exists.
7. Use the same operational count for last-Admin protection.

### 6.6 Authenticated minimal SSE

The stream is a cache invalidation mechanism. It must authenticate during handshake and send only the minimum event classification needed by the frontend. Do not expose raw global outbox payloads. Do not hold a database connection for the lifetime of the stream.

---

## 7. Mandatory implementation order

Follow this order so later work cannot be built on ambiguous state.

1. Add backend `/meta.auth_mode`, tests, and OpenAPI snapshot.
2. Add frontend runtime-auth bootstrap/provider and neutral loading/error states.
3. Make Layout and Login route mode-aware.
4. Make backend dev login fail with a typed mode-mismatch error.
5. Centralize mutually exclusive auth headers for JSON, text, uploads, and event streaming.
6. Add one-shot canonical stale-session handling and cross-tab synchronization.
7. Authenticate/minimize the SSE channel.
8. Split mode-aware system/dev seeding.
9. Add legacy credentialless-Admin upgrade semantics and operational Admin count.
10. Apply operational last-Admin protection to every role-change path.
11. Add safe local session configuration, strong service-token generation, explicit dev profile, Compose provisioning, and update migration.
12. Update README, USAGE, backend README, smoke scripts, Makefile, PowerShell tasks, and E2E setup.
13. Add the full unit/integration/E2E matrix.
14. Run all verification commands against isolated test databases and isolated Compose projects.
15. Commit, open a PR, wait for all checks, and provide the evidence report. Do not stop at an implementation plan.

---

## 8. Expected file surface

At minimum inspect and, where required, modify:

### Backend

- `backend/src/entropia/config/settings.py`
- `backend/src/entropia/apps/api/routes/meta.py`
- `backend/src/entropia/apps/api/routes/auth.py`
- `backend/src/entropia/apps/api/deps.py` — preserve strict semantics; change only if needed for reusable handshake logic
- `backend/src/entropia/apps/api/sse.py`
- `backend/src/entropia/application/commands/auth.py`
- `backend/src/entropia/application/commands/role_assignment.py`
- `backend/src/entropia/application/commands/roles.py`
- `backend/src/entropia/infrastructure/postgres/repositories/auth.py`
- `backend/src/entropia/infrastructure/postgres/repositories/identity.py`
- `backend/src/entropia/apps/seed.py`
- `backend/src/entropia/shared/errors.py`
- backend unit, integration, and contract tests
- `docs/openapi.json`

### Frontend

- `frontend/src/main.tsx` and/or `frontend/src/App.tsx`
- `frontend/src/app/Layout.tsx`
- `frontend/src/pages/Login.tsx`
- `frontend/src/pages/Provisioning.tsx`
- `frontend/src/lib/types.ts`
- `frontend/src/lib/hooks.ts`
- `frontend/src/lib/apiClient.ts`
- `frontend/src/lib/auth.ts`
- `frontend/src/lib/session.ts`
- `frontend/src/lib/devActor.ts`
- `frontend/src/lib/upload.ts`
- `frontend/src/lib/sse.ts`
- a new runtime-auth store/provider if appropriate
- frontend unit/integration tests and E2E fixtures/specs

### Deployment and documentation

- `.env.example`
- explicit dev-auth env/Compose override or equivalent
- `docker-compose.yml`
- `scripts/bootstrap.ps1`, `scripts/bootstrap.sh`
- `scripts/update.ps1`, `scripts/update.sh`
- `scripts/dev.ps1`, `scripts/dev.sh`
- `scripts/tasks.ps1`
- `scripts/smoke.sh`
- `Makefile`
- `.github/workflows/ci.yml`
- `.github/workflows/e2e.yml`
- `README.md`
- `docs/USAGE.md`
- `backend/README.md`
- `frontend/e2e/README.md`

Do not limit the diff to this list if another caller duplicates credential or provisioning behavior. Search all direct `fetch`, XHR, EventSource, `Authorization`, `X-Actor-Id`, session-store, seed, and Admin-count usages before declaring completion.

---

## 9. Mandatory automated test matrix

### 9.1 Backend unit/contract

- Settings accepts session locally and non-locally.
- Settings rejects dev outside local.
- Session profile handles missing service token according to the chosen fail-closed setup contract.
- `/meta` returns exact runtime mode.
- `/meta` contains no secret/provisioning data.
- Dev login returns typed mode mismatch.
- OpenAPI snapshot is current and valid.
- SSE anonymous handshake is rejected and payload is minimized.

### 9.2 Backend integration

- Dev mode ignores Bearer and resolves only `X-Actor-Id`.
- Session mode ignores bare human `X-Actor-Id`.
- Valid session resolves exact user and fresh role.
- Invalid, expired, and revoked sessions return `SESSION_INVALID`.
- Service token works only for enabled non-human principals.
- Fresh dev seed is idempotent.
- Fresh session seed does not create credentialless Admin.
- Bare/partial Principal seed states are idempotent.
- Fresh session bootstrap creates first credentialed Admin.
- Legacy credentialless Admin does not block bootstrap.
- Existing credentialed Admin blocks another bootstrap.
- Legacy owned data is byte-for-byte/field-for-field preserved.
- Last operational session Admin cannot be demoted through either role endpoint.
- Concurrent bootstrap and concurrent demotion remain safe under the advisory lock.

### 9.3 Frontend unit/integration

- Metadata loading shows neutral UI.
- Metadata error fails closed and retries.
- Dev mode shows only actor control.
- Session mode shows only real-session controls.
- Stale token in dev cannot alter UI or headers.
- Stale actor in session cannot alter UI or headers.
- Direct login route in dev displays explanation.
- Signup in session auto-logs in and refetches `/me`.
- Stored token is not presented as authenticated until `/me` confirms.
- Canonical invalid session clears once and redirects once.
- 403/access denial does not clear.
- Cross-tab logout updates the UI.
- JSON, text, upload, and SSE transports use the exact credential matrix.
- SSE reconnect/cache invalidation behavior remains green.

### 9.4 Real session-mode Docker E2E

Use an isolated Compose project and isolated volumes. Never destroy the user's normal local database.

1. Build the normal session profile without ad hoc mode replacement.
2. Confirm a strong service token is configured without printing it.
3. Confirm mode-safe provisioning completed.
4. Sign up the bootstrap Admin on a fresh database.
5. Log out and log in again.
6. Assert `/me` exact authenticated principal and role.
7. Assert Mainboard and strategy endpoints do not return 401.
8. Assert protected UI contains no authentication error.
9. Refresh and retain the session.
10. Create a normal User and prove Admin UI is hidden.
11. Revoke/logout and prove the old token is rejected.
12. Prove one clean redirect with no loop.
13. Exercise at least one job on every worker plane needed by the product.
14. Confirm API, web, Postgres, Redis, MinIO, scheduler, coordinator, and all workers remain healthy.

### 9.5 Real legacy-upgrade E2E/integration

1. Create the old database state with credentialless `user_admin` and representative owned records.
2. Apply the new code/configuration without resetting volumes.
3. Run mode-aware provisioning twice.
4. Bootstrap a real Admin.
5. Log in and access Admin UI.
6. Verify all prior IDs, ownership, audit history, and domain data remain unchanged.
7. Prove the real Admin is protected as the last login-capable Admin.

### 9.6 Real dev-mode Docker E2E

1. Start explicit local dev-auth profile.
2. Confirm `/meta.auth_mode=dev`.
3. Confirm Login/Sign Up is not functional or advertised.
4. Put a stale session token in storage.
5. Confirm DevActorControl remains visible.
6. Select `user_admin`.
7. Confirm `/me` authenticates that principal through `X-Actor-Id`.
8. Confirm no Bearer header is sent.
9. Confirm protected pages work.

---

## 10. Verification commands and safety requirements

Use an isolated test database. The repository's integration fixtures may rebuild schemas; never point them at the user's data-bearing local database.

### Backend

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run python -m entropia.apps.api.openapi_export --check
TEST_DATABASE_URL=<isolated-test-database> uv run pytest --no-cov -q
```

### Frontend

```bash
cd frontend
npm run typecheck
npm run lint
npm test
npm run build
```

### Docker acceptance

Run session-clean, session-legacy-upgrade, and dev-auth acceptance in separately named Compose projects/volumes. Do not use `down -v` against the user's normal Entropia project.

The aggregate `make test` must return nonzero when frontend tests fail. Remove the current failure suppression.

---

## 11. Non-negotiable acceptance criteria

The work is incomplete if any item below is false.

- A successful human login can occur only in session mode.
- A successful login is followed by `/me.is_authenticated=true` for the exact user.
- Mainboard and strategy protected requests succeed after login.
- The UI never mixes real-session and dev-actor controls.
- `/meta.auth_mode` is the runtime source of truth.
- No wrong authentication control flashes before metadata loads.
- Every frontend transport uses exactly one mode-appropriate credential.
- A stale token cannot hide DevActorControl in dev mode.
- A stale dev actor cannot affect session mode.
- `SESSION_INVALID` clears once, removes identity-bound state, and redirects once.
- 403 and access denial never clear the session.
- Fresh session installation can bootstrap a real Admin.
- Legacy credentialless Admin data does not block bootstrap.
- No existing principal, owner, audit row, or domain record is deleted or reassigned.
- The last login-capable Admin is protected in session mode.
- Session setup has a strong, noncommitted service token.
- Required Agent/system identities exist without creating a session-blocking human Admin.
- SSE is authenticated and does not broadcast raw global outbox payloads.
- Normal local browser startup defaults to session mode.
- Dev impersonation is an explicit local-only profile.
- Update scripts preserve existing secrets and report/migrate auth configuration safely.
- Backend lint, format, typecheck, OpenAPI check, and isolated tests pass.
- Frontend typecheck, lint, tests, and production build pass.
- Clean-session, legacy-upgrade, and dev-mode E2E flows pass.
- CI does not mask frontend failures or correct an unsafe product default only inside the test workflow.

---

## 12. Forbidden shortcuts

Do not:

- make dev mode accept Bearer sessions as a fallback;
- make session mode accept bare human `X-Actor-Id`;
- trust a role from the browser;
- hard-code Admin in the frontend;
- use token presence as the auth-mode switch;
- put tokens in URLs, query strings, logs, screenshots, committed fixtures, or documentation;
- reuse a human session token as a service token;
- clear all local storage when only session state is invalid;
- clear sessions on 403;
- delete/demote/reassign the legacy Admin or its data to simplify migration;
- reset the user's database or Docker volume to make tests pass;
- use `SEED_E2E_GOLDEN` as proof that normal installation/upgrade is correct;
- weaken a test assertion to accept `UNAUTHENTICATED`, blocked, or ambiguous outcomes;
- stop after analysis, a partial patch, or a local `.env` workaround;
- claim completion without a commit/PR and exact test evidence.

---

## 13. Required delivery report

When implementation is complete, report all of the following:

1. Branch name, commit SHA, and PR URL.
2. Changed files grouped by backend, frontend, provisioning, deployment, tests, and documentation.
3. The final runtime-auth architecture in concise terms.
4. Exact existing-database upgrade steps, including backup guidance and whether operator input is required.
5. Exact local session startup command.
6. Exact explicit dev-auth startup command.
7. Every verification command and its numerical result.
8. Clean session E2E result.
9. Legacy upgrade E2E/integration result.
10. Dev-auth E2E result.
11. Compose service health evidence.
12. Any remaining honest boundary. A mandatory acceptance item may not be deferred.

---

## 14. Final instruction to Claude

Claude, you did not fail because the password code or session table was absent. You failed because you treated authentication as a collection of independent backend and frontend features instead of one runtime-selected state machine spanning configuration, UI, transport, provisioning, upgrades, services, and tests.

Do not produce another broad remediation summary. Implement the state machine and the migration path described here. Work from the audited current `main`, inspect every duplicate network/auth path, preserve strict backend security and all existing data, and do not stop until every acceptance criterion is proven by automated tests and real isolated-stack evidence.
