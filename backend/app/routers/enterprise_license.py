"""مجوزِ «کوبیتا سازمانی» — فقط در نسخه‌ی سازمانی سوار می‌شود.

فعال‌سازیِ آفلاین‌محور: مالک «کدِ درخواست» را از اینجا می‌گیرد و برای ستاد می‌فرستد،
ستاد مجوزِ امضاشده (`CUB1.…`) پس می‌دهد و مالک آن را اینجا می‌چسباند. سرورِ خیلی از
شرکت‌ها اینترنت ندارد؛ فعال‌سازیِ آنلاینِ یک‌کلیکی (M3) روی همین مسیر سوار می‌شود،
نه جایش.

دیدنِ وضعیت برای هر عضو باز است — هر کسی که ثبتِ سندش بسته شده باید بتواند ببیند چرا
(همان استدلالِ `routers/subscription.py`). گرفتنِ کد و نصبِ مجوز فقط کارِ مالک است.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal
from app.licensing import state as license_state
from app.licensing.token import LicenseError
from app.schemas.enterprise import LicenseInstallIn, LicenseOut, LicenseRequestOut
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
