# Ensure .env carries a non-empty ENTROPIA_SERVICE_TOKEN (Windows / PowerShell).
#
# Session mode is the normal local profile, and in session mode the non-human
# runtimes (agent, scheduler, coordinator, every worker) authenticate with this
# static service token plus their own X-Actor-Id. An empty value disables the
# service line, so those runtimes silently lose their identity.
#
# The value is generated locally into the git-ignored .env and never committed.
# An existing non-empty value is ALWAYS left untouched — this script must be safe
# to re-run from update.ps1 without rotating a working deployment's secret.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

function Say($m) { Write-Host "▸ $m" -ForegroundColor Cyan }

if (-not (Test-Path ".env")) {
    Say "No .env yet — skipping service-token check"
    exit 0
}

$lines = Get-Content ".env"
if ($lines | Where-Object { $_ -match '^ENTROPIA_SERVICE_TOKEN=.+$' }) {
    Say "ENTROPIA_SERVICE_TOKEN already set — leaving it untouched"
    exit 0
}

$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$token = -join ($bytes | ForEach-Object { $_.ToString("x2") })

if ($lines | Where-Object { $_ -match '^ENTROPIA_SERVICE_TOKEN=' }) {
    $lines = $lines | ForEach-Object {
        if ($_ -match '^ENTROPIA_SERVICE_TOKEN=') { "ENTROPIA_SERVICE_TOKEN=$token" } else { $_ }
    }
} else {
    $lines += "ENTROPIA_SERVICE_TOKEN=$token"
}
Set-Content ".env" $lines
Say "Generated ENTROPIA_SERVICE_TOKEN into .env (git-ignored — never commit it)"
