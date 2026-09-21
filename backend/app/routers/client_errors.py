"""دریافتِ گزارشِ کرشِ کلاینت‌ها، و مرورشان توسطِ سوپرادمین.

**چرا ثبت احراز هویت نمی‌خواهد:** ارزشمندترین گزارش‌ها آن‌هایی‌اند که *پیش از ورود*
می‌افتند — خطای راه‌اندازی، خطای صفحه‌ی ورود، رفرش‌توکنِ باطل. اگر توکن لازم بود،
دقیقاً همان‌ها هرگز نمی‌رسیدند.

**ولی درِ باز نیست:** سه گارد هست — سقفِ تعدادِ گزارش در هر درخواست، سقفِ اندازه‌ی
هر میدان (بریدن به‌جای رد کردن، چون گزارشِ بریده از هیچ بهتر است)، و قیدِ یکتای
`client_id` که ارسالِ دوباره‌ی یک صف را به‌جای رکوردِ تکراری، بی‌اثر می‌کند.

**خواندن اما سوپرادمین می‌خواهد.** stack trace می‌تواند نامِ فایل و مسیرِ داخلی را
لو بدهد؛ این داده‌ی عملیاتیِ ماست، نه دفترِ مشتری.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.client_error import ClientError
from app.models.user import User
from app.security import decode_access_token

router = APIRouter(prefix="/api/client-errors", tags=["client-errors"])

#: بیشترین گزارش در یک درخواست. صفِ خودِ اپ روی ۵۰ بسته است، پس این سقف هم‌خوان
#: است و هم جلوی یک بدنه‌ی غول‌آسا را می‌گیرد.
MAX_BATCH = 50

MAX_STACK = 10_000
MAX_MESSAGE = 1_000


class ClientErrorIn(BaseModel):
    id: str = Field(max_length=64)
    at: datetime
    fatal: bool = False
    name: str = Field(default="Error", max_length=200)
    message: str = ""
    stack: str | None = None
    screen: str | None = Field(default=None, max_length=100)
    app_version: str | None = Field(default=None, max_length=30)
    platform: str | None = Field(default=None, max_length=20)
    os_version: str | None = Field(default=None, max_length=30)
    device: str | None = Field(default=None, max_length=100)


class ClientErrorBatchIn(BaseModel):
    reports: list[ClientErrorIn] = Field(max_length=MAX_BATCH)


class ClientErrorOut(BaseModel):
    id: str
    occurred_at: datetime
    received_at: datetime
    fatal: bool
    name: str
    message: str
    stack: str | None
    screen: str | None
    app_version: str | None
    platform: str | None
    os_version: str | None
    device: str | None


class IngestOut(BaseModel):
    #: چند تا تازه بودند. بقیه یعنی همان صف دوباره فرستاده شده — که خطا نیست.
    stored: int
    duplicates: int


def _optional_user(db: Session, authorization: str | None) -> User | None:
    """کاربر را از توکن درمی‌آورد اگر بود و معتبر بود؛ وگرنه None.

    عمداً از `get_principal` استفاده نمی‌شود: آن زمینه‌ی مستأجر را روی تراکنش
    می‌نشاند و برای جدولی که *سراسری* است هم بی‌مورد است هم گمراه‌کننده. اینجا
    فقط «این گزارش از کدام کاربر آمد» را می‌خواهیم، و نبودنش خطا نیست.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    claims = decode_access_token(authorization.split(" ", 1)[1].strip())
    if claims is None:
        return None
    return db.get(User, claims.user_id)


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=IngestOut)
def ingest(
    payload: ClientErrorBatchIn,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> IngestOut:
    """گزارش‌ها را ثبت می‌کند. اگر توکنِ معتبری همراه بود، به کاربر هم می‌چسبد."""
    user = _optional_user(db, authorization)
    if not payload.reports:
        return IngestOut(stored=0, duplicates=0)

    incoming = {r.id: r for r in payload.reports}
    already = set(
        db.execute(
            select(ClientError.client_id).where(ClientError.client_id.in_(incoming.keys()))
        ).scalars()
    )

    stored = 0
    for client_id, r in incoming.items():
        if client_id in already:
            continue
        db.add(
            ClientError(
                id=uuid4(),
                client_id=client_id,
                occurred_at=r.at,
                fatal=r.fatal,
                name=r.name,
                # بریدن به‌جای رد کردن: گزارشِ بریده از هیچ گزارشی بهتر است.
                message=r.message[:MAX_MESSAGE],
                stack=r.stack[:MAX_STACK] if r.stack else None,
                screen=r.screen,
                app_version=r.app_version,
                platform=r.platform,
                os_version=r.os_version,
                device=r.device,
                user_id=user.id if user else None,
            )
        )
        stored += 1

    db.commit()
    return IngestOut(stored=stored, duplicates=len(incoming) - stored)


#: خواندنِ گزارش‌ها به `app/routers/admin_errors.py` منتقل شد تا کنارِ بقیه‌ی
#: `/api/admin/*` باشد. ingestِ بالا عمداً اینجا و عمومی می‌ماند: مرورگری که در
#: حالِ سقوط است هنوز توکنِ معتبر ندارد.
