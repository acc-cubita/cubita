# Embedded ONLY into the NSIS test fixture. Does not invoke any OS command.
param([string]$Action, [string]$AppPath)
$ErrorActionPreference = 'Stop'
$directory = [IO.Path]::GetDirectoryName($AppPath)
$scenario = [IO.Path]::GetFileName($directory)
[IO.File]::AppendAllText((Join-Path $directory 'actions.log'), "$Action`n")
if ($scenario -in @('all-stopped', 'client-over-stopped-services') -and $Action -in @('api-state','pg-state','network-state')) { exit 8 }
if ($scenario -eq 'all-absent' -and $Action -in @('api-state','pg-state','network-state')) { exit 0 }
if ($Action -eq 'app-running') {
    if ($scenario -eq 'app-running') { exit 7 }
    exit 0
}
if($Action -eq 'maintenance-begin') {
    if($scenario -eq 'maintenance-failure') { exit 1 }
    if($scenario -like 'previous-blocked-*') { exit 7 }
}
if (($scenario -eq 'api-query-failure' -and $Action -eq 'api-state') -or
    ($scenario -eq 'pg-query-failure' -and $Action -eq 'pg-state') -or
    ($scenario -eq 'task-query-failure' -and $Action -eq 'network-state') -or
    ($scenario -eq 'pause-failure' -and $Action -eq 'pause-network') -or
    ($scenario -in @('stop-api-failure','previous-blocked-stop-failure') -and $Action -eq 'stop-api') -or
    ($scenario -eq 'stop-pg-failure' -and $Action -eq 'stop-pg')) { exit 1 }
if ($Action -in @('api-state','pg-state','network-state')) { exit 7 }
exit 0
