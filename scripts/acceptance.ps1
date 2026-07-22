# =============================================================================
# Entropia — acceptance state gate (DEP-05), PowerShell mirror of acceptance.sh.
#
# Proves every long-running plane is up and NO Compose service has
# exited/restarted/become unhealthy. Run against an ALREADY-RUNNING stack
# (bring it up with `.\scripts\tasks.ps1 up` or `up-dev-auth` first):
#
#   .\scripts\acceptance.ps1                       # session stack
#   $env:COMPOSE_DEV_AUTH=1; .\scripts\acceptance.ps1   # dev-auth stack
#
# Exit code: 0 = all planes healthy, 1 = a plane exited/restarted/unhealthy.
# =============================================================================
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$dc = @("docker", "compose")
if ($env:COMPOSE_DEV_AUTH -eq "1") {
    $dc += @("-f", "docker-compose.yml", "-f", "docker-compose.dev-auth.yml")
    $prof = "dev-auth"
} else {
    $prof = "session"
}

$oneShots = @("minio-setup", "migrate")
$fail = 0

Write-Host "== Acceptance gate ($prof stack) =="

$services = & $dc[0] $dc[1..($dc.Length - 1)] config --services
foreach ($svc in $services) {
    $cid = (& $dc[0] $dc[1..($dc.Length - 1)] ps -aq $svc | Select-Object -First 1)
    if (-not $cid) {
        Write-Host "  FAIL  $svc - no container (never created)"; $fail = 1; continue
    }
    $status   = docker inspect -f '{{.State.Status}}' $cid
    $exitcode = docker inspect -f '{{.State.ExitCode}}' $cid
    $restarts = [int](docker inspect -f '{{.RestartCount}}' $cid)
    $health   = docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $cid

    if ($oneShots -contains $svc) {
        if ($status -eq "exited" -and $exitcode -eq "0") {
            Write-Host "  PASS  $svc - one-shot completed (exit 0)"
        } else {
            Write-Host "  FAIL  $svc - one-shot status=$status exit=$exitcode (want exited/0)"; $fail = 1
        }
        continue
    }

    $problems = @()
    if ($status -ne "running") { $problems += "status=$status" }
    if ($restarts -gt 0)       { $problems += "restarts=$restarts" }
    if ($health -ne "healthy" -and $health -ne "none") { $problems += "health=$health" }

    if ($problems.Count -gt 0) {
        Write-Host ("  FAIL  $svc - " + ($problems -join " ")); $fail = 1
    } else {
        Write-Host "  PASS  $svc - running (health=$health restarts=$restarts)"
    }
}

Write-Host ""
if ($fail -eq 0) {
    Write-Host "ACCEPTANCE OK - every plane is up; nothing exited/restarted/unhealthy."
} else {
    Write-Host "ACCEPTANCE FAILED - see the FAIL lines above."
    & $dc[0] $dc[1..($dc.Length - 1)] ps
}
exit $fail
