"""چرخه‌ی عمرِ حسابِ آزمایشی — یادآوری و حذف. برای اجرای روزانه با کرون.

سه رفتار در این سیستم وجود دارد و **فقط دوتاش کرون می‌خواهد**:
- «قفلِ روزِ ۱۴» خودکار است: `deps` هر درخواستِ آزمایشیِ منقضی را می‌بندد، پس نیازی به
  تغییرِ وضعیت توسط کرون نیست.
- «یادآوری» و «حذف» زماندارند و بدونِ یک اجرای دوره‌ای اتفاق نمی‌افتند — همین‌جا.

**چرا حذف یک بافرِ ایمنی دارد:** trial_purge_grace_days بعد از انقضا صبر می‌کنیم تا
خریدِ دیرهنگام (روزِ ۱۵، ۱۶، ...) هنوز دیتا را نجات دهد. حذفِ دقیقاً سرِ روزِ ۱۴،
کاربری را که یک روز دیر تصمیم گرفته برای همیشه از دست می‌داد.

**چرا یادآوری فقط ایمیل است (فعلاً):** خطِ اشتراکیِ ملی‌پیامک فقط الگوی تأییدشده
می‌فرستد و الگوی فعلی مخصوصِ «کدِ تأیید» است. یادآوریِ پیامکی به یک الگوی تازه‌ی
تأییدشده نیاز دارد؛ تا آن زمان ایمیل مسیرِ مطمئن است. [[sms-activation-last]]
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.tenant import Membership, Tenant
from app.models.user import User
from app.services import mailer
from app.services.provisioning import purge_tenant
from app.services.subscriptions import current_subscription, trial_info


def _owner(db: Session, tenant_id) -> User | None:
    """کاربرِ مالکِ حسابِ آزمایشی. حسابِ تازه‌ی ثبت‌نامی یک عضو دارد؛ اولین عضویتِ فعال کافی است."""
    membership = (
        db.query(Membership)
        .filter(Membership.tenant_id == tenant_id, Membership.status == "active")
        .first()
    )
    return db.get(User, membership.user_id) if membership else None


def _plans_url() -> str:
    return f"{get_settings().marketing_site_url.rstrip('/')}/#pricing"


def process_trials(db: Session, *, now: datetime | None = None) -> dict:
    """یک بار روی همه‌ی حساب‌های آزمایشی می‌گذرد: یادآوری و حذف. خلاصه را برمی‌گرداند.

    خودش commit نمی‌کند — فراخواننده (کرون یا تست) تراکنش را می‌بندد، تا در تست بشود
    اثر را قبل از commit سنجید.
    """
    settings = get_settings()
    now = now or datetime.now(timezone.utc)

    trials = db.query(Tenant).filter(Tenant.is_trial.is_(True), Tenant.status == "active").all()
    reminded = purged = 0

    for tenant in trials:
        info = trial_info(db, tenant, now=now)
        if info.days_left is None:
            continue

        # یادآوری — یک بار، وقتی به آستانه رسید و هنوز منقضی نشده.
        if (
            not info.expired
            and info.days_left <= settings.trial_reminder_days_before
            and tenant.trial_reminder_sent_at is None
        ):
            owner = _owner(db, tenant.id)
            if owner is not None and owner.email:
                mailer.send_trial_reminder(owner.email, owner.name, max(info.days_left, 0), _plans_url())
            tenant.trial_reminder_sent_at = now
            db.flush()
            reminded += 1

        # حذف — فقط بعد از انقضا + بافرِ ایمنی.
        if info.expired:
            sub = current_subscription(db, tenant.id)
            if sub is not None:
                expires = sub.expires_at
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if now > expires + timedelta(days=settings.trial_purge_grace_days):
                    purge_tenant(db, tenant.id)
                    purged += 1

    return {"trials": len(trials), "reminded": reminded, "purged": purged}
