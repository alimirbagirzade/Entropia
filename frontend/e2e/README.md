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
| **Golden path** (R2-07): inline Strategy w/ typed forms + pickers → Validate → Save+attach → Ready Check **Ready** → RUN **succeeded** → inline Result | `specs/05-mainboard-ready-check-run.spec.ts` | `POST /strategy-drafts`, per-card OCC PATCH, `POST .../validate`, `POST .../save`, `POST /readiness-checks`, `POST /backtest-runs`, run polling to the terminal state, inline `ResultDetail` |
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

# R2-07: seed the E2E golden fixture (idempotent — safe to re-run). Provides the
# approved market dataset (with processed Parquet bars in MinIO), the
# approved+published ta.sma indicator package and the canonical rationale
# families the golden-path spec builds on. It deliberately does NOT create the
# default Admin, so the ENTROPIA_BOOTSTRAP_ADMIN_EMAIL first-signup promotion
# keeps working on a fresh database.
docker compose exec -T -e SEED_E2E_GOLDEN=1 api python -m entropia.apps.seed

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

- **Golden path is now strict (R2-07, GAP madde 12)**: `05-mainboard-ready-
  check-run.spec.ts` requires the REAL green chain — typed-form inline
  Strategy on "/", approved indicator pinned from the Library picker,
  approved market dataset pinned from the dataset picker, Validate clean,
  Save + auto-attach, Ready Check an EXPLICIT **Ready**, RUN's
  disabled → enabled transition, the admitted run reaching the terminal
  **succeeded** state, and the inline Result with headline metrics +
  provenance. Blocked / NOT_READY / error is a FAILURE. The former
  "a structured outcome is enough" reading is retired: L4 forbids
  *fabricating* success, it never excuses accepting a blocked report on the
  golden path. The spec depends on the `SEED_E2E_GOLDEN=1` fixture above.
- **Rationale family via the Admin Advanced editor** (reported product
  finding): the Mainboard inline flow has no control for the REQUIRED
  `StrategyConfig.rationale_family_id` (the Strategy Context card is
  read-only and "+ Add → Add Strategy" creates the draft with no family), so
  the golden-path spec runs as the bootstrap Admin and sets the family
  through the admin-gated Advanced (raw payload) editor — a real product
  surface, no mocking. When the product grows an inline family picker, the
  spec should switch to a plain user.
- **Where it has actually run green**: the golden-path spec passed twice
  (fresh DB and dirty re-run) against the full **host-native local stack**
  (Postgres + Redis + MinIO + API in session-auth mode + dramatiq worker +
  Vite dev server, `docs/LOCAL_STACK.md`) in the R2-07 authoring session.
  The containerized CI path runs the same seed step (`e2e.yml`) but had not
  executed at authoring time — treat CI-green as proven only once the E2E
  workflow has run on the PR.
- **Research Data create** is DR3-gated on an ACTIVE+APPROVED Market Data
  dataset; a freshly created (not yet Admin-approved) dataset legitimately
  gets `DEPENDENCY_BLOCKED` back. The spec asserts *a* real outcome landed,
  not approval.
- Journeys go green incrementally as the underlying UI slice's markup
  stabilizes; if a selector drifts (button text, label wording) the fix is a
  one-line Page Object update in `pages/`, not a suite rewrite.
