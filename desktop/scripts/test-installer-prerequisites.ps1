# Runtime installation is replaced with an in-memory fake. No system changes.
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\build\installer-prerequisites.ps1"
$PayloadDirectory = Join-Path ([IO.Path]::GetTempPath()) ('CubitaPrerequisiteQA-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $PayloadDirectory | Out-Null
$LogPath = Join-Path $PayloadDirectory 'qa.log'
$file = Join-Path $PayloadDirectory 'vc_redist.x64.exe'
[IO.File]::WriteAllText($file,'not an executable - unit test only')
$hash = (Get-FileHash $file -Algorithm SHA256).Hash
@{version='14.50.1.0';sha256=$hash} | ConvertTo-Json | Set-Content (Join-Path $PayloadDirectory 'runtime.json')
function Get-CubitaRuntimeVersion { return $script:Current }
function Get-AuthenticodeSignature { return [pscustomobject]@{Status=$script:Signature;SignerCertificate=[pscustomobject]@{Subject='CN=Microsoft Corporation, O=Microsoft Corporation, C=US'}} }
function Invoke-CubitaRuntimeInstaller { $script:Calls++;$script:Current=$script:After;return $script:ExitCode }
$count=0
foreach ($scenario in @(
    @('already current','14.50.1.0','14.50.1.0',0,0,0),
    @('newer installed','14.60.0.0','14.60.0.0',0,0,0),
    @('missing installed','0.0','14.50.1.0',0,0,1),
    @('older upgraded','14.20.0.0','14.50.1.0',0,0,1),
    @('restart needed','0.0','14.50.1.0',3010,3010,1),
    @('restart signalled','0.0','14.50.1.0',1641,3010,1),
    @('concurrent newer','0.0','14.60.0.0',1638,0,1),
    @('failed installation','0.0','0.0',1603,-1,1),
    @('success unconfirmed','0.0','0.0',0,-1,1)
)) {
    $script:Current=[version]$scenario[1];$script:After=[version]$scenario[2];$script:ExitCode=$scenario[3];$script:Calls=0;$script:Signature='Valid'
    try { $result=Install-CubitaPrerequisites } catch { $result=-1 }
    if ($result -ne $scenario[4] -or $script:Calls -ne $scenario[5]) { throw ('FAILED '+$scenario[0]+': '+$result) }
    $count++
}
foreach ($invalid in @('hash')) {
    $script:Current=[version]'0.0';$script:Calls=0;$script:Signature='UnknownError'
    if ($invalid -eq 'hash') { $script:Signature='Valid';[IO.File]::AppendAllText($file,'tamper') }
    $failed=$false
    try { $null=Install-CubitaPrerequisites } catch { $failed=$true }
    if (-not $failed -or $script:Calls -ne 0) { throw ('Unverified runtime executed: '+$invalid) }
    $count++
}
if (-not (Select-String -LiteralPath $LogPath -Pattern 'exit=1603' -Quiet)) { throw 'Failure code absent from log.' }
$netFile=Join-Path $PayloadDirectory 'dotnet48.exe'
[IO.File]::WriteAllText($netFile,'not executable - framework fixture')
@{sha256=(Get-FileHash $netFile -Algorithm SHA256).Hash} | ConvertTo-Json | Set-Content (Join-Path $PayloadDirectory 'dotnet.json')
function Get-CubitaFrameworkRelease { return $script:Framework }
function Invoke-CubitaFrameworkInstaller { $script:NetCalls++;$script:Framework=$script:NetAfter;return $script:NetExit }
foreach ($scenario in @(
    @('client skips framework','client',0,0,0,0,0),
    @('existing framework','server',394254,394254,0,0,0),
    @('missing framework','server',0,528040,0,0,1),
    @('framework reboot','server',0,528040,3010,3010,1),
    @('framework failed','server',0,0,1603,-1,1),
    @('framework unconfirmed','server',0,0,0,-1,1)
)) {
    $Role=$scenario[1];$script:Framework=$scenario[2];$script:NetAfter=$scenario[3];$script:NetExit=$scenario[4];$script:NetCalls=0
    $script:Current=[version]'14.60.0.0'
    try { $result=Install-CubitaPrerequisites } catch { $result=-1 }
    if ($result -ne $scenario[5] -or $script:NetCalls -ne $scenario[6]) { throw ('FAILED '+$scenario[0]) }
    $count++
}
$Role='server';$script:Framework=0;$script:NetCalls=0
[IO.File]::AppendAllText($netFile,'tampered')
$failed=$false
try { $null=Install-CubitaPrerequisites } catch { $failed=$true }
if (-not $failed -or $script:NetCalls -ne 0) { throw 'Tampered framework executed.' }
$count++
Write-Output "PASS: $count prerequisite scenarios; mocked installers; log=$LogPath"
