"""Windows فقط؛ فرمان‌های ثابت، ورودیِ JSON و تنظیمِ محافظت‌شدهٔ ماشین.

نقطهٔ تغییرِ OS یک CLI محلیِ elevated است، نه endpoint سرور. اجرای منظم SYSTEM
فقط از نصبِ Program Files مجاز است؛ فایلِ قابل‌نوشتنِ کاربر هرگز elevated اجرا نمی‌شود.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
from functools import wraps
from pathlib import Path

from app.onprem.network import NetworkError, make_plan, network_of, suggestions, validate_config

TASK = "CubitaEnterpriseNetwork"
RULE = "CubitaEnterpriseNetworkLAN"

PREAMBLE = r"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$taskName = 'CubitaEnterpriseNetwork'
$ruleName = 'CubitaEnterpriseNetworkLAN'
"""

# PowerShell late-bound COM cannot marshal GUID results; invoke the documented
# INetwork/INetworkConnection GUID slots with their exact native signature.
NETWORK_IDS = r"""
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class CubitaNetworkIds {
  [UnmanagedFunctionPointer(CallingConvention.StdCall)]
  private delegate int GuidResult(IntPtr self, out Guid result);
  private static string Read(object value, string iid, int slot) {
    IntPtr unknown = Marshal.GetIUnknownForObject(value), iface = IntPtr.Zero;
    try {
      Guid id = new Guid(iid);
      Marshal.ThrowExceptionForHR(Marshal.QueryInterface(unknown, ref id, out iface));
      IntPtr method = Marshal.ReadIntPtr(Marshal.ReadIntPtr(iface), slot * IntPtr.Size);
      GuidResult fn = (GuidResult)Marshal.GetDelegateForFunctionPointer(method, typeof(GuidResult));
      Guid result; Marshal.ThrowExceptionForHR(fn(iface, out result));
      return result.ToString();
    } finally { if (iface != IntPtr.Zero) Marshal.Release(iface); Marshal.Release(unknown); }
  }
  public static string Adapter(object connection) { return Read(connection, "DCB00005-570F-4A9B-8D69-199FDBA5723B", 12); }
  public static string Network(object network) { return Read(network, "DCB00002-570F-4A9B-8D69-199FDBA5723B", 11); }
}
'@
$networkIds = @{}
$nlm = [Activator]::CreateInstance([Type]::GetTypeFromCLSID([Guid]'DCB00C01-570F-4A9B-8D69-199FDBA5723B'))
foreach ($c in $nlm.GetNetworkConnections()) {
  $networkIds[[CubitaNetworkIds]::Adapter($c)] = [CubitaNetworkIds]::Network($c.GetNetwork())
}
"""

INVENTORY = r"""
$allRoutes = @(Get-NetRoute -ErrorAction Stop)
$adapters = @(foreach ($a in @(Get-NetAdapter -IncludeHidden -ErrorAction Stop)) {
  $idx = $a.InterfaceIndex
  $ip = Get-NetIPInterface -InterfaceIndex $idx -AddressFamily IPv4 -ErrorAction SilentlyContinue
  $profile = Get-NetConnectionProfile -InterfaceIndex $idx -ErrorAction SilentlyContinue | Select-Object -First 1
  $addresses = @(Get-NetIPAddress -InterfaceIndex $idx -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.AddressState -in @('Preferred', 'Tentative') } |
    ForEach-Object { @{address=$_.IPAddress; prefix=[int]$_.PrefixLength; origin=[string]$_.PrefixOrigin} })
  $gateways = @($allRoutes | Where-Object { $_.InterfaceIndex -eq $idx -and $_.DestinationPrefix -in @('0.0.0.0/0','::/0') } | ForEach-Object { $_.NextHop })
  $kind = 'other'
  # Some USB/older drivers report an unspecified physical medium; IANA type is the fallback.
  if ([int]$a.NdisPhysicalMedium -eq 14 -or [int]$a.InterfaceType -eq 6) { $kind = 'wired' }
  if ([int]$a.NdisPhysicalMedium -in @(1,9) -or [int]$a.InterfaceType -eq 71) { $kind = 'wifi' }
  $id = $a.InterfaceGuid.ToString().Trim('{}').ToLower()
  @{id=$id; name=$a.Name; description=$a.InterfaceDescription; index=[int]$idx;
    physical=[bool]$a.HardwareInterface; kind=$kind; status=[string]$a.Status;
    dhcp=([string]$ip.Dhcp -eq 'Enabled'); addresses=$addresses; gateways=$gateways;
    defaultRoute=($gateways.Count -gt 0); profile=[string]$profile.NetworkCategory;
    networkId=$networkIds[$id]}
})
@{adapters=$adapters; routes=@($allRoutes | ForEach-Object { @{index=[int]$_.InterfaceIndex; destination=$_.DestinationPrefix} })} | ConvertTo-Json -Depth 8 -Compress
"""

# Guard immediately before New-NetIPAddress too: the network may change after preview.
APPLY = r"""
$a = Get-NetAdapter -IncludeHidden | Where-Object { $_.InterfaceGuid.ToString().Trim('{}') -eq $data.config.adapterId } | Select-Object -First 1
if (!$a -or !$a.HardwareInterface -or $a.Status -ne 'Up') { throw 'کارت شبکه وصل نیست؛ تنظیمی اعمال نشد.' }
if ($data.config.topology -eq 'direct') {
  $defaults = @(Get-NetRoute -InterfaceIndex $a.InterfaceIndex | Where-Object { $_.DestinationPrefix -in @('0.0.0.0/0','::/0') })
  if ($defaults.Count) { throw 'کارت مسیر اینترنت دارد؛ IP و DHCP تغییر نکرد.' }
}
if ($data.addAddress) {
  if ([int]$a.NdisPhysicalMedium -in @(1,9) -or [int]$a.InterfaceType -eq 71 -or ([int]$a.NdisPhysicalMedium -ne 14 -and [int]$a.InterfaceType -ne 6)) { throw 'تغییر IP فقط روی LAN فیزیکی مجاز است.' }
  $defaults = @(Get-NetRoute -InterfaceIndex $a.InterfaceIndex | Where-Object { $_.DestinationPrefix -in @('0.0.0.0/0','::/0') })
  if ($defaults.Count) { throw 'کارت مسیر اینترنت دارد؛ IP و DHCP تغییر نکرد.' }
  $old = @(Get-NetIPAddress -InterfaceIndex $a.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '169.254.*' })
  if ($old.Count) { throw 'IP کارت تغییر کرده؛ ابتدا دوباره پیش‌نمایش بگیرید.' }
  $ipInterface = Get-NetIPInterface -InterfaceIndex $a.InterfaceIndex -AddressFamily IPv4
  $apipa = @(Get-NetIPAddress -InterfaceIndex $a.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -like '169.254.*' -and $_.AddressState -eq 'Preferred' })
  if ($ipInterface.Dhcp -eq 'Enabled' -and !$apipa.Count) { throw 'دریافت IP خودکار هنوز کامل نشده؛ DHCP تغییر نکرد.' }
  function IpSpan($cidr) {
    $parts=$cidr.Split('/'); $bytes=([ipaddress]$parts[0]).GetAddressBytes()
    if($bytes.Length -ne 4) { return $null }
    $number=[double]0; foreach($byte in $bytes) { $number=$number*256+$byte }
    $size=[math]::Pow(2,32-[int]$parts[1]); $lo=[math]::Floor($number/$size)*$size
    return @{lo=$lo; hi=$lo+$size-1}
  }
  $target=IpSpan $data.subnet
  foreach($route in @(Get-NetRoute -AddressFamily IPv4)) {
    if($route.InterfaceIndex -eq $a.InterfaceIndex -or $route.DestinationPrefix -eq '0.0.0.0/0') { continue }
    $range=IpSpan $route.DestinationPrefix
    if($range -and $target.lo -le $range.hi -and $range.lo -le $target.hi) { throw 'محدوده با مسیر شبکه/VPN تداخل دارد؛ IP تغییر نکرد.' }
  }
  # IP دیگری جایگزین/حذف نمی‌شود؛ ویندوز DAD را پیش از استفاده انجام می‌دهد.
  New-NetIPAddress -InterfaceIndex $a.InterfaceIndex -IPAddress $data.config.address -PrefixLength $data.config.prefix | Out-Null
  $ready = $false
  for ($i=0; $i -lt 15; $i++) {
    $state = Get-NetIPAddress -InterfaceIndex $a.InterfaceIndex -IPAddress $data.config.address -ErrorAction SilentlyContinue
    if ($state.AddressState -contains 'Duplicate') { throw 'این IP در شبکه تکراری است؛ در تنظیمات ویندوز حذف و IP دیگری انتخاب کنید.' }
    if ($state.AddressState -contains 'Preferred') { $ready = $true; break }
    Start-Sleep -Milliseconds 500
  }
  if (!$ready) { throw 'IP هنوز آماده نیست؛ اتصال و تکراری‌نبودن IP را بررسی کنید.' }
}
$present = @(Get-NetIPAddress -InterfaceIndex $a.InterfaceIndex -IPAddress $data.config.address -ErrorAction SilentlyContinue | Where-Object { $_.AddressState -eq 'Preferred' -and $_.PrefixLength -eq $data.config.prefix })
if (!$present.Count) { throw 'IP آماده نیست؛ فایروال باز نشد.' }
if ($data.networkId) {
  if ($networkIds[$data.config.adapterId] -ne $data.networkId) { throw 'هویت شبکه عوض شده؛ دوباره بررسی و تأیید کنید.' }
}
if ($data.role -ne 'server') {
  Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
  return
}
# InterfaceAlias accepts wildcards: Escape keeps an unusual adapter name literal.
$alias = [System.Management.Automation.WildcardPattern]::Escape($a.Name)
$rule = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
$params = @{Direction='Inbound'; Action='Allow'; Enabled='True'; Profile='Any'; Protocol='TCP';
  LocalPort=$data.config.port; LocalAddress=$data.config.address; RemoteAddress=$data.subnet; InterfaceAlias=$alias}
if ($rule) { Set-NetFirewallRule -Name $ruleName @params | Out-Null }
else { New-NetFirewallRule -Name $ruleName -DisplayName 'Cubita Enterprise trusted LAN' @params | Out-Null }
"""

REGISTER = r"""
$action = New-ScheduledTaskAction -Execute $data.exe -Argument 'network-maintain'
$boot = New-ScheduledTaskTrigger -AtStartup
$repeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 50) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId 'S-1-5-18' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($boot,$repeat) -Settings $settings -Principal $principal -Force | Out-Null
"""

DISABLE = r"""
Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false
Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
"""


def root() -> Path:
    # Separate from financial-data ACL: standard users can read network status, not write it.
    return Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "CubitaNetwork"


def ps(script: str, data: dict | None = None) -> str:
    if os.name != "nt":
        raise NetworkError("تنظیم خودکار شبکه فقط در نسخهٔ نصب‌شدهٔ ویندوز در دسترس است.")
    payload = base64.b64encode(json.dumps(data or {}).encode("utf-8")).decode("ascii")
    code = PREAMBLE + f"\n$data = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{payload}')) | ConvertFrom-Json\n" + script
    exe = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    env = dict(os.environ)
    # PowerShell 7's module path can otherwise load incompatible assemblies in Windows PowerShell 5.1.
    env.pop("PSModulePath", None)
    proc = subprocess.run([str(exe), "-NoProfile", "-NonInteractive", "-EncodedCommand", base64.b64encode(code.encode("utf-16le")).decode("ascii")],
                          capture_output=True, encoding="utf-8", timeout=45, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.returncode:
        error = proc.stderr.strip()
        if "<Objs" in error:
            import re
            import xml.etree.ElementTree as ET
            try:
                tree = ET.fromstring(error[error.index("<Objs"):])
                error = "\n".join(t.text or "" for t in tree.iter() if t.tag.endswith("}S") and t.attrib.get("S") == "Error")
                error = re.sub(r"_x([0-9a-fA-F]{4})_", lambda m: chr(int(m[1], 16)), error)
            except ET.ParseError:
                pass
        raise NetworkError(error[-1800:] or "فرمان شبکه اجرا نشد؛ دسترسی مدیر و سیاست شبکه را بررسی کنید.")
    return proc.stdout.strip().lstrip("\ufeff")


def local_role() -> str:
    if os.name != "nt":
        return "client"
    import winreg
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Cubita Enterprise", 0, winreg.KEY_READ | view) as key:
                return "server" if winreg.QueryValueEx(key, "Role")[0] == "server" else "client"
        except OSError:
            continue
    return "client"


def inventory() -> dict:
    result = json.loads(ps(NETWORK_IDS + INVENTORY))
    result["suggestions"] = suggestions(result)
    result["role"] = local_role()
    if result["role"] == "client":
        for suggestion in result["suggestions"].values():
            if suggestion["mode"] == "static":
                suggestion["address"] = suggestion["address"].rsplit(".", 1)[0] + ".2"
    result["state"] = read_state()
    return result


def require_admin() -> None:
    import ctypes
    if os.name != "nt" or not ctypes.windll.shell32.IsUserAnAdmin():
        raise NetworkError("برای اعمال شبکه، تأییدِ مدیر ویندوز لازم است.")


def trusted_executable() -> Path:
    exe = Path(sys.executable).resolve()
    roots = [Path(os.environ[k]).resolve() for k in ("ProgramFiles", "ProgramW6432") if os.environ.get(k)]
    if not getattr(sys, "frozen", False) or exe.name.lower() != "cubita-server.exe" or not any(exe.is_relative_to(p) for p in roots):
        raise NetworkError("اعمال و نگهداری شبکه فقط از نصاب سازمانیِ نصب‌شده در Program Files مجاز است؛ مسیر نصب را اصلاح کنید.")
    # A custom ACL must not let a standard user replace SYSTEM's executable/dependencies.
    ps(r"""
$dir = Split-Path $data.exe
foreach ($p in @($data.exe,$dir,(Split-Path $dir -Parent),(Split-Path (Split-Path $dir -Parent) -Parent))) {
  $acl = Get-Acl -LiteralPath $p
  foreach ($rule in $acl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier])) {
    $sid = $rule.IdentityReference.Value
    if ($rule.AccessControlType -eq 'Allow' -and $sid -notin @('S-1-5-18','S-1-5-32-544','S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464')) {
      if (($rule.FileSystemRights -band 852310) -ne 0 -and ($rule.PropagationFlags -band 2) -eq 0) { throw 'مسیر نصب قابل نوشتن است؛ برای امنیت به Program Files با دسترسی استاندارد نصب کنید.' }
    }
  }
}
""", {"exe": str(exe)})
    return exe


def is_link(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def protect_root() -> None:
    directory = root()
    directory.mkdir(parents=True, exist_ok=True)
    if is_link(directory):
        raise NetworkError("پوشهٔ تنظیم شبکه نباید پیوند باشد؛ مدیر ویندوز مسیر را بررسی کند.")
    ps(r"""
$p = $data.root
$acl = New-Object System.Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true,$false)
$acl.SetOwner((New-Object System.Security.Principal.SecurityIdentifier('S-1-5-32-544')))
foreach ($entry in @(@('S-1-5-18','FullControl'),@('S-1-5-32-544','FullControl'),@('S-1-5-32-545','ReadAndExecute'))) {
  $sid = New-Object System.Security.Principal.SecurityIdentifier($entry[0])
  $r = New-Object System.Security.AccessControl.FileSystemAccessRule($sid,$entry[1],'ContainerInherit,ObjectInherit','None','Allow')
  $acl.AddAccessRule($r)
}
Set-Acl -LiteralPath $p -AclObject $acl
""", {"root": str(directory)})


def _write(name: str, data: dict) -> None:
    target = root() / name
    if is_link(target):
        raise NetworkError("فایل تنظیم شبکه نباید پیوند باشد.")
    temp = root() / (name + ".tmp")
    if temp.exists():
        temp.unlink()
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    temp.replace(target)


def read_state() -> dict:
    try:
        return json.loads((root() / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"enabled": False, "message": "نگهداری خودکار شبکه هنوز فعال نشده است."}


def exclusive(func):
    @wraps(func)
    def run(*args, **kwargs):
        require_admin()
        trusted_executable()
        protect_root()
        lock_path = root() / "network.lock"
        if is_link(lock_path) or (lock_path.exists() and lock_path.stat().st_nlink > 1):
            raise NetworkError("فایل قفل شبکه نباید پیوند باشد؛ مدیر مسیر را بررسی کند.")
        with lock_path.open("a+b") as lock:
            if lock.tell() == 0:
                lock.write(b"0"); lock.flush()
            for attempt in range(31):
                try:
                    lock.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as exc:
                    if attempt == 30:
                        raise NetworkError("تنظیم دیگری در حال اجراست؛ چند لحظه بعد دوباره تلاش کنید.") from exc
                    time.sleep(0.25)
            try:
                return func(*args, **kwargs)
            finally:
                lock.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return run


@exclusive
def apply(raw: dict) -> dict:
    require_admin()
    exe = trusted_executable()
    plan = None
    try:
        plan = make_plan(raw, inventory())
        plan["role"] = local_role()
        check_server_port(plan)
        _write("settings.json", {"config": plan["config"], "networkId": plan["networkId"]})
        ps(NETWORK_IDS + APPLY, plan)
        if plan["config"]["startup"]:
            ps(REGISTER, {"exe": str(exe)})
        else:
            ps("Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false")
    except Exception as exc:
        # No broad rollback: preserve IP/data; close only our dedicated LAN rule on failure.
        message = close_rule_on_error(str(exc))
        state = {"enabled": False, "message": message}
        if plan is not None:
            state["config"] = plan["config"]
        _write("state.json", state)
        raise
    state = {"enabled": True, "config": plan["config"], "serverUrl": plan["serverUrl"], "message": "دسترسی شبکه اعمال شد؛ تنظیمات اینترنت حفظ شد."}
    _write("state.json", state)
    return state


@exclusive
def maintain() -> dict:
    require_admin()
    trusted_executable()
    config = None
    try:
        saved = read_trusted_settings()
        if not isinstance(saved, dict) or "networkId" not in saved:
            raise NetworkError("تنظیم ذخیره‌شده ناقص است؛ دوباره از فرم شبکه تأیید کنید.")
        config = validate_config(saved.get("config"))
        inv = inventory()
        # DHCP may renew within the approved subnet. Never move to a new network silently.
        if config["mode"] == "keep":
            adapter = next((a for a in inv["adapters"] if a["id"] == config["adapterId"]), None)
            net = network_of(config["address"], config["prefix"])
            if adapter:
                candidate = next((a for a in adapter["addresses"] if ip_in(a["address"], net) and a["prefix"] == config["prefix"]), None)
                if candidate:
                    config["address"] = candidate["address"]
        plan = make_plan(config, inv)
        plan["role"] = local_role()
        adapter = next(a for a in inv["adapters"] if a["id"] == config["adapterId"])
        if plan["addAddress"] and adapter["dhcp"]:
            raise NetworkError("DHCP این کارت دوباره فعال شده؛ برای حفظ اینترنت، IP خودکار تغییر نکرد. دوباره بررسی و تأیید کنید.")
        check_server_port(plan)
        if plan["networkId"] != saved["networkId"]:
            raise NetworkError("شبکه عوض شده؛ برای دسترسی شبکهٔ جدید دوباره بررسی و تأیید کنید.")
        ps(NETWORK_IDS + APPLY, plan)
        state = {"enabled": True, "config": config, "serverUrl": plan["serverUrl"], "message": "شبکه آماده است؛ اینترنت دست‌نخورده است."}
    except (NetworkError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        state = {"enabled": False, "message": close_rule_on_error(str(exc))}
        if config is not None:
            state["config"] = config
    _write("state.json", state)
    return state


def close_rule_on_error(message: str) -> str:
    try:
        ps("Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue | Disable-NetFirewallRule")
    except (NetworkError, OSError, subprocess.TimeoutExpired) as exc:
        return f"{message}\nبستن قاعدهٔ اختصاصی هم ناموفق بود؛ مدیر فایروال را بررسی کند: {exc}"
    return message


def ip_in(address: str, net) -> bool:
    import ipaddress
    return ipaddress.IPv4Address(address) in net


def check_server_port(plan: dict) -> None:
    if plan["role"] != "server":
        return
    env_path = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Cubita/.env"
    if not env_path.exists():
        raise NetworkError("تنظیم سرور نصب‌شده پیدا نشد؛ نصب سرور را کامل کنید.")
    port = next((line.split("=", 1)[1].strip() for line in env_path.read_text(encoding="utf-8").splitlines() if line.startswith("API_PORT=")), "8420")
    if str(plan["config"]["port"]) != port:
        raise NetworkError(f"پورت نصب‌شدهٔ سرور {port} است؛ پورت فرم را اصلاح کنید. فایروال باز نشد.")


def resume() -> dict:
    require_admin()
    exe = trusted_executable()
    if not (root() / "settings.json").exists():
        return {"enabled": False, "message": "تنظیم شبکه هنوز فعال نشده است."}
    saved = read_trusted_settings()
    if validate_config(saved["config"])["startup"]:
        ps(REGISTER, {"exe": str(exe)})
    return maintain()


def read_trusted_settings() -> dict:
    # In particular, an installer must not resume a settings file planted before first setup.
    ps(r"""
$trusted=@('S-1-5-18','S-1-5-32-544')
foreach($p in @($data.root,(Join-Path $data.root 'settings.json'))) {
  $item=Get-Item -LiteralPath $p -Force
  if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'تنظیم ذخیره‌شده نباید پیوند باشد.' }
  $acl=Get-Acl -LiteralPath $p
  if($acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -notin $trusted) { throw 'مالک تنظیم شبکه معتبر نیست؛ دوباره از فرم شبکه تأیید کنید.' }
  foreach($rule in $acl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier])) {
    $sid=$rule.IdentityReference.Value
    if($rule.AccessControlType -eq 'Allow' -and $sid -notin $trusted -and ($rule.PropagationFlags -band 2) -eq 0 -and ($rule.FileSystemRights -band 852310) -ne 0) {
      throw 'تنظیم شبکه قابل نوشتن است؛ دوباره از فرم شبکه تأیید کنید.'
    }
  }
}
""", {"root": str(root())})
    return json.loads((root() / "settings.json").read_text(encoding="utf-8"))


@exclusive
def disable() -> dict:
    require_admin()
    trusted_executable()
    ps(DISABLE)
    (root() / "settings.json").unlink(missing_ok=True)
    state = {"enabled": False, "message": "نگهداری شبکه و قاعدهٔ اختصاصی برداشته شدند. IP موجود حفظ شد؛ اصلاح IP از تنظیمات دستی ویندوز انجام می‌شود."}
    _write("state.json", state)
    return state
