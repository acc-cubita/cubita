"""حسابرسی — درخواست، تأیید، دسترسی و اجرای بررسی.

**هیچ‌چیز مداوم نیست.** کلِ نویسنده‌های `assurance_runs` سه‌تا هستند و هر سه در
همین فایل‌اند: تأییدِ قرارداد، اجرای دستیِ کاربر/حسابرس، و اجرای ستادی. نه کرونی
هست، نه هوکِ flush، نه کارِ پس‌زمینه. این تصمیمِ صریحِ مالکِ محصول بود: محاسبه با
تأیید انجام می‌شود و با درخواست به‌روز.

**موتور این‌جا نیست.** `run_snapshot` هیچ کوئری‌ای روی دفتر نمی‌زند؛ همان
`integrity.run_integrity_check` را با هر دو خانواده صدا می‌زند و نتیجه را ثبت
می‌کند. یعنی صفحه‌ی «بررسی یکپارچگی»ِ حسابدار و کارنامه‌ی حسابرس هرگز نمی‌توانند
دو جوابِ متفاوت بدهند.
"""
from __future__ import annotations

from datetime import date as date_
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assurance import (
    OPEN_ENGAGEMENT_STATUSES,
    AssuranceEngagement,
    AssuranceFinding,
    AssuranceRun,
)
from app.models.tenant import Membership
from app.models.user import User
from app.services import assurance_access, assurance_score, integrity
from app.services import members as members_service
from app.services.numbering import next_document_number
from app.services.reports import ReportFilters

#: سقفِ ردیفِ ذخیره‌شده در هر بررسیِ یک اجرا. بیشتر از سقفِ نمایشِ ابزارِ زنده،
#: چون snapshot باید بعداً هم قابلِ استناد باشد.
SNAPSHOT_ROW_LIMIT = 200

#: فاصله‌ی لازم بینِ دو اجرا. هر اجرا هزینه‌ی خواندنِ کلِ دفتر را دارد، و دکمه‌ای
#: که ده بار پشتِ‌هم زده شود نباید ده بار آن را بپردازد.
REFRESH_COOLDOWN = timedelta(minutes=5)

#: مهلتِ پیش‌فرضِ دسترسیِ حسابرس، اگر ستاد عددی ندهد.
DEFAULT_ACCESS_DAYS = 90

#: نقشی که عضویتِ موقتِ حسابرس با آن ساخته می‌شود (`DEFAULT_ROLES`).
AUDITOR_ROLE_KEY = "auditor"

#: گذارهای مجاز. نبودنِ یک جفت یعنی رد — نه استثنا، نه «فعلاً بگذار بشود».
_ALLOWED: dict[str, tuple[str, ...]] = {
    "requested": ("approved", "rejected"),
    "approved": ("active", "closed"),
    "active": ("closed",),
    "rejected": (),
    "closed": (),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _assert_transition(current: str, new: str) -> None:
    if new not in _ALLOWED.get(current, ()):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"گذار از «{current}» به «{new}» مجاز نیست",
        )


# ── سمتِ مشتری ───────────────────────────────────────────────────────────────


def own_engagement(db: Session, tenant_id: UUID) -> AssuranceEngagement | None:
    """آخرین قراردادِ همین کسب‌وکار.

    **تنها درِ خواندنِ مستأجری.** جدول سراسری است، پس فیلترِ `tenant_id` اگر یک
    جا جا بیفتد، قرارداد و نامِ حسابرس و نمره‌ی یک مشتریِ دیگر لو می‌رود. یک تابع
    یعنی یک جا برای درست‌بودن و یک جا برای تست‌کردن.
    """
    return (
        db.query(AssuranceEngagement)
        .filter(AssuranceEngagement.tenant_id == tenant_id)
        .order_by(AssuranceEngagement.requested_at.desc())
        .first()
    )


def request_engagement(
    db: Session,
    tenant_id: UUID,
    user: User,
    *,
    period_from: date_ | None,
    period_to: date_ | None,
    contact_phone: str,
    note: str,
) -> AssuranceEngagement:
    """ثبتِ درخواستِ حسابرسی توسطِ مشتری."""
    if period_from and period_to and period_to < period_from:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "پایانِ دوره نمی‌تواند پیش از آغازش باشد")

    existing = (
        db.query(AssuranceEngagement)
        .filter(
            AssuranceEngagement.tenant_id == tenant_id,
            AssuranceEngagement.status.in_(OPEN_ENGAGEMENT_STATUSES),
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "برای این کسب‌وکار یک درخواستِ حسابرسیِ باز وجود دارد",
        )

    engagement = AssuranceEngagement(
        tenant_id=tenant_id,
        status="requested",
        requested_at=_now(),
        requested_by_id=user.id,
        period_from=period_from,
        period_to=period_to,
        contact_phone=(contact_phone or "").strip(),
        request_note=(note or "").strip(),
    )
    db.add(engagement)
    db.flush()
    db.refresh(engagement)
    return engagement


# ── سمتِ ستاد ────────────────────────────────────────────────────────────────


def _auditor_by_email(db: Session, email: str) -> User:
    clean = (email or "").strip().lower()
    auditor = db.query(User).filter(User.email == clean).first()
    if auditor is None:
        #: عمداً کاربر ساخته نمی‌شود: ساختِ حساب کارِ ثبت‌نام و دعوت است که توکنِ
        #: تعیینِ رمز صادر می‌کنند. تکرارش این‌جا یعنی حسابی بی‌رمز.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کاربری با این ایمیل یافت نشد")
    return auditor


def _grant_access(
    db: Session, engagement: AssuranceEngagement, auditor: User, days: int
) -> Membership:
    """عضویتِ موقتِ فقط‌خواندنیِ حسابرس در کسب‌وکارِ مشتری.

    اگر حسابرس از قبل عضوِ این کسب‌وکار باشد ۴۰۹ می‌دهد: تبدیلِ بی‌صدای حسابدارِ
    خودِ مشتری به «حسابرس» هم دسترسی‌اش را می‌بُرد و هم دروغ بود.
    """
    already = (
        db.query(Membership)
        .filter(
            Membership.tenant_id == engagement.tenant_id,
            Membership.user_id == auditor.id,
        )
        .first()
    )
    if (
        already is not None
        and already.id != engagement.auditor_membership_id
        and already.role.key != AUDITOR_ROLE_KEY
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "این کاربر از قبل عضوِ این کسب‌وکار است"
        )
    #: عضویتی که نقشش «حسابرس» است از پرونده‌ی *پیشینِ* همین مشتری مانده (بستنِ
    #: پرونده عضویت را غیرفعال می‌کند، حذف نمی‌کند — ردِ «چه کسی و تا کی» باید
    #: بماند). همان ردیف دوباره فعال می‌شود، وگرنه حسابرسی که پارسال این پرونده
    #: را داشت برای حسابرسیِ امسالِ همان مشتری تا ابد ۴۰۹ می‌گرفت.

    role = members_service._role_by_key(db, engagement.tenant_id, AUDITOR_ROLE_KEY)
    membership = already or Membership(
        tenant_id=engagement.tenant_id, user_id=auditor.id, role_id=role.id
    )
    membership.role_id = role.id
    membership.status = "active"
    db.add(membership)
    db.flush()

    engagement.auditor_user_id = auditor.id
    engagement.auditor_membership_id = membership.id
    engagement.access_expires_at = _now() + timedelta(days=max(1, days))
    assurance_access.sync_membership(db, engagement)
    return membership


def approve(
    db: Session,
    engagement: AssuranceEngagement,
    actor: User,
    *,
    auditor_email: str,
    days: int = DEFAULT_ACCESS_DAYS,
    period_from: date_ | None = None,
    period_to: date_ | None = None,
) -> AssuranceEngagement:
    """تأییدِ درخواست: گمارشِ حسابرس، بازکردنِ دسترسی، و اولین اجرای بررسی.

    **اگر اجرا خطا بدهد، تأیید پابرجا می‌ماند.** دفترِ خرابِ مشتری نباید جلوی
    بازشدنِ دسترسیِ حسابرس را بگیرد — درست همان مشتری بیش از همه به حسابرس نیاز
    دارد. کارتابل «هنوز بررسی نشده» نشان می‌دهد و دکمه‌ی اجرای دوباره دارد.
    """
    _assert_transition(engagement.status, "approved")
    auditor = _auditor_by_email(db, auditor_email)

    if period_from is not None:
        engagement.period_from = period_from
    if period_to is not None:
        engagement.period_to = period_to

    engagement.status = "approved"
    engagement.decided_at = _now()
    engagement.decided_by_id = actor.id
    engagement.reject_reason = ""
    _grant_access(db, engagement, auditor, days)
    db.flush()

    try:
        run_snapshot(db, engagement, actor, trigger="approval")
    except Exception:  # noqa: BLE001 — دفترِ خراب نباید تأیید را برگرداند
        db.flush()

    db.refresh(engagement)
    return engagement


def reject(
    db: Session, engagement: AssuranceEngagement, actor: User, *, reason: str
) -> AssuranceEngagement:
    _assert_transition(engagement.status, "rejected")
    engagement.status = "rejected"
    engagement.decided_at = _now()
    engagement.decided_by_id = actor.id
    engagement.reject_reason = (reason or "").strip()
    db.flush()
    db.refresh(engagement)
    return engagement


def assign(
    db: Session,
    engagement: AssuranceEngagement,
    actor: User,
    *,
    auditor_email: str,
    days: int | None = None,
) -> AssuranceEngagement:
    """تعویضِ حسابرس روی قراردادِ باز.

    عضویتِ حسابرسِ قبلی بسته می‌شود، چون گمارشِ تازه یعنی قبلی دیگر کاری با این
    پرونده ندارد.
    """
    if engagement.status not in ("approved", "active"):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "فقط روی قراردادِ تأییدشده می‌شود حسابرس گماشت"
        )
    auditor = _auditor_by_email(db, auditor_email)
    previous = (
        db.get(Membership, engagement.auditor_membership_id)
        if engagement.auditor_membership_id
        else None
    )
    if previous is not None and previous.user_id != auditor.id:
        previous.status = "disabled"
        previous.expires_at = _now()
        engagement.auditor_membership_id = None

    remaining = days if days is not None else _remaining_days(engagement)
    _grant_access(db, engagement, auditor, remaining)
    engagement.decided_by_id = actor.id
    db.flush()
    db.refresh(engagement)
    return engagement


def extend(
    db: Session, engagement: AssuranceEngagement, *, days: int
) -> AssuranceEngagement:
    """تمدیدِ مهلتِ دسترسی — از «حالا»، نه از انقضای قبلی.

    تمدید از انقضای گذشته یعنی تمدیدِ یک‌روزه روی مهلتی که ده روز پیش تمام شده،
    هیچ دسترسی‌ای باز نمی‌کرد و پشتیبانی فکر می‌کرد کارش را کرده است.
    """
    if engagement.status not in ("approved", "active"):
        raise HTTPException(status.HTTP_409_CONFLICT, "این قرارداد باز نیست")
    base = max(engagement.access_expires_at or _now(), _now())
    engagement.access_expires_at = base + timedelta(days=max(1, days))
    assurance_access.sync_membership(db, engagement)
    db.flush()
    db.refresh(engagement)
    return engagement


def close(
    db: Session, engagement: AssuranceEngagement, *, note: str = ""
) -> AssuranceEngagement:
    """پایانِ پرونده — دسترسیِ حسابرس بی‌درنگ بسته می‌شود."""
    _assert_transition(engagement.status, "closed")
    engagement.status = "closed"
    engagement.closed_at = _now()
    engagement.close_note = (note or "").strip()
    assurance_access.sync_membership(db, engagement)
    db.flush()
    db.refresh(engagement)
    return engagement


def _remaining_days(engagement: AssuranceEngagement) -> int:
    if engagement.access_expires_at is None:
        return DEFAULT_ACCESS_DAYS
    left = (engagement.access_expires_at - _now()).days
    return max(1, left)


# ── اجرای بررسی ──────────────────────────────────────────────────────────────


def assert_can_refresh(db: Session, engagement: AssuranceEngagement) -> None:
    """خنک‌کننده: دو اجرا در پنج دقیقه یعنی دو بار خواندنِ کلِ دفتر، بی‌فایده."""
    if engagement.last_run_at is None:
        return
    elapsed = _now() - engagement.last_run_at
    if elapsed < REFRESH_COOLDOWN:
        left = int((REFRESH_COOLDOWN - elapsed).total_seconds() // 60) + 1
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"بررسی به‌تازگی اجرا شده — {left} دقیقه‌ی دیگر دوباره تلاش کنید",
        )


def run_snapshot(
    db: Session, engagement: AssuranceEngagement, user: User, *, trigger: str
) -> AssuranceRun:
    """اجرای بررسی‌ها و ثبتِ عکسِ نتیجه."""
    filters = ReportFilters(
        date_from=engagement.period_from, date_to=engagement.period_to
    )
    report = integrity.run_integrity_check(
        db,
        filters,
        families=(integrity.FAMILY_LEDGER, integrity.FAMILY_ASSURANCE),
        row_limit=SNAPSHOT_ROW_LIMIT,
    )
    scored = assurance_score.score_report(report)

    run = AssuranceRun(
        tenant_id=engagement.tenant_id,
        engagement_id=engagement.id,
        number=next_document_number(db, "assurance_run"),
        ran_at=_now(),
        ran_by_id=user.id,
        trigger=trigger,
        date_from=engagement.period_from,
        date_to=engagement.period_to,
        score=scored["score"],
        grade=scored["grade"],
        error_count=scored["error_count"],
        warning_count=scored["warning_count"],
        finding_count=scored["finding_count"],
        total_debit=Decimal(report["total_debit"]),
        total_credit=Decimal(report["total_credit"]),
        summary=scored["summary"],
    )
    db.add(run)
    db.flush()

    for check in report["checks"]:
        for seq, row in enumerate(check["rows"]):
            db.add(
                AssuranceFinding(
                    tenant_id=engagement.tenant_id,
                    run_id=run.id,
                    check_key=check["key"],
                    severity=check["severity"],
                    seq=seq,
                    label=str(row["label"])[:300],
                    detail=str(row["detail"]),
                    debit=Decimal(row["debit"]),
                    credit=Decimal(row["credit"]),
                    difference=Decimal(row["difference"]),
                    entry_id=row["entry_id"],
                    account_id=row["account_id"],
                    item_id=row["item_id"],
                )
            )

    engagement.last_run_id = run.id
    engagement.last_score = run.score
    engagement.last_run_at = run.ran_at
    if engagement.status == "approved":
        #: اولین اجرا، پرونده را از «تأییدشده» به «در جریان» می‌برد.
        engagement.status = "active"
    db.flush()
    db.refresh(run)
    return run
