# Download only during build. Customers receive an offline, verified payload.
[CmdletBinding()]
param([string]$Destination = "$PSScriptRoot\..\build\prerequisites", [switch]$Windows81)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$file = Join-Path $Destination 'vc_redist.x64.exe'
$manifestPath = Join-Path $Destination 'runtime.json'
if (-not (Test-Path -LiteralPath $file)) {
    $vcSource = if ($Windows81) { 'https://aka.ms/vs/16/release/vc_redist.x64.exe' } else { 'https://aka.ms/vc14/vc_redist.x64.exe' }
    Invoke-WebRequest -Uri $vcSource -OutFile $file -UseBasicParsing
}
$signature = Get-AuthenticodeSignature -LiteralPath $file
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation(?:,|$)') { throw 'Microsoft runtime signature is invalid; build stopped.' }
$info = (Get-Item -LiteralPath $file).VersionInfo
$version = '{0}.{1}.{2}.{3}' -f $info.FileMajorPart,$info.FileMinorPart,$info.FileBuildPart,$info.FilePrivatePart
if ($Windows81 -and -not $version.StartsWith('14.29.')) { throw 'Windows 8.1 requires the reviewed VC 2019 runtime.' }
$hash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash
if (Test-Path -LiteralPath $manifestPath) {
    $pinned = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($pinned.sha256 -ne $hash -or $pinned.version -ne $version) { throw 'Runtime differs from pinned build manifest. Review the new Microsoft payload before updating the manifest.' }
} else {
    @{version=$version;sha256=$hash;source='https://aka.ms/vc14/vc_redist.x64.exe'} | ConvertTo-Json | Set-Content -LiteralPath $manifestPath -Encoding UTF8
}
Write-Output "Verified Microsoft VC runtime x64 $version SHA256=$hash"

$dotnetSource = 'https://go.microsoft.com/fwlink/?linkid=2088631'
$dotnetFile = Join-Path $Destination 'dotnet48.exe'
$dotnetManifest = Join-Path $Destination 'dotnet.json'
if (-not (Test-Path -LiteralPath $dotnetFile)) { Invoke-WebRequest -Uri $dotnetSource -OutFile $dotnetFile -UseBasicParsing }
$signature = Get-AuthenticodeSignature -LiteralPath $dotnetFile
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation(?:,|$)') { throw 'Microsoft .NET signature is invalid.' }
$hash = (Get-FileHash -LiteralPath $dotnetFile -Algorithm SHA256).Hash
if (Test-Path -LiteralPath $dotnetManifest) {
    $pinned = Get-Content -LiteralPath $dotnetManifest -Raw | ConvertFrom-Json
    if ($pinned.sha256 -ne $hash) { throw '.NET payload differs from reviewed manifest.' }
} else {
    @{version='4.8';sha256=$hash;source=$dotnetSource} | ConvertTo-Json | Set-Content -LiteralPath $dotnetManifest -Encoding UTF8
}
Write-Output "Verified Microsoft .NET Framework 4.8 SHA256=$hash"
