# =============================================================================
# scripts/configure-local-session.ps1 (DEP-03) — idempotently switch the local
# .env to the NORMAL session profile (real browser login), touching only the
# auth keys. Safe to re-run; never prints a secret or the bootstrap email.
#
#   .\scripts\configure-local-session.ps1
#   .\scripts\configure-local-session.ps1 -Email you@example.com   # first Admin
# =============================================================================
param([string]$Email = "")
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

function Say($m)  { Write-Host "▸ $m" -ForegroundColor Cyan }
function Warn($m) { Write-Warning $m }

if (-not (Test-Path ".env")) {
    Say "Creating .env from .env.example"
    Copy-Item ".env.example" ".env"
}

. (Join-Path $PSScriptRoot "lib/env-audit.ps1")

$backup = Backup-EnvFile
if ($backup) { Say "Backed up .env -> $backup" }

# Only the auth keys change. AUTH_MODE -> session is idempotent.
Set-EnvKey "AUTH_MODE" "session"
Say "AUTH_MODE=session"

# Bootstrap email is recorded but never echoed (it is a sensitive identifier).
if ($Email) {
    Set-EnvKey "ENTROPIA_BOOTSTRAP_ADMIN_EMAIL" $Email
    Say "Recorded first-Admin bootstrap email (value not shown)."
}

# Session mode requires a non-empty service token; generate one only if empty.
& (Join-Path $PSScriptRoot "ensure-service-token.ps1")

$unresolved = Get-UnresolvedRequired
if ($unresolved.Count -gt 0) {
    Warn "Still-unresolved required keys (set them in .env, values not shown): $($unresolved -join ' ')"
    exit 1
}

Say "Session profile ready. Start the app and Sign Up / Log In in the browser."
