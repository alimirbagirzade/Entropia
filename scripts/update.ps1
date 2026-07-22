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

# 2b. Non-destructive configuration audit + migration (DEP-03). We never echo a
#     secret value, only key names; we back up .env before any mutation; and we
#     refuse to declare success on unresolved required configuration.
. (Join-Path $PSScriptRoot "lib/env-audit.ps1")

$authMode = Get-EnvValue "AUTH_MODE"

# Legacy / ambiguous auth profile — require an EXPLICIT, acknowledged choice
# rather than silently accepting or silently changing an intentional setup.
if (-not $authMode) {
    Warn "AUTH_MODE is not set in .env — choose a profile before updating:"
    Warn "  * normal browser login:  .\scripts\configure-local-session.ps1"
    Warn "  * local dev impersonation: set AUTH_MODE=dev in .env, re-run with ENTROPIA_ALLOW_DEV_AUTH=1"
    exit 1
} elseif ($authMode -eq "dev" -and $env:ENTROPIA_ALLOW_DEV_AUTH -ne "1") {
    Warn "AUTH_MODE=dev detected — local X-Actor-Id impersonation, no login."
    Warn "This is a deliberate developer profile; update will not change it silently."
    Warn "  * keep dev impersonation:  re-run with ENTROPIA_ALLOW_DEV_AUTH=1"
    Warn "  * switch to session login: .\scripts\configure-local-session.ps1"
    exit 1
} elseif ($authMode -ne "dev" -and $authMode -ne "session") {
    Warn "AUTH_MODE=$authMode is not a valid profile (expected 'session' or 'dev')."
    exit 1
}

# Back up .env once, then migrate — but only if there is actually something to
# change (missing safe keys, or a session profile with no service token yet).
$needsToken = ($authMode -eq "session") -and (-not (Test-EnvHas "ENTROPIA_SERVICE_TOKEN"))
$missingKeys = Get-MissingExampleKeys ".env.example"
if ($missingKeys.Count -gt 0 -or $needsToken) {
    $backup = Backup-EnvFile
    if ($backup) { Say "Backed up .env -> $backup" }
    $added = Add-MissingExampleKeys ".env.example"
    if ($added.Count -gt 0) { Say "Added missing non-secret keys: $($added -join ' ')" }
    # Session mode needs a service-line credential for the non-human runtimes; this
    # only fills an EMPTY value — an existing token is never rotated by an update.
    if ($needsToken) { & (Join-Path $PSScriptRoot "ensure-service-token.ps1") }
}

# Refuse to proceed on unresolved required configuration (values never shown).
$unresolved = Get-UnresolvedRequired
if ($unresolved.Count -gt 0) {
    Warn "Unresolved required configuration (set these in .env, values not shown): $($unresolved -join ' ')"
    Warn "Update aborted — fix the keys above and re-run. (No changes were applied beyond the .env backup.)"
    exit 1
}
if ($authMode -eq "dev") { Say "Auth profile: dev (local impersonation, acknowledged)." }
else { Say "Auth profile: session (browser login)." }

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
