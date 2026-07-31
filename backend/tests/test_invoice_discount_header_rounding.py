"""تخفیفِ کلِ فاکتور (تسهیم در ردیف‌ها) و گِرد کردنِ مبلغِ نهایی.

تخفیفِ کل باید مثلِ تخفیفِ تجاری درآمد و پایه‌ی مالیات را کم کند و در برگشت هم
درست برگردد؛ گِرد کردن باید سند را متوازن نگه دارد و مبلغِ قابل‌پرداخت را تغییر دهد.
"""
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.accounting import Account, JournalEntry
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.schemas.returns import SalesReturnIn, SalesReturnLineIn
from app.services import chart_codes as cc
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.returns import post_sales_return
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 3, 15)


def _stock_in(db, user, item, wh, qty, unit_cost):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost))],
        ),
        user,
    )


def _entry(db, invoice) -> JournalEntry:
    return db.get(JournalEntry, invoice.journal_entry_id)


# --- اعتبارسنجی --------------------------------------------------------------

def test_negative_invoice_discount_rejected():
    with pytest.raises(ValidationError):
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id="00000000-0000-0000-0000-000000000001",
            invoice_discount=Decimal(-1),
            lines=[SalesInvoiceLineIn(item_id="00000000-0000-0000-0000-000000000002", qty=Decimal(1), unit_price=Decimal(1000))],
        )


def test_rounding_beyond_limit_rejected():
    with pytest.raises(ValidationError):
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id="00000000-0000-0000-0000-000000000001",
            rounding=Decimal(200_000),
            lines=[SalesInvoiceLineIn(item_id="00000000-0000-0000-0000-000000000002", qty=Decimal(1), unit_price=Decimal(1000))],
        )


def test_invoice_discount_over_gross_rejected(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 10, 100_000)
    with pytest.raises(Exception):  # HTTPException 400
        post_sales_invoice(
            db,
            SalesInvoiceIn(
                invoice_date=TODAY,
                warehouse_id=wh.id,
                invoice_discount=Decimal(2_000_000),  # بیش از خالصِ ۱٬۰۰۰٬۰۰۰
                lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(1_000_000))],
            ),
            user,
        )


# --- تسهیمِ تخفیفِ کل --------------------------------------------------------

def test_invoice_discount_reduces_net_and_tax(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 100, 600_000)
    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(10),
            invoice_discount=Decimal(500_000),
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_price=Decimal(1_000_000))],
        ),
        user,
    )
    # خالص = ۲٬۰۰۰٬۰۰۰ − ۵۰۰٬۰۰۰ = ۱٬۵۰۰٬۰۰۰
    assert inv.total_amount == Decimal(1_500_000)
    assert inv.invoice_discount == Decimal(500_000)
    assert inv.total_discount == Decimal(500_000)  # کلِ تخفیف (تسهیم‌شده)
    assert inv.tax_amount == Decimal(150_000)  # مالیات روی پایه‌ی پس از تخفیف


def test_invoice_discount_allocated_across_lines_exactly(db, user):
    wh = main_warehouse(db)
    a = make_item(db, name="الف")
    b = make_item(db, name="ب")
    _stock_in(db, user, a, wh, 100, 100_000)
    _stock_in(db, user, b, wh, 100, 100_000)
    # خالصِ ردیف‌ها: ۳۰۰٬۰۰۰ و ۱۰۰٬۰۰۰ → نسبت ۳:۱؛ تخفیفِ ۱۰۰٬۰۰۰ → ۷۵٬۰۰۰ و ۲۵٬۰۰۰
    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            invoice_discount=Decimal(100_000),
            lines=[
                SalesInvoiceLineIn(item_id=a.id, qty=Decimal(3), unit_price=Decimal(100_000)),
                SalesInvoiceLineIn(item_id=b.id, qty=Decimal(1), unit_price=Decimal(100_000)),
            ],
        ),
        user,
    )
    by_item = {l.item_id: l for l in inv.lines}
    assert by_item[a.id].discount == Decimal(75_000)
    assert by_item[b.id].discount == Decimal(25_000)
    # جمعِ تسهیم دقیقاً برابرِ تخفیفِ کل
    assert sum(l.discount for l in inv.lines) == Decimal(100_000)
    assert inv.total_amount == Decimal(300_000)  # ۴۰۰هزار − ۱۰۰هزار


def test_invoice_discount_refunds_correctly_on_return(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 100, 400_000)
    sale = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            invoice_discount=Decimal(400_000),  # روی خالصِ ۲٬۰۰۰٬۰۰۰ → واحدِ مؤثر ۸۰۰٬۰۰۰
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_price=Decimal(1_000_000))],
        ),
        user,
    )
    assert sale.total_amount == Decimal(1_600_000)
    ret = post_sales_return(
        db,
        SalesReturnIn(
            return_date=TODAY,
            sales_invoice_id=sale.id,
            lines=[SalesReturnLineIn(item_id=item.id, qty=Decimal(1))],
        ),
        user,
    )
    # یکی از دو عدد → نیمی از مبلغِ پس از تخفیفِ کل، نه قیمتِ فهرست
    assert ret.total_amount == Decimal(800_000)


# --- گِرد کردن ---------------------------------------------------------------

def test_rounding_down_balances_and_lowers_payable(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 100, 500_000)
    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(9),
            rounding=Decimal(-700),  # رند به پایین
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(1_000_000))],
        ),
        user,
    )
    assert inv.total_amount == Decimal(1_000_000)
    assert inv.tax_amount == Decimal(90_000)
    assert inv.rounding == Decimal(-700)

    entry = _entry(db, inv)
    assert sum(l.debit for l in entry.lines) == sum(l.credit for l in entry.lines)  # متوازن
    # بدهکارِ صندوق/دریافتنی = خالص + مالیات + گِرد = ۱٬۰۸۹٬۳۰۰
    assert max(l.debit for l in entry.lines) == Decimal(1_089_300)
    rounding_acc = db.query(Account).filter(Account.system_role == cc.SALES_ROUNDING).first()
    assert rounding_acc is not None
    rline = next(l for l in entry.lines if l.account_id == rounding_acc.id)
    assert rline.debit == Decimal(700)  # رند به پایین → بدهکارِ حسابِ گِرد


def test_rounding_up_credits_rounding_account(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 100, 500_000)
    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            rounding=Decimal(300),
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(999_700))],
        ),
        user,
    )
    entry = _entry(db, inv)
    assert sum(l.debit for l in entry.lines) == sum(l.credit for l in entry.lines)
    rounding_acc = db.query(Account).filter(Account.system_role == cc.SALES_ROUNDING).first()
    rline = next(l for l in entry.lines if l.account_id == rounding_acc.id)
    assert rline.credit == Decimal(300)  # رند به بالا → بستانکارِ حسابِ گِرد
    assert max(l.debit for l in entry.lines) == Decimal(1_000_000)  # قابل پرداختِ گِردشده


def test_no_header_discount_no_rounding_unchanged(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 100, 500_000)
    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(10),
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_price=Decimal(1_000_000))],
        ),
        user,
    )
    assert inv.invoice_discount == Decimal(0)
    assert inv.rounding == Decimal(0)
    assert inv.total_amount == Decimal(2_000_000)
    assert inv.tax_amount == Decimal(200_000)
