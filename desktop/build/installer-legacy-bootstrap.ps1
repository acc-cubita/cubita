# PowerShell2-compatible entry point. It runs before app files, services, and PowerShell3 helpers.
[CmdletBinding()]
param([string]$PayloadDirectory,[string]$LogPath,[string]$DotNetSha256,[string]$WmfX64Sha256,[string]$WmfX86Sha256)
$ErrorActionPreference='Stop'
function Write-BootstrapLog([string]$Message) {
    Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value ((Get-Date).ToUniversalTime().ToString('o')+' bootstrap '+$Message)
}
function Get-BootstrapBuild {
    return [int](Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').CurrentBuildNumber
}
function Get-BootstrapFramework {
    $key=Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -ErrorAction SilentlyContinue
    if ($key -and $key.PSObject.Properties['Release']) { return [int]$key.Release }
    return 0
}
function Get-BootstrapPowerShell { return $PSVersionTable.PSVersion.Major }
function Get-BootstrapIs64 { return ($env:PROCESSOR_ARCHITECTURE -eq 'AMD64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'AMD64') }
function Test-BootstrapHash([string]$File,[string]$Expected) {
    if ($Expected -notmatch '^[0-9A-Fa-f]{64}$') { throw 'Expected prerequisite hash is missing.' }
    $stream=[IO.File]::OpenRead($File);$sha=[Security.Cryptography.SHA256]::Create()
    try { $actual=[BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','') }
    finally { $sha.Dispose();$stream.Close() }
    if ($actual -ne $Expected) { throw ('Prerequisite SHA256 mismatch: '+[IO.Path]::GetFileName($File)) }
}
function Invoke-BootstrapInstaller([string]$File,[string[]]$Arguments) {
    return (Start-Process -FilePath $File -ArgumentList $Arguments -WindowStyle Hidden -Wait -PassThru).ExitCode
}
function Install-LegacyBootstrap {
    $build=Get-BootstrapBuild
    Write-BootstrapLog ('build='+$build+'; PowerShell='+$PSVersionTable.PSVersion)
    if ($build -ne 7601) { Write-BootstrapLog 'Windows7 bootstrap not needed';return 0 }
    if ((Get-BootstrapPowerShell) -ge 3) { Write-BootstrapLog 'PowerShell already sufficient';return 0 }
    if ((Get-BootstrapFramework) -lt 378389) {
        $file=Join-Path $PayloadDirectory 'dotnet48.exe'
        Test-BootstrapHash $file $DotNetSha256
        $code=Invoke-BootstrapInstaller $file @('/q','/norestart','/log',('"'+$LogPath+'.dotnet-bootstrap.log"'))
        Write-BootstrapLog ('.NET exit='+$code)
        if ($code -eq 3010 -or $code -eq 1641) {return 3010}
        if ($code -ne 0) {throw ('.NET bootstrap failed; exit='+$code)}
        if ((Get-BootstrapFramework) -lt 378389) {throw '.NET bootstrap success could not be confirmed.'}
    }
    if (Get-BootstrapIs64) { $name='wmf-x64.msu';$expected=$WmfX64Sha256 } else { $name='wmf-x86.msu';$expected=$WmfX86Sha256 }
    $file=Join-Path $PayloadDirectory $name
    Test-BootstrapHash $file $expected
    $wusa=Join-Path $env:windir 'System32\wusa.exe'
    if ($env:PROCESSOR_ARCHITEW6432 -eq 'AMD64') {$wusa=Join-Path $env:windir 'Sysnative\wusa.exe'}
    $code=Invoke-BootstrapInstaller $wusa @(('"'+$file+'"'),'/quiet','/norestart')
    Write-BootstrapLog ('WMF exit='+$code+'; OS64='+(Get-BootstrapIs64))
    if ($code -eq 0 -or $code -eq 3010 -or $code -eq 1641 -or $code -eq 2359302) {
        # The current PS2 process cannot become PS5. Stop before touching the installation.
        Write-BootstrapLog 'Restart Windows and run the installer again before changing app files or services'
        return 3010
    }
    throw ('Windows PowerShell bootstrap failed; exit='+$code)
}
if ($MyInvocation.InvocationName -ne '.') {
    try {exit (Install-LegacyBootstrap)}
    catch {try {Write-BootstrapLog ('FAILED '+$_.Exception.ToString())}catch{};[Console]::Error.WriteLine('Bootstrap failed. See installer log.');exit 2}
}
