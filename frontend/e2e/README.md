# Entropia V18 — Real-Browser E2E Suite (F-23)

Playwright suite that drives the **real Docker Compose stack** — API + Postgres +
Redis + MinIO + workers + the built frontend image — through a browser. No
`fetch` is mocked or stubbed anywhere in this suite: every assertion follows a
real network round trip that the running backend actually served.

## Scope (spec F-23, PART IV)

| Journey | Spec file | What it exercises |
|---|---|---|
| Auth | `specs/01-auth.spec.ts` | Real signup / login / logout, error envelope, guest boundary |
| Market Data upload | `specs/02-market-data-upload.spec.ts` | `POST /market-datasets` |
| Research Data upload | `specs/03-research-data-upload.spec.ts` | `POST /research-datasets` (DR3-gated on an approved Market Data dataset) |
| Create Package lifecycle | `specs/04-create-package-lifecycle.spec.ts` | `POST /package-requests` + Pre-Check dependency scan |
| Strategy creation / Mainboard attach / Ready Check / RUN / inline result | `specs/05-mainboard-ready-check-run.spec.ts` | `POST /strategy-drafts`, generic work-object create+attach, `POST /readiness-checks`, `POST /backtest-runs` |
| Trash re-auth | `specs/06-trash-reauth.spec.ts` | Soft-delete -> Trash entry -> re-auth-gated Permanent Delete (purge) |

## Running locally

```sh
# From the repo root — bring up the full stack:
cp .env.example .env
# Real-login journeys need session auth (not the dev X-Actor-Id header) and a
# deterministic first Admin:
sed -i.bak -e 's/^AUTH_MODE=.*/AUTH_MODE=session/' \
           -e 's/^ENTROPIA_BOOTSTRAP_ADMIN_EMAIL=.*/ENTROPIA_BOOTSTRAP_ADMIN_EMAIL=e2e_admin@e2e.entropia.test/' .env
docker compose up -d --build
# Wait for: curl -f http://localhost:8000/api/v1/health/ready && curl -f http://localhost:8080

cd frontend/e2e
npm install
npm run install-browsers   # once per machine
E2E_BASE_URL=http://localhost:8080 npm test
```

Open the HTML report after a run with `npm run report`.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `E2E_BASE_URL` | `http://localhost:8080` | Frontend origin the browser navigates to |
| `E2E_ADMIN_EMAIL` | `e2e_admin@e2e.entropia.test` | Must match `ENTROPIA_BOOTSTRAP_ADMIN_EMAIL` on the API so the first signup with this email is auto-promoted to Admin |
| `E2E_ADMIN_USERNAME` | `e2e_admin` | Fixed username for the bootstrap-Admin actor |
| `E2E_ADMIN_PASSWORD` | `E2e-Admin-Passw0rd!23` | Fixed password for the bootstrap-Admin actor |

## Honest boundaries (do not over-claim green)

- **Docker on this machine could not be proven in this authoring session**
  (Docker Desktop was not available to run `docker compose up` end to end
  here). The suite is **authored against the real source** (every selector
  was read from the actual page component, not guessed) but has **not been
  run against a live stack** in this session. Treat it as *authored, needs a
  stack to go green* until it has run once in CI or locally — do not report
  it as "passing" without that run.
- **Golden-path depth**: a fully schema-valid, RUN-able Strategy needs an
  Admin-approved indicator package (full Create Package lifecycle incl.
  candidate generation + draft + approve) pinned into a saved Strategy
  revision, plus an Admin-approved Market Data revision for
  `data.market_dataset_revision_id`. Wiring that whole chain is a
  dedicated seeding effort beyond this slice's scope. `05-mainboard-ready-
  check-run.spec.ts` instead attaches a generic (non-domain-validated) work
  object to move the composition hash and exercises the real Ready Check /
  RUN admission endpoints — it asserts that a *structured* outcome came back
  (report or rejection), not a specific verdict, matching the app's own L4
  "never fabricate success" rule.
- **Research Data create** is DR3-gated on an ACTIVE+APPROVED Market Data
  dataset; a freshly created (not yet Admin-approved) dataset legitimately
  gets `DEPENDENCY_BLOCKED` back. The spec asserts *a* real outcome landed,
  not approval.
- Journeys go green incrementally as the underlying UI slice's markup
  stabilizes; if a selector drifts (button text, label wording) the fix is a
  one-line Page Object update in `pages/`, not a suite rewrite.
