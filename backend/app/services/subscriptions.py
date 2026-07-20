"""وضعیت اشتراک، و اینکه انقضا چه چیزی را محدود می‌کند.

**مهم‌ترین تصمیم این پرونده: انقضا دسترسی به دفتر را قطع نمی‌کند.**

دفاتر مالی سند قانونی خودِ مشتری‌اند. قفل کردنشان پشت پرداخت یعنی گروگان گرفتن
چیزی که مال ما نیست — و مشتری‌ای که نتواند اظهارنامه‌ی مالیاتی‌اش را دربیاورد
هرگز برنمی‌گردد. پس انقضا یعنی **فقط‌خواندنی**: دیدن، گزارش، چاپ و خروجی همیشه
باز می‌ماند؛ فقط ثبت سند تازه بسته می‌شود.

**چرا مهلت ارفاق:** تمدید دیرکرد دارد — حواله بانکی، تعطیلات، آدم مرخصی. قطع
ناگهانی در روز انقضا یک کسب‌وکار را وسط ماه زمین می‌زند به‌خاطر تأخیری که ممکن
است تقصیر او هم نباشد.

**چرا نبودِ اشتراک باز است و نه بسته:** برخلاف امنیت، اینجا fail-open درست است.
اشتباهِ بستن یعنی مشتری پولی از دفتر خودش بیرون می‌ماند؛ اشتباهِ باز گذاشتن یعنی
یک ماه رایگان. این دو هزینه اصلاً هم‌اندازه نیستند. مستأجرهای قدیمی هم که پیش از
وجود این جدول ساخته شده‌اند نباید با یک استقرار قفل شوند.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.subscription import Subscription

#: بعد از انقضا، این مدت هنوز همه‌چیز کار می‌کند.
GRACE_DAYS = 14

#: اکشن‌هایی که داده‌ی مالی می‌سازند یا عوض می‌کنند. خواندن اینجا نیست و عمداً
#: هرگز محدود نمی‌شود.
WRITE_ACTIONS = frozenset({"create", "update", "delete", "approve"})


@dataclass(frozen=True)
class SubscriptionState:
    #: active | grace | expired | cancelled | none
    status: str
    expires_at: datetime | None
    days_left: int | None

    @property
    def can_write(self) -> bool:
        return self.status in ("active", "grace", "none")

    @property
    def should_warn(self) -> bool:
        """آیا به کاربر هشدار نشان داده شود؟"""
        if self.status in ("grace", "expired", "cancelled"):
            return True
        return self.days_left is not None and self.days_left <= 14


def current_subscription(db: Session, tenant_id: UUID) -> Subscription | None:
    """آخرین دوره‌ی این کسب‌وکار — یعنی آنی که دیرتر از همه تمام می‌شود.

    مرتب‌سازی روی expires_at است و نه created_at: تمدیدی که زودتر ثبت شده ولی
    دورهٔ بلندتری دارد باید برنده باشد.
    """
    return (
        db.query(Subscription)
        .filter(Subscription.tenant_id == tenant_id)
        .order_by(Subscription.expires_at.desc())
        .first()
    )


def state_for(db: Session, tenant_id: UUID, *, now: datetime | None = None) -> SubscriptionState:
    now = now or datetime.now(timezone.utc)
    sub = current_subscription(db, tenant_id)

    if sub is None:
        return SubscriptionState(status="none", expires_at=None, days_left=None)

    expires = sub.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    days_left = (expires - now).days

    if sub.cancelled_at is not None and expires <= now:
        return SubscriptionState(status="cancelled", expires_at=expires, days_left=days_left)
    if now <= expires:
        return SubscriptionState(status="active", expires_at=expires, days_left=days_left)
    if now <= expires + timedelta(days=GRACE_DAYS):
        return SubscriptionState(status="grace", expires_at=expires, days_left=days_left)
    return SubscriptionState(status="expired", expires_at=expires, days_left=days_left)


def grant(
    db: Session,
    tenant_id: UUID,
    *,
    days: int,
    plan_id: UUID | None = None,
    purchase_id: UUID | None = None,
    note: str = "",
    source: str = "manual",
    now: datetime | None = None,
) -> Subscription:
    """یک دوره‌ی تازه اضافه می‌کند — و از انتهای دوره‌ی فعلی ادامه می‌دهد، نه از امروز.

    اگر از امروز حساب می‌شد، مشتری‌ای که یک ماه زودتر تمدید می‌کند آن یک ماه را
    از دست می‌داد؛ یعنی سیستم، تمدید زودهنگام را جریمه می‌کند — دقیقاً برعکس
    چیزی که می‌خواهیم.
    """
    now = now or datetime.now(timezone.utc)
    existing = current_subscription(db, tenant_id)

    start = now
    if existing is not None:
        current_end = existing.expires_at
        if current_end.tzinfo is None:
            current_end = current_end.replace(tzinfo=timezone.utc)
        if current_end > now:
            start = current_end

    sub = Subscription(
        tenant_id=tenant_id,
        plan_id=plan_id,
        purchase_id=purchase_id,
        starts_at=start,
        expires_at=start + timedelta(days=days),
        note=note,
        source=source,
    )
    db.add(sub)
    db.flush()
    return sub


def days_for_period(billing_period: str) -> int:
    """طول دوره بر حسب روز. ماه شمسی و میلادی هر دو تقریبی‌اند و اینجا مهم نیست."""
    return 30 if billing_period == "monthly" else 365
