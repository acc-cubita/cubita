# Exercise the EXACT installer-generated DACL script with an in-memory SCM fake.
# No service/registry/network/file ACL is queried or changed.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Push-Location "$PSScriptRoot\..\..\backend"
try {
    $encoded = & '.\venv\Scripts\python.exe' '-c' 'from app.onprem.services import service_start_permission_command, API_SERVICE; print(service_start_permission_command(API_SERVICE)[-1])'
    if($LASTEXITCODE -ne 0) { throw 'Could not load canonical permission script' }
} finally { Pop-Location }
$code = [Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($encoded.Trim()))
$code = $code.Replace('& "$env:SystemRoot\System32\sc.exe"','Invoke-QaSc')
if($code -match 'sc.exe|Start-Service|Stop-Service|Set-Service|icacls|HKLM:') { throw 'QA must not execute OS operations' }
$block = [ScriptBlock]::Create($code)
$script:Writes = 0
$script:Failure = ''
function Invoke-QaSc([string]$Operation,[string]$Name,[string]$Sddl) {
    if($Name -ne 'CubitaApi') { throw 'Wrong service target' }
    $global:LASTEXITCODE = if($Operation -eq $script:Failure) { 5 } else { 0 }
    if($Operation -eq 'sdshow') { return $script:Sddl }
    if($Operation -eq 'sdset') {
        if($LASTEXITCODE -eq 0) { $script:Writes++; $script:Sddl=$Sddl }
        return
    }
    throw 'Unexpected SCM operation'
}
function Assert-True($Value,[string]$Label) { if(-not $Value) { throw "FAIL: $Label" } }
function Descriptor { [Security.AccessControl.RawSecurityDescriptor]::new($script:Sddl) }
function UsersAllow {
    @((Descriptor).DiscretionaryAcl | Where-Object { $_.SecurityIdentifier.Value -eq 'S-1-5-32-545' -and $_.AceQualifier -eq 'AccessAllowed' })
}
# Preserve deny/start policy and the full original admin/SYSTEM ACEs.
$script:Sddl = 'D:(D;;RP;;;BU)(A;;CCDCLCSWRPWPDTLOCRSDRCWDWO;;;SY)(A;;CCDCLCSWRPWPDTLOCRSDRCWDWO;;;BA)'
$original = Descriptor
& $block
$updated = Descriptor
Assert-True ($script:Writes -eq 1) 'single merged write'
Assert-True (@(UsersAllow).Count -eq 1 -and @(UsersAllow)[0].AccessMask -eq 20) 'only QUERY_STATUS + START'
foreach($sid in @('S-1-5-18','S-1-5-32-544')) {
    $before = @($original.DiscretionaryAcl | Where-Object { $_.SecurityIdentifier.Value -eq $sid })[0]
    $after = @($updated.DiscretionaryAcl | Where-Object { $_.SecurityIdentifier.Value -eq $sid })[0]
    Assert-True ($before.AccessMask -eq $after.AccessMask) 'admin/SYSTEM permissions preserved'
}
Assert-True ($updated.DiscretionaryAcl[0].AceQualifier -eq 'AccessDenied') 'deny remains first and effective'
& $block
Assert-True ($script:Writes -eq 1) 'reinstall idempotent'
# Object/callback deny ACEs also precede the new allow: AceType alone misses them.
$script:Sddl = 'D:(OD;;RP;11111111-1111-1111-1111-111111111111;;BU)(A;;CCDCLCSWRPWPDTLOCRSDRCWDWO;;;BA)'
& $block
Assert-True ((Descriptor).DiscretionaryAcl[0].AceQualifier -eq 'AccessDenied') 'object deny remains before allow'
Assert-True ((Descriptor).DiscretionaryAcl[0].AceType -eq 'AccessDeniedObject') 'object deny is not rewritten'
$script:Sddl = 'O:SYG:SYD:(A;;LC;;;BU)(A;;CCDCLCSWRPWPDTLOCRSDRCWDWO;;;BA)'
& $block
Assert-True (@(UsersAllow).Count -eq 2) 'existing partial user permission preserved'
Assert-True (((UsersAllow | ForEach-Object AccessMask) -join ',') -eq '20,4') 'no STOP/config/delete permission added'
foreach($failure in @('sdshow','sdset')) {
    $script:Failure=$failure
    $script:Sddl='D:(A;;CCDCLCSWRPWPDTLOCRSDRCWDWO;;;BA)'
    $thrown=$false
    try { & $block } catch { $thrown=$true }
    Assert-True $thrown 'read/write failures not silent success'
}
Write-Output 'PASS: canonical service DACL merge, minimal rights, owner-prefix input, normal/object deny and admin preservation, idempotence and failures; SCM entirely mocked.'
