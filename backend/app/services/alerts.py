"""مرکز هشدارها — «امروز به چه چیزی باید رسیدگی شود؟».

هیچ داده‌ی تازه‌ای ذخیره نمی‌کند؛ فقط از ماژول‌های موجود (چک، مطالبات، سقف اعتبار،
اسناد تکرارشونده، تقویم، انبار) آیتم‌های قابلِ‌اقدام را زنده جمع می‌کند و یک‌جا با
شدت (danger/warning/info) و ارجاع به رکورد برمی‌گرداند. چون فقط خواندنی است، نه
مهاجرت لازم دارد نه سند می‌سازد — کم‌ریسک‌ترین شکلِ یک ماژول.

پیامک/ایمیل عمداً اینجا نیست: ترانسپورتِ بیرونی به providerِ ایرانی و کلید نیاز
دارد؛ وقتی provider تعیین شد، همین آیتم‌ها را می‌توان از این‌جا فرستاد.
"""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.banking import Check
from app.models.calendar import CalendarEvent
from app.models.inventory import Contact, Item, StockLedger
from app.models.recurring import RecurringJournalEntry
from app.services.reports import get_aging

#: چک تا این تعداد روزِ آینده «نزدیک سررسید» شمرده می‌شود.
CHECK_DUE_DAYS = 7
#: یادآوریِ تقویم تا این تعداد روزِ آینده هشدار می‌دهد.
CALENDAR_LOOKAHEAD_DAYS = 3
#: چک‌هایی که هنوز تعیین‌تکلیف نشده‌اند (وصول/برگشت/خرج نشده).
_ACTIVE_CHECK_STATUSES = ("in_hand", "deposited", "issued")


def get_alerts(db: Session, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    items: list[dict] = []

    # ۱) چک‌های نزدیک سررسید یا سررسیدگذشته که هنوز فعال‌اند
    horizon = as_of + timedelta(days=CHECK_DUE_DAYS)
    checks = (
        db.query(Check)
        .filter(Check.status.in_(_ACTIVE_CHECK_STATUSES), Check.due_date <= horizon)
        .order_by(Check.due_date)
        .all()
    )
    for c in checks:
        overdue = c.due_date < as_of
        kind = "دریافتنی" if c.type == "receivable" else "پرداختنی"
        items.append(
            {
                "category": "check",
                "severity": "danger" if overdue else "warning",
                "title": f"چک {kind} شماره {c.number}",
                "detail": f"{c.bank_name} — {'سررسید گذشته' if overdue else 'نزدیک سررسید'}".strip(" —"),
                "alert_date": c.due_date,
                "amount": Decimal(c.amount),
                "ref_id": c.id,
            }
        )

    # ۲ و ۳) از تحلیل سنیِ مطالبات: معوقات + عبور از سقف اعتبار (یک کوئری، دو هشدار)
    aging = get_aging(db, "receivable", as_of)
    limits = {
        c.id: Decimal(c.credit_limit or 0)
        for c in db.query(Contact).filter(Contact.credit_limit > 0).all()
    }
    for row in aging["rows"]:
        over_90 = Decimal(row["over_90"])
        overdue_amt = Decimal(row["d61_90"]) + over_90
        if overdue_amt > 0:
            items.append(
                {
                    "category": "receivable",
                    "severity": "danger" if over_90 > 0 else "warning",
                    "title": f"مطالبات معوق: {row['contact_name']}",
                    "detail": "بیش از ۹۰ روز" if over_90 > 0 else "۶۱ تا ۹۰ روز",
                    "alert_date": None,
                    "amount": overdue_amt,
                    "ref_id": row["contact_id"],
                }
            )
        limit = limits.get(row["contact_id"])
        if limit is not None and Decimal(row["total"]) > limit:
            items.append(
                {
                    "category": "credit",
                    "severity": "danger",
                    "title": f"عبور از سقف اعتبار: {row['contact_name']}",
                    "detail": "مانده از سقف مجاز گذشته",
                    "alert_date": None,
                    "amount": Decimal(row["total"]) - limit,
                    "ref_id": row["contact_id"],
                }
            )

    # ۴) اسناد تکرارشونده‌ی سررسیدشده
    due_templates = (
        db.query(RecurringJournalEntry)
        .filter(RecurringJournalEntry.is_active.is_(True), RecurringJournalEntry.next_run_date <= as_of)
        .order_by(RecurringJournalEntry.next_run_date)
        .all()
    )
    for t in due_templates:
        items.append(
            {
                "category": "recurring",
                "severity": "info",
                "title": f"سند تکرارشونده سررسید: {t.title}",
                "detail": "آماده‌ی تولید",
                "alert_date": t.next_run_date,
                "amount": sum((Decimal(line.debit) for line in t.lines), Decimal(0)),
                "ref_id": t.id,
            }
        )

    # ۵) یادآوری‌های تقویم که گذشته یا پیش‌رو و هنوز انجام‌نشده‌اند
    cal_horizon = as_of + timedelta(days=CALENDAR_LOOKAHEAD_DAYS)
    events = (
        db.query(CalendarEvent)
        .filter(CalendarEvent.is_done.is_(False), CalendarEvent.event_date <= cal_horizon)
        .order_by(CalendarEvent.event_date)
        .all()
    )
    for e in events:
        overdue = e.event_date < as_of
        items.append(
            {
                "category": "calendar",
                "severity": "danger" if overdue else "info",
                "title": e.title,
                "detail": "یادآوری گذشته" if overdue else "یادآوری پیش‌رو",
                "alert_date": e.event_date,
                "amount": None,
                "ref_id": e.id,
            }
        )

    # ۶) موجودی منفی (خطای یکپارچگیِ داده — نیازمند رسیدگی)
    negatives = (
        db.query(StockLedger.item_id, func.coalesce(func.sum(StockLedger.qty), 0).label("qty"))
        .group_by(StockLedger.item_id)
        .having(func.coalesce(func.sum(StockLedger.qty), 0) < 0)
        .all()
    )
    if negatives:
        names = {i.id: i.name for i in db.query(Item).all()}
        for item_id, qty in negatives:
            items.append(
                {
                    "category": "stock",
                    "severity": "danger",
                    "title": f"موجودی منفی: {names.get(item_id, '—')}",
                    "detail": f"موجودی {qty}",
                    "alert_date": None,
                    "amount": None,
                    "ref_id": item_id,
                }
            )

    counts: dict[str, int] = {}
    for it in items:
        counts[it["category"]] = counts.get(it["category"], 0) + 1

    return {"as_of": as_of, "total": len(items), "counts": counts, "items": items}
