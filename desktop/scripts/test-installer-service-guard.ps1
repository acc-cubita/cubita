# All OS operations are replaced before invoking the production guard.
# No Windows service, process, scheduled task, network, or financial data is changed.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. "$PSScriptRoot\..\build\installer-service-guard.ps1"

$script:Passed = 0
function Assert-Guard($Condition, [string]$Label) {
    if (-not $Condition) { throw "FAILED: $Label" }
    $script:Passed++
}
function Assert-GuardThrows([scriptblock]$Action, [string]$Label) {
    $thrown = $false
    try { $null = & $Action } catch { $thrown = $true }
    Assert-Guard $thrown $Label
}
function New-FakeService([string]$Name, [string]$Status) {
    $service = [pscustomobject]@{ Name = $Name; Status = $Status }
    $service | Add-Member ScriptMethod WaitForStatus {
        param($Target, $Timeout)
        $null = $script:Calls.Add("wait:$($this.Name):$Target")
        if ($script:Failure -eq 'wait') { throw 'simulated wait failure' }
        if ($Timeout.TotalSeconds -gt 30) { throw 'unbounded wait' }
        $this.Status = [string]$Target
    }
    $service | Add-Member ScriptMethod Start {
        $null = $script:Calls.Add("start:$($this.Name)")
        if ($script:Failure -eq 'start') { throw 'simulated start failure' }
        $this.Status = 'StartPending'
    }
    $service | Add-Member ScriptMethod Stop {
        $null = $script:Calls.Add("stop:$($this.Name)")
        if ($script:Failure -eq 'stop') { throw 'simulated stop failure' }
        $this.Status = 'StopPending'
    }
    return $service
}
function Reset-Fakes {
    $script:Failure = ''
    $script:Calls = [Collections.Generic.List[string]]::new()
    $script:Services = @(
        (New-FakeService 'CubitaApi' 'Running'),
        (New-FakeService 'CubitaPostgres' 'Running')
    )
    $script:Tasks = @([pscustomobject]@{
        TaskName = 'CubitaEnterpriseNetwork'; TaskPath = '\';
        Settings = [pscustomobject]@{ Enabled = $true }
    })
    $script:Processes = @()
    $script:AppPath = 'C:\QA\Cubita Enterprise\Cubita Enterprise.exe'
}

function Get-Service {
    [CmdletBinding()] param()
    if ($script:Failure -eq 'service-query') { throw 'simulated access failure' }
    $script:Services
}
function Get-ScheduledTask {
    [CmdletBinding()] param()
    if ($script:Failure -eq 'task-query') { throw 'simulated access failure' }
    $script:Tasks
}
function Disable-ScheduledTask {
    param([Parameter(ValueFromPipeline)]$InputObject)
    process {
        $null = $script:Calls.Add('disable-task')
        $InputObject.Settings.Enabled = $false
        if ($script:Failure -eq 'disable-task') { throw 'simulated partial disable' }
        $InputObject
    }
}
function Stop-ScheduledTask {
    param([Parameter(ValueFromPipeline)]$InputObject)
    process {
        $null = $script:Calls.Add('stop-task')
        if ($script:Failure -eq 'stop-task') { throw 'simulated task stop failure' }
    }
}
function Enable-ScheduledTask {
    param([Parameter(ValueFromPipeline)]$InputObject)
    process {
        $null = $script:Calls.Add('enable-task')
        $InputObject.Settings.Enabled = $true
        $InputObject
    }
}
function Get-CimInstance {
    param($ClassName, $Filter)
    if ($ClassName -ne 'Win32_Process' -or $Filter -ne "Name='Cubita Enterprise.exe'") {
        throw 'unsafe/unexpected process query'
    }
    $script:Processes | Where-Object { $_.Name -eq 'Cubita Enterprise.exe' }
}
function Get-Process {
    [CmdletBinding()] param($Id)
    $process = [pscustomobject]@{ Id = $Id }
    $process | Add-Member ScriptMethod CloseMainWindow {
        $null = $script:Calls.Add("close:$($this.Id)")
        $script:Processes = @($script:Processes | Where-Object { $_.ProcessId -ne $this.Id })
        return $true
    }
    $process
}
function Stop-Process {
    [CmdletBinding()] param($Id, [switch]$Force)
    $null = $script:Calls.Add("kill:$Id")
    $script:Processes = @($script:Processes | Where-Object { $_.ProcessId -ne $Id })
}
# A future unintended fallback must fail this test, not reach the real OS.
function Start-Service { throw 'Real service command forbidden in unit tests' }
function Stop-Service { throw 'Real service command forbidden in unit tests' }

Reset-Fakes
foreach ($action in @('api-state', 'pg-state', 'network-state')) {
    Assert-Guard ((Invoke-CubitaInstallerAction $action $script:AppPath) -eq 7) "${action}: running"
}
Assert-Guard ($script:Calls.Count -eq 0) 'state queries do not mutate'

foreach ($state in @('Stopped', 'StartPending', 'StopPending', 'Paused')) {
    Reset-Fakes
    $script:Services[0].Status = $state
    if ($state -eq 'Paused') {
        Assert-GuardThrows { Invoke-CubitaInstallerAction 'api-state' $script:AppPath } 'paused rejected'
    } else {
        $expected = if ($state -eq 'StartPending') { 7 } else { 8 }
        Assert-Guard ((Invoke-CubitaInstallerAction 'api-state' $script:AppPath) -eq $expected) "state $state"
    }
}

foreach ($name in @('api', 'pg')) {
    Reset-Fakes
    $service = if ($name -eq 'api') { $script:Services[0] } else { $script:Services[1] }
    $null = Invoke-CubitaInstallerAction "stop-$name" $script:AppPath
    Assert-Guard ($service.Status -eq 'Stopped') "stop $name waits for stopped"
    $null = Invoke-CubitaInstallerAction "start-$name" $script:AppPath
    Assert-Guard ($service.Status -eq 'Running') "start $name waits for running"
    $before = @($script:Calls | Where-Object { $_ -like 'start:*' }).Count
    $null = Invoke-CubitaInstallerAction "start-$name" $script:AppPath
    Assert-Guard (@($script:Calls | Where-Object { $_ -like 'start:*' }).Count -eq $before) "$name running not started twice"
}

Reset-Fakes
$script:Services = @()
Assert-Guard ((Invoke-CubitaInstallerAction 'api-state' $script:AppPath) -eq 0) 'absent api'
Assert-Guard ((Invoke-CubitaInstallerAction 'stop-api' $script:AppPath) -eq 0) 'absent stop is harmless'
Assert-GuardThrows { Invoke-CubitaInstallerAction 'start-api' $script:AppPath } 'absent start rejected'

foreach ($failure in @('service-query', 'wait', 'stop', 'start', 'task-query', 'disable-task', 'stop-task')) {
    Reset-Fakes
    $script:Failure = $failure
    $action = switch ($failure) {
        'wait' { $script:Services[0].Status = 'StartPending'; 'api-state' }
        'stop' { 'stop-api' }
        'start' { $script:Services[0].Status = 'Stopped'; 'start-api' }
        'task-query' { 'network-state' }
        'disable-task' { 'pause-network' }
        'stop-task' { 'pause-network' }
        default { 'api-state' }
    }
    Assert-GuardThrows { Invoke-CubitaInstallerAction $action $script:AppPath } "failure $failure propagated"
}

Reset-Fakes
$null = Invoke-CubitaInstallerAction 'pause-network' $script:AppPath
Assert-Guard (-not $script:Tasks[0].Settings.Enabled) 'task disabled before stop'
Assert-Guard (($script:Calls -join ',') -eq 'disable-task,stop-task') 'task pause ordering'
$null = Invoke-CubitaInstallerAction 'resume-network' $script:AppPath
Assert-Guard $script:Tasks[0].Settings.Enabled 'task restored'

Reset-Fakes
$script:Tasks[0].Settings.Enabled = $false
Assert-Guard ((Invoke-CubitaInstallerAction 'network-state' $script:AppPath) -eq 8) 'disabled task distinct from absent'
$script:Tasks[0].TaskPath = '\another-folder\'
$null = Invoke-CubitaInstallerAction 'pause-network' $script:AppPath
Assert-Guard ($script:Calls.Count -eq 0) 'unrelated task folder left alone'

Reset-Fakes
$script:Processes = @(
    [pscustomobject]@{ Name = 'Cubita Enterprise.exe'; ExecutablePath = $script:AppPath; ProcessId = 101 },
    [pscustomobject]@{ Name = 'Cubita Enterprise.exe'; ExecutablePath = 'C:\Other\Cubita Enterprise.exe'; ProcessId = 102 },
    [pscustomobject]@{ Name = 'postgres.exe'; ExecutablePath = 'C:\QA\Cubita Enterprise\resources\server\pgsql\bin\postgres.exe'; ProcessId = 103 },
    [pscustomobject]@{ Name = 'Cubita Enterprise.exe'; ExecutablePath = $null; ProcessId = 104 }
)
Assert-Guard ((Invoke-CubitaInstallerAction 'app-running' $script:AppPath) -eq 7) 'exact app found'
$null = Invoke-CubitaInstallerAction 'close-app' $script:AppPath
Assert-Guard (($script:Calls -join ',') -eq 'close:101') 'only exact GUI closed'
Assert-Guard ($script:Processes.Count -eq 3) 'postgres and other installation kept'
Assert-Guard ((Invoke-CubitaInstallerAction 'app-running' $script:AppPath) -eq 0) 'other installation not matched'
Assert-GuardThrows { Invoke-CubitaInstallerAction 'close-app' 'C:\QA\postgres.exe' } 'arbitrary exe refused'
Assert-GuardThrows { Invoke-CubitaInstallerAction 'unknown' $script:AppPath } 'unknown operation refused'

function Set-CubitaRecoveryBlocked([bool]$Blocked) {
    $prior = $script:Blocked
    $script:Blocked = [int]$Blocked
    return $prior
}
$script:Blocked = 0
Assert-Guard ((Invoke-CubitaInstallerAction 'maintenance-begin' $script:AppPath) -eq 0) 'first maintenance begin'
Assert-Guard ($script:Blocked -eq 1) 'automatic recovery blocked'
Assert-Guard ((Invoke-CubitaInstallerAction 'maintenance-begin' $script:AppPath) -eq 7) 'interrupted maintenance retained'
Assert-Guard ((Invoke-CubitaInstallerAction 'maintenance-end' $script:AppPath) -eq 0) 'verified install releases recovery'
Assert-Guard ($script:Blocked -eq 0) 'automatic recovery enabled'
Write-Output "PASS: $script:Passed installer guard assertions; all OS commands mocked."
