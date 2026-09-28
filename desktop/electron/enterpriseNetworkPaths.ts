import path from 'node:path'

export function trustedNetworkHelper(executable: string, programFiles: string[]): boolean {
  const target = path.win32.resolve(executable).toLowerCase()
  return path.win32.basename(target) === 'cubita-server.exe' && programFiles.some((root) => {
    const prefix = path.win32.resolve(root).toLowerCase() + '\\'
    return target.startsWith(prefix)
  })
}

export const NETWORK_INSTALL_ACL_CHECK = `
$ErrorActionPreference='Stop'
$trusted=@('S-1-5-18','S-1-5-32-544','S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464')
$dir=Split-Path $exe
$paths=@($dir,(Split-Path $dir -Parent),(Split-Path (Split-Path $dir -Parent) -Parent)) + @(Get-ChildItem -LiteralPath $dir -Recurse -Force | Select-Object -ExpandProperty FullName)
foreach($p in $paths) {
  $item=Get-Item -LiteralPath $p -Force
  if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'پوشهٔ نصب نباید پیوند باشد.' }
  $acl=Get-Acl -LiteralPath $p
  $owner=$acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
  if($owner -notin $trusted) { throw 'مالک مسیر نصب امن نیست؛ دوباره در Program Files نصب کنید.' }
  foreach($rule in $acl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier])) {
    $sid=$rule.IdentityReference.Value
    if($rule.AccessControlType -eq 'Allow' -and $sid -notin $trusted -and ($rule.PropagationFlags -band 2) -eq 0 -and ($rule.FileSystemRights -band 852310) -ne 0) {
      throw 'فایل نصب قابل نوشتن است؛ دوباره در Program Files با دسترسی استاندارد نصب کنید.'
    }
  }
}
Write-Output 'ok'
`
