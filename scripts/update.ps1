# Entropia V18 — pull latest + update deps + migrate DB (Docker-free).
# Run this on any machine to bring your local checkout up to date:
#   .\scripts\update.ps1     (or: .\scripts\tasks.ps1 update)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

function Say($m)  { Write-Host "▸ $m" -ForegroundColor Cyan }
function Warn($m) { Write-Warning $m }

# 1. Latest code — fast-forward only, so your local commits are never rewritten.
Say "Fetching latest code (git pull --ff-only)"
git pull --ff-only
if ($LASTEXITCODE -ne 0) {
    Warn "git pull failed. Commit or stash local changes (or resolve conflicts), then re-run."
    exit 1
}

# 2. Ensure .env exists — never overwrite an existing one (it holds your secrets).
if (-not (Test-Path ".env")) {
    Say "Creating .env from .env.example"
    Copy-Item ".env.example" ".env"
    Warn "New .env created. For a Docker-free run, set hosts to 'localhost' (see README)."
}

# 3. Backend dependencies + 4. database migrations.
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Say "Updating backend dependencies (uv sync)"
    Push-Location backend; uv sync --all-extras; Pop-Location

    Say "Applying database migrations (alembic upgrade head)"
    Push-Location backend; uv run alembic upgrade head; $mig = $LASTEXITCODE; Pop-Location
    if ($mig -ne 0) {
        Warn "Migration failed — is PostgreSQL running and DATABASE_URL correct?"
        exit 1
    }
} else {
    Warn "'uv' not found — skipping backend. Install from https://docs.astral.sh/uv/ then re-run."
}

# 5. Frontend dependencies (only needed for the web UI).
if (Get-Command npm -ErrorAction SilentlyContinue) {
    Say "Updating frontend dependencies (npm install)"
    Push-Location frontend; npm install; Pop-Location
} else {
    Warn "'npm' not found — skipping frontend deps (only needed for the web UI)."
}

Say "Update complete. Restart the API / workers to pick up the changes."
