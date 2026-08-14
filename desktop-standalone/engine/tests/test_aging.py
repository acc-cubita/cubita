"""تحلیل سنیِ مطالبات/بدهی‌ها — سطل‌های سنی، اعمالِ FIFOِ تسویه، و اثرِ برگشت."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.schemas.returns import SalesReturnIn, SalesReturnLineIn
from app.schemas.treasury import TreasuryTransactionIn
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.reports import get_aging
from app.services.returns import post_sales_return
from app.services.treasury import create_payment, create_receipt
from tests.factories import main_warehouse, make_contact, make_item

AS_OF = date(2026, 6, 1)


def _stock_in(db, user, item, wh, qty, unit_cost, on=date(2026, 1, 1)):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=on,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost))],
        ),
        user,
    )


def _sell(db, user, wh, item, contact, qty, price, on):
    return post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=on,
            warehouse_id=wh.id,
            contact_id=contact.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_price=Decimal(price))],
        ),
        user,
    )


def _row(report, contact_id):
    return next((r for r in report["rows"] if r["contact_id"] == contact_id), None)


def test_receivable_aging_buckets(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    contact = make_contact(db, name="مشتری الف")
    _stock_in(db, user, item, wh, 100, 500_000)

    _sell(db, user, wh, item, contact, 1, 1_000_000, AS_OF - timedelta(days=100))  # بالای ۹۰
    _sell(db, user, wh, item, contact, 1, 2_000_000, AS_OF - timedelta(days=45))  # ۳۱–۶۰
    _sell(db, user, wh, item, contact, 1, 3_000_000, AS_OF - timedelta(days=10))  # جاری

    report = get_aging(db, "receivable", AS_OF)
    row = _row(report, contact.id)
    assert row is not None
    assert row["over_90"] == Decimal(1_000_000)
    assert row["d31_60"] == Decimal(2_000_000)
    assert row["current"] == Decimal(3_000_000)
    assert row["d61_90"] == Decimal(0)
    assert row["total"] == Decimal(6_000_000)
    assert report["grand_total"] == Decimal(6_000_000)


def test_receipt_applied_to_oldest_first(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    contact = make_contact(db, name="مشتری ب")
    _stock_in(db, user, item, wh, 100, 500_000)
    _sell(db, user, wh, item, contact, 1, 1_000_000, AS_OF - timedelta(days=100))
    _sell(db, user, wh, item, contact, 1, 2_000_000, AS_OF - timedelta(days=45))
    _sell(db, user, wh, item, contact, 1, 3_000_000, AS_OF - timedelta(days=10))

    create_receipt(
        db,
        TreasuryTransactionIn(transaction_date=AS_OF - timedelta(days=5), contact_id=contact.id, amount=Decimal(1_500_000)),
        user,
    )

    report = get_aging(db, "receivable", AS_OF)
    row = _row(report, contact.id)
    # ۱٬۵۰۰٬۰۰۰ اول قدیمی‌ترین (۱م) را کامل و ۵۰۰هزار از دومی را می‌بندد
    assert row["over_90"] == Decimal(0)
    assert row["d31_60"] == Decimal(1_500_000)
    assert row["current"] == Decimal(3_000_000)
    assert row["total"] == Decimal(4_500_000)


def test_return_reduces_outstanding(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    contact = make_contact(db, name="مشتری ج")
    _stock_in(db, user, item, wh, 100, 500_000)
    sale = _sell(db, user, wh, item, contact, 2, 1_000_000, AS_OF - timedelta(days=10))  # مانده ۲م، جاری

    post_sales_return(
        db,
        SalesReturnIn(
            return_date=AS_OF - timedelta(days=5),
            sales_invoice_id=sale.id,
            lines=[SalesReturnLineIn(item_id=item.id, qty=Decimal(1))],
        ),
        user,
    )

    report = get_aging(db, "receivable", AS_OF)
    row = _row(report, contact.id)
    assert row["current"] == Decimal(1_000_000)  # ۲م منهای برگشتِ ۱م
    assert row["total"] == Decimal(1_000_000)


def test_payable_aging_with_payment(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    # خریدِ اعتباری (شخص‌دار) → حساب پرداختنی
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=AS_OF - timedelta(days=100),
            warehouse_id=wh.id,
            contact_id=supplier.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_cost=Decimal(5_000_000))],
        ),
        user,
    )
    create_payment(
        db,
        TreasuryTransactionIn(transaction_date=AS_OF - timedelta(days=2), contact_id=supplier.id, amount=Decimal(2_000_000)),
        user,
    )

    report = get_aging(db, "payable", AS_OF)
    row = _row(report, supplier.id)
    assert row is not None
    assert row["over_90"] == Decimal(3_000_000)  # ۵م منهای پرداختِ ۲م
    assert row["total"] == Decimal(3_000_000)


def test_fully_paid_contact_absent(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    contact = make_contact(db, name="مشتری تسویه‌شده")
    _stock_in(db, user, item, wh, 100, 500_000)
    _sell(db, user, wh, item, contact, 1, 1_000_000, AS_OF - timedelta(days=20))
    create_receipt(
        db,
        TreasuryTransactionIn(transaction_date=AS_OF, contact_id=contact.id, amount=Decimal(1_000_000)),
        user,
    )
    report = get_aging(db, "receivable", AS_OF)
    assert _row(report, contact.id) is None  # مانده صفر → در گزارش نمی‌آید


def test_invalid_kind_rejected(db, user):
    with pytest.raises(HTTPException) as exc:
        get_aging(db, "nonsense", AS_OF)
    assert exc.value.status_code == 400
