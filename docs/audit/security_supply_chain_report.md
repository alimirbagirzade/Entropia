# ADIM 23 — Security & supply-chain gates

**Base:** `origin/main` @ `e6cd2ee` · **Branch:** `security/supply-chain-gates` · **Date:** 2026-08-05

Everything below was **measured on this machine**, not inferred. Where a claim
rests on a scan, the command and its verbatim result are given. Where something
was NOT verified, it says so.

---

## 1. What existed before this slice

`main` already had two real dependency gates and one deliberate exception idiom:

| Gate | Where | Status on `e6cd2ee` |
|---|---|---|
| `pip-audit` (backend, blocking) | `ci.yml` backend job | **green** — `No known vulnerabilities found` |
| `npm audit` gate with frozen advisories | `scripts/npm-audit-gate.mjs` | **green** — `high=2 critical=0`, all frozen under one recorded id |
| Dependabot (uv, npm, github-actions, docker) | `.github/dependabot.yml` | active; frontend majors deliberately suppressed |

Absent entirely: **CodeQL**, **container image scanning**, **SBOM**, **secret
scanning**. Also absent: any `permissions:` block on `ci.yml` and `e2e.yml`, and
any SHA pinning of the one third-party action in use.

The canonical spec set (`docs/spec/Entropia_V18_Master_Technical_Reference_v1_0.md`
and docs 01–22) contains **no** supply-chain, SBOM or scanning requirement. This
slice is therefore infrastructure hardening, not a product-canon change — which
is why it carries **no migration, no `ENGINE_VERSION` bump and no OpenAPI
change** (drift guard verified clean, §6).

---

## 2. Audit inventory — severity and exploitability

### 2.1 Dependencies

| Scope | Tool | Result |
|---|---|---|
| backend (Python) | `pip-audit` against the synced env | **0 advisories** |
| frontend | `npm audit` via the repo gate | `high=2 critical=0`; both are `GHSA-qwww-vcr4-c8h2` (react-router RSC-mode CSRF), already frozen with a written reason |
| frontend/e2e | same | `high=0 critical=0` |

**Exploitability of the frozen advisory: none in this app.** It requires
react-router RSC mode; this is a Vite SPA on `BrowserRouter` and never enables
it. The only patched line is `react-router@8.2.1+`, i.e. the v8 migration that
removes `react-router-dom` — a major upgrade Dependabot is configured to suppress.

### 2.2 Container images

`trivy 0.73.0`, `--scanners vuln --severity HIGH,CRITICAL`, on `docker save` tarballs:

| Image | HIGH/CRITICAL | …with a published fix |
|---|---|---|
| `entropia-backend` (python:3.13-slim, debian 13.6) | **23** (4 CRITICAL, 19 HIGH) | **0** |
| `entropia-web` (nginx alpine) | **0** | **0** |

All 23 are Debian base-image packages with `FixedVersion: NONE` — 8 in
`perl-base` (4 CRITICAL: CVE-2026-13221, CVE-2026-42496, CVE-2026-57433,
CVE-2026-8376), 9 sharing CVE-2026-53615 across `util-linux`, 4 sharing
CVE-2025-69720 across `ncurses`, plus `gzip` and `libacl1`. Three carry Debian
status `fix_deferred`.

**Exploitability: low, and not actionable today.** None of these packages is on a
request path — the API and workers execute Python, and `perl`/`ncurses`/
`util-linux` are inherited base-image furniture the application never invokes.
More decisively, **there is nothing to do**: no fixed version exists in any
Debian suite. This is exactly why the gate is `--ignore-unfixed` (§3.2) rather
than a red build with no remedy.

### 2.3 Secrets

`gitleaks 8.30.1`, default ruleset, whole tree: **6 findings, all false
positives**, every one a collision with this repo's own domain vocabulary:

| File:line | Matched text | Why it is not a secret |
|---|---|---|
| `backend/tests/integration/test_idempotency_new_ops.py:238` | `idempotency_key="idem-noflush-2"` | Idempotency-Key contract value (CLAUDE.md §O-13) |
| `backend/tests/integration/test_backtest_funding_step_order.py:131` | `execution_key="exec_key_k03_integration"` | backtest execution identifier |
| `backend/tests/integration/test_research_available_time_enforcement.py:129` | `execution_key="exec_key_k02_integration"` | same |
| `frontend/src/pages/ResearchData.tsx:100` | a code comment naming "query keys, OCC/Idempotency tokens" | prose |
| `scripts/migration-acceptance.sh:235,237` | `app_metadata where key='adim22.legacy_probe'` | SQL row key |

No real credential is committed anywhere in the working tree.

---

## 3. What this slice adds

### 3.1 `.github/workflows/security.yml` (new)

Four scan surfaces, `permissions: contents: read` at the top, `security-events:
write` on the CodeQL job **only**:

* **CodeQL** — `python` and `javascript-typescript`, `build-mode: none`, the
  `security-and-quality` query pack.
* **Secret scan** — gitleaks over the working tree on every push/PR; over the
  **full history** on the weekly schedule. A secret that was committed and later
  deleted is a rotation problem, not a merge blocker, so it does not gate PRs.
* **Container scan** — both images built, `docker save`d, scanned from the tar.
  **No Docker socket is mounted into the scanner**: the socket is root-equivalent
  on the host and a scanner needs to read layers, not control the daemon.
* **SBOM** — four CycloneDX documents (backend image, frontend image, backend
  source, frontend source), uploaded as the `sbom-cyclonedx` artifact with 90-day
  retention. Both *image* and *source* SBOMs exist because the frontend image is
  nginx plus built assets — `node_modules` never ships, so an image-only SBOM
  would omit every JS dependency the bundle was compiled from.

Also in that job: a **non-root assertion** on both images (`docker run
--entrypoint id -u`, fail if `0`). A vulnerability scan says which packages are
weak; it never says who the process would be when one is exploited.

Locally measured, all four `bomFormat: CycloneDX`, specVersion `1.7`:

| Document | Components | Source it read |
|---|---|---|
| `backend-image.cdx.json` | 1202 | debian 13.6 packages + Python site-packages, plus the vendored Rust crates inside the `uv` binary |
| `frontend-image.cdx.json` | 72 | alpine packages (nginx runtime) |
| `backend-source.cdx.json` | 81 | `uv.lock` |
| `frontend-source.cdx.json` | 13 | `package-lock.json` |

**Caveat on the frontend source count, stated rather than glossed:** 13 is not a
mistake and it is not the whole dependency tree. Trivy's npm lockfile scanner
reports the **runtime** dependency closure and excludes `devDependencies`, so
vite, vitest, eslint and the TypeScript toolchain are absent. That is the right
scope for an SBOM of a shipped artifact — none of them reaches a user — but it
means these documents answer "what ships", not "what was used to build it".
Build-time dependency risk stays with `npm audit` in `ci.yml`, which reads the
full tree.

### 3.2 Fail policy and the allowlist

`.github/security-allowlist.json` + `scripts/security-allowlist-gate.mjs`.

The gate fails on **any CRITICAL/HIGH finding that has a published fix and no
recorded exception**, and it re-derives "has a fix" from `FixedVersion` itself
rather than trusting the `--ignore-unfixed` flag — dropping the flag cannot
silently widen it.

Every entry requires `id`, `scope`, `package`, `owner`, `justification`,
`expires`. Two behaviours the repo's two older exception lists
(`FROZEN_ADVISORIES`, `ACCEPTED_SERIOUS_RULES`) do not have:

* **An expired entry fails the build**, whether or not the finding still appears.
  An exception nobody re-examines is not an exception, it is a hole.
* **A malformed entry fails the build** — an entry missing `expires` would
  otherwise be an exception that never expires.

**The allowlist ships empty.** Nothing is currently excepted.

Five proofs, run locally:

| # | Scenario | Result |
|---|---|---|
| 1 | Real backend + frontend reports, empty allowlist | **PASS** — `0 fixable CRITICAL/HIGH` |
| 2 | Synthetic fixable HIGH, not allowlisted (plus an unfixable CRITICAL) | **FAIL** on the fixable one only |
| 3 | Same finding, allowlisted, `expires 2026-09-30` | **PASS**, printed as `allowed … owner …` |
| 4 | Same entry, `expires 2026-08-04` (yesterday) | **FAIL — expired security exceptions** |
| 5 | Same entry with `expires` deleted | **FAIL — malformed** |

### 3.3 Workflow hardening + a gate that keeps it

* `permissions: contents: read` added to `ci.yml` and `e2e.yml`. Both previously
  inherited the repository default. That matters here specifically: `ci.yml`
  resolves and executes third-party package code (`uv sync`, `npm install`,
  `pip-audit`) and `e2e.yml` boots the whole application and drives it with a
  browser — both while holding a token that could push to `main`.
* `astral-sh/setup-uv@v7` → `@37802adc94f370d6bfd71619e3f0bf239e1f3b78 # v7` in
  `ci.yml` and `install-acceptance.yml`. `actions/*` stay on tags on purpose:
  GitHub's own org, versioned with the runner images.
* Scanner containers are pinned **by digest**, not tag — stronger than a
  SHA-pinned marketplace action, because it also pins the tool's dependencies.
* **Fork-PR secret exposure: none.** Every workflow uses `pull_request`; no
  `pull_request_target` exists anywhere in the repo.

`backend/tests/unit/test_workflow_supply_chain.py` (20 tests, 5 assertions ×
4 workflows) pins all of it by reading the workflow files. Each assertion was
negative-proven against a deliberately bad workflow — all five fire.

### 3.4 Container runtime

| | Before | After |
|---|---|---|
| backend image user | uid 10001 (`entropia`) | unchanged |
| **frontend image user** | **root (uid 0)** | **uid 101 (`nginx`)** — `nginxinc/nginx-unprivileged:1.31-alpine`, container port 80 → 8080 |
| capabilities | full default set | `cap_drop: ALL` on all 11 of our services (api, migrate, provision, scheduler, agent-coordinator, 5 workers, web) |
| privilege escalation | possible via setuid | `no-new-privileges:true` |
| root filesystem | writable | `read_only: true` + tmpfs `/tmp` on `web` |
| Docker socket | not mounted | still not mounted |
| `privileged` | none | none |

The published **host** port is unchanged (`${WEB_HOST_PORT:-8080}`), so e2e,
install-acceptance and `scripts/smoke.sh` are untouched.

**Verified by running it**, not by reading the file: the full stack was brought
up on an isolated project with the hardening applied, and
`scripts/acceptance.sh` (the repo's own DEP-05 gate) returned
`ACCEPTANCE OK — every plane is up; nothing exited/restarted/unhealthy` across
all 12 services plus 3 one-shots. Measured effective uids: api `10001`,
worker-default `10001`, web `101`.

**Scope boundary, deliberate:** `postgres`, `redis` and `minio` keep default
capabilities. They are third-party images whose entrypoints perform their own
privilege drops, and widening a security PR into the data layer buys little for
real risk. Recorded, not overlooked.

### 3.5 HTTP response headers

**A real defect, reproduced before the fix.** `frontend/nginx.conf` set three
security headers at `server` level, and `location /assets/` set `add_header
Cache-Control`. nginx inherits `add_header` from an outer level *only if the
current level declares none of its own* — so every hashed JS and CSS bundle, i.e.
all the executable code this app ships, was served with **no `nosniff`, no
`X-Frame-Options`, no `Referrer-Policy`**, while `/` looked correct.

Measured on `e6cd2ee`:

```
/                    -> X-Content-Type-Options, X-Frame-Options, Referrer-Policy
/assets/index-*.js   -> Cache-Control only
```

Fixed by moving the header set into `frontend/nginx-security-headers.conf` and
`include`-ing it at both levels, so a future location block cannot regress it.
`Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()`
added. Re-measured after the fix: all four headers present on **both** paths.

The **backend** headers were already correct and are unchanged
(`apps/api/hardening.py`: `nosniff`, `DENY`, `no-referrer`,
`default-src 'none'`, HSTS in production only).

**CORS: no wildcard added, none present.** `API_CORS_ORIGINS` is env-driven;
`Settings._require_explicit_cors_origins_in_production` already refuses `*` and
an empty list under `ENTROPIA_ENV=production`, with 10 contract tests behind it.

### 3.6 Production credential fail-closed (new)

`.env.example` ships `OBJECT_STORAGE_ACCESS_KEY=entropia`,
`OBJECT_STORAGE_SECRET_KEY=entropia-secret` and a
`postgresql+asyncpg://entropia:entropia@…` URL — and `docker-compose.yml`
repeats every one as a `${VAR:-default}` fallback. A production deployment that
simply never set those variables did **not** get an error; it got a working stack
whose artifact store and database are reachable with credentials anyone can read
in this repository, with every health check green.

`Settings._reject_shipped_default_credentials_in_production` now refuses to
construct under `ENTROPIA_ENV=production` while any of the three is unchanged,
naming all offenders at once. Production-only on purpose: local and staging are
meant to run on these values, and breaking `make up` would only teach people to
unset `ENTROPIA_ENV`. Same shape as the two existing production validators.

9 tests, including one that pins the constants **to `.env.example` itself** — so
rotating the example values without updating the check cannot silently leave the
gate passing on whatever is newly published.

### 3.7 Upload surfaces

Two verified fail-open paths closed. Both preserve the wire contract — OpenAPI
drift guard is clean.

**(a) Create Package baseline accepted any file whose NAME ended in `.csv`.**
`upload_baseline_asset` called `is_allowed_baseline_file`, an extension predicate
only — no content sniff. A zip, PDF, ELF, gzip or NUL-bearing payload named
`baseline.csv` was accepted and written to object storage as an **immutable
baseline asset**, the single artifact a package's equivalence claim rests on.
Every other upload surface (trade_log, trading_signal, market_data,
research_data) already routed through the shared K-07 gate; this one did not.
Now routed through `assert_supported_source_file` with the same
`FileTypeNotAllowedError` / `FILE_TYPE_NOT_ALLOWED` class doc 06 §8.3 mandates.
**8 new integration tests** (5 binary payload shapes × `.csv` name, 3 blank-name
shapes); the file's 20 tests pass.

**(b) The Agent plane could upload what a human cannot.**
`_handle_trading_signal_upload_source` states the rule in its own docstring — the
F-03 byte gate lives at the multipart route, so the UI-less Agent plane must run
it itself "off ONE shared ceiling". `_handle_trade_log_upload_source` did not run
it: no size ceiling, no whole-document UTF-8 check, no CSV-header check, and it
used `request.get()` instead of the fail-closed shape helpers, so `bytes(5)`
would have silently stored five NUL bytes. Now runs
`assert_source_bytes_admissible(content, require_csv_schema=True)`, mirroring
`routes/trade_log.py` exactly. **16 new unit tests**, parametrized across both
planes; they pass `session=None` on purpose — the gate must reject before the
command, so reaching the session would be an `AttributeError`, not a pass.

**Adversarial coverage assessed, item by item** (from a full read of the upload
chain):

| Vector | Finding |
|---|---|
| extension | allowlisted, fail-closed on blank/missing filename |
| **MIME / `Content-Type`** | **never validated anywhere** — stored and echoed only. Low risk: the content sniff is strictly stronger than a client-declared type. Recorded, not changed. |
| magic bytes / header | 13 binary signatures + NUL scan + bounded UTF-8 decode (`sniff_text_content`) |
| size | 50 MB source, 200 MB market/research, 25 MB baseline. **No ASGI/Starlette request-body cap** — the ceiling is enforced after a bounded `read(max+1)`, so the socket still accepts the body. Recorded. |
| zip bomb | **not reachable** — nothing in `backend/` imports `zipfile`/`tarfile`/`gzip`; archives are rejected at the front door by the magic-byte table |
| path traversal | **not reachable** — object keys are `prefix/server-id/sha256`; the user filename never reaches a key or a path. It is stored and echoed unsanitized, but there is no download endpoint and no `Content-Disposition` anywhere. |
| object key | server-generated ids + hex digests only |
| CSV formula injection | **no CSV writer exists** in the backend — `ExportFormat.CSV` computes a key and a checksum; the engine is a documented stub. Greenfield, not a broken control. |
| Parquet metadata | user input is **never** parsed as Parquet (only `pl.read_csv`); Parquet reads are of server-written objects. No schema/footer validation on read — recorded. |

### 3.8 Backup artifacts

Two issues, both fixed and both verified end-to-end against the live stack.

* **World-readable dumps.** `mkdir -p "$DEST"` ran under the default umask, so
  `postgres.dump` — every argon2id password hash, every session-token digest,
  every row — landed `0644` inside a `0755` directory. Now `umask 077` plus an
  explicit `chmod 700`. Measured after: `drwx------` on both directories,
  `-rw-------` on `postgres.dump`.
* **Object-storage secret in the process table.** `mc alias set … "$OBJ_SK"` put
  the secret in argv (world-readable via `/proc/<pid>/cmdline` on Linux) and
  persisted it to `~/.mc/config.json`; the dockerized fallback additionally baked
  it into the container's stored command, where `docker inspect` hands it to
  anyone in the docker group. Both now use `MC_HOST_<alias>` (per-invocation,
  same-user-only, nothing persisted), with a percent-encoder so a secret
  containing `@`, `:` or `/` cannot re-parse the URL.

Both branches exercised: the host-`mc` path and — with `mc` hidden from `PATH` —
the dockerized fallback, which really mirrored a seeded object.

**Not changed:** backups are still unencrypted at rest. `backups/` is gitignored,
so no dump can be committed. Recorded in §5.

---

## 4. Verification performed

| Check | Result |
|---|---|
| `ruff check .` / `ruff format --check .` | pass |
| `mypy src` | `Success: no issues found in 394 source files` |
| OpenAPI drift guard | `snapshot is up to date` — no public API change |
| Alembic | **no migration in this slice** (single head unchanged, `0043_i08_registry_strategy_fks`) |
| Backend full suite + coverage gate | see §7 |
| Frontend lint / typecheck / coverage / build | see §7 |
| Container smoke — full stack, hardened | `ACCEPTANCE OK` (`scripts/acceptance.sh`, 12 services + 3 one-shots) |
| nginx headers, before and after | measured with `curl -D-` on the running image |
| Backup, both branches | run against the live stack; permissions and mirrored bytes measured |
| Allowlist gate | 5 scenarios, pass and fail paths both proven |
| Workflow gate assertions | all 5 negative-proven against a bad workflow |
| gitleaks config | 0 findings on the tree, and planted secrets still fire identically to the default ruleset |

**On the gitleaks config specifically:** the allowlist matches identifier
*shapes*, not paths. A path exclusion (`backend/tests/**`, `scripts/**`) would
also stop the scanner finding a real key committed into a test fixture — the most
likely place for one to land. Proven: with two secrets planted (one in
`backend/tests/`, one in `scripts/`), the configured scan and the bare default
ruleset both report exactly 2.

**Not verified in this slice** (stated plainly rather than implied):

* The `security.yml` workflow has **not yet run on GitHub Actions**. Every tool
  invocation in it was run locally with the same pinned image digests and the
  same flags, but CodeQL in particular cannot be exercised locally. Its first
  real run is on this PR.
* `read_only: true` was applied to `web` only. The backend planes were **not**
  made read-only: `parquet_stream.py` spools to disk above 32 MB, and proving
  that safe needs a full data-ingest acceptance run, not a smoke.
* No screen-reader or a11y work — out of scope, unchanged.

---

## 5. Risk acceptance list

Nothing here is in the machine-enforced allowlist (which ships empty); these are
findings recorded and deliberately not changed in this slice.

| # | Finding | Severity | Why not fixed here | Suggested owner action |
|---|---|---|---|---|
| R-1 | 23 unfixable HIGH/CRITICAL in the backend Debian base | HIGH (nominal) / low real | No published fix exists in any Debian suite. Not on a request path. | The `--ignore-unfixed` gate goes red automatically the day Debian ships a fix. Dependabot's docker ecosystem bumps the base. |
| R-2 | `GHSA-qwww-vcr4-c8h2` react-router RSC CSRF | HIGH (nominal) / none real | Requires RSC mode; this is a `BrowserRouter` SPA. Fix is the react-router v8 migration. | Revisit when v8 is scheduled. Already frozen with a written reason. |
| R-3 | **No rate limiting on `/auth/login` or `/auth/signup`** — `RATE_LIMIT_ENABLED` defaults to `False`, and when enabled login shares the generic 120/min write budget. No lockout, no failed-attempt throttle. | **HIGH** | Turning the middleware on by default, or adding a login-specific bucket, is a behaviour change on every deployment; it belongs in a reviewed auth slice, not bundled into a supply-chain PR. | Dedicated slice: login/signup bucket + `X-Forwarded-For` handling (today `request.client.host` collapses every caller behind the proxy into one bucket). |
| R-4 | **No bulk session revocation.** Changing a password does not invalidate outstanding sessions; there is no revoke-all. | MEDIUM | New feature, not a gate. (Role/status changes *are* covered — `resolve_actor` re-reads them per request.) | Add revoke-all on password change and on deactivation. |
| R-5 | Trade Log agent tool inlines raw upload bytes into the durable tool-call envelope — `_SOURCE_CONTENT_TOOLS` contains only `TRADING_SIGNAL_UPLOAD_SOURCE`. | MEDIUM | The exclusion is a **recorded prior decision** ("the landed trade_log tools have their own recorded envelope shape and this slice does not restate it"). Changing it alters a stored contract. | Owner decision: the harm the comment describes for the signal family (multi-megabyte payload duplicated into evidence storage forever) applies identically here. |
| R-6 | User Manual upload validates by extension only, no magic-byte sniff | LOW | Incidentally covered: the path decodes the whole document as UTF-8 and caps at 1M chars, so binary fails anyway. | Wire it through the shared gate for consistency. |
| R-7 | No ASGI request-body cap; ceilings are enforced after a bounded read | LOW | Correctly bounded already (`read(max+1)`) — the memory exposure is one byte over the cap, not the whole body. | Optional: a middleware `Content-Length` pre-check. |
| R-8 | `Content-Type` never validated on upload | LOW | The content sniff is strictly stronger than a client-declared MIME type. | None required. |
| R-9 | Backups unencrypted at rest | MEDIUM | Key management is a deployment decision, not a repo one. | Choose an approach (age/gpg/filesystem encryption) and document it in `docs/BACKUP_DR.md`. |
| R-10 | `postgres`/`redis`/`minio` keep default capabilities | LOW | Third-party entrypoints perform their own privilege drops; widening the blast radius of a security PR into the data layer is not worth it. | Optional follow-up with its own acceptance run. |
| R-11 | Backend planes not `read_only` | LOW | Needs a data-ingest acceptance run to prove the spool paths (§4). | Follow-up with `tmpfs /tmp` and a full ingest run. |
| R-12 | `/docs` and `/openapi.json` are ungated in production | LOW | Schema exposure only; every route behind it is authorized server-side. | Owner decision. |
| R-13 | No log-redaction processor — `observability/logging.py` states the rule in prose only | LOW | No actual leak found; adding a processor without a demonstrated leak is speculative. | Optional: a structlog processor that drops known credential keys. |
| R-14 | **`backend/uv.lock` on `main` is corrupt.** Its `[package.metadata] requires-dist` block has a blank line where `boto3` and `boto3-stubs[s3]` belong — verified byte-for-byte against `git show HEAD:backend/uv.lock`. Any `uv sync` repairs it, so every contributor gets a spuriously dirty working tree. | LOW (hygiene, not security) | Unrelated to this slice; including a lockfile repair in a security PR is exactly the bundling the PR discipline forbids. The change was **reverted** so this PR carries none of it. | One-line PR: run `uv sync --all-extras` and commit the regenerated lock. |

**Release verdict: NOT READY.** R-3 is an unresolved HIGH. Per this slice's stop
condition, the PR is opened and work stops here rather than declaring readiness.

---

## 6. Migration / OpenAPI / codemap impact

* **Migration:** none. Alembic head unchanged at `0043_i08_registry_strategy_fks`.
* **`ENGINE_VERSION`:** unchanged. No engine semantics touched — the upload
  changes reject earlier; they do not alter any accepted result.
* **OpenAPI:** unchanged, drift guard verified. The baseline fix deliberately
  keeps `FileTypeNotAllowedError`, so the wire contract is identical; only the
  `details` payload gains the shared gate's `{field, actual, reason}` shape,
  which `ErrorBody.details` already types as free-form.
* **Codemaps:** no new endpoint, table, page or job. `docs/CODEMAPS/` unchanged.

## 7. Suite results

Filled in from the runs recorded in the PR description — see the PR body for the
verbatim summary lines and exit codes.
