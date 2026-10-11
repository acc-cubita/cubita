[CmdletBinding()]
param([string]$ServerPath, [ValidateSet('install','network-resume')][string]$Action, [string]$LogPath)
$ErrorActionPreference = 'Stop'
try {
    if ([IO.Path]::GetFileName($ServerPath) -ne 'cubita-server.exe') { throw 'Unexpected server executable.' }
    Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value ((Get-Date).ToUniversalTime().ToString('o') + ' server begin=' + $Action)
    # Capture native stdout/stderr without interpreting it as commands or losing a nonzero exit.
    if (-not (Test-Path -LiteralPath $ServerPath -PathType Leaf)) { throw 'Packaged server executable missing.' }
    $global:LASTEXITCODE = 2
    $ErrorActionPreference = 'Continue'
    & $ServerPath $Action 2>&1 | ForEach-Object { Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value ([string]$_) }
    $code = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value ((Get-Date).ToUniversalTime().ToString('o') + ' server exit=' + $code)
    exit $code
} catch {
    try { Add-Content -LiteralPath $LogPath -Encoding UTF8 -Value ('server FAILED: ' + $_.Exception.ToString()) } catch {}
    exit 2
}
