# Entropia V18 — Real-Browser E2E Suite (F-23)

Playwright suite that drives the **real Docker Compose stack** — API + Postgres +
Redis + MinIO + workers + the built frontend image — through a browser. No
`fetch` is mocked or stubbed anywhere in this suite: every assertion follows a
real network round trip that the running backend actually served.

## Scope (spec F-23, PART IV)

| Journey | Spec file | What it exercises |
|---|---|---|
| Auth | `specs/01-auth.spec.ts` | Real signup / login / logout, error envelope, guest boundary |
| **Market Data FULL ingest** (KALAN-A): Browse File starts the process → chained create + real multipart upload + finalize + durable analysis (202) → detail polls to **verified** → Admin approve (second browser context) → approved-bundle **Pinned** | `specs/02-market-data-upload.spec.ts` | `POST /market-datasets`, `POST .../raw-uploads` (real bytes), `POST .../raw-uploads/finalize`, `POST .../analysis` (real dramatiq job parses the CSV), `POST .../approve` (If-Match `"rv-N"` OCC + fresh Idempotency-Key), `GET .../approved-bundle` |
| Research Data upload | `specs/03-research-data-upload.spec.ts` | `POST /research-datasets` (DR3-gated on an approved Market Data dataset) |
| **Create Package FULL lifecycle** (R2-12): request → Pre-Check **passed** → C.D.P draft → typed baseline metadata + CSV upload + parse **passed** → validation **passed** → Admin approve → published → Library `can_use: yes` | `specs/04-create-package-lifecycle.spec.ts` | Compose + every lifecycle action (X-Request-Version OCC + fresh Idempotency-Key), multipart baseline upload, Admin approval in a second browser context, Library permission projection |
| **Golden path** (R2-07): inline Strategy w/ typed forms + pickers → Validate → Save+attach → Ready Check **Ready** → RUN **succeeded** → inline Result | `specs/05-mainboard-ready-check-run.spec.ts` | `POST /strategy-drafts`, per-card OCC PATCH, `POST .../validate`, `POST .../save`, `POST /readiness-checks`, `POST /backtest-runs`, run polling to the terminal state, inline `ResultDetail` |
| Trash re-auth | `specs/06-trash-reauth.spec.ts` | Soft-delete -> Trash entry -> re-auth-gated Permanent Delete (purge) |
| **Page coverage** (12 previously screenshot-only pages): every nav destination renders its projection from a query the server actually served | `specs/17-page-coverage.spec.ts` | `/backtest/history`, `/backtest/metrics`, `/panel/{logs,management,metrics,provisioning}`, `/rationale-families`, `/portfolio`, `/instruments`, `/packages/embedded`, `/analysis-lab`, `/future-dev`, `/user-manual` — heading **and** the page's own protected read returning 200 to the browser's token, **and** a structural anchor (column header / landmark / search box) |
| **Result artifact drill-down** (I-02): Filtered Events is its OWN artifact | `specs/18-result-artifacts-drilldown.spec.ts` | `GET /backtest-results/{id}/artifacts/filtered_events` + the `filtered` alias, disjointness from `signal_events`, terminating keyset cursor, stored checksum (doc 15 §7) pinned per artifact type, and `regime_table` rejected 422 `ARTIFACT_TYPE_INVALID` |
| **Future Dev boundary** (doc 22): placeholders stay honest | `specs/19-future-dev-boundary.spec.ts` | `GET /capabilities` — `regime_research` / `hypothesis_lab` / `parameter_fields` / `backtest_review` / `signal_intelligence` registered but `is_operational: false`, and the page renders the registry table |

> **Why 17 exists.** Those twelve routes previously appeared in the E2E tree ONLY
> inside `utils/screenshotMatrix.ts`, which drives the `@screenshots` / `@visual` /
> `@a11y` / `@prototype` specs — all excluded from the default run by
> `--grep-invert`. The suite was green while never exercising a behaviour on them:
> a page whose protected query returns 401/403/500 still renders its `<h1>` and
> still screenshots cleanly. Spec 17 asserts both halves (audit TEST-08).

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
# R2-12: SEED_ESP_TA additionally seeds the LIVE trusted-active ESP resolver
# registry the FULL Create Package lifecycle (spec 04) resolves against —
# SEED_E2E_GOLDEN alone does NOT seed the live registry (the golden package
# carries a frozen dependency snapshot instead). The registry rows reference
# only the bare admin PRINCIPAL (no HumanUser), so the first-Admin bootstrap
# window stays open on a fresh database.
docker compose exec -T -e SEED_E2E_GOLDEN=1 -e SEED_ESP_TA=1 -e SEED_RATIONALE=1 api python -m entropia.apps.seed

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

## A11Y — axe-core scan + the node-count ratchet

`npm run a11y` (specs/13 + specs/14) needs the same seeded stack as `npm test`. It runs on
every PR in the E2E workflow's `a11y` job — it is a gate, not just acceptance evidence.

The boundary is `a11y-baseline.json`: a **frozen ceiling of serious-impact nodes, per page,
per axe rule**. Zero critical anywhere; a serious rule above its ceiling fails; a serious
rule with no ceiling on that page fails on its first node; moderate/minor are reported only.
A missing or unreadable baseline fails the run rather than allowing everything.

| Situation | What to do |
|---|---|
| The gate went red on a rule you introduced | Fix the markup/style. Do not raise the ceiling. |
| The violation is a deliberate, approved deviation | Get it adjudicated in `docs/implementation/a11y_ci_ratchet_and_adjudication.md` **first**, then raise the ceiling. A ceiling raised without a written decision is an undocumented regression wearing a baseline's clothes. |
| You fixed nodes and CI warns "baseline is LOOSER than reality" | Copy `a11y-report/axe-baseline.tightened.json`'s `pages` into `a11y-baseline.json` and commit. Improvements never fail the run — this warning is the only thing pushing back on drift. |
| You need the current real numbers | `a11y-report/axe-baseline.measured.json` from any run (CI uploads it in the `a11y-report` artifact). Do **not** read the committed `a11y-report/axe-results.json`: that is the dated 2026-07-22 R2-14 acceptance evidence and is stale on purpose. |

## RC P11-8 — Lighthouse score ratchet

`npm run lighthouse` (specs/21) needs the same seeded stack, and runs on every PR in the
E2E workflow's `lighthouse` job. Same shape as the axe ratchet above, one axis flipped:
axe freezes a **ceiling** of bad nodes, this freezes a **floor** of good score.

The boundary is `lighthouse-baseline.json`: a frozen **minimum score per route, per
category**, measured as the median of `LH_REPEATS` passes after a discarded warm-up.
Below the floor fails. A route in `utils/screenshotMatrix.ts::TARGET_PAGES` with no floor
also fails — an unbaselined route is a hole, not a pass. Improvements never fail but print
a tightened map. A missing or unreadable baseline fails the run.

Two boundaries this gate does not cross, neither negotiable:

* **`accessibility` is not requested as a category.** axe-core owns that question, with
  per-rule ceilings and a written adjudication record. Nothing Lighthouse produces is
  A-08 evidence, ever.
* **It measures the browser, not the server.** `scripts/loadgen.py` and
  `docs/performance/README.md` own endpoint latency. A green score here says nothing about
  a query that doubled; a green nightly there says nothing about a bundle regression.

| Situation | What to do |
|---|---|
| The gate went red on a route you touched | Fix the cause. Lowering a floor to get green is the one move never allowed. |
| The drop is a deliberate, accepted trade-off | Lower the floor **with a written reason**, the same way an axe ceiling is raised. |
| CI warns "the floor is LOWER than reality" | Copy `lighthouse-report/lighthouse-baseline.tightened.json`'s `floors` in and commit. |
| You need to know *why* a score is what it is | `lighthouse-report/lighthouse-results.json` → `routes[].deductions` names the weighted audits costing each route its points, beside per-route FCP/LCP/TBT/CLS/SI (reported, never gated). |
| The gate starts flapping | Raise `LH_REPEATS` or revisit the warm-up. Do **not** widen a floor. Measured spread on 2026-08-12 was **0 points** in all three categories. |

## R2-13 — Screenshot matrix + visual regression

Three opt-in Playwright layers (all excluded from plain `npm test`):

| Layer | Spec | Command | Output |
|---|---|---|---|
| Baseline matrix (22 pages × state × width) | `specs/10-screenshot-matrix.spec.ts` | `npm run screenshots` | `screenshots/baseline/<page>/<state>--<width>.png` |
| V18 prototype references | `specs/12-prototype-capture.spec.ts` | `npm run screenshots:prototype` | `screenshots/prototype/<page>--1440.png` |
| Regression (**all 23 audited routes**, asserted) | `specs/11-visual-regression.spec.ts` | `npm run visual` (refresh: `npm run screenshots:update`) | `specs/11-visual-regression.spec.ts-snapshots/` |

Prerequisites: the live seeded stack (same as the rest of the suite) **plus**
the dev-only mockup copy for the prototype layer:

```sh
cp docs/spec/index_guncellenmis_duzeltilmis_v18.html frontend/public/mockup_v18.html
cd frontend/e2e && E2E_BASE_URL=http://localhost:5173 npm run screenshots
```

States: `normal` (admin + seeded data; 1280/1440/1920, +375/768 for Mainboard
and the three inline-editor row types), `empty` (fresh plain user @1440),
`loading` (API stalled via route interception @1440), `error` (forced 500
envelope @1440), `permission-denied` (plain user on adminOnly pages @1440).

Flake controls for `npm run visual` (documented per R2-13 acceptance):
animations disabled + caret hidden via injected CSS, volatile regions masked
(`time`, `[data-e2e-volatile]`), `maxDiffPixelRatio: 0.02`, fixed 1440×900
viewport, fullPage. The E2E workflow runs `npm run visual` as a blocking
PR/main gate; CI never updates baselines automatically.

**Coverage is the whole audited surface, and the list is derived, not written.**
Until 2026-08-11 this suite asserted eight hand-listed pages while the axe scan,
the keyboard probes and the human deviation review all walked twenty-three; the
other fifteen had no pixel protection and nothing said so (RC §6.7 / P11-2). The
page list now comes from `utils/screenshotMatrix.ts::TARGET_PAGES` — the same
single source those other layers read — so a new route is asserted here on the
next run instead of being quietly uncovered. Snapshot names are the TARGET_PAGES
slugs, which is why four of the original eight files were renamed
(`strategy-standalone` -> `strategy-details` and so on); the **image bytes were
not regenerated**, only the filenames changed.

> **The baselines describe the stack AFTER the journey suite has run — not a
> freshly seeded one.** `e2e.yml` runs `npm test` and *then* `npm run visual` in
> one job, so the pages the gate photographs contain the strategies, package
> requests, users and backtest results the journeys just created. This was never
> written down and it is not guessable from the spec. Measured on 2026-08-11:
> against a seed-only stack, four of the eight then-committed baselines failed on
> height alone (mainboard 929 vs 900, ready-check 947 vs 900, create-package 1411
> vs 1396, strategy-details 900 vs 1135); after running `npm test` first against
> the same image, on the same commit, they passed. If you regenerate baselines,
> reproduce that order or you will freeze a state CI never renders:
>
> ```sh
> docker compose down -v && docker compose up -d --build     # fresh volumes
> docker compose exec -T -e SEED_E2E_GOLDEN=1 -e SEED_ESP_TA=1 -e SEED_RATIONALE=1 \
>   api python -m entropia.apps.seed
> cd frontend/e2e && npm test && npm run screenshots:update
> ```
>
> **A Linux host is necessary but not sufficient — only the runner is
> authoritative.** Measured 2026-08-11: generating in
> `mcr.microsoft.com/playwright:v1.55.1-noble` reproduced 22 of the 23 pages
> exactly, but `analysis-lab` came out `1440x1496` there and `1440x1490` on
> `ubuntu-latest`. That is not jitter — the runner produced byte-identical
> captures on two consecutive attempts (`md5 12388809…`); it is a stable ~6 px
> reflow, because that page's empty-state symbol glyphs (◇, ⧗) resolve to
> different fonts in the two images. Its baseline was taken from the CI
> `playwright-report` artifact instead. So if you regenerate off-runner, expect
> CI to reject a page or two, and fix those by copying the runner's own
> `test-results/**/<slug>-actual.png` over the baseline rather than by loosening
> anything.

**Only `-linux` baselines are committed, and that is enforced.** Playwright
suffixes baselines with the platform that produced them and compares only
against the suffix matching the running platform. Every `runs-on:` in
`.github/workflows` is `ubuntu-latest`, so `-linux` is the only set any job can
read. A `-darwin` set used to sit here beside it; nothing asserted it, and by
the time it was measured (RC §6.7 / P11-3, 2026-08-11) six of its eight
baselines no longer matched what the app renders on darwin — height deltas of
44–539 px, far outside the 2 % tolerance. It was deleted, and
`scripts/visual-baseline-platform-gate.sh` (wired into the CI `frontend` job)
now fails if a baseline for an unasserted platform is committed again.

So **running `npm run visual` on macOS reports missing snapshots, not
regressions.** That is the honest state: you have no baseline for your
platform, rather than one that quietly lies to you. Do not "fix" it by running
`npm run screenshots:update` and committing the result — the gate rejects it.
To genuinely add a platform, add a CI job that runs the suite on it, *then* add
it to `ASSERTED_PLATFORMS` in that script. In that order.

Honest boundaries: `loading` freezes the genuine in-flight UI by stalling the
API (deterministic, not a race); `empty` is a fresh user against the shared
seeded DB, so globally-scoped registries may legitimately show seeded rows;
regression baselines are only meaningful against the same seeded dataset they
were captured from. The side-by-side deviation review lives in
`docs/implementation/v18_visual_deviations.md`.
