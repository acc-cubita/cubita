"""گزارش‌های خطای کلاینت — کارتابلِ ستاد.

خواندنِ این گزارش‌ها از `app/routers/client_errors.py` منتقل شد. ingestِ عمومیِ
`POST /api/client-errors` سرِ جایش ماند و باید هم بماند: مرورگری که در حالِ
سقوط است هنوز توکنِ معتبر ندارد.

stack trace داده‌ی عملیاتیِ ماست و می‌تواند تکه‌هایی از دادهٔ مشتری را در خودش
داشته باشد، پس خواندنش فقط از ستاد.
"""
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import StaffPrincipal, require_staff
from app.models.client_error import ClientError
from app.routers.client_errors import ClientErrorOut

router = APIRouter(prefix="/api/admin/client-errors", tags=["admin-errors"])


@router.get("", response_model=list[ClientErrorOut])
def list_errors(
    db: Session = Depends(get_db),
    _: StaffPrincipal = Depends(require_staff("errors", "view")),
    limit: Annotated[int, Field(ge=1, le=200)] = 100,
    only_fatal: bool = False,
) -> list[ClientErrorOut]:
    """تازه‌ترین گزارش‌ها، تازه‌ترین اول."""
    q = select(ClientError).order_by(ClientError.received_at.desc()).limit(limit)
    if only_fatal:
        q = q.where(ClientError.fatal.is_(True))
    #: `id` در اسکیما رشته است و در مدل UUID — ساختِ صریح لازم است، وگرنه
    #: اعتبارسنجیِ پاسخ می‌شکند.
    return [
        ClientErrorOut(
            id=str(r.id),
            occurred_at=r.occurred_at,
            received_at=r.received_at,
            fatal=r.fatal,
            name=r.name,
            message=r.message,
            stack=r.stack,
            screen=r.screen,
            app_version=r.app_version,
            platform=r.platform,
            os_version=r.os_version,
            device=r.device,
        )
        for r in db.execute(q).scalars().all()
    ]
