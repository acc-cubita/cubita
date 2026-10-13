# Keep a UTF-8 BOM when packaging for Windows PowerShell 5.
[CmdletBinding()]
param([string]$PayloadDirectory, [string]$LogPath, [ValidateSet('client','server')][string]$Role='client', [ValidateSet('x64','x86')][string]$Architecture='x64', [ValidateRange(3,5)][int]$MinimumPowerShell=4, [int]$MinimumFrameworkRelease=394254)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-CubitaPrerequisiteLog([string]$Message) {
    Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value ((Get-Date).ToUniversalTime().ToString('o') + ' prerequisite ' + $Message)
}

function Get-CubitaPayloadHash([string]$File) {
    # Windows8 ships PowerShell3, which has no Get-FileHash.
    $stream = [IO.File]::OpenRead($File)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','') }
    finally { $sha.Dispose(); $stream.Dispose() }
}

function Get-CubitaRuntimeVersion {
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', $(if ($Architecture -eq 'x86') { 'Registry32' } else { 'Registry64' }))
    try {
        $key = $base.OpenSubKey(('SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\' + $Architecture))
        if (-not $key) { return [version]'0.0' }
        try {
            if ([int]$key.GetValue('Installed',0) -ne 1) { return [version]'0.0' }
            return [version]([string]$key.GetValue('Version','0.0')).TrimStart('v')
        } finally { $key.Dispose() }
    } finally { $base.Dispose() }
}

function Invoke-CubitaRuntimeInstaller([string]$File) {
    # No download or reboot during installation; the verified payload is embedded.
    $process = Start-Process -FilePath $File -ArgumentList @('/install','/quiet','/norestart','/log',('"' + $LogPath + '.vc.log"')) -WindowStyle Hidden -Wait -PassThru
    return $process.ExitCode
}

function Install-CubitaVcRuntime {
    Write-CubitaPrerequisiteLog ('start; PowerShell=' + $PSVersionTable.PSVersion + '; OS64=' + [Environment]::Is64BitOperatingSystem)
    if (($Architecture -eq 'x64' -and -not [Environment]::Is64BitOperatingSystem) -or $PSVersionTable.PSVersion.Major -lt $MinimumPowerShell) {
        throw ('The selected architecture requires Windows PowerShell ' + $MinimumPowerShell + ' or later and a matching Windows architecture.')
    }
    $manifest = Get-Content -LiteralPath (Join-Path $PayloadDirectory 'runtime.json') -Raw | ConvertFrom-Json
    $file = Join-Path $PayloadDirectory ('vc_redist.' + $Architecture + '.exe')
    $expected = [version]$manifest.version
    $installed = Get-CubitaRuntimeVersion
    Write-CubitaPrerequisiteLog (('VC ' + $Architecture + ' installed=') + $installed + '; packaged=' + $expected)
    if ($installed -ge $expected) {
        Write-CubitaPrerequisiteLog 'runtime already sufficient; no installation'
        return 0
    }
    if ((Get-CubitaPayloadHash $file) -ne $manifest.sha256) { throw 'Runtime payload SHA256 mismatch.' }
    # Publisher signature is checked at build time; the embedded SHA256 permits offline installs.
    $code = Invoke-CubitaRuntimeInstaller $file
    Write-CubitaPrerequisiteLog ('VC installer exit=' + $code)
    if ($code -eq 3010 -or $code -eq 1641) { return 3010 }
    # A concurrently installed newer runtime may return 1638; verify registry again.
    if ($code -ne 0 -and $code -ne 1638) { throw ('VC runtime installation failed; exit=' + $code) }
    $after = Get-CubitaRuntimeVersion
    if ($after -lt $expected) { throw ('VC runtime version was not confirmed after installation: ' + $after) }
    Write-CubitaPrerequisiteLog (('completed; VC ' + $Architecture + '=') + $after)
    return 0
}

function Get-CubitaFrameworkRelease {
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', $(if ($Architecture -eq 'x86') { 'Registry32' } else { 'Registry64' }))
    try {
        $key = $base.OpenSubKey('SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full')
        if (-not $key) { return 0 }
        try { return [int]$key.GetValue('Release',0) } finally { $key.Dispose() }
    } finally { $base.Dispose() }
}

function Invoke-CubitaFrameworkInstaller([string]$File) {
    $process = Start-Process -FilePath $File -ArgumentList @('/q','/norestart','/log',('"' + $LogPath + '.dotnet.log"')) -WindowStyle Hidden -Wait -PassThru
    return $process.ExitCode
}

function Install-CubitaFramework {
    $release = Get-CubitaFrameworkRelease
    Write-CubitaPrerequisiteLog ('server .NET release=' + $release)
    # WinSW v2 requires 4.6.1 or later. Existing newer frameworks are preserved.
    if ($release -ge $MinimumFrameworkRelease) { return 0 }
    $manifest = Get-Content -LiteralPath (Join-Path $PayloadDirectory 'dotnet.json') -Raw | ConvertFrom-Json
    $file = Join-Path $PayloadDirectory 'dotnet48.exe'
    if ((Get-CubitaPayloadHash $file) -ne $manifest.sha256) { throw '.NET payload SHA256 mismatch.' }
    $code = Invoke-CubitaFrameworkInstaller $file
    Write-CubitaPrerequisiteLog ('.NET installer exit=' + $code)
    if ($code -eq 3010 -or $code -eq 1641) { return 3010 }
    if ($code -ne 0) { throw ('.NET installation failed; exit=' + $code) }
    if ((Get-CubitaFrameworkRelease) -lt $MinimumFrameworkRelease) { throw '.NET installation could not be confirmed.' }
    return 0
}

function Install-CubitaPrerequisites {
    $result = Install-CubitaVcRuntime
    if ($result -ne 0) { return $result }
    if ($Role -eq 'server') { return (Install-CubitaFramework) }
    Write-CubitaPrerequisiteLog 'client role; server framework not required'
    return 0
}

if ($MyInvocation.InvocationName -ne '.') {
    try { exit (Install-CubitaPrerequisites) }
    catch {
        try { Write-CubitaPrerequisiteLog ('FAILED; ' + $_.Exception.ToString() + '; ' + $_.ScriptStackTrace) } catch {}
        [Console]::Error.WriteLine('Prerequisite installation failed. See installer log.')
        exit 2
    }
}
