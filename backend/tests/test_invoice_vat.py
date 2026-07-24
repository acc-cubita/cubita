"""مالیات بر ارزش افزوده روی فاکتور فروش و خرید — صحتِ سند دوطرفه و گزارش."""
from datetime import date
from decimal import Decimal

from app.models.accounting import Account, JournalEntry
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.schemas.returns import PurchaseReturnIn, PurchaseReturnLineIn, SalesReturnIn, SalesReturnLineIn
from app.services import chart_codes as cc
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.reports import get_vat_report
from app.services.returns import post_purchase_return, post_sales_return
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 3, 15)


def _entry(db, invoice) -> JournalEntry:
    return db.get(JournalEntry, invoice.journal_entry_id)


def _is_balanced(entry: JournalEntry) -> bool:
    return sum(l.debit for l in entry.lines) == sum(l.credit for l in entry.lines)


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


def test_sales_invoice_with_vat_posts_output_tax(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 10, 1_000_000)

    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(10),
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_price=Decimal(5_000_000))],
        ),
        user,
    )

    # خالص ۱۰٬۰۰۰٬۰۰۰ → مالیات ۱۰٪ = ۱٬۰۰۰٬۰۰۰
    assert inv.total_amount == Decimal(10_000_000)
    assert inv.tax_amount == Decimal(1_000_000)

    entry = _entry(db, inv)
    assert _is_balanced(entry)
    vat_acc = db.query(Account).filter(Account.system_role == cc.VAT_PAYABLE).first()
    assert vat_acc is not None
    vat_lines = [l for l in entry.lines if l.account_id == vat_acc.id]
    assert len(vat_lines) == 1
    assert vat_lines[0].credit == Decimal(1_000_000)
    # بدهکارِ دریافتنی باید خالص + مالیات باشد
    assert max(l.debit for l in entry.lines) == Decimal(11_000_000)


def test_purchase_invoice_with_vat_posts_input_tax(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    inv = post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(9),
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(4), unit_cost=Decimal(2_500_000))],
        ),
        user,
    )

    assert inv.total_amount == Decimal(10_000_000)
    assert inv.tax_amount == Decimal(900_000)  # ۹٪
    entry = _entry(db, inv)
    assert _is_balanced(entry)
    vat_acc = db.query(Account).filter(Account.system_role == cc.VAT_RECEIVABLE).first()
    assert vat_acc is not None
    vat_lines = [l for l in entry.lines if l.account_id == vat_acc.id]
    assert len(vat_lines) == 1
    assert vat_lines[0].debit == Decimal(900_000)


def test_zero_rate_adds_no_vat_line(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 10, 1_000_000)
    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(2_000_000))],
        ),
        user,
    )
    assert inv.tax_amount == Decimal(0)
    entry = _entry(db, inv)
    vat_acc = db.query(Account).filter(Account.system_role == cc.VAT_PAYABLE).first()
    if vat_acc is not None:  # اگر از فاکتور دیگری ساخته شده باشد، نباید در این سند ردیفی داشته باشد
        assert not any(l.account_id == vat_acc.id for l in entry.lines)


def test_vat_report_nets_output_minus_input(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    # خرید با مالیات ۱۰٪ روی ۱۰٬۰۰۰٬۰۰۰ → ورودی ۱٬۰۰۰٬۰۰۰
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(10),
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(1_000_000))],
        ),
        user,
    )
    # فروش با مالیات ۱۰٪ روی ۱۵٬۰۰۰٬۰۰۰ → خروجی ۱٬۵۰۰٬۰۰۰
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(10),
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(5), unit_price=Decimal(3_000_000))],
        ),
        user,
    )

    rep = get_vat_report(db, None, None)
    assert rep["output_vat"] == Decimal(1_500_000)
    assert rep["input_vat"] == Decimal(1_000_000)
    assert rep["net_vat"] == Decimal(500_000)


def test_sales_return_reverses_output_vat(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 10, 1_000_000)
    inv = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(10),
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(4), unit_price=Decimal(5_000_000))],
        ),
        user,
    )
    ret = post_sales_return(
        db,
        SalesReturnIn(
            return_date=TODAY,
            sales_invoice_id=inv.id,
            lines=[SalesReturnLineIn(item_id=item.id, qty=Decimal(1))],
        ),
        user,
    )
    # خالصِ برگشتی ۵٬۰۰۰٬۰۰۰ → مالیات ۱۰٪ = ۵۰۰٬۰۰۰
    assert ret.tax_amount == Decimal(500_000)
    entry = _entry(db, ret)
    assert _is_balanced(entry)
    vat_acc = db.query(Account).filter(Account.system_role == cc.VAT_PAYABLE).first()
    vat_lines = [l for l in entry.lines if l.account_id == vat_acc.id]
    # برگشتِ فروش، مالیاتِ پرداختنی را بدهکار می‌کند (کاهش بدهی)
    assert len(vat_lines) == 1 and vat_lines[0].debit == Decimal(500_000)
    # مشتری کل ۵٬۵۰۰٬۰۰۰ پس می‌گیرد
    assert max(l.credit for l in entry.lines) == Decimal(5_500_000)


def test_purchase_return_reverses_input_vat(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    inv = post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(10),
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(4), unit_cost=Decimal(2_500_000))],
        ),
        user,
    )
    ret = post_purchase_return(
        db,
        PurchaseReturnIn(
            return_date=TODAY,
            purchase_invoice_id=inv.id,
            lines=[PurchaseReturnLineIn(item_id=item.id, qty=Decimal(2))],
        ),
        user,
    )
    assert ret.tax_amount == Decimal(500_000)  # خالص ۵٬۰۰۰٬۰۰۰ × ۱۰٪
    entry = _entry(db, ret)
    assert _is_balanced(entry)
    vat_acc = db.query(Account).filter(Account.system_role == cc.VAT_RECEIVABLE).first()
    vat_lines = [l for l in entry.lines if l.account_id == vat_acc.id]
    # برگشتِ خرید، اعتبار مالیاتی را بستانکار می‌کند (کاهش دارایی)
    assert len(vat_lines) == 1 and vat_lines[0].credit == Decimal(500_000)


def test_vat_report_subtracts_returns(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    # فروش ۱۰٬۰۰۰٬۰۰۰ با مالیات ۱٬۰۰۰٬۰۰۰، سپس برگشتِ چهار واحد از ده واحد
    _stock_in(db, user, item, wh, 20, 500_000)
    sale = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(10),
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_price=Decimal(1_000_000))],
        ),
        user,
    )
    post_sales_return(
        db,
        SalesReturnIn(
            return_date=TODAY,
            sales_invoice_id=sale.id,
            lines=[SalesReturnLineIn(item_id=item.id, qty=Decimal(4))],
        ),
        user,
    )
    rep = get_vat_report(db, None, None)
    # خروجی خام ۱٬۰۰۰٬۰۰۰ منهای برگشتِ ۴۰۰٬۰۰۰ = ۶۰۰٬۰۰۰
    assert rep["sales_returns_vat"] == Decimal(400_000)
    assert rep["output_vat"] == Decimal(600_000)
