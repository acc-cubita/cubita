from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import JournalLine
from app.models.period_close import FiscalPeriodClose
from app.models.user import User
from app.schemas.period_close import FiscalPeriodCloseIn
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.reports import get_income_statement


def get_latest_close_date(db: Session) -> date | None:
    latest = db.query(FiscalPeriodClose).order_by(FiscalPeriodClose.closing_date.desc()).first()
    return latest.closing_date if latest else None


def assert_period_open(db: Session, entry_date: date) -> None:
    """باید در ابتدای هر عملیاتی که سند حسابداری/تاریخچه‌ی مالی می‌سازد صدا زده شود تا از ثبت در دوره‌ی بسته‌شده جلوگیری کند."""
    latest = get_latest_close_date(db)
    if latest is not None and entry_date <= latest:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"دوره مالی تا تاریخ {latest} رسماً بسته شده؛ ثبت سند با تاریخ {entry_date} مجاز نیست",
        )


def close_period(db: Session, data: FiscalPeriodCloseIn, user: User) -> FiscalPeriodClose:
    previous_close_date = get_latest_close_date(db)
    if previous_close_date is not None and data.closing_date <= previous_close_date:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"تاریخ بستن باید بعد از آخرین دوره‌ی بسته‌شده ({previous_close_date}) باشد",
        )

    date_from = previous_close_date + timedelta(days=1) if previous_close_date else None
    statement = get_income_statement(db, date_from, data.closing_date)

    journal_lines: list[JournalLine] = []
    for row in statement["income"]:
        if row["balance"] != 0:
            journal_lines.append(
                JournalLine(account_id=row["account_id"], debit=row["balance"], credit=0, description="بستن حساب درآمد")
            )
    for row in statement["expenses"]:
        if row["balance"] != 0:
            journal_lines.append(
                JournalLine(account_id=row["account_id"], debit=0, credit=row["balance"], description="بستن حساب هزینه")
            )

    if not journal_lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "در این بازه هیچ فعالیت درآمد/هزینه‌ای برای بستن وجود ندارد")

    net_profit = Decimal(statement["net_profit"])
    retained_earnings_id = get_account(db, cc.RETAINED_EARNINGS).id
    if net_profit > 0:
        journal_lines.append(
            JournalLine(account_id=retained_earnings_id, debit=0, credit=net_profit, description="انتقال سود دوره به سود انباشته")
        )
    elif net_profit < 0:
        journal_lines.append(
            JournalLine(
                account_id=retained_earnings_id, debit=abs(net_profit), credit=0, description="انتقال زیان دوره به سود انباشته"
            )
        )

    journal_entry = make_journal_entry(
        db, data.closing_date, f"سند بستن دوره مالی تا تاریخ {data.closing_date}", "period_close", user, journal_lines
    )

    close = FiscalPeriodClose(
        closing_date=data.closing_date,
        net_profit=net_profit,
        notes=data.notes,
        journal_entry_id=journal_entry.id,
        created_by_id=user.id,
    )
    db.add(close)
    db.flush()
    db.refresh(close)
    return close
