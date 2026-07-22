# Entropia Authentication-Mode Mismatch — Implementation Task

## Objective

Fix the authentication flow so that a successful Sign Up / Log In produces a genuinely authenticated browser session and all subsequent protected API requests succeed.

This must be a repository-level fix, not a machine-specific workaround and not merely a change to one developer's local `.env` file.

## Confirmed Failure

Current local runtime configuration:

```text
ENTROPIA_ENV=local
AUTH_MODE=dev
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Observed API sequence:

```text
POST /api/v1/auth/login                 200 OK
GET  /api/v1/me                         200 OK, but anonymous
GET  /api/v1/mainboards/default         401 Unauthorized
GET  /api/v1/strategy-drafts            401 Unauthorized
```

The credentials are accepted. The failure happens after login.

## Root Cause

The frontend always exposes real Sign Up / Log In and stores the returned opaque session token:

- `frontend/src/lib/auth.ts`
- `frontend/src/lib/session.ts`
- `frontend/src/pages/Login.tsx`

The API client then sends `Authorization: Bearer <token>`:

- `frontend/src/lib/apiClient.ts`

However, the backend is running with `AUTH_MODE=dev`. In this mode, `backend/src/entropia/apps/api/deps.py` deliberately ignores Bearer session tokens and resolves identity only from `X-Actor-Id`.

After login, the frontend sees a stored token and hides `DevActorControl` in `frontend/src/app/Layout.tsx`. Therefore the browser has a token that the backend ignores, while the UI hides the only identity control accepted by dev mode. Protected requests are resolved as anonymous and return 401.

There is a second provisioning issue: `backend/src/entropia/apps/seed.py` seeds the `user_admin` human Admin without a login credential. If the same persistent database is switched to `AUTH_MODE=session`, this credentialless active Admin can prevent the first-Admin bootstrap flow from promoting a real signup.

## Required Behaviour

Authentication UI and transport must follow the backend's runtime auth mode.

### Session mode

- Show `Login / Sign Up` and `Log out` controls.
- Hide `DevActorControl` completely.
- Sign Up must create the account and auto-login.
- Log In must store the returned token.
- Subsequent `/me` and protected requests must use the Bearer token.
- `/me` must return `is_authenticated: true` and the logged-in user's server-resolved role.
- Refreshing the browser must preserve a valid session.
- Logout must revoke and clear the session.
- An invalid/expired/revoked session must be cleared client-side and lead the user back to login without a retry loop.

### Dev mode

- Do not present Sign Up / Log In as a usable authentication mechanism.
- Show `DevActorControl` and explain that identity is selected through `X-Actor-Id` in local development.
- A stored session token must not hide the dev actor control or make the UI claim that the user is logged in.
- Protected requests must continue to use the server-resolved dev principal. Do not weaken the backend by accepting Bearer tokens as a fallback in dev mode.

### Security boundary

- Never fall back from failed session authentication to `X-Actor-Id` in session mode.
- Never trust a client-supplied role.
- Do not make `AUTH_MODE=dev` valid outside `ENTROPIA_ENV=local`.
- Do not hard-code an Admin role in the frontend.

## Required Implementation

### 1. Publish the runtime auth mode

Extend `GET /api/v1/meta`:

```json
{
  "name": "Entropia V18",
  "version": "0.1.0",
  "environment": "local",
  "api_base_path": "/api/v1",
  "auth_mode": "dev"
}
```

Required changes:

- Add a closed `dev | session` field to `MetaResponse` in `backend/src/entropia/apps/api/routes/meta.py`.
- Populate it from `get_settings().auth_mode`.
- Update `frontend/src/lib/types.ts`.
- Update the checked-in OpenAPI document if this repository requires generated OpenAPI changes.
- Add backend and frontend contract tests.

Do not expose secrets, tokens, bootstrap email addresses, or service-token state through `/meta`.

### 2. Make the application shell auth-mode aware

Use the runtime `/meta.auth_mode` value in `frontend/src/app/Layout.tsx` and the login route.

- Session mode: render the real-session controls only.
- Dev mode: render `DevActorControl` only.
- Do not use “token exists in localStorage” as the sole decision for which auth UI is shown.
- Do not briefly show the wrong auth control while `/meta` is loading; use a neutral/loading state.
- A direct visit to `/login` in dev mode must show a clear local-development message and a route back to the application instead of offering a token that the backend will ignore.

### 3. Keep request authentication mode-consistent

Preserve the backend's existing strict mode semantics in `deps.py`.

On the frontend, make request credential selection explicit:

- Session mode: Bearer session token is the human credential; do not rely on `X-Actor-Id`.
- Dev mode: `X-Actor-Id` is the local development identity; a stale Bearer token must not control UI state.

Use a small runtime auth-mode store/provider initialized from `/meta`, or another deterministic design. Avoid circular API initialization: `/meta`, health, signup and login must remain callable before an authenticated identity exists.

### 4. Fix local deployment profiles

Define two explicit local use cases and document them:

1. **Normal local browser use** — real Sign Up / Log In using `AUTH_MODE=session`.
2. **Developer/test impersonation** — explicit opt-in `AUTH_MODE=dev` using `X-Actor-Id`.

The normal local-browser startup instructions and generated `.env` should use session mode. Dev impersonation must be an explicit profile/override, not an accidental default presented alongside real login UI.

Update as applicable:

- `.env.example`
- `README.md`
- `scripts/update.ps1`
- local startup/task scripts
- Docker Compose profile or override documentation

Do not overwrite an existing user's secrets during updates.

### 5. Make session-mode provisioning valid

Review `backend/src/entropia/apps/seed.py` and the first-Admin bootstrap policy.

- Do not create a credentialless active `user_admin` that permanently blocks first-Admin bootstrap in a real session-mode installation.
- Keep the dev seed available for explicit dev mode.
- For a fresh session-mode database, support the documented bootstrap-email flow without requiring a database edit.
- Provide a safe, idempotent upgrade/provisioning path for an existing database that already contains the credentialless `user_admin` and user-owned data.
- Do not delete or rewrite existing principals, ownership, audit records, or domain data.
- Any operator bootstrap/provisioning transition must be fail-closed and auditable.

### 6. Preserve non-human service authentication

Session mode requires internal Agent/service calls to use the configured service token plus the intended non-human `X-Actor-Id`.

- Ensure normal local session-mode setup generates or requires a non-empty `ENTROPIA_SERVICE_TOKEN` without committing it.
- Confirm API, scheduler, coordinator and all workers remain functional in session mode.
- Never reuse a human session token as the service token.

### 7. Handle stale sessions cleanly

When an authenticated request receives the canonical invalid-session response:

- Clear the local session exactly once.
- Invalidate identity-dependent queries.
- Redirect to login when appropriate.
- Do not clear sessions for unrelated authorization failures such as `ACCESS_DENIED`/403.
- Do not create redirect or request retry loops.

## Tests Required

Add or update automated tests for all of the following.

### Backend

- `/meta` returns `auth_mode=dev` or `auth_mode=session` from settings.
- Dev mode ignores Bearer session authentication and resolves only the dev actor header.
- Session mode ignores bare human `X-Actor-Id` and accepts a valid Bearer session.
- Session mode rejects invalid, expired and revoked sessions.
- Fresh session-mode first-Admin bootstrap is possible.
- Existing credentialless dev Admin data is handled by the documented safe upgrade path.

### Frontend unit/integration

- Dev mode shows `DevActorControl` and does not offer functional Sign Up / Log In.
- Session mode shows Login / Sign Up and never shows `DevActorControl`.
- A stored token in dev mode cannot hide the dev actor control.
- Signup auto-login stores the token and refetches `/me`.
- Invalid-session handling clears only the session state and does not loop.

### Real E2E acceptance flow

Run against the actual Docker Compose stack with `AUTH_MODE=session`:

1. Start from a clean browser context.
2. Sign up a new human user.
3. Confirm auto-login or log in with the same credentials.
4. Confirm `/api/v1/me` returns `is_authenticated: true` for that exact user.
5. Confirm `GET /api/v1/mainboards/default` does not return 401.
6. Confirm `GET /api/v1/strategy-drafts` does not return 401.
7. Refresh and confirm the session still works.
8. Log out and confirm protected calls return the canonical unauthenticated response.
9. Confirm Admin-only UI remains hidden for a normal User.
10. Confirm API, scheduler, coordinator and every worker remain healthy.

Also run a dev-mode E2E check proving that selecting `user_admin` through `DevActorControl` authenticates via `X-Actor-Id` without presenting the real login workflow.

## Acceptance Criteria

- A successful login is followed by authenticated protected requests; the current `login 200 -> protected request 401` sequence is impossible.
- The UI never mixes session login and dev impersonation controls.
- The running auth mode is visible through the non-secret `/meta.auth_mode` contract.
- Fresh session-mode installations can bootstrap a real Admin safely.
- Existing databases are preserved and have a documented, idempotent upgrade path.
- Session-mode internal services remain healthy with service-token authentication.
- Unit, integration and E2E tests pass.
- Typecheck, lint and production build pass.
- Documentation clearly distinguishes normal local browser use from developer impersonation mode.

## Delivery Requirements

- Implement the fix; do not stop at an analysis or proposal.
- Do not solve this by weakening backend authentication or trusting both mechanisms simultaneously.
- Do not commit real passwords, session tokens or service tokens.
- Report changed files, configuration migration steps, test results and any operator action required for existing local databases.
