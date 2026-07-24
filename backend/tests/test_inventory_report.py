"""ارزش‌گذاری موجودی انبار — تعداد و ارزش، حذف کالای خدماتی و موجودیِ صفر، تفکیک انبار."""
from datetime import date
from decimal import Decimal

from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.reports import get_inventory_report
from tests.factories import main_warehouse, other_warehouse, make_item

TODAY = date(2026, 3, 1)


def _buy(db, user, wh, item, qty, unit_cost, on=TODAY):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=on,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost))],
        ),
        user,
    )


def _row(report, item_id):
    return next((r for r in report["rows"] if r["item_id"] == item_id), None)


def test_qty_and_value(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _buy(db, user, wh, item, 10, 200_000)

    report = get_inventory_report(db, None, None)
    row = _row(report, item.id)
    assert row is not None
    assert row["qty_on_hand"] == Decimal(10)
    assert row["unit_cost"] == Decimal(200_000)
    assert row["stock_value"] == Decimal(2_000_000)
    assert report["total_value"] == Decimal(2_000_000)


def test_sale_reduces_on_hand(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _buy(db, user, wh, item, 10, 200_000)
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(4), unit_price=Decimal(500_000))],
        ),
        user,
    )
    report = get_inventory_report(db, None, None)
    row = _row(report, item.id)
    assert row["qty_on_hand"] == Decimal(6)
    assert row["stock_value"] == Decimal(1_200_000)  # ۶ × ۲۰۰٬۰۰۰


def test_service_item_excluded(db, user):
    wh = main_warehouse(db)
    service = make_item(db, name="خدمت نصب", is_service=True)
    # خدمت موجودی ندارد؛ حتی اگر رکورد دفتری نباشد، نباید در گزارش بیاید
    report = get_inventory_report(db, None, None)
    assert _row(report, service.id) is None


def test_zero_on_hand_excluded(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _buy(db, user, wh, item, 5, 100_000)
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(5), unit_price=Decimal(300_000))],
        ),
        user,
    )
    report = get_inventory_report(db, None, None)
    assert _row(report, item.id) is None  # موجودی صفر → در گزارش نیست


def test_warehouse_filter(db, user):
    main = main_warehouse(db)
    other = other_warehouse(db)
    item = make_item(db)
    _buy(db, user, main, item, 10, 200_000)
    _buy(db, user, other, item, 3, 200_000)

    all_wh = get_inventory_report(db, None, None)
    assert _row(all_wh, item.id)["qty_on_hand"] == Decimal(13)

    only_other = get_inventory_report(db, other.id, None)
    assert _row(only_other, item.id)["qty_on_hand"] == Decimal(3)
