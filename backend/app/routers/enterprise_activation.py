"""فعال‌سازیِ آنلاینِ «کوبیتا سازمانی» — عمومی، فقط در ابر.

سرورِ مشتری (نه کاربر) این را صدا می‌زند: کدِ فعال‌سازیِ خریداری‌شده + کدِ درخواستِ
همان سرور، و توکنِ امضاشده پس می‌گیرد. توکنی از ما ندارد، پس احراز همان کدِ ۸۰بیتیِ
فعال‌سازی است؛ سقفِ نرخ لایه‌ی دوم است.

خطا با `JSONResponse` برمی‌گردد نه استثنا، تا رویدادِ «رد» (مثلاً تلاش از رایانه‌ی
دوم) در تاریخچه‌ی مجوز بماند — و در ثبت‌نامِ رایگان، شمارشِ تلاشِ غلطِ کدِ پیامکی.

ثبت‌نامِ رایگان (`/free/*`) هم همین‌جاست: سرورِ مشتری شماره و کدِ درخواستِ خودش را می‌فرستد،
کدِ پیامکی می‌گیرد و با آن مجوزِ رایگان (`services/enterprise_free.py`).
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.licensing.token import LicenseError
from app.rate_limit import limit_enterprise_free_for_phone, limit_license_activate, limit_sms_code
from app.schemas.enterprise_admin import (
    FreeActivateIn,
    FreeCodeSentOut,
    FreeSendCodeIn,
    LicenseTokenOut,
    OnlineActivateIn,
)
from app.services import enterprise_free as free
from app.services import enterprise_licenses as svc

router = APIRouter(prefix="/api/enterprise", tags=["enterprise-activation"])


@router.post("/activate", response_model=LicenseTokenOut, dependencies=[Depends(limit_license_activate)])
def activate(data: OnlineActivateIn, db: Session = Depends(get_db)):
    try:
        return LicenseTokenOut(token=svc.activate_online(db, data.code, data.request_code))
    except LicenseError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})


@router.post("/free/send-code", response_model=FreeCodeSentOut, dependencies=[Depends(limit_sms_code)])
def free_send_code(data: FreeSendCodeIn, db: Session = Depends(get_db)):
    try:
        limit_enterprise_free_for_phone(free.normalize_phone(data.phone))
        phone = free.send_code(db, data.phone, data.request_code)
    except LicenseError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    return FreeCodeSentOut(phone=free.mask_phone(phone), expires_in=free.CODE_TTL_MINUTES * 60)


@router.post("/free/activate", response_model=LicenseTokenOut, dependencies=[Depends(limit_license_activate)])
def free_activate(data: FreeActivateIn, db: Session = Depends(get_db)):
    try:
        return LicenseTokenOut(token=free.activate(db, data.phone, data.code, data.request_code, data.org))
    except LicenseError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
