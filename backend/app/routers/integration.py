import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_feature, require_module, require_permission
from app.models.user import User
from app.schemas.storefront import StorefrontSettingsIn, StorefrontSettingsOut
from app.services import storefront_integration as service
from app.services.storefront_integration import StorefrontConfigError, sync_all

# دو گیتِ مستقل روی کلِ روتر، به همین ترتیب:
#   • require_feature("storefront") — گیتِ پلن: حسابِ آزمایشی ۴۰۲ و باکسِ «خرید پلن».
#   • require_module("integration") — «حقِ دسترسی»: تا سوپرادمین این ماژول را به اکانت
#     نداده باشد، حتی حسابِ پولی هم ۴۰۳ می‌گیرد (پیش‌فرض خاموش).
# ترتیب عمدی است: به حسابِ آزمایشی باید «پلن بخر» گفته شود نه «با پشتیبانی تماس بگیر»،
# چون خریدِ پلن کاری است که خودش می‌تواند انجام دهد.
router = APIRouter(
    prefix="/api/integration",
    tags=["integration"],
    dependencies=[Depends(require_feature("storefront")), Depends(require_module("integration"))],
)


def _to_out(row) -> StorefrontSettingsOut:
    if row is None:
        return StorefrontSettingsOut(
            base_url="", admin_email="", has_password=False, cutover_order_id=0, is_active=False
        )
    return StorefrontSettingsOut(
        base_url=row.base_url,
        admin_email=row.admin_email,
        has_password=bool(row.admin_password),
        cutover_order_id=row.cutover_order_id,
        is_active=row.is_active,
    )


@router.get("/settings", response_model=StorefrontSettingsOut)
def get_settings(
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    return _to_out(service.get_settings_row(db))


@router.put("/settings", response_model=StorefrontSettingsOut)
def update_settings(
    data: StorefrontSettingsIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    return _to_out(service.update_settings(db, data))


@router.post("/sync")
def trigger_sync(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    try:
        return sync_all(db, user)
    except StorefrontConfigError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err))
    except httpx.HTTPError as err:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"ارتباط با سایت فروشگاهی برقرار نشد: {err}")
