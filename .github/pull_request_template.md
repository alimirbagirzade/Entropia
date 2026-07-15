## Summary

<!-- What changed, and why. Link the relevant spec section (docs/spec/) or
     stage doc (docs/STAGE_BUILD_PLAN.md) if applicable. -->

## Changes

-

## Test plan

<!-- How was this verified? Check what applies and describe specifics. -->

- [ ] `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest`
- [ ] `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`
- [ ] New/changed migrations: `alembic upgrade head` → `downgrade -1` → `upgrade head` verified
- [ ] New `create_*` commands: FK insert-order proof included
- [ ] Manually verified in the browser / via API calls (describe below)

## Risk / rollback

<!-- Anything risky about this change (migration, auth, payment/financial
     logic, breaking API/contract change)? How would it be rolled back? -->

## Checklist

- [ ] No secrets, credentials, or API keys committed
- [ ] No AI attribution in commit messages or this description
- [ ] Docs updated if behavior, setup, or API surface changed
- [ ] CI is green
