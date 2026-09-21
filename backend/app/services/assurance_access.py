"""دسترسیِ حسابرس — ماژولِ مشتق و عضویتِ موقت.

این فایل عمداً کوچک و بی‌وابستگی است، چون از **داغ‌ترین مسیرِ برنامه** صدا زده
می‌شود: `deps.require_module` و `/api/auth/me`.

دو کارِ جدا انجام می‌دهد که هر دو یک منبعِ حقیقت دارند — ردیفِ قرارداد:

۱. **`derived_modules`** — آیا «پرونده‌ی حسابرسی» برای این کسب‌وکار باز است؟
۲. **`sync_membership`** — عضویتِ موقتِ حسابرس را با وضعیتِ قرارداد هم‌گام می‌کند.
   تنها نویسنده‌ی `Membership.expires_at`/`status` برای حسابرس همین است؛ اگر دو
   جا می‌نوشتند، دیر یا زود قرارداد بسته می‌شد و دسترسی باز می‌ماند.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.assurance import OPEN_ENGAGEMENT_STATUSES, AssuranceEngagement
from app.models.tenant import Membership

#: کلیدِ ماژولی که با قراردادِ باز، باز می‌شود. همان رشته‌ای که در
#: `services/modules.DERIVED_MODULES` و در `PAGE_MODULE_KEY`ِ فرانت آمده.
WORK_MODULE = "assurance_work"


def has_open_engagement(db: Session, tenant_id: UUID) -> bool:
    """آیا این کسب‌وکار قراردادِ حسابرسیِ بازی دارد؟ (یک کوئریِ ایندکس‌خورده)"""
    return (
        db.query(AssuranceEngagement.id)
        .filter(
            AssuranceEngagement.tenant_id == tenant_id,
            AssuranceEngagement.status.in_(("approved", "active")),
        )
        .first()
        is not None
    )


def derived_modules(db: Session, tenant_id: UUID) -> frozenset[str]:
    """ماژول‌های مشتقِ بازِ این کسب‌وکار.

    «درخواست‌شده» کافی **نیست**: تا وقتی ما تأیید نکرده‌ایم، کاربر فقط فرمِ
    درخواست را می‌بیند — همان چیزی که کلِ این ماژول برایش ساخته شد.
    """
    return frozenset({WORK_MODULE}) if has_open_engagement(db, tenant_id) else frozenset()


def sync_membership(db: Session, engagement: AssuranceEngagement) -> Membership | None:
    """عضویتِ حسابرس را با وضعیتِ قرارداد هم‌گام می‌کند.

    - قراردادِ باز  → عضویت فعال با همان مهلتِ `access_expires_at`
    - قراردادِ بسته → عضویت `disabled` (ابطالِ بی‌درنگ در `get_principal`)

    عضویت **حذف نمی‌شود**: ردِ «چه کسی و تا کی دسترسی داشت» باید بماند، و حذفش
    ارجاعِ `auditor_membership_id` را هم می‌شکست.
    """
    if engagement.auditor_membership_id is None:
        return None
    membership = db.get(Membership, engagement.auditor_membership_id)
    if membership is None:
        return None

    if engagement.status in OPEN_ENGAGEMENT_STATUSES:
        membership.status = "active"
        membership.expires_at = engagement.access_expires_at
    else:
        membership.status = "disabled"
        membership.expires_at = engagement.access_expires_at or _now()
    db.flush()
    return membership


def _now() -> datetime:
    return datetime.now(timezone.utc)
