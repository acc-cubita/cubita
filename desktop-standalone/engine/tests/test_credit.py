"""سقف اعتبار مشتری — مانده‌ی خالص، تأثیر دریافت و برگشت، و پرچمِ over_limit."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.schemas.returns import SalesReturnIn, SalesReturnLineIn
from app.schemas.treasury import TreasuryTransactionIn
from app.services.credit import customer_outstanding, get_credit_status
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.returns import post_sales_return
from app.services.treasury import create_receipt
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


def _sell(db, user, wh, item, contact, qty, price, on=date(2026, 3, 1)):
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


def test_outstanding_is_net_of_receipts_and_returns(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    contact = make_contact(db)
    _stock_in(db, user, item, wh, 100, 500_000)

    _sell(db, user, wh, item, contact, 3, 1_000_000)  # +۳م
    create_receipt(
        db,
        TreasuryTransactionIn(transaction_date=date(2026, 3, 5), contact_id=contact.id, amount=Decimal(1_000_000)),
        user,
    )  # -۱م
    sale = _sell(db, user, wh, item, contact, 2, 1_000_000, on=date(2026, 3, 6))  # +۲م
    post_sales_return(
        db,
        SalesReturnIn(
            return_date=date(2026, 3, 8),
            sales_invoice_id=sale.id,
            lines=[SalesReturnLineIn(item_id=item.id, qty=Decimal(1))],
        ),
        user,
    )  # -۱م

    assert customer_outstanding(db, contact.id) == Decimal(3_000_000)


def test_credit_status_within_limit(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    contact = make_contact(db, credit_limit=10_000_000)
    _stock_in(db, user, item, wh, 100, 500_000)
    _sell(db, user, wh, item, contact, 4, 1_000_000)  # ۴م < ۱۰م

    status = get_credit_status(db, contact.id)
    assert status["credit_limit"] == Decimal(10_000_000)
    assert status["outstanding"] == Decimal(4_000_000)
    assert status["available"] == Decimal(6_000_000)
    assert status["over_limit"] is False


def test_credit_status_over_limit(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    contact = make_contact(db, credit_limit=3_000_000)
    _stock_in(db, user, item, wh, 100, 500_000)
    _sell(db, user, wh, item, contact, 5, 1_000_000)  # ۵م > ۳م

    status = get_credit_status(db, contact.id)
    assert status["outstanding"] == Decimal(5_000_000)
    assert status["available"] == Decimal(-2_000_000)
    assert status["over_limit"] is True


def test_zero_limit_means_no_limit(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    contact = make_contact(db, credit_limit=0)
    _stock_in(db, user, item, wh, 100, 500_000)
    _sell(db, user, wh, item, contact, 9, 1_000_000)  # مبلغِ زیاد

    status = get_credit_status(db, contact.id)
    assert status["outstanding"] == Decimal(9_000_000)
    assert status["over_limit"] is False  # سقفِ صفر هیچ‌وقت over نمی‌شود


def test_voided_invoice_excluded(db, user):
    from app.services.voiding import void_sales_invoice

    wh = main_warehouse(db)
    item = make_item(db)
    contact = make_contact(db, credit_limit=1_000_000)
    _stock_in(db, user, item, wh, 100, 500_000)
    sale = _sell(db, user, wh, item, contact, 5, 1_000_000)  # ۵م > ۱م
    assert get_credit_status(db, contact.id)["over_limit"] is True

    void_sales_invoice(db, sale.id, reason="اشتباه", user=user)
    status = get_credit_status(db, contact.id)
    assert status["outstanding"] == Decimal(0)
    assert status["over_limit"] is False


def test_unknown_contact_404(db, user):
    with pytest.raises(HTTPException) as exc:
        get_credit_status(db, uuid4())
    assert exc.value.status_code == 404
