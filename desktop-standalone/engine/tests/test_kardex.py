"""کاردکس کالا — ورود/خروج، موجودیِ در حال اجرا، فیلتر انبار/تاریخ و ماندهٔ اول دوره."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.reports import get_kardex
from tests.factories import main_warehouse, other_warehouse, make_item

JAN = date(2026, 1, 10)
MAR = date(2026, 3, 10)


def _buy(db, user, wh, item, qty, unit_cost, on):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=on,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost))],
        ),
        user,
    )


def _sell(db, user, wh, item, qty, price, on):
    return post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=on,
            warehouse_id=wh.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_price=Decimal(price))],
        ),
        user,
    )


def test_in_out_and_running_balance(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _buy(db, user, wh, item, 10, 200_000, MAR)
    _sell(db, user, wh, item, 4, 500_000, MAR)

    k = get_kardex(db, item.id, None, None, None)
    assert k["item_id"] == item.id
    assert [l["source_type"] for l in k["lines"]] == ["purchase_invoice", "sales_invoice"]
    assert k["lines"][0]["qty_in"] == Decimal(10)
    assert k["lines"][0]["balance_qty"] == Decimal(10)
    assert k["lines"][1]["qty_out"] == Decimal(4)
    assert k["lines"][1]["balance_qty"] == Decimal(6)
    assert k["total_in"] == Decimal(10)
    assert k["total_out"] == Decimal(4)
    assert k["closing_qty"] == Decimal(6)


def test_source_labels_are_persian(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _buy(db, user, wh, item, 5, 100_000, MAR)
    k = get_kardex(db, item.id, None, None, None)
    assert k["lines"][0]["source_label"] == "فاکتور خرید"


def test_opening_qty_with_date_filter(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _buy(db, user, wh, item, 10, 200_000, JAN)  # قبل از بازه
    _buy(db, user, wh, item, 3, 200_000, MAR)  # داخل بازه

    k = get_kardex(db, item.id, None, date(2026, 2, 1), date(2026, 4, 1))
    assert k["opening_qty"] == Decimal(10)
    assert len(k["lines"]) == 1
    assert k["lines"][0]["balance_qty"] == Decimal(13)  # از ماندهٔ اول دوره ادامه می‌دهد
    assert k["closing_qty"] == Decimal(13)


def test_warehouse_filter(db, user):
    main = main_warehouse(db)
    other = other_warehouse(db)
    item = make_item(db)
    _buy(db, user, main, item, 10, 200_000, MAR)
    _buy(db, user, other, item, 3, 200_000, MAR)

    assert get_kardex(db, item.id, None, None, None)["closing_qty"] == Decimal(13)
    only_other = get_kardex(db, item.id, other.id, None, None)
    assert only_other["closing_qty"] == Decimal(3)
    assert len(only_other["lines"]) == 1


def test_unknown_item_404(db, user):
    with pytest.raises(HTTPException) as exc:
        get_kardex(db, uuid4(), None, None, None)
    assert exc.value.status_code == 404
