from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry
from app.models.period_close import FiscalPeriodClose
from app.models.user import User
from app.schemas.period_close import FiscalPeriodCloseIn
from app.services import chart_codes as cc
from app.services.common import get_account


def get_latest_close_date(db: Session) -> date | None:
    latest = db.query(FiscalPeriodClose).order_by(FiscalPeriodClose.closing_date.desc()).first()
    return latest.closing_date if latest else None


def assert_period_open(db: Session, entry_date: date) -> None:
    """باید در ابتدای هر عملیاتی که سند حسابداری/تاریخچه‌ی مالی می‌سازد صدا زده شود تا از ثبت در دوره‌ی بسته‌شده جلوگیری کند.

    دو قفل پشتِ سرِ هم: تاریخ باید در یک **سال مالیِ باز** باشد (اگر سال مالی تعریف
    شده باشد) و بعد از آخرین **بستنِ دوره**. ایمپورت داخلِ تابع است چون سرویسِ سال
    مالی برای بستن به همین ماژول نیاز دارد.
    """
    from app.services.fiscal_year import assert_within_fiscal_year

    assert_within_fiscal_year(db, entry_date)
    latest = get_latest_close_date(db)
    if latest is not None and entry_date <= latest:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"دوره مالی تا تاریخ {latest} رسماً بسته شده؛ ثبت سند با تاریخ {entry_date} مجاز نیست",
        )


def close_period(db: Session, data: FiscalPeriodCloseIn, user: User) -> FiscalPeriodClose:
    """قفلِ رسمیِ دوره — **گامِ دوم**، پس از بستنِ حساب‌های سود و زیان.

    تا پیش از این، این تابع خودش ردیف‌های سند را می‌ساخت. حالا ساختِ سند یک‌جا در
    `accounting_ops.issue_pnl_close` است و این‌جا فقط صدا زده می‌شود؛ کاربر می‌تواند
    گامِ اول را جدا بزند، سند را ببیند، و بعد قفل کند.

    **قفل برگشت ندارد** — نه حذفی هست نه بازگشایی. پس هرچه پیش از آن دیده شود، سود.
    """
    #: درون‌تابعی، چون `accounting_ops` در سطحِ ماژول از همین‌جا
    #: `assert_period_open` را می‌گیرد.
    from app.services.accounting_ops import issue_pnl_close, pnl_close_entry_in

    previous_close_date = get_latest_close_date(db)
    if previous_close_date is not None and data.closing_date <= previous_close_date:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"تاریخ بستن باید بعد از آخرین دوره‌ی بسته‌شده ({previous_close_date}) باشد",
        )

    date_from = previous_close_date + timedelta(days=1) if previous_close_date else None
    existing = pnl_close_entry_in(db, date_from, data.closing_date)
    if existing is None:
        # گامِ اول زده نشده — همین‌جا زده می‌شود تا رفتارِ «یک دکمه» برای کسی که
        # مستقیم قفل می‌کند عوض نشود.
        out = issue_pnl_close(
            db, user, data.closing_date, f"سند بستن دوره مالی تا تاریخ {data.closing_date}"
        )
        journal_entry_id = out["entry_id"]
        net_profit = Decimal(out["net_profit"])
    else:
        # سند از قبل هست؛ سندِ دوم زده **نمی‌شود**. سود/زیان از خودِ همان سند
        # خوانده می‌شود — نه یک محاسبه‌ی دوم که می‌تواند با سند نخواند.
        journal_entry_id = existing.id
        destination_id = get_account(db, cc.RETAINED_EARNINGS).id
        net_profit = sum(
            (
                Decimal(line.credit) - Decimal(line.debit)
                for line in existing.lines
                if line.account_id == destination_id
            ),
            Decimal(0),
        )

    # بستنِ رسمیِ دوره یعنی هرچه در آن بازه است دیگر قابلِ بازبینی نیست — پس اسنادِ
    # موقتِ داخلِ دوره (و خودِ سندِ بستن) همین‌جا دائم می‌شوند. اگر این‌جا نبود، دوره‌ی
    # قفل‌شده پر از سندِ «موقت»ی می‌ماند که هیچ‌وقت نمی‌شد قطعی‌شان کرد.
    finalize_query = db.query(JournalEntry).filter(
        JournalEntry.status == "temporary",
        JournalEntry.entry_date <= data.closing_date,
    )
    if date_from is not None:
        finalize_query = finalize_query.filter(JournalEntry.entry_date >= date_from)
    now = datetime.now(timezone.utc)
    for pending in finalize_query.all():
        pending.status = "permanent"
        pending.finalized_at = now
        pending.finalized_by_id = user.id

    close = FiscalPeriodClose(
        closing_date=data.closing_date,
        net_profit=net_profit,
        notes=data.notes,
        journal_entry_id=journal_entry_id,
        created_by_id=user.id,
    )
    db.add(close)
    db.flush()
    db.refresh(close)
    return close
