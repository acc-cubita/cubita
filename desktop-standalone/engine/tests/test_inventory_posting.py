"""ثبت فاکتور فروش/خرید — کنترل موجودی و بهای تمام‌شده."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.services.inventory import get_stock_qty, post_purchase_invoice, post_sales_invoice
from tests.factories import main_warehouse, make_item, other_warehouse

TODAY = date(2026, 3, 15)


def stock_in(db, user, item, wh, qty, unit_cost):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost))],
        ),
        user,
    )


# --- کنترل کفایت موجودی -------------------------------------------------------


def test_sale_exceeding_stock_is_rejected(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    stock_in(db, user, item, wh, 5, 1_000_000)

    with pytest.raises(HTTPException) as exc:
        post_sales_invoice(
            db,
            SalesInvoiceIn(
                invoice_date=TODAY,
                warehouse_id=wh.id,
                lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(6), unit_price=Decimal(2_000_000))],
            ),
            user,
        )
    assert exc.value.status_code == 400
    assert "کافی نیست" in str(exc.value.detail)


def test_sale_of_exactly_available_stock_is_allowed(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    stock_in(db, user, item, wh, 5, 1_000_000)

    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(5), unit_price=Decimal(2_000_000))],
        ),
        user,
    )
    assert get_stock_qty(db, item.id, wh.id) == 0


def test_duplicate_lines_of_same_item_cannot_exceed_stock(db, user):
    """باگ تأییدشده: کنترل موجودی هر ردیف را جدا می‌سنجد و بین ردیف‌ها جمع نمی‌زند.

    با موجودی ۱۰، فاکتوری با دو ردیف ۶تایی از همان کالا مجموعاً ۱۲ عدد می‌فروشد.
    هر ردیف جداگانه در برابر همان ۱۰ سنجیده می‌شود و پاس می‌شود. این نیازی به
    همزمانی ندارد — تک‌نخی هم رخ می‌دهد.
    """
    wh = main_warehouse(db)
    item = make_item(db)
    stock_in(db, user, item, wh, 10, 1_000_000)

    with pytest.raises(HTTPException) as exc:
        post_sales_invoice(
            db,
            SalesInvoiceIn(
                invoice_date=TODAY,
                warehouse_id=wh.id,
                lines=[
                    SalesInvoiceLineIn(item_id=item.id, qty=Decimal(6), unit_price=Decimal(2_000_000)),
                    SalesInvoiceLineIn(item_id=item.id, qty=Decimal(6), unit_price=Decimal(2_000_000)),
                ],
            ),
            user,
        )
    assert exc.value.status_code == 400
    assert "کافی نیست" in str(exc.value.detail)

    # و مهم‌تر: موجودی نباید منفی شده باشد
    assert get_stock_qty(db, item.id, wh.id) == Decimal(10)


def test_stock_is_tracked_per_warehouse(db, user):
    """موجودی انبار الف نباید فروش از انبار ب را مجاز کند."""
    main, online = main_warehouse(db), other_warehouse(db)
    item = make_item(db)
    stock_in(db, user, item, main, 10, 1_000_000)

    with pytest.raises(HTTPException) as exc:
        post_sales_invoice(
            db,
            SalesInvoiceIn(
                invoice_date=TODAY,
                warehouse_id=online.id,
                lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(1), unit_price=Decimal(2_000_000))],
            ),
            user,
        )
    assert exc.value.status_code == 400


def test_service_items_are_exempt_from_stock_checks(db, user):
    """خدمات موجودی ندارند و نباید هرگز به‌خاطر کسری رد شوند."""
    wh = main_warehouse(db)
    service = make_item(db, name="خدمات", is_service=True)

    invoice = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[SalesInvoiceLineIn(item_id=service.id, qty=Decimal(999), unit_price=Decimal(1_000_000))],
        ),
        user,
    )
    assert Decimal(invoice.total_cost) == 0


# --- میانگین موزون بهای تمام‌شده ----------------------------------------------


def test_weighted_average_cost_after_second_purchase(db, user):
    """۱۰ تا × ۱٬۰۰۰٬۰۰۰ سپس ۱۰ تا × ۲٬۰۰۰٬۰۰۰ باید میانگین ۱٬۵۰۰٬۰۰۰ بدهد."""
    wh = main_warehouse(db)
    item = make_item(db)

    stock_in(db, user, item, wh, 10, 1_000_000)
    db.refresh(item)
    assert Decimal(item.average_cost) == Decimal(1_000_000)

    stock_in(db, user, item, wh, 10, 2_000_000)
    db.refresh(item)
    assert Decimal(item.average_cost) == Decimal(1_500_000)


def test_cogs_uses_average_cost_not_last_purchase_price(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    stock_in(db, user, item, wh, 10, 1_000_000)
    stock_in(db, user, item, wh, 10, 2_000_000)  # میانگین = ۱٬۵۰۰٬۰۰۰

    invoice = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(4), unit_price=Decimal(5_000_000))],
        ),
        user,
    )
    assert Decimal(invoice.total_cost) == Decimal(6_000_000), "بهای تمام‌شده باید ۴ × میانگین ۱٬۵۰۰٬۰۰۰ باشد"


def test_average_cost_survives_purchase_while_stock_is_zero(db, user):
    """مسیر new_qty <= 0 در به‌روزرسانی میانگین.

    اگر موجودی کل صفر باشد و خرید تازه‌ای بیاید، میانگین باید همان بهای خرید جدید
    شود — نه اینکه مقدار قبلی بی‌صدا حفظ شود.
    """
    wh = main_warehouse(db)
    item = make_item(db)
    stock_in(db, user, item, wh, 5, 1_000_000)
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(5), unit_price=Decimal(2_000_000))],
        ),
        user,
    )
    assert get_stock_qty(db, item.id, wh.id) == 0

    stock_in(db, user, item, wh, 4, 3_000_000)
    db.refresh(item)
    assert Decimal(item.average_cost) == Decimal(3_000_000)
