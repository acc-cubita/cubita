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

همه‌ی فرمان‌ها به‌صورتِ فهرستِ آرگومان ساخته می‌شوند (تست‌پذیر) و فقط `run_all` اجرا می‌کند.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

from app.onprem.provision import Layout, ProvisionError

PG_SERVICE = "CubitaPostgres"
API_SERVICE = "CubitaApi"
SERVICE_ACCOUNT = r"NT AUTHORITY\NetworkService"
FIREWALL_RULE = "Cubita Enterprise API"

SID_SYSTEM = "*S-1-5-18"
SID_ADMINS = "*S-1-5-32-544"
SID_NETWORK_SERVICE = "*S-1-5-20"


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

    log("فایروال (فقط شبکه‌ی خصوصی و دامنه)…")
    run_all(firewall_commands(api_port), tolerate_first=True, log=log)

    log("راه‌اندازیِ سرویس‌ها…")
    run_all([["net", "start", PG_SERVICE]], tolerate_first=True, log=log)
    run_all([["net", "start", API_SERVICE]], tolerate_first=True, log=log)


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
