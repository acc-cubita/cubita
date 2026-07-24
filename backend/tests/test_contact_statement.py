"""کارت حساب طرف‌حساب — گردشِ رویدادها، ماندهٔ در حال اجرا، ماندهٔ اول دوره، و علامت."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from uuid import uuid4

from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.schemas.returns import SalesReturnIn, SalesReturnLineIn
from app.schemas.treasury import TreasuryTransactionIn
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.reports import get_contact_statement
from app.services.returns import post_sales_return
from app.services.treasury import create_payment, create_receipt
from tests.factories import main_warehouse, make_contact, make_item


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


def test_customer_statement_running_balance(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    contact = make_contact(db, name="مشتری الف")
    _stock_in(db, user, item, wh, 100, 500_000)

    _sell(db, user, wh, item, contact, 1, 1_000_000, date(2026, 3, 1))
    create_receipt(
        db, TreasuryTransactionIn(transaction_date=date(2026, 3, 5), contact_id=contact.id, amount=Decimal(400_000)), user
    )
    _sell(db, user, wh, item, contact, 1, 2_000_000, date(2026, 3, 10))

    st = get_contact_statement(db, contact.id, None, None)
    assert [l["kind"] for l in st["lines"]] == ["sales_invoice", "receipt", "sales_invoice"]
    assert [l["balance"] for l in st["lines"]] == [Decimal(1_000_000), Decimal(600_000), Decimal(2_600_000)]
    assert st["total_debit"] == Decimal(3_000_000)
    assert st["total_credit"] == Decimal(400_000)
    assert st["closing_balance"] == Decimal(2_600_000)  # مثبت = مشتری به ما بدهکار است


def test_supplier_statement_is_negative(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 3, 1),
            warehouse_id=wh.id,
            contact_id=supplier.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_cost=Decimal(5_000_000))],
        ),
        user,
    )
    create_payment(
        db, TreasuryTransactionIn(transaction_date=date(2026, 3, 4), contact_id=supplier.id, amount=Decimal(2_000_000)), user
    )

    st = get_contact_statement(db, supplier.id, None, None)
    assert st["lines"][0]["credit"] == Decimal(5_000_000)  # خرید: بستانکار
    assert st["lines"][1]["debit"] == Decimal(2_000_000)  # پرداخت: بدهکار
    assert st["closing_balance"] == Decimal(-3_000_000)  # منفی = ما به او بدهکاریم


def test_opening_balance_with_date_filter(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    contact = make_contact(db)
    _stock_in(db, user, item, wh, 100, 500_000)
    _sell(db, user, wh, item, contact, 1, 1_000_000, date(2026, 1, 10))  # قبل از بازه
    _sell(db, user, wh, item, contact, 1, 2_000_000, date(2026, 3, 10))  # داخل بازه

    st = get_contact_statement(db, contact.id, date(2026, 2, 1), date(2026, 4, 1))
    assert st["opening_balance"] == Decimal(1_000_000)  # فروشِ دی‌ماه انتقالی است
    assert len(st["lines"]) == 1
    assert st["closing_balance"] == Decimal(3_000_000)


def test_return_shows_as_credit(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    contact = make_contact(db)
    _stock_in(db, user, item, wh, 100, 500_000)
    sale = _sell(db, user, wh, item, contact, 2, 1_000_000, date(2026, 3, 1))
    post_sales_return(
        db,
        SalesReturnIn(
            return_date=date(2026, 3, 8),
            sales_invoice_id=sale.id,
            lines=[SalesReturnLineIn(item_id=item.id, qty=Decimal(1))],
        ),
        user,
    )
    st = get_contact_statement(db, contact.id, None, None)
    kinds = [l["kind"] for l in st["lines"]]
    assert "sales_return" in kinds
    ret = next(l for l in st["lines"] if l["kind"] == "sales_return")
    assert ret["credit"] == Decimal(1_000_000)
    assert st["closing_balance"] == Decimal(1_000_000)  # ۲م منهای برگشتِ ۱م


def test_unknown_contact_404(db, user):
    with pytest.raises(HTTPException) as exc:
        get_contact_statement(db, uuid4(), None, None)
    assert exc.value.status_code == 404
