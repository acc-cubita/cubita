"""راه‌اندازیِ اولیه‌ی سرورِ «کوبیتا سازمانی» — فقط در نسخه‌ی سازمانی سوار می‌شود.

**چرا ثبت‌نامِ ابری کافی نیست.** ثبت‌نامِ ابری کدِ تأیید به ایمیل می‌فرستد؛ سرورِ
شرکت اغلب SMTP و حتی اینترنت ندارد. پس اینجا یک درِ دیگر است: اولین کسی که به
سرورِ تازه‌نصب وصل می‌شود کسب‌وکار و حسابِ مالک را می‌سازد.

**و فقط یک بار.** روی شبکه‌ی داخلی هر کسی می‌تواند این مسیر را صدا بزند؛ اگر بعد از
ساختِ اولین کسب‌وکار هم باز بود، هر کارمندی می‌توانست کسب‌وکارِ دومی بسازد و مالکش
شود. شرطِ «هیچ کسب‌وکاری نیست» زیرِ قفلِ تراکنشیِ Postgres سنجیده می‌شود تا دو
درخواستِ همزمان نتوانند هر دو از آن رد شوند.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.tenant import Tenant
from app.rate_limit import limit_signup
from app.schemas.auth import BusinessOwnerIn, TokenOut
from app.security import create_access_token
from app.services import modules as modules_service
from app.services import refresh as refresh_svc
from app.services.provisioning import signup_new_business

router = APIRouter(prefix="/api/setup", tags=["enterprise-setup"])

#: کلیدِ قفلِ تراکنشی — عددِ ثابتِ دلخواه، فقط باید با قفلِ دیگری در کد یکی نباشد.
_SETUP_LOCK_KEY = 0x0C0B17A5E7


class SetupStatusOut(BaseModel):
    needs_setup: bool


def _has_business(db: Session) -> bool:
    return db.query(Tenant.id).limit(1).first() is not None


@router.get("/status", response_model=SetupStatusOut)
def setup_status(db: Session = Depends(get_db)):
    """کلاینت پیش از صفحه‌ی ورود می‌پرسد: سرور هنوز راه‌اندازی نشده؟"""
    return SetupStatusOut(needs_setup=not _has_business(db))


@router.post("", response_model=TokenOut, status_code=201, dependencies=[Depends(limit_signup)])
def setup(data: BusinessOwnerIn, db: Session = Depends(get_db)):
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _SETUP_LOCK_KEY})
    if _has_business(db):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این سرور قبلاً راه‌اندازی شده است؛ با حسابِ کاربریِ خودتان وارد شوید "
            "یا از مالکِ کسب‌وکار دعوت‌نامه بگیرید.",
        )
    #: `trial=False`: دوره‌ی آزمایشیِ نسخه‌ی سازمانی از مجوز می‌آید، نه از اشتراکِ
    #: ابری — وگرنه کرونِ حذفِ آزمایشی‌ها و قفلِ کاملِ ابری سراغِ دفترِ این شرکت می‌آمد.
    tenant, user = signup_new_business(
        db,
        business_name=data.business_name,
        owner_name=data.owner_name,
        email=data.email,
        password=data.password,
        trial=False,
    )
    modules_service.set_industry(tenant, data.industry, grant_restricted=False)
    tenant.trade = data.trade
    db.flush()
    refresh = refresh_svc.issue_refresh(db, user=user, tenant_id=tenant.id)
    return TokenOut(access_token=create_access_token(user, tenant.id), refresh_token=refresh)
