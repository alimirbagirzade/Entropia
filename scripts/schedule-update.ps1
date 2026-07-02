# Entropia V18 — install a DAILY auto-update Scheduled Task for THIS checkout.
# The repo path is detected automatically, so there is nothing to edit.
#   .\scripts\schedule-update.ps1 [HH:mm]    # default 09:00 (re-run to change time)
#   .\scripts\schedule-update.ps1 -Remove    # remove the daily task
param(
    [string]$At = "09:00",
    [switch]$Remove
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$taskName = "EntropiaDailyUpdate"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task '$taskName'."
    exit 0
}

$script  = Join-Path $repo "scripts\update.ps1"
$action  = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -NoProfile -File `"$script`"" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Daily -At $At
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Description "Entropia daily Docker-free update ($repo)" -Force | Out-Null

Write-Host "Installed daily Entropia auto-update at $At."
Write-Host "Repo: $repo"
Write-Host "Remove with: .\scripts\schedule-update.ps1 -Remove"
