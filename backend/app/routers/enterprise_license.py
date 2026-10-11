"""مجوزِ «کوبیتا سازمانی» — فقط در نسخه‌ی سازمانی سوار می‌شود.

فعال‌سازیِ آفلاین‌محور: مالک «کدِ درخواست» را از اینجا می‌گیرد و برای ستاد می‌فرستد،
ستاد مجوزِ امضاشده (`CUB1.…`) پس می‌دهد و مالک آن را اینجا می‌چسباند. سرورِ خیلی از
شرکت‌ها اینترنت ندارد؛ فعال‌سازیِ آنلاینِ یک‌کلیکی (M3) روی همین مسیر سوار می‌شود،
نه جایش.

**ثبت‌نامِ رایگان** (`/free/*`): مالک شماره‌ی همراه می‌دهد، کدِ پیامکی می‌گیرد و سرور مجوزِ
دائمیِ رایگان (تا سه کاربر) نصب می‌کند. سرورِ بی‌اینترنت همان کدِ درخواست را برای پشتیبانی
می‌فرستد و مجوزِ رایگان را از پنل می‌گیرد — مسیرِ آفلاین برای رایگان و پولی یکی است.

دیدنِ وضعیت برای هر عضو باز است — هر کسی که ثبتِ سندش بسته شده باید بتواند ببیند چرا
(همان استدلالِ `routers/subscription.py`). گرفتنِ کد و نصبِ مجوز فقط کارِ مالک است.
"""

import logging

import httpx

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import Principal, get_principal
from app.licensing import state as license_state
from app.licensing.token import LicenseError
from app.schemas.enterprise import (
    LicenseActivateIn,
    LicenseFreeActivateIn,
    LicenseFreeCodeIn,
    LicenseFreeCodeOut,
    LicenseInstallIn,
    LicenseOut,
    LicenseRequestOut,
)
from app.services import members as members_service

router = APIRouter(prefix="/api/license", tags=["enterprise-license"])
log = logging.getLogger("cubita.license")


def _owner_only(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.role.key != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "فقط مالکِ کسب‌وکار می‌تواند نرم‌افزار را فعال کند.")
    return principal


def _out(status_, principal: Principal, db: Session) -> LicenseOut:
    out = LicenseOut.of(status_, seats_used=members_service.seats_used(db, principal.tenant_id))
    #: سقفی که واقعاً اعمال می‌شود ستونِ `max_users` است (دعوت همان را می‌سنجد)؛ در
    #: آزمایشی مجوزی نیست ولی سقف هست، و «بی‌سقف» نشان‌دادنش دروغ بود.
    if out.seats is None:
        out.seats = principal.membership.tenant.max_users
    return out


@router.get("", response_model=LicenseOut)
def get_license(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    return _out(license_state.current(db), principal, db)


@router.get("/request", response_model=LicenseRequestOut)
def get_request_code(principal: Principal = Depends(_owner_only), db: Session = Depends(get_db)):
    return LicenseRequestOut(code=license_state.request_code(db, principal.membership.tenant.name))


@router.post("", response_model=LicenseOut)
def install_license(
    data: LicenseInstallIn,
    principal: Principal = Depends(_owner_only),
    db: Session = Depends(get_db),
):
    try:
        result = license_state.install(db, data.token)
    except LicenseError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    log.info(
        "مجوز نصب شد",
        extra={"license_id": result.license_id, "mode": result.mode, "user_id": str(principal.user.id)},
    )
    return _out(result, principal, db)


def _cloud(path: str, body: dict) -> dict:
    """یک درخواست به ابرِ کوبیتا از طرفِ همین سرور (فعال‌سازی، ثبت‌نامِ رایگان).

    نبودِ اینترنت خطای کاربر نیست؛ پیام راهِ آفلاین (کدِ درخواست) را نشان می‌دهد. ردِ ابر
    (کدِ غلط، شماره‌ی نامعتبر) همان پیامِ فارسیِ ابر را به کاربر می‌رساند.
    """
    url = get_settings().license_server_url.rstrip("/") + path
    try:
        resp = httpx.post(url, json=body, timeout=20)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "این سرور به اینترنت یا سرورِ کوبیتا دسترسی ندارد. از روشِ «کدِ درخواست» استفاده کنید "
            "و کد را برای پشتیبانی بفرستید.",
        ) from exc
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail")
        except ValueError:
            detail = None
        if resp.status_code == 429:
            detail = "تلاش‌های زیادی انجام شد؛ یک ساعت دیگر دوباره امتحان کنید."
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST if resp.status_code < 500 else status.HTTP_503_SERVICE_UNAVAILABLE,
            detail if isinstance(detail, str) else "فعال‌سازی ناموفق بود؛ با پشتیبانیِ کوبیتا تماس بگیرید.",
        )
    try:
        data = resp.json()
    except ValueError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "پاسخِ سرورِ مجوز نامعتبر بود.") from exc
    if not isinstance(data, dict):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "پاسخِ سرورِ مجوز نامعتبر بود.")
    return data


def _install_from_cloud(db: Session, data: dict):
    try:
        return license_state.install(db, data["token"])
    except (LicenseError, KeyError, TypeError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc) or "پاسخِ سرورِ مجوز نامعتبر بود.") from exc


@router.post("/activate", response_model=LicenseOut)
def activate_online(
    data: LicenseActivateIn,
    principal: Principal = Depends(_owner_only),
    db: Session = Depends(get_db),
):
    """فعال‌سازیِ یک‌کلیکی: کدِ فعال‌سازی + کدِ درخواستِ همین سرور به ابر می‌رود و توکنِ
    امضاشده برمی‌گردد. بعد از آن سرور دیگر هرگز به اینترنت نیاز ندارد.
    """
    request_code = license_state.request_code(db, principal.membership.tenant.name)
    result = _install_from_cloud(db, _cloud("/api/enterprise/activate", {"code": data.code, "request_code": request_code}))
    log.info("مجوز آنلاین فعال شد", extra={"license_id": result.license_id, "user_id": str(principal.user.id)})
    return _out(result, principal, db)


@router.post("/free/send-code", response_model=LicenseFreeCodeOut)
def free_send_code(
    data: LicenseFreeCodeIn,
    principal: Principal = Depends(_owner_only),
    db: Session = Depends(get_db),
):
    """ثبت‌نامِ رایگان، قدمِ اول: ابر به این شماره کدِ پیامکی می‌فرستد.

    کد به همین سرور گره می‌خورد (کدِ درخواستش همراهِ شماره می‌رود)، پس اگر مالک آن را روی
    سرورِ دیگری وارد کند کار نمی‌کند.
    """
    request_code = license_state.request_code(db, principal.membership.tenant.name)
    out = _cloud("/api/enterprise/free/send-code", {"phone": data.phone, "request_code": request_code})
    try:
        return LicenseFreeCodeOut(phone=str(out["phone"]), expires_in=int(out["expires_in"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "پاسخِ سرورِ مجوز نامعتبر بود.") from exc


@router.post("/free/activate", response_model=LicenseOut)
def free_activate(
    data: LicenseFreeActivateIn,
    principal: Principal = Depends(_owner_only),
    db: Session = Depends(get_db),
):
    """ثبت‌نامِ رایگان، قدمِ دوم: کدِ پیامکی → مجوزِ رایگانِ دائمیِ همین سرور."""
    tenant_name = principal.membership.tenant.name
    request_code = license_state.request_code(db, tenant_name)
    body = {
        "phone": data.phone,
        "code": data.code,
        "request_code": request_code,
        "org": (data.org or "").strip() or tenant_name,
    }
    result = _install_from_cloud(db, _cloud("/api/enterprise/free/activate", body))
    log.info("ثبت‌نامِ رایگان انجام شد", extra={"license_id": result.license_id, "user_id": str(principal.user.id)})
    return _out(result, principal, db)
