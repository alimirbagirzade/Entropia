# Entropia V18 — Windows task runner (PowerShell mirror of the Makefile).
#   .\scripts\tasks.ps1 <task>
param([Parameter(Position = 0)][string]$Task = "help")
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

switch ($Task) {
    "help" {
        Write-Host "Entropia tasks:" -ForegroundColor Cyan
        @(
          "  bootstrap          One-time local setup",
          "  update             Pull latest + update deps + migrate (no Docker)",
          "  up                 Start the full stack - NORMAL session auth (real login)",
          "  up-dev-auth        Start the stack in dev-auth impersonation (X-Actor-Id; local-only)",
          "  down               Stop the stack (keep volumes)",
          "  restart            Rebuild and restart the stack",
          "  logs               Tail service logs",
          "  ps                 Stack status",
          "  migrate            Apply DB migrations to head",
          "  accept             Acceptance gate: fail if any service exited/restarted/unhealthy",
          "  accept-dev-auth    Acceptance gate against the dev-auth stack",
          "  backend-install    uv sync backend deps",
          "  backend-dev        Run API with reload",
          "  backend-test       Run backend tests",
          "  backend-lint       Ruff + mypy",
          "  test               Run all tests (backend + frontend; fails if either fails)",
          "  frontend-install   npm install",
          "  frontend-dev       Vite dev server",
          "  frontend-build     Production build",
          "  frontend-lint      ESLint + typecheck",
          "  nuke               Stop stack and DELETE volumes"
        ) | ForEach-Object { Write-Host $_ }
    }
    "bootstrap"        { & "$PSScriptRoot\bootstrap.ps1" }
    "update"           { & "$PSScriptRoot\update.ps1" }
    "up"               { docker compose up -d --build }
    "up-dev-auth"      { docker compose -f docker-compose.yml -f docker-compose.dev-auth.yml up -d --build }
    "down"             { docker compose down }
    "restart"          { docker compose down; docker compose up -d --build }
    "logs"             { docker compose logs -f --tail=100 }
    "ps"               { docker compose ps }
    "migrate"          { docker compose run --rm migrate }
    "accept"           { & "$PSScriptRoot\acceptance.ps1" }
    "accept-dev-auth"  { $env:COMPOSE_DEV_AUTH = "1"; try { & "$PSScriptRoot\acceptance.ps1" } finally { Remove-Item Env:\COMPOSE_DEV_AUTH } }
    "backend-install"  { Push-Location backend; uv sync --all-extras; Pop-Location }
    "backend-dev"      { Push-Location backend; uv run uvicorn entropia.apps.api.main:app --reload --port 8000; Pop-Location }
    "backend-test"     { Push-Location backend; uv run pytest; Pop-Location }
    "backend-lint"     { Push-Location backend; uv run ruff check .; uv run mypy src; Pop-Location }
    "frontend-install" { Push-Location frontend; npm install; Pop-Location }
    "frontend-dev"     { Push-Location frontend; npm run dev; Pop-Location }
    "frontend-build"   { Push-Location frontend; npm run build; Pop-Location }
    "frontend-lint"    { Push-Location frontend; npm run lint; npm run typecheck; Pop-Location }
    "test"             {
        # Fail-fast mirror of `make test` (TEST-11): backend THEN frontend, and
        # the whole task fails if EITHER suite fails (no swallowed exit codes).
        Push-Location backend; uv run pytest; $backend = $LASTEXITCODE; Pop-Location
        if ($backend -ne 0) { Write-Error "backend tests failed (exit $backend)"; exit $backend }
        Push-Location frontend; npm test --silent; $frontend = $LASTEXITCODE; Pop-Location
        if ($frontend -ne 0) { Write-Error "frontend tests failed (exit $frontend)"; exit $frontend }
    }
    "nuke"             { docker compose down -v }
    default            { Write-Error "Unknown task '$Task'. Run '.\scripts\tasks.ps1 help'." }
}
