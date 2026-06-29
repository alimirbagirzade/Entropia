# Entropia V18 — one-time local bootstrap (Windows / PowerShell).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

function Say($m) { Write-Host "▸ $m" -ForegroundColor Cyan }

if (-not (Test-Path ".env")) {
    Say "Creating .env from .env.example"
    Copy-Item ".env.example" ".env"
} else {
    Say ".env already exists — leaving it untouched"
}

if (Get-Command uv -ErrorAction SilentlyContinue) {
    Say "Installing backend dependencies (uv sync)"
    Push-Location backend; uv sync --all-extras; Pop-Location
} else {
    Write-Warning "'uv' not found. Install from https://docs.astral.sh/uv/ then re-run."
}

if (Get-Command npm -ErrorAction SilentlyContinue) {
    Say "Installing frontend dependencies (npm install)"
    Push-Location frontend; npm install; Pop-Location
} else {
    Write-Warning "'npm' not found. Install Node.js 20+ then re-run."
}

Say "Bootstrap complete. Next: '.\scripts\tasks.ps1 up' (full stack)."
