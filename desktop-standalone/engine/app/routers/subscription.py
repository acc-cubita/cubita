"""وضعیت اشتراک کسب‌وکار جاری.

عمداً پشت مجوز خاصی نیست: هر عضوی باید بتواند ببیند چرا نمی‌تواند سند ثبت کند.
پنهان کردنش از کاربر عادی یعنی او خطای ۴۰۲ می‌گیرد و هیچ راهی برای فهمیدن علت
ندارد.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal
from app.services.subscriptions import state_for

router = APIRouter(prefix="/api/subscription", tags=["subscription"])


class SubscriptionOut(BaseModel):
    status: str
    expires_at: str | None
    days_left: int | None
    can_write: bool
    should_warn: bool


@router.get("", response_model=SubscriptionOut)
def my_subscription(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
):
    s = state_for(db, principal.tenant_id)
    return SubscriptionOut(
        status=s.status,
        expires_at=s.expires_at.isoformat() if s.expires_at else None,
        days_left=s.days_left,
        can_write=s.can_write,
        should_warn=s.should_warn,
    )
