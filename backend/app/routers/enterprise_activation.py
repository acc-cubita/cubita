"""فعال‌سازیِ آنلاینِ «کوبیتا سازمانی» — عمومی، فقط در ابر.

سرورِ مشتری (نه کاربر) این را صدا می‌زند: کدِ فعال‌سازیِ خریداری‌شده + کدِ درخواستِ
همان سرور، و توکنِ امضاشده پس می‌گیرد. توکنی از ما ندارد، پس احراز همان کدِ ۸۰بیتیِ
فعال‌سازی است؛ سقفِ نرخ لایه‌ی دوم است.

خطا با `JSONResponse` برمی‌گردد نه استثنا، تا رویدادِ «رد» (مثلاً تلاش از رایانه‌ی
دوم) در تاریخچه‌ی مجوز بماند.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.licensing.token import LicenseError
from app.rate_limit import limit_license_activate
from app.schemas.enterprise_admin import LicenseTokenOut, OnlineActivateIn
from app.services import enterprise_licenses as svc

router = APIRouter(prefix="/api/enterprise", tags=["enterprise-activation"])


@router.post("/activate", response_model=LicenseTokenOut, dependencies=[Depends(limit_license_activate)])
def activate(data: OnlineActivateIn, db: Session = Depends(get_db)):
    try:
        return LicenseTokenOut(token=svc.activate_online(db, data.code, data.request_code))
    except LicenseError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
