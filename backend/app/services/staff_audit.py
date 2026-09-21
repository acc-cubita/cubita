"""ثبتِ ردِ کارهای ستاد.

**ثبت اینجا صریح است، نه خودکار** — عمداً برعکسِ `app/audit.py` که با قلابِ
`before_flush` دیفِ ORM را می‌گیرد. دو دلیل:

۱. کارِ ستاد یک **قصد** است نه یک دیف. «تعلیق شد چون فاکتور پرداخت نشده» چیزی
   است که شش ماه بعد کسی می‌پرسد؛ «`status` از `active` به `suspended` رفت» نیست.
۲. این کنش‌ها روی جدول‌های سراسری‌ای می‌نشینند که هیچ قلابِ امروزی پوششان نمی‌دهد،
   و بعضی‌شان (حذفِ اکانت) اصلاً از راهِ ORM نمی‌گذرند.

بهای صراحت این است که می‌شود فراموشش کرد. مهارش `tests/test_staff_audit_coverage.py`
است که روی `app.routes` راه می‌رود — **یک دزدگیرِ دود، نه یک تضمین**: چون متنِ
منبع را می‌خواند، فراخوانیِ غیرمستقیم از راهِ یک helper را نمی‌بیند.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.staff_audit import StaffAuditLog

#: کنش‌های شناخته‌شده. تستِ پوشش این فهرست را می‌خواند، و نامِ تازه‌ای که اینجا
#: نباشد یعنی کسی بدونِ فکر کردن به «این در گزارش چه شکلی دیده می‌شود» ثبت کرده.
ACTIONS = frozenset(
    {
        "login",
        "password_change",
        "staff_create",
        "staff_role_change",
        "staff_disable",
        "staff_reset_password",
        "account_create",
        "account_extend",
        "account_status",
        "account_kind",
        "account_industry",
        "account_modules",
        "account_reset_password",
        "account_delete",
        "purchase_fulfill",
        "commission_settle",
        "assurance_approve",
        "assurance_reject",
        "assurance_assign",
        "assurance_extend",
        "assurance_run",
        "assurance_close",
        "plan_create",
        "plan_update",
        "plan_deactivate",
        "support_session_open",
        "support_session_revoke",
    }
)


def record(
    db: Session,
    staff,
    action: str,
    *,
    summary: str,
    target_type: str | None = None,
    target_id: UUID | None = None,
    target_label: str | None = None,
    tenant_id: UUID | None = None,
    details: dict | None = None,
) -> StaffAuditLog:
    """یک ردِ ستادی می‌نویسد و **بی‌درنگ flush می‌کند**.

    flush عمدی است: کنشِ بعدی ممکن است خودِ هدف را نابود کند (`purge_tenant`)، و
    ردی که هنوز در صفِ session نشسته باشد ترتیبش تضمین‌شده نیست. اگر تراکنش
    rollback شود ردش هم می‌رود — که درست است، چون کاری هم انجام نشده.

    `staff` یک `StaffPrincipal` است؛ ایمیل و نقش از آن **اسنپ‌شات** می‌شوند نه
    join، تا رد بعد از حذفِ خودِ کاربر هم خوانا بماند.
    """
    assert action in ACTIONS, f"کنشِ ناشناخته‌ی ستاد: {action}"
    row = StaffAuditLog(
        actor_user_id=staff.user.id,
        actor_email=staff.email,
        actor_role=staff.role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_label=(target_label or None) and target_label[:200],
        tenant_id=tenant_id,
        summary=summary,
        details=details,
        ip=staff.ip,
        request_id=staff.request_id,
        via=staff.via,
    )
    db.add(row)
    db.flush()
    return row
