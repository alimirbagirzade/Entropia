# =============================================================================
# scripts/lib/env-audit.ps1 — shared, non-destructive .env inspection/migration
# helpers (Windows / PowerShell). Dot-sourced by update.ps1 and
# configure-local-session.ps1. DEP-03: never prints a secret VALUE, only key
# NAMES; every mutation is idempotent and backup-guarded by the caller.
# =============================================================================

# The file every helper reads/writes. Callers may override before dot-sourcing.
if (-not $script:EnvFile) { $script:EnvFile = ".env" }

# Keys that must be present AND non-empty for any coherent local run.
$script:EnvRequiredAlways  = @("ENTROPIA_ENV", "AUTH_MODE", "DATABASE_URL")
# Additionally required (non-empty) only under AUTH_MODE=session.
$script:EnvRequiredSession = @("ENTROPIA_SERVICE_TOKEN")
# Sensitive keys: never auto-filled from the example, values never printed.
$script:EnvSecretKeys = @(
    "POSTGRES_PASSWORD", "OBJECT_STORAGE_ACCESS_KEY", "OBJECT_STORAGE_SECRET_KEY",
    "ENTROPIA_SERVICE_TOKEN", "ENTROPIA_BOOTSTRAP_ADMIN_EMAIL"
)

# Echo KEY's raw value ($null if absent). Callers MUST NOT print it for secrets.
function Get-EnvValue([string]$Key) {
    if (-not (Test-Path $script:EnvFile)) { return $null }
    foreach ($l in Get-Content $script:EnvFile) {
        if ($l -match ("^" + [regex]::Escape($Key) + "=(.*)$")) { return $Matches[1] }
    }
    return $null
}

# True if KEY has a non-empty value.
function Test-EnvHas([string]$Key) {
    $v = Get-EnvValue $Key
    return ($null -ne $v -and $v -ne "")
}

# True if a line for KEY exists at all (even KEY= with an empty value).
function Test-EnvLine([string]$Key) {
    if (-not (Test-Path $script:EnvFile)) { return $false }
    return [bool](Get-Content $script:EnvFile |
        Where-Object { $_ -match ("^" + [regex]::Escape($Key) + "=") } |
        Select-Object -First 1)
}

# True if KEY is sensitive (excluded from example backfill + logging).
function Test-EnvSecret([string]$Key) { return ($script:EnvSecretKeys -contains $Key) }

# Idempotently set KEY=VALUE: replace an existing line or append. Never prints
# VALUE. Every other line is preserved verbatim.
function Set-EnvKey([string]$Key, [string]$Value) {
    $lines = @()
    if (Test-Path $script:EnvFile) { $lines = @(Get-Content $script:EnvFile) }
    $found = $false
    $out = foreach ($l in $lines) {
        if ($l -match ("^" + [regex]::Escape($Key) + "=")) { $found = $true; "$Key=$Value" }
        else { $l }
    }
    if (-not $found) { $out = @($out) + "$Key=$Value" }
    Set-Content -Path $script:EnvFile -Value $out
}

# Timestamped backup of .env. Returns the backup PATH (never contents); returns
# "" when there is no .env yet.
function Backup-EnvFile {
    if (-not (Test-Path $script:EnvFile)) { return "" }
    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    $dst = "$($script:EnvFile).bak.$ts"; $n = 1
    while (Test-Path $dst) { $dst = "$($script:EnvFile).bak.$ts.$n"; $n++ }
    Copy-Item $script:EnvFile $dst
    return $dst
}

# Return the non-secret keys present in the example but missing from .env — the
# safe backfill set. Names only, no values, no mutation.
function Get-MissingExampleKeys([string]$Example = ".env.example") {
    if (-not (Test-Path $Example)) { return @() }
    $out = @()
    foreach ($l in Get-Content $Example) {
        if ($l -match '^\s*#') { continue }
        if ($l -notmatch '^([^=]+)=') { continue }
        $key = $Matches[1]
        if (Test-EnvSecret $key) { continue }
        if (Test-EnvLine $key) { continue }
        $out += $key
    }
    return $out
}

# Append every safe missing example key (verbatim example line, comment and all,
# matching a fresh copy of .env.example). Returns the appended NAMES. The caller
# is responsible for taking a Backup-EnvFile first.
function Add-MissingExampleKeys([string]$Example = ".env.example") {
    $added = @()
    foreach ($key in (Get-MissingExampleKeys $Example)) {
        $line = Get-Content $Example |
            Where-Object { $_ -match ("^" + [regex]::Escape($key) + "=") } |
            Select-Object -First 1
        if ($line) { Add-Content -Path $script:EnvFile -Value $line; $added += $key }
    }
    return $added
}

# Return the unresolved required keys for the .env's own AUTH_MODE. Empty = the
# configuration is complete. Names only.
function Get-UnresolvedRequired {
    $mode = Get-EnvValue "AUTH_MODE"
    $missing = @()
    foreach ($k in $script:EnvRequiredAlways) { if (-not (Test-EnvHas $k)) { $missing += $k } }
    if ($mode -eq "session") {
        foreach ($k in $script:EnvRequiredSession) { if (-not (Test-EnvHas $k)) { $missing += $k } }
    }
    return $missing
}
