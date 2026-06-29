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
          "  up                 Start the full Docker stack",
          "  down               Stop the stack (keep volumes)",
          "  restart            Rebuild and restart the stack",
          "  logs               Tail service logs",
          "  ps                 Stack status",
          "  migrate            Apply DB migrations to head",
          "  backend-install    uv sync backend deps",
          "  backend-dev        Run API with reload",
          "  backend-test       Run backend tests",
          "  backend-lint       Ruff + mypy",
          "  frontend-install   npm install",
          "  frontend-dev       Vite dev server",
          "  frontend-build     Production build",
          "  frontend-lint      ESLint + typecheck",
          "  nuke               Stop stack and DELETE volumes"
        ) | ForEach-Object { Write-Host $_ }
    }
    "bootstrap"        { & "$PSScriptRoot\bootstrap.ps1" }
    "up"               { docker compose up -d --build }
    "down"             { docker compose down }
    "restart"          { docker compose down; docker compose up -d --build }
    "logs"             { docker compose logs -f --tail=100 }
    "ps"               { docker compose ps }
    "migrate"          { docker compose run --rm migrate }
    "backend-install"  { Push-Location backend; uv sync --all-extras; Pop-Location }
    "backend-dev"      { Push-Location backend; uv run uvicorn entropia.apps.api.main:app --reload --port 8000; Pop-Location }
    "backend-test"     { Push-Location backend; uv run pytest; Pop-Location }
    "backend-lint"     { Push-Location backend; uv run ruff check .; uv run mypy src; Pop-Location }
    "frontend-install" { Push-Location frontend; npm install; Pop-Location }
    "frontend-dev"     { Push-Location frontend; npm run dev; Pop-Location }
    "frontend-build"   { Push-Location frontend; npm run build; Pop-Location }
    "frontend-lint"    { Push-Location frontend; npm run lint; npm run typecheck; Pop-Location }
    "nuke"             { docker compose down -v }
    default            { Write-Error "Unknown task '$Task'. Run '.\scripts\tasks.ps1 help'." }
}
