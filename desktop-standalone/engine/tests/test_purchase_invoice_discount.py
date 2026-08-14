"""تخفیفِ کلِ فاکتور خرید — تسهیم در ردیف‌ها، اثر بر ارزش‌گذاریِ موجودی و اعتبارِ مالیاتی."""
from datetime import date
from decimal import Decimal

import pytest

from app.models.accounting import Account, JournalEntry
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.schemas.returns import PurchaseReturnIn, PurchaseReturnLineIn
from app.services import chart_codes as cc
from app.services.inventory import post_purchase_invoice
from app.services.reports import get_inventory_report
from app.services.returns import post_purchase_return
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 3, 15)


def test_invoice_discount_lowers_inventory_valuation(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    # ۱۰ عدد × ۱۰۰٬۰۰۰ = ۱٬۰۰۰٬۰۰۰ با تخفیفِ کلِ ۲۰۰٬۰۰۰ → خالص ۸۰۰٬۰۰۰ یعنی واحدی ۸۰٬۰۰۰
    inv = post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            invoice_discount=Decimal(200_000),
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(100_000))],
        ),
        user,
    )
    assert inv.invoice_discount == Decimal(200_000)
    assert inv.total_discount == Decimal(200_000)
    assert inv.total_amount == Decimal(800_000)

    report = get_inventory_report(db, None, None)
    row = next(r for r in report["rows"] if r["item_id"] == item.id)
    assert row["unit_cost"] == Decimal(80_000)  # پس از تخفیفِ کل


def test_invoice_discount_reduces_tax_credit(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    inv = post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(10),
            invoice_discount=Decimal(500_000),
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_cost=Decimal(1_000_000))],
        ),
        user,
    )
    # خالص ۱٬۵۰۰٬۰۰۰ → اعتبار مالیاتی ۱۵۰٬۰۰۰
    assert inv.total_amount == Decimal(1_500_000)
    assert inv.tax_amount == Decimal(150_000)
    entry = db.get(JournalEntry, inv.journal_entry_id)
    assert sum(l.debit for l in entry.lines) == sum(l.credit for l in entry.lines)
    vat = db.query(Account).filter(Account.system_role == cc.VAT_RECEIVABLE).first()
    vat_line = next(l for l in entry.lines if l.account_id == vat.id)
    assert vat_line.debit == Decimal(150_000)


def test_invoice_discount_allocated_and_refunded_on_return(db, user):
    wh = main_warehouse(db)
    a = make_item(db, name="الف")
    b = make_item(db, name="ب")
    # خالصِ ردیف‌ها ۳۰۰هزار و ۱۰۰هزار (۳:۱)؛ تخفیفِ ۱۰۰هزار → ۷۵هزار و ۲۵هزار
    inv = post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            invoice_discount=Decimal(100_000),
            lines=[
                PurchaseInvoiceLineIn(item_id=a.id, qty=Decimal(3), unit_cost=Decimal(100_000)),
                PurchaseInvoiceLineIn(item_id=b.id, qty=Decimal(1), unit_cost=Decimal(100_000)),
            ],
        ),
        user,
    )
    by_item = {l.item_id: l for l in inv.lines}
    assert by_item[a.id].discount == Decimal(75_000)
    assert by_item[b.id].discount == Decimal(25_000)
    assert inv.total_amount == Decimal(300_000)

    # برگشتِ کلِ کالای «الف» (۳ عدد) → باید بهای پس از تخفیف (۲۲۵هزار) برگردد، نه ۳۰۰هزار
    ret = post_purchase_return(
        db,
        PurchaseReturnIn(
            return_date=TODAY,
            purchase_invoice_id=inv.id,
            lines=[PurchaseReturnLineIn(item_id=a.id, qty=Decimal(3))],
        ),
        user,
    )
    assert ret.total_amount == Decimal(225_000)


def test_invoice_discount_over_gross_rejected(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    with pytest.raises(Exception):
        post_purchase_invoice(
            db,
            PurchaseInvoiceIn(
                invoice_date=TODAY,
                warehouse_id=wh.id,
                invoice_discount=Decimal(5_000_000),
                lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_cost=Decimal(1_000_000))],
            ),
            user,
        )
