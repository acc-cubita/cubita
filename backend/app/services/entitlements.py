"""چه کسی اجازه‌ی کار با دفتر را دارد — بر پایه‌ی اشتراک (ابر) یا مجوز (سازمانی).

**یک تابع، یک فراخوان.** `deps.require_permission` تنها گلوگاهِ اجازه‌ی نوشتن است و
فقط `enforce` را صدا می‌زند؛ هر دو نسخه از همین یک در رد می‌شوند. اگر شاخه‌ی
سازمانی در سرویس‌ها پخش می‌شد، اولین اندپوینتی که فراموشش می‌کرد، نوشتن را پس از
انقضای مجوز باز می‌گذاشت.

**خواندن هرگز قفل نمی‌شود** — مگر آزمایشیِ منقضیِ ابری (پایین توضیح داده شده). روی
سرورِ خودِ مشتری این اصل حتی واجب‌تر است: داده روی ماشینِ خودشان است و انقضای
مجوز فقط ثبتِ تازه را می‌بندد.
"""

from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.tenant import Tenant
from app.services.subscriptions import WRITE_ACTIONS
from app.services.subscriptions import state_for as subscription_state
from app.services.subscriptions import trial_info


def enforce(db: Session, tenant: Tenant, actions: Iterable[str]) -> None:
    """اگر این کسب‌وکار حقِ این اکشن‌ها را ندارد، ۴۰۲ می‌دهد."""
    if get_settings().is_enterprise:
        _enforce_license(db, tenant, tuple(actions))
    else:
        _enforce_subscription(db, tenant, tuple(actions))


def _enforce_license(db: Session, tenant: Tenant, actions: tuple[str, ...]) -> None:
    """نسخه‌ی سازمانی: وضعیتِ مجوز (M2 — ENTERPRISE_PLAN.md).

    تا وقتی هسته‌ی مجوز ساخته نشده، عمداً هیچ چیز را نمی‌بندد. اشتراکِ ابری هم اینجا
    سنجیده **نمی‌شود**: سرورِ شرکت هرگز اشتراکی ثبت نمی‌کند و کرون‌های ابری رویش
    اجرا نمی‌شوند؛ سنجیدنش فقط یک منبعِ حقیقتِ دوم و نادرست می‌ساخت.
    """


def _enforce_subscription(db: Session, tenant: Tenant, actions: tuple[str, ...]) -> None:
    # آزمایشیِ منقضی: کلِ دفتر قفل می‌شود (خواندن هم)، نه فقط نوشتن. این عمداً
    # سخت‌گیرانه‌تر از انقضای مشتریِ واقعی است — داده‌ی آزمایشی سندِ قانونیِ کسی
    # نیست، و هدفِ قفلِ کامل، سوق دادن به خرید است. /me و /subscription و
    # /billing از require_permission رد نمی‌شوند، پس صفحه‌ی خرید همچنان باز می‌ماند.
    if tenant.is_trial and trial_info(db, tenant).expired:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "دوره‌ی آزمایشیِ رایگان تمام شده است؛ برای ادامه و حفظِ اطلاعات یک پلن تهیه کنید.",
        )

    if any(a in WRITE_ACTIONS for a in actions):
        state = subscription_state(db, tenant.id)
        if not state.can_write:
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED,
                "اشتراک این کسب‌وکار تمام شده است. دفترها و گزارش‌ها در دسترس‌اند "
                "ولی برای ثبت سند تازه باید اشتراک تمدید شود.",
            )
