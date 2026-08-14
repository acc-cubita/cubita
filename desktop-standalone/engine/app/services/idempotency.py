"""اجرای یک‌بارِ عملیات، حتی اگر درخواستش چند بار برسد.

سه راهی که امروز یک سند مالی دوباره ثبت می‌شود، و هیچ‌کدام باگ کلاینت نیستند:

  - کاربر روی «ثبت فاکتور» دوبار کلیک می‌کند
  - پاسخ در شبکه گم می‌شود و کلاینت دوباره می‌فرستد (سرور کارش را کرده بود)
  - مرورگر یا پراکسی درخواست را retry می‌کند

هر سه دو فاکتور، دو سند حسابداری و دو حرکت انبار می‌سازند — بدون هیچ خطایی. برای
نرم‌افزار حسابداری این بدترین شکل باگ است، چون فقط دفتر را غلط می‌کند و ساکت است.

**درخواست‌های هم‌زمان با یک کلید:** این‌جا هیچ قفل دستی‌ای نوشته نشده، چون لازم نیست.
قید یکتای (tenant_id, key) خودش سریالیزه می‌کند: درخواست دوم روی INSERT بلاک می‌شود
تا تراکنش اول تمام شود. اگر اول commit کند، دومی خطای یکتایی می‌گیرد و نتیجه‌ی
ذخیره‌شده را برمی‌گرداند؛ اگر اول rollback کند، INSERT دومی موفق می‌شود و خودش
عملیات را انجام می‌دهد. هر دو حالت درست‌اند و هیچ‌کدام کد اضافه نمی‌خواهند.

SAVEPOINT لازم است چون در Postgres بعد از نقض قید، کل تراکنش abort می‌شود و بدون
آن نمی‌شد از خطا برگشت.
"""
import hashlib
import json
import logging
from typing import Any, Callable
from uuid import UUID

from fastapi import HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.idempotency import IdempotencyKey
from app.models.user import User

logger = logging.getLogger(__name__)

HEADER = "Idempotency-Key"
MAX_KEY_LENGTH = 200


def request_fingerprint(payload: BaseModel) -> str:
    """اثر انگشت محتوای درخواست.

    `sort_keys` لازم است: ترتیب کلیدها در JSON معنایی ندارد و بدون مرتب‌سازی، همان
    درخواست با ترتیب متفاوت اثر انگشت متفاوت می‌گرفت و محافظت بی‌اثر می‌شد.
    """
    body = payload.model_dump(mode="json")
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read_key(request: Request) -> str | None:
    raw = request.headers.get(HEADER) or request.headers.get(HEADER.lower())
    if raw is None:
        return None
    key = raw.strip()
    if not key:
        return None
    if len(key) > MAX_KEY_LENGTH:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{HEADER} طولانی‌تر از حد مجاز است")
    return key


def idempotent(
    db: Session,
    request: Request,
    user: User,
    *,
    operation: str,
    payload: BaseModel,
    run: Callable[[], Any],
    replay: Callable[[UUID], Any],
    resource_id: Callable[[Any], UUID] = lambda obj: obj.id,
) -> Any:
    """`run` را اجرا می‌کند، مگر اینکه همین کلید قبلاً اجرا شده باشد.

    بدون هدر، عملیات مثل قبل اجرا می‌شود و هیچ محافظتی وجود ندارد. این عمدی است:
    اجباری کردنش، اپ دسکتاپِ مستقرشده را همان لحظه می‌شکست. ولی نبودِ هدر لاگ
    می‌شود تا معلوم باشد کدام کلاینت هنوز نمی‌فرستد — هدف این است که روزی اجباری شود.
    """
    key = read_key(request)
    if key is None:
        logger.info("درخواست %s بدون %s — بدون محافظت در برابر ارسال تکراری", operation, HEADER)
        return run()

    fingerprint = request_fingerprint(payload)

    try:
        with db.begin_nested():
            db.add(
                IdempotencyKey(
                    key=key,
                    operation=operation,
                    request_hash=fingerprint,
                    created_by_id=user.id,
                )
            )
            db.flush()
        record = None
    except IntegrityError:
        # کلید از قبل هست. تراکنش دیگری یا تمام شده یا همین حالا commit کرد.
        record = db.query(IdempotencyKey).filter(IdempotencyKey.key == key).one_or_none()
        if record is None:
            # نظری غیرمنتظره: قید شکست ولی ردیفی دیده نمی‌شود. fail loud، چون
            # ادامه دادن یعنی احتمال ثبت دوباره‌ی سند مالی.
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "وضعیت نامشخص در بررسی درخواست تکراری؛ لطفاً نتیجه را بررسی کنید و در صورت نیاز دوباره تلاش کنید",
            )

    if record is not None:
        if record.operation != operation or record.request_hash != fingerprint:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"این {HEADER} قبلاً برای درخواست دیگری استفاده شده است. "
                "برای هر عملیات یک کلید تازه بفرستید.",
            )
        if record.resource_id is None:
            # عملیات قبلی نیمه‌کاره مانده (rollback بعد از ثبت کلید). چون نمی‌دانیم
            # سند ساخته شده یا نه، تصمیم به کاربر واگذار می‌شود نه به حدس ما.
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "درخواست قبلی با همین کلید کامل نشد؛ نتیجه را بررسی کنید و با کلید تازه دوباره تلاش کنید",
            )
        logger.info("پاسخ تکراری برای %s با کلید موجود بازپخش شد", operation)
        return replay(record.resource_id)

    result = run()

    stored = db.query(IdempotencyKey).filter(IdempotencyKey.key == key).one()
    stored.resource_id = resource_id(result)
    db.flush()
    return result
