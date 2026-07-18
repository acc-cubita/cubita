"""بستن دوره‌ی مالی — انتقال سود/زیان به سود انباشته و قفل‌شدن دوره.

این نقطه‌ای است که اشتباه در آن بی‌سروصدا می‌ماند: اگر علامت انتقال سود برعکس شود
ترازنامه هنوز متوازن به‌نظر می‌رسد ولی سود انباشته غلط است، و اگر قفل دوره کار نکند
کاربر می‌تواند سند را به دوره‌ی رسماً بسته‌شده برگرداند.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import JournalEntry
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.schemas.period_close import FiscalPeriodCloseIn
from app.services import chart_codes as cc
from app.services.common import get_account
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.period_close import assert_period_open, close_period
from app.services.reports import get_balance_sheet, get_income_statement
from tests.factories import main_warehouse, make_item

IN_PERIOD = date(2026, 3, 10)
CLOSING = date(2026, 3, 20)
AFTER = date(2026, 3, 25)


def trade(db, user, *, buy_qty, buy_cost, sell_qty, sell_price, when=IN_PERIOD):
    """یک چرخه‌ی خرید و فروش که سود یا زیان مشخصی تولید کند."""
    wh = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=when,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(buy_qty), unit_cost=Decimal(buy_cost))],
        ),
        user,
    )
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=when,
            warehouse_id=wh.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(sell_qty), unit_price=Decimal(sell_price))],
        ),
        user,
    )
    return item


def retained_earnings_balance(db, as_of=CLOSING) -> Decimal:
    sheet = get_balance_sheet(db, as_of)
    code = cc.RETAINED_EARNINGS
    for row in sheet["equity"]:
        if row["account_code"] == code:
            return Decimal(row["balance"])
    return Decimal(0)


# --- انتقال سود و زیان --------------------------------------------------------


def test_profit_is_credited_to_retained_earnings(db, user):
    trade(db, user, buy_qty=10, buy_cost=1_000_000, sell_qty=10, sell_price=3_000_000)
    profit_before = Decimal(get_income_statement(db, None, CLOSING)["net_profit"])
    assert profit_before == Decimal(20_000_000)

    close = close_period(db, FiscalPeriodCloseIn(closing_date=CLOSING, notes=""), user)

    assert Decimal(close.net_profit) == Decimal(20_000_000)
    assert retained_earnings_balance(db) == Decimal(20_000_000), "سود باید بستانکار سود انباشته شود"


def test_loss_is_debited_to_retained_earnings(db, user):
    """فروش زیر بهای تمام‌شده — علامت باید برعکس سود باشد."""
    trade(db, user, buy_qty=10, buy_cost=3_000_000, sell_qty=10, sell_price=1_000_000)
    assert Decimal(get_income_statement(db, None, CLOSING)["net_profit"]) == Decimal(-20_000_000)

    close = close_period(db, FiscalPeriodCloseIn(closing_date=CLOSING, notes=""), user)

    assert Decimal(close.net_profit) == Decimal(-20_000_000)
    assert retained_earnings_balance(db) == Decimal(-20_000_000), "زیان باید بدهکار سود انباشته شود"


def test_closing_entry_is_balanced_and_zeroes_income_and_expense(db, user):
    trade(db, user, buy_qty=10, buy_cost=1_000_000, sell_qty=10, sell_price=3_000_000)
    close = close_period(db, FiscalPeriodCloseIn(closing_date=CLOSING, notes=""), user)

    entry = db.get(JournalEntry, close.journal_entry_id)
    debit = sum((Decimal(line.debit) for line in entry.lines), Decimal(0))
    credit = sum((Decimal(line.credit) for line in entry.lines), Decimal(0))
    assert debit == credit, "سند بستن دوره نامتوازن است"
    assert entry.source_type == "period_close"

    # بعد از بستن، درآمد و هزینه‌ی همان بازه باید صفر شده باشند
    after = get_income_statement(db, None, CLOSING)
    assert Decimal(after["total_income"]) == 0
    assert Decimal(after["total_expenses"]) == 0
    assert Decimal(after["net_profit"]) == 0


# --- قفل شدن دوره -------------------------------------------------------------


def test_posting_into_closed_period_is_rejected(db, user):
    trade(db, user, buy_qty=5, buy_cost=1_000_000, sell_qty=5, sell_price=2_000_000)
    close_period(db, FiscalPeriodCloseIn(closing_date=CLOSING, notes=""), user)

    wh = main_warehouse(db)
    item = make_item(db)
    with pytest.raises(HTTPException) as exc:
        post_purchase_invoice(
            db,
            PurchaseInvoiceIn(
                invoice_date=IN_PERIOD,  # داخل دوره‌ی بسته‌شده
                warehouse_id=wh.id,
                lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_cost=Decimal(1_000_000))],
            ),
            user,
        )
    assert exc.value.status_code == 400
    assert "بسته شده" in str(exc.value.detail)


def test_posting_on_the_closing_date_itself_is_rejected(db, user):
    """مرز باید شامل خود روز بستن باشد (<=)، نه فقط قبل از آن."""
    trade(db, user, buy_qty=5, buy_cost=1_000_000, sell_qty=5, sell_price=2_000_000)
    close_period(db, FiscalPeriodCloseIn(closing_date=CLOSING, notes=""), user)

    with pytest.raises(HTTPException):
        assert_period_open(db, CLOSING)


def test_posting_after_closing_date_is_allowed(db, user):
    trade(db, user, buy_qty=5, buy_cost=1_000_000, sell_qty=5, sell_price=2_000_000)
    close_period(db, FiscalPeriodCloseIn(closing_date=CLOSING, notes=""), user)

    assert_period_open(db, AFTER)  # نباید خطا بدهد

    wh = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=AFTER,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_cost=Decimal(1_000_000))],
        ),
        user,
    )


def test_cannot_close_the_same_period_twice(db, user):
    trade(db, user, buy_qty=5, buy_cost=1_000_000, sell_qty=5, sell_price=2_000_000)
    close_period(db, FiscalPeriodCloseIn(closing_date=CLOSING, notes=""), user)

    with pytest.raises(HTTPException) as exc:
        close_period(db, FiscalPeriodCloseIn(closing_date=CLOSING, notes=""), user)
    assert exc.value.status_code == 400


def test_closing_with_no_activity_is_rejected(db, user):
    with pytest.raises(HTTPException) as exc:
        close_period(db, FiscalPeriodCloseIn(closing_date=CLOSING, notes=""), user)
    assert exc.value.status_code == 400
    assert "هیچ فعالیت" in str(exc.value.detail)
