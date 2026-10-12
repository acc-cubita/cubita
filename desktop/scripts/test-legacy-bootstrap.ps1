# No system changes: all installers and OS detection replaced with test doubles.
$ErrorActionPreference='Stop'
. "$PSScriptRoot\..\build\installer-legacy-bootstrap.ps1"
$PayloadDirectory=Join-Path ([IO.Path]::GetTempPath()) ('CubitaBootstrapQA-'+[guid]::NewGuid())
New-Item -ItemType Directory -Path $PayloadDirectory | Out-Null
$LogPath=Join-Path $PayloadDirectory 'bootstrap.log'
function Get-BootstrapBuild {return $script:Build}
function Get-BootstrapPowerShell {return $script:PowerShellMajor}
function Get-BootstrapFramework {return $script:Framework}
function Get-BootstrapIs64 {return $script:Is64}
function Test-BootstrapHash { $script:Verified += [IO.Path]::GetFileName($args[0]); if ($script:Tampered) {throw 'Tampered payload'} }
function Invoke-BootstrapInstaller {
 param([string]$File,[string[]]$Arguments)
 $script:Invoked += [IO.Path]::GetFileName($File)
 if ([IO.Path]::GetFileName($File) -eq 'dotnet48.exe') {$script:Framework=$script:FrameworkAfter;return $script:DotNetExit}
 $script:WmfPath=$Arguments[0];return $script:WmfExit
}
$count=0
foreach ($scenario in @(
 @('Windows10 untouched',19045,5,0,0,0,0,0),
 @('Windows8 untouched',9200,3,378389,0,0,0,0),
 @('PS already sufficient',7601,3,378389,0,0,0,0),
 @('NET reboot',7601,2,0,3010,528040,0,3010),
 @('NET failure',7601,2,0,1603,0,0,-1),
 @('NET success unconfirmed',7601,2,0,0,0,0,-1),
 @('WMF restart',7601,2,378389,0,0,3010,3010),
 @('WMF success requires restart',7601,2,378389,0,0,0,3010),
 @('WMF already installed',7601,2,378389,0,0,2359302,3010),
 @('WMF failed',7601,2,378389,0,0,1603,-1)
)) {
 $script:Build=$scenario[1];$script:PowerShellMajor=$scenario[2];$script:Framework=$scenario[3];$script:DotNetExit=$scenario[4];$script:FrameworkAfter=$scenario[5];$script:WmfExit=$scenario[6]
 $script:Is64=$true;$script:Tampered=$false;$script:Invoked=@();$script:Verified=@()
 try {$result=Install-LegacyBootstrap}catch{$result=-1}
 if ($result -ne $scenario[7]) {throw ('FAILED '+$scenario[0]+' actual='+$result)}
 if ($scenario[0] -like '*untouched' -and $script:Invoked.Count -ne 0) {throw 'Unexpected system installer'}
 $count++
}
foreach ($arch in @($true,$false)) {
 $script:Build=7601;$script:PowerShellMajor=2;$script:Framework=378389;$script:WmfExit=0;$script:Is64=$arch;$script:Tampered=$false;$script:Verified=@();$script:Invoked=@()
 $result=Install-LegacyBootstrap
 $expected=if($arch){'wmf-x64.msu'}else{'wmf-x86.msu'}
 if ($script:Verified[0] -ne $expected -or $script:WmfPath -notlike ('*'+$expected+'*')) {throw 'Wrong WMF architecture'}
 $count++
}
$script:Tampered=$true;$script:Invoked=@();$failed=$false
try {Install-LegacyBootstrap}catch{$failed=$true}
if (-not $failed -or $script:Invoked.Count -ne 0) {throw 'Tampered payload executed'}
$count++
Write-Output ('PASS: '+$count+' legacy bootstrap scenarios; all system installers mocked')
