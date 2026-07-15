# Contributing to Entropia

Entropia is proprietary software (see [`LICENSE`](LICENSE)). This guide is for
authorized collaborators working in this repository — it documents the local
setup, development workflow, and quality gates a change must pass before merge.

## Getting started

**Docker (recommended):**

```bash
git clone https://github.com/alimirbagirzade/Entropia.git
cd Entropia
cp .env.example .env
docker compose up -d --build
```

**Docker-free (native):** see the [`README`](README.md#quick-start) for the
per-OS bootstrap script, or run `make bootstrap` then `make up` /
`make backend-dev` / `make frontend-dev`. Run `make help` for the full list of
developer targets (migrations, linting, tests, backups).

## Project structure

| Path | Contents |
| --- | --- |
| `backend/` | FastAPI + SQLAlchemy 2 (async) + Alembic; see [`backend/README.md`](backend/README.md) |
| `frontend/` | React 18 + TypeScript + Vite; see [`frontend/README.md`](frontend/README.md) |
| `docs/spec/` | Canonical specification — the authoritative tech contract |
| `docs/STAGE_BUILD_PLAN.md` | Stage roadmap and acceptance criteria |
| `docs/STAGE2_HANDOFF.md` | Running handoff — what has landed, what's next |

Read [`docs/spec/`](docs/spec/) and the current
[`STAGE2_HANDOFF.md`](docs/STAGE2_HANDOFF.md) before starting non-trivial work
— this project is built stage-by-stage from a canonical spec, and changes
should trace back to it.

## Development workflow

1. **Branch from `main`.** Use a descriptive prefix: `feat/`, `fix/`, `docs/`,
   `refactor/`, `chore/`.
2. **Make focused changes.** One logical change per PR — do not mix unrelated
   fixes, refactors, and features.
3. **Write tests first where practical** and keep coverage at or above the
   project baseline; a behavior change without a test is not done.
4. **Run the local verification suite before opening a PR:**

   ```bash
   cd backend && uv run ruff check . && uv run ruff format --check . \
     && uv run mypy src && uv run pytest
   cd frontend && npm run lint && npm run typecheck && npm test && npm run build
   ```

   Every new `create_*` command needs an FK insert-order proof; every new
   migration needs an `alembic upgrade head` / `downgrade -1` / `upgrade head`
   round-trip and migration↔model column parity — see
   [`backend/README.md`](backend/README.md) for details.
5. **Commit using Conventional Commits:** `type(scope): subject` (types: feat,
   fix, refactor, docs, test, chore, perf, ci). No AI attribution in commit
   messages or PR text.
6. **Open a PR against `main`.** Include a summary of the change, the
   motivation, and a test plan. Link any relevant spec section or issue.
7. **CI must be green** (backend lint/type/test, frontend lint/typecheck/
   test/build, Docker image build) before requesting review.

## Code conventions

- **Backend:** Python 3.12, full type hints, Pydantic v2 models, async
  SQLAlchemy 2. Follow the module-level async command pattern already used
  throughout `backend/src/entropia/application/commands/` (one transaction,
  no partial commits, optimistic concurrency via row versions / revision
  ids, audit + outbox emitted in the same transaction).
- **Frontend:** TypeScript, React 18 function components, TanStack Query for
  server state. UI changes must match the canonical v18 mockup
  (`docs/spec/index_guncellenmis_duzeltilmis_v18.html`) and must not touch
  route paths, query keys, OCC tokens, or `lib/*.ts` data logic unless the
  change is explicitly about that logic.
- **No dead code, no commented-out code, no speculative abstractions.** Keep
  functions small and files focused; extract when a file grows unwieldy
  rather than before.
- **Never commit secrets.** `.env`, credentials, and API keys stay out of the
  repository — see [`SECURITY.md`](SECURITY.md) if you find one that leaked.

## Reporting bugs and requesting features

Use the issue templates under **New Issue** — pick *Bug report* or *Feature
request*. Include reproduction steps, expected vs. actual behavior, and
relevant logs for bugs; use case and proposed approach for features.

## Security issues

Do not open a public issue for a security vulnerability. See
[`SECURITY.md`](SECURITY.md) for how to report it privately.
