# Only the packaged installer calls these fixed-name operations, after UAC.
# Keep the UTF-8 BOM: Windows PowerShell 5.1 otherwise parses Persian as ANSI.
# Dot-sourcing loads the same functions for tests with OS commands replaced.
[CmdletBinding()]
param(
    [ValidateSet('app-running', 'close-app', 'api-state', 'stop-api', 'start-api',
                 'pg-state', 'stop-pg', 'start-pg',
                 'network-state', 'pause-network', 'resume-network',
                 'maintenance-begin', 'maintenance-end')]
    [string]$Action = 'api-state',
    [string]$AppPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-CubitaInstallerAppProcesses([string]$ExpectedPath) {
    # The builder's default directory-prefix match also kills pg_ctl/postgres.
    # Never close a service, a different installation, or an arbitrary exe.
    if ([IO.Path]::GetFileName($ExpectedPath) -ne 'Cubita Enterprise.exe') {
        throw 'مسیر برنامهٔ سازمانی معتبر نیست.'
    }
    $fullPath = [IO.Path]::GetFullPath($ExpectedPath)
    @(Get-CimInstance -ClassName Win32_Process -Filter "Name='Cubita Enterprise.exe'" |
        Where-Object { $_.ExecutablePath -and
            [string]::Equals($_.ExecutablePath, $fullPath, [StringComparison]::OrdinalIgnoreCase) })
}

function Get-CubitaInstallerService([string]$ServiceName) {
    # Listing avoids treating a query/access failure as a missing service.
    if ($ServiceName -notin @('CubitaApi', 'CubitaPostgres')) { throw 'نام سرویس معتبر نیست.' }
    Get-Service -ErrorAction Stop | Where-Object { $_.Name -eq $ServiceName }
}

function Get-CubitaInstallerTask {
    Get-ScheduledTask -ErrorAction Stop |
        Where-Object { $_.TaskName -eq 'CubitaEnterpriseNetwork' -and $_.TaskPath -eq '\' }
}

# `[Type]::new()` below needs PowerShell 5+. Windows 8/8.1 ship PowerShell 3/4 and failed here with the
# misleading "recovery could not be paused" message; installer-os.nsh now refuses Windows < 10 before any
# guard runs, and every Windows 10/11 has PowerShell 5.x.
function Set-CubitaRecoveryBlocked([bool]$Blocked) {
    $name = 'Global\CubitaEnterpriseServiceOperation'
    $rights = [System.Security.AccessControl.MutexRights]1048577
    $mutex = $null
    $held = $false
    try {
        try { $mutex = [System.Threading.Mutex]::OpenExisting($name, $rights) }
        catch [System.Threading.WaitHandleCannotBeOpenedException] {
            $acl = [System.Security.AccessControl.MutexSecurity]::new()
            $acl.SetSecurityDescriptorSddlForm('D:(A;;GA;;;SY)(A;;GA;;;BA)(A;;0x00100001;;;BU)')
            $created = $false
            try { $mutex = [System.Threading.Mutex]::new($false,$name,[ref]$created,$acl) }
            catch [UnauthorizedAccessException] { $mutex = [System.Threading.Mutex]::OpenExisting($name,$rights) }
        }
        try { $held = $mutex.WaitOne([TimeSpan]::FromSeconds(70)) }
        catch [System.Threading.AbandonedMutexException] { $held = $true }
        if(-not $held) { throw 'بازیابی سرویس تمام نشد؛ نصب هنوز شروع نشده است.' }
        # HKLM is protected from ordinary users, including after an interrupted install.
        $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine','Registry64')
        try {
            $key = $base.CreateSubKey('Software\Cubita Enterprise')
            try {
                $prior = [int]$key.GetValue('AutomaticStartBlocked',0)
                $key.SetValue('AutomaticStartBlocked',[int]$Blocked,'DWord')
                return $prior
            } finally { $key.Dispose() }
        } finally { $base.Dispose() }
    } finally {
        if($held) { $mutex.ReleaseMutex() }
        if($mutex) { $mutex.Dispose() }
    }
}

function Invoke-CubitaInstallerAction([string]$Operation, [string]$ExpectedAppPath) {
    switch ($Operation) {
        'maintenance-begin' {
            if((Set-CubitaRecoveryBlocked $true) -ne 0) { return 7 }
        }
        'maintenance-end' { $null = Set-CubitaRecoveryBlocked $false }
        'app-running' {
            if (@(Get-CubitaInstallerAppProcesses $ExpectedAppPath).Count) { return 7 }
        }
        'close-app' {
            foreach ($appProcess in @(Get-CubitaInstallerAppProcesses $ExpectedAppPath)) {
                $process = Get-Process -Id $appProcess.ProcessId -ErrorAction SilentlyContinue
                if ($process) { $null = $process.CloseMainWindow() }
            }
            $deadline = [DateTime]::UtcNow.AddSeconds(5)
            while (@(Get-CubitaInstallerAppProcesses $ExpectedAppPath).Count -and
                   [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 200 }
            # Re-query exact paths after the grace period; never kill by a prefix/name alone.
            foreach ($appProcess in @(Get-CubitaInstallerAppProcesses $ExpectedAppPath)) {
                Stop-Process -Id $appProcess.ProcessId -Force -ErrorAction Stop
            }
            if (@(Get-CubitaInstallerAppProcesses $ExpectedAppPath).Count) {
                throw 'برنامه بسته نشد؛ کارها را ذخیره کنید و برنامه را ببندید.'
            }
        }
        { $_ -in @('api-state', 'pg-state') } {
            $name = if ($Operation -eq 'api-state') { 'CubitaApi' } else { 'CubitaPostgres' }
            $service = Get-CubitaInstallerService $name
            if ($service) {
                if ($service.Status -eq 'StartPending') {
                    $service.WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
                } elseif ($service.Status -eq 'StopPending') {
                    $service.WaitForStatus('Stopped', [TimeSpan]::FromSeconds(30))
                }
                if ($service.Status -eq 'Running') { return 7 }
                if ($service.Status -eq 'Stopped') { return 8 }
                if ($service.Status -ne 'Stopped') { throw 'وضعیت سرویس سرور برای ارتقا مناسب نیست.' }
            }
        }
        { $_ -in @('stop-api', 'stop-pg') } {
            $name = if ($Operation -eq 'stop-api') { 'CubitaApi' } else { 'CubitaPostgres' }
            $service = Get-CubitaInstallerService $name
            if ($service -and $service.Status -ne 'Stopped') {
                # ServiceController returns promptly; the wait below is bounded.
                $service.Stop()
                $service.WaitForStatus('Stopped', [TimeSpan]::FromSeconds(30))
            }
        }
        { $_ -in @('start-api', 'start-pg') } {
            $name = if ($Operation -eq 'start-api') { 'CubitaApi' } else { 'CubitaPostgres' }
            $service = Get-CubitaInstallerService $name
            if (-not $service) { throw 'سرویس سرور موجود نیست؛ نصب سرور را کامل کنید.' }
            if ($service.Status -eq 'StopPending') {
                $service.WaitForStatus('Stopped', [TimeSpan]::FromSeconds(30))
            }
            if ($service.Status -eq 'StartPending') {
                $service.WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
            }
            if ($service.Status -ne 'Running') { $service.Start() }
            $service.WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
        }
        'network-state' {
            $task = Get-CubitaInstallerTask
            if ($task -and $task.Settings.Enabled) { return 7 }
            if ($task) { return 8 }
        }
        'pause-network' {
            $task = Get-CubitaInstallerTask
            if ($task) {
                $task | Disable-ScheduledTask | Out-Null
                $task | Stop-ScheduledTask
            }
        }
        'resume-network' {
            $task = Get-CubitaInstallerTask
            if ($task) { $task | Enable-ScheduledTask | Out-Null }
        }
        default { throw 'عملیات نصاب شناخته‌شده نیست.' }
    }
    return 0
}

if ($MyInvocation.InvocationName -ne '.') {
    try { exit (Invoke-CubitaInstallerAction $Action $AppPath) }
    catch {
        # OS errors can contain paths or configuration; the installer shows a safe, actionable error.
        [Console]::Error.WriteLine('عملیات نصاب انجام نشد؛ وضعیت سرویس‌ها و مجوز مدیر را بررسی کنید.')
        exit 1
    }
}
