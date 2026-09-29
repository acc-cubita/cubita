"""سرویس‌های ویندوز و فایروالِ سرورِ «کوبیتا سازمانی».

- **CubitaPostgres** با `pg_ctl register`ِ خودِ Postgres — نه WinSW: `postgres.exe` با
  دسترسیِ مدیر اجرا نمی‌شود و pg_ctl همین را با توکنِ محدود حل می‌کند.
- **CubitaApi** با WinSW (`cubita-server.exe serve`)، وابسته به اولی.
- هر دو با **NetworkService**، نه SYSTEM: سرویسی که پورتی روی شبکه باز می‌کند نباید
  بالاترین دسترسیِ ویندوز را داشته باشد.

**دسترسیِ پوشه با SID، نه نام.** روی ویندوزِ فارسی/عربی نامِ گروه‌ها ترجمه شده است
(«Administrators» وجود ندارد) و `icacls` با نامِ انگلیسی بی‌صدا شکست می‌خورد.

قاعده‌ی فایروال فقط برای شبکه‌ی **خصوصی و دامنه** است — هرگز Public: لپ‌تاپی که سرور
شده و در کافه به وای‌فای وصل می‌شود نباید دفترِ شرکت را روی شبکه‌ی عمومی باز کند.

فرمان‌ها به‌صورتِ فهرستِ آرگومان ساخته می‌شوند؛ موفقیتِ نصب علاوه بر خروجیِ فرمان،
به وضعیتِ واقعیِ سرویس و پاسخِ سالمِ API وابسته است.
"""

from __future__ import annotations

import json
import base64
import subprocess
import time
from pathlib import Path
from urllib.request import ProxyHandler, build_opener
from xml.sax.saxutils import escape

from app.onprem.provision import Layout, ProvisionError
from app.version import app_version

PG_SERVICE = "CubitaPostgres"
API_SERVICE = "CubitaApi"
SERVICE_ACCOUNT = r"NT AUTHORITY\NetworkService"
FIREWALL_RULE = "Cubita Enterprise API"

SID_SYSTEM = "*S-1-5-18"
SID_ADMINS = "*S-1-5-32-544"
SID_NETWORK_SERVICE = "*S-1-5-20"
SID_USERS = "*S-1-5-32-545"


def acl_commands(layout: Layout) -> list[list[str]]:
    """پوشه‌ی داده فقط برای SYSTEM، مدیرها و حسابِ سرویس — رازها و دیتابیس آنجاست."""
    return [
        ["icacls", str(layout.home), "/inheritance:r"],
        [
            "icacls",
            str(layout.home),
            "/grant:r",
            f"{SID_SYSTEM}:(OI)(CI)F",
            f"{SID_ADMINS}:(OI)(CI)F",
            f"{SID_NETWORK_SERVICE}:(OI)(CI)M",
        ],
        #: نصابِ نسخه‌ی تازه راز نیست؛ برنامه‌ی روی سرور (بی‌ارتقای UAC) باید بتواند اجرایش کند.
        ["icacls", str(layout.updates), "/grant", f"{SID_USERS}:(OI)(CI)RX"],
    ]


def pg_register_command(pg_bin: Path, layout: Layout) -> list[str]:
    return [
        str(pg_bin / "pg_ctl.exe"),
        "register",
        "-N", PG_SERVICE,
        "-U", SERVICE_ACCOUNT,
        "-D", str(layout.pgdata),
        "-S", "auto",
        "-w",
    ]


def pg_unregister_command(pg_bin: Path) -> list[str]:
    return [str(pg_bin / "pg_ctl.exe"), "unregister", "-N", PG_SERVICE]


def winsw_xml(server_exe: Path, layout: Layout) -> str:
    """پیکربندیِ WinSW v2 برای سرویسِ API. حسابِ سرویس جدا با `sc config` گذاشته می‌شود
    تا به تفاوتِ نحوِ نسخه‌های WinSW وابسته نباشیم."""
    home = escape(str(layout.home))
    return f"""<service>
  <id>{API_SERVICE}</id>
  <name>Cubita Enterprise API</name>
  <description>سرورِ کوبیتا سازمانی — کلاینت‌های شبکه‌ی داخلی به این وصل می‌شوند.</description>
  <executable>{escape(str(server_exe))}</executable>
  <arguments>serve --home "{home}"</arguments>
  <workingdirectory>{home}</workingdirectory>
  <depend>{PG_SERVICE}</depend>
  <startmode>Automatic</startmode>
  <delayedAutoStart>true</delayedAutoStart>
  <onfailure action="restart" delay="10 sec"/>
  <onfailure action="restart" delay="30 sec"/>
  <resetfailure>1 hour</resetfailure>
  <stoptimeout>20 sec</stoptimeout>
  <logpath>{escape(str(layout.logs))}</logpath>
  <log mode="roll-by-size">
    <sizeThreshold>10240</sizeThreshold>
    <keepFiles>8</keepFiles>
  </log>
</service>
"""


def firewall_commands(api_port: int) -> list[list[str]]:
    return [
        ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={FIREWALL_RULE}"],
        [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={FIREWALL_RULE}",
            "dir=in", "action=allow", "protocol=TCP",
            f"localport={api_port}",
            "profile=private,domain",
        ],
    ]


def run_all(commands: list[list[str]], *, tolerate_first: bool = False, log=print) -> None:
    for i, cmd in enumerate(commands):
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0 and not (tolerate_first and i == 0):
            raise ProvisionError(f"{Path(cmd[0]).name} {' '.join(cmd[1:3])} شکست خورد:\n{(proc.stderr or proc.stdout).strip()[-1500:]}")
        log(f"  ✓ {Path(cmd[0]).name} {cmd[1] if len(cmd) > 1 else ''}")


def _service_exists(name: str) -> bool:
    return (
        subprocess.run(
            ["sc", "query", name],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).returncode
        == 0
    )


def service_start_permission_command(name: str) -> list[str]:
    """Merge a single minimal ACE; never replace the admin/SYSTEM DACL or grant STOP.

    Windows service rights: QUERY_STATUS=0x4, START=0x10 (Microsoft Learn).
    Explicit company deny entries remain effective; failed grants fail installation.
    """
    if name not in (PG_SERVICE, API_SERVICE):
        raise ProvisionError("نام سرویس معتبر نیست.")
    script = f"""
$ErrorActionPreference='Stop'
$raw=& "$env:SystemRoot\\System32\\sc.exe" sdshow '{name}'
if($LASTEXITCODE -ne 0) {{ throw 'Service DACL query failed' }}
$sddl=($raw | Where-Object {{ $_ -match '^[OGDS]:' }} | Select-Object -First 1).Trim()
$sd=[System.Security.AccessControl.RawSecurityDescriptor]::new($sddl)
if($null -eq $sd.DiscretionaryAcl) {{ throw 'Service DACL is missing' }}
$sid=[System.Security.Principal.SecurityIdentifier]::new('S-1-5-32-545')
$allowed=0
foreach($ace in $sd.DiscretionaryAcl) {{
  if($ace -is [System.Security.AccessControl.CommonAce] -and $ace.SecurityIdentifier -eq $sid -and $ace.AceQualifier -eq 'AccessAllowed') {{ $allowed=$allowed -bor $ace.AccessMask }}
}}
if(($allowed -band 20) -ne 20) {{
  $ace=[System.Security.AccessControl.CommonAce]::new(0,0,20,$sid,$false,$null)
  $index=0
  while($index -lt $sd.DiscretionaryAcl.Count -and $sd.DiscretionaryAcl[$index] -is [System.Security.AccessControl.QualifiedAce] -and $sd.DiscretionaryAcl[$index].AceQualifier -eq 'AccessDenied') {{ $index++ }}
  $sd.DiscretionaryAcl.InsertAce($index,$ace)
  $new=$sd.GetSddlForm([System.Security.AccessControl.AccessControlSections]::Access)
  & "$env:SystemRoot\\System32\\sc.exe" sdset '{name}' $new | Out-Null
  if($LASTEXITCODE -ne 0) {{ throw 'Service DACL update failed' }}
}}
"""
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand",
            base64.b64encode(script.encode("utf-16le")).decode("ascii")]


def automatic_service_commands() -> list[list[str]]:
    commands = []
    for name in (PG_SERVICE, API_SERVICE):
        commands.extend([
            ["sc", "config", name, "start=", "delayed-auto" if name == API_SERVICE else "auto"],
            ["sc", "failure", name, "reset=", "3600", "actions=", "restart/10000/restart/30000/restart/60000"],
            service_start_permission_command(name),
        ])
    return commands


def write_recovery_port(api_port: int) -> None:
    # Public configuration only: ordinary users must never need to read .env/DB secrets.
    import winreg
    try:
        with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, r"Software\Cubita Enterprise", 0,
                               winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as key:
            winreg.SetValueEx(key, "ApiPort", 0, winreg.REG_DWORD, api_port)
    except OSError as exc:
        raise ProvisionError("پورتِ بازیابی خودکار ذخیره نشد؛ نصاب را با دسترسی مدیر دوباره اجرا کنید.") from exc


def _service_state(name: str) -> int:
    # عددِ ServiceControllerStatus ترجمه نمی‌شود؛ متنِ sc/net در ویندوزهای مختلف فرق دارد.
    if name not in (PG_SERVICE, API_SERVICE):
        raise ProvisionError("نام سرویسِ سازمانی معتبر نیست.")
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             f"$ErrorActionPreference='Stop'; [int](Get-Service -Name '{name}' -ErrorAction Stop).Status"],
            capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode == 0:
            state = int(proc.stdout.strip())
            if 1 <= state <= 7:
                return state
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    raise ProvisionError(f"وضعیتِ سرویس {name} خوانده نشد؛ دسترسیِ مدیر و Services را بررسی کنید.")


def _wait_service_state(name: str, target: int, *, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while _service_state(name) != target:
        if time.monotonic() >= deadline:
            raise ProvisionError(f"سرویس {name} به وضعیتِ مورد انتظار نرسید؛ Services و پوشهٔ logs را بررسی کنید.")
        time.sleep(0.5)


def _ensure_service_running(name: str, *, log=print) -> None:
    state = _service_state(name)
    if state == 3:  # StopPending: شروعِ سرویس پیش از پایانِ توقف ممکن نیست.
        _wait_service_state(name, 1)
        state = 1
    if state not in (1, 2, 4):
        raise ProvisionError(f"سرویس {name} متوقف یا در حال اجرا نیست؛ وضعیت آن را در Services بررسی کنید.")
    if state == 1:
        try:
            proc = subprocess.run(
                ["net", "start", name], capture_output=True, text=True,
                stdin=subprocess.DEVNULL, timeout=60,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProvisionError(f"راه‌اندازیِ سرویس {name} انجام نشد؛ Services و پوشهٔ logs را بررسی کنید.") from exc
        # فقط رقابتِ «سرویس هم‌زمان روشن شد» بی‌خطر است؛ خطاهای واقعی نباید سبز گزارش شوند.
        if proc.returncode != 0 and _service_state(name) not in (2, 4):
            raise ProvisionError(f"راه‌اندازیِ سرویس {name} شکست خورد؛ Services و پوشهٔ logs را بررسی کنید.")
    _wait_service_state(name, 4)
    log(f"  ✓ {name} در حال اجراست")


def _wait_api_ready(api_port: int, *, timeout: float = 45) -> None:
    if not 1 <= api_port <= 65535:
        raise ProvisionError("پورتِ سرور معتبر نیست.")
    # localhost نباید به پراکسی/VPNِ اینترنت فرستاده شود. Running بودنِ WinSW کافی نیست.
    opener = build_opener(ProxyHandler({}))
    expected_version = app_version()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with opener.open(f"http://127.0.0.1:{api_port}/api/health", timeout=min(3, max(0.1, deadline - time.monotonic()))) as response:
                data = json.loads(response.read(16384))
                if (response.status == 200 and isinstance(data, dict)
                        and data.get("status") == "ok" and data.get("edition") == "enterprise"
                        and data.get("version") == expected_version):
                    return
        except (OSError, ValueError):
            pass
        time.sleep(0.5)
    raise ProvisionError("سرویس روشن شد ولی سرورِ هم‌نسخه پاسخ سالم نداد؛ پوشهٔ logs، نسخه و پورتِ API را بررسی کنید. نصب هنوز کامل نیست.")


def install_services(*, layout: Layout, pg_bin: Path, server_exe: Path, winsw_exe: Path, api_port: int, log=print) -> None:
    """ACL، دو سرویس، فایروال و راه‌اندازی. نیاز به مدیر دارد. بی‌خطر برای اجرای دوباره."""
    log("دسترسیِ پوشه‌ی داده…")
    run_all(acl_commands(layout), log=log)

    log("سرویسِ PostgreSQL…")
    if not _service_exists(PG_SERVICE):
        run_all([pg_register_command(pg_bin, layout)], log=log)

    log("سرویسِ API…")
    #: WinSW پیکربندی را از فایلِ همنامِ کنارِ خودش می‌خواند: CubitaApi.exe + CubitaApi.xml.
    wrapper = layout.home / "service" / f"{API_SERVICE}.exe"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_bytes(winsw_exe.read_bytes())
    wrapper.with_suffix(".xml").write_text(winsw_xml(server_exe, layout), encoding="utf-8")
    if not _service_exists(API_SERVICE):
        run_all([[str(wrapper), "install"]], log=log)
    run_all([["sc", "config", API_SERVICE, "obj=", SERVICE_ACCOUNT, "password=", ""]], log=log)

    log("شروعِ خودکار و مجوز محدودِ بازیابی سرویس‌ها…")
    run_all(automatic_service_commands(), log=log)

    log("فایروال (فقط شبکه‌ی خصوصی و دامنه)…")
    run_all(firewall_commands(api_port), tolerate_first=True, log=log)

    log("راه‌اندازیِ سرویس‌ها…")
    _ensure_service_running(PG_SERVICE, log=log)
    _ensure_service_running(API_SERVICE, log=log)
    _wait_api_ready(api_port)
    write_recovery_port(api_port)
    log("  ✓ سرورِ سازمانی پاسخ سالم می‌دهد")


def uninstall_services(*, layout: Layout, pg_bin: Path, log=print) -> None:
    """سرویس‌ها و قاعده‌ی فایروال را برمی‌دارد. **به داده دست نمی‌زند** — دفترِ حسابداریِ
    شرکت با حذفِ برنامه پاک نمی‌شود؛ پوشه‌ی داده را فقط خودِ مدیر آگاهانه پاک می‌کند."""
    wrapper = layout.home / "service" / f"{API_SERVICE}.exe"
    steps: list[list[str]] = [["net", "stop", API_SERVICE]]
    if wrapper.exists():
        steps.append([str(wrapper), "uninstall"])
    steps += [["net", "stop", PG_SERVICE], pg_unregister_command(pg_bin)]
    steps += [firewall_commands(0)[0]]
    for cmd in steps:
        try:
            run_all([cmd], tolerate_first=True, log=log)
        except ProvisionError as exc:
            log(f"  ! {exc}")
