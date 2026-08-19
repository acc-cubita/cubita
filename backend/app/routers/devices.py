"""ثبتِ دستگاه برای اعلانِ Push (اپ موبایل).

هر کاربرِ احرازشده دستگاهِ *خودش* را ثبت/حذف می‌کند — نه پشتِ require_permission، چون
این یک تنظیمِ شخصیِ نشست است نه کنشی روی دفترِ کسب‌وکار. مالکیت با فیلترِ صریحِ
user_id تضمین می‌شود (device_tokens سراسری است و RLS ندارد).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal
from app.schemas.devices import DeviceRegisterIn
from app.services import push

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.post("", status_code=204)
def register_device(
    data: DeviceRegisterIn,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """توکنِ FCMِ این دستگاه را ثبت/به‌روزرسانی می‌کند (upsert بر پایه‌ی توکن)."""
    push.register_device(
        db,
        user_id=principal.user.id,
        tenant_id=principal.tenant_id,
        fcm_token=data.fcm_token,
        platform=data.platform,
    )


@router.delete("", status_code=204)
def unregister_device(
    token: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    """توکنِ دستگاهِ همین کاربر را حذف می‌کند (هنگامِ خروج). token به‌صورتِ query می‌آید
    چون توکنِ FCM می‌تواند کاراکترهای ناسازگار با مسیر داشته باشد."""
    push.unregister_device(db, user_id=principal.user.id, fcm_token=token)
