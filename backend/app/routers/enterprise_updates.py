"""آپدیتِ «کوبیتا سازمانی» روی سرورِ شرکت — فقط در نسخه‌ی سازمانی سوار می‌شود.

- `GET /updates/{name}` **بی‌احراز**: electron-updater توکن نمی‌فرستد. امن است چون فقط نام‌هایی
  را می‌دهد که در `latest.yml`ِ امضاشده‌ی نسخه‌ی **همین سرور** آمده‌اند (`feed_files`)، و
  کلاینت خودش امضا و هش را دوباره می‌سنجد. نصابِ برنامه راز نیست.
- `GET /api/updates` و `POST /api/updates/check` فقط مالک: وضعیت و گرفتنِ نسخه‌ی تازه از ابر.

منطق در `app/onprem/updates.py` است.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import get_settings
from app.deps import Principal, get_principal
from app.licensing.state import license_file
from app.onprem import updates as upd

router = APIRouter(tags=["enterprise-updates"])


def _home() -> Path:
    #: پوشه‌ی داده‌ی نصب (همان جای `license.lic`؛ `.env`ِ نصاب `LICENSE_DIR` را آنجا می‌گذارد).
    return license_file().parent


def _owner_only(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.role.key != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "به‌روزرسانیِ سرور فقط کارِ مالکِ کسب‌وکار است.")
    return principal


class UpdateStatusOut(BaseModel):
    running: str
    latest_available: str | None
    #: مسیرِ نصابِ دانلودشده روی دیسکِ سرور — برنامه‌ی روی خودِ سرور اجرایش می‌کند.
    installer_path: str | None
    serving_clients: bool


def _out(s: upd.UpdateStatus) -> UpdateStatusOut:
    return UpdateStatusOut(
        running=s.running,
        latest_available=s.latest_available,
        installer_path=s.installer_path,
        serving_clients=s.serving_clients,
    )


@router.get("/updates/{name}", include_in_schema=False)
def feed(name: str):
    folder = upd.feed_dir(_home())
    if name not in upd.feed_files(folder):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    media = "text/yaml" if name.endswith(".yml") else "application/octet-stream"
    #: latest.yml نباید کش شود — وگرنه کلاینت نسخه‌ی تازه را دیر می‌بیند.
    headers = {"Cache-Control": "no-cache"} if name.endswith((".yml", ".sig")) else None
    return FileResponse(folder / name, media_type=media, headers=headers)


@router.get("/api/updates", response_model=UpdateStatusOut)
def get_status(_: Principal = Depends(_owner_only)):
    return _out(upd.status(_home()))


@router.post("/api/updates/check", response_model=UpdateStatusOut)
def check(_: Principal = Depends(_owner_only)):
    try:
        result = upd.check_and_download(_home(), get_settings().license_server_url)
    except upd.UpdateError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    upd.prune(_home())
    return _out(result)
