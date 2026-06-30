# Entropia — Stage 2 Handoff

> Living handoff for the staged build. Update the **Status** + **Next** sections as sub-stages land.

## Status (as of Stage 2e merge)

`main` contains: **Stage 0 + 1 + 2a + 2b + 2c + 2d + 2e**, all merged via green CI (backend lint/type/**integration on real Postgres**/alembic, frontend, docker).

| Sub-stage | Page(s) | State | PR |
|-----------|---------|-------|----|
| 2a | Market Data (11) | ✅ merged | #1 |
| 2b | Research Data (12) | ✅ merged | #2 → #1 → main |
| 2c | ESP / Embedded System Packages (09) | ✅ merged | #3 |
| 2d | Rationale Families (10) | ✅ merged | #4 |
| 2e | Create Package + Pre-Check (06, 07) | ✅ merged | #5 |
| 2f | Package Library (08) | ⬜ next | — |

Alembic head: `0007_create_package_precheck` (…→0005_esp_packages→0006_rationale_families→0007_create_package_precheck).

## How each sub-stage is built (the working loop)

1. Branch off `main`: `feat/stage-2<x>-<slug>`.
2. Run a **Workflow** (author core → author app+tests → review) with the binding decisions + lessons below baked into the prompt.
3. Verify locally: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest --no-cov` (unit+contract pass; integration auto-skips without local Postgres).
4. **FK insert-order proof** for any new `create_*` (async probe with `uv run --with aiosqlite python`, JSONB→TEXT `@compiles` shim) — confirm `entity_registry` inserts before child rows.
5. Apply review CRITICAL/HIGH/cheap-MEDIUM fixes; commit.
6. PR → `main`; watch CI (`gh run watch <id> --exit-status`); merge with `gh pr merge <n> --merge --delete-branch` when green.

## Binding architecture (authoritative: docs/ARCHITECTURE.md §131-133, DOMAIN_MODEL.md §1)

- `entity_registry` is the **universal Root** (one row per durable object, discriminated by `entity_type`). Per-domain **dedicated `*_revision` + detail/support tables** FK to `entity_registry.entity_id`. No EAV/generic-JSON for core domain; dependency/reference edges get normalized tables.
- Stage-1 soft-delete/restore/purge operate generically on `entity_registry` — keep them working.
- One generic `approval_decision` table (target_kind discriminator) for all approvals.
- Lifecycle/validation/approval/visibility are **separate facets** (CR-04), lowercase snake_case enums in `domain/<x>/enums.py` (+ shared in `domain/lifecycle/enums.py`).

## Hard-learned lessons (apply proactively — these caused real failures)

- **L1 FK insert order:** SQLAlchemy UOW does NOT order parent-before-child from a bare `ForeignKey` (no `relationship()` on `entity_registry`). Every `create_*` that makes a root + child in one flush must be **async**: add root → `await session.flush()` → add children. (Fixed in `create_market_dataset`, `create_research_dataset`, `create_package`.)
- **L2 Idempotency ordering:** put optimistic-concurrency (`check_row_version`/`check_head`) **and** state-machine legality checks **inside** the `run_idempotent` operation body — else a completed-key replay raises a spurious 409 instead of returning the cached result. Authorization + pure input validation stay outside.
- **L3 Role/page gating:** enforce server-side at route **and** service layer, per each page's doc. Read the doc's role matrix — e.g. Research Data page is Admin/Supervisor/Agent only (router gate); ESP list/detail are any-authenticated but activate/deprecate are Admin-only; the resolve endpoint requires `require_authenticated`. Contract tests must pick an actor that passes the page gate but fails the specific check, so the asserted error code is the intended one.
- **L4** No fabricated metrics (null/`not_applicable`, never 0). **L5** Pin exact `revision_id`+`content_hash` (never "latest"). **L6** Register every model in `models/__init__.py __all__`.
- **L7 Optimistic-token + check-before-mutate:** an `expected_*_version` token is **inert unless** every state-advancing op bumps the root `row_version` (and `SELECT … FOR UPDATE`-locks the root). Within the `run_idempotent` body, run legality/concurrency checks **before** any row mutation — 2e `approve_and_publish` first mutated then checked (and whitelisted states with no legal `→approved` edge); both fixed pre-merge.
- CI runs only on PRs whose **base is `main`** (push to non-main branches does not run CI). So land each stage via a PR → main.

## Reusable foundation (don't re-create)

`application/idempotency.py` (`run_idempotent` — now **per-principal scoped**: never replays another actor's cached result), `infrastructure/queues/enqueue.py` (`enqueue_job`/`send_job`, durable job row = source of truth, CR-09), `shared/manifest.py` (`manifest_hash`), `infrastructure/s3/datasets.py`, `repositories/approvals.py` (`add_approval_decision`), the shared **Package** model from 2c (`models/packages.py`, `repositories/packages.py` — `create_package` is async/FK-safe) which **2e reuses**, and the ESP resolver registry (`resolve_embedded_dependency`) which **2e Pre-Check consumes**.

## Known LOW follow-ups (tracked, not blocking)

- List endpoints (market/research/esp) compute `has_more`/cursor over the **post-visibility-filter** set → under-filled pages; push the visibility predicate into SQL.
- `queries/esp.py::_visibility_of` has an unused `root` param + misleading docstring.
- ESP soft-delete / `DELETE_POLICY_BLOCKED` deprecate-first guard deferred to a later stage.
- Research: derive-from-base market-link carry-forward; approve/revoke root `row_version` bump; idempotency keys on draft-edit endpoints.
- Consider aligning ESP audit `event_kind` to doc 09's `resolver.registry.activated`.
- Rationale family **name uniqueness is app-enforced only** (`find_active_or_reserved_by_name` + check inside `_op`); add a root-level denormalized active-name column + partial unique index for a DB-level backstop against concurrent same-name creation. Same gap as the no-cascade `package_rationale_assignment` table-version token (coarse; the per-row `expected_head_revision_id` is the real guard).
- 2e **candidate-generation compute + dependency-scan parsing are V1 stubs** (the durable rows, both state machines, resolver wiring, idempotency, concurrency, and audit/outbox are real); wire real generation + a real source-call scanner in a later stage. `dependency_scan` is already append-only with `attempt_no` to absorb re-scans.

## Stage 2d — Rationale Families (doc 10) ✅ landed (#4)

Shared-edit exception (DOMAIN_MODEL §6): all four roles create/edit/rename/soft-delete any family + edit any assignment via `can_manage_rationale_families` / `can_edit_rationale_assignments` (NOT owner policy). `rationale_family_root` (detail + `display_color`) + immutable `rationale_family_revision` + `package_rationale_assignment` edge (`target_kind = package_revision | working_item_revision`), all entity_registry-anchored; `create_family` is async/FK-safe. Atomic all-or-nothing batch with `expected_table_version` + per-row `expected_head_revision_id` → `PACKAGE_RATIONALE_ASSIGNMENT_CONFLICT`; each changed assignment makes a new package revision (carrying contracts forward; package owner unchanged); identical resubmit = idempotent no-op; output mismatch = non-blocking `OUTPUT_TYPE_NOT_LISTED` warning. Assignment table renders the family's **current** name live (rename without re-pinning). 6 ACTIVE seed families behind `SEED_RATIONALE` (incl. `Embedded System / TA Resolver`). Migration `0006_rationale_families`. **Consumed by:** 2e Strategy required-family picker (ACTIVE roots only) + 2f Package Library family filter (`rationale_family_id` join).

## Stage 2e — Create Package + Pre-Check (docs 06, 07) ✅ landed (#5)

Reuses the shared **Package** model (2c `create_package`, async/FK-safe) + the ESP resolver registry (`resolve_embedded_dependency`). Two new entity_registry-anchored tables: `package_request` (mutable detail, optimistic `row_version`) + immutable append-only `dependency_scan` (`attempt_no`, `source_hash`/`context_hash` staleness anchors, JSONB detected/resolved/missing/unsupported calls). Command chain (all idempotent; concurrency + legality checks inside the body, **before** mutation — L2/L7): `create_package_request` → `run_precheck` (resolves each declared canonical TA call against the **live** 2c ESP registry, pins exact `revision_id`+`content_hash` — L5; blocked path on missing/untrusted) → `submit_candidate_generation` (Send gate re-checks precheck freshness + registry-race staleness) → `create_draft_from_candidate` (reuses 2c `create_package`) → `approve_and_publish` (**Admin-only**, CR-02, atomic head repoint). Non-Admins create requests only. Create-Package + Pre-Check state machines per DOMAIN_MODEL §3.2. Candidate-generation compute + scan parsing are honest **V1 stubs**; all durable rows, resolver wiring, per-principal idempotency, concurrency control, and audit/outbox are real. Migration `0007_create_package_precheck`. **Adversarial review fixed 3 issues pre-merge:** (1) `approve_and_publish` legality check hoisted before any mutation + approvable-state set reconciled to legal edges; (2) `package_request.row_version` now bumped on every state advance (+ root row lock) so `expected_request_version` is a live token; (3) per-principal idempotency isolation in shared `run_idempotent`. **Consumed by:** 2f Package Library (lists published packages; `dependency_scan` = "how this package was built" provenance).

## Next: Stage 2f — Package Library (doc 08)

The catalog/browse surface over published packages — the last sub-stage of Stage 2. **Extract doc 08's spec first** (role matrix, filter set, columns, detail panel, pagination) — no spec has been extracted yet. Known reuse: the shared **Package** model + revision chain (2c), the **2d rationale family filter** (`rationale_family_id` join, ACTIVE roots only), and 2e `package_request`/`dependency_scan` provenance for the detail view. Likely **read-mostly** (list/detail queries with server-side visibility filtering + cursor pagination), so mind the known LOW follow-up: push the visibility predicate into SQL so `has_more`/cursor count the **post-filter** set (don't repeat the market/research/esp under-fill). Follow the working loop above; FK insert-order proof for any new `create_*`.
