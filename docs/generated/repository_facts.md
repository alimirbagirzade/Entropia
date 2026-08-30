<!-- doc-status: current -->
# Repository facts (GENERATED — do not edit by hand)

> Regenerate with `cd backend && uv run python ../scripts/generate_repository_facts.py --root ..`.
> CI runs the same script with `--check` and fails when this file is stale, so an out-of-date
> number here is a red build rather than a document a later agent believes.

**This file contains working-tree facts only.** No commit sha, no timestamp and no GitHub
state (open PRs, issue status, workflow runs) — those are properties of a server, not of this
tree, and embedding them would make the artefact impossible to reproduce or to keep green.
**No test pass count either:** every test number below is a *collected* node count from a
static walk. Only a full CI run reports passes.

## Summary

| Fact | Value |
|---|---|
| Alembic head | `0044_drop_net_conflict_policy` |
| Alembic revisions | 44 (single head) |
| Postgres tables | 104 |
| Foreign keys | 140 |
| HTTP paths | 177 |
| HTTP operations | 196 |
| Frontend router paths | 29 |
| Frontend nav items | 25 |
| Application modules (`domain/` packages) | 32 `commands` · 38 `queries` · 16 `jobs` (26 packages) |
| `ENGINE_VERSION` | `backtest-engine-v18-policy-provenance-completed` |
| `SHARED_ALLOCATION_STATUS` | `active_v1` |
| Capability matrix | 62 rows (40 `active_v1`, 22 `future_dev`) |
| Backend tests **collected** (static, not a pass count) | 3892 in 371 files |
| Backend `xfail` markers | 0 (0 strict) |
| Frontend unit test **call sites** (static; `.each` expands at run time) | 732 in 72 files |
| E2E test **call sites** (static) | 84 in 22 specs |
| Acceptance criteria mapped | 383 |
| Acceptance clauses mapped | 1175 |

## Acceptance map status totals

| Level | covered | deliberate_future_dev | not_applicable | partial | uncovered |
|---|---|---|---|---|---|
| Criteria | 308 | 8 | 7 | 54 | 6 |
| Clauses | 1068 | 27 | 12 | 4 | 64 |

## HTTP operations by method

| Method | Count |
|---|---|
| `DELETE` | 9 |
| `GET` | 81 |
| `PATCH` | 3 |
| `POST` | 102 |
| `PUT` | 1 |

## Visual baselines and recorded deviations

| Fact | Value |
|---|---|
| Playwright snapshot PNGs | 23 |
| Screenshot baseline PNGs | 122 |
| Screenshot prototype PNGs | 20 |
| a11y frozen serious nodes (`frontend/e2e/a11y-baseline.json`) | 45 across 23 pages |
| Visual deviation rows | 38 |
| … awaiting a FIX slice | 8 |
| … PO-APPROVE (deliberate) | 26 |
| … neither (no deviation / decided on another row / deferred) | 4 |

> The full per-table, per-route and per-path lists live in [`repository_facts.json`](repository_facts.json).
